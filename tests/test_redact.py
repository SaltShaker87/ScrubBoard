from scrubboard.redact import (
    Entity,
    expand_to_word_boundaries,
    placeholder_for,
    redact_text,
    resolve_overlaps,
    truncate_text,
)


def test_redact_basic():
    text = "Contact john.smith@email.com or (555) 123-4567."
    ents = [Entity(8, 28, "email", 0.99), Entity(32, 46, "phone_number", 0.98)]
    assert redact_text(text, ents) == "Contact [EMAIL] or [PHONE_NUMBER]."


def test_overlap_keeps_best():
    text = "John Smith"
    ents = [Entity(0, 10, "first_name", 0.6), Entity(0, 10, "last_name", 0.9)]
    resolved = resolve_overlaps(ents)
    assert len(resolved) == 1 and resolved[0].label == "LAST_NAME"
    assert redact_text(text, ents) == "[LAST_NAME]"


def test_partial_overlap_is_unioned_not_dropped():
    # Regression: the old resolver dropped the second span, leaking "CCCCC".
    text = "AAAAABBBBBCCCCC tail"
    ents = [Entity(0, 10, "first_name", 0.9), Entity(5, 15, "last_name", 0.5)]
    assert redact_text(text, ents) == "[FIRST_NAME] tail"


def test_chained_overlaps_merge():
    ents = [Entity(0, 4, "a", 0.5), Entity(2, 6, "b", 0.9), Entity(5, 9, "c", 0.1), Entity(12, 14, "d")]
    assert [(e.start, e.end, e.label) for e in resolve_overlaps(ents)] == [(0, 9, "B"), (12, 14, "D")]


def test_word_boundary_expansion_covers_subword_fragments():
    out = expand_to_word_boundaries("Smithson went home", [Entity(0, 3, "last_name")])
    assert (out[0].start, out[0].end) == (0, 8)


def test_expansion_trims_whitespace():
    out = expand_to_word_boundaries(" John ", [Entity(0, 6, "name")])
    assert (out[0].start, out[0].end) == (1, 5)


def test_entity_repr_hides_text():
    assert "John" not in repr(Entity(0, 4, "name", text="John"))


def test_render_callback():
    assert redact_text("ab cd", [Entity(3, 5, "x")], render=lambda e, s: s.upper()) == "ab CD"


def test_placeholder_styles():
    assert placeholder_for("email", "[LABEL]") == "[EMAIL]"
    assert placeholder_for("email", "[REDACTED]") == "[REDACTED]"
    assert placeholder_for("email", "BLOCK") == "███"


def test_truncate():
    assert truncate_text("abcde", 3) == ("abc", True)
    assert truncate_text("ab", 3) == ("ab", False)
