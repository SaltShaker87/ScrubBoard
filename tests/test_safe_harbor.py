import datetime as dt

import pytest

from privatecopy.config import PrivateCopyConfig
from privatecopy.pipeline import RedactionPipeline
from privatecopy.redact import Entity
from privatecopy.safe_harbor import SafeHarborPolicy


def redact(text: str, **cfg) -> str:
    return RedactionPipeline(PrivateCopyConfig(ner_model="none", **cfg)).redact(text).text


# (text, identifier that must disappear, placeholder that must appear)
REDACTED = [
    ("SSN 123-45-6789 on file", "123-45-6789", "[SSN]"),
    ("SSN: 123456789", "123456789", "[SSN]"),
    ("Call (617) 555-0123 today", "555-0123", "[PHONE]"),
    ("Fax: 617-555-0199", "555-0199", "[FAX]"),
    ("pager 555-0142", "555-0142", "[PHONE]"),
    ("Email jane.doe@example.org now", "jane.doe@example.org", "[EMAIL]"),
    ("Portal https://portal.example.com/p/123.", "portal.example.com", "[URL]."),
    ("from 192.168.1.20", "192.168.1.20", "[IP_ADDRESS]"),
    ("host fe80::1ff:fe23:4567:890a", "fe80::1ff", "[IP_ADDRESS]"),
    ("MAC 00:1A:2B:3C:4D:5E", "00:1A:2B", "[DEVICE_ID]"),
    ("MRN: 00123456", "00123456", "[MRN]"),
    ("MR# A-99812", "A-99812", "[MRN]"),
    ("Member ID: XJH123456789", "XJH123456789", "[HEALTH_PLAN_ID]"),
    ("Acct # 99-1234", "99-1234", "[ACCOUNT]"),
    ("DEA # AB1234563", "AB1234563", "[LICENSE]"),
    ("VIN 1HGCM82633A004352", "1HGCM82633A004352", "[VEHICLE_ID]"),
    ("Serial number: SN-44Z-9981", "SN-44Z-9981", "[DEVICE_ID]"),
    ("card 4111 1111 1111 1111 exp", "4111 1111", "[ACCOUNT]"),
    ("Accession 20240314007", "20240314007", "[ID]"),
    ("Patient: Robert Jones", "Robert Jones", "[NAME]"),
    ("seen by Dr. Alice Chen today", "Alice Chen", "[NAME]"),
    ("Mary Smith, RN", "Mary Smith", "[NAME], RN"),
    ("A 92-year-old woman", "92", "[AGE 90+]"),
    ("92F with CHF", "92F", "[AGE 90+] with CHF"),
    ("aged 101", "101", "[AGE 90+]"),
    ("DOB: 02/01/1931", "1931", "[DATE]"),
    ("born in 1930", "1930", "[DATE]"),
]


@pytest.mark.parametrize("text,secret,placeholder", REDACTED)
def test_identifier_is_redacted(text, secret, placeholder):
    out = redact(text)
    assert secret not in out
    assert placeholder in out


KEPT = [
    "Dx: Parkinson's disease; T2DM on metformin 500 mg BID",
    "Motor strength 5/5 bilaterally, pain 7/10, take 1/2 tab",
    "BP 120/80, HR 72, SpO2 98%",
    "A 67-year-old man with CHF, EF 35%",
    "Lives in MA; transferred from Texas",
    "Follow up in 2 weeks at 14:30",
    "Hgb 13.2, platelets 250000, WBC 7.1",
    "Version 2.1.0 of the order set",
]


@pytest.mark.parametrize("text", KEPT)
def test_clinical_content_is_kept(text):
    assert redact(text) == text


@pytest.mark.parametrize("text,expected", [
    ("Admitted 03/14/2024.", "Admitted [DATE 2024]."),
    ("on March 3rd, 2021 she", "on [DATE 2021] she"),
    ("seen 2024-01-20 in clinic", "seen [DATE 2024] in clinic"),
    ("follow up 12/25 please", "follow up [DATE] please"),
    ("since Jan 2019", "since [DATE 2019]"),
    ("the 4th of July", "the [DATE]"),
])
def test_dates_keep_only_the_year(text, expected):
    assert redact(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("Boston, MA 02139", "Boston, MA [ZIP 021]"),
    ("Jackson, WY 83001", "Jackson, WY [ZIP 000]"),  # restricted ZIP3
    ("zip code: 10001-1234", "zip code: [ZIP 100]"),
])
def test_zip_codes_keep_three_digits(text, expected):
    assert redact(text) == expected


def test_zip3_can_be_dropped_entirely():
    assert redact("MA 02139", keep_zip3=False) == "MA [ZIP]"


def test_policy_keeps_what_safe_harbor_allows():
    p = SafeHarborPolicy()
    for label in ("state", "country", "medication", "diagnosis", "blood_type", "time", "gender"):
        assert p.tag_for(label) is None, label
    assert p.tag_for("first_name") == "NAME"
    assert p.tag_for("postcode") == "ZIP"
    assert p.tag_for("health_plan_beneficiary_number") == "HEALTH_PLAN_ID"
    assert p.tag_for("weird_new_label") == "WEIRD_NEW_LABEL"  # unknown -> still redacted
    assert SafeHarborPolicy(extra_keep_labels=["occupation"]).tag_for("occupation") is None


def test_ages_89_and_under_are_kept():
    text = "age 65 and 95"
    kept = SafeHarborPolicy().filter(text, [Entity(4, 6, "age"), Entity(11, 13, "age")])
    assert [(e.start, e.end) for e in kept] == [(11, 13)]


def test_eponym_guard():
    p = SafeHarborPolicy()
    t1 = "History of Parkinson's disease."
    s = t1.index("Parkinson")
    assert p.filter(t1, [Entity(s, s + 9, "last_name")]) == []
    t2 = "Mr. Parkinson came in."
    s = t2.index("Parkinson")
    assert len(p.filter(t2, [Entity(s, s + 9, "last_name")])) == 1
    assert p.filter("Guillain-Barré syndrome", [Entity(0, 14, "name")]) == []


def test_render_transforms():
    today = dt.date(2026, 9, 13)
    p = SafeHarborPolicy(today=today)
    assert p.render(Entity(0, 10, "DATE"), "03/14/2024") == "[DATE 2024]"
    assert p.render(Entity(0, 10, "DATE"), "02/01/1931") == "[DATE]"  # year implies age > 89
    assert SafeHarborPolicy(keep_year=False, today=today).render(Entity(0, 10, "DATE"), "03/14/2024") == "[DATE]"
    assert p.render(Entity(0, 5, "ZIP"), "83001") == "[ZIP 000]"
    assert p.render(Entity(0, 2, "AGE"), "95") == "[AGE 90+]"
    redacted_style = SafeHarborPolicy(style="[REDACTED]", today=today)
    assert redacted_style.render(Entity(0, 10, "DATE"), "03/14/2024") == "[REDACTED] 2024"
