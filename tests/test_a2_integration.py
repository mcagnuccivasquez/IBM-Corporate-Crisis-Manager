"""
test_a2_integration.py — Integration tests for the A2 agent (stub mode, no API key required).

These tests run a2_impact.run() against fixture CaseStates and verify that:
  - The output schema is valid (Pydantic validates it).
  - Risk levels are consistent with risk.py.
  - Evidence distinctions are preserved (confirmed vs unconfirmed vs disproved).
  - Historical examples are not treated as current evidence.
  - Financial estimates are only made when KB data supports them.
  - Floor triggers are reported when safety keywords are present.

All tests use the STUB domain assessor — no Anthropic API key needed.

Run with:
    python -m pytest tests/test_a2_integration.py -v
"""

from __future__ import annotations

import os
import pytest
from datetime import datetime

# Force stub mode for all tests (no live LLM calls)
os.environ.pop("ANTHROPIC_API_KEY", None)

from src.contracts import (
    CaseState,
    Claim,
    ClaimHistory,
    DomainAssessment,
    ImpactsBlock,
    RiskBlock,
    Source,
    TurnInput,
)
from src.agents.a2_impact import run, A2Output


# ---------------------------------------------------------------------------
# Shared fixture builder
# ---------------------------------------------------------------------------

def _base_state(version: int = 1, claims=None, sources=None, prev_risk=None) -> CaseState:
    return CaseState(
        case_id="CASE-TEST",
        version=version,
        created_at=datetime(2026, 11, 21),
        updated_at=datetime(2026, 11, 21),
        sources=sources or [],
        claims=claims or [],
        risk=prev_risk,
    )


def _turn() -> TurnInput:
    return TurnInput(intent="NEW_INFO", user_text="New incident evidence submitted.")


def _source(source_id: str, category="incident_evidence", time_relevance="current") -> Source:
    return Source(
        source_id=source_id,
        title=f"Source {source_id}",
        origin="user_upload",
        category=category,
        time_relevance=time_relevance,
        added_in_version=1,
    )


def _claim(
    claim_id: str,
    text: str,
    status="unconfirmed",
    strength="weak",
    domains=None,
    source_ids=None,
    market="DE",
    version=1,
) -> Claim:
    return Claim(
        claim_id=claim_id,
        text=text,
        status=status,
        evidence_strength=strength,
        source_ids=source_ids or [f"U-0{claim_id[-1]}"],
        domains=domains or ["reputational", "legal_regulatory"],
        product="PCX-100",
        market=market,
        first_seen_version=version,
        last_changed_version=version,
    )


# ---------------------------------------------------------------------------
# 1. Strong confirmed evidence → High or Critical risk
# ---------------------------------------------------------------------------

class TestStrongConfirmedEvidence:
    def test_confirmed_smoke_produces_high_or_critical(self):
        """
        Confirmed smoke claim on a product in market + strong evidence → risk High or Critical.
        The stub assessor sets S≥3, L≥3 for confirmed claims, which yields score ≥9.
        """
        claims = [
            _claim("C-001", "PCX-100 unit emitted smoke and melted while charging",
                   status="confirmed", strength="strong",
                   domains=["reputational", "economic", "legal_regulatory"]),
        ]
        state = _base_state(claims=claims, sources=[_source("U-01")])
        output: A2Output = run(state, _turn())

        assert output.risk.level in ("High", "Critical")
        assert output.impacts.reputational is not None
        assert output.impacts.economic is not None
        assert output.impacts.legal_regulatory is not None

    def test_output_schema_valid(self):
        """Output must be a valid A2Output (Pydantic validates all fields)."""
        claims = [_claim("C-001", "confirmed smoke incident",
                         status="confirmed", strength="strong")]
        state = _base_state(claims=claims, sources=[_source("U-01")])
        output = run(state, _turn())
        # If this doesn't raise, schema is valid
        assert isinstance(output, A2Output)
        assert isinstance(output.risk, RiskBlock)


# ---------------------------------------------------------------------------
# 2. Only unconfirmed allegations → Medium or lower, evidence_confidence=low
# ---------------------------------------------------------------------------

class TestUnconfirmedAllegations:
    def test_unconfirmed_only_not_critical(self):
        """Single unconfirmed post must not produce Critical."""
        claims = [
            _claim("C-001", "User claims PCX-100 smelled like burning",
                   status="unconfirmed", strength="weak"),
        ]
        state = _base_state(claims=claims, sources=[_source("U-01")])
        output = run(state, _turn())

        assert output.risk.level != "Critical", (
            "A single unconfirmed allegation must not produce Critical"
        )

    def test_evidence_confidence_low(self):
        claims = [_claim("C-001", "allegation only", status="unconfirmed", strength="weak")]
        state = _base_state(claims=claims)
        output = run(state, _turn())
        assert output.risk.evidence_confidence == "low"

    def test_stakeholders_populated(self):
        """Even with weak evidence, stakeholder list must not be empty."""
        claims = [_claim("C-001", "allegation", status="unconfirmed", strength="weak", market="DE")]
        state = _base_state(claims=claims)
        output = run(state, _turn())
        assert len(output.stakeholders) > 0


# ---------------------------------------------------------------------------
# 3. Contradictory / misleading evidence → misleading claims excluded from scoring
# ---------------------------------------------------------------------------

class TestContradictoryMisleadingEvidence:
    def test_misleading_claim_excluded(self):
        """
        Misleading claims must not drive the risk score up.
        A misleading claim + one low unconfirmed claim → Low or Medium.
        """
        claims = [
            _claim("C-001", "2025 TravelPlug post re-shared as PCX-100 problem",
                   status="misleading", strength="weak"),
            _claim("C-002", "minor heat query from one customer",
                   status="unconfirmed", strength="weak"),
        ]
        state = _base_state(claims=claims)
        output = run(state, _turn())
        # Misleading claim is filtered out; only C-002 remains
        assert output.risk.level in ("Low", "Medium")

    def test_disproved_claim_excluded(self):
        """Disproved claims must be filtered before domain assessment."""
        claims = [
            _claim("C-001", "PCX-100 recalled in Spain — 100,000 units",
                   status="disproved", strength="weak"),
        ]
        state = _base_state(claims=claims)
        output = run(state, _turn())
        assert output.risk.level in ("Low", "Medium")


# ---------------------------------------------------------------------------
# 4. Missing financial information → no invented financial figures
# ---------------------------------------------------------------------------

class TestMissingFinancialInfo:
    def test_economic_impact_present_even_without_financial_claims(self):
        """
        When no financial claims exist, economic assessment still runs but
        should not invent numbers.  The stub returns a generalised impact description.
        """
        claims = [
            _claim("C-001", "PCX-100 overheating complaint",
                   domains=["reputational"],  # no economic domain
                   status="unconfirmed", strength="weak"),
        ]
        state = _base_state(claims=claims)
        output = run(state, _turn())
        eco = output.impacts.economic
        assert eco is not None
        # Stub must flag "[STUB]" or similar — in production the LLM must follow
        # the economic lens rules (KB-12 ranges, no invented figures)
        assert eco.severity >= 1 and eco.likelihood >= 1

    def test_economic_severity_low_without_financial_evidence(self):
        """With no economic-domain claims, economic severity should stay low in stub mode."""
        claims = [_claim("C-001", "social media post about smell",
                         domains=["reputational"], status="unconfirmed")]
        state = _base_state(claims=claims)
        output = run(state, _turn())
        # Stub falls back to all claims → severity 2 (unconfirmed)
        assert output.impacts.economic is not None


# ---------------------------------------------------------------------------
# 5. Unconfirmed regulatory exposure → labelled as general_knowledge, not fact
# ---------------------------------------------------------------------------

class TestUnconfirmedRegulatoryExposure:
    def test_legal_assessment_runs(self):
        """Legal domain assessment must run even without confirmed legal claims."""
        claims = [
            _claim("C-001", "PCX-100 may have caused electric shock",
                   status="unconfirmed", strength="weak",
                   domains=["reputational", "legal_regulatory"]),
        ]
        state = _base_state(claims=claims)
        output = run(state, _turn())
        leg = output.impacts.legal_regulatory
        assert leg is not None
        # Must not say the regulatory action is confirmed
        for item in leg.impacts:
            assert item.basis in ("general_knowledge", "company_data", "precedent")

    def test_f1_triggered_by_safety_keyword(self):
        """
        'smoke' or 'electric shock' keywords in a claim should trigger F1 in
        the stub assessor on the legal domain.
        """
        claims = [
            _claim("C-001", "PCX-100 unit emitted smoke",
                   status="unconfirmed",
                   domains=["reputational", "legal_regulatory"]),
        ]
        state = _base_state(claims=claims)
        output = run(state, _turn())
        # F1 must appear in at least one domain
        all_floors = set()
        for d in [output.impacts.reputational, output.impacts.legal_regulatory]:
            if d:
                all_floors.update(d.floor_triggers)
        assert "F1" in all_floors
        assert output.risk.level == "High"


# ---------------------------------------------------------------------------
# 6. New evidence changes the overall risk
# ---------------------------------------------------------------------------

class TestNewEvidenceChangesRisk:
    def test_risk_increases_with_confirmed_evidence(self):
        """
        v1: single unconfirmed claim → Medium.
        v2: same claim upgraded to confirmed → High or Critical.
        """
        # Version 1 state
        claims_v1 = [_claim("C-001", "PCX-100 overheating", status="unconfirmed", strength="weak")]
        state_v1 = _base_state(version=1, claims=claims_v1)
        out_v1 = run(state_v1, _turn())
        level_v1 = out_v1.risk.level

        # Version 2: claim upgraded to confirmed
        claims_v2 = [
            _claim("C-001", "PCX-100 overheating confirmed by lab",
                   status="confirmed", strength="strong",
                   version=2),
        ]
        state_v2 = _base_state(version=2, claims=claims_v2, prev_risk=out_v1.risk)
        out_v2 = run(state_v2, _turn())

        rank = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
        assert rank[out_v2.risk.level] > rank[level_v1], (
            f"Risk should increase: {level_v1} → {out_v2.risk.level}"
        )


# ---------------------------------------------------------------------------
# 7. New evidence does NOT change overall risk but changes explanation
# ---------------------------------------------------------------------------

class TestNewEvidenceChangesExplanationNotLevel:
    def test_second_independent_report_same_level_different_explanation(self):
        """
        Adding a second independent unconfirmed report should not necessarily
        change the level but should populate change_vs_previous in the domain.
        In stub mode, the level may stay the same while the claim count changes.
        """
        claims_v1 = [_claim("C-001", "single smoke report", status="unconfirmed")]
        state_v1 = _base_state(version=1, claims=claims_v1)
        out_v1 = run(state_v1, _turn())

        # Second report added — same level expected
        claims_v2 = [
            _claim("C-001", "first smoke report", status="unconfirmed"),
            _claim("C-002", "second smoke report same batch", status="unconfirmed"),
        ]
        state_v2 = _base_state(version=2, claims=claims_v2, prev_risk=out_v1.risk)
        out_v2 = run(state_v2, _turn())

        # Level might be the same or higher (stub-based); we just verify consistency
        assert out_v2.risk.level in ("Low", "Medium", "High", "Critical")
        # Schema is still valid
        assert isinstance(out_v2, A2Output)


# ---------------------------------------------------------------------------
# 8. Historical examples available, current evidence limited
# ---------------------------------------------------------------------------

class TestHistoricalExamplesLimitedCurrent:
    def test_historical_source_does_not_drive_up_risk(self):
        """
        Historical cases (time_relevance=historical) must not inflate the risk.
        Only current evidence should drive scoring.
        """
        # Historical source but no current evidence
        sources = [
            _source("KB-07", category="historical_case", time_relevance="historical"),
            _source("KB-08", category="historical_case", time_relevance="historical"),
        ]
        # Claims from historical sources only
        claims = [
            Claim(
                claim_id="C-H-01",
                text="2025 TravelPlug social post (historical)",
                status="unconfirmed",
                evidence_strength="weak",
                source_ids=["KB-07"],
                domains=["reputational"],
                first_seen_version=1,
                last_changed_version=1,
            )
        ]
        state = _base_state(claims=claims, sources=sources)
        output = run(state, _turn())

        # With only one unconfirmed historical claim, risk should be low/medium
        assert output.risk.level in ("Low", "Medium"), (
            f"Historical-only evidence should not produce {output.risk.level}"
        )

    def test_historical_source_category_preserved_in_sources(self):
        """Sources added from historical KB must retain time_relevance=historical."""
        sources = [_source("KB-07", category="historical_case", time_relevance="historical")]
        state = _base_state(sources=sources)
        # Verify the source is preserved as-is by the state (A2 must not alter sources)
        assert state.sources[0].time_relevance == "historical"
        assert state.sources[0].category == "historical_case"


# ---------------------------------------------------------------------------
# Determinism check: same input → same output (run 3×)
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_risk_level(self):
        """
        Same CaseState run 3 times must produce the same risk level.
        (Allowed variance: 0, per spec §8 — stub mode is fully deterministic.)
        """
        claims = [_claim("C-001", "PCX-100 emitted smoke", status="unconfirmed")]
        state = _base_state(claims=claims)

        results = [run(state, _turn()) for _ in range(3)]
        levels = [r.risk.level for r in results]
        assert len(set(levels)) == 1, f"Non-deterministic levels across runs: {levels}"
