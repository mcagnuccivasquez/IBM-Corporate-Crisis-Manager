"""Live check of llm.py against the real API (costs a few cents).

    python scripts/smoke_llm.py

Makes two small calls with different agent prompts. The second should show
cache_read_input_tokens > 0, because the common rules + KB prefix is shared
(A0 acceptance test: "prompt cache hit visible in the trace").
Trace: cases/_dev/trace.jsonl
"""

import sys
from pathlib import Path

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.llm import call_structured  # noqa: E402


class Answer(BaseModel):
    answer: str
    source_ids: list[str]


def main() -> None:
    for agent, prompt, question in [
        ("smoke-1", "Answer questions about ACME using the knowledge base.", "How many PCX-100 units of batch PCX-2609-B are in the warehouse?"),
        ("smoke-2", "You check facts about ACME's people and roles.", "Who must be involved before a large customer remedy is committed?"),
    ]:
        out = call_structured(agent, prompt, question, Answer, effort="low")
        print(f"{agent}: {out.answer}  {out.source_ids}")
    print("\nTokens and cache per call: see cases/_dev/trace.jsonl (cache_read_input_tokens should be > 0 on smoke-2)")


if __name__ == "__main__":
    main()
