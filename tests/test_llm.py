"""llm.py with a fake Anthropic client: no network, no API key, no cost."""

import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, Field

from src import llm
from src.contracts import DomainImpact


class Out(BaseModel):
    summary: str
    source_ids: list[str] = Field(min_length=1)


def _response(text: str, stop_reason: str = "end_turn", model: str = "claude-opus-5-5"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category="cyber") if stop_reason == "refusal" else None,
        model=model,
        _request_id="req_test",
        usage=SimpleNamespace(input_tokens=100, cache_creation_input_tokens=0, cache_read_input_tokens=6000, output_tokens=50),
    )


class FakeClient:
    """Mimics client.beta.messages.stream(...) -> context manager -> get_final_message()."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        # snapshot messages: llm.py appends to the same list on retry
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        response = self.responses.pop(0)

        class _Ctx:
            def __enter__(self_inner):
                return SimpleNamespace(get_final_message=lambda: response)

            def __exit__(self_inner, *exc):
                return False

        return _Ctx()


@pytest.fixture(autouse=True)
def tmp_cases(tmp_path, monkeypatch):
    monkeypatch.setenv("ACME_CASES_DIR", str(tmp_path))
    monkeypatch.setenv("ACME_MODEL", "claude-opus-5-5")
    return tmp_path


def _trace(tmp_cases, case_id="CASE-001"):
    lines = (tmp_cases / case_id / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


GOOD = json.dumps({"summary": "ok", "source_ids": ["KB-01"]})
BAD = json.dumps({"summary": "ok", "source_ids": []})


def test_success_request_shape_and_trace(tmp_cases):
    client = FakeClient(_response(GOOD))
    out = llm.call_structured("A1", "Agent prompt", "state...", Out, "high", case_id="CASE-001", client=client)
    assert out == Out(summary="ok", source_ids=["KB-01"])

    req = client.calls[0]
    assert req["model"] == "claude-opus-5-5"
    assert req["thinking"] == {"type": "adaptive"}
    assert req["output_config"]["effort"] == "high"
    assert req["output_config"]["format"]["type"] == "json_schema"
    assert req["fallbacks"] == "default" and req["betas"] == [llm.FALLBACK_BETA]
    # cache layout: [rules + KB] then [agent prompt], both cached; volatile content in messages
    kb_block, agent_block = req["system"]
    assert '<document source_id="KB-13">' in kb_block["text"] and kb_block["cache_control"]
    assert agent_block == {"type": "text", "text": "Agent prompt", "cache_control": {"type": "ephemeral"}}
    assert req["messages"] == [{"role": "user", "content": "state..."}]

    (rec,) = _trace(tmp_cases)
    assert rec["agent"] == "A1" and rec["ok"] is True
    assert rec["cache_read_input_tokens"] == 6000 and rec["cost_usd"] > 0


def test_kb_prefix_identical_across_agents():
    c1, c2 = FakeClient(_response(GOOD)), FakeClient(_response(GOOD))
    llm.call_structured("A1", "prompt one", "x", Out, "high", client=c1)
    llm.call_structured("A4", "prompt two", "y", Out, "low", client=c2)
    assert c1.calls[0]["system"][0] == c2.calls[0]["system"][0]


def test_validation_error_retries_once_with_feedback(tmp_cases):
    client = FakeClient(_response(BAD), _response(GOOD))
    out = llm.call_structured("A3", "p", "x", Out, case_id="CASE-001", client=client)
    assert out.source_ids == ["KB-01"]
    retry_msgs = client.calls[1]["messages"]
    assert retry_msgs[1]["role"] == "assistant"
    assert len(retry_msgs[1]["content"]) == 2  # thinking block passed back unchanged
    assert "source_ids" in retry_msgs[2]["content"]
    assert [r["ok"] for r in _trace(tmp_cases)] == [False, True]


def test_still_invalid_after_retry_raises_clear_error():
    client = FakeClient(_response(BAD), _response(BAD))
    with pytest.raises(llm.LLMOutputError) as exc:
        llm.call_structured("A3", "p", "x", Out, client=client)
    assert "source_ids" in str(exc.value) and exc.value.raw_text == BAD
    assert len(client.calls) == 2


def test_contract_validators_trigger_retry():
    bad = {"severity": 3, "likelihood": 2, "score": 9, "severity_reason": "s", "likelihood_reason": "l", "evidence_confidence": "low"}
    good = {**bad, "score": 6}
    client = FakeClient(_response(json.dumps(bad)), _response(json.dumps(good)))
    out = llm.call_structured("A2a", "p", "x", DomainImpact, client=client)
    assert out.score == 6 and len(client.calls) == 2


def test_check_callback_problems_trigger_retry():
    client = FakeClient(_response(json.dumps({"summary": "s", "source_ids": ["KB-99"]})), _response(GOOD))
    check = lambda o: [f"unknown source {i}" for i in o.source_ids if i == "KB-99"]  # noqa: E731
    out = llm.call_structured("A1", "p", "x", Out, check=check, client=client)
    assert out.source_ids == ["KB-01"]
    assert "KB-99" in client.calls[1]["messages"][2]["content"]


def test_refusal_is_not_retried(tmp_cases):
    client = FakeClient(_response("", stop_reason="refusal"))
    with pytest.raises(llm.LLMRefusal, match="cyber"):
        llm.call_structured("A1", "p", "x", Out, case_id="CASE-001", client=client)
    assert len(client.calls) == 1
    assert _trace(tmp_cases)[0]["error"].startswith("refusal")


def test_max_tokens_raises_truncated():
    client = FakeClient(_response('{"summary": "cut', stop_reason="max_tokens"))
    with pytest.raises(llm.LLMTruncated):
        llm.call_structured("A5", "p", "x", Out, client=client)


def test_file_block_types(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "b.png").write_bytes(b"\x89PNG")
    (tmp_path / "c.txt").write_text("hello", encoding="utf-8")
    assert llm.file_block(tmp_path / "a.pdf")["type"] == "document"
    assert llm.file_block(tmp_path / "b.png")["source"]["media_type"] == "image/png"
    assert "hello" in llm.file_block(tmp_path / "c.txt")["text"]


def test_cost_estimate_uses_cache_prices():
    usage = SimpleNamespace(input_tokens=1_000_000, cache_creation_input_tokens=0, cache_read_input_tokens=1_000_000, output_tokens=0)
    assert llm.estimate_cost("claude-opus-5-5", usage) == pytest.approx(4.20)
    assert llm.estimate_cost("unknown-model", usage) is None
