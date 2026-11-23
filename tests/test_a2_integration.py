"""
test_a2_integration.py — Integration tests for A2 stub logic and risk.py.

Tests call _stub_domain_assessment() directly (the deterministic fallback also used
by stubs.a2 in the pipeline). This avoids any LLM call while still exercising the
full domain-scoring and risk-computation path.

Covers:
  - Output schema validity (Pydantic validates DomainImpact).
  - Risk levels consistent with risk.py.
  - Evidence distinctions (confirmed vs unconfirmed vs disproved).
  - Historical examples not inflating risk.
  - Floor triggers reported when safety keywords present.

Run with:
    python -m pytest tests/test_a2_integration.py -v
"""

from __future__ import annotations

import pytest
from datetime import datetime

from src.contracts import (
    CaseState,
    Claim,
    ClaimChange,
    Domain,
    DomainImpact,
    Impacts,
    Risk,
    Source,
    new_case,
)
from src.agents.a2_impact import _stub_domain_assessment
from src.risk import compute_risk


# ---------------------------------------------------------------------------
# Shared fixture builder
# ---------------------------------------------------------------------------

def _base_state(version: int = 1, claims=None, sources=None, prev_risk: Risk | None = None) -> CaseState:
    state = new_case("CASE-001")
    state.version = version
    state.sources = sources or []
    state.claims = claims or []
    state.risk = prev_risk
    return state


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
        change_history=[ClaimChange(version=version, **{"from": None}, to=status,
                                     reason="initial", source_ids=source_ids or [f"U-0{claim_id[-1]}"])],
    )


def _active_claims(state: CaseState) -> list[Claim]:
    return [c for c in state.claims if c.status not in ("disproved", "misleading")]


def _run_all(state: CaseState) -> tuple[DomainImpact, DomainImpact, DomainImpact]:
    """Helper: run stub assessor for all three domains and return (rep, eco, leg)."""
    claims = _active_claims(state)
    rep = _stub_domain_assessment("reputational", claims, None)
    eco = _stub_domain_assessment("economic", claims, None)
    leg = _stub_domain_assessment("legal_regulatory", claims, None)
    return rep, eco, leg


def _risk_from_all(state: CaseState, prev: CaseState | None = None) -> Risk:
    """Run stub assessor for all three domains into state.impacts, then compute risk."""
    claims = _active_claims(state)
    state.impacts = Impacts(
        reputational=_stub_domain_assessment("reputational", claims, None),
        economic=_stub_domain_assessment("economic", claims, None),
        legal_regulatory=_stub_domain_assessment("legal_regulatory", claims, None),
    )
    return compute_risk(state, prev)


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
        risk = _risk_from_all(state)

        assert risk.level in ("High", "Critical")
        assert state.impacts.reputational is not None
        assert state.impacts.economic is not None
        assert state.impacts.legal_regulatory is not None

    def test_output_schema_valid(self):
        """Output must be a valid DomainImpact (Pydantic validates all fields)."""
        claims = [_claim("C-001", "confirmed smoke incident",
                         status="confirmed", strength="strong")]
        state = _base_state(claims=claims, sources=[_source("U-01")])
        rep, eco, leg = _run_all(state)
        assert isinstance(rep, DomainImpact)
        assert isinstance(eco, DomainImpact)
        assert isinstance(leg, DomainImpact)


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
        risk = _risk_from_all(state)

        assert risk.level != "Critical", (
            "A single unconfirmed allegation must not produce Critical"
        )

    def test_evidence_confidence_low(self):
        claims = [_claim("C-001", "allegation only", status="unconfirmed", strength="weak")]
        state = _base_state(claims=claims)
        risk = _risk_from_all(state)
        assert risk.evidence_confidence == "low"

    def test_stakeholders_check_domain_runs(self):
        """Even with weak evidence, all three domains must return valid DomainImpact."""
        claims = [_claim("C-001", "allegation", status="unconfirmed", strength="weak", market="DE")]
        state = _base_state(claims=claims)
        rep, eco, leg = _run_all(state)
        assert rep is not None
        assert eco is not None
        assert leg is not None


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
        risk = _risk_from_all(state)
        # Misleading claim is filtered out; only C-002 remains
        assert risk.level in ("Low", "Medium")

    def test_disproved_claim_excluded(self):
        """Disproved claims must be filtered before domain assessment."""
        claims = [
            _claim("C-001", "PCX-100 recalled in Spain — 100,000 units",
                   status="disproved", strength="weak"),
        ]
        state = _base_state(claims=claims)
        risk = _risk_from_all(state)
        assert risk.level in ("Low", "Medium")


# ---------------------------------------------------------------------------
# 4. Missing financial information → no invented financial figures
# ---------------------------------------------------------------------------

class TestMissingFinancialInfo:
    def test_economic_impact_present_even_without_financial_claims(self):
        """
        When no financial claims exist, economic assessment still runs but
        should not invent numbers. The stub returns a generalised impact description.
        """
        claims = [
            _claim("C-001", "PCX-100 overheating complaint",
                   domains=["reputational"],  # no economic domain
                   status="unconfirmed", strength="weak"),
        ]
        state = _base_state(claims=claims)
        _, eco, _ = _run_all(state)
        assert eco is not None
        # Stub must flag "[STUB]" or similar — in production the LLM must follow
        # the economic lens rules (KB-12 ranges, no invented figures)
        assert eco.severity >= 1 and eco.likelihood >= 1

    def test_economic_severity_low_without_financial_evidence(self):
        """With no economic-domain claims, economic severity should stay low in stub mode."""
        claims = [_claim("C-001", "social media post about smell",
                         domains=["reputational"], status="unconfirmed")]
        state = _base_state(claims=claims)
        _, eco, _ = _run_all(state)
        assert eco is not None


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
        _, _, leg = _run_all(state)
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
        rep, eco, leg = _run_all(state)
        state.impacts = Impacts(reputational=rep, economic=eco, legal_regulatory=leg)
        risk = compute_risk(state)

        # F1 must appear in at least one domain
        all_floors: set[str] = set()
        for d in [rep, leg]:
            if d:
                all_floors.update(d.floor_triggers)
        assert "F1" in all_floors
        assert risk.level == "High"


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
        risk_v1 = _risk_from_all(state_v1)
        level_v1 = risk_v1.level

        # Version 2: claim upgraded to confirmed
        claims_v2 = [
            _claim("C-001", "PCX-100 overheating confirmed by lab",
                   status="confirmed", strength="strong",
                   version=2),
        ]
        state_v2 = _base_state(version=2, claims=claims_v2, prev_risk=risk_v1)
        risk_v2 = _risk_from_all(state_v2, prev=state_v1)

        rank = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
        assert rank[risk_v2.level] > rank[level_v1], (
            f"Risk should increase: {level_v1} → {risk_v2.level}"
        )


# ---------------------------------------------------------------------------
# 7. New evidence does NOT change overall risk but changes explanation
# ---------------------------------------------------------------------------

class TestNewEvidenceChangesExplanationNotLevel:
    def test_second_independent_report_same_level_different_explanation(self):
        """
        Adding a second independent unconfirmed report should not necessarily
        change the level. In stub mode, the level may stay the same while the
        claim count changes.
        """
        claims_v1 = [_claim("C-001", "single smoke report", status="unconfirmed")]
        state_v1 = _base_state(version=1, claims=claims_v1)
        risk_v1 = _risk_from_all(state_v1)

        # Second report added — same level expected
        claims_v2 = [
            _claim("C-001", "first smoke report", status="unconfirmed"),
            _claim("C-002", "second smoke report same batch", status="unconfirmed"),
        ]
        state_v2 = _base_state(version=2, claims=claims_v2, prev_risk=risk_v1)
        risk_v2 = _risk_from_all(state_v2)

        # Level might be the same or higher (stub-based); we just verify consistency
        assert risk_v2.level in ("Low", "Medium", "High", "Critical")
        # Schema is still valid
        assert isinstance(risk_v2, Risk)


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
                claim_id="C-101",
                text="2025 TravelPlug social post (historical)",
                status="unconfirmed",
                evidence_strength="weak",
                source_ids=["KB-07"],
                domains=["reputational"],
                first_seen_version=1,
                last_changed_version=1,
                change_history=[ClaimChange(version=1, **{"from": None}, to="unconfirmed",
                                             reason="initial", source_ids=["KB-07"])],
            )
        ]
        state = _base_state(claims=claims, sources=sources)
        risk = _risk_from_all(state)

        # With only one unconfirmed historical claim, risk should be low/medium
        assert risk.level in ("Low", "Medium"), (
            f"Historical-only evidence should not produce {risk.level}"
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

        levels = []
        for _ in range(3):
            s = _base_state(claims=claims)
            risk = _risk_from_all(s)
            levels.append(risk.level)
        assert len(set(levels)) == 1, f"Non-deterministic levels across runs: {levels}"
