"""A3 Action Planner: the action register and the stakeholder map.

Pipeline interface (src/pipeline.py): run(state, turn) -> A3Output, with only NEW or
CHANGED actions as full Action objects (A0 merges by ID, never deletes) and the full
current stakeholder list. The pipeline computes closure.open_actions itself on CLOSE.

Design (Serdar, 2026-11-23): the LLM returns a short PLAN (new actions, changes to
existing actions, stakeholders); CODE builds the Action records. So IDs always continue
the numbering (never reused), every status change gets a status_history entry for this
version with the reason, earlier history is always kept, and status == last entry.

Checks (agreed with Serdar):
- HARD (one retry inside llm.call_structured, then warning): owner/approver not in the
  KB-02 contact sheet; source IDs that do not exist; unknown action IDs in changes;
  invalid actions (e.g. verified without result evidence); banned phrases / personal
  data in A3's texts (src/report/checks.py); focus_related missing when a focus is set.
- SOFT (warning only): a High/Critical domain without an action or a "no action, because";
  a major decision with < 2 options or not exactly one chosen; recall/withdrawal/large
  remedy without the CEO as approver; injury/authority/personal-data action without
  Sophie Laurent (Legal/DPO).
Warnings are logged (A3Output has no warnings field yet: proposed to the director).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from src.contracts import A3Output, Action, ActionOption, ActionStatus, CaseState, Domain, Priority, Stakeholder, TurnInput
from src.kb import SOURCE_REGISTRY
from src.llm import LLMError, LLMOutputError, call_structured, load_prompt
from src.report.checks import find_banned_phrases, find_personal_data

log = logging.getLogger(__name__)

# KB-02 (Operations contact sheet, 20 Oct 2026): the only people who may own or approve actions.
ACME_STAFF = ("Elena Rossi", "Daniel Moretti", "Maya Chen", "Luca Ferri", "Tom Weber",
              "Aisha Khan", "Sophie Laurent", "Anna Keller", "Marco Bianchi")
CEO = "Daniel Moretti"
LEGAL_DPO = "Sophie Laurent"

_MAJOR = re.compile(r"\b(hold|recall\w*|withdraw\w*|replace\w*|refund\w*|statement|press|announc\w*|notif\w*)\b", re.I)
_LARGE_REMEDY = re.compile(r"\b(recall\w*|withdraw\w*|replacement\s+program\w*|replace\s+(all|every)|large\s+remed\w*)\b", re.I)
_NO_PRECEDENT = re.compile(r"\bno\s+(?:ACME\s+)?precedent\b|\bgeneral\s+knowledge\b", re.I)
_LEGAL = re.compile(r"\b(injur\w*|authorit\w*|regulator\w*|notif\w*|personal\s+data|GDPR|breach)\b", re.I)


# ---------------------------------------------------------------- what the LLM returns (a plan)

class NewAction(BaseModel):
    title: str
    what_it_does: str
    owner: str
    approver: Optional[str] = None
    timing: str
    priority: Priority
    focus_related: Optional[bool] = None
    domains: list[Domain] = Field(default_factory=list)
    options_considered: list[ActionOption] = Field(default_factory=list)
    basis_source_ids: list[str] = Field(default_factory=list)
    expected_effect: str = ""
    # Usually "proposed". Another status only if the user reported it (decision 2026-11-23).
    initial_status: Literal["proposed", "approved", "in_progress", "completed"] = "proposed"
    result_evidence_source_ids: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)


class ActionChange(BaseModel):
    action_id: str
    reason: str = Field(min_length=1)
    new_status: Optional[ActionStatus] = None
    result_evidence_source_ids: list[str] = Field(default_factory=list)
    # optional revisions (None = unchanged)
    title: Optional[str] = None
    what_it_does: Optional[str] = None
    owner: Optional[str] = None
    approver: Optional[str] = None
    timing: Optional[str] = None
    priority: Optional[Priority] = None
    focus_related: Optional[bool] = None
    domains: Optional[list[Domain]] = None
    options_considered: Optional[list[ActionOption]] = None
    basis_source_ids: Optional[list[str]] = None
    expected_effect: Optional[str] = None


class A3Plan(BaseModel):
    new_actions: list[NewAction] = Field(default_factory=list)
    changes: list[ActionChange] = Field(default_factory=list)
    stakeholders: list[Stakeholder] = Field(default_factory=list)
    no_action_reasons: list[str] = Field(default_factory=list)


_REVISABLE = ("title", "what_it_does", "owner", "approver", "timing", "priority", "focus_related",
              "domains", "options_considered", "basis_source_ids", "expected_effect")


# ---------------------------------------------------------------- code builds the actions

def _next_number(state: CaseState) -> int:
    nums = [int(a.action_id.split("-")[1]) for a in state.actions]
    return max(nums, default=0) + 1


def assemble(plan: A3Plan, state: CaseState) -> tuple[list[Action], list[str]]:
    """Turn the plan into Action records. Invalid items are skipped and reported."""
    v = state.version
    problems: list[str] = []
    actions: list[Action] = []
    n = _next_number(state)

    for i, new in enumerate(plan.new_actions, start=1):
        data = new.model_dump(exclude={"initial_status", "reason"})
        data.update(
            action_id=f"ACT-{n:03d}",
            status=new.initial_status,
            status_history=[{"version": v, "from": None, "to": new.initial_status, "reason": new.reason}],
        )
        if not state.focus:
            data["focus_related"] = None
        try:
            actions.append(Action.model_validate(data))
            n += 1
        except ValidationError as e:
            problems.append(f"new action {i} ('{new.title}') is invalid: {_short(e)}")

    seen: set[str] = set()
    for ch in plan.changes:
        old = state.action(ch.action_id)
        if old is None:
            problems.append(f"change refers to {ch.action_id}, which is not in the action register")
            continue
        if ch.action_id in seen:
            problems.append(f"{ch.action_id} is changed twice; merge the changes into one")
            continue
        seen.add(ch.action_id)
        data = old.model_dump(mode="json")
        for key in _REVISABLE:
            value = getattr(ch, key)
            if value is not None:
                data[key] = [o.model_dump() for o in value] if key == "options_considered" else value
        if not state.focus:
            data["focus_related"] = None
        data["result_evidence_source_ids"] = list(dict.fromkeys(data["result_evidence_source_ids"] + ch.result_evidence_source_ids))
        if ch.new_status and ch.new_status != old.status:
            data["status"] = ch.new_status
            data["status_history"] = data["status_history"] + [
                {"version": v, "from": old.status, "to": ch.new_status, "reason": ch.reason}]
        try:
            actions.append(Action.model_validate(data))
        except ValidationError as e:
            problems.append(f"change to {ch.action_id} is invalid: {_short(e)}")
    return actions, problems


def _short(e: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()[:3])


# ---------------------------------------------------------------- checks

def _texts(actions: list[Action], stakeholders: list[Stakeholder]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for a in actions:
        for key in ("title", "what_it_does", "expected_effect"):
            texts[f"{a.action_id} {key}"] = getattr(a, key)
        for k, o in enumerate(a.options_considered, start=1):
            texts[f"{a.action_id} option {k}"] = f"{o.option} | {o.pros} | {o.cons}"
    for s in stakeholders:
        texts[f"stakeholder '{s.name}'"] = f"{s.name} | {s.interest} | {s.impact}"
    return texts


def _norm(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _is_staff(person: str | None) -> bool:
    return bool(person) and any(name in person for name in ACME_STAFF)


def _status_changed(a: Action, state: CaseState) -> bool:
    old = state.action(a.action_id)
    return a.status != (old.status if old else "proposed")


def _user_reported_something(turn: TurnInput | None, state: CaseState) -> bool:
    t = turn or state.turn_input
    return bool(t and ((t.user_text or "").strip() or t.attachments))


def hard_problems(plan: A3Plan, state: CaseState, actions: list[Action], assemble_problems: list[str],
                  turn: TurnInput | None = None) -> list[str]:
    problems = list(assemble_problems)
    registered = {s.source_id for s in state.sources}
    reported = _user_reported_something(turn, state)
    for a in actions:
        # Spec rule 7 (session 3): a status moves only on a fact the user reported in this turn.
        if _status_changed(a, state) and not reported:
            problems.append(f"{a.action_id}: status set to '{a.status}' but the user reported nothing in this turn "
                            "(status changes need a user-reported fact)")
        # Spec rule 4 / R10: every action says what it does.
        if not a.title.strip() or not a.what_it_does.strip():
            problems.append(f"{a.action_id}: title and what_it_does must not be empty")
        if not _is_staff(a.owner):
            problems.append(f"{a.action_id}: owner '{a.owner}' is not on the ACME contact sheet (KB-02)")
        if a.approver and not _is_staff(a.approver):
            problems.append(f"{a.action_id}: approver '{a.approver}' is not on the ACME contact sheet (KB-02)")
        bad_basis = [i for i in a.basis_source_ids if i not in registered and i not in SOURCE_REGISTRY]
        if bad_basis:
            problems.append(f"{a.action_id}: basis_source_ids not found: {', '.join(bad_basis)}")
        # Result evidence = evidence about THIS incident (registered, not a KB background file):
        # a company file from before the incident cannot show that an action worked.
        bad_result = [i for i in a.result_evidence_source_ids if i not in registered or i in SOURCE_REGISTRY]
        if bad_result:
            problems.append(f"{a.action_id}: result_evidence_source_ids must be registered evidence about this "
                            f"incident (not KB files); not valid: {', '.join(bad_result)}")
    # Duplicates (e.g. on an A4 revise run, the first run's actions are already in the register)
    existing_titles = {_norm(a.title): a.action_id for a in state.actions}
    for a in actions:
        if state.action(a.action_id) is None and _norm(a.title) in existing_titles:
            problems.append(f"new action '{a.title}' is already in the register as {existing_titles[_norm(a.title)]}; "
                            "put the update in `changes` instead")
    for s in plan.stakeholders:
        if s.acme_contact and not _is_staff(s.acme_contact):
            problems.append(f"stakeholder '{s.name}': acme_contact '{s.acme_contact}' is not on the ACME contact sheet (KB-02)")
    if state.focus:
        changed = {a.action_id: a for a in actions}
        final = [changed.get(a.action_id, a) for a in state.actions] + [a for a in actions if state.action(a.action_id) is None]
        missing = [a.action_id for a in final if a.focus_related is None and a.status != "dropped"]
        if missing:
            problems.append(f"the case has a focus ('{state.focus}'): set focus_related (true/false) for {', '.join(missing)}")
    data = state.model_dump(mode="json")
    texts = _texts(actions, plan.stakeholders)
    problems += find_banned_phrases(texts, data)
    problems += find_personal_data(texts)
    return problems


def soft_problems(plan: A3Plan, state: CaseState, actions: list[Action]) -> list[str]:
    warnings: list[str] = []
    changed = {a.action_id: a for a in actions}
    final = [changed.get(a.action_id, a) for a in state.actions] + [a for a in actions if state.action(a.action_id) is None]
    live = [a for a in final if a.status != "dropped"]
    for domain in ("reputational", "economic", "legal_regulatory"):
        block = getattr(state.impacts, domain)
        if not block:
            continue
        high = (block.score or 0) >= 8 or any(f != "F4" for f in block.floor_triggers)
        explained = any(domain.split("_")[0] in r.lower() for r in plan.no_action_reasons)
        if high and not explained and not any(domain in a.domains for a in live):
            warnings.append(f"{domain} impact is High/Critical but no action covers it and no 'no action, because' was given")
    for a in actions:
        # Spec rule 3 (session 3): grounded in a precedent/policy, or labelled as having none.
        if not a.basis_source_ids and not _NO_PRECEDENT.search(a.what_it_does):
            warnings.append(f"{a.action_id}: no basis_source_ids and not labelled 'no precedent' / 'general knowledge'")
        if not a.expected_effect.strip():
            warnings.append(f"{a.action_id}: expected_effect is empty")
        # Heuristics look at the TITLE only: descriptions often contain drafting guidance
        # ("do not claim 'authorities contacted'") that would trigger false alarms.
        text = a.title
        people = f"{a.owner} {a.approver or ''} {a.title} {a.what_it_does}"
        if _MAJOR.search(text):
            chosen = sum(o.chosen for o in a.options_considered)
            if len(a.options_considered) < 2 or chosen != 1:
                warnings.append(f"{a.action_id}: major decision needs >= 2 options with exactly one chosen "
                                f"(has {len(a.options_considered)} options, {chosen} chosen)")
        if _LARGE_REMEDY.search(text) and CEO not in (a.approver or ""):
            warnings.append(f"{a.action_id}: recall/withdrawal/large remedy should have {CEO} (CEO) as approver (KB-12)")
        if _LEGAL.search(text) and LEGAL_DPO not in people:
            warnings.append(f"{a.action_id}: injury/authority/personal-data action should involve {LEGAL_DPO} (Legal/DPO)")
    for r in plan.no_action_reasons:
        warnings.append(f"no action: {r}")
    return [w + " (automatic check; please review)" if not w.startswith("no action:") else w for w in warnings]


# ---------------------------------------------------------------- the LLM call

def _user_message(state: CaseState, turn: TurnInput | None) -> str:
    s = state.model_dump(mode="json")
    payload = {
        "case": {"case_id": s["case_id"], "version": s["version"], "status": s["status"], "focus": s.get("focus")},
        "this_turn": (turn.model_dump(mode="json") if turn else s.get("turn_input")),
        "risk": s.get("risk"),
        "impacts": s.get("impacts"),
        "claims": s.get("claims"),
        "sources": s.get("sources"),
        "action_register": s.get("actions"),
        "stakeholders": s.get("stakeholders"),
        "open_questions": s.get("open_questions"),
        "qa_issues_for_A3": [i for i in (s.get("qa") or {}).get("issues", []) if i.get("target") == "A3" and not i.get("resolved")],
    }
    return ("Case data for the action plan (JSON). Changes and new actions are for version "
            f"{s['version']}.\n\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1))


def plan_actions(state: CaseState, turn: TurnInput | None = None, *, client=None) -> tuple[A3Output, list[str]]:
    """Return (A3Output, warnings)."""
    def check(plan: A3Plan) -> list[str]:
        actions, assembly = assemble(plan, state)
        return hard_problems(plan, state, actions, assembly, turn)

    try:
        plan = call_structured("A3", load_prompt("a3_actions"), _user_message(state, turn), A3Plan, "high",
                               case_id=state.case_id, check=check, client=client)
    except LLMOutputError as e:
        # Still wrong after the one retry: keep what is valid, report the rest.
        try:
            plan = A3Plan.model_validate_json(e.raw_text)
        except ValidationError:
            raise LLMError("A3", f"output invalid after one retry: {'; '.join(e.problems[:5])}") from e

    actions, assembly = assemble(plan, state)
    warnings = hard_problems(plan, state, actions, assembly, turn) + soft_problems(plan, state, actions)
    return A3Output(actions=actions, stakeholders=plan.stakeholders), warnings


def run(state: CaseState, turn: TurnInput | None = None, *, client=None) -> A3Output:
    """Pipeline entry point. API errors (LLMError) go up to the pipeline, like A1/A2."""
    out, warnings = plan_actions(state, turn, client=client)
    for w in warnings:
        log.warning("A3 %s: %s", state.case_id, w)
    return out
