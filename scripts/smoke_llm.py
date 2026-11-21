"""Live check of llm.py against the real API (costs about one cent).

    python scripts/smoke_llm.py

Three small calls:
  1-2. two "reasoning" agents on the main model (Sonnet 5.5) with different prompts:
       the 2nd should show cache_read_input_tokens > 0, because the common rules + KB
       prefix is shared (A0 acceptance test: "prompt cache hit visible in the trace")
  3.   an A0 call on the light model (Haiku 5.5), which runs without the refusal fallback
Trace: cases/_dev/trace.jsonl (caches are per model, so call 3 writes its own entry)
"""

import json
import sys
from pathlib import Path

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.llm import call_structured, cases_dir  # noqa: E402


class Answer(BaseModel):
    answer: str
    source_ids: list[str]


CALLS = [
    ("smoke-1", "Answer questions about ACME using the knowledge base.", "How many PCX-100 units of batch PCX-2609-B are in the warehouse?"),
    ("smoke-2", "You check facts about ACME's people and roles.", "Who must be involved before a large customer remedy is committed?"),
    ("A0-smoke", "Answer in one sentence.", "Which ACME product has no remote firmware update?"),
]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    trace = cases_dir() / "_dev" / "trace.jsonl"
    start = len(trace.read_text(encoding="utf-8").splitlines()) if trace.exists() else 0
    for agent, prompt, question in CALLS:
        out = call_structured(agent, prompt, question, Answer, effort="low")
        print(f"{agent}: {out.answer}  {out.source_ids}")
    print("\nagent      model              in  cache_write  cache_read   out   cost_usd")
    total = 0.0
    for line in trace.read_text(encoding="utf-8").splitlines()[start:]:
        r = json.loads(line)
        total += r.get("cost_usd") or 0
        print(f"{r['agent']:<10} {r.get('model', '?'):<18} {r.get('input_tokens', 0):>4} {r.get('cache_creation_input_tokens', 0):>11} "
              f"{r.get('cache_read_input_tokens', 0):>11} {r.get('output_tokens', 0):>5}   {r.get('cost_usd')}")
    print(f"\ntotal ≈ ${total:.4f}")


if __name__ == "__main__":
    main()
