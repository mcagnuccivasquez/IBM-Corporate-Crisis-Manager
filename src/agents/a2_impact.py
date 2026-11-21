"""
a2_impact.py — A2 Impact & Risk Assessment Agent (coordinator + three domain sub-agents).

Owner: A2 (Junda).
Owns: this file, src/prompts/a2_*.md, src/risk.py, tests/test_risk.py, tests/test_a2_*.py.

Architecture
------------
  run()           — public entry point called by A0 pipeline.
  _run_domain()   — calls one domain sub-agent (A2a / A2b / A2c) via the LLM.
  _build_prompt() — assembles the system prompt from the common + domain-specific parts.

Each sub-agent returns a DomainAssessment.  The coordinator combines them, calls risk.py,
and returns an A2Output that A0 merges into CaseState.

LLM calls
---------
The file imports `call_structured` from src/llm.py (owned by A0/Matteo).
Until llm.py is published, _STUB_MODE=True routes through a local stub that returns
fixture-driven responses so A2 is fully testable without an Anthropic key.

Do NOT invent LLM responses in production code. When STUB_MODE is off, every domain
assessment comes from the actual Claude response parsed into DomainAssessment.
"""

from __future__ import annotations

import concurrent.futures
import os
from pathlib import Path
from typing import Optional

from src.contracts import (
    CaseState,
    Claim,
    ClaimStatus,
    Domain,
    DomainAssessment,
    EvidenceConfidence,
    FloorTrigger,
    ImpactItem,
    ImpactsBlock,
    RiskBlock,
    Source,
    Stakeholder,
    TurnInput,
)
from src.risk import ActionChange, ClaimChange, compute_risk

# ---------------------------------------------------------------------------
# Stub mode — used when llm.py is not yet available or ANTHROPIC_API_KEY unset
# ---------------------------------------------------------------------------
_STUB_MODE: bool = not os.environ.get("ANTHROPIC_API_KEY")

try:
    from src.llm import call_structured  # type: ignore[import]
except ImportError:
    _STUB_MODE = True
    call_structured = None  # type: ignore[assignment]

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


# ---------------------------------------------------------------------------
# Output model (returned to A0)
# ---------------------------------------------------------------------------

from pydantic import BaseModel, Field


class A2Output(BaseModel):
    """
    A2's contribution to CaseState.  A0 merges these fields.
    Fields match CaseState exactly so A0 can do:
        state.impacts = output.impacts
        state.risk    = output.risk
        state.stakeholders = output.stakeholders   # initial list; A3 enriches it
    """
    impacts: ImpactsBlock
    risk: RiskBlock
    stakeholders: list[Stakeholder] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(state: CaseState, turn: TurnInput) -> A2Output:
    """
    Run A2: assess reputational, economic, and legal/regulatory impacts in parallel,
    then compute the overall risk via risk.py.

    Parameters
    ----------
    state:  CaseState from the previous version (v N-1); contains A1's claims/sources.
    turn:   Current turn metadata (intent, user_text, attachments).

    Returns
    -------
    A2Output ready for A0 to merge into the new CaseState version.
    """
    # Gather inputs that every sub-agent needs
    active_claims = [c for c in state.claims if c.status not in ("disproved", "misleading")]
    all_sources   = state.sources
    prev_impacts  = state.impacts
    prev_risk     = state.risk

    # Build claim_changes and action_changes for the F4 guard
    claim_changes  = _extract_claim_changes(state)
    action_changes = _extract_action_changes(state)

    # -----------------------------------------------------------------
    # Run A2a, A2b, A2c in parallel (PROJECT §3.2)
    # -----------------------------------------------------------------
    domains_to_run: list[Domain] = ["reputational", "economic", "legal_regulatory"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            domain: pool.submit(
                _run_domain,
                domain=domain,
                claims=active_claims,
                sources=all_sources,
                prev_domain=_prev_domain(prev_impacts, domain),
                focus=state.focus,
            )
            for domain in domains_to_run
        }
        results: dict[Domain, DomainAssessment] = {}
        for domain, fut in futures.items():
            results[domain] = fut.result()

    impacts = ImpactsBlock(
        reputational=results["reputational"],
        economic=results["economic"],
        legal_regulatory=results["legal_regulatory"],
    )

    # -----------------------------------------------------------------
    # Compute overall risk (pure code — no LLM)
    # -----------------------------------------------------------------
    risk = compute_risk(
        domains=list(results.values()),
        prev_level=prev_risk.level if prev_risk else None,
        claim_changes=claim_changes,
        action_changes=action_changes,
    )

    # -----------------------------------------------------------------
    # Derive initial stakeholder list (A3 will enrich this)
    # -----------------------------------------------------------------
    stakeholders = _derive_stakeholders(results, active_claims)

    return A2Output(impacts=impacts, risk=risk, stakeholders=stakeholders)


# ---------------------------------------------------------------------------
# Domain sub-agent dispatcher
# ---------------------------------------------------------------------------

def _run_domain(
    domain: Domain,
    claims: list[Claim],
    sources: list[Source],
    prev_domain: Optional[DomainAssessment],
    focus: Optional[str],
) -> DomainAssessment:
    """
    Run one domain sub-agent (A2a / A2b / A2c).

    In production: calls Claude via call_structured(), parsing the response into
    DomainAssessment.  In stub mode: returns a fixture-driven assessment based on
    the claims present in the state (useful for testing without an API key).
    """
    if _STUB_MODE or call_structured is None:
        return _stub_domain_assessment(domain, claims, prev_domain)

    system_prompt = _build_prompt(domain, prev_domain, focus)
    user_content  = _build_user_content(domain, claims, sources, prev_domain)

    # call_structured is provided by A0's llm.py:
    #   call_structured(agent_name, system_prompt, user_content, output_model, effort)
    # It returns a validated Pydantic object.
    result: DomainAssessment = call_structured(
        agent_name=f"A2_{domain}",
        system_prompt=system_prompt,
        user_content=user_content,
        output_model=DomainAssessment,
        effort="high",
    )
    # Defensively enforce the domain tag (the LLM must not change it)
    result.domain = domain
    result.score  = result.severity * result.likelihood
    return result


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

def _build_prompt(
    domain: Domain,
    prev_domain: Optional[DomainAssessment],
    focus: Optional[str],
) -> str:
    """
    Assemble the system prompt: common part + domain-specific lens + anchor table.
    Reads from src/prompts/a2_common.md and src/prompts/a2_<domain>.md.
    """
    domain_file_map: dict[Domain, str] = {
        "reputational":    "a2_reputational.md",
        "economic":        "a2_economic.md",
        "legal_regulatory": "a2_legal.md",
    }

    common_path = PROMPTS_DIR / "a2_common.md"
    domain_path = PROMPTS_DIR / domain_file_map[domain]

    common_text = common_path.read_text(encoding="utf-8") if common_path.exists() else ""
    domain_text = domain_path.read_text(encoding="utf-8") if domain_path.exists() else ""

    domain_label = {
        "reputational":    "Reputational",
        "economic":        "Economic",
        "legal_regulatory": "Legal/Regulatory",
    }[domain]

    prompt = common_text.replace("{DOMAIN}", domain_label)
    prompt += "\n\n" + domain_text

    if focus:
        prompt += (
            f"\n\n## Focus\nThe user has set focus: '{focus}'. "
            "This affects the depth of your analysis and the ordering of impacts, "
            "but NEVER changes your Severity or Likelihood scores."
        )

    if prev_domain:
        prompt += (
            f"\n\n## Previous assessment (v{prev_domain.domain})\n"
            f"Severity={prev_domain.severity}, Likelihood={prev_domain.likelihood}, "
            f"score={prev_domain.score}. Explain what changed and why in change_vs_previous."
        )

    return prompt


def _build_user_content(
    domain: Domain,
    claims: list[Claim],
    sources: list[Source],
    prev_domain: Optional[DomainAssessment],
) -> str:
    """Build the user-turn content block sent to the LLM."""
    # Filter claims relevant to this domain
    domain_claims = [c for c in claims if domain in c.domains]
    if not domain_claims:
        domain_claims = claims  # fall back to all claims if no domain tag

    claim_lines = "\n".join(
        f"- [{c.claim_id}] {c.text} "
        f"(status={c.status}, strength={c.evidence_strength}, "
        f"sources={c.source_ids})"
        for c in domain_claims
    )

    source_lines = "\n".join(
        f"- [{s.source_id}] {s.title} "
        f"(category={s.category}, time_relevance={s.time_relevance}, "
        f"reliability={s.reliability_note or 'n/a'})"
        for s in sources
    )

    return (
        f"## Claims relevant to {domain}\n{claim_lines or 'None.'}\n\n"
        f"## Sources in evidence ledger\n{source_lines or 'None.'}"
    )


# ---------------------------------------------------------------------------
# Stub domain assessment (used when ANTHROPIC_API_KEY is not set)
# ---------------------------------------------------------------------------

def _stub_domain_assessment(
    domain: Domain,
    claims: list[Claim],
    prev_domain: Optional[DomainAssessment],
) -> DomainAssessment:
    """
    Returns a minimal but schema-valid DomainAssessment derived purely from claim data.

    Rules (conservative, no invented facts):
    - severity / likelihood start at 1.
    - Any confirmed claim on this domain → severity at least 3, likelihood at least 3.
    - Any unconfirmed claim on this domain → severity at least 2, likelihood at least 2.
    - Smoke/fire/injury keywords in claim text → F1 trigger (reputational/legal domains).
    - Unauthorised access keywords → F3 trigger (legal domain).
    """
    domain_claims = [c for c in claims if domain in c.domains] or claims

    severity   = 1
    likelihood = 1
    floor_triggers: list[FloorTrigger] = []
    source_ids: list[str] = []
    evidence_confidence: EvidenceConfidence = "low"

    for c in domain_claims:
        source_ids.extend(c.source_ids)
        if c.status == "confirmed":
            severity   = max(severity,   3)
            likelihood = max(likelihood, 3)
            if c.evidence_strength == "strong":
                evidence_confidence = "high"
            elif c.evidence_strength == "moderate" and evidence_confidence != "high":
                evidence_confidence = "moderate"
        elif c.status == "unconfirmed":
            severity   = max(severity,   2)
            likelihood = max(likelihood, 2)

        # Floor trigger detection (keyword-based, conservative)
        text_lower = c.text.lower()
        if any(kw in text_lower for kw in ("smoke", "smoked", "fire", "burning", "shock", "injury", "injur")):
            if domain in ("reputational", "legal_regulatory"):
                if "F1" not in floor_triggers:
                    floor_triggers.append("F1")
        if any(kw in text_lower for kw in ("unauthorised access", "unauthorized access", "account access", "recordings")):
            if domain == "legal_regulatory":
                if "F3" not in floor_triggers:
                    floor_triggers.append("F3")

    source_ids = list(dict.fromkeys(source_ids))  # deduplicate, preserve order

    # Build a minimal impact item
    if domain_claims:
        impact_description = (
            f"[STUB] {len(domain_claims)} claim(s) touch this domain. "
            "Replace with LLM assessment in production."
        )
        impact_unaddressed = (
            "If unaddressed, the situation may escalate. "
            "Specific consequences require LLM assessment."
        )
    else:
        impact_description = "[STUB] No claims found for this domain."
        impact_unaddressed = "No specific consequences identified from available claims."

    impact_item = ImpactItem(
        description=impact_description,
        if_unaddressed=impact_unaddressed,
        timeframe="7d",
        stakeholders=["Customers", "ACME"],
        source_ids=source_ids,
        basis="company_data",
    )

    severity_anchors = {
        1: "Minor: isolated, single customer, no safety/data dimension, cost < €10k",
        2: "Moderate: several customers or limited public visibility; cost €10k–100k",
        3: "Major: safety or data question on a product line in market; broad public attention; cost €100k–1M",
        4: "Severe: confirmed injury/fire, confirmed data access, authority action; cost > €1M",
    }
    likelihood_anchors = {
        1: "Remote: claim disproved or no plausible mechanism; no exposure",
        2: "Possible: single unverified report; limited reach",
        3: "Likely: multiple independent reports or defect confirmed; reach growing",
        4: "Occurring: harm, media coverage, or authority action already happening",
    }

    change_note = None
    if prev_domain and (
        prev_domain.severity != severity or prev_domain.likelihood != likelihood
    ):
        change_note = (
            f"S{prev_domain.severity}→S{severity}, "
            f"L{prev_domain.likelihood}→L{likelihood} based on updated claim statuses."
        )

    return DomainAssessment(
        domain=domain,
        severity=severity,
        severity_reason=f"[STUB] Matched anchor: '{severity_anchors[severity]}'",
        likelihood=likelihood,
        likelihood_reason=f"[STUB] Matched anchor: '{likelihood_anchors[likelihood]}'",
        score=severity * likelihood,
        impacts=[impact_item],
        floor_triggers=floor_triggers,
        evidence_confidence=evidence_confidence,
        change_vs_previous=change_note,
    )


# ---------------------------------------------------------------------------
# Stakeholder derivation (initial list; A3 enriches)
# ---------------------------------------------------------------------------

def _derive_stakeholders(
    results: dict[Domain, DomainAssessment],
    claims: list[Claim],
) -> list[Stakeholder]:
    """
    Derive an initial stakeholder list from claims and domain assessments.
    A3 (Action Planner) produces the full enriched stakeholder map.
    This satisfies R8: identify directly vs potentially affected stakeholders.
    """
    stakeholders: list[Stakeholder] = []
    seen: set[str] = set()

    # Map claim markets → customer stakeholders
    markets = {c.market for c in claims if c.market}
    for market in sorted(markets):
        name = f"Customers in {market}"
        if name not in seen:
            seen.add(name)
            stakeholders.append(Stakeholder(
                name=name,
                type="external",
                interest="Product safety and reliability",
                impact="Directly affected if defect is confirmed",
                acme_contact="Tom Weber (Customer Care)",
            ))

    # Reputational domain → public / media
    rep = results.get("reputational")
    if rep and rep.severity >= 3:
        if "Media / Public" not in seen:
            seen.add("Media / Public")
            stakeholders.append(Stakeholder(
                name="Media / Public",
                type="external",
                interest="Consumer safety and corporate accountability",
                impact="Potentially affected by reputational escalation",
                acme_contact="Anna Keller (Communications)",
            ))

    # Economic domain → retail partners
    eco = results.get("economic")
    if eco and eco.severity >= 2:
        if "Retail partners" not in seen:
            seen.add("Retail partners")
            stakeholders.append(Stakeholder(
                name="Retail partners",
                type="external",
                interest="Supply reliability and product safety",
                impact="Potentially affected by stock holds or returns",
                acme_contact="Luca Ferri (Supply Chain)",
            ))

    # Legal domain → regulators
    leg = results.get("legal_regulatory")
    if leg and (leg.severity >= 3 or leg.floor_triggers):
        if "Regulatory authorities" not in seen:
            seen.add("Regulatory authorities")
            stakeholders.append(Stakeholder(
                name="Regulatory authorities",
                type="external",
                interest="Consumer safety and data protection compliance",
                impact="Potentially notified if product safety or data incident confirmed",
                acme_contact="Sophie Laurent (Legal/DPO)",
            ))

    # Always include ACME internal stakeholders
    for name, contact in [
        ("ACME Quality team",       "Maya Chen (Quality)"),
        ("ACME Supply Chain",       "Luca Ferri (Supply Chain)"),
        ("ACME Legal / DPO",        "Sophie Laurent (Legal/DPO)"),
        ("ACME Communications",     "Anna Keller (Communications)"),
        ("ACME Finance",            "Marco Bianchi (Finance)"),
    ]:
        if name not in seen:
            seen.add(name)
            stakeholders.append(Stakeholder(
                name=name,
                type="internal",
                interest="Incident management and business continuity",
                impact="Directly involved in response",
                acme_contact=contact,
            ))

    return stakeholders


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prev_domain(
    prev_impacts: ImpactsBlock,
    domain: Domain,
) -> Optional[DomainAssessment]:
    return getattr(prev_impacts, domain if domain != "legal_regulatory" else "legal_regulatory", None)


def _extract_claim_changes(state: CaseState) -> list[ClaimChange]:
    """Extract claim status changes that happened in the current version."""
    changes: list[ClaimChange] = []
    current_version = state.version
    for c in state.claims:
        for h in c.change_history:
            if h.version == current_version:
                changes.append(ClaimChange(
                    claim_id=c.claim_id,
                    from_status=h.from_status,
                    to_status=h.to_status,
                ))
    return changes


def _extract_action_changes(state: CaseState) -> list[ActionChange]:
    """Extract action status changes that happened in the current version."""
    changes: list[ActionChange] = []
    current_version = state.version
    for a in state.actions:
        for h in a.status_history:
            if h.version == current_version:
                changes.append(ActionChange(
                    action_id=a.action_id,
                    from_status=h.from_status,
                    to_status=h.to_status,
                ))
    return changes
