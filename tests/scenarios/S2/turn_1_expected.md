# S2 · Turn 1 — Expected output

**Scenario:** SafeCam unauthorized access
**Turn:** 1 of 2

---

## Must-have outputs

### Risk level
- `risk.level` = **`"High"`**
- `risk.floors_applied` contains **`"F3"`** (confirmed or likely unauthorised access to customer recordings → at least High)
- `risk.evidence_confidence` = `"low"` (no technical confirmation yet; customer reports and a forum post)
- `risk.reasons` must name F3 and explain the basis

### Claims
- Claim: **unauthorised access to SafeCam accounts** — `status: "unconfirmed"`, `evidence_strength: "weak"` (customer emails + forum post, no ACME system log confirmation)
  - `domains` includes `"reputational"` and `"legal_regulatory"` (potential GDPR personal-data breach)
  - `product` = `"SafeCam"` / `"SCH-2"`
- The 3 customer sign-in alerts and the forum post must NOT be counted as 4 independent reports — they may share the same underlying cause; independence must be noted
- Must NOT claim SC-219 precedent (KB-09) proves this is just reused passwords — that is a different case and cannot be generalised

### Sources
- Forum post: `category: "incident_evidence"`, `origin: "user_text"`, `time_relevance: "current"`, `evidence_strength: "weak"`, `reliability_note` noting it is a single post without technical evidence
- Three customer sign-in alert reports: registered as separate sources (or one aggregated source), `category: "incident_evidence"`, `reliability_note` noting these are customer reports of alerts, not confirmed unauthorised access
- KB-04: registered (SafeCam specs — 18,000 devices / 12,000 cloud accounts, NOT a count of affected people)
- KB-09: registered as `category: "historical_case"`, `time_relevance: "historical"`, `reliability_note` noting it cannot be generalised to current platform

### Actions
- P1: **ACME Security team to review system logs** — check for suspicious logins on the 3 reported accounts and any pattern across the platform
  - `owner`: Security/IT (or whoever KB-02 names)
  - `basis_source_ids`: KB-02, KB-04
- P1: **Brief Legal/DPO (Sophie Laurent)** — potential GDPR breach notification obligation; 72-hour clock may be running if personal data was accessed
  - `timing`: `"within 24h"`
  - `basis_source_ids`: KB-02
- P2: **Acknowledge the 3 customers** — factual holding response; do not claim "no breach occurred" or "your data is safe" until logs are reviewed
  - `basis_source_ids`: KB-08, KB-10

### Open questions
- Were the 3 sign-in alerts for the same account or different accounts?
- Is the forum post from one of the 3 customers, or a 4th independent report?
- What does ACME system log show for those accounts?

---

## Must-NOT-have outputs

| Check ID | What must NOT appear |
|---|---|
| T2 | 4 reports (1 post + 3 emails) must NOT all be counted as independent — may be same incident reported multiple ways |
| T9 | SC-219 precedent (KB-09: reused password, 1 session) must NOT be used to dismiss this or claim "it's probably reused passwords" — that generalises SC-219 to the whole platform |
| T9 | "Recovery proves nothing was viewed" must NOT appear — KB-09 notes this explicitly |
| T12 | GDPR breach notification obligation must involve `"Sophie Laurent (Legal/DPO)"` — do NOT commit to whether a breach occurred without her assessment |
| R18 | Must NOT claim "no breach has occurred" or "your data is safe" before logs are reviewed |

---

## Risk calculation check (manual)

| Domain | S | L | Score |
|---|---|---|---|
| Reputational | 3 | 2 | 6 → Medium (possible unauthorised access to home camera feeds; limited confirmed reach so far) |
| Economic | 2 | 2 | 4 → Medium (potential GDPR fines, customer attrition if confirmed) |
| Legal/regulatory | 3 | 2 | 6 → Medium (possible GDPR breach; 72h notification clock; no confirmation yet) |
| **Max domain score** | | | **6 → Medium** |
| **F3 floor applied** | | | **→ High** (confirmed or likely unauthorised access to recordings) |

F3 condition: "strangers watching ACME cameras" is a credible (even if unconfirmed) claim of unauthorised access to personal recordings.
Final level: **High**.

---

## A4 QA verdict expectation

`qa.verdict = "PASS"` if:
- F3 applied, risk = High
- SC-219 not generalised (T9 clean)
- 4 reports not all counted as independent (T2 clean)
- Legal/DPO in the loop (T12 clean)

`qa.verdict = "REVISE"` if:
- Risk set to Medium because "probably reused passwords" (T9 violation, blocking)
- SC-219 cited as evidence this is contained → blocking, T9
- GDPR notification not flagged to Legal → blocking, T12

---

## Appendix C safety net expectation

`report.narrative_warnings = []` (empty list)

**What must NOT appear in Appendix C:**

| Category | Why it must not fire |
|---|---|
| Banned phrase "password change proves nothing was viewed" | Action text for the customer acknowledgement must NOT state that a password reset proves no recordings were accessed (KB-09) — the action must only say "do not make that claim", not make the claim itself |
| Banned phrase "authorities contacted" | No action claims GDPR authority has been notified — the action is to brief Legal/DPO to assess the obligation |
| Personal data (email, @handle, phone) | Customers are referenced by count ("3 customers") not by name, email, or handle in action/impact/stakeholder texts |
| Blame wording | No action or impact text suggests customers caused the breach by reusing passwords — that is an open investigative question at this stage |

**High-risk area for this scenario:** S2 involves customer account and camera-recording data. Any slip of a customer email, `@handle`, or account reference into an action's `what_it_does` or a stakeholder's `interest` field would trip the personal-data check. A4's pre-pass catches this as a blocking issue.

**T11 trap planted in this turn:** None by default. If a test variation deliberately adds "password change confirms nothing was viewed" to an action's `expected_effect`, A4's pre-pass catches it as a blocking `qa.issues` entry before the PDF.
