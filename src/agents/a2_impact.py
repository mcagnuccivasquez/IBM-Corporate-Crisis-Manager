"""
a2_impact.py — A2 Impact & Risk Assessment Agent (coordinator + three domain sub-agents).

Owner: A2 (Junda).
Owns: this file, src/prompts/a2_*.md, src/risk.py, tests/test_risk.py, tests/test_a2_*.py.

Architecture
------------
  run(state, turn, domain)  — public entry point called by A0 pipeline for each domain.
  _build_prompt()           — assembles the system prompt from the common + domain-specific parts.
  _build_user_content()     — builds the volatile user-turn content block.
  _stub_domain_assessment() — deterministic stub used by the pipeline's "Stub agents" switch.

The pipeline (src/pipeline.py) calls run() three times in parallel (once per domain) and
then calls compute_risk() from src/risk.py to combine the three DomainImpact results.

Signature (matches pipeline.py AgentSet.a2 slot):
    run(state: CaseState, turn: TurnInput, domain: Domain) -> DomainImpact

LLM calls
---------
Always calls call_structured from src/llm.py. Without a valid ANTHROPIC_API_KEY that
raises a clear LLMError — it never silently returns [STUB] scores in the live app.
Cost-free / CI runs use the pipeline's built-in stub switch (--stubs / use_stubs=True),
which replaces A2 with stubs.a2 before run() is ever called.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.contracts import (
    CaseState,
    Claim,
    Confidence,
    Domain,
    DomainImpact,
    FloorId,
    ImpactItem,
    Source,
    Stakeholder,
    TurnInput,
)

from src.kb import unknown_kb_ids
from src.llm import call_structured  # type: ignore[import]

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


# ---------------------------------------------------------------------------
# Public entry point (called by pipeline once per domain)
# ---------------------------------------------------------------------------

def run(state: CaseState, turn: TurnInput, domain: Domain) -> DomainImpact:
    """
    Assess one impact domain (reputational | economic | legal_regulatory).

    Parameters
    ----------
    state:  CaseState after A1 has run (contains claims and sources).
    turn:   Current turn metadata.
    domain: Which domain sub-agent to run (A2a=reputational, A2b=economic, A2c=legal_regulatory).

    Returns
    -------
    DomainImpact — stored by A0 pipeline into state.impacts.<domain>.
    """
    active_claims = [c for c in state.claims if c.status not in ("disproved", "misleading")]
    prev_domain = _prev_domain(state, domain)

    system_prompt = _build_prompt(domain, prev_domain, state.focus)
    user_content = _build_user_content(domain, active_claims, state.sources, prev_domain)

    valid_source_ids = {s.source_id for s in state.sources}

    def _check_source_ids(r: DomainImpact) -> list[str]:
        problems: list[str] = []
        all_sids = [i for item in r.impacts for i in item.source_ids]
        for sid in all_sids:
            if not (sid.startswith("KB-") or sid.startswith("U-")):
                problems.append(
                    f"source_ids may only contain sources (U-xx, KB-xx); not a source: {sid}"
                )
            elif sid.startswith("U-") and sid not in valid_source_ids:
                problems.append(
                    f"source_ids references unknown U-xx source: {sid}"
                )
        problems.extend(
            f"unknown KB id {sid}"
            for sid in unknown_kb_ids([s for s in all_sids if s.startswith("KB-")])
        )
        return problems

    result: DomainImpact = call_structured(
        agent=f"A2{_domain_agent_suffix(domain)}",
        system_prompt=system_prompt,
        user_content=user_content,
        output_model=DomainImpact,
        effort="high",
        case_id=state.case_id,
        check=_check_source_ids,
    )
    # Defensively enforce the score (DomainImpact validator also does this)
    result.score = result.severity * result.likelihood
    return result


def _domain_agent_suffix(domain: Domain) -> str:
    return {"reputational": "a", "economic": "b", "legal_regulatory": "c"}[domain]


# ---------------------------------------------------------------------------
# Stakeholder derivation helper (used by A3 and exported for tests)
# ---------------------------------------------------------------------------

def derive_stakeholders(
    reputational: Optional[DomainImpact],
    economic: Optional[DomainImpact],
    legal_regulatory: Optional[DomainImpact],
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
    if reputational and reputational.severity >= 3:
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
    if economic and economic.severity >= 2:
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
    if legal_regulatory and (legal_regulatory.severity >= 3 or legal_regulatory.floor_triggers):
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
# Prompt assembly
# ---------------------------------------------------------------------------

def _build_prompt(
    domain: Domain,
    prev_domain: Optional[DomainImpact],
    focus: Optional[str],
) -> str:
    """
    Assemble the system prompt: common part + domain-specific lens + anchor table.
    Reads from src/prompts/a2_common.md and src/prompts/a2_<domain>.md.
    """
    domain_file_map: dict[Domain, str] = {
        "reputational":     "a2_reputational.md",
        "economic":         "a2_economic.md",
        "legal_regulatory": "a2_legal.md",
    }

    common_path = PROMPTS_DIR / "a2_common.md"
    domain_path = PROMPTS_DIR / domain_file_map[domain]

    common_text = common_path.read_text(encoding="utf-8") if common_path.exists() else ""
    domain_text = domain_path.read_text(encoding="utf-8") if domain_path.exists() else ""

    domain_label = {
        "reputational":     "Reputational",
        "economic":         "Economic",
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
            f"\n\n## Previous assessment\n"
            f"Severity={prev_domain.severity}, Likelihood={prev_domain.likelihood}, "
            f"score={prev_domain.score}. Explain what changed and why in severity_reason / "
            "likelihood_reason."
        )

    return prompt


def _build_user_content(
    domain: Domain,
    claims: list[Claim],
    sources: list[Source],
    prev_domain: Optional[DomainImpact],
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
    prev_domain: Optional[DomainImpact],
) -> DomainImpact:
    """
    Returns a minimal but schema-valid DomainImpact derived purely from claim data.

    Rules (conservative, no invented facts):
    - severity / likelihood start at 1.
    - Any confirmed claim on this domain → severity at least 3, likelihood at least 3.
    - Any unconfirmed claim on this domain → severity at least 2, likelihood at least 2.
    - Smoke/fire/injury keywords in claim text → F1 trigger (reputational/legal domains).
    - Unauthorised access keywords → F3 trigger (legal domain).
    """
    domain_claims = [c for c in claims if domain in c.domains] or claims

    severity: int = 1
    likelihood: int = 1
    floor_triggers: list[FloorId] = []
    source_ids: list[str] = []
    evidence_confidence: Confidence = "low"

    for c in domain_claims:
        source_ids.extend(c.source_ids)
        if c.status == "confirmed":
            severity   = max(severity,   3)
            likelihood = max(likelihood, 3)
            if c.evidence_strength == "strong":
                evidence_confidence = "high"
            elif c.evidence_strength == "moderate" and evidence_confidence != "high":
                evidence_confidence = "medium"
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

    return DomainImpact(
        severity=severity,
        severity_reason=f"[STUB] Matched anchor: '{severity_anchors[severity]}'",
        likelihood=likelihood,
        likelihood_reason=f"[STUB] Matched anchor: '{likelihood_anchors[likelihood]}'",
        impacts=[impact_item],
        floor_triggers=floor_triggers,
        evidence_confidence=evidence_confidence,
    )


# ---------------------------------------------------------------------------
# Helper: get the previous DomainImpact for a given domain
# ---------------------------------------------------------------------------

def _prev_domain(state: CaseState, domain: Domain) -> Optional[DomainImpact]:
    return getattr(state.impacts, domain, None)
