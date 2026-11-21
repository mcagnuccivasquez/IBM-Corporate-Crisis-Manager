"""
A1 — Evidence Analyst
=====================
Owned by: Giacomo Castelmare
Spec: agents/A1_evidence_analyst.md

Entry point
-----------
    from src.agents.a1_evidence import run
    output = run(state, turn)

The function sends a single LLM call (Claude, structured output) and returns
an A1Output object.  A0 merges the result into CaseState.

Stubs
-----
Until src/contracts.py and src/llm.py land (Matteo), this module defines
the minimum Pydantic models it needs inline and uses a lightweight LLM helper.
When those modules exist:
  - Replace the "--- Inline stubs ---" sections below with:
      from src.contracts import (
          CaseState, TurnInput, Source, Claim, ClaimUpdate, EvidenceGap
      )
      from src.llm import call_structured
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

import anthropic
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# --- Inline stubs (replace with contracts.py imports when available) --------
# ---------------------------------------------------------------------------

class TurnInput(BaseModel):
    intent: str = "NEW_INFO"
    user_text: str = ""
    attachments: list[str] = Field(default_factory=list)  # file paths


class Source(BaseModel):
    source_id: str
    title: str
    file: Optional[str] = None
    origin: str                     # kb | user_upload | user_text
    date: Optional[str] = None      # date of content (not upload)
    category: str                   # incident_evidence | company_record |
                                    # historical_case | informal_note |
                                    # planning_assumption | reference
    time_relevance: str             # current | historical
    duplicate_of: Optional[str] = None
    reliability_note: Optional[str] = None
    added_in_version: int = 1


class Claim(BaseModel):
    claim_id: str
    text: str
    status: str                     # confirmed | unconfirmed | disproved | misleading
    evidence_strength: str          # strong | moderate | weak
    source_ids: list[str]
    contradicted_by: list[str] = Field(default_factory=list)
    domains: list[str]              # reputational | economic | legal_regulatory
    product: Optional[str] = None
    batch: Optional[str] = None
    market: Optional[str] = None
    first_seen_version: int = 1
    last_changed_version: int = 1
    change_history: list[dict] = Field(default_factory=list)


class ClaimUpdate(BaseModel):
    claim_id: str
    to: str                         # confirmed | unconfirmed | disproved | misleading
    reason: str
    source_ids: list[str]


class EvidenceGap(BaseModel):
    question: str
    owner: str                      # ACME contact best placed to answer (from KB-02)


class CaseState(BaseModel):
    """Minimal slice that A1 reads from.  Full model lives in contracts.py."""
    case_id: str = "CASE-001"
    version: int = 1
    sources: list[Source] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    open_questions: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# --- A1 output model (§3 of spec) ------------------------------------------
# ---------------------------------------------------------------------------

class A1Output(BaseModel):
    new_sources: list[Source] = Field(default_factory=list)
    new_claims: list[Claim] = Field(default_factory=list)
    claim_updates: list[ClaimUpdate] = Field(default_factory=list)
    evidence_gaps: list[EvidenceGap] = Field(default_factory=list)
    trend_notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# --- Helpers ----------------------------------------------------------------
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_KB_DIR = Path(__file__).parent.parent.parent / "knowledge_base" / "ACME_company_files"


def _load_system_prompt() -> str:
    """Load the A1 system prompt from src/prompts/a1_evidence.md."""
    prompt_path = _PROMPTS_DIR / "a1_evidence.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    # Fallback: inline minimal prompt if file is missing
    return (
        "You are the Evidence Analyst in ACME's crisis-management system. "
        "Your only job is to maintain a reliable evidence ledger. "
        "You do not assess risk and you do not recommend actions."
    )


def _next_source_id(existing_sources: list[Source]) -> str:
    """Return the next U-xx ID after the highest existing user source."""
    nums = [
        int(s.source_id[2:])
        for s in existing_sources
        if re.match(r"^U-\d+$", s.source_id)
    ]
    return f"U-{(max(nums) + 1) if nums else 1:02d}"


def _next_claim_id(existing_claims: list[Claim]) -> str:
    """Return the next C-xxx ID after the highest existing claim."""
    nums = [
        int(c.claim_id[2:])
        for c in existing_claims
        if re.match(r"^C-\d+$", c.claim_id)
    ]
    return f"C-{(max(nums) + 1) if nums else 1:03d}"


def _build_attachment_blocks(attachments: list[str]) -> list[dict]:
    """
    Turn file paths into Anthropic content blocks (image or document).
    Only files that actually exist on disk are included.
    """
    blocks: list[dict] = []
    for path_str in attachments:
        p = Path(path_str)
        if not p.exists():
            continue
        suffix = p.suffix.lower()
        data = p.read_bytes()
        import base64
        b64 = base64.b64encode(data).decode()
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            media_map = {
                ".png": "image/png", ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg", ".gif": "image/gif",
                ".webp": "image/webp",
            }
            blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_map[suffix], "data": b64},
            })
        elif suffix == ".pdf":
            blocks.append({
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
            })
        # .txt / other text files: read as plain text in the user message
        elif suffix in {".txt", ".csv", ".md"}:
            blocks.append({
                "type": "text",
                "text": f"[Attachment: {p.name}]\n{p.read_text(encoding='utf-8', errors='replace')}",
            })
    return blocks


def _build_context_block(state: CaseState) -> str:
    """
    Serialise the existing sources and claims so the LLM can re-evaluate them.
    Keeps the JSON compact to save tokens.
    """
    return json.dumps(
        {
            "case_id": state.case_id,
            "version": state.version,
            "existing_sources": [s.model_dump() for s in state.sources],
            "existing_claims": [c.model_dump() for c in state.claims],
            "open_questions": state.open_questions,
        },
        indent=2,
    )


def _build_id_hints(state: CaseState) -> str:
    """Tell the LLM which IDs to continue from."""
    next_src = _next_source_id(state.sources)
    next_claim = _next_claim_id(state.claims)
    return (
        f"Next available source ID: {next_src}  "
        f"(continue sequentially: U-01, U-02, …)\n"
        f"Next available claim ID: {next_claim}  "
        f"(continue sequentially: C-001, C-002, …)\n"
        f"Current case version: {state.version}\n"
    )


# ---------------------------------------------------------------------------
# --- Main entry point -------------------------------------------------------
# ---------------------------------------------------------------------------

def run(state: CaseState, turn: TurnInput) -> A1Output:
    """
    Run the A1 Evidence Analyst for one turn.

    Parameters
    ----------
    state   Current CaseState (vN-1); A0 passes this in.
    turn    The new user input + attachments.

    Returns
    -------
    A1Output  Structured evidence delta.  A0 merges this into CaseState.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Copy .env.example to .env and add your key."
        )

    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = _load_system_prompt()
    context_block = _build_context_block(state)
    id_hints = _build_id_hints(state)

    # Build the user message: text + file attachments
    user_content: list[dict] = []

    # 1. ID hints (plain text)
    user_content.append({
        "type": "text",
        "text": f"=== ID allocation hints (do not change these) ===\n{id_hints}",
    })

    # 2. Existing case context
    user_content.append({
        "type": "text",
        "text": f"=== Current case context (vN-1) ===\n{context_block}",
    })

    # 3. New user input
    user_content.append({
        "type": "text",
        "text": f"=== New user input ===\n{turn.user_text}" if turn.user_text else "",
    })

    # 4. Attachments (images / PDFs / text files)
    attachment_blocks = _build_attachment_blocks(turn.attachments)
    user_content.extend(attachment_blocks)

    # 5. Output instruction
    user_content.append({
        "type": "text",
        "text": (
            "=== Task ===\n"
            "Analyse the new input above. Return a JSON object that strictly matches "
            "the schema below. Use only source IDs that already exist in the case context "
            "or the new IDs allocated above.\n\n"
            "Required JSON schema:\n"
            "{\n"
            '  "new_sources":   [ <Source objects> ],\n'
            '  "new_claims":    [ <Claim objects> ],\n'
            '  "claim_updates": [ { "claim_id": "C-xxx", "to": "...", "reason": "...", "source_ids": [...] } ],\n'
            '  "evidence_gaps": [ { "question": "...", "owner": "..." } ],\n'
            '  "trend_notes":   [ "..." ]\n'
            "}\n\n"
            "Rules:\n"
            "- Every claim must have at least one source_id.\n"
            "- A screenshot or repost alone → status unconfirmed, evidence_strength weak.\n"
            "- Historical KB cases (KB-06..KB-09) are category historical_case; never cite them "
            "as evidence about the current incident.\n"
            "- Do not invent facts, figures, names, dates, or source IDs.\n"
            "- Respond with valid JSON only. No markdown fences, no commentary outside the JSON."
        ),
    })

    # Remove empty text blocks
    user_content = [b for b in user_content if b.get("text", "x").strip()]

    response = client.messages.create(
        model="claude-opus-4-5",          # PROJECT.md §9 default
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = response.content[0].text.strip()

    # Strip accidental markdown code fences if the model adds them
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

    data = json.loads(raw)
    return A1Output.model_validate(data)
