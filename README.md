# ACME Corporate Crisis Manager

Multi-agent system that assesses an emerging corporate crisis from company documents and new evidence, and produces a versioned Crisis Management Report (one PDF per version). IBM Use Case 2, group project.

**Start here:** [AGENTS.md](AGENTS.md) (how to work) · [STATUS.md](STATUS.md) (what's happening now) · [PROJECT.md](PROJECT.md) (architecture and decisions) · [agents/](agents/) (one spec per agent)

## Quick start
Requires **Python 3.11 or newer** (macOS ships 3.9: use e.g. `uv venv --python 3.12` or python.org; Windows: `py -3.13 -m venv .venv`).
```bash
python -m venv .venv          # then activate it
pip install -r requirements.txt
python -m playwright install chromium     # PDF engine, once
cp .env.example .env          # add your key: ANTHROPIC_API_KEY=sk-ant-...  (no spaces, no quotes)
pytest                        # no API key needed
python -m src.pipeline --stubs --text "Customers report hot PCX-100 chargers"   # full flow on stubs
streamlit run src/app.py      # chat UI (once app.py exists)
```
