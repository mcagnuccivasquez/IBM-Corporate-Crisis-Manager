# A2 — Impact & Risk Assessors (A2a Reputational · A2b Economic · A2c Legal/Regulatory) + risk engine

> **New chat? Load in this order:** `AGENTS.md` → `STATUS.md` → `PROJECT.md` (esp. §4, §6, §8) → this file.
> **Owns:** `src/agents/a2_impact.py` (one module, three domain configs), `src/prompts/a2_common.md`, `a2_reputational.md`, `a2_economic.md`, `a2_legal.md`, **`src/risk.py`**, `tests/test_risk.py`, `tests/test_a2_*.py`.
> One shared spec on purpose: the three sub-agents share the method and output schema and differ only in domain lens.

## 1. Mission
For each domain, explain **what the impact is, who it hits, how bad it is and how likely, and what happens if nothing is done**, then give a Severity and Likelihood score with reasons.
The **overall level is not decided here**. `risk.py` computes it from the three domain scores (PROJECT §6).

## 2. Input (same for all three)
- `claims` (with status/strength), `sources`, `focus`, previous `impacts` + previous `risk` (to explain changes), current `actions` and their statuses (completed or verified actions can lower likelihood), KB (cached).

## 3. Output (one object per domain)
```json
{
  "domain": "economic",
  "severity": 3, "severity_reason": "Replacement exposure up to ~€330k if all 11,000 channel units of both batches were replaced (KB-12 €30/unit × KB-13 delivered qty); realistic scope smaller since delivered ≠ sold",
  "likelihood": 2, "likelihood_reason": "Single unconfirmed report (C-007); no lab result yet",
  "impacts": [{
    "description": "...", "if_unaddressed": "...", "timeframe": "24h|7d|30d",
    "stakeholders": ["Retail partners DE", "Finance"], "source_ids": ["KB-12", "KB-13", "C-007"],
    "basis": "company_data | precedent | general_knowledge"
  }],
  "floor_triggers": ["F1"],             // F1/F2/F3 conditions observed (risk.py decides)
  "evidence_confidence": "low",         // from the statuses of the claims used
  "change_vs_previous": "Likelihood 1→2 because of new independent report U-04"
}
```

## 4. Domain lenses

**A2a Reputational:** public visibility and spread (views, reposts, media pick-up, independence of reports), customer trust, retailer perception, social norms and expectations (safety and privacy are high-sensitivity topics; perceived evasiveness or blaming the customer escalates). Precedent: the TravelPlug handling (KB-07/08). A short acknowledgement and private follow-up worked, but questions kept coming after the answer (9 the next morning), so visibility of the answer matters. Never treat TravelPlug as evidence about PCX.

**A2b Economic:** use **only** KB-12 assumptions + KB-13 quantities + KB-01 scale. Always show **scoped ranges** (e.g. warehouse-only hold: €5k per batch; replacement of delivered units: lower bound = confirmed affected, upper bound = delivered units of the suspect batch(es)). State that delivered ≠ sold. Exclusions listed by Finance (lost sales, retailer effects, legal, campaigns) are named as *not estimated*. No multiplying by all units ever shipped without justification. Large remedy → CEO involvement is a fact to mention.

**A2c Legal/Regulatory:** product safety (possible hazard in market: duties to assess and, if confirmed, to notify authorities and take corrective action) and personal data (SafeCam: possible unauthorised access to accounts/recordings → DPO assessment, possible breach notification deadlines). These come from **general knowledge** → label `basis: "general_knowledge"` and phrase as "may require / Legal to confirm", never as legal advice. Company facts: Sophie Laurent (Legal/DPO) must be involved for injury, authority requests, or personal data (KB-02, KB-04, KB-08, KB-09). Flag consumer-claim and retailer-contract exposure only as possibilities.

## 5. Scoring rules
- Use the anchors in PROJECT §6 **exactly**. Quote the anchor you matched in `severity_reason`.
- Likelihood reflects exposure and spread in the world. Evidence strength goes in `evidence_confidence`. Don't double count.
- Report `floor_triggers` whenever the condition is present, even if the score is already high.
- Completed or verified actions may reduce likelihood. Proposed actions may **not**.
- Focus: deeper analysis and ordering only, **never** a higher score (D-005).
- Each impact needs `source_ids` or `basis: general_knowledge`.

## 6. Risk engine (`src/risk.py`) — pure code
```python
def compute_risk(domains: list[DomainAssessment], prev_level: str | None,
                 claim_changes: list, action_changes: list) -> Risk:
    # 1. score = S*L per domain; max_score
    # 2. level = Low(1-3) / Medium(4-6) / High(8-9) / Critical(12-16)
    # 3. floors: F2 → Critical; F1 or F3 → at least High
    # 4. F4: if level < prev_level and no claim disproved/downgraded and no action verified_effective → keep prev_level, add reason
    # 5. reasons: one line per domain + one per floor applied; evidence_confidence = lowest of the domains driving the level
```
Unit tests: every score → level boundary, each floor, F4 guard both ways, reasons text present.

## 7. Draft runtime prompt — common part (`a2_common.md`)
```
You are the {DOMAIN} impact assessor in ACME's crisis-management system. Using only the evidence ledger, the ACME
knowledge base and clearly labelled general knowledge, describe the {DOMAIN} impacts of the situation: what could
happen, to whom, within what timeframe, and what happens if ACME does nothing. Then score Severity and Likelihood from
1 to 4 using the anchors provided, quoting the anchor you matched. Likelihood reflects exposure and spread in the
world; evidence confidence is reported separately and must not change your scores. Report any floor trigger (F1-F3)
you observe. Cite claim or source IDs for every impact. If you rely on general knowledge, label it. Do not recommend
actions; another agent does that. Explain what changed versus the previous assessment and why.
```
Then append the domain lens from §4 and the anchor table from PROJECT §6.

## 8. Acceptance tests
- [ ] S1 turn 1 (single unconfirmed smoke post): reputational ≈ S3×L2, legal flags F1, `risk.py` → **High** with reason "F1 floor".
- [ ] Economic output never multiplies €30 by total shipped units without scope, and always shows a range + exclusions.
- [ ] Legal output labels regulatory duties as general knowledge and names Sophie Laurent.
- [ ] Same input twice → same S/L (run 3×, allow ≤1 point variance; tighten the prompt if more).
- [ ] Turn where the claim is disproved → likelihood drops, F4 allows de-escalation, reasons cite the disproved claim.
