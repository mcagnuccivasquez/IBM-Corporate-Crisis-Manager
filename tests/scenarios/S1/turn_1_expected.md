# S1 · Turn 1 — Expected output

**Scenario:** PCX-100 overheating (main demo)
**Turn:** 1 of 4

---

## Must-have outputs

### Risk level
- `risk.level` = **`"High"`**
- `risk.floors_applied` contains **`"F1"`**
- `risk.previous_level` = `null` (first version)
- `risk.evidence_confidence` = `"low"`

### Claims
- At least one claim with `product = "PCX-100"`, `market = "DE"`, `status = "unconfirmed"`, `evidence_strength = "weak"`
- `source_ids` references the uploaded screenshot source (e.g. `"U-01"`)
- `domains` includes at least `"reputational"` and `"legal_regulatory"`

### Sources
- The screenshot is registered as a source with `category = "incident_evidence"`, `origin = "user_upload"`, `time_relevance = "current"`
- `reliability_note` acknowledges it is a screenshot (cannot independently verify)

### Actions
- At least one P1 action to **retrieve and test a sample unit** (`timing = "within 24h"` or `"within 48h"`)
- At least one P1 action for a **public holding statement** (social media acknowledgement)
- Each major action has `options_considered` with ≥ 2 options and `chosen` flags
- Actions cite `basis_source_ids` from the KB (e.g. `KB-02`, `KB-08`)

### Outlook
- `outlook.assumptions` is **non-empty**
- `outlook.cannot_estimate` is **non-empty** (must include something about units sold vs delivered)
- `outlook.pattern_warnings` warns against using the KB-06 cable explanation for smoke/melt reports

### Open questions
- At least one open question about the **batch** of the reported unit

---

## Must-NOT-have outputs

| Check ID | What must NOT appear |
|---|---|
| T3 | The screenshot must NOT be treated as proof (claim status must be `"unconfirmed"`, not `"confirmed"`) |
| T4 | Ticket counts from KB-05 (18 heat reports) must NOT be presented as a failure rate |
| T5 | The #4471 cable-fault explanation (KB-06) must NOT be used to explain or dismiss the smoke/melt report |
| T6 | VN-3 (KB-11, July sampling) must NOT be cited to claim September batches are safe |
| T7 | Economic cost must NOT be calculated as `16,000 × €30` without scope justification; `delivered ≠ sold` must be noted if costs are estimated |
| T8 | No claim that a firmware or remote fix is possible for PCX-100 (it has no network capability, KB-03) |
| T11 | Holding statement wording must NOT claim "all units tested" or "authorities contacted" |
| T12 | No large remedy (batch recall/withdrawal) proposed without CEO (Daniel Moretti) approval pathway |

---

## Risk calculation check (manual)

| Domain | S | L | Score |
|---|---|---|---|
| Reputational | 3 | 2 | 6 → Medium |
| Economic | 2 | 2 | 4 → Medium |
| Legal/regulatory | 3 | 2 | 6 → Medium |
| **Max domain score** | | | **6 → Medium** |
| **F1 floor applied** | | | **→ High** |

F1 condition is met: credible unconfirmed report of smoke/melting on a product in market (DE).
Final level: **High** (not Critical — no confirmed injury, no authority contact yet).

---

## A4 QA verdict expectation

For a clean v1 fixture state: `qa.verdict = "PASS"`, `qa.issues = []`

(A4 acceptance test: "Clean S1 v1 → PASS" — from A4 spec §8)
