# A4 — Critic & Outlook

> **New chat? Load in this order:** `AGENTS.md` → `STATUS.md` → `PROJECT.md` (esp. §4, §6, §8 traps) → this file.
> **Owns:** `src/agents/a4_critic.py`, `src/prompts/a4_critic.md`, `tests/test_a4_*.py`, and the **test scenarios** in `tests/scenarios/` (the A4 owner is also QA lead).

## 1. Mission
Two jobs, both "a second look" at the draft version before it is published:
1. **Critic (QA gate):** verify that A1–A3 followed the rules (grounding, the trap list, policy, status discipline) and send precise fixes back. This is the "verify accuracy of Agent Three" idea from the original plan, extended to A1 and A2.
2. **Outlook:** if the P1/P2 actions are carried out and work, what risk remains, based on precedent and data, with explicit assumptions and an explicit list of what **cannot** be estimated. It also detects **pattern traps** (repeating past mistakes).

## 2. Input
Full draft CaseState vN (after A3 + risk.py), previous version vN-1, KB (cached).

## 3. Output
```json
{
  "qa": {
    "verdict": "PASS | REVISE",
    "issues": [{ "target": "A1|A2a|A2b|A2c|A3", "item_id": "ACT-004", "check": "T7", "problem": "...", "fix_hint": "...", "blocking": true }]
  },
  "outlook": {
    "residual_risk_if_p1_effective": "Medium",
    "domain_projection": [{ "domain": "reputational", "severity": 3, "likelihood": 1, "reason": "...", "basis_source_ids": ["KB-08"] }],
    "assumptions": ["Hold is executed within 24h", "Lab confirms the defect is limited to PCX-2609-B"],
    "cannot_estimate": ["Number of units actually sold to consumers (KB-12)", "Media pick-up"],
    "pattern_warnings": ["Closing heat reports with the #4471 cable explanation would repeat the mistake Maya warned against (KB-06)"]
  },
  "reopen_conditions": []     // only on CLOSE: concrete triggers, e.g. "any new smoke/fire report on PCX-2609-*", "authority contact", "lab finds fault outside batch B"
}
```
`residual_risk_if_p1_effective` is computed by calling `risk.py` on the projected domain scores. Don't eyeball it.

## 4. Checklist (each check has an ID so issues are traceable)
**Grounding**
- G1 Every claim, impact, and action cites existing IDs (validate against the registry and the case sources).
- G2 No fact, number, name, or date that isn't in the inputs/KB. General knowledge is labelled.
- G3 Economic numbers are reproducible from KB-12/KB-13 (recompute them).

**Traps (PROJECT §8, T1–T12)**
- T1 TravelPlug/historical cases used as current evidence · T2 duplicates counted as independent · T3 screenshot treated as proof · T4 tickets → failure rate / heat = fault · T5 #4471 cable explanation applied to smoke/damage · T6 VN-3 used to clear September batches · T7 unscoped cost (all units × €30, delivered = sold) · T8 remote fix promised for PCX · T9 password change ⇒ "nothing viewed" / SC-219 generalised · T10 working notes treated as policy · T11 public wording blames customers / has personal data / unverified claims · T12 missing approvals (CEO, Legal/DPO).

**Method consistency**
- M1 S/L scores match the quoted anchors; floors reported when the condition holds.
- M2 Risk not inflated by focus; evidence confidence not mixed into the scores.
- M3 Every High/Critical impact has an action or an explicit "no action because".
- M4 Major decisions have ≥2 options.
- M5 Action status changes are backed by the user's turn; `verified_*` has result evidence.
- M6 The changelog explains every risk change, and states why the level stayed the same if it did.

**Blocking** = G1, G2, G3, T1–T12, M5. Non-blocking issues are reported as QA notes in the report.

## 5. Rules
- Be specific: point to the item ID and the fix. Don't rewrite other agents' work yourself.
- If nothing is wrong, say PASS. Don't invent issues.
- Outlook uses precedent (KB-08 response pattern, KB-09 containment, KB-06 limits) and data. If there is no basis, put it in `cannot_estimate` rather than guessing.

## 6. Draft runtime system prompt
```
You are the Critic and Outlook agent in ACME's crisis-management system. First, audit the draft report state against
the checklist provided (grounding, known traps, method consistency, action status discipline). For each problem give
the check ID, the item ID, the responsible agent, what is wrong and how to fix it, and whether it is blocking. Return
PASS if there are no blocking issues. Do not invent problems and do not fix them yourself.

Second, project the outlook: assuming the priority actions are carried out and work, estimate the remaining Severity
and Likelihood per domain using the same anchors, based only on ACME's precedents and data. List your assumptions,
what cannot be estimated from the available data, and any sign that ACME is about to repeat a past mistake.
On case closure, list concrete, observable conditions that should reopen the case.
```

## 7. Test scenarios (A4 owner writes these; fictional inputs used **only** as test fixtures)
- **S1 PCX-100 overheating (main demo, 4 turns):** T1 viral post with screenshot: "PCX-100 smoked and melted on my desk", bought DE, Oct 2026. T2 Quality: 2 returned samples from PCX-2609-B, one shut down late (above spec), label genuine; a DE retailer asks questions. T3 actions reported: hold on batch B done, holding statement published, ticket volume trend. T4 close.
- **S2 SafeCam access:** post claims "strangers are watching ACME cameras" + 3 customer sign-in alerts; later Security finds reused passwords on 2 accounts, 1 unexplained.
- **S3 Misleading:** the 2025 TravelPlug post re-shared as "ACME chargers overheating now", plus a news article quoting it. Expected: `misleading`, risk stays Low/Medium, the action is a factual clarification.
Each scenario: `tests/scenarios/Sx/turn_k.md` (+ attachments) and `expected.md` (key expected statuses, levels, must-have and must-not-have actions).

## 8. Acceptance tests
- [ ] A3 draft containing "all units tested" → REVISE, T11, blocking.
- [ ] Economic impact using 16,000 × €30 without scope → REVISE, T7.
- [ ] Clean S1 v1 → PASS.
- [ ] Outlook always has non-empty `assumptions` and `cannot_estimate`.
