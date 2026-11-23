# S1 · Turn 1 — Viral smoke post

**Scenario:** PCX-100 overheating (main demo, 4 turns)
**Turn:** 1 of 4 — first report received

---

## User message

> We just received a viral social media post. A customer claims their PCX-100 power adapter **smoked and melted on their desk**. They say they bought it in Germany in October 2026. I'm attaching a screenshot of the post.

## Attachments

| File | Description |
|---|---|
| `pcx100_smoke_post.png` | Screenshot of the customer's social media post showing the charger with visible damage and caption "ACME PCX-100 smoked and melted on my desk, bought in Germany last month. Dangerous!! #ACME #PCX100" |

> **Note for testers:** `pcx100_smoke_post.png` is a fictional test fixture image. For automated tests, use a placeholder 1×1 PNG or skip the attachment field. The key data is in the user text.

---

## Intent classification

Expected: `NEW_INFO`

---

## Context that the system has at this point

- No prior case exists. This is turn 1; `version` starts at 1.
- KB (KB-01 through KB-13) is available in the cached system prompt.
- No prior sources, claims, or actions.
