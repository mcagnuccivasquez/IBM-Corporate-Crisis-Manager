"""Version diff (A0): compare v(N-1) and vN and build the changelog entry in code.

A5 adds the narrative "why" (ChangelogEntry.summary).
"""

from __future__ import annotations

from src.contracts import CaseState, ChangelogEntry


def build_changelog_entry(prev: CaseState | None, curr: CaseState) -> ChangelogEntry:
    prev_sources = {s.source_id for s in prev.sources} if prev else set()
    prev_claims = {c.claim_id: c for c in prev.claims} if prev else {}
    prev_actions = {a.action_id: a for a in prev.actions} if prev else {}

    claim_changes = []
    for c in curr.claims:
        old = prev_claims.get(c.claim_id)
        if old is None:
            claim_changes.append(f"{c.claim_id} new ({c.status})")
        elif old.status != c.status:
            claim_changes.append(f"{c.claim_id} {old.status} → {c.status}")
        elif old.evidence_strength != c.evidence_strength:
            claim_changes.append(f"{c.claim_id} evidence {old.evidence_strength} → {c.evidence_strength}")

    action_changes = []
    for a in curr.actions:
        old = prev_actions.get(a.action_id)
        if old is None:
            action_changes.append(f"{a.action_id} {a.status}")
        elif old.status != a.status:
            action_changes.append(f"{a.action_id} {old.status} → {a.status}")

    return ChangelogEntry(
        version=curr.version,
        risk_from=prev.risk.level if prev and prev.risk else None,
        risk_to=curr.risk.level if curr.risk else None,
        new_source_ids=[s.source_id for s in curr.sources if s.source_id not in prev_sources],
        claim_changes=claim_changes,
        action_changes=action_changes,
    )
