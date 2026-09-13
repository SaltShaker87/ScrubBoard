from privatecopy.config import PrivateCopyConfig
from privatecopy.models import predict_chunked
from privatecopy.models.base import RegexFallbackModel
from privatecopy.models.manifest import MODEL_CATALOG, get_entry
from privatecopy.service import PrivateCopyService


def test_catalog_has_both_models():
    assert set(MODEL_CATALOG) == {"nvidia-gliner", "openmed-44m"}
    assert get_entry("nvidia-gliner")["default_threshold"] == 0.5


def test_chunked_matches_single():
    model = RegexFallbackModel()
    text = "mail a@b.com then " + "x" * 5000 + " call (555) 123-4567 end"
    single = sorted(model.predict(text), key=lambda e: e.start)
    chunked = predict_chunked(model, text, 0.5, window=1000, overlap=200)
    assert [(e.start, e.end, e.label) for e in chunked] == [(e.start, e.end, e.label) for e in single]


def test_service_end_to_end():
    cfg = PrivateCopyConfig(model="nvidia-gliner", threshold=0.5, placeholder_style="[LABEL]")
    svc = PrivateCopyService(cfg, model=RegexFallbackModel())
    clean, n, truncated = svc.redact("Email john.smith@email.com, SSN 123-45-6789.")
    assert n == 2
    assert clean == "Email [EMAIL], SSN [SSN]."
    assert truncated is False
