"""Tests for A3 Action Planner (src/agents/a3_actions.py).

Claude is faked at the client level (same pattern as tests/test_llm.py), so the real
llm.py retry logic runs: no network, no API key, no cost.
Case data: Alibek's S1 v1 fixture (tests/fixtures/state_v1_S1.json): 1 unconfirmed smoke
claim, 3 proposed actions (ACT-001 retrieve sample, ACT-002 holding statement, ACT-003
brief Legal), focus "PCX-100 overheating". Plans below simulate S1 turn 2.

Run: python -m pytest tests/test_a3_actions.py -v
"""

import copy
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import anthropic
import pytest

from src import pipeline
from src.agents import a3_actions as a3
from src.contracts import A3Output, CaseState, TurnInput
from src.llm import LLMError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "state_v1_S1.json"

TURN2 = TurnInput(intent="NEW_INFO", user_text=(
    "Quality just came back with results. They managed to retrieve 2 returned units from batch PCX-2609-B. "
    "One unit tested fine. The other shut down later than it should."))

HOLD = {
    "title": "Warehouse hold on batch PCX-2609-B (3,000 units, Frankfurt)",
    "what_it_does": "Stops new shipments of the batch with a confirmed defect while Quality tests more samples. "
                    "Batch B only is recommended because the defect was found there.",
    "owner": "Luca Ferri (Supply Chain)", "approver": "Elena Rossi (COO)",
    "timing": "within 24h", "priority": "P1", "focus_related": True,
    "domains": ["economic", "legal_regulatory"], "basis_source_ids": ["KB-12", "KB-13"],
    "expected_effect": "No further units of the suspect batch reach customers",
    "reason": "Defect confirmed in one PCX-2609-B unit",
    "options_considered": [
        {"option": "Hold batch PCX-2609-B only", "pros": "Targets the confirmed batch", "cons": "Batch A not covered", "chosen": True},
        {"option": "Hold batches PCX-2609-A and PCX-2609-B", "pros": "Covers both September batches",
         "cons": "Two hold setups (KB-12)", "chosen": False}],
}
FOCUS_ONLY = [{"action_id": i, "reason": "focus evaluated", "focus_related": True} for i in ("ACT-002", "ACT-003")]


def plan(new=(), changes=(), stakeholders=None, no_action=()):
    s = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {"new_actions": list(new), "changes": list(changes),
            "stakeholders": s["stakeholders"] if stakeholders is None else stakeholders,
            "no_action_reasons": list(no_action)}


GOOD = plan(new=[HOLD], changes=[
    {"action_id": "ACT-001", "new_status": "completed", "focus_related": True,
     "reason": "User: Quality retrieved 2 units from PCX-2609-B and tested them"}, *FOCUS_ONLY])


# ---------------------------------------------------------------- fake Claude

def _response(text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason, stop_details=None, model="claude-sonnet-5-5", _request_id="req_test",
        usage=SimpleNamespace(input_tokens=100, cache_creation_input_tokens=0, cache_read_input_tokens=0, output_tokens=50),
    )


class FakeClient:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        response = _response(out if isinstance(out, str) else json.dumps(out))

        class _Ctx:
            def __enter__(self_inner):
                return SimpleNamespace(get_final_message=lambda: response)

            def __exit__(self_inner, *exc):
                return False

        return _Ctx()


@pytest.fixture(autouse=True)
def tmp_cases(tmp_path, monkeypatch):
    monkeypatch.setenv("ACME_CASES_DIR", str(tmp_path))
    monkeypatch.setenv("ACME_MODEL", "claude-sonnet-5-5")
    monkeypatch.setenv("ACME_MODEL_LIGHT", "claude-haiku-5-5")
    return tmp_path


@pytest.fixture
def state():
    """S1 at the start of turn 2: the pipeline has already bumped the version."""
    s = CaseState.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    s.version = 2
    return s


def build(p, state):
    parsed = a3.A3Plan.model_validate(p)
    actions, problems = a3.assemble(parsed, state)
    return parsed, actions, problems


def hard(p, state, turn=TURN2):
    parsed, actions, problems = build(p, state)
    return a3.hard_problems(parsed, state, actions, problems, turn)


def soft(p, state):
    parsed, actions, _ = build(p, state)
    return a3.soft_problems(parsed, state, actions)


# ---------------------------------------------------------------- code builds the records

def test_plan_schema_is_accepted_by_the_api():
    assert set(anthropic.transform_schema(a3.A3Plan)["properties"]) == {"new_actions", "changes", "stakeholders", "no_action_reasons"}


def test_new_action_gets_next_id_and_history_for_this_version(state):
    _, actions, problems = build(GOOD, state)
    new = next(a for a in actions if a.title.startswith("Warehouse hold"))
    assert problems == []
    assert new.action_id == "ACT-004"  # continues after ACT-001..003, never reused
    assert new.status == "proposed"
    assert [(h.version, h.from_, h.to) for h in new.status_history] == [(2, None, "proposed")]


def test_two_new_actions_get_consecutive_ids(state):
    second = dict(HOLD, title="Answer the DE retailer with factual guidance", options_considered=[],
                  owner="Luca Ferri (Supply Chain)")
    _, actions, _ = build(plan(new=[HOLD, second]), state)
    assert [a.action_id for a in actions] == ["ACT-004", "ACT-005"]


def test_status_change_appends_history_and_keeps_earlier_entries(state):
    _, actions, _ = build(GOOD, state)
    act1 = next(a for a in actions if a.action_id == "ACT-001")
    old = state.action("ACT-001")
    assert act1.status == "completed"
    assert pipeline._history_kept(old.status_history, act1.status_history)  # the merge rule A0 enforces
    assert (act1.status_history[-1].version, act1.status_history[-1].from_, act1.status_history[-1].to) == (2, "proposed", "completed")
    assert "Quality retrieved 2 units" in act1.status_history[-1].reason


def test_field_revision_without_status_change_adds_no_history(state):
    p = plan(changes=[{"action_id": "ACT-003", "reason": "F2 now triggered", "priority": "P1",
                       "what_it_does": "Legal assesses the authority notification obligation now that a defect is confirmed (F2).",
                       "focus_related": True}])
    _, actions, _ = build(p, state)
    assert actions[0].what_it_does.startswith("Legal assesses")
    assert actions[0].status_history == state.action("ACT-003").status_history


def test_user_reported_done_action_starts_at_reported_status(state):
    done = dict(HOLD, title="Call the DE retailer", options_considered=[], initial_status="completed",
                reason="User: the DE retailer has been contacted")
    _, actions, _ = build(plan(new=[done]), state)
    assert actions[0].status == "completed"
    assert [(h.from_, h.to) for h in actions[0].status_history] == [(None, "completed")]


def test_new_action_can_never_start_as_verified():
    with pytest.raises(Exception):
        a3.A3Plan.model_validate(plan(new=[dict(HOLD, initial_status="verified_effective")]))


def test_unknown_action_id_and_double_change_are_reported(state):
    p = plan(changes=[{"action_id": "ACT-099", "reason": "x"},
                      {"action_id": "ACT-002", "reason": "a", "focus_related": True},
                      {"action_id": "ACT-002", "reason": "b", "focus_related": True}])
    _, actions, problems = build(p, state)
    assert any("ACT-099" in x and "not in the action register" in x for x in problems)
    assert any("ACT-002 is changed twice" in x for x in problems)
    assert [a.action_id for a in actions] == ["ACT-002"]


def test_verified_without_result_evidence_is_rejected(state):
    p = plan(changes=[{"action_id": "ACT-001", "new_status": "verified_effective", "reason": "User: works", "focus_related": True}])
    _, actions, problems = build(p, state)
    assert actions == [] and "needs result_evidence_source_ids" in problems[0]


def test_no_focus_means_focus_related_is_none(state):
    state.focus = None
    _, actions, _ = build(GOOD, state)
    assert all(a.focus_related is None for a in actions)


# ---------------------------------------------------------------- hard checks

def test_good_plan_has_no_hard_problems(state):
    assert hard(GOOD, state) == []


def test_owner_and_approver_must_be_on_contact_sheet(state):
    p = plan(new=[dict(HOLD, owner="John Smith (Logistics)", approver="Warehouse manager")], changes=FOCUS_ONLY + [
        {"action_id": "ACT-001", "reason": "focus", "focus_related": True}])
    problems = hard(p, state)
    assert any("owner 'John Smith (Logistics)' is not on the ACME contact sheet" in x for x in problems)
    assert any("approver 'Warehouse manager'" in x for x in problems)


def test_stakeholder_contact_must_be_on_contact_sheet(state):
    s = json.loads(FIXTURE.read_text(encoding="utf-8"))["stakeholders"]
    s[0]["acme_contact"] = "Someone Else"
    assert any("acme_contact 'Someone Else'" in x for x in hard(dict(GOOD, stakeholders=s), state))


def test_source_ids_must_exist(state):
    p = copy.deepcopy(GOOD)
    p["new_actions"][0]["basis_source_ids"] = ["KB-12", "KB-99", "U-77"]
    problems = hard(p, state)
    assert any("basis_source_ids not found: KB-99, U-77" in x for x in problems)
    p = copy.deepcopy(GOOD)
    p["changes"][0]["result_evidence_source_ids"] = ["KB-03"]  # a KB file is not result evidence for this case
    assert any("result_evidence_source_ids must be registered evidence about this incident" in x and "KB-03" in x
               for x in hard(p, state))
    p["changes"][0]["result_evidence_source_ids"] = ["U-01"]  # the user's evidence is fine
    assert hard(p, state) == []


def test_duplicate_of_existing_action_is_rejected(state):
    """On an A4 revise run the first run's actions are already in the register."""
    dup = dict(HOLD, title="Publish holding statement on social media post!")  # = ACT-002's title
    problems = hard(plan(new=[dup], changes=GOOD["changes"]), state)
    assert any("already in the register as ACT-002" in x for x in problems)


def test_focus_related_required_for_every_live_action_when_focus_is_set(state):
    p = plan(new=[dict(HOLD, focus_related=None)])
    problems = hard(p, state)
    assert any("set focus_related" in x and "ACT-001" in x and "ACT-004" in x for x in problems)


@pytest.mark.parametrize("text", [
    "DRAFT – requires approval by Anna Keller: all units were tested and the authorities have been notified.",
    "A remote firmware update will fix the PCX-100 charger.",
    "Ask R. Dubois for the unit.",
])
def test_banned_phrases_and_personal_data_in_drafts_are_hard(state, text):
    p = copy.deepcopy(GOOD)
    p["new_actions"][0]["what_it_does"] = text
    assert hard(p, state)


@pytest.mark.parametrize("text", [  # session 3: KB-04, KB-09, scenario S2
    "Ask the customers to send their camera recordings to our support account.",
    "Request customers for their passwords so Security can check.",
    "DRAFT – requires approval by Anna Keller: your data is safe.",
    "No breach has occurred, so the case can be closed.",
    "No personal data was accessed.",
    "The account recovery proves that no earlier recording was viewed.",
])
def test_session3_banned_phrases_are_hard(state, text):
    p = copy.deepcopy(GOOD)
    p["new_actions"][0]["what_it_does"] = text
    assert any("banned phrase" in x for x in hard(p, state))


@pytest.mark.parametrize("text", [
    "Do not ask customers to send passwords or camera recordings (KB-04).",
    "Do not tell customers their data is safe before Security has reviewed the logs.",
    "Legal decides; we cannot say that no breach occurred.",
])
def test_session3_negated_guidance_passes(state, text):
    p = copy.deepcopy(GOOD)
    p["new_actions"][0]["what_it_does"] = text
    assert hard(p, state) == []


def test_status_change_needs_a_user_message_this_turn(state):
    silent = TurnInput(intent="NEW_INFO", user_text="", attachments=[])
    problems = hard(GOOD, state, silent)
    assert any("ACT-001: status set to 'completed' but the user reported nothing" in x for x in problems)
    # a new 'proposed' action is fine without a user message
    assert not any("ACT-004" in x and "reported nothing" in x for x in problems)
    # an attachment (e.g. a lab report PDF) counts as a user report
    assert hard(GOOD, state, TurnInput(intent="NEW_INFO", user_text="", attachments=["U-02"])) == []


def test_empty_what_it_does_is_hard(state):
    p = copy.deepcopy(GOOD)
    p["new_actions"][0]["what_it_does"] = "  "
    assert any("ACT-004: title and what_it_does must not be empty" in x for x in hard(p, state))


def test_negated_guidance_in_draft_is_fine(state):
    # wording from Alibek's S1 fixture (ACT-002)
    p = copy.deepcopy(GOOD)
    p["new_actions"][0]["what_it_does"] = "Do not claim 'all units tested' or 'authorities contacted' (KB-10 restriction)."
    assert hard(p, state) == []


def test_negation_only_counts_close_to_the_phrase(state):
    """Deliberate trade-off: a 'not' far before the phrase does not cancel it, so a real false
    claim like this one is caught (a long negated sentence costs at most one retry)."""
    p = copy.deepcopy(GOOD)
    p["new_actions"][0]["what_it_does"] = "ACME has not seen further reports and the authorities have been notified."
    assert any("authorities contacted" in x for x in hard(p, state))


# ---------------------------------------------------------------- soft checks

def test_good_plan_has_no_soft_warnings(state):
    assert soft(GOOD, state) == []


def test_missing_basis_and_effect_are_warned(state):
    p = copy.deepcopy(GOOD)
    p["new_actions"][0]["basis_source_ids"] = []
    p["new_actions"][0]["expected_effect"] = ""
    warnings = soft(p, state)
    assert any("ACT-004: no basis_source_ids and not labelled" in x for x in warnings)
    assert any("ACT-004: expected_effect is empty" in x for x in warnings)
    p["new_actions"][0]["what_it_does"] += " ACME has no precedent for this (general knowledge)."
    assert not any("no basis_source_ids" in x for x in soft(p, state))


def test_major_decision_needs_two_options_one_chosen(state):
    p = copy.deepcopy(GOOD)
    p["new_actions"][0]["options_considered"] = p["new_actions"][0]["options_considered"][:1]
    assert any("major decision needs >= 2 options" in x for x in soft(p, state))


def test_recall_needs_ceo_and_authority_needs_legal(state):
    recall = dict(HOLD, title="Recall batch PCX-2609-B from retailers", approver="Elena Rossi (COO)")
    notify = dict(HOLD, title="Notify the product-safety authority", owner="Elena Rossi (COO)",
                  approver="Elena Rossi (COO)", options_considered=HOLD["options_considered"])
    warnings = soft(plan(new=[recall, notify]), state)
    assert any("ACT-004" in x and "Daniel Moretti (CEO)" in x for x in warnings)
    assert any("ACT-005" in x and "Sophie Laurent" in x for x in warnings)


def test_high_domain_without_action_is_flagged_unless_explained(state):
    state.impacts.economic.severity, state.impacts.economic.likelihood, state.impacts.economic.score = 3, 3, 9
    for a in state.actions:
        a.domains = [d for d in a.domains if d != "economic"]
    p = plan(changes=FOCUS_ONLY + [{"action_id": "ACT-001", "reason": "focus", "focus_related": True}])
    assert any("economic impact is High/Critical" in x for x in soft(p, state))
    p["no_action_reasons"] = ["economic: no action, because the hold cost is covered by ACT-001"]
    warnings = soft(p, state)
    assert not any("economic impact is High/Critical" in x for x in warnings)
    assert "no action: economic: no action, because the hold cost is covered by ACT-001" in warnings


# ---------------------------------------------------------------- LLM call + retry (through llm.py)

def test_good_plan_one_call(state):
    client = FakeClient(GOOD)
    out, warnings = a3.plan_actions(state, TURN2, client=client)
    assert isinstance(out, A3Output) and len(client.calls) == 1 and warnings == []
    assert {a.action_id for a in out.actions} == {"ACT-001", "ACT-002", "ACT-003", "ACT-004"}
    assert len(out.stakeholders) == 5


def test_hard_problem_triggers_one_retry_with_the_problems(state):
    bad = copy.deepcopy(GOOD)
    bad["new_actions"][0]["owner"] = "John Smith (Logistics)"
    client = FakeClient(bad, GOOD)
    out, warnings = a3.plan_actions(state, TURN2, client=client)
    assert len(client.calls) == 2 and warnings == []
    assert "John Smith" in client.calls[1]["messages"][-1]["content"]


def test_still_wrong_after_retry_keeps_valid_parts_and_warns(state):
    bad = copy.deepcopy(GOOD)
    bad["changes"].append({"action_id": "ACT-099", "reason": "x"})
    out, warnings = a3.plan_actions(state, TURN2, client=FakeClient(bad, bad))
    assert "ACT-004" in {a.action_id for a in out.actions}
    assert any("ACT-099" in w for w in warnings)


def test_invalid_json_twice_raises_like_other_agents(state):
    with pytest.raises(LLMError):
        a3.plan_actions(state, TURN2, client=FakeClient("not json", "still not json"))


def test_request_settings_and_input(state):
    state.qa.issues = state.qa.issues + [
        state.qa.issues[0].model_copy(update={"target": "A3", "problem": "Hold has only one option", "resolved": False})
    ] if state.qa.issues else []
    client = FakeClient(GOOD)
    a3.plan_actions(state, TURN2, client=client)
    call = client.calls[0]
    assert call["model"] == "claude-sonnet-5-5" and call["output_config"]["effort"] == "high"
    assert "You are the Action Planner" in call["system"][1]["text"]
    user = call["messages"][0]["content"]
    assert "Quality just came back with results" in user and '"action_register"' in user
    if state.qa.issues:
        assert "Hold has only one option" in user


def test_run_logs_warnings(state, caplog):
    p = copy.deepcopy(GOOD)
    p["new_actions"][0]["options_considered"] = []
    with caplog.at_level(logging.WARNING, logger="src.agents.a3_actions"):
        out = a3.run(state, TURN2, client=FakeClient(p))
    assert isinstance(out, A3Output)
    assert "major decision needs >= 2 options" in caplog.text
    assert any("major decision needs >= 2 options" in w for w in out.warnings)  # D-015


# ---------------------------------------------------------------- pipeline

def test_pipeline_picks_up_real_a3():
    assert pipeline.load_agents(use_stubs=False).used["a3"] == "src.agents.a3_actions.run"


def test_pipeline_two_turns_with_real_a3(tmp_cases):
    """Turn 1 proposes an action; turn 2 (user reports it approved) changes only its status."""
    first = {"new_actions": [dict(HOLD, focus_related=None, domains=["economic"])], "changes": [],
             "stakeholders": [{"name": "Retailers", "type": "external", "acme_contact": "Luca Ferri (Supply Chain)"}],
             "no_action_reasons": []}
    a = pipeline.load_agents(use_stubs=True)
    client = FakeClient(first)
    a.a3 = lambda s, t: a3.run(s, t, client=client)
    r1 = pipeline.run_turn("Customers in Germany report PCX-100 chargers getting hot", agents=a)
    assert r1.error is None
    s1 = CaseState.model_validate_json((tmp_cases / r1.case_id / "state_v1.json").read_text(encoding="utf-8"))
    hold = next(x for x in s1.actions if x.title.startswith("Warehouse hold"))

    second = {"new_actions": [], "changes": [{"action_id": hold.action_id, "new_status": "approved",
                                              "reason": "User: Elena approved the hold"}],
              "stakeholders": [], "no_action_reasons": []}
    client.outputs.append(second)
    r2 = pipeline.run_turn("Elena approved the hold.", case_id=r1.case_id, agents=a)
    assert r2.error is None and r2.version == 2
    s2 = CaseState.model_validate_json((tmp_cases / r1.case_id / "state_v2.json").read_text(encoding="utf-8"))
    hold2 = s2.action(hold.action_id)
    assert hold2.status == "approved"  # approved, not completed
    assert [(h.version, h.to) for h in hold2.status_history] == [(1, "proposed"), (2, "approved")]
    assert len(s2.actions) == len(s1.actions)  # nothing deleted, nothing duplicated
    assert [x.name for x in s2.stakeholders] == ["Retailers"]  # empty stakeholder list keeps the old map
