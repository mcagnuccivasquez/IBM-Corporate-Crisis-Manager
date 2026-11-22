"""A0 Case Orchestrator: runs one user turn end to end (A0 spec §3).

    from src.pipeline import run_turn
    result = run_turn("Here is a screenshot of a post...", attachments=[path])           # new case
    result = run_turn("Why is the risk High?", case_id=result.case_id)                   # QUESTION
    print(result.reply, result.pdf_path)

CLI (stubs, no API key needed):
    python -m src.pipeline --stubs --text "Customers report hot PCX-100 chargers"
    python -m src.pipeline --stubs --case CASE-001 --text "Why is the risk High?"

Agents are looked up in a registry (AgentSet): a teammate's real module is used as
soon as it exists (e.g. src/agents/a1_evidence.py with `run`), otherwise a stub that
returns fixture JSON. `--stubs` / use_stubs=True forces stubs everywhere;
ACME_STUB_AGENTS=a1,a3 in .env forces stubs for just those agents (e.g. one not ready yet).

Storage: cases/<case_id>/state_vN.json + report_vN.pdf (immutable per version),
inputs/ (uploaded files), case_meta.json (focus between versions), trace.jsonl (llm.py).
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from src.agents import stubs
from src.contracts import (
    QA,
    A1Output,
    A3Output,
    A4Output,
    A5Output,
    CaseState,
    Closure,
    Domain,
    DomainImpact,
    Intent,
    QAIssue,
    Report,
    Risk,
    TurnInput,
    new_case,
)
from src.diff import build_changelog_entry
from src.kb import ROOT
from src.llm import call_structured, cases_dir, load_prompt

log = logging.getLogger("acme.pipeline")

DOMAINS: tuple[Domain, ...] = ("reputational", "economic", "legal_regulatory")
VERSIONED_INTENTS = {"NEW_INFO", "ACTION_UPDATE", "CLOSE"}
OPEN_ACTION_STATUSES = {"proposed", "approved", "in_progress"}


# ---------------------------------------------------------------------------
# A0's own LLM calls (intent + question answering)
# ---------------------------------------------------------------------------


class IntentResult(BaseModel):
    intents: list[Intent] = Field(min_length=1)
    focus: str | None = None
    question: str | None = None
    close_requested: bool = False


class Answer(BaseModel):
    answer: str
    cited_ids: list[str] = Field(default_factory=list)


def llm_classify_intent(user_text: str, has_attachments: bool, case_id: str | None = None) -> IntentResult:
    content = f"Attachments in this turn: {'yes' if has_attachments else 'no'}\n\nUser message:\n{user_text}"
    return call_structured("A0-intent", load_prompt("a0_intent"), content, IntentResult, "low", case_id=case_id)


def llm_answer_question(state: CaseState, question: str) -> Answer:
    content = f"<case_state>\n{state.to_json()}\n</case_state>\n\nQuestion: {question}"
    return call_structured("A0-answer", load_prompt("a0_answer"), content, Answer, "low", case_id=state.case_id)


# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------

# slot -> (module, function) of the real implementation; signatures:
#   a1(state, turn) -> A1Output                 a2(state, turn, domain) -> DomainImpact
#   risk(state, prev_state) -> Risk             a3(state, turn) -> A3Output
#   a4(state, turn) -> A4Output                 a5(state, turn, prev_state) -> A5Output
#   render(state, pdf_path) -> Path
REAL_AGENTS: dict[str, tuple[str, str]] = {
    "a1": ("src.agents.a1_evidence", "run"),
    "a2": ("src.agents.a2_impact", "run"),
    "risk": ("src.risk", "compute_risk"),
    "a3": ("src.agents.a3_actions", "run"),
    "a4": ("src.agents.a4_critic", "run"),
    "a5": ("src.agents.a5_report", "run"),
    "render": ("src.report.render", "render_pdf"),
}


@dataclass
class AgentSet:
    classify: Callable[..., Any]
    answer: Callable[..., Any]
    a1: Callable[..., Any]
    a2: Callable[..., Any]
    risk: Callable[..., Any]
    a3: Callable[..., Any]
    a4: Callable[..., Any]
    a5: Callable[..., Any]
    render: Callable[..., Any]
    used: dict[str, str] = field(default_factory=dict)  # slot -> "stub" | "module.function"


def _import_real(module: str, func: str) -> Callable[..., Any] | None:
    try:
        mod = importlib.import_module(module)
    except ModuleNotFoundError as e:
        # module (or its package, e.g. src.report) not written yet -> stub;
        # a broken import *inside* an existing module is a real error
        if e.name == module or module.startswith(f"{e.name}."):
            return None
        raise
    return getattr(mod, func)


ALL_SLOTS = (*REAL_AGENTS, "classify", "answer")
FORCED_STUB_LABEL = "stub (ACME_STUB_AGENTS)"


def forced_stub_slots() -> set[str]:
    """Slots forced to their stub via .env, e.g. ACME_STUB_AGENTS=a1,a3.

    Use it while one teammate's agent exists but isn't ready, so the others can run for
    real. Unknown names are ignored with a warning (a typo must not break the app)."""
    load_dotenv(ROOT / ".env")
    raw = os.environ.get("ACME_STUB_AGENTS", "")
    names = {n.strip().lower() for n in raw.split(",") if n.strip()}
    unknown = names - set(ALL_SLOTS)
    if unknown:
        log.warning("ACME_STUB_AGENTS: unknown agent(s) %s ignored; valid: %s", sorted(unknown), ", ".join(ALL_SLOTS))
    return names & set(ALL_SLOTS)


def load_agents(use_stubs: bool = False) -> AgentSet:
    """use_stubs=True: every slot is a stub. Otherwise each slot uses its real module if it
    exists, unless it's listed in ACME_STUB_AGENTS (then it isn't even imported)."""
    fns: dict[str, Any] = {}
    used: dict[str, str] = {}
    forced = set(ALL_SLOTS) if use_stubs else forced_stub_slots()
    stub_map = {
        "a1": stubs.a1, "a2": stubs.a2, "risk": stubs.risk, "a3": stubs.a3,
        "a4": stubs.a4, "a5": stubs.a5, "render": stubs.render,
        "classify": stubs.classify_intent, "answer": stubs.answer_question,
    }
    real_map: dict[str, tuple[Callable[..., Any] | None, str]] = {
        "classify": (llm_classify_intent, "llm"),
        "answer": (llm_answer_question, "llm"),
    }
    for slot in ALL_SLOTS:
        if slot in forced:
            fns[slot] = stub_map[slot]
            used[slot] = "stub" if use_stubs else FORCED_STUB_LABEL
            continue
        if slot in REAL_AGENTS:
            module, func = REAL_AGENTS[slot]
            real, label = _import_real(module, func), f"{module}.{func}"
        else:
            real, label = real_map[slot]
        fns[slot] = real or stub_map[slot]
        used[slot] = label if real else "stub"
    return AgentSet(**fns, used=used)


# ---------------------------------------------------------------------------
# Case storage
# ---------------------------------------------------------------------------


def case_dir(case_id: str) -> Path:
    return cases_dir() / case_id


def latest_version(case_id: str) -> int:
    versions = [int(p.stem.split("_v")[1]) for p in case_dir(case_id).glob("state_v*.json")]
    return max(versions, default=0)


def load_state(case_id: str, version: int | None = None) -> CaseState | None:
    version = latest_version(case_id) if version is None else version
    if version == 0:
        return None
    path = case_dir(case_id) / f"state_v{version}.json"
    return CaseState.model_validate_json(path.read_text(encoding="utf-8"))


def next_case_id() -> str:
    existing = [int(p.name.split("-")[1]) for p in cases_dir().glob("CASE-*") if p.name.split("-")[1].isdigit()]
    return f"CASE-{max(existing, default=0) + 1:03d}"


def _meta_path(case_id: str) -> Path:
    return case_dir(case_id) / "case_meta.json"


def _load_meta(case_id: str) -> dict[str, Any]:
    p = _meta_path(case_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save_meta(case_id: str, meta: dict[str, Any]) -> None:
    _meta_path(case_id).parent.mkdir(parents=True, exist_ok=True)
    _meta_path(case_id).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def list_cases() -> list[str]:
    """Case IDs that have at least one saved version or chat message, newest first."""
    ids = [p.name for p in cases_dir().glob("CASE-*") if p.is_dir() and (latest_version(p.name) or (p / "chat.jsonl").exists())]
    return sorted(ids, reverse=True)


def load_chat(case_id: str) -> list[dict[str, Any]]:
    """Chat history of a case (written by the UI): [{"role", "content", ...}, ...]."""
    p = case_dir(case_id) / "chat.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_chat(case_id: str, message: dict[str, Any]) -> None:
    p = case_dir(case_id) / "chat.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(message, ensure_ascii=False) + "\n")


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _save_attachments(case_id: str, version: int, attachments: list[Path]) -> list[str]:
    inputs = case_dir(case_id) / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    saved = []
    for src in attachments:
        dest = inputs / src.name
        if dest.exists():
            dest = inputs / f"v{version}_{src.name}"
        shutil.copyfile(src, dest)
        saved.append(_rel(dest))
    return saved


# ---------------------------------------------------------------------------
# Merge rules (PROJECT §4) — enforced here, not trusted to the LLM
# ---------------------------------------------------------------------------


def _merge_by_id(old: list, new: list, key: str) -> list:
    """Replace items with the same ID, append new ones; never delete."""
    by_id = {getattr(x, key): x for x in new}
    merged = [by_id.pop(getattr(x, key), x) for x in old]
    return merged + list(by_id.values())


def _history_kept(old_hist: list, new_hist: list) -> bool:
    return new_hist[: len(old_hist)] == old_hist


def merge_a1(state: CaseState, out: A1Output, issues: list[QAIssue]) -> None:
    state.sources = _merge_by_id(state.sources, out.sources, "source_id")
    accepted = []
    for c in out.claims:
        old = state.claim(c.claim_id)
        if old and not _history_kept(old.change_history, c.change_history):
            issues.append(QAIssue(target="A1", item_id=c.claim_id, blocking=False,
                                  problem="Merge rule: change_history must keep earlier entries; this update was rejected and the previous version of the claim kept"))
            continue
        accepted.append(c)
    state.claims = _merge_by_id(state.claims, accepted, "claim_id")
    known = {q.question: i for i, q in enumerate(state.open_questions)}
    for q in out.open_questions:
        if q.question in known:
            state.open_questions[known[q.question]] = q
        else:
            state.open_questions.append(q)


def merge_a3(state: CaseState, out: A3Output, issues: list[QAIssue]) -> None:
    accepted = []
    for a in out.actions:
        old = state.action(a.action_id)
        if old and not _history_kept(old.status_history, a.status_history):
            issues.append(QAIssue(target="A3", item_id=a.action_id, blocking=False,
                                  problem="Merge rule: status_history must keep earlier entries; this update was rejected and the previous version of the action kept"))
            continue
        accepted.append(a)
    state.actions = _merge_by_id(state.actions, accepted, "action_id")
    if out.stakeholders:
        state.stakeholders = out.stakeholders


# ---------------------------------------------------------------------------
# The turn
# ---------------------------------------------------------------------------


@dataclass
class TurnResult:
    case_id: str | None
    version: int  # version after this turn (unchanged for QUESTION / focus-only turns)
    new_version: bool
    intents: list[str]
    reply: str
    state: CaseState | None = None
    pdf_path: str | None = None
    error: str | None = None
    agents_used: dict[str, str] = field(default_factory=dict)


def _as(model: type[BaseModel], value: Any) -> Any:
    """Validate an agent's output. Model instances are dumped and re-validated too: an
    instance changed after creation (e.g. c.status = ...) skipped its validators."""
    if isinstance(value, BaseModel):
        value = value.model_dump()
    return model.model_validate(value)


def _step(on_step: Callable[[str], None] | None, name: str) -> None:
    log.info("step %s", name)
    if on_step:
        on_step(name)


def run_turn(
    user_text: str,
    attachments: list[str | Path] = (),
    case_id: str | None = None,
    *,
    agents: AgentSet | None = None,
    use_stubs: bool = False,
    on_step: Callable[[str], None] | None = None,
) -> TurnResult:
    """Run one chat turn. Never raises for agent/LLM failures: returns TurnResult.error."""
    agents = agents or load_agents(use_stubs)
    attachments = [Path(a) for a in attachments]
    step = "A0 intent"
    try:
        _step(on_step, step)
        intent = _as(IntentResult, agents.classify(user_text, bool(attachments), case_id))
        intents = list(dict.fromkeys(intent.intents))
        if attachments and not VERSIONED_INTENTS & set(intents):
            intents.append("NEW_INFO")

        prev = load_state(case_id) if case_id else None

        # QUESTION / focus-only: no new version
        if not VERSIONED_INTENTS & set(intents):
            if "SET_FOCUS" in intents and intent.focus:
                case_id = case_id or next_case_id()
                _save_meta(case_id, {**_load_meta(case_id), "focus": intent.focus})
                reply = f"Focus set to “{intent.focus}”. It will shape the next report version (it never changes the risk scores)."
            else:
                step = "A0 answer"
                _step(on_step, step)
                if prev is None:
                    reply = "There is no report for this case yet. Share the incident evidence to start."
                else:
                    reply = _as(Answer, agents.answer(prev, intent.question or user_text)).answer
            return TurnResult(case_id, prev.version if prev else 0, False, intents, reply,
                              state=prev, agents_used=agents.used)

        # Versioned turn
        case_id = case_id or next_case_id()
        meta = _load_meta(case_id)
        if "SET_FOCUS" in intents and intent.focus:
            meta["focus"] = intent.focus
            _save_meta(case_id, meta)
        state = prev.model_copy(deep=True) if prev else new_case(case_id)
        version = state.version + 1
        state.version = version
        state.focus = meta.get("focus", state.focus)
        if state.status == "closed":
            state.status = "open"
            state.closure = None  # reopened by new information
        primary: Intent = "CLOSE" if "CLOSE" in intents else "ACTION_UPDATE" if "ACTION_UPDATE" in intents else "NEW_INFO"
        saved = _save_attachments(case_id, version, attachments)
        turn = TurnInput(intent=primary, user_text=user_text, attachments=saved)
        state.turn_input = turn
        merge_issues: list[QAIssue] = []

        def snapshot() -> CaseState:
            return state.model_copy(deep=True)

        def run_a1() -> None:
            out = _as(A1Output, agents.a1(snapshot(), turn))
            merge_a1(state, out, merge_issues)
            # D-009: attachments = file paths in, U-xx IDs out
            ids = {s.file: s.source_id for s in state.sources if s.file in saved}
            state.turn_input.attachments = [ids.get(p, p) for p in saved]

        def run_a2(domains: tuple[Domain, ...] = DOMAINS) -> None:
            snap = snapshot()
            with ThreadPoolExecutor(max_workers=len(domains)) as pool:
                futures = {d: pool.submit(agents.a2, snap, turn, d) for d in domains}
                for d, fut in futures.items():
                    setattr(state.impacts, d, _as(DomainImpact, fut.result()))

        def run_risk() -> None:
            state.risk = _as(Risk, agents.risk(snapshot(), prev))

        def run_a3() -> None:
            merge_a3(state, _as(A3Output, agents.a3(snapshot(), turn)), merge_issues)

        def run_a4() -> A4Output:
            out = _as(A4Output, agents.a4(snapshot(), turn))
            state.qa, state.outlook = out.qa, out.outlook
            return out

        step = "A1 evidence"; _step(on_step, step); run_a1()
        step = "A2 impacts (3 in parallel)"; _step(on_step, step); run_a2()
        step = "risk engine"; _step(on_step, step); run_risk()
        step = "A3 actions"; _step(on_step, step); run_a3()
        step = "A4 critic"; _step(on_step, step); a4_out = run_a4()

        # A4 revise loop: at most once
        blocking = [i for i in state.qa.issues if i.blocking and not i.resolved]
        if state.qa.verdict == "REVISE" and blocking:
            targets = {i.target for i in blocking}
            step = f"revise ({', '.join(sorted(targets))})"
            _step(on_step, step)
            if "A1" in targets:
                run_a1(); run_a2(); run_risk(); run_a3()
            elif targets & {"A2", "A2a", "A2b", "A2c"}:
                run_a2(); run_risk(); run_a3()
            elif "A3" in targets:
                run_a3()
            step = "A4 critic (after revise)"; _step(on_step, step); a4_out = run_a4()
        if merge_issues:
            state.qa = QA(verdict=state.qa.verdict, issues=state.qa.issues + merge_issues)

        if primary == "CLOSE":
            state.status = "closed"
            state.closure = Closure(
                remaining_risk=f"{state.risk.level} (evidence confidence: {state.risk.evidence_confidence})",
                open_actions=[a.action_id for a in state.actions if a.status in OPEN_ACTION_STATUSES],
                reopen_conditions=a4_out.reopen_conditions,
            )

        step = "diff"
        state.changelog = state.changelog + [build_changelog_entry(prev, state)]

        step = "A5 report"
        _step(on_step, step)
        a5_out = _as(A5Output, agents.a5(snapshot(), turn, prev))
        state.changelog[-1].summary = a5_out.changes_summary
        pdf = case_dir(case_id) / f"report_v{version}.pdf"
        state.report = Report(pdf_path=_rel(pdf), narrative=a5_out.narrative,
                              narrative_warnings=a5_out.narrative_warnings)
        state.updated_at = datetime.now(timezone.utc)

        step = "validate + save"
        state = CaseState.model_validate(state.model_dump())  # re-run every contract validator
        for problem in state.reference_errors():
            log.warning("reference: %s", problem)
        step = "render PDF"
        _step(on_step, step)
        agents.render(state, pdf)
        state_path = case_dir(case_id) / f"state_v{version}.json"
        if state_path.exists():
            raise FileExistsError(f"{state_path} already exists (versions are immutable)")
        state_path.write_text(state.to_json(), encoding="utf-8")

        return TurnResult(case_id, version, True, intents, chat_reply(prev, state),
                          state=state, pdf_path=_rel(pdf), agents_used=agents.used)

    except Exception as e:  # noqa: BLE001 — the chat must never crash; report where it failed
        log.exception("turn failed at step %s", step)
        prev_version = latest_version(case_id) if case_id else 0
        return TurnResult(case_id, prev_version, False, [], f"Sorry, the analysis failed at step “{step}”. No new report version was saved.",
                          error=f"{step}: {type(e).__name__}: {e}", agents_used=agents.used)


def chat_reply(prev: CaseState | None, state: CaseState) -> str:
    """Template reply (no LLM), as Markdown: version, risk change, key changes, top P1 actions.
    The PDF is offered separately (download button in the UI, path printed by the CLI)."""
    risk = state.risk
    entry = state.changelog[-1]
    if risk.previous_level is None:
        risk_text = f"Risk: **{risk.level}** (first assessment)"
    elif risk.previous_level == risk.level:
        risk_text = f"Risk: **{risk.level}** (unchanged)"
    else:
        risk_text = f"Risk: {risk.previous_level} → **{risk.level}**"
    header = f"**Report v{state.version}** · {risk_text} · evidence confidence: {risk.evidence_confidence}"
    if state.status == "closed":
        header += " · case **closed**"
    changes = (entry.claim_changes + entry.action_changes)[:3] or ["no claim or action changes"]
    lines = [header, "", "**Key changes**"] + [f"- {c}" for c in changes]
    p1 = [a for a in state.actions if a.priority == "P1" and a.status in OPEN_ACTION_STATUSES][:3]
    if p1:
        lines += ["", "**Top P1 actions**"] + [f"- {a.action_id} · {a.title} · {a.owner} · {a.timing}" for a in p1]
    unresolved = [i for i in (state.qa.issues if state.qa else []) if not i.resolved]
    if unresolved:
        lines += ["", f"QA notes: {len(unresolved)} open (see the report appendix)"]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one ACME crisis-manager turn")
    parser.add_argument("--text", required=True)
    parser.add_argument("--case", default=None, help="existing case ID (omit for a new case)")
    parser.add_argument("--attach", action="append", default=[], help="file to attach (repeatable)")
    parser.add_argument("--stubs", action="store_true", help="use stub agents (no API key needed)")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows console: keep → … “ ” readable
    logging.basicConfig(level=logging.WARNING)
    result = run_turn(args.text, args.attach, args.case, use_stubs=args.stubs, on_step=lambda s: print(f"  … {s}"))
    print(f"\ncase {result.case_id} · intents {result.intents}\n{result.reply}")
    if result.pdf_path:
        print(f"\nPDF: {result.pdf_path}")
    if result.error:
        print(f"\nERROR: {result.error}")
    print(f"\nagents: {result.agents_used}")


if __name__ == "__main__":
    main()
