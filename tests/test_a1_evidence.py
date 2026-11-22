"""Tests for A1 Evidence Analyst.

Covers:
- _next_source_id / _next_claim_id helpers
- _build_context_block structure
- run() happy path (mocked call_structured)
- run() with no existing state (first turn)
- run() passes correct args to call_structured
- Contracts enforcement: missing change_history, bad claim status, bad source ID
- Acceptance criteria from A1_evidence_analyst.md §7 (pure contract / logic tests;
  the full LLM-in-the-loop scenarios live in tests/scenarios/)

No LLM calls are made in this file. The `run()` integration test patches
`call_structured` so only the wrapper code is exercised.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.agents.a1_evidence import _build_context_block, _next_claim_id, _next_source_id, run
from src.contracts import (
    A1Output,
    CaseState,
    Claim,
    ClaimChange,
    OpenQuestion,
    Source,
    TurnInput,
    new_case,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_STATE = Path(__file__).parent / "fixtures" / "contract_example_state.json"


@pytest.fixture
def example_state() -> CaseState:
    return CaseState.model_validate_json(FIXTURE_STATE.read_text(encoding="utf-8"))


@pytest.fixture
def empty_state() -> CaseState:
    return new_case("CASE-099")


@pytest.fixture
def turn_text() -> TurnInput:
    return TurnInput(intent="NEW_INFO", user_text="A new report from a customer.")


@pytest.fixture
def turn_no_text() -> TurnInput:
    return TurnInput(intent="NEW_INFO", user_text="")


# ---------------------------------------------------------------------------
# Helper: _next_source_id
# ---------------------------------------------------------------------------


def test_next_source_id_empty_state(empty_state):
    assert _next_source_id(empty_state) == "U-01"


def test_next_source_id_with_existing(example_state):
    # example_state has U-01, U-02, U-03 → next should be U-04
    nxt = _next_source_id(example_state)
    assert nxt == "U-04"


def test_next_source_id_ignores_kb_sources(empty_state):
    # KB sources should not influence U-xx numbering
    # Add a KB source artificially to the state to verify
    empty_state.sources = [
        Source(
            source_id="KB-01", title="KB", origin="kb",
            category="reference", time_relevance="current",
            added_in_version=0,
        )
    ]
    assert _next_source_id(empty_state) == "U-01"


# ---------------------------------------------------------------------------
# Helper: _next_claim_id
# ---------------------------------------------------------------------------


def test_next_claim_id_empty_state(empty_state):
    assert _next_claim_id(empty_state) == "C-001"


def test_next_claim_id_with_existing(example_state):
    # example_state has C-001, C-002, C-003 → next should be C-004
    nxt = _next_claim_id(example_state)
    assert nxt == "C-004"


# ---------------------------------------------------------------------------
# Helper: _build_context_block
# ---------------------------------------------------------------------------


def test_build_context_block_has_id_hints(example_state):
    text = _build_context_block(example_state)
    assert "U-04" in text
    assert "C-004" in text


def test_build_context_block_has_case_state_json(example_state):
    text = _build_context_block(example_state)
    assert "existing_sources" in text
    assert "existing_claims" in text
    assert "CASE-001" in text


def test_build_context_block_has_version_hint(example_state):
    """raised_in_version hint must match state.version so the LLM uses the right value."""
    text = _build_context_block(example_state)
    assert f"raised_in_version: {example_state.version}" in text


def test_build_context_block_returns_str(example_state):
    text = _build_context_block(example_state)
    assert isinstance(text, str)


def test_build_context_block_empty_state(empty_state):
    text = _build_context_block(empty_state)
    assert "U-01" in text
    assert "C-001" in text
    assert "CASE-099" in text


# ---------------------------------------------------------------------------
# run(): integration (call_structured patched — no API calls)
# ---------------------------------------------------------------------------


def _make_a1_output(state: CaseState) -> A1Output:
    """Build a minimal valid A1Output for a given state."""
    next_u = _next_source_id(state)
    next_c = _next_claim_id(state)
    # A0 always bumps version to N+1 before calling A1, so version ≥ 1 when A1 runs.
    # For tests that start from version=0, use 1 to match what the pipeline would pass.
    version = max(state.version, 1)
    return A1Output(
        sources=[
            Source(
                source_id=next_u,
                title="Customer email describing PCX-100 smoke",
                origin="user_text",
                date="2026-11-22",
                category="incident_evidence",
                time_relevance="current",
                reliability_note="Single customer report, identity unverified",
                added_in_version=version,
            )
        ],
        claims=[
            Claim(
                claim_id=next_c,
                text="Customer reports PCX-100 emitted smoke during charging",
                status="unconfirmed",
                evidence_strength="weak",
                source_ids=[next_u],
                domains=["reputational", "legal_regulatory"],
                product="PCX-100",
                first_seen_version=version,
                last_changed_version=version,
                change_history=[
                    ClaimChange(
                        version=version,
                        **{"from": None},
                        to="unconfirmed",
                        reason="Single unverified customer report",
                        source_ids=[next_u],
                    )
                ],
            )
        ],
        open_questions=[
            OpenQuestion(
                question="Can the customer supply the original unit for lab testing?",
                owner="Tom Weber (Customer Care)",
                raised_in_version=version,
            )
        ],
    )


@patch("src.agents.a1_evidence.call_structured")
def test_run_returns_a1_output(mock_cs, example_state, turn_text):
    mock_cs.return_value = _make_a1_output(example_state)
    result = run(example_state, turn_text)
    assert isinstance(result, A1Output)
    assert len(result.sources) == 1
    assert result.sources[0].source_id == "U-04"
    assert len(result.claims) == 1
    assert result.claims[0].status == "unconfirmed"


@patch("src.agents.a1_evidence.call_structured")
def test_run_first_turn_empty_state(mock_cs, empty_state, turn_text):
    """run() must work with a brand-new case (version 0, no sources/claims)."""
    mock_cs.return_value = _make_a1_output(empty_state)
    result = run(empty_state, turn_text)
    assert result.sources[0].source_id == "U-01"
    assert result.claims[0].claim_id == "C-001"


@patch("src.agents.a1_evidence.call_structured")
def test_run_passes_agent_a1_to_call_structured(mock_cs, example_state, turn_text):
    mock_cs.return_value = _make_a1_output(example_state)
    run(example_state, turn_text)
    call_args = mock_cs.call_args
    # call_structured("A1", ...) — first positional arg
    assert call_args.args[0] == "A1"


@patch("src.agents.a1_evidence.call_structured")
def test_run_passes_case_id(mock_cs, example_state, turn_text):
    mock_cs.return_value = _make_a1_output(example_state)
    run(example_state, turn_text)
    call_kwargs = mock_cs.call_args
    assert call_kwargs.kwargs.get("case_id") == example_state.case_id


@patch("src.agents.a1_evidence.call_structured")
def test_run_uses_effort_high(mock_cs, example_state, turn_text):
    mock_cs.return_value = _make_a1_output(example_state)
    run(example_state, turn_text)
    call_args = mock_cs.call_args
    # call_structured("A1", prompt, content, A1Output, "high", ...)
    # effort is the 5th positional arg (index 4)
    assert call_args.args[4] == "high"


@patch("src.agents.a1_evidence.call_structured")
def test_run_passes_check_kwarg(mock_cs, example_state, turn_text):
    """run() must pass a `check` callable to call_structured for KB-id validation."""
    mock_cs.return_value = _make_a1_output(example_state)
    run(example_state, turn_text)
    call_kwargs = mock_cs.call_args
    assert callable(call_kwargs.kwargs.get("check")), "check= kwarg must be a callable"


@patch("src.agents.a1_evidence.call_structured")
def test_run_check_passes_valid_kb_ids(mock_cs, example_state, turn_text):
    """The check= lambda must return [] for a claim citing only valid source IDs."""
    mock_cs.return_value = _make_a1_output(example_state)
    run(example_state, turn_text)
    check_fn = mock_cs.call_args.kwargs.get("check")
    # _make_a1_output uses U-xx IDs (not KB-xx), so unknown_kb_ids returns []
    result = check_fn(_make_a1_output(example_state))
    assert result == []


@patch("src.agents.a1_evidence.call_structured")
def test_run_check_flags_unknown_kb_ids(mock_cs, example_state, turn_text):
    """The check= lambda must flag KB-xx IDs not in the registry."""
    mock_cs.return_value = _make_a1_output(example_state)
    run(example_state, turn_text)
    check_fn = mock_cs.call_args.kwargs.get("check")

    bad_output = A1Output(
        claims=[
            Claim(
                claim_id="C-001",
                text="Test",
                status="unconfirmed",
                evidence_strength="weak",
                source_ids=["KB-99"],  # not in registry
                first_seen_version=1,
                last_changed_version=1,
                change_history=[
                    ClaimChange(
                        version=1,
                        **{"from": None},
                        to="unconfirmed",
                        reason="test",
                        source_ids=["KB-99"],
                    )
                ],
            )
        ]
    )
    problems = check_fn(bad_output)
    assert len(problems) == 1
    assert "KB-99" in problems[0]


@patch("src.agents.a1_evidence.call_structured")
def test_run_user_text_included_in_content(mock_cs, example_state, turn_text):
    """The user message block must contain the turn's user_text."""
    mock_cs.return_value = _make_a1_output(example_state)
    run(example_state, turn_text)
    call_args = mock_cs.call_args
    # content is 3rd positional arg (index 2)
    content: list[dict] = call_args.args[2]
    all_text = " ".join(b.get("text", "") for b in content if b.get("type") == "text")
    assert "A new report from a customer" in all_text


@patch("src.agents.a1_evidence.call_structured")
def test_run_context_block_in_content(mock_cs, example_state, turn_text):
    """The context block (ID hints + existing state JSON) must be in the content."""
    mock_cs.return_value = _make_a1_output(example_state)
    run(example_state, turn_text)
    call_args = mock_cs.call_args
    content: list[dict] = call_args.args[2]
    all_text = " ".join(b.get("text", "") for b in content if b.get("type") == "text")
    assert "existing_sources" in all_text
    assert "U-04" in all_text  # next source ID hint


# ---------------------------------------------------------------------------
# A1Output contract enforcement (via contracts.py validators)
# ---------------------------------------------------------------------------


def test_a1_output_claim_requires_change_history():
    """A claim without change_history must be rejected."""
    with pytest.raises(ValidationError):
        A1Output(
            claims=[
                Claim(
                    claim_id="C-001",
                    text="Some claim",
                    status="unconfirmed",
                    evidence_strength="weak",
                    source_ids=["U-01"],
                    domains=["reputational"],
                    first_seen_version=1,
                    last_changed_version=1,
                    change_history=[],  # violates min_length=1
                )
            ]
        )


def test_a1_output_claim_status_must_match_history():
    """Claim.status ≠ last change_history entry → ValidationError."""
    with pytest.raises(ValidationError, match="change_history"):
        Claim(
            claim_id="C-001",
            text="Some claim",
            status="confirmed",  # ← mismatch
            evidence_strength="moderate",
            source_ids=["U-01"],
            domains=["reputational"],
            first_seen_version=1,
            last_changed_version=1,
            change_history=[
                ClaimChange(
                    version=1,
                    **{"from": None},
                    to="unconfirmed",
                    reason="Single report",
                    source_ids=["U-01"],
                )
            ],
        )


def test_a1_output_claim_history_requires_source():
    """change_history entry with empty source_ids must be rejected."""
    with pytest.raises(ValidationError):
        Claim(
            claim_id="C-001",
            text="Some claim",
            status="unconfirmed",
            evidence_strength="weak",
            source_ids=["U-01"],
            domains=["reputational"],
            first_seen_version=1,
            last_changed_version=1,
            change_history=[
                ClaimChange(
                    version=1,
                    **{"from": None},
                    to="unconfirmed",
                    reason="Single report",
                    source_ids=[],  # violates min_length=1
                )
            ],
        )


def test_a1_output_claim_requires_source_ids():
    """A claim with no source_ids must be rejected."""
    with pytest.raises(ValidationError):
        Claim(
            claim_id="C-001",
            text="Some claim",
            status="unconfirmed",
            evidence_strength="weak",
            source_ids=[],  # violates min_length=1
            domains=["reputational"],
            first_seen_version=1,
            last_changed_version=1,
            change_history=[
                ClaimChange(
                    version=1,
                    **{"from": None},
                    to="unconfirmed",
                    reason="x",
                    source_ids=["U-01"],
                )
            ],
        )


def test_a1_output_bad_source_id_format():
    """Source IDs that don't match KB-xx or U-xx patterns must be rejected."""
    with pytest.raises(ValidationError):
        Source(
            source_id="SRC-01",  # invalid pattern
            title="Bad ID",
            origin="user_text",
            category="incident_evidence",
            time_relevance="current",
            added_in_version=1,
        )


def test_a1_output_bad_claim_id_format():
    """Claim IDs must match C-NNN+."""
    with pytest.raises(ValidationError):
        Claim(
            claim_id="CLAIM-1",  # invalid pattern
            text="Some claim",
            status="unconfirmed",
            evidence_strength="weak",
            source_ids=["U-01"],
            domains=["reputational"],
            first_seen_version=1,
            last_changed_version=1,
            change_history=[
                ClaimChange(
                    version=1,
                    **{"from": None},
                    to="unconfirmed",
                    reason="x",
                    source_ids=["U-01"],
                )
            ],
        )


def test_a1_output_duplicate_of_must_be_valid_id():
    """duplicate_of must match SOURCE_ID_PATTERN or be None."""
    with pytest.raises(ValidationError):
        Source(
            source_id="U-02",
            title="Repost",
            origin="user_text",
            category="incident_evidence",
            time_relevance="current",
            added_in_version=1,
            duplicate_of="NOT-VALID",
        )


def test_a1_output_accepts_duplicate_of_with_valid_id():
    src = Source(
        source_id="U-02",
        title="Repost",
        origin="user_text",
        category="incident_evidence",
        time_relevance="current",
        added_in_version=1,
        duplicate_of="U-01",
    )
    assert src.duplicate_of == "U-01"


# ---------------------------------------------------------------------------
# Acceptance tests (§7 — logic only, no LLM)
# ---------------------------------------------------------------------------


def test_screenshot_claim_unconfirmed_weak():
    """
    §7 bullet 1: screenshot of a viral post → source incident_evidence,
    claim unconfirmed / weak, domains include reputational + legal_regulatory.
    This tests that the contracts accept the expected shape.
    """
    src = Source(
        source_id="U-01",
        title="Screenshot of TownSquare post: PCX-100 caught fire",
        origin="user_upload",
        date="2026-11-20",
        category="incident_evidence",
        time_relevance="current",
        reliability_note="Screenshot only; original link not provided",
        added_in_version=1,
    )
    claim = Claim(
        claim_id="C-001",
        text="PCX-100 unit caught fire during charging",
        status="unconfirmed",
        evidence_strength="weak",
        source_ids=["U-01"],
        domains=["reputational", "legal_regulatory"],
        product="PCX-100",
        first_seen_version=1,
        last_changed_version=1,
        change_history=[
            ClaimChange(
                version=1,
                **{"from": None},
                to="unconfirmed",
                reason="Single screenshot; original link and capture time not provided",
                source_ids=["U-01"],
            )
        ],
    )
    output = A1Output(sources=[src], claims=[claim])
    assert output.claims[0].status == "unconfirmed"
    assert output.claims[0].evidence_strength == "weak"
    assert "reputational" in output.claims[0].domains
    assert "legal_regulatory" in output.claims[0].domains


def test_repost_duplicate_of():
    """§7 bullet 2: reshared screenshot → new source with duplicate_of set."""
    src = Source(
        source_id="U-02",
        title="News article re-sharing the TownSquare post",
        origin="user_text",
        date="2026-11-21",
        category="incident_evidence",
        time_relevance="current",
        reliability_note="Repeats U-01; not a second independent report",
        added_in_version=1,
        duplicate_of="U-01",
    )
    assert src.duplicate_of == "U-01"


def test_misleading_travelplug_repost():
    """§7 bullet 3: 2025 TravelPlug repost → claim 'misleading' citing KB-07/KB-08."""
    claim = Claim(
        claim_id="C-002",
        text="Old TravelPlug post re-shared as new PCX-100 problem",
        status="misleading",
        evidence_strength="weak",
        source_ids=["U-01", "KB-07"],
        domains=["reputational"],
        product="TravelPlug",
        first_seen_version=1,
        last_changed_version=1,
        change_history=[
            ClaimChange(
                version=1,
                **{"from": None},
                to="misleading",
                reason="This is the 2025 TravelPlug post (KB-07, different product); not evidence about PCX-100",
                source_ids=["KB-07", "KB-08"],
            )
        ],
    )
    assert claim.status == "misleading"
    assert "KB-07" in claim.change_history[0].source_ids


def test_claim_upgrade_to_confirmed_appends_history():
    """§7 bullet 4: lab result in turn 2 upgrades earlier claim to confirmed."""
    claim = Claim(
        claim_id="C-001",
        text="Shutdown fault confirmed in PCX-2609-B samples",
        status="confirmed",
        evidence_strength="strong",
        source_ids=["U-01", "U-05"],
        domains=["reputational", "legal_regulatory"],
        product="PCX-100",
        batch="PCX-2609-B",
        first_seen_version=1,
        last_changed_version=2,
        change_history=[
            ClaimChange(
                version=1,
                **{"from": None},
                to="unconfirmed",
                reason="Single customer report",
                source_ids=["U-01"],
            ),
            ClaimChange(
                version=2,
                **{"from": "unconfirmed"},
                to="confirmed",
                reason="Quality lab confirmed shutdown fault on 2 samples from PCX-2609-B",
                source_ids=["U-05"],
            ),
        ],
    )
    assert claim.status == "confirmed"
    assert len(claim.change_history) == 2
    assert claim.change_history[-1].to == "confirmed"


def test_implausible_quantity_claim_misleading_or_unconfirmed():
    """§7 bullet 5: '100,000 units recalled in Spain' → flagged implausible (misleading or unconfirmed)."""
    # Contracts don't enforce KB-based plausibility — that's the LLM's job.
    # This test confirms the contract accepts such a claim with misleading/unconfirmed status.
    for status in ("misleading", "unconfirmed"):
        claim = Claim(
            claim_id="C-003",
            text="100,000 units recalled in Spain",
            status=status,
            evidence_strength="weak",
            source_ids=["U-01"],
            domains=["reputational", "economic"],
            first_seen_version=1,
            last_changed_version=1,
            change_history=[
                ClaimChange(
                    version=1,
                    **{"from": None},
                    to=status,
                    reason="ACME does not operate in Spain (KB-01) and total stock is 16,000 units (KB-13)",
                    source_ids=["U-01"],
                )
            ],
        )
        assert claim.status == status
