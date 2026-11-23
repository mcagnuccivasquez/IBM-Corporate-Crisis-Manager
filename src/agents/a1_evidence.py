"""A1 — Evidence Analyst
======================
Owned by: Giacomo Castelmare
Spec:     agents/A1_evidence_analyst.md
Prompt:   src/prompts/a1_evidence.md

Entry point
-----------
    from src.agents.a1_evidence import run
    output: A1Output = run(state, turn)

The function sends one structured LLM call (Claude Sonnet 5.5) and returns an
A1Output instance. A0 merges the result into CaseState by source_id / claim_id.

Contract rules A1 must honour (enforced again by contracts.py validators):
- Sources:  new U-xx IDs, continuing from the highest existing one.
- Claims:   every claim needs ≥1 source_id and ≥1 change_history entry;
            status must equal the last change_history entry's `to` field.
- Updates:  return the full claim (with the new change_history entry appended);
            A0 merges by claim_id and checks that history is preserved.
- open_questions: raised_in_version = state.version (the *new* version A0 is building).
"""

from __future__ import annotations

import json
import re

from src.contracts import A1Output, CaseState, TurnInput
from src.kb import unknown_kb_ids
from src.llm import call_structured, file_block, load_prompt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_source_id(state: CaseState) -> str:
    """Return the first free U-xx ID (zero-padded to 2 digits minimum)."""
    nums = [
        int(s.source_id[2:])
        for s in state.sources
        if re.match(r"^U-\d+$", s.source_id)
    ]
    return f"U-{(max(nums) + 1) if nums else 1:02d}"


def _next_claim_id(state: CaseState) -> str:
    """Return the first free C-xxx ID (zero-padded to 3 digits minimum)."""
    nums = [
        int(c.claim_id[2:])
        for c in state.claims
        if re.match(r"^C-\d+$", c.claim_id)
    ]
    return f"C-{(max(nums) + 1) if nums else 1:03d}"


def _build_context_block(state: CaseState) -> str:
    """Serialise existing case state + ID allocation hints as a text string."""
    next_src = _next_source_id(state)
    next_clm = _next_claim_id(state)

    existing = {
        "case_id": state.case_id,
        "version": state.version,
        "existing_sources": [s.model_dump(mode="json") for s in state.sources],
        "existing_claims": [c.model_dump(mode="json") for c in state.claims],
        "open_questions": [q.model_dump(mode="json") for q in state.open_questions],
    }

    return (
        f"=== ID allocation (do not reuse existing IDs) ===\n"
        f"Next source ID : {next_src}  (then {next_src[:-2]}{int(next_src[2:])+1:02d}, …)\n"
        f"Next claim ID  : {next_clm}  (then {next_clm[:-3]}{int(next_clm[2:])+1:03d}, …)\n"
        f"Current case version: {state.version}\n"
        f"Use `raised_in_version: {state.version}` for all new open_questions.\n"
        f"\n=== Existing case state ===\n"
        f"{json.dumps(existing, indent=2, ensure_ascii=False)}"
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run(state: CaseState, turn: TurnInput) -> A1Output:
    """Run the A1 Evidence Analyst for one turn.

    Parameters
    ----------
    state : CaseState
        Current case state at version N-1 (a snapshot; A0 passes this in).
    turn  : TurnInput
        New user input + attachment file paths.

    Returns
    -------
    A1Output
        New and updated sources, claims, and open questions.
        A0 merges these into CaseState by ID and validates the result.

    Raises
    ------
    src.llm.LLMError (and subclasses LLMRefusal, LLMTruncated, LLMOutputError)
        Callers should catch LLMError; A0 wraps it in TurnResult.error.
    """
    content: list[dict] = [file_block(p) for p in turn.attachments]
    content.append({"type": "text", "text": _build_context_block(state) + "\n\n" + turn.user_text})

    return call_structured(
        "A1",
        load_prompt("a1_evidence"),
        content,
        A1Output,
        "high",
        case_id=state.case_id,
        check=lambda out: [
            f"unknown KB id {i}"
            for i in unknown_kb_ids([s for c in out.claims for s in c.source_ids])
        ],
    )
