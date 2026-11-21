"""Shared Claude wrapper used by every agent (A0 spec §4).

    from src.llm import call_structured, load_prompt, file_block

    out = call_structured(
        agent="A1",
        system_prompt=load_prompt("a1"),          # src/prompts/a1.md
        user_content=[file_block(path), {"type": "text", "text": state_json}],
        output_model=A1Output,                    # any Pydantic model
        effort="high",
        case_id=state.case_id,
    )

What it does for you:
  - system prompt = [common rules + knowledge base] (cached, identical for every agent)
                    + [your agent prompt] (cached per agent); your user_content goes last
  - structured output: the reply must match `output_model`'s JSON schema and is then
    validated with Pydantic (so contract validators such as score = S×L also run).
    On a validation error it retries ONCE, showing the model its reply and the errors.
  - model per agent (D-012): Sonnet 5.5 by default, Haiku 5.5 for A0*/A5* (see model_for)
  - adaptive thinking + per-agent `effort`; server-side refusal fallback where the model supports it
  - 429/5xx/overloaded/connection errors are retried by the SDK (max_retries=4)
  - every API call (including failed ones) is logged to cases/<case_id>/trace.jsonl
    with tokens, cache reads/writes and an estimated cost

Errors raised (all subclasses of LLMError, never a bare crash):
  LLMRefusal       the model declined (stop_reason "refusal")
  LLMTruncated     the reply hit max_tokens
  LLMOutputError   the reply still failed validation after the one retry
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import threading
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Literal, TypeVar

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from src.kb import ROOT, load_kb_block

T = TypeVar("T", bound=BaseModel)
Effort = Literal["low", "medium", "high", "xhigh", "max"]

# Hybrid setup (D-012): reasoning agents on the main model, simple calls on the light one.
# Override in .env with ACME_MODEL / ACME_MODEL_LIGHT.
DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_LIGHT_MODEL = "claude-haiku-5-5"
LIGHT_AGENT_PREFIXES = ("A0", "A5")  # A0 intent + answers, A5 report narrative
DEFAULT_MAX_TOKENS = 32_000  # includes thinking; streamed, so no HTTP timeout risk
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Models that accept the server-side refusal fallback (Haiku 5.5 does not).
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-opus-5", "claude-fable-5-2", "claude-fable-5-1"}
PROMPTS_DIR = ROOT / "src" / "prompts"

# USD per million tokens: (input, output, cache read). Cache write (5 min TTL) = 1.25 × input.
# Source: claude-api skill model table, 2026-11. Used for the trace estimate only.
PRICES: dict[str, tuple[float, float, float]] = {
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-opus-5": (5.00, 25.00, 0.50),
    "claude-opus-4-8": (5.00, 25.00, 0.50),
}

# Shared by every agent. Changing this text changes every agent's behaviour and
# invalidates the prompt cache: treat it like the contract (director review).
COMMON_RULES = """\
You are one agent in ACME's Corporate Crisis Manager, a multi-agent system that helps ACME \
assess an emerging incident and produces a versioned crisis management report.

Rules for every agent:
- The system drafts and recommends only. Never state or imply that a public statement was \
published, an authority was notified, a recall or hold was carried out, or a customer was \
contacted, unless a cited source says so.
- Ground every factual statement in the case state or the knowledge base below and cite \
source IDs (KB-01 ... KB-13 for company files, U-01, U-02, ... for evidence the user supplied).
- General domain knowledge (for example EU product-safety or GDPR duties) is allowed, but \
label it as general knowledge and never present it as an ACME fact.
- If the data does not support a conclusion, say what is unknown instead of guessing.
"""


class LLMError(RuntimeError):
    def __init__(self, agent: str, message: str):
        super().__init__(f"[{agent}] {message}")
        self.agent = agent


class LLMRefusal(LLMError):
    pass


class LLMTruncated(LLMError):
    pass


class LLMOutputError(LLMError):
    def __init__(self, agent: str, message: str, raw_text: str, problems: list[str]):
        super().__init__(agent, message)
        self.raw_text = raw_text
        self.problems = problems


# ---------------------------------------------------------------------------
# Client, prompts, content helpers
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_client() -> anthropic.Anthropic:
    load_dotenv(ROOT / ".env")
    return anthropic.Anthropic(max_retries=4)


def model_for(agent: str) -> str:
    """Main model for reasoning agents; light model for agents in LIGHT_AGENT_PREFIXES."""
    load_dotenv(ROOT / ".env")
    if agent.startswith(LIGHT_AGENT_PREFIXES):
        return os.environ.get("ACME_MODEL_LIGHT", DEFAULT_LIGHT_MODEL)
    return os.environ.get("ACME_MODEL", DEFAULT_MODEL)


def load_prompt(name: str) -> str:
    """Text of src/prompts/<name>.md (e.g. 'a1')."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def shared_system_text() -> str:
    """Common rules + KB. Byte-identical for every agent -> one shared cache entry."""
    return COMMON_RULES + "\n" + load_kb_block()


def file_block(path: str | Path) -> dict[str, Any]:
    """Content block for a user attachment: PDF -> document, PNG/JPG/GIF/WEBP -> image,
    anything else -> text (read as UTF-8)."""
    path = Path(path)
    mime = mimetypes.guess_type(path.name)[0] or ""
    if mime == "application/pdf":
        data = base64.standard_b64encode(path.read_bytes()).decode()
        return {"type": "document", "source": {"type": "base64", "media_type": mime, "data": data}, "title": path.name}
    if mime in ("image/png", "image/jpeg", "image/gif", "image/webp"):
        data = base64.standard_b64encode(path.read_bytes()).decode()
        return {"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}}
    return {"type": "text", "text": f"<file name=\"{path.name}\">\n{path.read_text(encoding='utf-8')}\n</file>"}


# ---------------------------------------------------------------------------
# Trace log
# ---------------------------------------------------------------------------

_trace_lock = threading.Lock()


def cases_dir() -> Path:
    load_dotenv(ROOT / ".env")
    d = Path(os.environ.get("ACME_CASES_DIR", "cases"))
    return d if d.is_absolute() else ROOT / d


def estimate_cost(model: str, usage: Any) -> float | None:
    price = PRICES.get(model)
    if price is None or usage is None:
        return None
    p_in, p_out, p_read = price
    cost = (
        (getattr(usage, "input_tokens", 0) or 0) * p_in
        + (getattr(usage, "cache_creation_input_tokens", 0) or 0) * p_in * 1.25
        + (getattr(usage, "cache_read_input_tokens", 0) or 0) * p_read
        + (getattr(usage, "output_tokens", 0) or 0) * p_out
    ) / 1_000_000
    return round(cost, 6)


def _trace(case_id: str | None, record: dict[str, Any]) -> None:
    path = cases_dir() / (case_id or "_dev") / "trace.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with _trace_lock, path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _usage_dict(usage: Any) -> dict[str, int]:
    keys = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
    return {k: (getattr(usage, k, 0) or 0) for k in keys} if usage is not None else {}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _problems_from(err: ValidationError) -> list[str]:
    out = []
    for e in err.errors(include_url=False):
        loc = ".".join(str(p) for p in e["loc"]) or "(root)"
        out.append(f"{loc}: {e['msg']}")
    return out


def call_structured(
    agent: str,
    system_prompt: str,
    user_content: str | list[dict[str, Any]],
    output_model: type[T],
    effort: Effort = "high",
    *,
    case_id: str | None = None,
    check: Callable[[T], list[str]] | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    model: str | None = None,
    client: anthropic.Anthropic | None = None,
) -> T:
    """One structured LLM call. Returns a validated `output_model` instance.

    agent          label for the trace, e.g. "A1", "A2b", "A0-intent"
    system_prompt  the agent's own instructions (keep it stable across calls: it is cached)
    user_content   the volatile part: state, turn, attachments (string or content blocks)
    effort         "low" for simple calls (intent, report narrative), "high" for analysis
    check          optional extra rules on the parsed output; return a list of problems
                   (e.g. unknown source IDs). Problems trigger the same single retry.
    model          override; by default model_for(agent) (A0*/A5* -> light model)
    """
    client = client or get_client()
    model = model or model_for(agent)
    fallback_args: dict[str, Any] = {"betas": [FALLBACK_BETA], "fallbacks": "default"} if model in FALLBACK_MODELS else {}
    schema = anthropic.transform_schema(output_model)
    system = [
        {"type": "text", "text": shared_system_text(), "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}},
    ]
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]

    for attempt in (1, 2):
        started = time.monotonic()
        record: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "case_id": case_id,
            "agent": agent,
            "attempt": attempt,
            "model_requested": model,
            "effort": effort,
        }
        try:
            with client.beta.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                thinking={"type": "adaptive"},
                output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
                **fallback_args,
            ) as stream:
                response = stream.get_final_message()
        except anthropic.APIError as e:
            record.update(ok=False, error=f"{type(e).__name__}: {e}", duration_s=round(time.monotonic() - started, 2))
            _trace(case_id, record)
            raise LLMError(agent, f"API call failed after SDK retries: {type(e).__name__}: {e}") from e

        usage = getattr(response, "usage", None)
        record.update(
            model=response.model,
            stop_reason=response.stop_reason,
            request_id=getattr(response, "_request_id", None),
            duration_s=round(time.monotonic() - started, 2),
            **_usage_dict(usage),
            cost_usd=estimate_cost(response.model, usage),
        )

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None)
            record.update(ok=False, error=f"refusal ({category})")
            _trace(case_id, record)
            raise LLMRefusal(agent, f"model declined the request (category: {category})")
        if response.stop_reason == "max_tokens":
            record.update(ok=False, error="max_tokens")
            _trace(case_id, record)
            raise LLMTruncated(agent, f"reply cut off at max_tokens={max_tokens}; raise max_tokens or shorten the input")

        raw = next((b.text for b in response.content if b.type == "text"), "")
        try:
            parsed = output_model.model_validate_json(raw)
            problems = check(parsed) if check else []
        except ValidationError as e:
            parsed, problems = None, _problems_from(e)

        record.update(ok=not problems, problems=problems or None)
        _trace(case_id, record)
        if not problems:
            return parsed  # type: ignore[return-value]

        if attempt == 2:
            raise LLMOutputError(agent, "output invalid after one retry: " + "; ".join(problems[:5]), raw, problems)
        # Retry once: keep the full assistant turn (thinking blocks included, unchanged) and
        # ask for a corrected complete JSON object.
        messages += [
            {"role": "assistant", "content": response.content},
            {
                "role": "user",
                "content": "Your JSON failed validation:\n- "
                + "\n- ".join(problems)
                + "\nReturn the complete corrected JSON object.",
            },
        ]
    raise AssertionError("unreachable")
