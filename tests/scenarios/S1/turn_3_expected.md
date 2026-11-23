# S1 · Turn 3 — Expected output

**Scenario:** PCX-100 overheating (main demo)
**Turn:** 3 of 4

---

## Must-have outputs

### Risk level
- `risk.level` = **`"Critical"`** (must stay — F2 still applies; no claim disproved, no action `verified_effective` yet)
- `risk.previous_level` = `"Critical"` (unchanged from v2)
- **F4 de-escalation guard applies**: risk may NOT drop because "hold is done" — the hold is `completed` but not `verified_effective` yet; no claim has been disproved
- `risk.reasons` must explicitly state why the level did not change

### Actions
- `ACT-001` (batch hold PCX-2609-B) status → **`"completed"`**
  - `result_evidence_source_ids` must reference the new user confirmation source
  - Must NOT be `"verified_effective"` yet — no evidence that the hold has reduced harm
- `ACT-002` (holding statement) status → **`"completed"`**
  - `result_evidence_source_ids` must reference the user confirmation source
- Retailer response action → **`"completed"`**
- New **P2** action: **monitor ticket volume trend** — 6 heat tickets this week (up from 2), no smoke/fire; Care team to flag immediately if any smoke/fire reported
- New **P2** action: **test batch PCX-2609-A samples** — rising heat ticket trend raises question of whether batch A is affected (VN-3 does not cover September batches, KB-11)

### Sources
- New source: weekly ticket summary from Customer Care (`origin: "user_text"`, `category: "company_record"`, `reliability_note` noting contacts ≠ failure rate)

### Claims
- **No new smoke/fire claim** — the 6 heat tickets report "perceived heat", not smoke or fire; they must NOT be treated as confirmed thermal fault reports (trap T4)
- Optionally: a new `unconfirmed` claim that heat ticket volume is rising, with `evidence_strength: "moderate"` and `domains: ["reputational", "economic"]`
- C-001 stays `confirmed` — no change

### Outlook
- `residual_risk_if_p1_effective` should be **`"High"`** or **`"Medium"`** — batch hold is done, but defect scope (is batch A affected?) still unknown
- `pattern_warnings` must include the warning that rising heat tickets must NOT be treated as a failure rate or as confirmed faults (trap T4)

---

## Must-NOT-have outputs

| Check ID | What must NOT appear |
|---|---|
| T4 | 6 heat tickets must NOT be presented as a failure rate or as confirmation of a wider thermal fault |
| T5 | #4471 cable explanation (KB-06) must NOT be used to explain or dismiss heat tickets |
| T6 | VN-3 (KB-11) must NOT be cited to say batch A is unaffected |
| **F4** | Risk level must NOT drop to High because "the hold is done" — hold is `completed`, not `verified_effective`; F4 guard applies |

---

## Risk calculation check (manual)

Risk must stay **Critical**:
- F2 floor still active: hazardous defect confirmed in PCX-2609-B market units (from v2); no verification that the hold has contained the harm
- F4 guard: level can only drop if a claim is disproved or an action reaches `verified_effective` — neither has happened
- Rising heat tickets do not lower risk; they may raise it if any are confirmed smoke/fire

---

## Changelog check

- `risk_from` = `"Critical"`, `risk_to` = `"Critical"`
- `changelog.summary` must explain **why** the level stayed the same (F4 guard, hold not yet verified effective)
- `action_changes` includes: ACT-001 → completed, ACT-002 → completed, new monitoring action proposed
- `new_source_ids` includes the ticket summary source

---

## A4 QA verdict expectation

`qa.verdict = "PASS"` if:
- Risk stays Critical with F4 explanation
- No trap T4 (heat tickets ≠ failure rate)
- ACT-001 is `completed` not `verified_effective` (M5 check)
- Changelog explains the unchanged level (M6 check)

`qa.verdict = "REVISE"` if:
- Risk is lowered to High because "hold is done" → blocking, F4 violation, M6
- Heat tickets are cited as confirming a wider fault → blocking, T4

---

## Appendix C safety net expectation

`report.narrative_warnings = []` (empty list)

**What must NOT appear in Appendix C:**

| Category | Why it must not fire |
|---|---|
| Banned phrase "all units tested" | No action text should claim monitoring confirmed all units safe — only batch B hold is confirmed `completed` |
| Banned phrase "authorities contacted" | Legal/DPO (Sophie Laurent) is tracking the obligation; no text should state authorities have been notified |
| Personal data | 6 heat tickets are an aggregate count — no individual customer name, email, or handle should appear in action or impact texts |
| Blame wording | Rising heat tickets must not be characterised as "customer misuse" or "user error" |

**T11 trap planted in this turn:** None by default. The natural T4 risk (presenting heat tickets as a failure rate) is a method error caught by the LLM review; it would not appear in `what_it_does` or impact texts. If a test variation adds blame wording or personal data to monitor-action texts, A4's pre-pass catches it as a blocking issue before the PDF.
