"""A5 Report Writer: narrative (LLM) + PDF (code).

run(state) asks Claude for the four narrative paragraphs, checks them, and renders
cases/<case_id>/report_v<N>.pdf via src/report/render.py.

Behaviour agreed with Serdar (2026-11-21):
- "Hard" checks (reliable): invented numbers, citations to IDs that do not exist,
  banned phrases (KB-03, KB-09, KB-10) without support in the case data, personal data.
  Any hard problem -> ONE combined retry; problems left after it -> warning in Appendix C.
- "Soft" checks (heuristics, may misfire): "confirmed" said about a claim that is not
  confirmed; a risk level that does not appear in the case data; word limits.
  -> warning only, never a retry, never cutting text.
- LLM call fails (no key, network, refusal) -> PDF is still produced; narrative
  paragraphs say "Narrative not available (AI step failed)"; tables are unaffected.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SRC_DIR.parent))

from src.report import render  # noqa: E402

PROMPT_PATH = SRC_DIR / "prompts" / "a5_report.md"
MODEL = "claude-opus-5-5"
FIELDS = ("executive_summary", "situation", "changes_summary", "closure_summary")
WORD_LIMITS = {"executive_summary": 80, "situation": 150, "changes_summary": 120, "closure_summary": 120}
FAILED_TEXT = "Narrative not available (AI step failed)."
SOFT_SUFFIX = " (automatic check; may be a false alarm, please review the wording)"


class Narrative(BaseModel):
    executive_summary: str
    situation: str
    changes_summary: Optional[str] = None
    closure_summary: Optional[str] = None


def _texts(narrative: dict):
    for field in FIELDS:
        text = narrative.get(field)
        if text:
            yield field, text


def state_without_report(state: dict) -> dict:
    """The case state the narrative may draw on (the previous narrative is excluded)."""
    return {k: v for k, v in state.items() if k not in ("report", "_comment")}


def _state_text(state: dict) -> str:
    return json.dumps(state_without_report(state), ensure_ascii=False)


_NEGATION = re.compile(r"\b(no|not|never|cannot|can't|without|nor)\b|n't\b", re.IGNORECASE)


def _negated(text: str, start: int, window: int = 5) -> bool:
    """True if one of the `window` words before position `start` is a negation."""
    before = text[:start].split()[-window:]
    return bool(_NEGATION.search(" ".join(before)))


# ---------------------------------------------------------------- hard check 1: numbers

_NUMBER = re.compile(r"\d[\d,.]*\d|\d")
_CITATION = re.compile(r"\[[^\]]*\]")


def _numbers(text: str) -> set:
    found = set()
    for raw in _NUMBER.findall(text):
        cleaned = raw.replace(",", "")
        try:
            found.add(float(cleaned))
        except ValueError:  # e.g. "1.2.3" (a version string): compare as text instead
            found.add(raw)
    return found


def find_unsupported_numbers(narrative: dict, state: dict) -> dict[str, list[str]]:
    """Numbers in each narrative field that do not appear anywhere in the case state.

    Citations in brackets ([C-007, U-03]) are ignored. "11,000" and "11000" count as
    the same number. Limitation: numbers written as words ("two") are not checked, and a
    number that exists in the state but is used for the wrong thing is not caught.
    """
    allowed = _numbers(_state_text(state))
    problems: dict[str, list[str]] = {}
    for field, text in _texts(narrative):
        bad = []
        for raw in _NUMBER.findall(_CITATION.sub("", text)):
            value = next(iter(_numbers(raw)))
            if value not in allowed and raw not in bad:
                bad.append(raw)
        if bad:
            problems[field] = bad
    return problems


# ---------------------------------------------------------------- hard check 2: citations

def find_unknown_ids(narrative: dict, state: dict) -> dict[str, list[str]]:
    """IDs (C-, U-, KB-, ACT-) in the narrative that do not exist in the case state."""
    known = render.known_ids(state)
    problems: dict[str, list[str]] = {}
    for field, text in _texts(narrative):
        bad = []
        for id_ in render.ID_PATTERN.findall(text):
            if id_ not in known and id_ not in bad:
                bad.append(id_)
        if bad:
            problems[field] = bad
    return problems


# ---------------------------------------------------------------- hard check 3: banned phrases
# Each rule: (label, regex, source of the rule, only-in-sentences-matching or None)
BANNED_PHRASES = [
    ("authorities contacted",
     r"\b(contacted|notified|informed|alerted)\s+(the\s+)?(relevant\s+|competent\s+)?authorit(y|ies)\b"
     r"|\bauthorit(y|ies)\s+(have|has|had|were|was)\s+(been\s+)?(contacted|notified|informed|alerted)\b",
     "KB-10", None),
    ("independent tests", r"\bindependent(ly)?\s+(lab(oratory)?\s+)?test(s|ed|ing)?\b", "KB-10", None),
    ("all units tested",
     r"\ball\s+(the\s+)?(units|chargers|devices|products|cameras)\s+(were\s+|have\s+been\s+|are\s+|being\s+|got\s+)?(tested|checked)\b",
     "KB-10", None),
    ("remote fix for PCX-100", r"\b(remote|over[- ]the[- ]air|OTA)\s+(firmware\s+)?(fix|update|patch)\b",
     "KB-03", r"PCX|PowerCharge|charger"),
    ("password change proves no recording was viewed",
     r"\bpassword\s+(change|reset)\s+(proves|shows|confirms|ensures|guarantees)\b", "KB-09", None),
]

_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _affirmed_matches(pattern: str, text: str) -> list[str]:
    return [m.group(0) for m in re.finditer(pattern, text, re.IGNORECASE) if not _negated(text, m.start())]


def find_banned_phrases(narrative: dict, state: dict) -> list[str]:
    """Phrases ACME's own files say must not be used unless true (KB-03, KB-09, KB-10).

    A negated use ("no remote fix is possible") is fine. A phrase is also allowed when the
    case state itself affirms it (e.g. the user reported that authorities were contacted).
    """
    state_text = _state_text(state)
    problems = []
    for label, pattern, rule_source, scope in BANNED_PHRASES:
        if _affirmed_matches(pattern, state_text):
            continue  # the case data supports it
        for field, text in _texts(narrative):
            for sentence in _SENTENCE.split(text):
                if scope and not re.search(scope, sentence, re.IGNORECASE):
                    continue
                if _affirmed_matches(pattern, sentence):
                    problems.append(f"{field}: banned phrase '{label}' ({rule_source}) without support in the case data")
                    break
    return problems


# ---------------------------------------------------------------- hard check 4: personal data

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_HANDLE = re.compile(r"(?<![\w.@])@[A-Za-z0-9_]{2,}")
_PHONE = re.compile(r"\+\d[\d \-/().]{7,}\d|\b\d{3,4}[ \-/]\d{3,4}[ \-/]?\d{3,4}\b")


def find_personal_data(narrative: dict) -> list[str]:
    """Emails, social-media handles and phone numbers. Names are NOT detected."""
    problems = []
    for field, text in _texts(narrative):
        found = [m.group(0) for rx in (_EMAIL, _HANDLE, _PHONE) for m in rx.finditer(text)]
        if found:
            problems.append(f"{field}: possible personal data: {', '.join(dict.fromkeys(found))}")
    return problems


# ---------------------------------------------------------------- soft checks

_CERTAIN = re.compile(r"\b(confirmed|proven|proves|proved|verified|established)\b", re.IGNORECASE)


def find_overstated_claims(narrative: dict, state: dict) -> list[str]:
    """Sentences that cite only non-confirmed claims but call something confirmed/proven."""
    status = {c.get("claim_id"): c.get("status") for c in state.get("claims") or []}
    problems = []
    for field, text in _texts(narrative):
        for sentence in _SENTENCE.split(text):
            cited = [i for i in render.ID_PATTERN.findall(sentence) if i in status]
            if not cited or any(status[i] == "confirmed" for i in cited):
                continue
            if any(not _negated(sentence, m.start()) for m in _CERTAIN.finditer(sentence)):
                problems.append(f"{field}: calls {', '.join(cited)} confirmed/proven, but its status is "
                                f"{', '.join(sorted({status[i] for i in cited}))}{SOFT_SUFFIX}")
    return problems


_LEVEL = re.compile(r"\b(Low|Medium|High|Critical)\b")  # capitalised only: "high temperature" is ignored


def find_unknown_risk_levels(narrative: dict, state: dict) -> list[str]:
    """Risk levels named in the narrative that appear nowhere in the risk data."""
    risk = state.get("risk") or {}
    sources = [risk.get("level"), risk.get("previous_level"), *(risk.get("reasons") or []),
               (state.get("outlook") or {}).get("residual_risk_if_p1_effective"),
               (state.get("closure") or {}).get("remaining_risk")]
    for entry in state.get("changelog") or []:
        sources += [entry.get("risk_from"), entry.get("risk_to")]
    allowed = set(_LEVEL.findall(" ".join(str(x) for x in sources if x)))
    problems = []
    for field, text in _texts(narrative):
        bad = sorted(set(_LEVEL.findall(text)) - allowed)
        if bad:
            problems.append(f"{field}: mentions risk level {', '.join(bad)}, which is not in the risk data{SOFT_SUFFIX}")
    return problems


def check_word_limits(narrative: dict) -> list[str]:
    warnings = []
    for field, limit in WORD_LIMITS.items():
        text = narrative.get(field)
        if text and len(text.split()) > limit:
            warnings.append(f"{field} has {len(text.split())} words (limit {limit})")
    return warnings


# ---------------------------------------------------------------- combining the checks

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
            + check_word_limits(narrative))


# ---------------------------------------------------------------- LLM call
# TEMPORARY: a minimal Claude call kept inside A5 until the shared src/llm.py (Matteo)
# exists. Replace _call_claude with the llm.py wrapper then.

def _call_claude(system: str, user: str, client=None) -> Narrative:
    import anthropic

    client = client or anthropic.Anthropic()
    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=Narrative,
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined the request (refusal)")
    if response.parsed_output is None:
        raise RuntimeError(f"No structured output (stop_reason={response.stop_reason})")
    return response.parsed_output


def _user_message(state: dict, feedback: str | None = None) -> str:
    case_json = json.dumps(state_without_report(state), ensure_ascii=False, sort_keys=True, indent=1)
    msg = f"Case state (version {state['version']}, status {state.get('status')}):\n\n{case_json}"
    if feedback:
        msg += f"\n\n{feedback}"
    return msg


def write_narrative(state: dict, client=None) -> tuple[dict, list[str]]:
    """Return (narrative dict, warnings). Never raises on LLM failure."""
    system = PROMPT_PATH.read_text(encoding="utf-8")
    try:
        narrative = _call_claude(system, _user_message(state), client).model_dump()
        problems = hard_problems(narrative, state)
        if problems:
            feedback = (
                "Your previous draft had these problems:\n- " + "\n- ".join(problems) +
                "\nRewrite the narrative and fix them. Use only numbers and IDs that appear in the case state, "
                "and no personal data.\n\n"
                f"Previous draft:\n{json.dumps(narrative, ensure_ascii=False, indent=1)}"
            )
            narrative = _call_claude(system, _user_message(state, feedback), client).model_dump()
    except Exception as exc:  # no key, network, refusal, invalid output: PDF still produced
        narrative = {f: FAILED_TEXT for f in ("executive_summary", "situation")}
        narrative.update({"changes_summary": None if state["version"] == 1 else FAILED_TEXT,
                          "closure_summary": FAILED_TEXT if state.get("status") == "closed" else None})
        return narrative, [f"AI step failed: {type(exc).__name__}: {exc}"]

    return narrative, hard_problems(narrative, state) + soft_problems(narrative, state)


# ---------------------------------------------------------------- agent entry point

def run(state: Any, turn: Any = None, cases_dir: str | Path = "cases", client=None) -> dict:
    """Write the narrative, render the PDF, and return A5's output for A0 to merge.

    Returns {"narrative": {...}, "narrative_warnings": [...], "pdf_path": "..."}.
    The input state is not modified.
    """
    s = copy.deepcopy(state.model_dump(mode="json") if hasattr(state, "model_dump") else state)
    narrative, warnings = write_narrative(s, client)
    out_path = render.pdf_path_for(s, cases_dir)
    s["report"] = {"pdf_path": str(out_path), "narrative": narrative, "narrative_warnings": warnings}
    render.render_pdf(s, cases_dir)
    return s["report"]


if __name__ == "__main__":
    # Manual run: python src/agents/a5_report.py [state.json] [cases_dir]
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else SRC_DIR / "report" / "sample_state_v1_TEMPORARY.json"
    cases = sys.argv[2] if len(sys.argv) > 2 else "cases"
    result = run(json.loads(src.read_text(encoding="utf-8")), cases_dir=cases)
    print(json.dumps(result, ensure_ascii=False, indent=1))
