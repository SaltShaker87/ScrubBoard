import pytest

from privatecopy.config import PrivateCopyConfig
from privatecopy.models.base import PIIModel
from privatecopy.pipeline import NotProtectedError, RedactionPipeline
from privatecopy.redact import Entity


class FakeNER(PIIModel):
    name = "fake-ner"

    def __init__(self, targets: list[tuple[str, str]]):
        self.targets = targets

    @property
    def labels(self) -> list[str]:
        return [label for _, label in self.targets]

    def predict(self, text: str, threshold: float = 0.5) -> list[Entity]:
        out = []
        for word, label in self.targets:
            start = text.find(word)
            while start != -1:
                out.append(Entity(start, start + len(word), label, 0.9))
                start = text.find(word, start + 1)
        return out


class FakeLLM:
    name = "fake-llm"

    def __init__(self, behaviour: str):
        self.behaviour = behaviour

    def predict(self, text: str, deadline: float) -> list[Entity]:
        if self.behaviour == "timeout":
            raise TimeoutError
        if self.behaviour == "error":
            raise ValueError("boom")
        s = text.find("Zelda")
        return [Entity(s, s + 5, "first_name", 0.8)] if s >= 0 else []


def cfg(**kw) -> PrivateCopyConfig:
    return PrivateCopyConfig(ner_model="openmed-44m", **kw)


def test_rules_and_ner_combine():
    p = RedactionPipeline(cfg(), ner=FakeNER([("John", "first_name"), ("hypertension", "diagnosis")]))
    r = p.redact("John has hypertension, SSN 123-45-6789.")
    assert r.text == "[NAME] has hypertension, SSN [SSN]."
    assert r.counts == {"NAME": 1, "SSN": 1}
    assert r.engines == ["rules", "fake-ner"]


def test_missing_model_is_not_protected(tmp_path):
    p = RedactionPipeline(cfg(models_dir=str(tmp_path)))
    with pytest.raises(NotProtectedError):
        p.redact("John Smith")


def test_rules_only_must_be_explicit():
    r = RedactionPipeline(PrivateCopyConfig(ner_model="none")).redact("SSN 123-45-6789")
    assert r.text == "SSN [SSN]"
    assert r.engines == ["rules"]


def test_phi_at_end_of_long_text_is_redacted():
    text = "note " * 3900 + "SSN 123-45-6789"
    r = RedactionPipeline(PrivateCopyConfig(ner_model="none")).redact(text)
    assert "123-45-6789" not in r.text
    assert not r.truncated


def test_over_limit_text_is_truncated_visibly():
    r = RedactionPipeline(PrivateCopyConfig(ner_model="none", max_chars=100)).redact("x" * 150)
    assert r.truncated
    assert r.text.startswith("x" * 100)
    assert "truncated at 100" in r.text


@pytest.mark.parametrize("behaviour,reason", [("timeout", "timed out"), ("error", "error (ValueError)")])
def test_llm_failure_falls_back_to_rules_and_ner(behaviour, reason):
    p = RedactionPipeline(cfg(llm_enabled=True), ner=FakeNER([("John", "first_name")]),
                          llm=FakeLLM(behaviour))
    r = p.redact("John and Zelda")
    assert r.text == "[NAME] and Zelda"
    assert reason in r.llm_skipped


def test_llm_entities_are_merged():
    p = RedactionPipeline(cfg(llm_enabled=True), ner=FakeNER([("John", "first_name")]), llm=FakeLLM("ok"))
    r = p.redact("John and Zelda")
    assert r.text == "[NAME] and [NAME]"
    assert r.engines[-1] == "fake-llm"
    assert not r.llm_skipped


def test_llm_disabled_is_not_called():
    r = RedactionPipeline(cfg(), ner=FakeNER([]), llm=FakeLLM("error")).redact("Zelda")
    assert r.text == "Zelda"
    assert r.llm_skipped == ""


def test_llm_enabled_but_unavailable_is_reported():
    r = RedactionPipeline(cfg(llm_enabled=True), ner=FakeNER([])).redact("Zelda")
    assert r.llm_skipped == "local LLM not available"
