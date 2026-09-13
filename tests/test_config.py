from privatecopy.config import PrivateCopyConfig


def test_defaults():
    cfg = PrivateCopyConfig()
    assert cfg.model == "nvidia-gliner"
    assert cfg.threshold == 0.5
    assert cfg.max_chars == 10_000
    assert "+" in cfg.hotkey


def test_save_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = PrivateCopyConfig(model="openmed-44m", threshold=0.7, hotkey="ctrl+shift+p")
    p = cfg.save()
    loaded = PrivateCopyConfig.load(p)
    assert loaded.model == "openmed-44m"
    assert loaded.threshold == 0.7
    assert loaded.hotkey == "ctrl+shift+p"
