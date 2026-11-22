# S2 · Turn 1 — SafeCam access post + sign-in alerts

**Scenario:** SafeCam unauthorized access
**Turn:** 1 of 2 — initial post + customer alerts received

---

## User message

> We've got a situation with SafeCam. A post on a home-security forum is claiming "strangers are watching ACME cameras" — the user says they can see activity on their SafeCam app from an IP they don't recognise. At the same time Customer Care has forwarded three customer emails — all three say they received sign-in alert emails from ACME for logins they didn't make. Two of the customers are in IT, one is in DE.

## Attachments

None. User provides the information as text.

---

## Intent classification

Expected: `NEW_INFO`

---

## Context that the system has at this point

- No prior case. This is turn 1; `version` starts at 1.
- KB available: KB-04 (SafeCam specs: SCH-2 fw 2.6.1, 18,000 devices / 12,000 cloud accounts — not a count of affected people), KB-09 (SC-219 precedent: reused password, 1 session, contained — cannot generalise to platform).
- No prior sources, claims, or actions.
- Three separate customer contacts + one public post = four data points, but independence must be assessed.
