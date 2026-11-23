"""A5 Report Writer: the narrative paragraphs of the report (LLM via src/llm.py).

Pipeline interface (PROJECT.md §9, D-013): run(state, turn, prev_state) -> A5Output.
The pipeline validates the state and then renders the PDF itself with
src/report/render.py: render_pdf(state, pdf_path). This module never writes files.

Behaviour agreed with Serdar (2026-11-21); the checks live in src/report/checks.py:
- HARD checks (invented numbers incl. number words, unknown IDs, banned phrases from
  KB-03/09/10, personal data incl. "R. Dubois"-style names) run inside
  llm.call_structured(check=...), which retries ONCE; what is left -> warning.
- SOFT checks ("confirmed" on unconfirmed claims, unknown risk level, blaming wording,
  word limits) -> warning only.
- AI fact-check pass: a second light-model call compares each sentence with the case data
  and lists mismatches (e.g. a real number used for the wrong thing) -> warning only.
- LLM call fails (no key, network, refusal) -> "Narrative not available (AI step failed)";
  the pipeline still produces the PDF, and all tables are unaffected.
"""

from __future__ import annotations

import copy
import json
from typing import Optional

from pydantic import BaseModel, ValidationError

from src.contracts import A5Output, CaseState, TurnInput
from src.llm import LLMError, LLMOutputError, call_structured, load_prompt
from src.report.checks import (  # noqa: F401  (re-exported for tests and readers)
    FIELDS,
    SOFT_SUFFIX,
    WORD_LIMITS,
    check_word_limits,
    find_banned_phrases,
    find_blame,
    find_overstated_claims,
    find_personal_data,
    find_unknown_ids,
    find_unknown_risk_levels,
    find_unsupported_numbers,
    hard_problems,
    soft_problems,
    state_without_report,
)

# The model is chosen by llm.py: agents named "A5..." run on the light model (Haiku 5.5, D-012).
FAILED_TEXT = "Narrative not available (AI step failed)."
FACT_CHECK_SUFFIX = " (AI fact-check; may be a false alarm, please review)"


class Narrative(BaseModel):
    executive_summary: str
    situation: str
    changes_summary: Optional[str] = None
    closure_summary: Optional[str] = None


class FactIssue(BaseModel):
    field: str
    sentence: str
    issue: str


class FactCheck(BaseModel):
    issues: list[FactIssue]


# ---------------------------------------------------------------- helpers

def _case_json(state: dict) -> str:
    return json.dumps(state_without_report(state), ensure_ascii=False, sort_keys=True, indent=1)


def _user_message(state: dict) -> str:
    return f"Case state (version {state['version']}, status {state.get('status')}):\n\n{_case_json(state)}"


def _clean(narrative: Narrative | dict) -> dict[str, str]:
    """Drop empty keys: report.narrative values must be text, never null (D-013)."""
    data = narrative.model_dump() if isinstance(narrative, BaseModel) else narrative
    return {k: v.strip() for k, v in data.items() if isinstance(v, str) and v.strip()}


def _failed(state: dict) -> dict[str, str]:
    narrative = {"executive_summary": FAILED_TEXT, "situation": FAILED_TEXT}
    if state.get("version", 1) > 1:
        narrative["changes_summary"] = FAILED_TEXT
    if state.get("status") == "closed":
        narrative["closure_summary"] = FAILED_TEXT
    return narrative


# ---------------------------------------------------------------- AI fact-check pass

def fact_check(narrative: dict[str, str], state: dict, *, client=None) -> list[str]:
    """Second light-model call: list sentences whose facts don't match the case data.
    Warnings only; if the call fails, say so instead of pretending the text was checked."""
    user = (f"Case state (version {state['version']}):\n\n{_case_json(state)}\n\n"
            f"Narrative to check:\n\n{json.dumps(narrative, ensure_ascii=False, indent=1)}")
    try:
        result = call_structured("A5-factcheck", load_prompt("a5_factcheck"), user, FactCheck, "low",
                                 case_id=state.get("case_id"), client=client)
    except LLMError as e:
        return [f"AI fact-check not run: {e}"]
    return [f'{i.field}: {i.issue}: "{i.sentence}"{FACT_CHECK_SUFFIX}' for i in result.issues]


# ---------------------------------------------------------------- narrative

def write_narrative(state: dict, *, client=None, run_fact_check: bool = True) -> tuple[dict[str, str], list[str]]:
    """Return (narrative, warnings). Never raises on LLM failure: the PDF must still be produced.

    The hard checks run inside llm.call_structured(check=...), which retries once with the
    list of problems (the same single retry for format errors and for our checks).
    """
    try:
        parsed = call_structured(
            "A5", load_prompt("a5_report"), _user_message(state), Narrative, "low",
            case_id=state.get("case_id"),
            check=lambda n: hard_problems(_clean(n), state),
            client=client,
        )
        narrative = _clean(parsed)
    except LLMOutputError as e:
        # Still wrong after the one retry: keep the text if it is valid JSON, and flag the problems.
        try:
            narrative = _clean(Narrative.model_validate_json(e.raw_text))
        except ValidationError:
            return _failed(state), [f"AI step failed: output invalid after one retry: {'; '.join(e.problems)}"]
    except LLMError as e:  # API down, no key, refusal, cut off
        return _failed(state), [f"AI step failed: {e}"]

    warnings = hard_problems(narrative, state) + soft_problems(narrative, state)
    if run_fact_check:
        warnings += fact_check(narrative, state, client=client)
    return narrative, warnings


# ---------------------------------------------------------------- agent entry point

def run(state: CaseState, turn: TurnInput | None = None, prev_state: CaseState | None = None,
        *, client=None) -> A5Output:
    """Pipeline entry point: write the narrative for this version. Does not render the PDF.

    `prev_state` is not needed: A0 has already built this version's changelog entry, which
    carries the previous risk level and the changes. `client` is only for tests (fake Claude).
    """
    data = state.model_dump(mode="json") if hasattr(state, "model_dump") else copy.deepcopy(state)
    narrative, warnings = write_narrative(data, client=client)
    return A5Output(
        narrative=narrative,
        changes_summary=narrative.get("changes_summary", ""),
        narrative_warnings=warnings,
    )
