# S2 · Turn 2 — Expected output

**Scenario:** SafeCam unauthorized access
**Turn:** 2 of 2

---

## Must-have outputs

### Risk level
- `risk.level` = **`"High"`** — must NOT drop to Medium or Low
- F3 floor still applies: 1 unexplained session on an account with a camera feed = "likely unauthorised access to recordings" until proven otherwise
- **F4 applies**: risk may only drop if the unexplained session is explained or the claim is downgraded — neither has happened
- `risk.reasons` must explain why F3 still applies despite the 2 reused-password accounts being resolved

### Claims
- 2 reused-password claims → `status: "confirmed"` (reused password confirmed by security logs), `evidence_strength: "strong"`, `domains: ["reputational"]` (contained, low ongoing risk)
- Unexplained session claim → `status: "unconfirmed"`, `evidence_strength: "moderate"` (log shows the session, but cause is unknown)
  - Must NOT be set to `disproved` or `misleading` — it is real and unexplained
- Original claim (unauthorised access) partially updated but NOT fully resolved

### Actions
- Previous 3 actions updated with results:
  - Log review → `"completed"`, `result_evidence_source_ids` pointing to the security log source
  - Customer acknowledgement → `"completed"` for the 2 resolved accounts
- New **P1** action: **investigate the unexplained session** — determine IP, timing, what (if anything) was accessed
  - `timing`: `"within 24h"`
  - `owner`: Security team
- New **P2** action: **keep Legal/DPO (Sophie Laurent) updated** on the unexplained session — GDPR 72h clock consideration if personal data was accessed
- System should respond to the user's "should we close?" question: **recommend keeping open** until the unexplained session is resolved

### Open questions
- What was the unexplained session? (IP, geolocation, duration, content accessed)
- Was any camera footage or personal data viewed during the unexplained session?

---

## Must-NOT-have outputs

| Check ID | What must NOT appear |
|---|---|
| T9 | "Password reset proves nothing was viewed" — KB-09 explicitly states recovery ≠ proof nothing was viewed |
| T9 | SC-219 generalised: "this is just like SC-219, so it's contained" — SC-219 was 1 account with a known reused password; here 1 session remains unexplained |
| **F4** | Risk must NOT drop because "2 of 3 accounts are resolved" — 1 unexplained session keeps F3 active |
| R18 | Must NOT recommend closing the case while the unexplained session is unresolved |

---

## Risk calculation check (manual)

| Domain | S | L | Score |
|---|---|---|---|
| Reputational | 3 | 2 | 6 → Medium (2 accounts resolved, but 1 unexplained; not yet public) |
| Economic | 2 | 1 | 2 → Low (contained for 2 accounts; 1 open) |
| Legal/regulatory | 3 | 2 | 6 → Medium (unexplained session; GDPR 72h not yet triggered but Legal monitoring) |
| **Max domain score** | | | **6 → Medium** |
| **F3 still applies** | | | **→ High** (1 unexplained session on a camera account) |

Final level: **High**

---

## A4 QA verdict expectation

`qa.verdict = "PASS"` if:
- Risk stays High, F3 still applied with justification
- T9 not violated (no "reset proves nothing viewed")
- Unexplained session claim stays `unconfirmed` not `disproved`
- Recommendation is to keep case open

`qa.verdict = "REVISE"` if:
- Risk drops to Medium → blocking, F3/F4 violation
- Unexplained session marked `disproved` without evidence → blocking, G2
- Case closure recommended → blocking, R18

---

## Appendix C safety net expectation

`report.narrative_warnings = []` (empty list)

**What must NOT appear in Appendix C:**

| Category | Why it must not fire |
|---|---|
| Banned phrase "password change proves nothing was viewed" | The 2 resolved-account actions must NOT state that the password reset proved no recordings were accessed — only that the accounts are secured; the unexplained session is separately open |
| Banned phrase "authorities contacted" | Legal/DPO is monitoring the GDPR clock; no action should state authorities have been notified |
| Personal data (email, @handle, phone) | Security log findings are described in aggregate or by account-ID pattern — no customer email or @handle in action or impact text |
| Blame wording | Reused passwords are a factual finding for 2 accounts, stated neutrally — not framed as "customers caused this by being careless" |

**High-risk area for this turn:** the "investigate unexplained session" action may tempt agents to include the account owner's contact details. Those must stay out of `what_it_does` and `expected_effect`. A4's pre-pass catches any slip as a blocking issue.

**T11 trap planted in this turn:** None by default. The classic T9 trap ("password reset proves nothing viewed") is a logical/wording error caught by A4's LLM review (not the regex pre-pass) since it typically appears in natural-language reasoning rather than a fixed phrase.
