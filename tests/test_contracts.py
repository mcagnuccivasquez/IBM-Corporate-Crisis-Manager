"""Contract tests: the example state in PROJECT.md §4 must validate, and the
per-object invariants must reject bad agent output."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.contracts import (
    Action,
    CaseState,
    Claim,
    DomainImpact,
    new_case,
)

FIXTURE = Path(__file__).parent / "fixtures" / "contract_example_state.json"


@pytest.fixture
def raw() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_example_state_validates(raw):
    state = CaseState.model_validate(raw)
    assert state.version == 2
    assert state.risk.level == "High" and state.risk.previous_level == "Medium"
    assert state.claim("C-002").status == "unconfirmed"
    assert state.source("U-03").duplicate_of == "U-02"
    assert state.impacts.reputational.score == 6
    assert state.reference_errors() == []


def test_round_trip_keeps_field_names(raw):
    state = CaseState.model_validate(raw)
    dumped = json.loads(state.to_json())
    # "from" (a Python keyword) must survive as "from", not "from_"
    assert dumped["claims"][0]["change_history"][0]["from"] is None
    assert "from_" not in state.to_json()
    assert CaseState.model_validate(dumped) == state


def test_new_case_is_valid_and_empty():
    state = new_case("CASE-007")
    assert state.version == 0 and state.status == "open"
    assert state.sources == [] and state.risk is None
    CaseState.model_validate_json(state.to_json())


def test_json_schema_builds():
    # Agents use these models (or subsets) as structured-output schemas.
    schema = CaseState.model_json_schema()
    assert "claims" in schema["properties"]


def test_unknown_field_rejected(raw):
    raw["claims"][0]["confidence"] = "high"  # typo / invented field
    with pytest.raises(ValidationError):
        CaseState.model_validate(raw)


def test_score_must_equal_s_times_l(raw):
    block = raw["impacts"]["economic"]
    block["score"] = 9
    with pytest.raises(ValidationError, match="severity"):
        DomainImpact.model_validate(block)
    del block["score"]
    assert DomainImpact.model_validate(block).score == 4  # filled automatically


def test_claim_change_needs_reason_and_source(raw):
    claim = copy.deepcopy(raw["claims"][1])
    claim["change_history"].append({"version": 3, "from": "unconfirmed", "to": "disproved", "reason": "Lab test", "source_ids": []})
    claim["status"] = "disproved"
    with pytest.raises(ValidationError):
        Claim.model_validate(claim)


def test_claim_status_must_match_history(raw):
    claim = copy.deepcopy(raw["claims"][1])
    claim["status"] = "confirmed"  # changed without a history entry
    with pytest.raises(ValidationError, match="change_history"):
        Claim.model_validate(claim)


def test_verified_action_needs_result_evidence(raw):
    action = copy.deepcopy(raw["actions"][0])
    action["status_history"].append({"version": 3, "from": "approved", "to": "verified_effective", "reason": "Done"})
    action["status"] = "verified_effective"
    with pytest.raises(ValidationError, match="result_evidence"):
        Action.model_validate(action)
    action["result_evidence_source_ids"] = ["U-04"]
    Action.model_validate(action)


def test_duplicate_ids_rejected(raw):
    raw["claims"].append(copy.deepcopy(raw["claims"][0]))
    with pytest.raises(ValidationError, match="duplicate claim_id"):
        CaseState.model_validate(raw)


@pytest.mark.parametrize("bad", ["KB-1", "U-1", "SRC-01", "kb-01"])
def test_bad_source_id_rejected(raw, bad):
    raw["sources"][0]["source_id"] = bad
    with pytest.raises(ValidationError):
        CaseState.model_validate(raw)


def test_d013_additions_are_optional_and_validated(raw):
    # existing data (without the new fields) stays valid
    state = CaseState.model_validate(raw)
    assert state.actions[0].focus_related is None and state.report.narrative_warnings is None
    # new fields accepted
    raw["actions"][0]["focus_related"] = True
    raw["report"]["narrative_warnings"] = ["executive_summary: 92 words (limit 80)"]
    raw["impacts"]["reputational"]["impacts"][0]["basis"] = "incident_evidence"
    raw["report"]["narrative"]["closure_summary"] = "Case closed with residual risk Medium."
    state = CaseState.model_validate(raw)
    assert state.actions[0].focus_related is True
    assert state.impacts.reputational.impacts[0].basis == "incident_evidence"
    # narrative values must be text: omit a key instead of sending null
    raw["report"]["narrative"]["closure_summary"] = None
    with pytest.raises(ValidationError):
        CaseState.model_validate(raw)


def test_reference_errors_reports_dangling_ids(raw):
    raw["claims"][0]["source_ids"] = ["U-99"]
    raw["closure"] = {"remaining_risk": "Medium", "open_actions": ["ACT-999"], "reopen_conditions": []}
    errors = CaseState.model_validate(raw).reference_errors()
    assert any("U-99" in e for e in errors)
    assert any("ACT-999" in e for e in errors)
