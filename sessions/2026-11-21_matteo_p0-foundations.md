# Session · 2026-11-21 · Matteo · p0-foundations

| Field | Value |
|---|---|
| Who | Matteo |
| Start → end | 15:25 → 18:05 |
| Tool / LLM | Claude Code (Opus 5.5) |
| Working on | A0 foundations (phase P0) · issue #<n> |
| Branch | matteo/p0-foundations |
| Goal | Ship the P0 foundations (contracts, KB extraction, LLM wrapper, stub pipeline) so teammates can build their agents against them |

## Log
<!-- one line per meaningful action: HH:MM · what · files -->
- 15:25 · Session start; `git pull` (up to date); branch `matteo/p0-foundations` created; read STATUS, PROJECT, A0 spec
- 15:40 · Step 1: `requirements.txt`, `.env.example`, `pytest.ini`, `src/__init__.py`, `src/contracts.py` (§4 as Pydantic), `tests/fixtures/contract_example_state.json` (v2 PCX example), `tests/test_contracts.py` · local `.venv` (py 3.13), all deps install · pytest 15 passed
- 15:40 · Decision (A0-internal, matches §4): imports are `from src.contracts import ...` with repo root on the path (pytest.ini `pythonpath = .`)
- 15:50 · Matteo (director) approved the contract choices → logged as D-009 in PROJECT.md §12 · committed + pushed step 1
- 15:55 · Decision: tell teammates about steps 1–4 in one message at session end (list below)
- 16:15 · Step 2: `src/kb.py` (SOURCE_REGISTRY = §8, `load_kb_block()`, `kb_source()`, `unknown_kb_ids()`), `scripts/extract_kb.py`, generated `knowledge_base/extracted/KB-01..13.md`, `tests/test_kb.py` · pytest 57 passed
- 16:15 · Findings: screenshot text in KB-06/07/09 is in the PDF text layer (verified against the PNG), so no OCR is needed; KB-01/KB-03 images are illustrations with no text. Tables rebuilt from word boxes (PyMuPDF dropped spaces); CSV gets clearly labelled computed totals
- 16:25 · Matteo approved extraction notes, KB-13 totals and `time_relevance` header → D-010 in PROJECT.md §12 · committed + pushed step 2
- 16:30 · Step 3: loaded `claude-api` skill; `src/llm.py` (`call_structured`, `load_prompt`, `file_block`, trace log), `tests/test_llm.py` (fake client), `scripts/smoke_llm.py` (live cache check) · pytest 67 passed · request body verified offline against SDK 2.12 via a mock HTTP transport
- 16:30 · Design: `create`/`stream` + own Pydantic validation instead of `messages.parse()` (parse raises inside the HTTP call → no usage logged, no raw text for the retry, refusals show up as validation errors). The one validation retry lives in `call_structured`. Server-side refusal fallback on. Streaming, max_tokens 32k
- 16:40 · Matteo approved the 5 llm.py decisions → D-011 in PROJECT.md §12; A0 spec §3 validation line updated to match · committed + pushed step 3
- 16:50 · Idea kept open (not applied): hybrid provider in `llm.py` (`ACME_PROVIDER`): IBM watsonx.ai where it covers the need, Anthropic for the rest (structured outputs, caching, vision). Blocked on IBM API access + which models it offers; would change PROJECT §9 (director decision). For now Anthropic only
- 17:20 · Step 4: `src/pipeline.py` (run_turn, agent registry with stub fallback, merge rules, A4 revise-once, close-out, template chat reply, CLI), `src/diff.py`, `src/agents/stubs.py`, `src/prompts/a0_intent.md` + `a0_answer.md`, `tests/fixtures/stubs/*.json`, `tests/test_pipeline.py` · contracts.py: agent output models A1Output/A3Output/A4Output/A5Output · CLI 3-turn stub run (new → question → close) OK, stub PDF renders
- 17:20 · Bug found by tests and fixed: pipeline now re-validates agent outputs that are model instances (mutated models skip validators)
- 17:45 · `.env` format fixed (was `Anthropic API: "sk-…"`); Matteo chose hybrid models → D-012 (Sonnet 5.5 for A1–A4, Haiku 5.5 for A0/A5; refusal fallback only where supported); `.env` ACME_MODEL switched from Opus, `.env.example`, PROJECT §9, A0 spec updated; test for light-model routing · pytest 79 passed
- 17:45 · Live smoke test PASSED (3 calls, $0.03): call 2 read 9,103 cached tokens (KB+rules prefix ≈ 9.1k tokens, not 6k as estimated); answers grounded with correct KB IDs (KB-13 "delivered ≠ sold", KB-12/KB-02); Haiku works without fallback
- 18:05 · Session closed; step 4 + D-012 committed and pushed; STATUS.md updated

## Summary
All four P0 foundation pieces are on branch `matteo/p0-foundations`: the CaseState contract (`contracts.py`), the extracted knowledge base with its registry (`kb.py`), the shared Claude wrapper (`llm.py`, verified live with a cache hit), and the A0 pipeline with stub agents that runs the full turn end to end (new case → question → close). Teammates can now build their agents against fixed interfaces and see them run inside the full flow as soon as their module exists. Models switched to a cheaper hybrid (Sonnet 5.5 + Haiku 5.5, D-012). 79 tests pass.

## Done
- Step 1: `contracts.py` + example state + tests (D-009)
- Step 2: `kb.py`, KB-01…KB-13 extracted, tests (D-010)
- Step 3: `llm.py` + tests + live smoke test (D-011)
- Step 4: `pipeline.py`, `diff.py`, stub agents, A0 intent/answer prompts, tests
- Hybrid models (D-012); live API verified ($0.03)

## Not done / blockers
- PR to `main` not opened yet; teammates can't use the foundations from `main` until it's merged
- `app.py` (Streamlit UI) not started
- A0 intent classifier and question answering (LLM versions) have not been run live (only stubs in tests)
- Open: does a different `effort` per agent split the KB cache? Check `trace.jsonl` once real agents run
- Open: IBM watsonx hybrid provider idea (needs IBM API access)
- Open team questions in STATUS.md (IBM expectation, API keys/budget)

## Next steps (for whoever picks this up)
- Open the PR `matteo/p0-foundations` → `main`, merge, then send the teammate message below
- Each owner checks the agent interface (signature + output model in `contracts.py`) against their spec and reports mismatches to the director
- Build `src/app.py` (Streamlit chat: case selector, upload, per-agent progress via `on_step`, PDF download)
- Run S1 turn 1 live as soon as A1 + A2 exist; read `trace.jsonl` for real cost per turn and the effort/cache question

## Files touched
- New: `requirements.txt`, `.env.example`, `pytest.ini`, `src/__init__.py`, `src/contracts.py`, `src/kb.py`, `src/llm.py`, `src/diff.py`, `src/pipeline.py`, `src/agents/__init__.py`, `src/agents/stubs.py`, `src/prompts/a0_intent.md`, `src/prompts/a0_answer.md`, `scripts/extract_kb.py`, `scripts/smoke_llm.py`, `knowledge_base/extracted/KB-01..13.md`, `tests/test_contracts.py`, `tests/test_kb.py`, `tests/test_llm.py`, `tests/test_pipeline.py`, `tests/fixtures/contract_example_state.json`, `tests/fixtures/stubs/*.json`
- Changed: `PROJECT.md` (§9 LLM row, §12 D-009…D-012), `agents/A0_orchestrator.md` (§3 validation line, §4 model), `STATUS.md`
- Local only (not committed): `.env` (gitignored), `.venv/`

## Needs director review
All contract/method decisions of this session were reviewed and approved by Matteo as director in-session (D-009…D-012). Still to confirm **with the team**:
- The agent interface (function names/signatures and `A1Output`/`A3Output`/`A4Output`/`A5Output` in `contracts.py`) was derived from PROJECT §3.3 without reading the other agent specs. Each owner must check it against their spec
- Hybrid models (D-012) and the shared `COMMON_RULES` prompt in `llm.py` affect every agent

## Changes for teammates (paste in the group chat after the PR is merged)
> **P0 foundations are ready** (branch `matteo/p0-foundations`, PR → main). What you need to know:
> - **Setup:** `pip install -r requirements.txt`; copy `.env.example` to `.env` and put your own key in it as `ANTHROPIC_API_KEY=sk-ant-...` (no spaces, no quotes). Run `pytest` from the repo root.
> - **Contract** (`src/contracts.py`): output is validated strictly, so unknown or misspelled fields are rejected; IDs must look like `KB-01`, `U-01`, `C-001`, `ACT-001`, `CASE-001`.
> - **KB:** already extracted in `knowledge_base/extracted/`. `llm.py` puts it into every prompt automatically, so don't paste the KB into your own prompt.
> - **LLM calls:** always use `call_structured(agent, load_prompt("a1"), user_content, YourOutputModel, effort, case_id=state.case_id)` from `src/llm.py`. Your prompt goes in `src/prompts/<agent>.md` with no timestamps or state, because it's cached; state and turn go in `user_content`. Attachments: `file_block(path)`. Catch `LLMError`. Models: Sonnet 5.5 for A1–A4, Haiku 5.5 for A0/A5.
> - **Your module is picked up automatically** by the pipeline when it exists (a stub runs until then):
>   - A1: `src/agents/a1_evidence.py` → `run(state, turn) -> A1Output`
>   - A2: `src/agents/a2_impact.py` → `run(state, turn, domain) -> DomainImpact`
>   - risk: `src/risk.py` → `compute_risk(state, prev_state) -> Risk`
>   - A3: `src/agents/a3_actions.py` → `run(state, turn) -> A3Output`
>   - A4: `src/agents/a4_critic.py` → `run(state, turn) -> A4Output`
>   - A5: `src/agents/a5_report.py` → `run(state, turn, prev_state) -> A5Output` and `src/report/render.py` → `render_pdf(state, pdf_path)`
>   Return only new or changed items; A0 merges by ID and never deletes. **Check this interface against your spec and tell me about any mismatch.**
> - **Try the whole flow:** `python -m src.pipeline --stubs --text "Customers report hot PCX-100 chargers"`
> - **Giacomo (A1):** every claim needs ≥1 `change_history` entry (reason + ≥1 source_id), and `status` must equal the last entry; attachments arrive as file paths and you assign the `U-xx` IDs.
> - **Junda (A2/risk):** `score` is filled in as S×L (a wrong value is rejected); `evidence_confidence` is low/medium/high; `RISK_LEVELS` gives the 4 levels in order. The stub risk engine in `src/agents/stubs.py` is a placeholder; yours replaces it.
> - **Serdar (A3/A5):** every action needs ≥1 `status_history` entry, and `status` must equal the last entry; `verified_*` needs `result_evidence_source_ids`; `report.narrative` is a free dict, so you choose the section keys.
> - **Alibek (A4/fixtures):** QA `target` can be A0–A5 or A2a/b/c; fixtures must validate with `CaseState.model_validate_json(...)`; see `tests/fixtures/contract_example_state.json`. On a REVISE, the target agent re-runs once and finds your issues in `state.qa.issues`.
