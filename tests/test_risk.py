"""
test_risk.py — Unit tests for src/risk.py

Covers (per A2 spec §8 acceptance tests):
  - Every S×L → level boundary (1–3=Low, 4–6=Med, 8–9=High, 12–16=Critical)
  - Each floor trigger (F1, F2, F3) in isolation and in combination
  - F4 de-escalation guard: blocked (no disprove/no verified), allowed (claim disproved),
    allowed (action verified_effective)
  - Level unchanged when only explanations change
  - Reasons text is always present
  - Evidence confidence reflects the weakest driving domain

Run with:
    python -m pytest tests/test_risk.py -v
"""

import pytest
from src.contracts import DomainAssessment, ImpactItem
from src.risk import ActionChange, ClaimChange, compute_risk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_domain(
    domain="reputational",
    severity=1,
    likelihood=1,
    floor_triggers=None,
    evidence_confidence="low",
) -> DomainAssessment:
    return DomainAssessment(
        domain=domain,
        severity=severity,
        severity_reason=f"Test S{severity}",
        likelihood=likelihood,
        likelihood_reason=f"Test L{likelihood}",
        score=severity * likelihood,
        impacts=[ImpactItem(
            description="test impact",
            if_unaddressed="test unaddressed",
            timeframe="7d",
            stakeholders=["test"],
            source_ids=["KB-01"],
            basis="general_knowledge",
        )],
        floor_triggers=floor_triggers or [],
        evidence_confidence=evidence_confidence,
    )


# ---------------------------------------------------------------------------
# Step 2: S×L → level mapping
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("severity,likelihood,expected_level", [
    # Low band (score 1–3)
    (1, 1, "Low"),    # score 1
    (1, 2, "Low"),    # score 2
    (1, 3, "Low"),    # score 3
    (3, 1, "Low"),    # score 3
    # Medium band (score 4–6)
    (2, 2, "Medium"), # score 4
    (2, 3, "Medium"), # score 6
    (3, 2, "Medium"), # score 6
    (1, 4, "Medium"), # score 4
    (4, 1, "Medium"), # score 4
    # High band (score 8–9)
    (2, 4, "High"),   # score 8
    (4, 2, "High"),   # score 8
    (3, 3, "High"),   # score 9
    # Critical band (score 12–16)
    (3, 4, "Critical"),  # score 12
    (4, 3, "Critical"),  # score 12
    (4, 4, "Critical"),  # score 16
])
def test_score_to_level(severity, likelihood, expected_level):
    domain = make_domain(severity=severity, likelihood=likelihood)
    result = compute_risk([domain])
    assert result.level == expected_level, (
        f"S{severity}×L{likelihood}={severity*likelihood} expected {expected_level}, "
        f"got {result.level}"
    )


# ---------------------------------------------------------------------------
# Step 3: Floor triggers
# ---------------------------------------------------------------------------

class TestF1Floor:
    def test_f1_raises_low_to_high(self):
        """F1 must raise a Low score to at least High."""
        domain = make_domain(severity=1, likelihood=2, floor_triggers=["F1"])  # score 2 → Low
        result = compute_risk([domain])
        assert result.level == "High"
        assert "F1" in result.floors_applied

    def test_f1_does_not_lower_critical(self):
        """F1 must not lower a Critical score."""
        domain = make_domain(severity=4, likelihood=4, floor_triggers=["F1"])
        result = compute_risk([domain])
        assert result.level == "Critical"
        assert "F1" in result.floors_applied

    def test_f1_does_not_affect_already_high(self):
        """F1 on a High score keeps it High."""
        domain = make_domain(severity=3, likelihood=3, floor_triggers=["F1"])  # score 9 → High
        result = compute_risk([domain])
        assert result.level == "High"

    def test_f1_reason_present(self):
        domain = make_domain(severity=1, likelihood=1, floor_triggers=["F1"])
        result = compute_risk([domain])
        assert any("F1" in r for r in result.reasons)


class TestF2Floor:
    def test_f2_raises_to_critical(self):
        """F2 must always produce Critical."""
        domain = make_domain(severity=1, likelihood=1, floor_triggers=["F2"])
        result = compute_risk([domain])
        assert result.level == "Critical"
        assert "F2" in result.floors_applied

    def test_f2_overrides_f1(self):
        """When F2 is present, F1 reasoning should not appear (F2 is stronger)."""
        domain = make_domain(severity=1, likelihood=1, floor_triggers=["F1", "F2"])
        result = compute_risk([domain])
        assert result.level == "Critical"
        assert "F2" in result.floors_applied
        # F1 is superseded by F2; check F2 reason present
        assert any("F2" in r for r in result.reasons)


class TestF3Floor:
    def test_f3_raises_low_to_high(self):
        """F3 must raise a Low score to at least High."""
        domain = make_domain(domain="legal_regulatory", severity=1, likelihood=2, floor_triggers=["F3"])
        result = compute_risk([domain])
        assert result.level == "High"
        assert "F3" in result.floors_applied

    def test_f3_does_not_lower_critical(self):
        domain = make_domain(severity=4, likelihood=4, floor_triggers=["F3"])
        result = compute_risk([domain])
        assert result.level == "Critical"


class TestF1F3Combination:
    def test_f1_and_f3_both_applied(self):
        """Both F1 and F3 can appear together; level = at least High."""
        d_rep = make_domain(domain="reputational", severity=2, likelihood=2, floor_triggers=["F1"])
        d_leg = make_domain(domain="legal_regulatory", severity=1, likelihood=1, floor_triggers=["F3"])
        result = compute_risk([d_rep, d_leg])
        assert result.level == "High"
        assert "F1" in result.floors_applied
        assert "F3" in result.floors_applied


# ---------------------------------------------------------------------------
# Step 4: F4 de-escalation guard
# ---------------------------------------------------------------------------

class TestF4Guard:
    def test_f4_blocks_drop_when_no_disprove_no_verified(self):
        """Level must not drop if no claim was disproved and no action verified_effective."""
        domain = make_domain(severity=1, likelihood=2)  # score 2 → Low
        result = compute_risk(
            [domain],
            prev_level="High",
            claim_changes=[],
            action_changes=[],
        )
        assert result.level == "High", "F4 should block de-escalation"
        assert any("F4" in r for r in result.reasons)

    def test_f4_allows_drop_when_claim_disproved(self):
        """Level may drop if a claim was disproved in this turn."""
        domain = make_domain(severity=1, likelihood=1)  # score 1 → Low
        changes = [ClaimChange(claim_id="C-001", from_status="unconfirmed", to_status="disproved")]
        result = compute_risk(
            [domain],
            prev_level="High",
            claim_changes=changes,
            action_changes=[],
        )
        assert result.level == "Low"
        assert not any("F4" in r for r in result.reasons)

    def test_f4_allows_drop_when_action_verified_effective(self):
        """Level may drop if an action reached verified_effective."""
        domain = make_domain(severity=1, likelihood=1)
        action_changes = [ActionChange(action_id="ACT-001", from_status="completed", to_status="verified_effective")]
        result = compute_risk(
            [domain],
            prev_level="High",
            claim_changes=[],
            action_changes=action_changes,
        )
        assert result.level == "Low"

    def test_f4_allows_drop_when_claim_misleading(self):
        """Downgrading to 'misleading' also justifies de-escalation."""
        domain = make_domain(severity=1, likelihood=1)
        changes = [ClaimChange(claim_id="C-002", from_status="unconfirmed", to_status="misleading")]
        result = compute_risk(
            [domain],
            prev_level="Medium",
            claim_changes=changes,
        )
        assert result.level == "Low"

    def test_f4_no_effect_when_level_increases(self):
        """F4 guard only applies to drops; increases are always allowed."""
        domain = make_domain(severity=4, likelihood=4)  # Critical
        result = compute_risk(
            [domain],
            prev_level="Low",
            claim_changes=[],
            action_changes=[],
        )
        assert result.level == "Critical"


# ---------------------------------------------------------------------------
# Reasons always present
# ---------------------------------------------------------------------------

def test_reasons_always_present():
    domain = make_domain(severity=2, likelihood=3)
    result = compute_risk([domain])
    assert len(result.reasons) > 0
    assert all(isinstance(r, str) and len(r) > 0 for r in result.reasons)


def test_reasons_present_with_floors():
    domain = make_domain(severity=1, likelihood=1, floor_triggers=["F1"])
    result = compute_risk([domain])
    assert len(result.reasons) >= 2  # at least one domain reason + floor reason


# ---------------------------------------------------------------------------
# Evidence confidence
# ---------------------------------------------------------------------------

def test_evidence_confidence_weakest_driving_domain():
    """The evidence_confidence of the result must be the weakest among driving domains."""
    d1 = make_domain(domain="reputational", severity=3, likelihood=3, evidence_confidence="high")    # score 9
    d2 = make_domain(domain="economic", severity=3, likelihood=3, evidence_confidence="low")         # score 9
    result = compute_risk([d1, d2])
    assert result.level == "High"
    assert result.evidence_confidence == "low"


def test_evidence_confidence_single_domain():
    domain = make_domain(severity=2, likelihood=2, evidence_confidence="moderate")
    result = compute_risk([domain])
    assert result.evidence_confidence == "moderate"


# ---------------------------------------------------------------------------
# No domains edge case
# ---------------------------------------------------------------------------

def test_empty_domains():
    result = compute_risk([])
    assert result.level == "Low"
    assert len(result.reasons) > 0


# ---------------------------------------------------------------------------
# Max domain score is correct
# ---------------------------------------------------------------------------

def test_max_domain_score():
    d1 = make_domain(domain="reputational", severity=3, likelihood=2)   # score 6
    d2 = make_domain(domain="economic",     severity=2, likelihood=4)   # score 8
    d3 = make_domain(domain="legal_regulatory", severity=1, likelihood=1)  # score 1
    result = compute_risk([d1, d2, d3])
    assert result.max_domain_score == 8
    assert result.level == "High"


# ---------------------------------------------------------------------------
# S1 turn 1 acceptance test (from A2 spec §8)
# Single unconfirmed smoke post: rep ≈ S3×L2, legal flags F1 → risk.py → High
# ---------------------------------------------------------------------------

def test_s1_turn1_acceptance():
    """
    Spec §8 acceptance test S1 turn 1:
    reputational S3×L2=6 (Medium), legal flags F1 → overall High with F1 floor reason.
    """
    rep = make_domain(domain="reputational", severity=3, likelihood=2, evidence_confidence="low")
    eco = make_domain(domain="economic",     severity=2, likelihood=1, evidence_confidence="low")
    leg = make_domain(domain="legal_regulatory", severity=3, likelihood=2,
                      floor_triggers=["F1"], evidence_confidence="low")

    result = compute_risk([rep, eco, leg])

    assert result.level == "High", f"Expected High, got {result.level}"
    assert "F1" in result.floors_applied
    assert any("F1" in r for r in result.reasons)
    assert result.evidence_confidence == "low"
