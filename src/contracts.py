"""CaseState: the shared contract between all agents (PROJECT.md ┬º4).

Owned by A0. Field names are binding: change them only through the Decision log
(PROJECT.md ┬º12), never inside an agent's own chat.

What is enforced here (per object, at validation time):
  - ID formats (KB-xx / U-xx, C-xxx, ACT-xxx) and unique IDs inside one state
  - domain score = severity ├ù likelihood
  - every claim change_history entry has a reason and >= 1 source_id;
    the claim's current status equals the last history entry
  - an action can be verified_effective/ineffective only with result evidence

What is NOT enforced here (cross-version merge rules, see pipeline.py):
  - sources/claims/actions are never deleted between versions
  - only risk.py writes `risk`
`CaseState.reference_errors()` reports dangling source/claim/action IDs without
raising, so a half-built fixture still loads.

Usage:
    from src.contracts import CaseState
    state = CaseState.model_validate_json(path.read_text(encoding="utf-8"))
    path.write_text(state.to_json(), encoding="utf-8")
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Enumerations (Literal types serialize as plain strings and work with
# structured outputs)
# ---------------------------------------------------------------------------

Intent = Literal["NEW_INFO", "ACTION_UPDATE", "QUESTION", "SET_FOCUS", "CLOSE"]
CaseStatus = Literal["open", "closed"]

SourceOrigin = Literal["kb", "user_upload", "user_text"]
SourceCategory = Literal[
    "incident_evidence",
    "company_record",
    "historical_case",
    "informal_note",
    "planning_assumption",
    "reference",
]
TimeRelevance = Literal["current", "historical"]

ClaimStatus = Literal["confirmed", "unconfirmed", "disproved", "misleading"]
EvidenceStrength = Literal["strong", "moderate", "weak"]
Domain = Literal["reputational", "economic", "legal_regulatory"]

Timeframe = Literal["24h", "7d", "30d"]
ImpactBasis = Literal["company_data", "precedent", "general_knowledge", "incident_evidence"]
FloorId = Literal["F1", "F2", "F3", "F4"]
Confidence = Literal["low", "medium", "high"]
RiskLevel = Literal["Low", "Medium", "High", "Critical"]
RISK_LEVELS: tuple[RiskLevel, ...] = ("Low", "Medium", "High", "Critical")  # ascending

StakeholderType = Literal["internal", "external"]
Priority = Literal["P1", "P2", "P3"]
ActionStatus = Literal[
    "proposed",
    "approved",
    "in_progress",
    "completed",
    "verified_effective",
    "verified_ineffective",
    "dropped",
]
QAVerdict = Literal["PASS", "REVISE"]
AgentId = Literal["A0", "A1", "A2", "A2a", "A2b", "A2c", "A3", "A4", "A5"]

# ID patterns
SOURCE_ID_PATTERN = r"^(KB-\d{2}|U-\d{2,})$"
CLAIM_ID_PATTERN = r"^C-\d{3,}$"
ACTION_ID_PATTERN = r"^ACT-\d{3,}$"
KB_SOURCE_IDS: tuple[str, ...] = tuple(f"KB-{i:02d}" for i in range(1, 14))  # PROJECT.md ┬º8


class _Model(BaseModel):
    """Base: unknown fields are errors (catches typos in agent output and fixtures)."""

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,  # `from_` is written as "from"
    )


# ---------------------------------------------------------------------------
# Turn input
# ---------------------------------------------------------------------------


class TurnInput(_Model):
    intent: Intent
    user_text: str = ""
    # ┬º4 example lists source IDs (["U-03"]). A0 passes the saved file paths to A1;
    # once A1 has registered them, A0 stores the assigned U-xx IDs here.
    attachments: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# A1: sources and claims
# ---------------------------------------------------------------------------


class Source(_Model):
    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    title: str
    file: str | None = None
    origin: SourceOrigin
    date: str | None = None  # date of the content (free text allowed: "Sep 2026")
    category: SourceCategory
    time_relevance: TimeRelevance
    duplicate_of: str | None = Field(default=None, pattern=SOURCE_ID_PATTERN)
    reliability_note: str = ""
    added_in_version: int = Field(ge=0)


class ClaimChange(_Model):
    version: int = Field(ge=1)
    from_: ClaimStatus | None = Field(default=None, alias="from")
    to: ClaimStatus
    reason: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)


class Claim(_Model):
    claim_id: str = Field(pattern=CLAIM_ID_PATTERN)
    text: str
    status: ClaimStatus
    evidence_strength: EvidenceStrength
    source_ids: list[str] = Field(min_length=1)
    contradicted_by: list[str] = Field(default_factory=list)
    domains: list[Domain] = Field(default_factory=list)
    product: str | None = None
    batch: str | None = None
    market: str | None = None
    first_seen_version: int = Field(ge=1)
    last_changed_version: int = Field(ge=1)
    change_history: list[ClaimChange] = Field(min_length=1)

    @model_validator(mode="after")
    def _status_matches_history(self) -> Claim:
        if self.change_history[-1].to != self.status:
            raise ValueError(
                f"{self.claim_id}: status '{self.status}' differs from the last "
                f"change_history entry ('{self.change_history[-1].to}')"
            )
        return self


# ---------------------------------------------------------------------------
# A2: impacts per domain
# ---------------------------------------------------------------------------


class ImpactItem(_Model):
    description: str
    if_unaddressed: str
    timeframe: Timeframe
    stakeholders: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    basis: ImpactBasis


class DomainImpact(_Model):
    severity: int = Field(ge=1, le=4)
    likelihood: int = Field(ge=1, le=4)
    score: int | None = Field(default=None, description="severity ├ù likelihood; filled automatically")
    severity_reason: str
    likelihood_reason: str
    impacts: list[ImpactItem] = Field(default_factory=list)
    floor_triggers: list[FloorId] = Field(default_factory=list)
    evidence_confidence: Confidence

    @model_validator(mode="after")
    def _score_is_product(self) -> DomainImpact:
        expected = self.severity * self.likelihood
        if self.score is not None and self.score != expected:
            raise ValueError(f"score {self.score} != severity├ùlikelihood = {expected}")
        self.score = expected
        return self


class Impacts(_Model):
    reputational: DomainImpact | None = None
    economic: DomainImpact | None = None
    legal_regulatory: DomainImpact | None = None


# ---------------------------------------------------------------------------
# risk.py output (never written by an LLM)
# ---------------------------------------------------------------------------


class Risk(_Model):
    level: RiskLevel
    previous_level: RiskLevel | None = None
    max_domain_score: int = Field(ge=0, le=16)
    floors_applied: list[FloorId] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    evidence_confidence: Confidence


# ---------------------------------------------------------------------------
# A3: stakeholders and actions
# ---------------------------------------------------------------------------


class Stakeholder(_Model):
    name: str
    type: StakeholderType
    interest: str = ""
    impact: str = ""
    acme_contact: str | None = None


class ActionOption(_Model):
    option: str
    pros: str = ""
    cons: str = ""
    chosen: bool = False


class ActionStatusChange(_Model):
    version: int = Field(ge=1)
    from_: ActionStatus | None = Field(default=None, alias="from")
    to: ActionStatus
    reason: str = Field(min_length=1)


class Action(_Model):
    action_id: str = Field(pattern=ACTION_ID_PATTERN)
    title: str
    what_it_does: str
    owner: str
    approver: str | None = None
    timing: str
    priority: Priority
    domains: list[Domain] = Field(default_factory=list)
    status: ActionStatus
    options_considered: list[ActionOption] = Field(default_factory=list)
    basis_source_ids: list[str] = Field(default_factory=list)
    expected_effect: str = ""
    result_evidence_source_ids: list[str] = Field(default_factory=list)
    status_history: list[ActionStatusChange] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_status(self) -> Action:
        if self.status in ("verified_effective", "verified_ineffective") and not self.result_evidence_source_ids:
            raise ValueError(f"{self.action_id}: status '{self.status}' needs result_evidence_source_ids")
        if self.status_history[-1].to != self.status:
            raise ValueError(
                f"{self.action_id}: status '{self.status}' differs from the last "
                f"status_history entry ('{self.status_history[-1].to}')"
            )
        return self


# ---------------------------------------------------------------------------
# A4: outlook and QA
# ---------------------------------------------------------------------------


class Outlook(_Model):
    residual_risk_if_p1_effective: RiskLevel | None = None
    reasons: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    cannot_estimate: list[str] = Field(default_factory=list)
    pattern_warnings: list[str] = Field(default_factory=list)


class QAIssue(_Model):
    target: AgentId
    item_id: str | None = None
    problem: str
    fix_hint: str = ""
    blocking: bool = False
    resolved: bool = False


class QA(_Model):
    verdict: QAVerdict
    issues: list[QAIssue] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Questions, changelog, closure, report
# ---------------------------------------------------------------------------


class OpenQuestion(_Model):
    question: str
    owner: str | None = None
    raised_in_version: int = Field(ge=1)
    closed_in_version: int | None = None


class ChangelogEntry(_Model):
    version: int = Field(ge=1)
    risk_from: RiskLevel | None = None
    risk_to: RiskLevel | None = None
    new_source_ids: list[str] = Field(default_factory=list)
    claim_changes: list[str] = Field(default_factory=list)
    action_changes: list[str] = Field(default_factory=list)
    summary: str = ""  # A5 fills the narrative "why"


class Closure(_Model):
    remaining_risk: str
    open_actions: list[str] = Field(default_factory=list)
    reopen_conditions: list[str] = Field(default_factory=list)


class Report(_Model):
    pdf_path: str | None = None
    # Section name -> text, e.g. {"situation": ..., "changes_summary": ...}. A5 owns the keys.
    narrative: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# CaseState
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CaseState(_Model):
    case_id: str = Field(pattern=r"^CASE-\d{3,}$")
    version: int = Field(ge=0, description="0 = empty new case; A0 sets N+1 on every versioned turn")
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    status: CaseStatus = "open"
    focus: str | None = None
    turn_input: TurnInput | None = None

    sources: list[Source] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    impacts: Impacts = Field(default_factory=Impacts)
    risk: Risk | None = None
    stakeholders: list[Stakeholder] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    outlook: Outlook | None = None
    qa: QA | None = None
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    changelog: list[ChangelogEntry] = Field(default_factory=list)
    closure: Closure | None = None
    report: Report | None = None

    @model_validator(mode="after")
    def _unique_ids(self) -> CaseState:
        for name, ids in (
            ("source_id", [s.source_id for s in self.sources]),
            ("claim_id", [c.claim_id for c in self.claims]),
            ("action_id", [a.action_id for a in self.actions]),
        ):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            if dupes:
                raise ValueError(f"duplicate {name}: {dupes}")
        return self

    # -- helpers ------------------------------------------------------------

    def source(self, source_id: str) -> Source | None:
        return next((s for s in self.sources if s.source_id == source_id), None)

    def claim(self, claim_id: str) -> Claim | None:
        return next((c for c in self.claims if c.claim_id == claim_id), None)

    def action(self, action_id: str) -> Action | None:
        return next((a for a in self.actions if a.action_id == action_id), None)

    def reference_errors(self) -> list[str]:
        """Dangling IDs: cited sources not registered (KB-01..13 always count as known),
        QA item_ids / closure open_actions that don't exist. Empty list = clean."""
        known_sources = set(KB_SOURCE_IDS) | {s.source_id for s in self.sources}
        known_items = {c.claim_id for c in self.claims} | {a.action_id for a in self.actions} | known_sources
        errors: list[str] = []

        def check(where: str, ids: list[str]) -> None:
            for i in ids:
                if i not in known_sources:
                    errors.append(f"{where}: unknown source {i}")

        for s in self.sources:
            if s.duplicate_of:
                check(f"source {s.source_id}.duplicate_of", [s.duplicate_of])
        for c in self.claims:
            check(f"claim {c.claim_id}.source_ids", c.source_ids)
            check(f"claim {c.claim_id}.contradicted_by", c.contradicted_by)
            for h in c.change_history:
                check(f"claim {c.claim_id}.change_history v{h.version}", h.source_ids)
        for domain in ("reputational", "economic", "legal_regulatory"):
            block = getattr(self.impacts, domain)
            if block:
                for item in block.impacts:
                    check(f"impacts.{domain}", item.source_ids)
        for a in self.actions:
            check(f"action {a.action_id}.basis_source_ids", a.basis_source_ids)
            check(f"action {a.action_id}.result_evidence_source_ids", a.result_evidence_source_ids)
        if self.turn_input:
            # attachments may still be file paths before A1 runs; only check ID-shaped ones
            check("turn_input.attachments", [x for x in self.turn_input.attachments if x.startswith("U-")])
        for entry in self.changelog:
            check(f"changelog v{entry.version}.new_source_ids", entry.new_source_ids)
        if self.qa:
            for issue in self.qa.issues:
                if issue.item_id and issue.item_id not in known_items:
                    errors.append(f"qa issue for {issue.target}: unknown item {issue.item_id}")
        if self.closure:
            for a_id in self.closure.open_actions:
                if a_id not in {a.action_id for a in self.actions}:
                    errors.append(f"closure.open_actions: unknown action {a_id}")
        return errors

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)


# ---------------------------------------------------------------------------
# Agent outputs: what each agent returns to A0 (PROJECT.md ┬º3.3 "Writes" column).
# Agents return only new or changed items; A0 merges them into CaseState by ID
# (never deletes) and enforces the merge rules. risk is never an agent output.
# ---------------------------------------------------------------------------


class A1Output(_Model):
    sources: list[Source] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)


# A2a/b/c each return one DomainImpact (A0 stores it under impacts.<domain>).


class A3Output(_Model):
    actions: list[Action] = Field(default_factory=list)
    stakeholders: list[Stakeholder] = Field(default_factory=list)  # full current list (replaces)


class A4Output(_Model):
    qa: QA
    outlook: Outlook
    reopen_conditions: list[str] = Field(default_factory=list)  # used when the case is closed


class A5Output(_Model):
    narrative: dict[str, str] = Field(default_factory=dict)  # report section -> text
    changes_summary: str = ""  # the "why" for changelog[-1].summary


def new_case(case_id: str) -> CaseState:
    """Empty case at version 0. A0 bumps to version 1 on the first versioned turn."""
    return CaseState(case_id=case_id, version=0)
