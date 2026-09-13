import os
import sys
import time

import pytest

from privatecopy.config import PrivateCopyConfig
from privatecopy.llm import create_llm_engine
from privatecopy.llm.engine import LLMEngine, chunk_text, map_to_entities, parse_inline_tags, parse_json_spans
from privatecopy.llm.runtime import ChatClient, LlamaServer
from privatecopy.models.manifest import LLM_CATALOG

FAKE_SERVER = os.path.join(os.path.dirname(__file__), "fake_llama_server.py")
QWEN = LLM_CATALOG["qwen3-0.6b-pii-q4km"]


def test_parse_inline_tags():
    out = "My name is [John Smith]first_name and my SSN is [123-45-6789]ssn."
    assert parse_inline_tags(out) == [("John Smith", "first_name"), ("123-45-6789", "ssn")]


def test_parse_inline_tags_ignores_thinking_and_placeholders():
    out = "<think>[x]name</think>Seen [DATE 2024] by [Ann Lee]first_name"
    assert parse_inline_tags(out) == [("Ann Lee", "first_name")]


def test_parse_json_spans():
    out = 'Here: [{"text": "Maria", "label": "first_name"}, {"bad": 1}] done'
    assert parse_json_spans(out) == [("Maria", "first_name")]
    assert parse_json_spans("not json") == []


def test_map_to_entities_whole_words_only():
    text = "John saw John. Johnson waved."
    ents = map_to_entities(text, [("John", "first_name"), ("Zed", "last_name"), ("a", "x")], "llm")
    assert [(e.start, e.end, e.label) for e in ents] == [(0, 4, "FIRST_NAME"), (9, 13, "FIRST_NAME")]


def test_map_to_entities_tolerates_whitespace_changes():
    ents = map_to_entities("Mary\n  Smith came", [("Mary Smith", "name")], "llm")
    assert [(e.start, e.end) for e in ents] == [(0, 12)]


def test_chunk_text_covers_everything():
    text = "line of text.\n" * 500
    chunks = chunk_text(text, 1000)
    assert "".join(chunks) == text
    assert all(len(c) <= 1000 for c in chunks)


@pytest.fixture
def server(tmp_path):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"gguf")
    srv = LlamaServer([sys.executable, FAKE_SERVER], str(model), ctx_size=2048, idle_unload_s=0)
    yield srv
    srv.close()


def test_engine_end_to_end_with_fake_server(server):
    engine = LLMEngine(server, QWEN, "fake")
    ents = engine.predict("Seen by Zelda today; Zelda again.", deadline=time.monotonic() + 30)
    assert [(e.start, e.end, e.label) for e in ents] == [(8, 13, "FIRST_NAME"), (21, 26, "FIRST_NAME")]


def test_deadline_raises_timeout(server, monkeypatch):
    monkeypatch.setenv("FAKE_LLAMA_DELAY", "0.5")
    server.ensure_running()
    with pytest.raises(TimeoutError):
        LLMEngine(server, QWEN, "fake").predict("Zelda " * 50, deadline=time.monotonic() + 0.3)


def test_wrong_api_key_is_rejected(server):
    server.ensure_running()
    bad = ChatClient("127.0.0.1", server.port, "wrong-key")
    with pytest.raises(RuntimeError, match="401"):
        bad.chat({"messages": [{"role": "user", "content": "Text: x\n\nProvide"}]}, time.monotonic() + 5)


def test_stop_and_restart(server):
    server.ensure_running()
    first = server.pid
    server.stop()
    assert server.pid is None
    server.ensure_running()
    assert server.pid and server.pid != first


def test_idle_unload(tmp_path):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"gguf")
    srv = LlamaServer([sys.executable, FAKE_SERVER], str(model), ctx_size=2048, idle_unload_s=0.5,
                      idle_check_s=0.1)
    try:
        srv.ensure_running()
        assert srv.pid
        time.sleep(1.5)
        assert srv.pid is None
    finally:
        srv.close()


def test_create_engine_reports_missing_pieces(tmp_path):
    cfg = PrivateCopyConfig(models_dir=str(tmp_path), llm_server_path=str(tmp_path / "nope"))
    with pytest.raises(FileNotFoundError, match="download-model --llm"):
        create_llm_engine(cfg)
    model = tmp_path / "llm" / QWEN["file"]
    model.parent.mkdir()
    model.write_bytes(b"gguf")
    with pytest.raises(RuntimeError, match="llama-server not found"):
        create_llm_engine(cfg)
