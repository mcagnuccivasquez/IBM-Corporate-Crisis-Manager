"""A5 text checks: pure code, no LLM. Used by the A5 agent (on its narrative) and by the
renderer (safety net on other agents' texts, warnings only).

Two kinds of check (agreed with Serdar, 2026-11-21):
- HARD (reliable): invented numbers (digits or words), IDs that the case data never
  mentions, banned phrases from ACME's own files (KB-03, KB-04, KB-09, KB-10), personal data
  mentions, banned phrases from ACME's own files (KB-03, KB-09, KB-10), personal data
  (emails, @handles, phones, "R. Dubois" / "Mr X" style names). On the A5 narrative they
  trigger the one retry in llm.call_structured; what is left becomes a warning.
- SOFT (heuristics, may misfire): "confirmed" said about a non-confirmed claim, a risk
  level that is not in the data, wording that may blame a customer, word limits.
  Warning only.

Known limits (documented, not hidden): a real number used for the wrong thing passes
these checks (the A5 AI fact-check pass looks for that); full names like "Rachel Dubois"
are not detected; phrase checks look for wording, so a new paraphrase can slip through.
"""

from __future__ import annotations

import json
import re

from src.kb import SOURCE_REGISTRY

FIELDS = ("executive_summary", "situation", "changes_summary", "closure_summary")
WORD_LIMITS = {"executive_summary": 80, "situation": 150, "changes_summary": 120, "closure_summary": 120}
SOFT_SUFFIX = " (automatic check; may be a false alarm, please review the wording)"

ID_PATTERN = re.compile(r"\b(?:ACT|KB|C|U)-\d+\b")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_NEGATION = re.compile(r"\b(no|not|never|cannot|can't|without|nor)\b|n't\b", re.IGNORECASE)

# ACME staff from KB-02 (Operations contact sheet): named as action owners, so not personal data.
ACME_STAFF_SURNAMES = {"Rossi", "Moretti", "Chen", "Ferri", "Weber", "Khan", "Laurent", "Keller", "Bianchi"}


# ---------------------------------------------------------------- helpers

def _texts(texts: dict):
    """(label, text) for every non-empty text value."""
    for label, text in texts.items():
        if isinstance(text, str) and text.strip():
            yield label, text


def state_without_report(state: dict) -> dict:
    """The case data a narrative may draw on (the previous narrative is excluded)."""
    return {k: v for k, v in state.items() if k not in ("report", "_comment")}


def state_text(state: dict) -> str:
    return json.dumps(state_without_report(state), ensure_ascii=False)


def evidence_text(state: dict) -> str:
    """What counts as support for a sensitive statement: the evidence and user-reported facts
    (claims, sources, the user's turn, action status history, changelog), not the other
    agents' own wording."""
    parts = {
        "claims": state.get("claims"),
        "sources": state.get("sources"),
        "turn_input": state.get("turn_input"),
        "changelog": state.get("changelog"),
        "action_history": [a.get("status_history") for a in state.get("actions") or []],
    }
    return json.dumps(parts, ensure_ascii=False)


def known_ids(state: dict) -> set[str]:
    ids = {c.get("claim_id") for c in state.get("claims") or []}
    ids |= {s.get("source_id") for s in state.get("sources") or []}
    ids |= {a.get("action_id") for a in state.get("actions") or []}
    ids.discard(None)
    return ids


def _negated(text: str, start: int, window: int = 5) -> bool:
    """True if one of the `window` words before position `start` is a negation."""
    before = text[:start].split()[-window:]
    return bool(_NEGATION.search(" ".join(before)))


def _affirmed(pattern: str, text: str) -> list[str]:
    return [m.group(0) for m in re.finditer(pattern, text, re.IGNORECASE) if not _negated(text, m.start())]


# ---------------------------------------------------------------- hard: numbers (digits and words)

_NUMBER = re.compile(r"\d[\d,.]*\d|\d")
_CITATION = re.compile(r"\[[^\]]*\]")

_UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split(), start=2)}
_SCALES = {"hundred": 100, "thousand": 1_000, "million": 1_000_000}
_NUM_WORD = "|".join([*_UNITS, *_TENS, *_SCALES, "dozen"])
_WORD_NUMBER = re.compile(rf"\b(?:{_NUM_WORD})(?:(?:[\s-]+(?:and[\s-]+)?)(?:{_NUM_WORD}))*\b", re.IGNORECASE)


def _word_value(phrase: str) -> float:
    """'two thousand five hundred' -> 2500, 'a dozen' handled as 'dozen' -> 12."""
    total = current = 0
    for tok in re.split(r"[\s-]+", phrase.lower()):
        if tok in _UNITS:
            current += _UNITS[tok]
        elif tok in _TENS:
            current += _TENS[tok]
        elif tok == "dozen":
            current = (current or 1) * 12
        elif tok == "hundred":
            current = (current or 1) * 100
        elif tok in ("thousand", "million"):
            total += (current or 1) * _SCALES[tok]
            current = 0
    return float(total + current)


def _numbers(text: str) -> set:
    found = set()
    for raw in _NUMBER.findall(text):
        try:
            found.add(float(raw.replace(",", "")))
        except ValueError:  # e.g. "1.2.3" (a version string): compare as text instead
            found.add(raw)
    return found


def find_unsupported_numbers(texts: dict, state: dict) -> dict[str, list[str]]:
    """Numbers (digits or words) in each text that do not appear anywhere in the case data.

    Citations in brackets are ignored; "11,000" = "11000"; "two thousand" = 2000.
    """
    allowed = _numbers(state_text(state))
    problems: dict[str, list[str]] = {}
    for label, text in _texts(texts):
        body = _CITATION.sub("", text)
        bad = []
        for raw in _NUMBER.findall(body):
            value = next(iter(_numbers(raw)))
            if value not in allowed and raw not in bad:
                bad.append(raw)
        for m in _WORD_NUMBER.finditer(body):
            if _word_value(m.group(0)) not in allowed and m.group(0) not in bad:
                bad.append(m.group(0))
        if bad:
            problems[label] = bad
    return problems


# ---------------------------------------------------------------- hard: IDs

def find_unknown_ids(texts: dict, state: dict) -> dict[str, list[str]]:
    """IDs (C-, U-, KB-, ACT-) that appear nowhere in the case data.

    Allowed: every registered claim/source/action ID, plus any ID the case data mentions
    (e.g. A4's outlook citing KB-06 without KB-06 being a registered source).
    """
    known = known_ids(state) | set(ID_PATTERN.findall(state_text(state)))
    problems: dict[str, list[str]] = {}
    for label, text in _texts(texts):
        bad = list(dict.fromkeys(i for i in ID_PATTERN.findall(text) if i not in known))
        if bad:
            problems[label] = bad
    return problems


# ---------------------------------------------------------------- hard: banned phrases
# (label, regex, rule source, only in sentences matching this scope or None)
_AUTH = (r"(authorit(?:y|ies)|regulators?|regulatory\s+(?:body|bodies)|market\s+surveillance(?:\s+authorit(?:y|ies))?"
         r"|(?:government\s+)?agenc(?:y|ies)|ministry)")
_TOLD = r"(contacted|notified|informed|alerted|told|reported\s+(?:\w+\s+){0,2}?to)"
BANNED_PHRASES = [
    ("authorities contacted",
     rf"\b{_TOLD}\s+(?:the\s+)?(?:\w+\s+){{0,2}}?{_AUTH}\b"
     rf"|\b{_AUTH}\s+(?:have|has|had|were|was|are|is)\s+(?:been\s+)?(?:contacted|notified|informed|alerted|told)\b"
     r"|\bnotification\s+(?:was\s+|has\s+been\s+|is\s+)?(?:sent|submitted|filed|made)\s+to\b",
     "KB-10", None),
    ("independent tests",
     r"\b(?:independent(?:ly)?|third[- ]party|external)\s+(?:lab(?:oratory)?\s+)?(?:test(?:s|ed|ing)?|certification)\b",
     "KB-10", None),
    ("all units tested",
     r"\b(?:all|every|each)\s+(?:of\s+)?(?:the\s+)?(?:units?|chargers?|devices?|products?|cameras?|batch(?:es)?|stock)\s+"
     r"(?:was\s+|were\s+|have\s+been\s+|has\s+been\s+|are\s+|is\s+|being\s+|got\s+)?(?:tested|checked|inspected|verified)\b"
     r"|\b(?:tested|checked|inspected)\s+(?:all|every)\s+(?:the\s+)?(?:units?|chargers?|devices?|batch(?:es)?)\b",
     "KB-10", None),
    ("remote fix for PCX-100",
     r"\b(?:remote|over[- ]the[- ]air|OTA|software|firmware)\s+(?:fix|update|patch|repair)\b",
     "KB-03", r"PCX|PowerCharge|charger"),
    ("password change / recovery proves no recording was viewed",
     r"\b(?:password\s+(?:change|reset)|(?:account\s+)?recovery)\s+(?:proves|shows|confirms|ensures|guarantees|means)\b"
     r"|\bno\s+(?:earlier\s+)?recordings?\s+(?:was|were|has\s+been|have\s+been)\s+(?:viewed|accessed|seen)\b",
     "KB-09, KB-04", None),
    # Session 3 (KB-04: "Do not ask customers to send passwords or camera recordings")
    ("asking customers for passwords or recordings",
     r"\b(?:ask(?:s|ed|ing)?|request(?:s|ed|ing)?|tell(?:s|ing)?|told|invit(?:e|es|ed|ing))\s+(?:the\s+)?(?:customers?|users?|owners?|them)\s+"
     r"(?:to\s+(?:send|share|provide|post|give)\s+|for\s+)(?:us\s+)?(?:their\s+|the\s+|your\s+)?"
     r"(?:passwords?|credentials|login\s+details|(?:camera\s+)?recordings?|footage|videos?)\b",
     "KB-04", None),
    # Session 3 (KB-04 "avoid overpromising"; scenario S2: not before the logs are reviewed)
    ("data is safe / no breach occurred",
     r"\b(?:your|customers?'?|the|their|all)\s+(?:personal\s+)?data\s+(?:is|are|was|were|remains?|stays?)\s+(?:safe|secure|protected)\b"
     r"|\bno\s+(?:data\s+|security\s+)?breach\s+(?:has\s+|had\s+)?(?:occurred|happened|taken\s+place|took\s+place)\b"
     r"|\bno\s+(?:personal\s+|customer\s+)?(?:data|recordings?)\s+(?:was|were|has\s+been|have\s+been)\s+(?:accessed|exposed|compromised|leaked)\b",
     "KB-04, scenario S2", None),
    ("password change proves no recording was viewed",
     r"\bpassword\s+(?:change|reset)\s+(?:proves|shows|confirms|ensures|guarantees|means)\b"
     r"|\bno\s+(?:earlier\s+)?recordings?\s+(?:was|were|has\s+been|have\s+been)\s+(?:viewed|accessed|seen)\b",
     "KB-09", None),
]


def find_banned_phrases(texts: dict, state: dict) -> list[str]:
    """Statements ACME's own files say must not be made unless true (KB-03, KB-09, KB-10).

    A negated use ("no remote fix is possible") is fine. The phrase is also allowed when
    the evidence (claims, sources, the user's own words, action history) affirms it.
    """
    support = evidence_text(state)
    problems = []
    for label, pattern, rule_source, scope in BANNED_PHRASES:
        if _affirmed(pattern, support):
            continue
        for where, text in _texts(texts):
            for sentence in _SENTENCE.split(text):
                if scope and not re.search(scope, sentence, re.IGNORECASE):
                    continue
                if _affirmed(pattern, sentence):
                    problems.append(f"{where}: banned phrase '{label}' ({rule_source}) without support in the case data")
                    break
    return problems


# ---------------------------------------------------------------- hard: personal data

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_HANDLE = re.compile(r"(?<![\w.@])@[A-Za-z0-9_]{2,}")
_PHONE = re.compile(r"\+\d[\d \-/().]{7,}\d|\b\d{3,4}[ \-/]\d{3,4}[ \-/]?\d{3,4}\b")
_TITLE_NAME = re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s+([A-Z][a-z]+(?:[- ][A-Z][a-z]+)?)")
# "R. Dubois", but not "batch B. Covers" / "options A and B. Then": a single letter after
# these words is a label, not an initial (false alarm found in session 3).
_INITIAL_NAME = re.compile(
    r"(?<!\bbatch )(?<!\bbatches )(?<!\boption )(?<!\boptions )(?<!\bplan )(?<!\bphase )(?<!\btype )"
    r"(?<!\bmodel )(?<!\bclass )(?<!\bgrade )(?<!\bpart )(?<!\bunit )(?<!\band )(?<!\bor )(?<!\bvs )"
    r"\b[A-Z]\.\s?([A-Z][a-z]{2,})\b")
_INITIAL_NAME = re.compile(r"\b[A-Z]\.\s?([A-Z][a-z]{2,})\b")
_NOT_A_SURNAME = {"The", "This", "That", "These", "Those", "Then", "There", "It", "Its", "In", "On", "At",
                  "As", "An", "And", "But", "If", "No", "Not", "We", "All", "Any", "Each", "For", "From",
                  "Risk", "Quality", "Customer", "Care", "Legal", "Security", "Finance", "Supply"}


def _is_customer_name(surname: str) -> bool:
    return surname.split()[-1] not in ACME_STAFF_SURNAMES and surname not in _NOT_A_SURNAME


def find_personal_data(texts: dict) -> list[str]:
    """Emails (except ACME's own @acme.example), @handles, phone numbers and names written as
    'R. Dubois' or 'Mr Dubois' (ACME staff from KB-02 excepted). Full names are NOT detected."""
    problems = []
    for where, text in _texts(texts):
        found = [m.group(0) for m in _EMAIL.finditer(text) if not m.group(0).lower().endswith("@acme.example")]
        found += [m.group(0) for rx in (_HANDLE, _PHONE) for m in rx.finditer(text)]
        found += [m.group(0) for rx in (_TITLE_NAME, _INITIAL_NAME) for m in rx.finditer(text) if _is_customer_name(m.group(1))]
        if found:
            problems.append(f"{where}: possible personal data: {', '.join(dict.fromkeys(found))}")
    return problems


# ---------------------------------------------------------------- soft checks

_CERTAIN = re.compile(r"\b(confirmed|proven|proves|proved|verified|established)\b", re.IGNORECASE)


def find_overstated_claims(texts: dict, state: dict) -> list[str]:
    """Sentences that cite only non-confirmed claims but call something confirmed/proven."""
    status = {c.get("claim_id"): c.get("status") for c in state.get("claims") or []}
    problems = []
    for where, text in _texts(texts):
        for sentence in _SENTENCE.split(text):
            cited = [i for i in ID_PATTERN.findall(sentence) if i in status]
            if not cited or any(status[i] == "confirmed" for i in cited):
                continue
            if any(not _negated(sentence, m.start()) for m in _CERTAIN.finditer(sentence)):
                problems.append(f"{where}: calls {', '.join(cited)} confirmed/proven, but its status is "
                                f"{', '.join(sorted({status[i] for i in cited}))}{SOFT_SUFFIX}")
    return problems


_LEVEL = re.compile(r"\b(Low|Medium|High|Critical)\b")  # capitalised only: "high temperature" is ignored


def find_unknown_risk_levels(texts: dict, state: dict) -> list[str]:
    """Risk levels named in the text that appear nowhere in the risk data."""
    risk = state.get("risk") or {}
    sources = [risk.get("level"), risk.get("previous_level"), *(risk.get("reasons") or []),
               (state.get("outlook") or {}).get("residual_risk_if_p1_effective"),
               (state.get("closure") or {}).get("remaining_risk")]
    for entry in state.get("changelog") or []:
        sources += [entry.get("risk_from"), entry.get("risk_to")]
    allowed = set(_LEVEL.findall(" ".join(str(x) for x in sources if x)))
    problems = []
    for where, text in _texts(texts):
        bad = sorted(set(_LEVEL.findall(text)) - allowed)
        if bad:
            problems.append(f"{where}: mentions risk level {', '.join(bad)}, which is not in the risk data{SOFT_SUFFIX}")
    return problems


_BLAME = re.compile(
    r"\b(?:customer|user|owner)(?:'s|s')?\s+(?:misuse|error|fault|mistake|negligence|carelessness)\b"
    r"|\b(?:misuse[ds]?|improper(?:ly)?\s+used?|incorrect(?:ly)?\s+used?)\b"
    r"|\bfault\s+of\s+the\s+(?:customer|user)\b"
    r"|\b(?:customer|user)\s+(?:caused|damaged|broke)\b",
    re.IGNORECASE,
)


def find_blame(texts: dict) -> list[str]:
    """Wording that may blame a customer (KB-10: 'one draft sounded like we were blaming a customer')."""
    problems = []
    for where, text in _texts(texts):
        hits = [m.group(0) for m in _BLAME.finditer(text) if not _negated(text, m.start())]
        if hits:
            problems.append(f"{where}: wording may blame a customer: {', '.join(dict.fromkeys(hits))} (KB-10){SOFT_SUFFIX}")
    return problems


def check_word_limits(narrative: dict) -> list[str]:
    warnings = []
    for field, limit in WORD_LIMITS.items():
        text = narrative.get(field)
        if text and len(text.split()) > limit:
            warnings.append(f"{field} has {len(text.split())} words (limit {limit})")
    return warnings


# ---------------------------------------------------------------- combined

def hard_problems(narrative: dict, state: dict) -> list[str]:
    problems = [f"{f}: numbers not found in the case data: {', '.join(n)}"
                for f, n in find_unsupported_numbers(narrative, state).items()]
    problems += [f"{f}: cites IDs that do not exist in the case data: {', '.join(i)}"
                 for f, i in find_unknown_ids(narrative, state).items()]
    problems += find_banned_phrases(narrative, state)
    problems += find_personal_data(narrative)
    return problems


def soft_problems(narrative: dict, state: dict) -> list[str]:
    return (find_overstated_claims(narrative, state)
            + find_unknown_risk_levels(narrative, state)
            + find_blame(narrative)
            + check_word_limits(narrative))


def other_agent_texts(state: dict) -> dict[str, str]:
    """Texts written by A2-A4 that appear in the report (labelled by where they come from).
    Claims are excluded: they record what was reported, and may quote anything."""
    texts: dict[str, str] = {}
    for a in state.get("actions") or []:
        aid = a.get("action_id")
        for key in ("title", "what_it_does", "expected_effect"):
            texts[f"{aid} {key}"] = a.get(key)
        for n, o in enumerate(a.get("options_considered") or [], start=1):
            for key in ("option", "pros", "cons"):
                texts[f"{aid} option {n} {key}"] = o.get(key)
    for st in state.get("stakeholders") or []:
        for key in ("interest", "impact"):
            texts[f"stakeholder '{st.get('name')}' {key}"] = st.get(key)
    for domain, block in (state.get("impacts") or {}).items():
        for n, imp in enumerate((block or {}).get("impacts") or [], start=1):
            for key in ("description", "if_unaddressed"):
                texts[f"{domain} impact {n} {key}"] = imp.get(key)
    for key, items in (state.get("outlook") or {}).items():
        if isinstance(items, list):
            for n, x in enumerate(items, start=1):
                texts[f"outlook {key} {n}"] = x
    return texts


def check_other_agents(state: dict) -> list[str]:
    """Safety net (warnings only): banned phrases, personal data and blame wording in the
    texts other agents wrote. A5 never changes those texts; checking them is A4's job."""
    texts = other_agent_texts(state)
    return find_banned_phrases(texts, state) + find_personal_data(texts) + find_blame(texts)
