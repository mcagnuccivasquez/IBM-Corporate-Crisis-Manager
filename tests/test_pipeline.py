"""Pipeline (A0) end to end with stub agents: covers the A0 spec §7 acceptance tests
that don't need a live LLM."""

import copy

import pytest

from src import pipeline
from src.agents import stubs
from src.contracts import A1Output, A4Output, A5Output, CaseState, ClaimChange
from src.llm import LLMOutputError

TEXT_V1 = "Customers in Germany report PCX-100 chargers getting hot; a post says one smoked"


@pytest.fixture(autouse=True)
def tmp_cases(tmp_path, monkeypatch):
    monkeypatch.setenv("ACME_CASES_DIR", str(tmp_path))
    return tmp_path


def agents(**overrides):
    a = pipeline.load_agents(use_stubs=True)
    for k, v in overrides.items():
        setattr(a, k, v)
    return a


def test_new_case_creates_v1_state_and_pdf(tmp_cases, tmp_path):
    shot = tmp_path / "post.png"
    shot.write_bytes(b"\x89PNG fake")
    steps = []
    r = pipeline.run_turn(TEXT_V1, [shot], agents=agents(), on_step=steps.append)
    assert r.error is None and r.new_version and r.version == 1 and r.case_id == "CASE-001"
    d = tmp_cases / "CASE-001"
    state = CaseState.model_validate_json((d / "state_v1.json").read_text(encoding="utf-8"))
    assert (d / "report_v1.pdf").stat().st_size > 0
    assert (d / "inputs" / "post.png").exists()
    assert state.risk.level == "High" and state.changelog[-1].version == 1
    assert {"reputational", "economic", "legal_regulatory"} <= state.impacts.model_dump(exclude_none=True).keys()
    assert steps[0] == "A0 intent" and "A2 impacts (3 in parallel)" in steps and steps[-1] == "render PDF"
    assert "Report v1" in r.reply and "High" in r.reply


def test_question_turn_creates_no_new_version(tmp_cases):
    pipeline.run_turn(TEXT_V1, agents=agents())
    r = pipeline.run_turn("Why is the risk High?", case_id="CASE-001", agents=agents())
    assert r.intents == ["QUESTION"] and not r.new_version and r.version == 1
    assert sorted(p.name for p in (tmp_cases / "CASE-001").glob("state_v*.json")) == ["state_v1.json"]
    assert "High" in r.reply


def test_disproved_claim_survives_with_history_and_diff(tmp_cases):
    pipeline.run_turn(TEXT_V1, agents=agents())

    def a1_disprove(state, turn):
        c = copy.deepcopy(state.claim("C-002"))
        c.change_history.append(ClaimChange(version=2, from_="unconfirmed", to="disproved",
                                            reason="Lab test of the returned unit found no fault", source_ids=["U-04"]))
        c.status, c.last_changed_version = "disproved", 2
        new_src = {"source_id": "U-04", "title": "Quality lab report", "origin": "user_upload", "category": "company_record",
                   "time_relevance": "current", "added_in_version": 2}
        return A1Output.model_validate({"sources": [new_src], "claims": [c.model_dump()]})  # C-001, C-003 omitted

    r = pipeline.run_turn("Quality tested the unit: no fault", case_id="CASE-001", agents=agents(a1=a1_disprove))
    assert r.error is None and r.version == 2
    s = r.state
    assert [c.claim_id for c in s.claims] == ["C-001", "C-002", "C-003"]  # nothing deleted
    c2 = s.claim("C-002")
    assert c2.status == "disproved" and len(c2.change_history) == 2
    assert "C-002 unconfirmed → disproved" in s.changelog[-1].claim_changes
    assert s.changelog[-1].new_source_ids == ["U-04"]
    assert [e.version for e in s.changelog] == [1, 2]


def test_history_rewrite_is_rejected_by_merge_rule():
    pipeline.run_turn(TEXT_V1, agents=agents())

    def a1_rewrite(state, turn):
        c = copy.deepcopy(state.claim("C-002"))
        c.change_history = [ClaimChange(version=2, to="confirmed", reason="rewritten", source_ids=["U-02"])]
        c.status = "confirmed"
        return A1Output(claims=[c])

    r = pipeline.run_turn("more info", case_id="CASE-001", agents=agents(a1=a1_rewrite))
    assert r.state.claim("C-002").status == "unconfirmed"  # old claim kept
    assert any(i.item_id == "C-002" and "Merge rule" in i.problem for i in r.state.qa.issues)


def test_a3_warnings_become_non_blocking_qa_issues():
    """D-015: A3Output.warnings -> QAIssue(target="A3", blocking=False) in the state."""
    def a3_warn(state, turn):
        out = stubs.a3(state, turn)
        out.warnings = ["reputational impact is High/Critical but no action covers it"]
        return out

    r = pipeline.run_turn(TEXT_V1, agents=agents(a3=a3_warn))
    hits = [i for i in r.state.qa.issues if i.target == "A3" and "no action covers it" in i.problem]
    assert r.error is None and len(hits) == 1 and not hits[0].blocking


def test_a3_warnings_only_from_latest_run_after_revise():
    """If A4 sends A3 back once, the first run's warnings are dropped (D-015)."""
    calls = {"a3": 0, "a4": 0}

    def a3_counted(state, turn):
        calls["a3"] += 1
        out = stubs.a3(state, turn)
        out.warnings = [f"warning from A3 run {calls['a3']}"]
        return out

    def a4_revise_once(state, turn):
        calls["a4"] += 1
        out = stubs.a4(state, turn)
        if calls["a4"] == 1:
            out.qa.verdict = "REVISE"
            out.qa.issues = [i.model_copy(update={"blocking": False}) for i in out.qa.issues] + [
                out.qa.issues[0].model_copy(update={"target": "A3", "item_id": None, "blocking": True,
                                                    "problem": "fix the plan"})]
        return out

    r = pipeline.run_turn(TEXT_V1, agents=agents(a3=a3_counted, a4=a4_revise_once))
    problems = [i.problem for i in r.state.qa.issues if i.target == "A3"]
    assert r.error is None and calls["a3"] == 2
    assert "warning from A3 run 2" in problems and "warning from A3 run 1" not in problems


def test_mutated_invalid_agent_output_is_caught():
    """An agent that edits a model after creation bypasses validators; the pipeline re-validates."""
    def a1_sloppy(state, turn):
        c = copy.deepcopy(state.claim("C-002"))
        c.status = "confirmed"  # no change_history entry -> contract violation
        return {"claims": [c.model_dump()]}

    pipeline.run_turn(TEXT_V1, agents=agents())
    r = pipeline.run_turn("more info", case_id="CASE-001", agents=agents(a1=a1_sloppy))
    assert r.error and r.error.startswith("A1 evidence: ValidationError") and not r.new_version


def test_failing_agent_gives_clear_error_and_saves_nothing(tmp_cases):
    def a3_broken(state, turn):
        raise LLMOutputError("A3", "output invalid after one retry: actions.0.owner: Field required", "{}", ["actions.0.owner"])

    r = pipeline.run_turn(TEXT_V1, agents=agents(a3=a3_broken))
    assert r.error.startswith("A3 actions: LLMOutputError") and not r.new_version
    assert "failed at step" in r.reply
    assert not list(tmp_cases.glob("CASE-*/state_v*.json"))


def test_close_turn_sets_closure():
    pipeline.run_turn(TEXT_V1, agents=agents())
    r = pipeline.run_turn("We can stop here, close the case", case_id="CASE-001", agents=agents())
    s = r.state
    assert "CLOSE" in r.intents and s.status == "closed" and s.version == 2
    assert s.closure.open_actions == ["ACT-001", "ACT-002"]
    assert s.closure.reopen_conditions and s.closure.remaining_risk.startswith("High")


def test_revise_loop_runs_target_once():
    calls = {"a3": 0, "a4": 0}

    def a3_counting(state, turn):
        calls["a3"] += 1
        return stubs.a3(state, turn)

    def a4_always_revise(state, turn):
        calls["a4"] += 1
        out = stubs.a4(state, turn)
        return A4Output(qa={"verdict": "REVISE", "issues": [{"target": "A3", "item_id": "ACT-002", "problem": "No CEO approval for remedy", "blocking": True}]},
                        outlook=out.outlook)

    r = pipeline.run_turn(TEXT_V1, agents=agents(a3=a3_counting, a4=a4_always_revise))
    assert r.error is None
    assert calls == {"a3": 2, "a4": 2}  # one revise, never a loop
    assert r.state.qa.verdict == "REVISE" and r.state.qa.issues[0].blocking  # unresolved -> QA notes
    assert "QA notes" in r.reply


def test_focus_only_turn_is_stored_and_applied_next_version():
    pipeline.run_turn(TEXT_V1, agents=agents())
    r = pipeline.run_turn("Focus on the legal side", case_id="CASE-001", agents=agents())
    assert r.intents == ["SET_FOCUS"] and not r.new_version
    r2 = pipeline.run_turn("New post from a retailer", case_id="CASE-001", agents=agents())
    assert r2.state.focus == "the legal side"
    assert r2.state.risk.level == "High"  # focus never changes the score


def test_registry_falls_back_to_stubs_until_real_modules_exist():
    a = pipeline.load_agents(use_stubs=False)
    for slot in ("a1", "a2", "a3", "a4", "a5", "render"):
        assert a.used[slot] in ("stub", f"{pipeline.REAL_AGENTS[slot][0]}.{pipeline.REAL_AGENTS[slot][1]}")
    assert a.used["classify"] == "llm"


def test_a5_narrative_warnings_reach_the_saved_state(tmp_cases):
    def a5_with_warnings(state, turn, prev):
        return A5Output(narrative={"executive_summary": "x", "situation": "y"}, changes_summary="z",
                        narrative_warnings=["situation: number 7,000 not found in the case data"])

    r = pipeline.run_turn(TEXT_V1, agents=agents(a5=a5_with_warnings))
    saved = CaseState.model_validate_json((tmp_cases / "CASE-001" / "state_v1.json").read_text(encoding="utf-8"))
    assert saved.report.narrative_warnings == ["situation: number 7,000 not found in the case data"]
    assert saved.report.narrative == {"executive_summary": "x", "situation": "y"}


def test_acme_stub_agents_forces_selected_slots(monkeypatch):
    monkeypatch.setenv("ACME_STUB_AGENTS", " A1, risk ,classify")
    a = pipeline.load_agents(use_stubs=False)
    assert a.a1 is stubs.a1 and a.used["a1"] == pipeline.FORCED_STUB_LABEL
    assert a.risk is stubs.risk and a.used["risk"] == pipeline.FORCED_STUB_LABEL
    assert a.classify is stubs.classify_intent and a.used["classify"] == pipeline.FORCED_STUB_LABEL
    assert a.used["answer"] == "llm"  # not listed -> real
    for slot in ("a2", "a3", "a4", "a5", "render"):  # not listed -> real module if it exists
        assert not a.used[slot].startswith("stub (")


def test_acme_stub_agents_unknown_name_is_ignored(monkeypatch, caplog):
    monkeypatch.setenv("ACME_STUB_AGENTS", "a1,a9")
    a = pipeline.load_agents(use_stubs=False)
    assert a.used["a1"] == pipeline.FORCED_STUB_LABEL
    assert "a9" in caplog.text


def test_forced_stub_runs_a_full_turn(monkeypatch):
    """With every slot forced, a turn runs end to end exactly like use_stubs=True."""
    monkeypatch.setenv("ACME_STUB_AGENTS", ",".join(pipeline.ALL_SLOTS))
    r = pipeline.run_turn(TEXT_V1, agents=pipeline.load_agents(use_stubs=False))
    assert r.error is None and r.version == 1
    assert set(r.agents_used.values()) == {pipeline.FORCED_STUB_LABEL}


def test_stub_intents():
    assert stubs.classify_intent("Why is the risk High?", False)["intents"] == ["QUESTION"]
    assert stubs.classify_intent("Why?", True)["intents"] == ["NEW_INFO"]
    assert "CLOSE" in stubs.classify_intent("ok, close the case", False)["intents"]
    assert stubs.classify_intent("A new article appeared", False)["intents"] == ["NEW_INFO"]
