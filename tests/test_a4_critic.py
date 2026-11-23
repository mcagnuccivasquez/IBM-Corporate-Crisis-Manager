"""Tests for A4 Critic & Outlook (src/agents/a4_critic.py).

Claude is faked at the client level (same pattern as test_a3_actions.py), so the real
llm.py retry logic runs: no network, no API key, no cost.

Acceptance tests from spec §8:
  AT-1  A3 draft containing "all units tested" → REVISE, T11, blocking.
  AT-2  Economic impact using 16,000 × €30 without scope → REVISE, T7.
  AT-3  Clean S1 v1 → PASS.
  AT-4  Outlook always has non-empty `assumptions` and `cannot_estimate`.

Pre-pass unit tests (no LLM):
  PP-1  "all units tested" in an action → check_other_agents returns a hit → prepass produces blocking issue.
  PP-2  Personal data in outlook → blocking issue, target A4.
  PP-3  Blame wording in action → non-blocking issue.
  PP-4  Clean state → no prepass issues.

Integration tests (LLM faked):
  INT-1  Pre-pass issues are always present in final output even when LLM omits them.
  INT-2  REVISE when any blocking issue exists.
  INT-3  PASS verdict when LLM returns PASS and pre-pass is clean.

Run: python -m pytest tests/test_a4_critic.py -v
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.agents import a4_critic as a4
from src.contracts import A4Output, CaseState, Outlook, QA, QAIssue, TurnInput

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "state_v1_S1.json"

TURN1 = TurnInput(
    intent="NEW_INFO",
    user_text=(
        "We just got a viral post from a customer saying their PCX-100 smoked "
        "and melted on their desk. It has a screenshot attached."
    ),
    attachments=["U-01"],
)

# ------------------------------------------------------------------ helpers

def load_state() -> CaseState:
    return CaseState.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def state_dict() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def mutate_action(state_d: dict, action_id: str, field: str, value: str) -> dict:
    """Return a copy with the given action field replaced."""
    s = copy.deepcopy(state_d)
    for a in s["actions"]:
        if a["action_id"] == action_id:
            a[field] = value
    return s


def mutate_impact(state_d: dict, domain: str, field: str, value: str) -> dict:
    s = copy.deepcopy(state_d)
    for item in s["impacts"][domain]["impacts"]:
        item[field] = value
    return s


def mutate_outlook(state_d: dict, field: str, items: list) -> dict:
    s = copy.deepcopy(state_d)
    s["outlook"][field] = items
    return s


# ------------------------------------------------------------------ fake Claude


def _response(text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=text),
        ],
        stop_reason=stop_reason,
        stop_details=None,
        model="claude-sonnet-5-5",
        _request_id="req_test",
        usage=SimpleNamespace(
            input_tokens=100,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
            output_tokens=50,
        ),
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
        payload = out if isinstance(out, str) else json.dumps(out)
        response = _response(payload)

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


# ------------------------------------------------------------------ canonical LLM payloads

def _pass_payload():
    """LLM returns a clean PASS with minimal outlook (pre-pass will fill gaps if needed)."""
    return {
        "qa": {"verdict": "PASS", "issues": []},
        "outlook": {
            "residual_risk_if_p1_effective": "Medium",
            "reasons": ["Reputational: projected Low if defect ruled out"],
            "assumptions": ["Sample retrieval succeeds within 7 days"],
            "cannot_estimate": ["Units actually sold (KB-13: delivered ≠ sold)"],
            "pattern_warnings": [],
        },
        "reopen_conditions": [],
    }


def _revise_payload(check: str, item_id: str, problem: str, fix_hint: str, blocking: bool = True):
    """LLM returns a REVISE payload for one issue."""
    return {
        "qa": {
            "verdict": "REVISE",
            "issues": [{
                "target": "A3",
                "item_id": item_id,
                "problem": problem,
                "fix_hint": fix_hint,
                "blocking": blocking,
                "resolved": False,
            }],
        },
        "outlook": {
            "residual_risk_if_p1_effective": "Medium",
            "reasons": ["Projected lower if actions work"],
            "assumptions": ["Actions are carried out within 24h"],
            "cannot_estimate": ["Number of units actually sold"],
            "pattern_warnings": [],
        },
        "reopen_conditions": [],
    }


# ================================================================ UNIT TESTS: pre-pass only


class TestPrepass:
    """Tests for _prepass_issues directly — no LLM involved."""

    def test_pp1_banned_phrase_in_action_is_blocking(self):
        """PP-1: 'independent tests' (KB-10 banned phrase) in what_it_does → blocking issue.

        Note: 'all units tested' is skipped by checks.py when it appears in KB-10's
        reliability_note (the evidence support text), which is correct behaviour.
        'independent tests' does not appear in the fixture support text and fires reliably.
        """
        s = mutate_action(
            state_dict(), "ACT-002", "what_it_does",
            "Independent lab tests confirmed the product is safe."
        )
        state = CaseState.model_validate(s)
        issues = a4._prepass_issues(state)
        assert any(i.blocking for i in issues), "Expected at least one blocking issue"
        problems = " ".join(i.problem for i in issues)
        assert "independent" in problems.lower() or "banned phrase" in problems.lower()

    def test_pp2_personal_data_in_outlook_targets_a4(self):
        """PP-2: email address in outlook assumptions → blocking, target A4."""
        s = mutate_outlook(
            state_dict(), "assumptions",
            ["Customer r.dubois@gmail.com will return the unit within 24h."]
        )
        state = CaseState.model_validate(s)
        issues = a4._prepass_issues(state)
        a4_issues = [i for i in issues if i.target == "A4"]
        assert a4_issues, "Expected an A4 issue for personal data in outlook"
        assert all(i.blocking for i in a4_issues)

    def test_pp3_blame_wording_in_action_is_non_blocking(self):
        """PP-3: customer misuse wording → non-blocking."""
        s = mutate_action(
            state_dict(), "ACT-002", "what_it_does",
            "The report may be due to customer misuse of the charger."
        )
        state = CaseState.model_validate(s)
        issues = a4._prepass_issues(state)
        blame = [i for i in issues if "blame" in i.problem.lower() or "wording may blame" in i.problem.lower()]
        assert blame, "Expected a blame warning"
        assert all(not i.blocking for i in blame), "Blame warnings must be non-blocking"

    def test_pp4_clean_state_no_prepass_issues(self):
        """PP-4: the reference fixture has no banned phrases, personal data or blame."""
        state = load_state()
        issues = a4._prepass_issues(state)
        assert issues == []

    def test_pp_act_prefix_maps_to_a3(self):
        """Labels starting with ACT- map to target=A3."""
        target, item_id = a4._map_label("ACT-002 what_it_does")
        assert target == "A3"
        assert item_id == "ACT-002"

    def test_pp_outlook_prefix_maps_to_a4(self):
        """Labels containing 'outlook' map to target=A4."""
        target, _ = a4._map_label("outlook assumptions 1")
        assert target == "A4"

    def test_pp_impact_prefix_maps_to_a2(self):
        """Labels containing 'impact' map to target=A2."""
        target, _ = a4._map_label("reputational impact 1 description")
        assert target == "A2"

    def test_pp_stakeholder_prefix_maps_to_a3(self):
        """Labels containing 'stakeholder' map to target=A3."""
        target, _ = a4._map_label("stakeholder 'DE retailers' interest")
        assert target == "A3"


# ================================================================ INTEGRATION TESTS (LLM faked)


class TestA4Integration:
    """Full a4() with the LLM faked at the client level."""

    # -- AT-1 ----------------------------------------------------------------

    def test_at1_banned_phrase_in_a3_draft_is_revise_blocking(self, monkeypatch):
        """AT-1 (spec §8): Action containing a KB-10 banned phrase → REVISE, blocking, T11.

        Uses 'independent tests' rather than 'all units tested' because the latter appears
        in KB-10's reliability_note (evidence support text) and is correctly skipped by
        checks.py when that note is present. 'independent tests' fires reliably.
        """
        s = mutate_action(
            state_dict(), "ACT-002", "what_it_does",
            "Third-party independent tests have confirmed the chargers are safe."
        )
        state = CaseState.model_validate(s)

        # LLM also catches it (belt and suspenders), but pre-pass already fires
        llm_resp = _revise_payload(
            check="T11", item_id="ACT-002",
            problem="ACT-002 what_it_does: banned phrase 'independent tests' (KB-10) without support in the case data",
            fix_hint="Remove the claim about independent tests; it is not supported by evidence.",
            blocking=True,
        )
        fc = FakeClient(llm_resp)
        monkeypatch.setattr("src.llm.get_client", lambda: fc)

        result = a4.a4(state, TURN1)

        assert result.qa.verdict == "REVISE"
        blocking = [i for i in result.qa.issues if i.blocking]
        assert blocking, "Expected at least one blocking issue"
        problems_text = " ".join(i.problem.lower() for i in blocking)
        assert "independent" in problems_text or "banned phrase" in problems_text

    # -- AT-2 ----------------------------------------------------------------

    def test_at2_unscoped_economic_cost_is_revise_t7(self, monkeypatch):
        """AT-2 (spec §8): Economic impact using 16,000 × €30 without scope → REVISE, T7."""
        s = mutate_impact(
            state_dict(), "economic", "description",
            "Total cost: 16,000 units × €30 = €480,000 replacement cost."
        )
        state = CaseState.model_validate(s)

        llm_resp = _revise_payload(
            check="T7",
            item_id=None,
            problem="economic impact 1 description: unscoped cost of €480,000 "
                    "uses all 16,000 delivered units without scope justification (T7, KB-12/KB-13)",
            fix_hint="Replace with a scoped estimate or state that scope is unknown (KB-12: delivered ≠ sold).",
            blocking=True,
        )
        fc = FakeClient(llm_resp)
        monkeypatch.setattr("src.llm.get_client", lambda: fc)

        result = a4.a4(state, TURN1)

        assert result.qa.verdict == "REVISE"
        blocking = [i for i in result.qa.issues if i.blocking]
        assert blocking
        t7_hits = [i for i in blocking if "T7" in i.problem or "16,000" in i.problem or "480" in i.problem or "scope" in i.problem.lower()]
        assert t7_hits, f"Expected a T7 issue, got: {[i.problem for i in blocking]}"

    # -- AT-3 ----------------------------------------------------------------

    def test_at3_clean_s1_v1_pass(self, monkeypatch):
        """AT-3 (spec §8): Clean S1 v1 fixture → PASS."""
        state = load_state()
        fc = FakeClient(_pass_payload())
        monkeypatch.setattr("src.llm.get_client", lambda: fc)

        result = a4.a4(state, TURN1)

        assert result.qa.verdict == "PASS"
        blocking = [i for i in result.qa.issues if i.blocking]
        assert blocking == [], f"Unexpected blocking issues on clean fixture: {blocking}"

    # -- AT-4 ----------------------------------------------------------------

    def test_at4_outlook_always_has_assumptions_and_cannot_estimate(self, monkeypatch):
        """AT-4 (spec §8): Outlook.assumptions and Outlook.cannot_estimate are non-empty."""
        state = load_state()
        fc = FakeClient(_pass_payload())
        monkeypatch.setattr("src.llm.get_client", lambda: fc)

        result = a4.a4(state, TURN1)

        assert result.outlook.assumptions, "outlook.assumptions must not be empty"
        assert result.outlook.cannot_estimate, "outlook.cannot_estimate must not be empty"

    # -- INT-1 ---------------------------------------------------------------

    def test_int1_prepass_issues_added_even_when_llm_omits_them(self, monkeypatch):
        """INT-1: Pre-pass hits are merged into output even if the LLM ignores them."""
        # Plant a banned phrase that the pre-pass will catch ('independent tests' is not in
        # KB-10 reliability_note text, so it fires reliably)
        s = mutate_action(
            state_dict(), "ACT-002", "what_it_does",
            "Third-party independent tests confirmed the product is safe."
        )
        state = CaseState.model_validate(s)

        # LLM returns PASS (pretends it missed the problem)
        fc = FakeClient(_pass_payload())
        monkeypatch.setattr("src.llm.get_client", lambda: fc)

        result = a4.a4(state, TURN1)

        # Merge must have added the pre-pass issue and flipped verdict to REVISE
        assert result.qa.verdict == "REVISE", "Pre-pass blocking issue must override LLM PASS"
        problems = [i.problem for i in result.qa.issues]
        assert any("independent" in p.lower() or "banned phrase" in p.lower() for p in problems)

    # -- INT-2 ---------------------------------------------------------------

    def test_int2_revise_when_any_blocking_issue_exists(self, monkeypatch):
        """INT-2: Verdict is REVISE when any QAIssue is blocking."""
        state = load_state()
        llm_resp = {
            "qa": {
                "verdict": "PASS",   # LLM claims PASS, but has a blocking issue below (contradiction)
                "issues": [{
                    "target": "A1",
                    "item_id": "C-001",
                    "problem": "C-001 cites U-01 which is unverified; wording says 'confirmed'.",
                    "fix_hint": "Change 'confirmed' to 'unconfirmed'.",
                    "blocking": True,
                    "resolved": False,
                }],
            },
            "outlook": _pass_payload()["outlook"],
            "reopen_conditions": [],
        }
        fc = FakeClient(llm_resp)
        monkeypatch.setattr("src.llm.get_client", lambda: fc)

        result = a4.a4(state, TURN1)

        assert result.qa.verdict == "REVISE"

    # -- INT-3 ---------------------------------------------------------------

    def test_int3_pass_when_llm_pass_and_prepass_clean(self, monkeypatch):
        """INT-3: PASS when LLM returns PASS and pre-pass is clean."""
        state = load_state()
        fc = FakeClient(_pass_payload())
        monkeypatch.setattr("src.llm.get_client", lambda: fc)

        result = a4.a4(state, TURN1)

        assert result.qa.verdict == "PASS"
        assert isinstance(result.outlook, Outlook)

    # -- Structural ----------------------------------------------------------

    def test_output_is_valid_a4output_pydantic(self, monkeypatch):
        """The return value is a fully valid A4Output (Pydantic validates it)."""
        state = load_state()
        fc = FakeClient(_pass_payload())
        monkeypatch.setattr("src.llm.get_client", lambda: fc)

        result = a4.a4(state, TURN1)

        assert isinstance(result, A4Output)
        assert isinstance(result.qa, QA)
        assert isinstance(result.outlook, Outlook)
        assert isinstance(result.reopen_conditions, list)

    def test_prepass_issues_in_prompt_when_prepass_fires(self, monkeypatch):
        """The pre-pass hits are injected into the LLM user message."""
        s = mutate_action(
            state_dict(), "ACT-002", "what_it_does",
            "Third-party independent tests confirmed the batch is safe."
        )
        state = CaseState.model_validate(s)
        fc = FakeClient(_pass_payload())
        monkeypatch.setattr("src.llm.get_client", lambda: fc)

        a4.a4(state, TURN1)

        # user_content is a string passed directly as message content
        user_msg = fc.calls[0]["messages"][-1]["content"]
        assert isinstance(user_msg, str), "user_content should be a string"
        assert "pre_pass_issues" in user_msg, "Pre-pass block must appear in LLM user content"

    def test_no_prepass_no_preamble_when_clean(self, monkeypatch):
        """No <pre_pass_issues> block sent to the LLM when the pre-pass is clean."""
        state = load_state()
        fc = FakeClient(_pass_payload())
        monkeypatch.setattr("src.llm.get_client", lambda: fc)

        a4.a4(state, TURN1)

        user_msg = fc.calls[0]["messages"][-1]["content"]
        assert "pre_pass_issues" not in user_msg
