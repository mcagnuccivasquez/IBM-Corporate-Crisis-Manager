"""
risk.py — Deterministic risk engine for the ACME Corporate Crisis Manager.

Owner: A2 (Junda). Pure Python — no LLM, no external dependencies beyond Pydantic.
Called by: A0 pipeline (after A2a/b/c return domain scores), A4 (for residual risk projection).

Implements PROJECT.md §6 exactly:
  Step 1  domain score = Severity × Likelihood (each 1–4)
  Step 2  level from max_domain_score: 1–3→Low, 4–6→Medium, 8–9→High, 12–16→Critical
          (score 7 is not achievable with integer S×L; mapped to High to be conservative)
  Step 3  floor overrides (applied after Step 2):
            F1  credible fire/smoke/shock/injury report → at least High
            F2  confirmed injury, confirmed hazard in market, or authority contact → Critical
            F3  confirmed/likely unauthorised access to personal data/recordings → at least High
  Step 4  F4 de-escalation guard: level may only drop vs previous_level if a claim was
            disproved/downgraded OR an action reached verified_effective. "No news" ≠ de-escalation.

Scoring rationale (PROJECT §6):
  - S×L gives a natural 1–16 scale; the four level bands match the brief's Low/Med/High/Critical.
  - Floors capture mandatory escalation rules from ACME policy (KB-02) and EU product-safety/GDPR
    obligations regardless of the mathematical score.
  - F4 prevents the system from silently de-escalating just because nothing new arrived.
  - Evidence strength is NEVER an input to this function; it is reported alongside the level.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.contracts import (
    CaseState,
    Confidence,
    DomainImpact,
    FloorId,
    Risk,
    RiskLevel,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Mapping from raw score to level (Step 2).
# Score 7 is mathematically unreachable (S×L with integers 1–4 skips 7).
# Included for safety; mapped to High.
def _score_to_level(score: int) -> RiskLevel:
    if score <= 3:
        return "Low"
    if score <= 6:
        return "Medium"
    if score <= 9:    # covers 8, 9 (and unreachable 7)
        return "High"
    return "Critical"  # 12–16


def _level_rank(level: RiskLevel) -> int:
    """Numeric rank so we can compare levels (Low=1 … Critical=4)."""
    return {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}[level]


def _rank_to_level(rank: int) -> RiskLevel:
    return {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}[rank]


def _lowest_confidence(assessments: list[DomainImpact]) -> Confidence:
    """Return the weakest evidence_confidence across the driving assessments."""
    order = {"low": 0, "medium": 1, "high": 2}
    if not assessments:
        return "low"
    return min(assessments, key=lambda a: order[a.evidence_confidence]).evidence_confidence


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class ClaimChange:
    """A claim status change from A1 — used by the F4 de-escalation guard."""
    claim_id: str
    from_status: Optional[str]   # None if newly added
    to_status: str


@dataclass
class ActionChange:
    """An action status change from A3 — used by the F4 de-escalation guard."""
    action_id: str
    from_status: Optional[str]
    to_status: str


def _derive_claim_changes(state: CaseState, prev: Optional[CaseState]) -> list[ClaimChange]:
    """Derive claim status changes by comparing state vs prev claim statuses.
    Used when the pipeline calls compute_risk(state, prev) without explicit changes.
    """
    if prev is None:
        return []
    prev_by_id = {c.claim_id: c for c in prev.claims}
    changes: list[ClaimChange] = []
    for c in state.claims:
        old = prev_by_id.get(c.claim_id)
        old_status = old.status if old else None
        if old_status != c.status:
            changes.append(ClaimChange(claim_id=c.claim_id, from_status=old_status, to_status=c.status))
    return changes


def _derive_action_changes(state: CaseState, prev: Optional[CaseState]) -> list[ActionChange]:
    """Derive action status changes by comparing state vs prev action statuses."""
    if prev is None:
        return []
    prev_by_id = {a.action_id: a for a in prev.actions}
    changes: list[ActionChange] = []
    for a in state.actions:
        old = prev_by_id.get(a.action_id)
        old_status = old.status if old else None
        if old_status != a.status:
            changes.append(ActionChange(action_id=a.action_id, from_status=old_status, to_status=a.status))
    return changes


def compute_risk(
    state: CaseState,
    prev: Optional[CaseState] = None,
    claim_changes: Optional[list[ClaimChange]] = None,
    action_changes: Optional[list[ActionChange]] = None,
) -> Risk:
    """
    Compute the overall risk level from the domain impacts stored in state.impacts.

    Parameters
    ----------
    state:          Current CaseState (after A2a/b/c have written their DomainImpact results).
    prev:           Previous CaseState version, or None for v1.
    claim_changes:  Claim status changes this turn. If None, derived automatically from
                    state vs prev by comparing claim/action statuses (used by the pipeline
                    which calls compute_risk(state, prev) without explicit change lists).
    action_changes: Action status changes this turn. Same auto-derivation if None.

    Returns
    -------
    Risk — written directly into CaseState.risk by A0. Never written by an LLM.
    """
    # Auto-derive changes from state vs prev when not supplied explicitly.
    if claim_changes is None:
        claim_changes = _derive_claim_changes(state, prev)
    if action_changes is None:
        action_changes = _derive_action_changes(state, prev)

    prev_level = prev.risk.level if (prev and prev.risk) else None

    domains: list[DomainImpact] = [
        d for d in (
            state.impacts.reputational,
            state.impacts.economic,
            state.impacts.legal_regulatory,
        )
        if d is not None
    ]

    if not domains:
        # Edge case: called before any domain assessment is available.
        return Risk(
            level="Low",
            previous_level=prev_level,
            max_domain_score=0,
            floors_applied=[],
            reasons=["No domain assessments available; defaulting to Low pending assessment."],
            evidence_confidence="low",
        )

    # ------------------------------------------------------------------
    # Step 1 — domain scores (Severity × Likelihood)
    # ------------------------------------------------------------------
    # DomainImpact.score is auto-set by its validator, but defensively recompute.
    for d in domains:
        d.score = d.severity * d.likelihood

    max_score = max(d.score for d in domains)
    driving = [d for d in domains if d.score == max_score]

    # ------------------------------------------------------------------
    # Step 2 — baseline level from max score
    # ------------------------------------------------------------------
    level_rank = _level_rank(_score_to_level(max_score))
    reasons: list[str] = []

    domain_names = {
        id(state.impacts.reputational): "reputational",
        id(state.impacts.economic): "economic",
        id(state.impacts.legal_regulatory): "legal_regulatory",
    }
    for d in domains:
        name = domain_names.get(id(d), "unknown")
        reasons.append(
            f"{name.capitalize()}: {d.severity}×{d.likelihood}={d.score} → {_score_to_level(d.score)}"
        )

    # ------------------------------------------------------------------
    # Step 3 — floor overrides
    # ------------------------------------------------------------------
    floors_applied: list[FloorId] = []

    # Collect all floor_triggers across all domains
    all_triggers: set[FloorId] = set()
    for d in domains:
        all_triggers.update(d.floor_triggers)

    if "F2" in all_triggers:
        floors_applied.append("F2")
        if level_rank < 4:
            level_rank = 4
            reasons.append(
                "F2 floor applied: confirmed injury, confirmed hazardous defect in market, "
                "or authority contact → Critical (PROJECT §6)."
            )

    if "F1" in all_triggers and "F2" not in all_triggers:
        floors_applied.append("F1")
        if level_rank < 3:
            level_rank = 3
            reasons.append(
                "F1 floor applied: credible fire/smoke/shock/injury report on product in market "
                "→ at least High (KB-02: 'do not wait for complete diagnosis before flagging a "
                "possible safety issue', PROJECT §6)."
            )

    if "F3" in all_triggers and "F2" not in all_triggers:
        # F3 is independent of F1; both can apply.
        if "F3" not in floors_applied:
            floors_applied.append("F3")
        if level_rank < 3:
            level_rank = 3
            reasons.append(
                "F3 floor applied: confirmed or likely unauthorised access to customer personal "
                "data or recordings → at least High (PROJECT §6)."
            )

    # ------------------------------------------------------------------
    # Step 4 — F4 de-escalation guard
    # ------------------------------------------------------------------
    if prev_level is not None:
        prev_rank = _level_rank(prev_level)
        if level_rank < prev_rank:
            # Check whether de-escalation is earned.
            disproved_or_downgraded = any(
                c.to_status in ("disproved", "misleading")
                or (
                    c.from_status == "confirmed"
                    and c.to_status in ("unconfirmed",)
                )
                for c in claim_changes
            )
            verified_effective = any(
                a.to_status == "verified_effective"
                for a in action_changes
            )

            if not disproved_or_downgraded and not verified_effective:
                # Block the drop — keep the previous level.
                reasons.append(
                    f"F4 de-escalation guard: level would drop {prev_level}→"
                    f"{_rank_to_level(level_rank)} but no claim was disproved/downgraded and no "
                    "action reached verified_effective in this turn. Level held at "
                    f"{prev_level} (PROJECT §6 F4)."
                )
                level_rank = prev_rank

    computed_level: RiskLevel = _rank_to_level(level_rank)

    # ------------------------------------------------------------------
    # Evidence confidence — lowest of the domains driving the level
    # ------------------------------------------------------------------
    evidence_confidence = _lowest_confidence(driving)

    return Risk(
        level=computed_level,
        previous_level=prev_level,
        max_domain_score=max_score,
        floors_applied=floors_applied,
        reasons=reasons,
        evidence_confidence=evidence_confidence,
    )
