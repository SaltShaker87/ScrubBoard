import json

import pytest

from scrubboard.config import ScrubboardConfig, coerce_value


def test_defaults():
    cfg = ScrubboardConfig()
    assert cfg.ner_model == "openmed-44m"
    assert cfg.threshold is None
    assert cfg.max_chars == 20_000
    assert not cfg.intercept_enabled and not cfg.llm_enabled and not cfg.onboarding_done
    assert cfg.hotkey == ""
    cfg.validate()


def test_save_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg = ScrubboardConfig(ner_model="nvidia-gliner", threshold=0.7, hotkey="ctrl+shift+p",
                            exclude_apps=["Epic.exe"])
    loaded = ScrubboardConfig.load(cfg.save())
    assert (loaded.ner_model, loaded.threshold, loaded.hotkey, loaded.exclude_apps) == \
        ("nvidia-gliner", 0.7, "ctrl+shift+p", ["Epic.exe"])
    assert loaded.load_warning == ""


def test_invalid_config_falls_back_to_defaults(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"ner_model": "bogus"}')
    cfg = ScrubboardConfig.load(str(p))
    assert cfg.ner_model == "openmed-44m"
    assert "invalid" in cfg.load_warning
    assert list(tmp_path.glob("config.json.invalid-*"))


def test_corrupt_json_falls_back(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{not json")
    assert ScrubboardConfig.load(str(p)).load_warning


def test_v01_config_migrates(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"model": "nvidia-gliner", "threshold": 0.5,
                             "hotkey": "ctrl+shift+c", "auto_update": True}))
    cfg = ScrubboardConfig.load(str(p))
    assert cfg.load_warning == ""
    assert (cfg.ner_model, cfg.hotkey) == ("nvidia-gliner", "ctrl+shift+c")


def test_coerce_value():
    assert coerce_value("llm_enabled", "yes") is True
    assert coerce_value("threshold", "default") is None
    assert coerce_value("threshold", "0.4") == 0.4
    assert coerce_value("max_chars", "5000") == 5000
    assert coerce_value("exclude_apps", "Epic.exe, Hyperdrive") == ["Epic.exe", "Hyperdrive"]
    with pytest.raises(ValueError):
        coerce_value("nope", "1")
    with pytest.raises(ValueError):
        coerce_value("llm_enabled", "maybe")
