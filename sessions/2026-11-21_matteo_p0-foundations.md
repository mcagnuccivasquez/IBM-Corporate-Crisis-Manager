# Session · 2026-11-21 · Matteo · p0-foundations

| Field | Value |
|---|---|
| Who | Matteo |
| Start → end | 15:25 → … |
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
- 15:55 · Decision: tell teammates about steps 1–4 in one message at session end (running list below)
- 16:15 · Step 2: `src/kb.py` (SOURCE_REGISTRY = §8, `load_kb_block()`, `kb_source()`, `unknown_kb_ids()`), `scripts/extract_kb.py`, generated `knowledge_base/extracted/KB-01..13.md`, `tests/test_kb.py` · pytest 57 passed
- 16:15 · Findings: screenshot text in KB-06/07/09 is in the PDF text layer (verified against the PNG), so no OCR is needed; KB-01/KB-03 images are illustrations with no text. KB block ≈ 23k chars ≈ 6k tokens. Tables rebuilt from word boxes (PyMuPDF dropped spaces); CSV gets clearly labelled computed totals
- 16:25 · Matteo approved extraction notes, KB-13 totals and `time_relevance` header → D-010 in PROJECT.md §12 · committed + pushed step 2
- 16:30 · Step 3: loaded `claude-api` skill; `src/llm.py` (`call_structured`, `load_prompt`, `file_block`, trace log), `tests/test_llm.py` (fake client), `scripts/smoke_llm.py` (live cache check) · pytest 67 passed · request body verified offline against SDK 2.12 via a mock HTTP transport (beta header, output_config effort+format, 2 cached system blocks)
- 16:30 · Design: `create`/`stream` + own Pydantic validation instead of `messages.parse()` (parse raises inside the HTTP call → no usage logged, no raw text for the retry, refusals show up as validation errors). The one validation retry lives in `call_structured` (A0 spec put it in the pipeline). Server-side refusal fallback on (`fallbacks="default"`). Streaming, max_tokens 32k
- 16:40 · Matteo approved the 5 llm.py decisions → D-011 in PROJECT.md §12; A0 spec §3 validation line updated to match · committed + pushed step 3
- 16:30 · Not verified live: no API key on this machine (no .env, no `ant` CLI) → `scripts/smoke_llm.py` pending

## Changes for teammates (send once at session end)
- **Everyone:** `pip install -r requirements.txt`; import with `from src.contracts import ...`; run tests with `pytest` from the repo root
- **Everyone:** agent output is validated strictly: unknown/misspelled fields are rejected; IDs must look like `KB-01`, `U-01`, `C-001`, `ACT-001`, `CASE-001`
- **Giacomo (A1):** every claim needs ≥1 `change_history` entry (reason + ≥1 source_id); `status` = last entry's `to`; `turn_input.attachments` = file paths in, `U-xx` IDs after A1
- **Junda (A2/risk.py):** `score` auto-filled = S×L (wrong value rejected); `evidence_confidence` ∈ low/medium/high; `RISK_LEVELS` tuple available
- **Serdar (A3/A5):** every action needs ≥1 `status_history` entry, `status` = last entry; `verified_*` needs `result_evidence_source_ids`; `report.narrative` is a free dict (you choose keys)
- **Everyone (KB):** the KB is in `knowledge_base/extracted/KB-xx.md`; `from src.kb import load_kb_block, SOURCE_REGISTRY, kb_source`; `llm.py` will put the KB block in every system prompt automatically, so don't paste the KB into your own prompts
- **Everyone (LLM calls):** use `call_structured(agent, load_prompt("a1"), user_content, YourOutputModel, effort, case_id=state.case_id)` from `src/llm.py`; never call the SDK directly. Put your prompt in `src/prompts/<agent>.md` and keep it free of timestamps/state (it is cached); state + turn go in `user_content`. Attachments: `file_block(path)`. Extra checks (e.g. unknown IDs) via `check=`. Catch `LLMError`. Each teammate needs their own `.env` with `ANTHROPIC_API_KEY`; test without a key using the fake client in `tests/test_llm.py`
- **Alibek (A4/fixtures):** QA `target` ∈ A0–A5, A2a/b/c; fixtures must validate (`CaseState.model_validate_json(...)`); see `tests/fixtures/contract_example_state.json`
