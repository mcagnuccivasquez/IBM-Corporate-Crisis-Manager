"""
contracts.py — Shared Pydantic models for the ACME Corporate Crisis Manager.

This is the LOCAL STUB used by A2 until Matteo (A0) publishes the official version.
Every field name and type mirrors PROJECT.md §4 exactly so the import swap is mechanical:
    replace `from src.contracts import ...` with the official import path.

Owner: A0 (Matteo). Do NOT change field names here without a director-review entry.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations (string literals used as enum values throughout)
# ---------------------------------------------------------------------------

ClaimStatus = Literal["confirmed", "unconfirmed", "disproved", "misleading"]
EvidenceStrength = Literal["strong", "moderate", "weak"]
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
RiskLevel = Literal["Low", "Medium", "High", "Critical"]
EvidenceConfidence = Literal["low", "moderate", "high"]
ImpactBasis = Literal["company_data", "precedent", "general_knowledge"]
ActionStatus = Literal[
    "proposed",
    "approved",
    "in_progress",
    "completed",
    "verified_effective",
    "verified_ineffective",
    "dropped",
]
ActionPriority = Literal["P1", "P2", "P3"]
ActionTimeframe = Literal["24h", "7d", "30d"]
Domain = Literal["reputational", "economic", "legal_regulatory"]
CaseStatus = Literal["open", "closed"]
TurnIntent = Literal["NEW_INFO", "ACTION_UPDATE", "SET_FOCUS", "QUESTION", "CLOSE"]
FloorTrigger = Literal["F1", "F2", "F3"]


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------

class Source(BaseModel):
    source_id: str                              # KB-01..KB-13 or U-01, U-02, …
    title: str
    file: Optional[str] = None                  # relative path inside the repo
    origin: SourceOrigin
    date: Optional[str] = None                  # date of content (not upload)
    category: SourceCategory
    time_relevance: TimeRelevance
    duplicate_of: Optional[str] = None          # source_id of the original
    reliability_note: Optional[str] = None
    added_in_version: int


# ---------------------------------------------------------------------------
# Claim
# ---------------------------------------------------------------------------

class ClaimHistory(BaseModel):
    model_config = {"populate_by_name": True}

    version: int
    from_status: Optional[ClaimStatus] = Field(None, alias="from")
    to_status: ClaimStatus = Field(..., alias="to")
    reason: str
    source_ids: list[str]


class Claim(BaseModel):
    claim_id: str                               # C-001, C-002, …
    text: str
    status: ClaimStatus
    evidence_strength: EvidenceStrength
    source_ids: list[str]
    contradicted_by: list[str] = Field(default_factory=list)
    domains: list[Domain]
    product: Optional[str] = None
    batch: Optional[str] = None
    market: Optional[str] = None
    first_seen_version: int
    last_changed_version: int
    change_history: list[ClaimHistory] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Impact domain block (written by A2a / A2b / A2c)
# ---------------------------------------------------------------------------

class ImpactItem(BaseModel):
    description: str
    if_unaddressed: str                         # what happens if ACME does nothing
    timeframe: ActionTimeframe
    stakeholders: list[str]
    source_ids: list[str]
    basis: ImpactBasis


class DomainAssessment(BaseModel):
    domain: Domain
    severity: int = Field(..., ge=1, le=4)
    severity_reason: str                        # quote the matched anchor
    likelihood: int = Field(..., ge=1, le=4)
    likelihood_reason: str
    score: int                                  # = severity × likelihood (computed by risk.py)
    impacts: list[ImpactItem]
    floor_triggers: list[FloorTrigger] = Field(default_factory=list)
    evidence_confidence: EvidenceConfidence
    change_vs_previous: Optional[str] = None    # one line explaining delta vs prior version


class ImpactsBlock(BaseModel):
    reputational: Optional[DomainAssessment] = None
    economic: Optional[DomainAssessment] = None
    legal_regulatory: Optional[DomainAssessment] = None


# ---------------------------------------------------------------------------
# Risk (written exclusively by risk.py — never by an LLM)
# ---------------------------------------------------------------------------

class RiskBlock(BaseModel):
    level: RiskLevel
    previous_level: Optional[RiskLevel] = None
    max_domain_score: int
    floors_applied: list[FloorTrigger] = Field(default_factory=list)
    reasons: list[str]                          # one line per domain + one per floor applied
    evidence_confidence: EvidenceConfidence     # lowest of the domains driving the level


# ---------------------------------------------------------------------------
# Stakeholder
# ---------------------------------------------------------------------------

class Stakeholder(BaseModel):
    name: str
    type: Literal["internal", "external"]
    interest: str
    impact: str
    acme_contact: Optional[str] = None


# ---------------------------------------------------------------------------
# Action
# ---------------------------------------------------------------------------

class ActionOption(BaseModel):
    option: str
    pros: str
    cons: str
    chosen: bool


class ActionHistory(BaseModel):
    model_config = {"populate_by_name": True}

    version: int
    from_status: Optional[ActionStatus] = Field(None, alias="from")
    to_status: ActionStatus = Field(..., alias="to")
    reason: str


class Action(BaseModel):
    action_id: str                              # ACT-001, ACT-002, …
    title: str
    what_it_does: str
    owner: str
    approver: Optional[str] = None
    timing: str
    priority: ActionPriority
    domains: list[Domain]
    status: ActionStatus
    options_considered: list[ActionOption] = Field(default_factory=list)
    basis_source_ids: list[str] = Field(default_factory=list)
    expected_effect: Optional[str] = None
    result_evidence_source_ids: list[str] = Field(default_factory=list)
    status_history: list[ActionHistory] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Outlook (A4)
# ---------------------------------------------------------------------------

class DomainProjection(BaseModel):
    domain: Domain
    severity: int = Field(..., ge=1, le=4)
    likelihood: int = Field(..., ge=1, le=4)
    reason: str
    basis_source_ids: list[str] = Field(default_factory=list)


class OutlookBlock(BaseModel):
    residual_risk_if_p1_effective: Optional[RiskLevel] = None
    domain_projection: list[DomainProjection] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    cannot_estimate: list[str] = Field(default_factory=list)
    pattern_warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# QA (A4)
# ---------------------------------------------------------------------------

class QAIssue(BaseModel):
    target: str                                 # A1 | A2a | A2b | A2c | A3
    item_id: Optional[str] = None
    check: str                                  # e.g. "T7", "G2"
    problem: str
    fix_hint: str
    blocking: bool
    resolved: bool = False


class QABlock(BaseModel):
    verdict: Literal["PASS", "REVISE"]
    issues: list[QAIssue] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Open question
# ---------------------------------------------------------------------------

class OpenQuestion(BaseModel):
    question: str
    owner: Optional[str] = None
    raised_in_version: int
    closed_in_version: Optional[int] = None


# ---------------------------------------------------------------------------
# Changelog entry
# ---------------------------------------------------------------------------

class ChangelogEntry(BaseModel):
    version: int
    risk_from: Optional[RiskLevel] = None
    risk_to: Optional[RiskLevel] = None
    new_source_ids: list[str] = Field(default_factory=list)
    claim_changes: list[str] = Field(default_factory=list)
    action_changes: list[str] = Field(default_factory=list)
    summary: Optional[str] = None              # narrative filled by A5


# ---------------------------------------------------------------------------
# Turn input
# ---------------------------------------------------------------------------

class TurnInput(BaseModel):
    intent: TurnIntent
    user_text: str
    attachments: list[str] = Field(default_factory=list)   # source_ids of uploaded files


# ---------------------------------------------------------------------------
# Closure
# ---------------------------------------------------------------------------

class ClosureBlock(BaseModel):
    remaining_risk: str
    open_actions: list[str]                     # action_ids
    reopen_conditions: list[str]


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

class ReportBlock(BaseModel):
    pdf_path: Optional[str] = None
    narrative: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# CaseState — the top-level shared contract
# ---------------------------------------------------------------------------

class CaseState(BaseModel):
    case_id: str
    version: int
    created_at: datetime
    updated_at: datetime
    status: CaseStatus = "open"
    focus: Optional[str] = None
    turn_input: Optional[TurnInput] = None

    sources: list[Source] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    impacts: ImpactsBlock = Field(default_factory=ImpactsBlock)
    risk: Optional[RiskBlock] = None
    stakeholders: list[Stakeholder] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    outlook: Optional[OutlookBlock] = None
    qa: Optional[QABlock] = None
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    changelog: list[ChangelogEntry] = Field(default_factory=list)
    closure: Optional[ClosureBlock] = None
    report: Optional[ReportBlock] = None
