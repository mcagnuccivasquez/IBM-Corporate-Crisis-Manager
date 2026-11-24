# S1 · Turn 2 — Expected output

**Scenario:** PCX-100 overheating (main demo)
**Turn:** 2 of 4

---

## Must-have outputs

### Risk level
- `risk.level` = **`"Critical"`**
- `risk.floors_applied` contains **`"F2"`** (hazardous defect confirmed in market units)
- `risk.previous_level` = `"High"` (carried from v1)
- `risk.evidence_confidence` = `"moderate"` or `"high"` (lab test = strong evidence)
- `risk.reasons` must name F2 and explain the confirmed defect in PCX-2609-B

### Claims
- C-001 status upgraded from `"unconfirmed"` → **`"confirmed"`**
  - `change_history` entry must include the lab result source, a reason, and a source_id
  - `evidence_strength` upgraded to **`"strong"`** (lab test = primary record)
- New claim added: thermal shutdown above spec confirmed in at least one PCX-2609-B unit
  - `batch` = `"PCX-2609-B"`, `product` = `"PCX-100"`, `market` = `"DE"`
  - `domains` includes `"legal_regulatory"` and `"economic"`

### Sources
- New source registered for the **Quality lab report** (user_text or user_upload): `category: "incident_evidence"`, `origin: "user_text"` or `"user_upload"`, `time_relevance: "current"`, `evidence_strength: "strong"`
- New source registered for the **DE retailer contact**: `category: "incident_evidence"`, `origin: "user_text"`, `reliability_note` noting it is a channel contact, not an authority

### Actions
- `ACT-001` (retrieve sample) status → **`"completed"`** with `result_evidence_source_ids` pointing to the new lab source
- New **P1** action: **warehouse hold on batch PCX-2609-B** (3,000 units, KB-13)
  - `owner` = `"Luca Ferri (Supply Chain)"`, `approver` = `"Elena Rossi (COO)"` (or `"Daniel Moretti (CEO)"` if treated as large remedy)
  - `timing` = `"within 24h"`, `basis_source_ids` cites KB-12 and KB-13
  - Must have ≥2 `options_considered` (e.g. hold batch B only vs. hold both batches)
- New **P1** action: **respond to DE retailer** with factual guidance
- `ACT-003` (brief Legal/DPO) must reference that F2 is now triggered; Legal must assess authority notification obligation
- `ACT-002` (holding statement) may be updated or a new action added for a more substantive public statement

### Outlook
- `residual_risk_if_p1_effective` should reflect that if the hold succeeds and batch A is cleared: **`"Medium"`** or **`"High"`** depending on whether further units in market may be affected
- `domain_projection` updated per new scores
- `assumptions` and `cannot_estimate` both non-empty

### Open questions
- Existing Q about batch identity (OQ-001) can be **closed** (batch PCX-2609-B confirmed)
- New open question: Is batch PCX-2609-A affected? (VN-3 covers July, not September batches — KB-11)
- New open question: How many PCX-2609-B units have been sold (not just delivered) to consumers? (KB-12/KB-13)

---

## Must-NOT-have outputs

| Check ID | What must NOT appear |
|---|---|
| T6 | VN-3 (KB-11) must NOT be cited to say PCX-2609-A or other batches are safe — that visit covered July units only |
| T7 | Cost must NOT be `16,000 × €30` (all units ever shipped); scope must be scoped to batch B in market; `delivered ≠ sold` |
| T8 | No claim that a firmware/remote fix is possible for PCX-100 (no network, KB-03) |
| T12 | If a full batch recall or large remedy is proposed, it must name `"Daniel Moretti (CEO)"` as approver (KB-12) |
| T12 | Authority notification decision must involve `"Sophie Laurent (Legal/DPO)"` — F2 triggered |

---

## Risk calculation check (manual)

| Domain | S | L | Score |
|---|---|---|---|
| Reputational | 3 | 3 | 9 → High (multiple reports + confirmed defect) |
| Economic | 3 | 3 | 9 → High (batch hold + replacement costs, confirmed scope) |
| Legal/regulatory | 4 | 3 | 12 → Critical (confirmed hazardous defect in market units) |
| **Max domain score** | | | **12 → Critical** |
| **F2 floor applied** | | | **→ Critical** (confirmed hazardous defect in market units) |

Final level: **Critical** — F2 condition met: hazardous defect confirmed in market units.

---

## Changelog check

- `risk_from` = `"High"`, `risk_to` = `"Critical"`
- `new_source_ids` includes the lab report source
- `claim_changes` includes C-001 `unconfirmed → confirmed`
- `action_changes` includes ACT-001 `proposed → completed`, new batch hold action `proposed`

---

## A4 QA verdict expectation

For a correctly processed v2: `qa.verdict = "PASS"`, `qa.issues = []`

Key A4 checks that must pass:
- G3: economic figures must be scoped to PCX-2609-B delivered units (5,000, KB-13), not all 16,000
- T6: VN-3 must not be used to clear other batches
- M3: Critical legal/regulatory impact must have a corresponding action (Legal briefing + authority notification plan)
- M5: ACT-001 `completed` only valid if `result_evidence_source_ids` is non-empty

---

## Appendix C safety net expectation

`report.narrative_warnings = []` (empty list)

**What must NOT appear in Appendix C:**

| Category | Why it must not fire |
|---|---|
| Banned phrase "all units tested" | The batch hold covers only PCX-2609-B (3,000 warehouse units); no text should claim all units are tested |
| Banned phrase "authorities contacted" | ACT-003 (Legal/DPO brief) is a brief, not an authority notification — wording must stay "inform" or "assess obligation", not "contacted regulators" |
| Banned phrase "remote fix for PCX-100" | No action proposes a firmware/OTA fix — the hold is a physical warehouse stop |
| Personal data | No customer names, emails, or handles appear in action, impact, stakeholder, or outlook texts |
| Blame wording | Defect is a confirmed manufacturing issue (thermal shutdown above spec); no text implies customer fault |

**T11 trap planted in this turn:** None by default. If a test variation deliberately plants "all units tested" or "authorities contacted" in an action text, A4's pre-pass must catch it as a **blocking** `qa.issues` entry before the PDF renders, so Appendix C stays empty after the revise loop.
