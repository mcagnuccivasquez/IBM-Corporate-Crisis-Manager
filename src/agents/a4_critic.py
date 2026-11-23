"""A4 Critic & Outlook agent (agents/A4_critic_outlook.md).

Two steps:
1. Free pre-pass  — `src/report/checks.check_other_agents` runs on the full state
   without an LLM call.  Every hit is turned into a QAIssue before the LLM sees the state.
2. LLM review     — Sonnet 5.5 audits grounding (G1–G3), traps (T1–T12) and method
   consistency (M1–M6), and projects the Outlook.

Pre-pass rule mapping (from the director message, 2026-11-23):
  - ACT-xxx prefix  → target A3
  - stakeholder …   → target A3
  - … impact …      → target A2
  - outlook …       → target A4 (self; own text)
  - banned phrase, personal data → blocking=True
  - blame wording   → blocking=False (soft; LLM review decides)
"""

from __future__ import annotations

import json

from src.contracts import (
    A4Output,
    AgentId,
    CaseState,
    Outlook,
    QA,
    QAIssue,
    QAVerdict,
    TurnInput,
)
from src.llm import call_structured, load_prompt
from src.report.checks import check_other_agents


# ------------------------------------------------------------------ pre-pass


def _prepass_issues(state: CaseState) -> list[QAIssue]:
    """Run check_other_agents; map each hit to a QAIssue."""
    hits = check_other_agents(state.model_dump(mode="json"))
    issues: list[QAIssue] = []
    for hit in hits:
        # Determine owning agent and item_id from the label prefix
        label = hit.split(":")[0].strip()  # e.g. "ACT-002 what_it_does" / "outlook assumptions 1"
        target, item_id = _map_label(label)

        # Blocking: banned phrases and personal data are hard; blame is soft
        is_soft = "(automatic check; may be a false alarm" in hit or "wording may blame" in hit
        blocking = not is_soft

        issues.append(
            QAIssue(
                target=target,
                item_id=item_id,
                problem=hit,
                fix_hint=(
                    "Remove or replace the flagged text. See src/report/checks.py for the rule."
                ),
                blocking=blocking,
            )
        )
    return issues


def _map_label(label: str) -> tuple[AgentId, str | None]:
    """Return (target agent, item_id or None) from a checks.py label prefix."""
    upper = label.upper()
    if upper.startswith("ACT-"):
        # e.g. "ACT-002 what_it_does" → A3, item_id=ACT-002
        item_id = label.split()[0]
        return "A3", item_id
    if "STAKEHOLDER" in upper:
        return "A3", None
    if "IMPACT" in upper:
        return "A2", None
    if "OUTLOOK" in upper:
        return "A4", None
    # Fallback: ownership unclear → A3 (most text comes from A3)
    return "A3", None


# ------------------------------------------------------------------ main entry point


def a4(state: CaseState, turn: TurnInput) -> A4Output:
    """Run A4 Critic & Outlook.

    1. Free pre-pass with check_other_agents.
    2. If pre-pass found blocking issues and there are more than 3 blocking hits,
       skip the LLM call to save cost — verdict is already REVISE.
       Otherwise always call the LLM for the full audit and outlook.
    3. Merge pre-pass issues into the LLM result (deduplicate by problem text).
    """
    prepass = _prepass_issues(state)

    # Build user content for the LLM
    prev_qa_summary = ""
    if prepass:
        lines = [f"  - [{'+blocking' if i.blocking else 'warning'}] {i.problem}" for i in prepass]
        prev_qa_summary = (
            "\n\n<pre_pass_issues>\n"
            "The following issues were found by the automated check before your review.\n"
            "Include each relevant issue in your qa.issues (do not omit or contradict them):\n"
            + "\n".join(lines)
            + "\n</pre_pass_issues>"
        )

    state_json = state.model_dump_json(indent=2)
    user_content = (
        f"<case_state>\n{state_json}\n</case_state>"
        + prev_qa_summary
    )

    llm_output: A4Output = call_structured(
        agent="A4",
        system_prompt=load_prompt("a4_critic"),
        user_content=user_content,
        output_model=A4Output,
        effort="high",
        case_id=state.case_id,
    )

    # Merge: add any pre-pass issue whose problem text is not already in the LLM output
    existing_problems = {i.problem for i in llm_output.qa.issues}
    extra = [i for i in prepass if i.problem not in existing_problems]
    merged_issues = llm_output.qa.issues + extra

    # Re-evaluate verdict: any blocking issue → REVISE (corrects LLM if it said PASS with blocking issues)
    correct_verdict: QAVerdict = (
        "REVISE" if any(i.blocking for i in merged_issues) else "PASS"
    )
    if extra or correct_verdict != llm_output.qa.verdict:
        llm_output = A4Output(
            qa=QA(verdict=correct_verdict, issues=merged_issues),
            outlook=llm_output.outlook,
            reopen_conditions=llm_output.reopen_conditions,
        )

    return llm_output


# Pipeline entry point (src/pipeline.py REAL_AGENTS expects "run")
run = a4
