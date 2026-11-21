# A0 — Case Orchestrator

> **New chat? Load in this order:** `AGENTS.md` → `STATUS.md` → `PROJECT.md` → this file. Don't load the other agent specs unless you're working on an interface.
> **Owns:** `src/app.py`, `src/pipeline.py`, `src/contracts.py`, `src/llm.py`, `src/kb.py`, `src/diff.py`, `knowledge_base/extracted/`.
> **Build first:** `contracts.py`, `llm.py`, `kb.py` are dependencies for every other agent (Phase P0).

## 1. Mission
Run the **conversation loop** that the brief describes. Every user turn has to:
1. understand what the user is giving or asking,
2. call the right agents in the right order with the right state,
3. enforce the merge rules so earlier facts survive unless disproved,
4. compute the version diff,
5. save one immutable state + one PDF per version,
6. reply in the chat with a short summary.

A0 is mostly **code**. The LLM is used only for intent classification and for answering QUESTION turns.

## 2. Intents (one small LLM call, structured output)

| Intent | Example user turn | Pipeline | New version? |
|---|---|---|---|
| `NEW_INFO` | "Here's a screenshot of a post going viral…", a new attachment, a news excerpt | A1 → A2abc → risk → A3 → A4 → A5 | yes |
| `ACTION_UPDATE` | "Elena approved the batch hold; it was done yesterday; complaints dropped 40%" | A1 (registers the update as a source) → A2abc → risk → A3 → A4 → A5 | yes |
| `SET_FOCUS` | "Focus on the legal side" | store `focus`; if combined with info → as NEW_INFO | only if combined |
| `QUESTION` | "Why is the risk High?" | answer from latest CaseState (cite IDs), no agents | **no** |
| `CLOSE` | "We can stop here / close the case" | A1 (if new info) → A2 → risk → A3 (open actions) → A4 (reopen conditions) → A5 with closure section | yes (final) |

One turn can carry multiple intents (info + focus). The classifier returns a list. If the intent is ambiguous, prefer `NEW_INFO`.

Output schema:
```json
{ "intents": ["NEW_INFO"], "focus": null, "question": null, "close_requested": false }
```

## 3. Pipeline responsibilities (`pipeline.py`)
- Load `state_v{N}.json` (or create an empty CaseState for a new case), set `version = N+1`, `turn_input`.
- Save attachments to `cases/<id>/inputs/` and pass file paths to A1 (A1 assigns `U-xx` IDs).
- Call agents in order. Run **A2a/b/c in parallel** (threads or asyncio).
- After each agent: **validate** its output against the Pydantic model; on a validation failure, retry that agent once with the error message.
- **Merge rules** (code, see PROJECT §4): never delete sources/claims/actions; claim status changes need a `change_history` entry with sources; `verified_*` statuses need result evidence; only `risk.py` writes `risk`.
- **A4 revise loop:** if `qa.verdict == "REVISE"` with blocking issues, re-run the target agent(s) **once**, passing the issues, then re-run risk + A4. Whatever is still unresolved stays in `qa.issues` (rendered as QA notes). Never loop more than once.
- `diff.py`: compare v(N-1) and vN → fill `changelog[-1]` (risk_from/to, new sources, claim status changes, action status changes). A5 writes the narrative "why".
- Persist `state_vN.json`, call A5 to render `report_vN.pdf`.
- Chat reply (template, not LLM): `Report vN · Risk: <prev> → <now> (evidence confidence: x) · 3 key changes · top 3 P1 actions · [Download PDF]`.

## 4. LLM wrapper (`llm.py`) — shared by every agent
One helper, e.g. `call_structured(agent_name, system_prompt, user_content, output_model, effort)`, that:
- uses the official `anthropic` SDK, model from config (default `claude-opus-5-5`), adaptive thinking, `output_config.effort` per agent;
- returns a validated Pydantic object (structured outputs / `messages.parse`);
- puts the **KB text block first with cache_control** so every agent call reuses the cache (stable prefix: KB → agent prompt → volatile state/turn last);
- handles `stop_reason == "refusal"` and retries on 429/5xx;
- logs tokens and cost per call to `cases/<id>/trace.jsonl` (useful for the playback and for A5 Appendix C).
> Load the `claude-api` skill in Claude Code before writing this file. Don't write SDK calls from memory.

## 5. KB loader (`kb.py`)
- One-off script: extract text from the 12 PDFs + CSV into `knowledge_base/extracted/KB-01.md … KB-13.md`, each with a header: `source_id, file, date, category` (copy the registry in PROJECT §8).
- `load_kb_block()` → one concatenated string, deterministic order (cache-stable).
- `SOURCE_REGISTRY` dict for validation (any cited `KB-xx` must exist).

## 6. Chat UI (`app.py`, Streamlit)
- Sidebar: case selector / "New case", version list with a download link per PDF, current risk badge.
- Main: chat history, `st.chat_input` + file uploader (PDF, PNG/JPG, TXT).
- A progress indicator per agent step (A1 … A5). Useful in the demo to show the multi-agent flow.

## 7. Acceptance tests
- [ ] New case + S1 turn 1 → `state_v1.json` + `report_v1.pdf` exist and validate.
- [ ] QUESTION turn → no new version file.
- [ ] Turn 2 that disproves a claim → claim still present with status `disproved` + history; diff lists it.
- [ ] An agent returning invalid JSON is retried once, then surfaces a clear error (no crash).
- [ ] CLOSE → `status = closed`, `closure` filled, final PDF has section 9.
- [ ] Prompt cache hit visible in the trace (`cache_read_input_tokens > 0` from the 2nd agent call onward).

## 8. Notes for the director
- Contract changes (`contracts.py`) → propose in the session log under "Needs director review".
- Keep `pipeline.py` agent-agnostic: agents are registered functions, so stubs can be swapped in while other teammates build the real agents (stub = returns a fixture JSON from `tests/fixtures/`).
