"""Opt-in local LLM pass. The model only *finds* strings — its output text is
never used as the redaction. Found strings are mapped back onto every
whole-word occurrence in the original text; anything not present verbatim is
dropped, so a hallucinating model can add redactions but never alter text.
"""
from __future__ import annotations

import json
import re
import time
from typing import Protocol

from scrubboard.redact import Entity

# Prompt format from the naazimsnh02/qwen3-0.6b-pii-detector model card.
INLINE_PROMPT = ("Analyze the following medical_record from the healthcare domain (US locale) and identify "
                 "all PII (Personally Identifiable Information) and PHI (Protected Health Information) "
                 "entities.\n\nText: {text}\n\nProvide the output with inline tags in the format: [entity]label")
_INLINE_TAG = re.compile(r"\[([^\[\]\n]{1,200})\]([A-Za-z][A-Za-z_]{1,40})")
_THINK = re.compile(r"<think>.*?</think>", re.S)
JSON_SPANS_SCHEMA = {
    "type": "array",
    "items": {"type": "object",
              "properties": {"text": {"type": "string"}, "label": {"type": "string"}},
              "required": ["text", "label"]},
}


class ChatBackend(Protocol):
    def chat(self, payload: dict, deadline: float) -> str:
        ...


def parse_inline_tags(output: str) -> list[tuple[str, str]]:
    output = _THINK.sub("", output)
    return [(m.group(1).strip(), m.group(2)) for m in _INLINE_TAG.finditer(output)]


def parse_json_spans(output: str) -> list[tuple[str, str]]:
    output = _THINK.sub("", output)
    start, end = output.find("["), output.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(output[start:end + 1])
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    return [(str(d["text"]).strip(), str(d["label"])) for d in data
            if isinstance(d, dict) and d.get("text") and d.get("label")]


def chunk_text(text: str, max_chars: int) -> list[str]:
    """Split on line/sentence boundaries into chunks of at most max_chars."""
    chunks: list[str] = []
    start, n = 0, len(text)
    while start < n:
        end = min(n, start + max_chars)
        if end < n:
            window = text[start:end]
            cut = max(window.rfind("\n"), window.rfind(". "))
            if cut >= max_chars // 2:
                end = start + cut + 1
        chunks.append(text[start:end])
        start = end
    return chunks


def map_to_entities(text: str, found: list[tuple[str, str]], source: str) -> list[Entity]:
    out: list[Entity] = []
    for value, label in dict.fromkeys(found):
        if len(value) < 3 and not any(c.isdigit() for c in value):
            continue  # too short to map safely ("he", "Dr")
        matches = list(re.finditer(rf"(?<!\w){re.escape(value)}(?!\w)", text))
        if not matches:  # the model may have normalized whitespace
            flexible = r"\s+".join(re.escape(p) for p in value.split())
            matches = list(re.finditer(rf"(?<!\w){flexible}(?!\w)", text))
        out.extend(Entity(m.start(), m.end(), label, 0.7, source=source) for m in matches)
    return out


class LLMEngine:
    def __init__(self, backend: ChatBackend, entry: dict, name: str, closer=None):
        self._backend = backend
        self.entry = entry
        self.name = name
        self._closer = closer

    def predict(self, text: str, deadline: float) -> list[Entity]:
        inline = self.entry["parser"] == "inline_tags"
        found: list[tuple[str, str]] = []
        for chunk in chunk_text(text, self.entry["chunk_chars"]):
            if time.monotonic() >= deadline:
                raise TimeoutError("LLM deadline reached")
            output = self._backend.chat(self._payload(chunk, inline), deadline)
            found += parse_inline_tags(output) if inline else parse_json_spans(output)
        return map_to_entities(text, found, self.name)

    @staticmethod
    def _payload(chunk: str, inline: bool) -> dict:
        if inline:
            return {"messages": [{"role": "user", "content": INLINE_PROMPT.format(text=chunk)}],
                    "temperature": 0, "max_tokens": len(chunk) // 3 + 64,
                    "chat_template_kwargs": {"enable_thinking": False}}
        # Ministral-3B-PII bakes its extraction prompt into the chat template.
        return {"messages": [{"role": "user", "content": chunk}], "temperature": 0, "max_tokens": 768,
                "response_format": {"type": "json_object", "schema": JSON_SPANS_SCHEMA}}

    def close(self) -> None:
        if self._closer is not None:
            self._closer()
