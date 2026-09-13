from privatecopy.redact import Entity, placeholder_for, redact_text, resolve_overlaps, truncate_text


def test_redact_basic():
    text = "Contact john.smith@email.com or (555) 123-4567."
    ents = [Entity(8, 28, "email", 0.99), Entity(32, 46, "phone_number", 0.98)]
    out = redact_text(text, ents)
    assert out == "Contact [EMAIL] or [PHONE_NUMBER]."


def test_overlap_keeps_best():
    text = "John Smith"
    ents = [Entity(0, 10, "first_name", 0.6), Entity(0, 10, "last_name", 0.9)]
    resolved = resolve_overlaps(ents)
    assert len(resolved) == 1 and resolved[0].label == "LAST_NAME"
    assert redact_text(text, ents) == "[LAST_NAME]"


def test_placeholder_styles():
    assert placeholder_for("email", "[LABEL]") == "[EMAIL]"
    assert placeholder_for("email", "[REDACTED]") == "[REDACTED]"
    assert placeholder_for("email", "BLOCK") == "███"


def test_truncate():
    t, flag = truncate_text("abcde", 3)
    assert (t, flag) == ("abc", True)
    t2, flag2 = truncate_text("ab", 3)
    assert (t2, flag2) == ("ab", False)
