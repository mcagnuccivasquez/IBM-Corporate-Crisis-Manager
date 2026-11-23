# S1 · Turn 4 — Expected output (CLOSE)

**Scenario:** PCX-100 overheating (main demo)
**Turn:** 4 of 4

---

## Must-have outputs

### Status
- `status` = **`"closed"`**
- `closure` object must be **non-null** and contain:
  - `remaining_risk`: narrative of residual risk (batch B still in hold; batch A cleared; no new incidents)
  - `open_actions`: list of any actions not yet `verified_effective` (batch hold on B should become `verified_effective` given 5 days no incidents)
  - `reopen_conditions`: concrete, observable triggers (see below)

### Risk level
- `risk.level` = **`"Medium"`** or **`"High"`** — reduced from Critical
- **F4 de-escalation must be justified**: level drops because:
  1. C-001 (smoke/melt) is still `confirmed` but contained — no new incidents in 5 days
  2. ACT-001 (batch B hold) reaches `verified_effective` (5 days no incidents = result evidence)
  3. Batch A cleared by lab (new claim: `confirmed`, `disproved` scope of defect to batch B only)
- `risk.reasons` must name which claim or action justified the drop (F4 rule)

### Claims
- New claim: **PCX-2609-A samples within spec** — `status: "confirmed"`, `evidence_strength: "strong"`, `batch: "PCX-2609-A"`, `domains: ["legal_regulatory", "economic"]`
- New claim: **no new smoke/fire reports in 5 days post-hold** — `status: "confirmed"`, `evidence_strength: "moderate"` (user report, not independent audit)
- C-001 remains `confirmed` — it is not disproved; a real incident occurred

### Actions
- `ACT-001` (batch B hold) status → **`"verified_effective"`**
  - `result_evidence_source_ids` must include the "no new incidents" source
- Monitoring action from turn 3 → **`"completed"`** (baseline restored) or kept `in_progress` with note
- All remaining open actions must be listed in `closure.open_actions`

### Reopen conditions (A4 spec §3 — required on CLOSE)
Must include concrete, observable triggers such as:
- Any new smoke, fire, or electric shock report on any PCX-100 unit
- Any contact from an authority (national market surveillance, product-safety body)
- Lab finding of a defect outside batch PCX-2609-B
- Rising heat ticket trend above baseline (e.g. >5 in a week) with no other explanation

### Outlook (final)
- `residual_risk_if_p1_effective`: not applicable on close — use `closure.remaining_risk` instead
- Final `pattern_warnings` should still flag the KB-06 and KB-11 traps for the record

---

## Must-NOT-have outputs

| Check ID | What must NOT appear |
|---|---|
| T6 | VN-3 must NOT be cited as evidence that batch A was always safe — it was the new lab test, not VN-3, that cleared batch A |
| T7 | No unscoped cost claim (must reference batch B scope, not all 16,000 units) |
| **F4** | Risk must NOT drop without naming the specific claim or action that justified it |
| R18 | The case close must NOT be presented as a guarantee that no further incidents can occur — it is a recommendation to close, not a clearance of all risk |

---

## Risk calculation check (manual — post-close)

| Domain | S | L | Score |
|---|---|---|---|
| Reputational | 2 | 1 | 2 → Low (hold done, statement visible, baseline restored) |
| Economic | 2 | 2 | 4 → Medium (batch B still held; replacement costs for confirmed units) |
| Legal/regulatory | 2 | 1 | 2 → Low (legal confirmed no authority notification; defect scoped to batch B) |
| **Max domain score** | | | **4 → Medium** |
| **F2 no longer applies** | | | ACT-001 `verified_effective`; no new incidents |
| **F4 satisfied** | | | ACT-001 → verified_effective named in reasons |

Final level: **Medium**

---

## Closure block check

```json
"closure": {
  "remaining_risk": "Batch PCX-2609-B remains under warehouse hold. 5,000 units were delivered to DE/IT/FR channels; not all will have been sold. Batch PCX-2609-A cleared by lab. No new smoke/fire reports in 5 days post-hold. Residual risk: units already in consumers' hands from batch B.",
  "open_actions": ["ACT-001 batch hold — ongoing until Quality determines disposition of held stock"],
  "reopen_conditions": [
    "Any new smoke, fire, burning, or electric shock report on any PCX-100 unit",
    "Any contact from a national market surveillance or product-safety authority",
    "Lab finding of a thermal defect outside batch PCX-2609-B",
    "Heat ticket volume rising above baseline (>5 per week) without an identified cause"
  ]
}
```

---

## Changelog check

- `risk_from` = `"Critical"`, `risk_to` = `"Medium"`
- `changelog.summary` must name: ACT-001 → verified_effective; batch A cleared by lab
- `action_changes` includes ACT-001 → verified_effective

---

## A4 QA verdict expectation

`qa.verdict = "PASS"` if:
- Risk drops with F4 justification (names ACT-001 verified_effective + batch A cleared)
- `closure.reopen_conditions` is non-empty and concrete
- C-001 remains `confirmed` (the incident happened; it is not disproved)
- No T6, T7, R18 violations

`qa.verdict = "REVISE"` if:
- Risk drops without F4 justification → blocking, M6
- `closure.reopen_conditions` is empty or vague → blocking, A4 spec §3
- C-001 is set to `disproved` without evidence of that → blocking, G2

---

## Appendix C safety net expectation

`report.narrative_warnings = []` (empty list)

**What must NOT appear in Appendix C:**

| Category | Why it must not fire |
|---|---|
| Banned phrase "all units tested" | Batch A was cleared by lab test, not by testing "all units"; action/impact text must not over-generalise |
| Banned phrase "authorities contacted" | Closure summary must not state authorities were notified unless Legal/DPO confirmed a notification was filed |
| Banned phrase "remote fix for PCX-100" | Closure narrative must not suggest any firmware or OTA remedy |
| Personal data | No customer names, handles, or contact details in closure action, stakeholder, impact, or outlook texts |
| Blame wording | The defect was a manufacturing issue in batch B — closure text must not shift responsibility to customers |

**On CLOSE turns, `reopen_conditions` are also checked.** Each reopen condition must be concrete and observable (e.g. "any new smoke/fire report on PCX-100") — not vague ("if anything goes wrong"). Vague conditions do not trip the safety net but do trigger a T12-adjacent issue in A4's LLM review.
