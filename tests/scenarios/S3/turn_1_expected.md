# S3 · Turn 1 — Expected output (Misleading repost)

**Scenario:** Misleading repost
**Turn:** 1 of 1

---

## Must-have outputs

### Risk level
- `risk.level` = **`"Low"`** or **`"Medium"`** — must NOT be High or Critical
- `risk.floors_applied` = `[]` — F1 does NOT apply because the post is about a different product (TravelPlug 30) in a historical case, not a current PCX-100 incident
- `risk.evidence_confidence` = `"low"`
- `risk.reasons` must explain why risk is Low/Medium: the post is about a different product; the newspaper article is a copy of the same post, not an independent report

### Claims
- The repost claim must be classified as **`"misleading"`**:
  - `text`: something like "ACME chargers are still dangerous" is misleading — based on a 2025 TravelPlug 30 post about a different product, re-shared as if it is current
  - `status: "misleading"`, `evidence_strength: "weak"`
  - `domains: ["reputational"]`
  - `product`: `"TravelPlug 30"` (not PCX-100 — this must be explicit)
  - `change_history` with reason explaining the misleading classification

- The newspaper article must be registered as `duplicate_of` the original repost source — it quotes the same post and is NOT an independent report (KB-08 precedent: "the newspaper link was a repeat, not a 2nd customer")

### Sources
- Original repost: `category: "incident_evidence"`, `time_relevance: "current"` (the repost is current), `reliability_note` noting it is a re-share of KB-07 (2025 TravelPlug post)
- Newspaper article: `category: "incident_evidence"`, `duplicate_of` pointing to the repost source, `reliability_note` noting it quotes the same post and is not an independent report
- KB-07: registered as `category: "historical_case"`, `time_relevance: "historical"`
- KB-08: registered as `category: "historical_case"`, `time_relevance: "historical"`

### Actions
- P2 action: **publish a factual clarification** — brief public response noting the post refers to a 2025 TravelPlug 30 case that was investigated and resolved; do not inflate the response
  - `basis_source_ids`: KB-08 (response precedent), KB-07
  - Must NOT claim "all units tested" or "no safety issues exist" (KB-10)
  - Must NOT escalate to a recall or batch hold (no PCX-100 evidence)
- No P1 actions — this is a reputational clarification only

### Outlook
- `residual_risk_if_p1_effective`: `"Low"` — if the clarification is published and visible, the misleading claim has limited ongoing reach
- `pattern_warnings`: must flag trap T1 (treating the TravelPlug 2025 case as evidence about PCX-100) and trap T2 (counting the newspaper article as an independent report)

---

## Must-NOT-have outputs

| Check ID | What must NOT appear |
|---|---|
| **T1** | TravelPlug 2025 case must NOT be treated as evidence about PCX-100 or any current ACME product — it is a historical case about a different product |
| **T2** | The newspaper article must NOT be counted as an independent second report — it quotes the same original post (KB-08 precedent) |
| T3 | The repost/article must NOT be treated as proof of a current defect |
| **F1** | F1 must NOT be triggered — the smoke/heat claim is about TravelPlug 30 in 2025, not a product currently in market under a live incident |
| R18 | No batch hold, recall, or escalation — there is no current evidence of a PCX-100 or SafeCam issue |

---

## Risk calculation check (manual)

| Domain | S | L | Score |
|---|---|---|---|
| Reputational | 2 | 2 | 4 → Medium (misleading post is public; minor brand confusion possible if unclarified) |
| Economic | 1 | 1 | 1 → Low (no product defect involved; clarification is low cost) |
| Legal/regulatory | 1 | 1 | 1 → Low (no product safety obligation for a 2025 resolved case) |
| **Max domain score** | | | **4 → Medium** |
| **No floors apply** | | | **→ Medium** |

Final level: **Medium** (or Low if reputational S=1 is argued — both acceptable; the key constraint is NOT High or Critical).

---

## A4 QA verdict expectation

`qa.verdict = "PASS"` if:
- Risk is Low or Medium (not High/Critical)
- F1 not applied
- Repost claim classified `misleading`
- Newspaper article has `duplicate_of` set (not counted as independent)
- Action is a factual clarification only (no batch hold, no recall)

`qa.verdict = "REVISE"` if:
- Risk = High or Critical → blocking, T1 violation (treating historical TravelPlug case as current evidence)
- F1 applied → blocking, T1
- Newspaper article counted as independent report → blocking, T2
- Batch hold or recall proposed → blocking, R18 / T1

---

## Appendix C safety net expectation

`report.narrative_warnings = []` (empty list)

**What must NOT appear in Appendix C:**

| Category | Why it must not fire |
|---|---|
| Banned phrase "all units tested" | The clarification action must NOT claim TravelPlug or any current product units have been tested — the 2025 case was resolved; no current testing is proposed |
| Banned phrase "independent tests" | Same constraint — the response action is a factual clarification, not a testing programme |
| Personal data | The original post may contain a poster's @handle or name. Neither must appear in action `what_it_does`, impact descriptions, or outlook texts |
| Blame wording | The poster is spreading a misleading repost — this must not be characterised as the customer's "misuse" or "fault" |

**Key constraint for this scenario:** the repost comes from a 2025 source (KB-07/KB-08). The clarification action will reference that history. Phrases like "our 2025 TravelPlug investigation found no defect and we consider it resolved" are fine. Phrases like "all TravelPlug units were independently tested" would trip the safety net — A4's pre-pass catches it as blocking.

**T11 trap planted in this turn:** The scenario does not plant a T11 trap by default. The natural T1 trap (treating TravelPlug history as current evidence) is a logical error caught by the LLM review, not the regex pre-pass.
