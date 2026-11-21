"""Stub agents: return fixture JSON from tests/fixtures/stubs/ so the pipeline runs
end to end before the real agents exist. No LLM calls, no API key.

Each stub has the same signature as the real agent it stands in for (see AgentSet
in src/pipeline.py). Replace one by adding the real module; the registry picks it up.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.contracts import (
    RISK_LEVELS,
    A1Output,
    A3Output,
    A4Output,
    A5Output,
    CaseState,
    Domain,
    DomainImpact,
    Risk,
    TurnInput,
)
from src.kb import ROOT

FIXTURES = ROOT / "tests" / "fixtures" / "stubs"


def _load(name: str) -> str:
    return (FIXTURES / f"{name}.json").read_text(encoding="utf-8")


def a1(state: CaseState, turn: TurnInput) -> A1Output:
    return A1Output.model_validate_json(_load("a1"))


def a2(state: CaseState, turn: TurnInput, domain: Domain) -> DomainImpact:
    return DomainImpact.model_validate_json(_load(f"a2_{domain}"))


def a3(state: CaseState, turn: TurnInput) -> A3Output:
    return A3Output.model_validate_json(_load("a3"))


def a4(state: CaseState, turn: TurnInput) -> A4Output:
    return A4Output.model_validate_json(_load("a4"))


def a5(state: CaseState, turn: TurnInput, prev: CaseState | None) -> A5Output:
    return A5Output.model_validate_json(_load("a5"))


def risk(state: CaseState, prev: CaseState | None) -> Risk:
    """Minimal stand-in for risk.py (Junda): PROJECT §6 steps 2-3 without F4.
    NOT the real engine; do not test the risk method against this."""
    blocks = [b for b in (state.impacts.reputational, state.impacts.economic, state.impacts.legal_regulatory) if b]
    max_score = max((b.score or 0 for b in blocks), default=0)
    level = "Low" if max_score <= 3 else "Medium" if max_score <= 6 else "High" if max_score <= 9 else "Critical"
    reasons = [f"[STUB risk] max domain score {max_score} → {level}"]
    floors = sorted({f for b in blocks for f in b.floor_triggers if f != "F4"})
    for f in floors:
        floor_level = "Critical" if f == "F2" else "High"
        if RISK_LEVELS.index(floor_level) > RISK_LEVELS.index(level):
            level = floor_level
        reasons.append(f"[STUB risk] {f} → at least {floor_level}")
    confidences = [b.evidence_confidence for b in blocks]
    confidence = "low" if "low" in confidences else "medium" if "medium" in confidences else "high"
    return Risk(
        level=level,
        previous_level=prev.risk.level if prev and prev.risk else None,
        max_domain_score=max_score,
        floors_applied=floors,
        reasons=reasons,
        evidence_confidence=confidence,
    )


def render(state: CaseState, path: Path) -> Path:
    """Stand-in for A5's PDF renderer: a one-page PDF with the header and narrative."""
    import pymupdf

    risk = state.risk
    lines = [
        f"ACME Crisis Management Report  [STUB RENDERER]",
        f"Case {state.case_id} · version {state.version} · status {state.status}",
        f"Risk: {risk.previous_level or '-'} -> {risk.level} (evidence confidence: {risk.evidence_confidence})" if risk else "Risk: -",
        "",
    ]
    if state.report:
        for section, text in state.report.narrative.items():
            lines += [section.upper(), text, ""]
    lines += [f"Sources: {len(state.sources)} · Claims: {len(state.claims)} · Actions: {len(state.actions)}"]
    text = "\n".join(lines).replace("·", "-").replace("→", "->")
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 545, 800), text, fontsize=10)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return path


# -- A0 helpers in stub mode (no LLM) -----------------------------------------


def classify_intent(user_text: str, has_attachments: bool, case_id: str | None = None) -> dict:
    t = user_text.lower().strip()
    intents: list[str] = []
    focus = None
    if re.search(r"\b(close the case|close it|we can stop|stop here)\b", t):
        intents.append("CLOSE")
    m = re.search(r"\bfocus on (.+?)(?:[.!?]|$)", t)
    if m:
        intents.append("SET_FOCUS")
        focus = m.group(1).strip()
    if re.search(r"\b(approved|completed|done|implemented|carried out)\b", t):
        intents.append("ACTION_UPDATE")
    is_question = t.endswith("?") and not has_attachments
    if is_question and not intents:
        intents.append("QUESTION")
    if not intents or (has_attachments and "NEW_INFO" not in intents and "ACTION_UPDATE" not in intents):
        intents.append("NEW_INFO")
    return {
        "intents": intents,
        "focus": focus,
        "question": user_text if "QUESTION" in intents else None,
        "close_requested": "CLOSE" in intents,
    }


def answer_question(state: CaseState, question: str) -> dict:
    risk = state.risk
    answer = (
        f"[STUB answer] Current risk is {risk.level}. " + " ".join(risk.reasons)
        if risk
        else "[STUB answer] No report exists yet for this case."
    )
    return {"answer": answer, "cited_ids": []}
