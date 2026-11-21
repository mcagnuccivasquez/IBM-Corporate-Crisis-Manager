"""Tests for the A5 narrative step (src/agents/a5_report.py).

Claude is faked at the client level (same pattern as tests/test_llm.py), so these tests
go through the real src/llm.py retry logic: no network, no API key, no cost.
The case data is tests/fixtures/a5_sample_state_v1.json: ACME facts verified against the
KB files; scores, actions and narrative are hand-written placeholders, NOT agent results.

Run: python -m pytest tests/test_a5_narrative.py -v
"""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import pipeline
from src.agents import a5_report
from src.contracts import A5Output, CaseState
from src.report import render

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests" / "fixtures" / "a5_sample_state_v1.json"

GOOD = {
    "executive_summary": "An unconfirmed post reports smoke from a PCX-100 [C-001, U-01]. Risk is High (floor F1).",
    "situation": "11,000 units are in channels and 5,000 in the Frankfurt warehouse [C-002, KB-13].",
}
NO_ISSUES = {"issues": []}  # fact-check answer: every sentence matches the case data


# ---------------------------------------------------------------- fake Claude (client level)

def _response(text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category="cyber") if stop_reason == "refusal" else None,
        model="claude-haiku-5-5",
        _request_id="req_test",
        usage=SimpleNamespace(input_tokens=100, cache_creation_input_tokens=0, cache_read_input_tokens=0, output_tokens=50),
    )


class FakeClient:
    """Mimics client.beta.messages.stream(...); each queued item is a narrative dict,
    a raw string, a ready response, or an exception to raise."""

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        response = out if isinstance(out, SimpleNamespace) else _response(out if isinstance(out, str) else json.dumps(out))

        class _Ctx:
            def __enter__(self_inner):
                return SimpleNamespace(get_final_message=lambda: response)

            def __exit__(self_inner, *exc):
                return False

        return _Ctx()


@pytest.fixture(autouse=True)
def tmp_cases(tmp_path, monkeypatch):
    monkeypatch.setenv("ACME_CASES_DIR", str(tmp_path))
    monkeypatch.setenv("ACME_MODEL_LIGHT", "claude-haiku-5-5")
    return tmp_path


@pytest.fixture
def state():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


@pytest.fixture
def case_state(state):
    return CaseState.model_validate(state)


def _retry_feedback(client) -> str:
    return client.calls[1]["messages"][-1]["content"]


# ---------------------------------------------------------------- hard check 1: numbers

def test_numbers_from_state_are_accepted(state):
    assert a5_report.find_unsupported_numbers(GOOD, state) == {}


def test_invented_number_is_caught(state):
    bad = dict(GOOD, situation="12,500 units are in channels [C-002].")
    assert a5_report.find_unsupported_numbers(bad, state) == {"situation": ["12,500"]}


def test_numbers_inside_citations_are_ignored(state):
    text = dict(GOOD, situation="See the post [C-999, U-77].")
    assert a5_report.find_unsupported_numbers(text, state) == {}


def test_thousands_separator_does_not_matter(state):
    text = dict(GOOD, situation="11000 units are in channels.")
    assert a5_report.find_unsupported_numbers(text, state) == {}


@pytest.mark.parametrize("words, ok", [
    ("eleven thousand units are in channels", True),       # 11000 is in the data
    ("five thousand units are in the warehouse", True),    # 5000
    ("twelve thousand five hundred units", False),          # 12500 is not
    ("three dozen retailers", False),                       # 36 is not
    ("a dozen retailers", True),                            # 12 passes: "KB-12" contains it (known limit)
    ("one of the reports", True),                           # 1 appears in the data
])
def test_numbers_written_as_words(state, words, ok):
    problems = a5_report.find_unsupported_numbers(dict(GOOD, situation=words), state)
    assert (problems == {}) is ok, problems


def test_previous_narrative_is_not_a_valid_source(state):
    s = copy.deepcopy(state)
    s["report"]["narrative"]["situation"] = "There were 777 reports."
    text = dict(GOOD, situation="There were 777 reports.")
    assert a5_report.find_unsupported_numbers(text, s) == {"situation": ["777"]}


# ---------------------------------------------------------------- hard checks 2-4

def test_unknown_citation_is_caught(state):
    text = dict(GOOD, situation="Smoke was reported [C-899, U-01].")
    assert a5_report.find_unknown_ids(text, state) == {"situation": ["C-899"]}


def test_known_citations_pass(state):
    assert a5_report.find_unknown_ids(GOOD, state) == {}


def test_id_mentioned_in_case_data_may_be_cited(state):
    text = dict(GOOD, situation="The #4471 cable explanation does not apply [KB-06].")
    assert a5_report.find_unknown_ids(text, state) == {"situation": ["KB-06"]}  # not in this case's data
    s = copy.deepcopy(state)
    s["outlook"]["pattern_warnings"].append("Do not reuse the #4471 cable explanation (KB-06)")
    assert a5_report.find_unknown_ids(text, s) == {}  # now the case data mentions it


@pytest.mark.parametrize("sentence", [
    "ACME has contacted the authorities.",
    "The authorities have been notified [C-001].",
    "Independent tests are under way.",
    "All units were tested in July.",
    "A remote firmware update will fix the PCX-100 charger.",
    "A password change proves no recording was viewed.",
    # paraphrases (session 2)
    "The regulator was informed on Friday.",
    "ACME reported the incident to the market surveillance authority.",
    "A notification was sent to the agency.",
    "Third-party testing is under way.",
    "Every unit has been checked.",
    "ACME tested all chargers.",
    "A software update for the PCX-100 charger will solve it.",
    "No recording was viewed.",
])
def test_banned_phrases_are_caught(state, sentence):
    assert a5_report.find_banned_phrases(dict(GOOD, situation=sentence), state)


@pytest.mark.parametrize("sentence", [
    "The PCX-100 has no remote fix.",
    "ACME has not contacted the authorities.",
    "The system does not claim that all units were tested.",
    "A remote update for the SafeCam app is planned.",  # rule is PCX-100 specific (KB-03)
    "Legal will assess whether a notification to the authorities is required.",
    "We cannot say that no recording was viewed.",
])
def test_negated_or_out_of_scope_phrases_pass(state, sentence):
    assert a5_report.find_banned_phrases(dict(GOOD, situation=sentence), state) == []


def test_banned_phrase_allowed_when_case_data_says_so(state):
    s = copy.deepcopy(state)
    s["claims"][0]["text"] = "ACME has notified the authorities on 22 Nov"
    assert a5_report.find_banned_phrases(dict(GOOD, situation="ACME has notified the authorities."), s) == []


def test_personal_data_is_caught():
    text = dict(GOOD, situation="Posted by @charger_fan, contact jane.doe@mail.com or +49 170 1234567.")
    problems = a5_report.find_personal_data(text)
    assert problems and all(x in problems[0] for x in ("@charger_fan", "jane.doe@mail.com", "+49 170 1234567"))


def test_dates_and_batches_are_not_personal_data():
    text = dict(GOOD, situation="Batch PCX-2609-A, export of 2026-10-22, 11,000 units.")
    assert a5_report.find_personal_data(text) == []


@pytest.mark.parametrize("sentence, found", [
    ("The account of R. Dubois was reviewed.", "R. Dubois"),   # the KB-09 customer
    ("Ms Dubois asked about recordings.", "Ms Dubois"),
    ("Dr. Martin Weiss sent the unit.", "Dr. Martin Weiss"),
])
def test_customer_names_are_caught(sentence, found):
    problems = a5_report.find_personal_data(dict(GOOD, situation=sentence))
    assert problems and found in problems[0]


@pytest.mark.parametrize("sentence", [
    "Owner: Tom Weber. Approver: E. Rossi.",          # ACME staff (KB-02) are not personal data
    "Contact tom.weber@acme.example for returns.",     # ACME's own address
    "Option A. Then hold both batches.",               # sentence boundary, not a name
])
def test_staff_and_sentence_starts_are_not_flagged(sentence):
    assert a5_report.find_personal_data(dict(GOOD, situation=sentence)) == []


# ---------------------------------------------------------------- soft checks

def test_overstated_unconfirmed_claim_is_flagged(state):
    text = dict(GOOD, situation="The smoke incident is confirmed [C-001, U-01].")
    problems = a5_report.find_overstated_claims(text, state)
    assert problems and "C-001" in problems[0] and "unconfirmed" in problems[0]


def test_negated_confirmation_passes(state):
    text = dict(GOOD, situation="The smoke report is not confirmed [C-001]. It remains unconfirmed [C-001].")
    assert a5_report.find_overstated_claims(text, state) == []


def test_confirmed_claim_may_be_called_confirmed(state):
    text = dict(GOOD, situation="The stock figures are confirmed [C-002].")
    assert a5_report.find_overstated_claims(text, state) == []


def test_unknown_risk_level_is_flagged(state):
    text = dict(GOOD, executive_summary="Risk is Critical [C-001].")
    assert "Critical" in a5_report.find_unknown_risk_levels(text, state)[0]
    assert a5_report.find_unknown_risk_levels(GOOD, state) == []  # "High" is in the data
    lower = dict(GOOD, situation="It reached a high temperature.")
    assert a5_report.find_unknown_risk_levels(lower, state) == []  # lower-case is not a risk level


@pytest.mark.parametrize("sentence, flagged", [
    ("The damage was caused by customer misuse.", True),
    ("The charger was improperly used.", True),
    ("There is no evidence of misuse.", False),
    ("The customer reported smoke.", False),
])
def test_blame_wording_is_a_soft_warning(sentence, flagged):
    problems = a5_report.find_blame(dict(GOOD, situation=sentence))
    assert bool(problems) is flagged
    if flagged:
        assert "false alarm" in problems[0]


def test_word_limit_only_warns():
    long = dict(GOOD, executive_summary="word " * 81)
    assert a5_report.check_word_limits(long) == ["executive_summary has 81 words (limit 80)"]


# ---------------------------------------------------------------- retry behaviour (through llm.py)

def test_good_narrative_one_call_no_warnings(state):
    client = FakeClient(GOOD)
    narrative, warnings = a5_report.write_narrative(state, client=client, run_fact_check=False)
    assert narrative == GOOD and warnings == [] and len(client.calls) == 1


def test_bad_number_retries_once_and_succeeds(state):
    client = FakeClient(dict(GOOD, situation="12,500 units [C-002]."), GOOD)
    narrative, warnings = a5_report.write_narrative(state, client=client, run_fact_check=False)
    assert len(client.calls) == 2
    assert "12,500" in _retry_feedback(client)  # the retry tells the model what was wrong
    assert narrative == GOOD and warnings == []


def test_bad_number_twice_is_flagged_not_dropped(state):
    bad = dict(GOOD, situation="12,500 units [C-002].")
    client = FakeClient(bad, bad)
    narrative, warnings = a5_report.write_narrative(state, client=client, run_fact_check=False)
    assert len(client.calls) == 2  # only one retry
    assert narrative["situation"] == bad["situation"]
    assert warnings == ["situation: numbers not found in the case data: 12,500"]


def test_hard_problems_share_one_retry(state):
    client = FakeClient(dict(GOOD, situation="12,500 units [C-899]. Contact @someone."), GOOD)
    narrative, warnings = a5_report.write_narrative(state, client=client, run_fact_check=False)
    assert len(client.calls) == 2
    feedback = _retry_feedback(client)
    assert "12,500" in feedback and "C-899" in feedback and "@someone" in feedback
    assert narrative == GOOD and warnings == []


def test_soft_problems_do_not_trigger_retry(state):
    client = FakeClient(dict(GOOD, executive_summary="Risk is Critical [C-001]."))
    _, warnings = a5_report.write_narrative(state, client=client, run_fact_check=False)
    assert len(client.calls) == 1
    assert "Critical" in warnings[0] and "false alarm" in warnings[0]


def test_long_text_does_not_trigger_retry(state):
    client = FakeClient(dict(GOOD, executive_summary="word " * 90))
    _, warnings = a5_report.write_narrative(state, client=client, run_fact_check=False)
    assert len(client.calls) == 1
    assert warnings == ["executive_summary has 90 words (limit 80)"]


def test_empty_keys_are_dropped(state):
    client = FakeClient(dict(GOOD, changes_summary=None, closure_summary="  "))
    narrative, _ = a5_report.write_narrative(state, client=client, run_fact_check=False)
    assert set(narrative) == {"executive_summary", "situation"}


# ---------------------------------------------------------------- failure behaviour

def test_api_failure_gives_placeholder(state):
    import anthropic
    import httpx2  # the HTTP library used by anthropic 2.x
    err = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com"))
    narrative, warnings = a5_report.write_narrative(state, client=FakeClient(err))
    assert narrative == {"executive_summary": a5_report.FAILED_TEXT, "situation": a5_report.FAILED_TEXT}
    assert warnings[0].startswith("AI step failed")


def test_refusal_counts_as_failure(state):
    narrative, warnings = a5_report.write_narrative(state, client=FakeClient(_response("", "refusal")))
    assert narrative["executive_summary"] == a5_report.FAILED_TEXT
    assert "declined" in warnings[0]


def test_invalid_json_twice_counts_as_failure(state):
    narrative, warnings = a5_report.write_narrative(state, client=FakeClient("not json", "still not json"))
    assert narrative["situation"] == a5_report.FAILED_TEXT
    assert warnings[0].startswith("AI step failed: output invalid after one retry")


def test_failure_on_v2_and_closed_case_fills_those_sections(state):
    s = copy.deepcopy(state)
    s["version"], s["status"] = 2, "closed"
    narrative, _ = a5_report.write_narrative(s, client=FakeClient("not json", "still not json"))
    assert narrative["changes_summary"] == narrative["closure_summary"] == a5_report.FAILED_TEXT


# ---------------------------------------------------------------- AI fact-check pass

def test_fact_check_issues_become_warnings_without_retry(state):
    issue = {"field": "situation", "sentence": "5,000 units are in shops.",
             "issue": "5,000 is the Frankfurt warehouse stock, not units in shops"}
    client = FakeClient(dict(GOOD, situation="5,000 units are in shops."), {"issues": [issue]})
    narrative, warnings = a5_report.write_narrative(state, client=client)
    assert len(client.calls) == 2  # narrative + fact-check, no retry
    assert narrative["situation"] == "5,000 units are in shops."  # text kept, never rewritten
    assert warnings == ['situation: 5,000 is the Frankfurt warehouse stock, not units in shops: '
                        '"5,000 units are in shops."' + a5_report.FACT_CHECK_SUFFIX]


def test_fact_check_request(state):
    client = FakeClient(GOOD, NO_ISSUES)
    a5_report.write_narrative(state, client=client)
    call = client.calls[1]
    assert call["model"] == "claude-haiku-5-5" and call["output_config"]["effort"] == "low"
    assert "You do not rewrite anything" in call["system"][1]["text"]
    user = call["messages"][0]["content"]
    assert "Narrative to check" in user and GOOD["situation"] in user


def test_fact_check_failure_is_reported_not_hidden(state):
    narrative, warnings = a5_report.write_narrative(state, client=FakeClient(GOOD, "not json", "still not json"))
    assert narrative == GOOD
    assert warnings[0].startswith("AI fact-check not run")


def test_no_fact_check_when_narrative_failed(state):
    client = FakeClient(_response("", "refusal"))
    a5_report.write_narrative(state, client=client)
    assert len(client.calls) == 1


# ---------------------------------------------------------------- request shape

def test_request_uses_agreed_settings(state):
    client = FakeClient(GOOD)
    a5_report.write_narrative(state, client=client, run_fact_check=False)
    call = client.calls[0]
    assert call["model"] == "claude-haiku-5-5"  # D-012: A5 runs on the light model
    assert call["output_config"]["effort"] == "low"
    assert "Use only information in the case state" in call["system"][1]["text"]
    user = call["messages"][0]["content"]
    assert '"claims"' in user and '"report"' not in user  # old narrative is not sent


# ---------------------------------------------------------------- pipeline interface

def test_run_returns_a5output_and_writes_no_files(case_state, tmp_cases):
    before = case_state.model_copy(deep=True)
    out = a5_report.run(case_state, None, None, client=FakeClient(dict(GOOD, changes_summary="Risk stays High [C-001]."), NO_ISSUES))
    assert isinstance(out, A5Output)
    assert out.narrative["situation"] == GOOD["situation"]
    assert out.changes_summary == "Risk stays High [C-001]."
    assert out.narrative_warnings == []
    assert case_state == before
    assert not list(tmp_cases.rglob("*.pdf"))


def test_pipeline_picks_up_real_a5_and_renderer():
    used = pipeline.load_agents(use_stubs=False).used
    assert used["a5"] == "src.agents.a5_report.run"
    assert used["render"] == "src.report.render.render_pdf"


def test_pipeline_turn_with_real_a5_and_renderer(tmp_cases):
    """Full A0 turn on stub agents, but with the real A5 (fake Claude) and the real renderer."""
    a = pipeline.load_agents(use_stubs=True)
    client = FakeClient({"executive_summary": "Summary of the case.", "situation": "Situation of the case."}, NO_ISSUES)
    a.a5 = lambda s, t, p: a5_report.run(s, t, p, client=client)
    a.render = render.render_pdf
    r = pipeline.run_turn("Customers in Germany report PCX-100 chargers getting hot", agents=a)
    assert r.error is None and r.version == 1
    state = CaseState.model_validate_json((tmp_cases / r.case_id / "state_v1.json").read_text(encoding="utf-8"))
    assert state.report.narrative == {"executive_summary": "Summary of the case.", "situation": "Situation of the case."}
    assert state.report.narrative_warnings == []
    pdf = tmp_cases / r.case_id / "report_v1.pdf"
    assert pdf.read_bytes()[:5] == b"%PDF-"
