"""HIPAA Safe Harbor (45 CFR 164.514(b)(2)) layer.

* ``SafeHarborRules`` — deterministic detectors for the structured identifiers.
  Always runs, independent of any ML model.
* ``SafeHarborPolicy`` — every engine's labels pass through it: labels map onto
  Safe Harbor categories, what Safe Harbor allows is kept (state, country,
  diagnoses, medications, ages <= 89, ...), unknown labels are redacted, and the
  Safe Harbor transforms are rendered (year-only dates, "90+" ages, 3-digit ZIPs).
"""
from __future__ import annotations

import datetime as _dt
import ipaddress
import re
from collections.abc import Callable, Iterator

from privatecopy.models.base import PIIModel
from privatecopy.redact import Entity, normalize_label, placeholder_for

# 3-digit ZIPs whose combined ZCTAs have <= 20,000 people (HHS guidance, 2000
# Census). These become "000" even when 3-digit prefixes are otherwise kept.
RESTRICTED_ZIP3 = frozenset({
    "036", "059", "063", "102", "203", "556", "692", "790", "821",
    "823", "830", "831", "878", "879", "884", "890", "893",
})

# Output tag -> model labels (Nemotron-PII / OpenMed / GLiNER / qwen3 names,
# normalized) that map onto it.
_TAG_GROUPS: dict[str, tuple[str, ...]] = {
    "NAME": ("NAME", "FIRST_NAME", "LAST_NAME", "MIDDLE_NAME", "MAIDEN_NAME", "FULL_NAME",
             "PERSON", "PER", "PATIENT", "PATIENT_NAME", "DOCTOR", "DOCTOR_NAME",
             "USER_NAME", "USERNAME", "FIRSTNAME", "LASTNAME", "MIDDLENAME"),
    "ADDRESS": ("STREET_ADDRESS", "ADDRESS", "STREET", "PO_BOX", "BUILDING_NUMBER",
                "BUILDINGNUMBER"),
    "LOCATION": ("CITY", "COUNTY", "LOCATION", "LOC", "COORDINATE", "COORDINATES", "GPS",
                 "PRECINCT", "NEIGHBORHOOD"),
    "ZIP": ("ZIP", "ZIP_CODE", "ZIPCODE", "POSTCODE", "POSTAL_CODE"),
    "DATE": ("DATE", "DATE_OF_BIRTH", "DOB", "DATE_TIME", "DATETIME", "BIRTHDATE",
             "DATE_OF_DEATH", "ADMISSION_DATE", "DISCHARGE_DATE"),
    "AGE": ("AGE",),
    "PHONE": ("PHONE", "PHONE_NUMBER", "PHONENUMBER", "TELEPHONE", "MOBILE"),
    "FAX": ("FAX", "FAX_NUMBER"),
    "EMAIL": ("EMAIL", "EMAIL_ADDRESS"),
    "SSN": ("SSN", "SOCIAL_SECURITY_NUMBER"),
    "MRN": ("MEDICAL_RECORD_NUMBER", "MRN", "PATIENT_ID", "MEDICALRECORD"),
    "HEALTH_PLAN_ID": ("HEALTH_PLAN_BENEFICIARY_NUMBER", "HEALTH_PLAN_ID", "HEALTHPLAN",
                       "INSURANCE_NUMBER", "INSURANCE_ID", "POLICY_NUMBER", "MEMBER_ID",
                       "SUBSCRIBER_ID"),
    "ACCOUNT": ("ACCOUNT_NUMBER", "BANK_ACCOUNT_NUMBER", "ACCOUNT", "ACCOUNTNUMBER",
                "CREDIT_DEBIT_CARD", "CREDIT_CARD", "CREDIT_CARD_NUMBER", "IBAN",
                "BANK_ROUTING_NUMBER", "ROUTING_NUMBER", "SWIFT_BIC", "CVV", "PIN",
                "CUSTOMER_ID"),
    "LICENSE": ("CERTIFICATE_LICENSE_NUMBER", "LICENSE_NUMBER", "DRIVER_LICENSE",
                "DRIVERS_LICENSE", "PASSPORT", "PASSPORT_NUMBER", "LICENSE"),
    "VEHICLE_ID": ("VEHICLE_IDENTIFIER", "VEHICLE_ID", "LICENSE_PLATE", "VIN"),
    "DEVICE_ID": ("DEVICE_IDENTIFIER", "DEVICE_ID", "DEVICE", "IMEI", "SERIAL_NUMBER",
                  "MAC_ADDRESS"),
    "URL": ("URL", "DOMAIN_NAME", "WEBSITE"),
    "IP_ADDRESS": ("IPV4", "IPV6", "IP_ADDRESS", "IP"),
    "BIOMETRIC": ("BIOMETRIC_IDENTIFIER", "BIOMETRIC"),
    "ID": ("ID", "UNIQUE_ID", "EMPLOYEE_ID", "EMPLOYER_ID", "STUDENT_ID", "USER_ID",
           "NATIONAL_ID", "TAX_ID", "CASE_NUMBER", "CASE_ID", "IDNUM"),
    "CREDENTIAL": ("API_KEY", "PASSWORD", "HTTP_COOKIE"),
    # Not one of the 18 identifiers, but redacted by default as "other unique
    # characteristics" (conservative). Add to extra_keep_labels to keep.
    "ORGANIZATION": ("COMPANY_NAME", "COMPANY", "COMPANYNAME", "ORGANIZATION", "ORG",
                     "EMPLOYER", "HOSPITAL", "HOSPITAL_NAME", "SCHOOL_NAME", "UNIVERSITY",
                     "COURT_NAME"),
    "OCCUPATION": ("OCCUPATION", "JOB_TITLE", "JOBTITLE", "PROFESSION"),
}
_TAG_BY_LABEL = {label: tag for tag, labels in _TAG_GROUPS.items() for label in labels}

# Labels Safe Harbor does not require removing. Diagnoses/medications are kept
# on purpose so the text stays clinically useful.
KEEP_LABELS = frozenset({
    "STATE", "COUNTRY", "GENDER", "SEX", "RACE_ETHNICITY", "RACE", "ETHNICITY",
    "RELIGIOUS_BELIEF", "RELIGION", "POLITICAL_VIEW", "SEXUALITY", "BLOOD_TYPE",
    "EDUCATION_LEVEL", "EMPLOYMENT_STATUS", "LANGUAGE", "NATIONALITY", "TIME",
    "DIAGNOSIS", "CONDITION", "DISEASE", "MEDICATION", "MEDICINE", "DRUG", "PROCEDURE",
    "TREATMENT", "SYMPTOM", "DEGREE", "GPA", "SALARY", "INCOME", "TITLE",
})

# Disease/sign eponyms: a NAME tag on these is dropped only when a disease word
# follows (so "Parkinson's disease" stays, "Mr. Parkinson" is still redacted).
_EPONYMS = frozenset(w.casefold() for w in (
    "Addison Alzheimer Apgar Asperger Babinski Barrett Barre Barré Bell Bright Brudzinski "
    "Brugada Buerger Burkitt Charcot Chiari Colles Crohn Cushing Danlos DiGeorge Down "
    "Dupuytren Ehlers Epstein Ewing Fanconi Foley Ganz Gaucher Gilbert Glasgow Graves "
    "Guillain Hashimoto Heimlich Hirschsprung Hodgkin Homan Homans Huntington Johnson "
    "Kaposi Kawasaki Kernig Klinefelter Korsakoff Lachman Lyme Marfan McBurney Meniere "
    "Ménière Murphy Paget Parkinson Phalen Raynaud Reiter Reye Romberg Sachs Sjogren "
    "Sjögren Smith Stevens Swan Tay Tinel Tourette Trendelenburg Turner Valsalva Wernicke "
    "Whipple White Wilms Wilson Wolff").split())
_DISEASE_WORDS = (r"disease|syndrome|palsy|sign|test|maneuver|manoeuvre|reflex|lymphoma|"
                  r"sarcoma|phenomenon|triad|criteria|scale|score|classification|ulcer|"
                  r"fracture|tumou?r|contracture|nodes?|law|operation|procedure|position|"
                  r"incision|catheter|esophagus|oesophagus|thyroiditis|encephalopathy|"
                  r"anomaly|malformation|anemia|anaemia|point|chorea|dementia")
_DISEASE_AFTER = re.compile(rf"^(?:['’]s)?\s+(?:{_DISEASE_WORDS})\b", re.I)
_DISEASE_TOKEN = re.compile(rf"^(?:{_DISEASE_WORDS})$", re.I)


class SafeHarborPolicy:
    def __init__(self, keep_year: bool = True, keep_zip3: bool = True,
                 extra_keep_labels: list[str] | tuple[str, ...] = (), style: str = "[LABEL]",
                 today: _dt.date | None = None):
        self.keep_year = keep_year
        self.keep_zip3 = keep_zip3
        self.keep = KEEP_LABELS | {normalize_label(x) for x in extra_keep_labels}
        self.style = style
        self.today = today or _dt.date.today()

    def tag_for(self, label: str) -> str | None:
        """Output tag for a model label, or None if Safe Harbor lets it stay.
        Unknown labels are redacted under their own name (fail-safe)."""
        norm = normalize_label(label)
        if norm in self.keep:
            return None
        tag = _TAG_BY_LABEL.get(norm, norm)
        return None if tag in self.keep else tag

    def filter(self, text: str, entities: list[Entity]) -> list[Entity]:
        out: list[Entity] = []
        for ent in entities:
            tag = self.tag_for(ent.label)
            if tag is None:
                continue
            span = text[ent.start:ent.end]
            if tag == "AGE" and not _age_over_89(span):
                continue
            if tag == "NAME" and _is_eponym(text, ent.start, ent.end):
                continue
            out.append(Entity(ent.start, ent.end, tag, ent.score, source=ent.source))
        return out

    def render(self, ent: Entity, span: str) -> str:
        if ent.label == "DATE":
            year = _year_in(span)
            if self.keep_year and year and year > self.today.year - 90:
                return self._with_suffix("DATE", str(year))
        elif ent.label == "AGE":
            return self._with_suffix("AGE", "90+")
        elif ent.label == "ZIP" and self.keep_zip3:
            digits = re.sub(r"\D", "", span)
            if len(digits) >= 5:
                zip3 = digits[:3]
                return self._with_suffix("ZIP", "000" if zip3 in RESTRICTED_ZIP3 else zip3)
        return placeholder_for(ent.label, self.style)

    def _with_suffix(self, tag: str, suffix: str) -> str:
        if self.style == "[LABEL]":
            return f"[{tag} {suffix}]"
        return f"{placeholder_for(tag, self.style)} {suffix}"


def _year_in(span: str) -> int | None:
    years = re.findall(r"(?<!\d)(?:18|19|20)\d{2}(?!\d)", span)
    return int(years[-1]) if years else None


_TENS = (("ninet", 90), ("eight", 80), ("sevent", 70), ("sixt", 60), ("fift", 50),
         ("fort", 40), ("thirt", 30), ("twent", 20))


def _age_value(span: str) -> int | None:
    m = re.search(r"\d{1,3}", span)
    if m:
        return int(m.group())
    low = span.lower()
    if "hundred" in low:
        return 100
    if re.search(r"(?:thir|four|fif|six|seven|eigh|nine)teen", low):
        return 15
    for stem, value in _TENS:
        if stem in low:
            return value
    return None


def _age_over_89(span: str) -> bool:
    value = _age_value(span)
    return value is None or value > 89  # unparseable -> redact (fail-safe)


def _is_eponym(text: str, start: int, end: int) -> bool:
    tokens = [t for t in re.split(r"[\s\-–]+", text[start:end].strip()) if t]
    tokens = [re.sub(r"['’]s?$", "", t) for t in tokens]
    has_disease_word = False
    while tokens and _DISEASE_TOKEN.match(tokens[-1]):
        tokens.pop()
        has_disease_word = True
    if not tokens or not all(t.casefold() in _EPONYMS for t in tokens):
        return False
    return has_disease_word or bool(_DISEASE_AFTER.match(text[end:end + 40]))


# --------------------------------------------------------------------------
# Deterministic detectors
# --------------------------------------------------------------------------

Validator = Callable[[str, re.Match, str], bool]

_MONTH_FORMS = ("January", "February", "March", "April", "May", "June", "July", "August",
                "September", "October", "November", "December", "Jan", "Feb", "Mar", "Apr",
                "Jun", "Jul", "Aug", "Sept", "Sep", "Oct", "Nov", "Dec")
_M = "(?:" + "|".join(sorted({f for m in _MONTH_FORMS for f in (m, m.upper())},
                             key=len, reverse=True)) + ")"
_DAY = r"(?:0?[1-9]|[12]\d|3[01])"
_MON = r"(?:0?[1-9]|1[0-2])"
_YEAR4 = r"(?:18|19|20)\d{2}"

_STATE_ABBR = ("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO "
               "MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY PR "
               "GU VI AS MP").split()
_STATE_NAMES = ("Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|"
                "Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|"
                "Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|"
                "Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|"
                "North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|"
                "South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|"
                "Wisconsin|Wyoming|Puerto Rico|District of Columbia")

_KEYWORD_IDS: tuple[tuple[str, str], ...] = (
    ("MRN", r"MRN|MR\s?#|MR\s+(?:no\.?|number)|medical\s+record(?:\s+(?:number|no\.?|#))?|"
            r"patient\s+(?:id|#|number|no\.?)|chart\s*(?:#|number|no\.?)"),
    ("HEALTH_PLAN_ID", r"member\s*(?:id|#|number|no\.?)|subscriber\s*(?:id|#|number)|"
                       r"policy\s*(?:id|#|number|no\.?)|health\s*plan\s*(?:id|#|number)?|"
                       r"insurance\s*(?:id|#|number|no\.?)|group\s*(?:#|number|no\.?)|"
                       r"medicaid\s*(?:id|#|number)|medicare\s*(?:id|#|number)|MBI|HICN|"
                       r"beneficiary\s*(?:id|#|number)"),
    ("ACCOUNT", r"acct\.?\s*(?:#|no\.?)?|account\s*(?:#|number|no\.?)?|billing\s*(?:#|number|id)|"
                r"claim\s*(?:#|number|no\.?|id)"),
    ("LICENSE", r"licen[cs]e\s*(?:#|number|no\.?)|lic\.?\s*#|DL\s*#|"
                r"driver'?s?\s+licen[cs]e(?:\s*(?:#|number|no\.?))?|passport\s*(?:#|number|no\.?)?|"
                r"DEA\s*(?:#|number|no\.?)?|NPI\s*(?:#|number)?|certificate\s*(?:#|number|no\.?)"),
    ("DEVICE_ID", r"serial\s*(?:#|number|no\.?)|S/N|SN\s*#|device\s*(?:id|#|number)|IMEI|UDI|"
                  r"implant\s*(?:id|#|serial)"),
    ("VEHICLE_ID", r"(?:license\s+)?plate\s*(?:#|number|no\.?)?|VIN\s*(?:#|number)?"),
    ("SSN", r"SSN|social\s+security(?:\s+(?:number|no\.?|#))?"),
    ("ID", r"FIN|CSN|encounter\s*(?:#|number|no\.?|id)|visit\s*(?:#|number|no\.?|id)|"
           r"accession\s*(?:#|number|no\.?)?|case\s*(?:#|number|no\.?)|specimen\s*(?:#|id|number)|"
           r"order\s*(?:#|number|id)|employee\s*(?:id|#|number)|badge\s*(?:#|number|id)|EIN|TIN|"
           r"tax\s*id|ITIN"),
)

_NAME_FIELD_KEYWORDS = (r"patient(?:\s+name)?|pt(?:\s+name)?|name|full\s+name|guarantor|"
                        r"emergency\s+contact|next\s+of\s+kin|NOK|contact|attending|resident|"
                        r"referring(?:\s+(?:physician|provider|md))?|PCP|provider|"
                        r"(?:electronically\s+)?signed(?:\s+by)?|author|nurse|physician|surgeon|"
                        r"mother|father|spouse|husband|wife|son|daughter|caregiver")
_CREDENTIALS = (r"MD|M\.D\.|DO|D\.O\.|RN|NP|PA-C|PA|DNP|PhD|PharmD|MSW|LCSW|CNM|CRNA|DPM|"
                r"DDS|APRN|FNP|LPN")

_SCALE_BEFORE = re.compile(r"(?i)(?:pain|strength|score|scale|gcs|motor|reflex(?:es)?|grade|"
                           r"power|tab(?:let)?s?|caps?|dose|ratio|murmur|x)\W*$")
_SCALE_AFTER = re.compile(r"(?i)\s*(?:pain|strength|tab|caps?|dose|bilat|murmur|power)")


def _short_date_ok(val: str, m: re.Match, text: str) -> bool:
    a, b = (int(x) for x in val.split("/"))
    if a <= b <= 8:           # 1/2, 3/4, 5/5: fractions and exam grades
        return False
    if b == 10 and a <= 10:   # x/10 scales
        return False
    before = text[max(0, m.start() - 20):m.start()]
    after = text[m.end():m.end() + 12]
    return not (_SCALE_BEFORE.search(before) or _SCALE_AFTER.match(after))


def _born_year_ok(val: str, _m: re.Match, _text: str) -> bool:
    # A bare year only needs redacting when it reveals an age over 89.
    return int(val) <= _dt.date.today().year - 90


def _luhn_ok(val: str, _m: re.Match, _text: str) -> bool:
    digits = [int(c) for c in val if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
    return total % 10 == 0


def _ipv4_ok(val: str, _m: re.Match, _text: str) -> bool:
    try:
        ipaddress.IPv4Address(val)
    except ValueError:
        return False
    return True


def _ipv6_ok(val: str, _m: re.Match, _text: str) -> bool:
    if sum(c in "0123456789abcdefABCDEF" for c in val) < 4:
        return False
    try:
        ipaddress.IPv6Address(val)
    except ValueError:
        return False
    return True


def _id_value_ok(val: str, _m: re.Match, _text: str) -> bool:
    return len(val) >= 4 and sum(c.isdigit() for c in val) >= 2


def _vin_ok(val: str, _m: re.Match, _text: str) -> bool:
    return any(c.isdigit() for c in val) and any(c.isalpha() for c in val)


def _intl_phone_ok(val: str, _m: re.Match, _text: str) -> bool:
    return 8 <= sum(c.isdigit() for c in val) <= 15


def _phone_tag(m: re.Match, text: str) -> str:
    before = text[max(0, m.start() - 16):m.start()].lower()
    return "FAX" if "fax" in before else "PHONE"


def _local_phone_ok(_val: str, m: re.Match, text: str) -> bool:
    before = text[max(0, m.start() - 24):m.start()].lower()
    return bool(re.search(r"tel|phone|ph\b|call|cell|mobile|pager|contact|fax|#", before))


# (tag or tagger, regex, capture group, validator)
_Rule = tuple[str | Callable[[re.Match, str], str], re.Pattern, int, Validator | None]

_RULES: list[_Rule] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), 0, None),
    ("URL", re.compile(r"(?i)\b(?:https?://|ftp://|www\.)[^\s<>\"']+[^\s<>\"'.,;:!?)\]}]"), 0, None),
    ("IP_ADDRESS", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), 0, _ipv4_ok),
    ("IP_ADDRESS", re.compile(r"(?i)(?<![\w:])(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}(?![\w:])"), 0,
     _ipv6_ok),
    ("DEVICE_ID", re.compile(r"\b[0-9A-Fa-f]{2}([:-])[0-9A-Fa-f]{2}(?:\1[0-9A-Fa-f]{2}){4}\b"), 0,
     None),
    ("SSN", re.compile(r"\b(?!000|666|9\d\d)\d{3}([- ])(?!00)\d{2}\1(?!0000)\d{4}\b"), 0, None),
    (_phone_tag, re.compile(r"(?<![\w+])(?:\+?1[\s.-]?)?(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]\d{4}"
                            r"\b(?:\s*(?:x|ext\.?)\s*\d{1,5})?"), 0, None),
    (_phone_tag, re.compile(r"(?<![\w+])\+\d{1,3}(?:[\s.-]?\(?\d{1,4}\)?){2,5}"), 0, _intl_phone_ok),
    (_phone_tag, re.compile(r"(?<![\w-])\d{3}-\d{4}\b"), 0, _local_phone_ok),
    ("ACCOUNT", re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"), 0, _luhn_ok),
    ("VEHICLE_ID", re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b"), 0, _vin_ok),
    # Dates (every element except the year is an identifier).
    ("DATE", re.compile(rf"\b{_YEAR4}[-/.]{_MON}[-/.]{_DAY}(?:[T ]\d{{1,2}}:\d{{2}}(?::\d{{2}})?)?\b"),
     0, None),
    ("DATE", re.compile(rf"\b{_DAY}[/.-]{_DAY}[/.-](?:\d{{4}}|\d{{2}})\b"), 0, None),
    ("DATE", re.compile(rf"\b{_M}\.?\s+{_DAY}(?:st|nd|rd|th)?\b(?:,?\s+{_YEAR4}\b)?"), 0, None),
    ("DATE", re.compile(rf"\b{_DAY}(?:st|nd|rd|th)?\s+(?:of\s+)?{_M}\b\.?(?:,?\s+{_YEAR4}\b)?"), 0,
     None),
    ("DATE", re.compile(rf"\b{_M}\.?,?\s+{_YEAR4}\b"), 0, None),
    ("DATE", re.compile(rf"\b{_MON}/{_DAY}\b(?![/.-]\d)"), 0, _short_date_ok),
    ("DATE", re.compile(rf"(?i)\b(?:born(?:\s+in)?|b\.|DOB|date\s+of\s+birth|year\s+of\s+birth|YOB)"
                        rf"\s*[:\-]?\s*({_YEAR4})\b"), 1, _born_year_ok),
    # Ages over 89 (ages <= 89 are allowed and dropped by the policy).
    ("AGE", re.compile(r"(?i)\b(?:9\d|1[01]\d|120)\s*-?\s*(?:y/?o\b|y\.o\.|yo\b|yrs?\b|years?\b)"
                       r"(?:[-\s]+old\b)?"), 0, None),
    ("AGE", re.compile(r"(?i)\b(?:age|aged)\s*[:=]?\s*(9\d|1[01]\d|120)\b"), 1, None),
    ("AGE", re.compile(r"\b(?:9\d|1[01]\d)\s?(?:M|F)\b"), 0, None),
    ("AGE", re.compile(r"(?i)\b(?:ninety|one\s+hundred)(?:[-\s](?:one|two|three|four|five|six|"
                       r"seven|eight|nine))?[-\s]+years?[-\s]+old\b"), 0, None),
    # ZIP codes in address context.
    ("ZIP", re.compile(rf"\b(?:{'|'.join(_STATE_ABBR)})\.?,?\s+(\d{{5}}(?:-\d{{4}})?)\b"), 1, None),
    ("ZIP", re.compile(rf"(?i)\b(?:{_STATE_NAMES}),?\s+(\d{{5}}(?:-\d{{4}})?)\b"), 1, None),
    ("ZIP", re.compile(r"(?i)\b(?:zip|zip\s*code|postal\s*code)\s*[:#]?\s*(\d{5}(?:-\d{4})?)\b"), 1,
     None),
    # Names in unambiguous contexts.
    ("NAME", re.compile(r"\b(?:Mr|Mrs|Ms|Mx|Miss|Dr|Prof)\.?[ \t]+([A-Z][a-zA-Z'’-]+"
                        r"(?:[ \t]+[A-Z]\.)?(?:[ \t]+[A-Z][a-zA-Z'’-]+)?)"), 1, None),
    ("NAME", re.compile(rf"\b(?i:{_NAME_FIELD_KEYWORDS})[ \t]*:[ \t]*(?:(?:Dr|Mr|Mrs|Ms|Mx|Miss|Prof)\.?[ \t]+)?"
                        rf"([A-Z][A-Za-z'’-]+(?:,?[ \t][A-Z][A-Za-z'’.-]*){{0,3}})"), 1, None),
    ("NAME", re.compile(rf"\b([A-Z][a-z'’-]+(?:[ \t]+[A-Z]\.?)?[ \t]+[A-Z][a-z'’-]+(?:-[A-Z][a-z]+)?)"
                        rf",?[ \t]+(?:{_CREDENTIALS})\b"), 1, None),
] + [
    (tag, re.compile(rf"(?i)\b(?:{kw})(?![A-Za-z])\s*(?:[:#=\-]|is|no\.?)?\s*"
                     r"([A-Za-z0-9](?:[A-Za-z0-9-]{2,}[A-Za-z0-9])?)"), 1, _id_value_ok)
    for tag, kw in _KEYWORD_IDS
] + [
    # Long digit runs / prefixed numbers are almost always identifiers in clinical
    # text. Listed last so a more specific tag wins on an identical span.
    ("ID", re.compile(r"(?<![\d.,/])\d{7,}(?!\d|[.,/]\d)"), 0, None),
    ("ID", re.compile(r"\b[A-Z]{1,3}-?\d{6,}\b"), 0, None),
]


class SafeHarborRules(PIIModel):
    """Regex detectors for the structured Safe Harbor identifiers."""

    name = "rules"

    @property
    def labels(self) -> list[str]:
        return sorted({t for t, *_ in _RULES if isinstance(t, str)} | {"FAX", "PHONE"})

    def predict(self, text: str, threshold: float = 0.5) -> list[Entity]:
        del threshold
        return sorted(self._iter(text), key=lambda e: (e.start, e.end))

    @staticmethod
    def _iter(text: str) -> Iterator[Entity]:
        for tag, rx, group, validate in _RULES:
            for m in rx.finditer(text):
                s, e = m.span(group)
                if s < 0 or s >= e:
                    continue
                if validate and not validate(text[s:e], m, text):
                    continue
                label = tag(m, text) if callable(tag) else tag
                yield Entity(s, e, label, 1.0, source="rules")
