# ACME Corporate Crisis Manager

Multi-agent system that assesses an emerging corporate crisis from company documents and new evidence, and produces a versioned Crisis Management Report (one PDF per version). IBM Use Case 2, group project.

**Start here:** [AGENTS.md](AGENTS.md) (how to work) · [STATUS.md](STATUS.md) (what's happening now) · [PROJECT.md](PROJECT.md) (architecture and decisions) · [agents/](agents/) (one spec per agent)

## Quick start (once code exists)
```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env        # add your ANTHROPIC_API_KEY
streamlit run src/app.py
```
