"""Tests for the A5 narrative step (src/agents/a5_report.py). Uses a fake Claude client:
no API key needed, no cost.

Run: .venv/bin/python -m pytest tests/test_a5_narrative.py -v
"""

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agents import a5_report  # noqa: E402
from src.report import render  # noqa: E402

SAMPLE = ROOT / "src" / "report" / "sample_state_v1_TEMPORARY.json"

GOOD = {
    "executive_summary": "An unconfirmed post reports smoke from a PCX-100 [C-001, U-01]. Risk is High (floor F1).",
    "situation": "11,000 units are in channels and 5,000 in the Frankfurt warehouse [C-002, KB-13].",
    "changes_summary": None,
    "closure_summary": None,
}


class FakeClient:
    """Returns the queued narratives in order; records every call."""

    def __init__(self, *outputs, stop_reason="end_turn"):
        self.outputs = list(outputs)
        self.calls = []
        self.stop_reason = stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        parsed = a5_report.Narrative(**out) if self.stop_reason != "refusal" else None
        return SimpleNamespace(stop_reason=self.stop_reason, parsed_output=parsed)


@pytest.fixture
def state():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- number check

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


def test_previous_narrative_is_not_a_valid_source(state):
    s = copy.deepcopy(state)
    s["report"]["narrative"]["situation"] = "There were 777 reports."
    text = dict(GOOD, situation="There were 777 reports.")
    assert a5_report.find_unsupported_numbers(text, s) == {"situation": ["777"]}


# ---------------------------------------------------------------- citations, phrases, personal data

def test_unknown_citation_is_caught(state):
    text = dict(GOOD, situation="Smoke was reported [C-899, U-01].")
    assert a5_report.find_unknown_ids(text, state) == {"situation": ["C-899"]}


def test_known_citations_pass(state):
    assert a5_report.find_unknown_ids(GOOD, state) == {}


@pytest.mark.parametrize("sentence", [
    "ACME has contacted the authorities.",
    "The authorities have been notified [C-001].",
    "Independent tests are under way.",
    "All units were tested in July.",
    "A remote firmware update will fix the PCX-100 charger.",
    "A password change proves no recording was viewed.",
])
def test_banned_phrases_are_caught(state, sentence):
    assert a5_report.find_banned_phrases(dict(GOOD, situation=sentence), state)


@pytest.mark.parametrize("sentence", [
    "The PCX-100 has no remote fix.",
    "ACME has not contacted the authorities.",
    "The system does not claim that all units were tested.",
    "A remote update for the SafeCam app is planned.",  # rule is PCX-100 specific (KB-03)
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


def test_soft_problems_do_not_trigger_retry(state):
    client = FakeClient(dict(GOOD, executive_summary="Risk is Critical [C-001]."))
    _, warnings = a5_report.write_narrative(state, client)
    assert len(client.calls) == 1
    assert "Critical" in warnings[0] and "false alarm" in warnings[0]


def test_hard_problems_share_one_retry(state):
    bad = dict(GOOD, situation="12,500 units [C-899]. Contact @someone.")
    client = FakeClient(bad, GOOD)
    narrative, warnings = a5_report.write_narrative(state, client)
    assert len(client.calls) == 2
    feedback = client.calls[1]["messages"][0]["content"]
    assert "12,500" in feedback and "C-899" in feedback and "@someone" in feedback
    assert narrative == GOOD and warnings == []


# ---------------------------------------------------------------- word limits

def test_word_limit_only_warns():
    long = dict(GOOD, executive_summary="word " * 81)
    assert a5_report.check_word_limits(long) == ["executive_summary has 81 words (limit 80)"]


# ---------------------------------------------------------------- retry behaviour

def test_good_narrative_one_call_no_warnings(state):
    client = FakeClient(GOOD)
    narrative, warnings = a5_report.write_narrative(state, client)
    assert narrative["situation"] == GOOD["situation"]
    assert warnings == []
    assert len(client.calls) == 1


def test_bad_number_retries_once_and_succeeds(state):
    client = FakeClient(dict(GOOD, situation="12,500 units [C-002]."), GOOD)
    narrative, warnings = a5_report.write_narrative(state, client)
    assert len(client.calls) == 2
    assert "12,500" in client.calls[1]["messages"][0]["content"]  # feedback names the bad number
    assert narrative == GOOD and warnings == []


def test_bad_number_twice_is_flagged_not_dropped(state):
    bad = dict(GOOD, situation="12,500 units [C-002].")
    client = FakeClient(bad, bad)
    narrative, warnings = a5_report.write_narrative(state, client)
    assert len(client.calls) == 2  # only one retry
    assert narrative["situation"] == bad["situation"]
    assert warnings == ["situation: numbers not found in the case data: 12,500"]


def test_long_text_does_not_trigger_retry(state):
    client = FakeClient(dict(GOOD, executive_summary="word " * 90))
    _, warnings = a5_report.write_narrative(state, client)
    assert len(client.calls) == 1
    assert warnings == ["executive_summary has 90 words (limit 80)"]


# ---------------------------------------------------------------- failure behaviour

def test_api_failure_still_returns_placeholder(state):
    client = FakeClient(ConnectionError("no internet"))
    narrative, warnings = a5_report.write_narrative(state, client)
    assert narrative["situation"] == a5_report.FAILED_TEXT
    assert narrative["changes_summary"] is None  # v1 has no change summary
    assert warnings[0].startswith("AI step failed: ConnectionError")


def test_refusal_counts_as_failure(state):
    client = FakeClient(GOOD, stop_reason="refusal")
    narrative, warnings = a5_report.write_narrative(state, client)
    assert narrative["executive_summary"] == a5_report.FAILED_TEXT
    assert "refusal" in warnings[0]


# ---------------------------------------------------------------- request shape

def test_request_uses_agreed_settings(state):
    client = FakeClient(GOOD)
    a5_report.write_narrative(state, client)
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"] == {"effort": "low"}
    assert call["output_format"] is a5_report.Narrative
    assert "Use only information in the case state" in call["system"]
    assert '"report"' not in call["messages"][0]["content"]  # old narrative not sent


# ---------------------------------------------------------------- end to end (PDF)

def test_run_writes_pdf_and_does_not_modify_input(state, tmp_path):
    before = copy.deepcopy(state)
    result = a5_report.run(state, cases_dir=tmp_path, client=FakeClient(GOOD))
    assert state == before
    assert Path(result["pdf_path"]).read_bytes()[:5] == b"%PDF-"
    assert result["narrative_warnings"] == []


def test_warnings_are_printed_in_appendix_c(state):
    s = copy.deepcopy(state)
    s["report"]["narrative_warnings"] = ["situation: numbers not found in the case state: 12,500"]
    assert "numbers not found in the case state: 12,500" in render.render_html(s)
    s["report"]["narrative_warnings"] = []
    assert "No issues found in the narrative checks" in render.render_html(s)
    del s["report"]["narrative_warnings"]
    assert "Narrative checks not run" in render.render_html(s)
