"""A1 — Evidence Analyst
======================
Owned by: Giacomo Castelmare
Spec:     agents/A1_evidence_analyst.md
Prompt:   src/prompts/a1.md

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
from pathlib import Path

from src.contracts import A1Output, CaseState, TurnInput
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


def _build_user_content(state: CaseState, turn: TurnInput) -> list[dict]:
    """Compose the user message: ID hints + case context + new input + attachments."""
    next_src = _next_source_id(state)
    next_clm = _next_claim_id(state)

    # Serialise the existing evidence so the LLM can re-evaluate it
    existing = {
        "case_id": state.case_id,
        "version": state.version,
        "existing_sources": [s.model_dump(mode="json") for s in state.sources],
        "existing_claims": [c.model_dump(mode="json") for c in state.claims],
        "open_questions": [q.model_dump(mode="json") for q in state.open_questions],
    }

    blocks: list[dict] = [
        {
            "type": "text",
            "text": (
                f"=== ID allocation (do not reuse existing IDs) ===\n"
                f"Next source ID : {next_src}  (then {next_src[:-2]}{int(next_src[2:])+1:02d}, …)\n"
                f"Next claim ID  : {next_clm}  (then {next_clm[:-3]}{int(next_clm[2:])+1:03d}, …)\n"
                f"Current case version: {state.version}\n"
                f"Use `raised_in_version: {state.version}` for all new open_questions.\n"
            ),
        },
        {
            "type": "text",
            "text": f"=== Existing case state ===\n{json.dumps(existing, indent=2, ensure_ascii=False)}",
        },
    ]

    if turn.user_text.strip():
        blocks.append({"type": "text", "text": f"=== New user input ===\n{turn.user_text}"})

    # Attachments: file paths → native content blocks (image / document / text)
    for path_str in turn.attachments:
        p = Path(path_str)
        if p.exists():
            blocks.append(file_block(p))
        else:
            blocks.append({"type": "text", "text": f"[Attachment not found on disk: {path_str}]"})

    return blocks


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
    user_content = _build_user_content(state, turn)

    return call_structured(
        agent="A1",
        system_prompt=load_prompt("a1"),
        user_content=user_content,
        output_model=A1Output,
        effort="high",
        case_id=state.case_id,
    )
