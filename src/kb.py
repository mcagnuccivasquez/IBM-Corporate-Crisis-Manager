"""Knowledge base: source registry (PROJECT.md §8) and the cached KB text block.

Owned by A0. Every agent cites KB sources by these IDs.

    from src.kb import SOURCE_REGISTRY, load_kb_block, kb_source, unknown_kb_ids
    block = load_kb_block()            # full KB text, deterministic (prompt-cache stable)
    src = kb_source("KB-13", version=1)  # contracts.Source for A1 to register

The extracted text in knowledge_base/extracted/ is generated once by
`python scripts/extract_kb.py` and committed, so runtime needs no PDF library.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from src.contracts import SourceCategory, Source, TimeRelevance

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "knowledge_base" / "ACME_company_files"
EXTRACTED_DIR = ROOT / "knowledge_base" / "extracted"


@dataclass(frozen=True)
class KBEntry:
    source_id: str
    file: str  # relative to KB_DIR
    title: str
    date: str  # date of the content, as in PROJECT.md §8
    category: SourceCategory

    @property
    def time_relevance(self) -> TimeRelevance:
        return "historical" if self.category == "historical_case" else "current"

    @property
    def extracted_path(self) -> Path:
        return EXTRACTED_DIR / f"{self.source_id}.md"


# PROJECT.md §8. Change only through the Decision log.
SOURCE_REGISTRY: dict[str, KBEntry] = {
    e.source_id: e
    for e in (
        KBEntry("KB-01", "ACME_company_overview_2026.pdf", "ACME company overview 2026", "Sep 2026", "reference"),
        KBEntry("KB-02", "Operations_contacts_Oct26.pdf", "Operations contacts (who to contact)", "20 Oct 2026", "reference"),
        KBEntry("KB-03", "Product_PCX100_v4_sales_copy.pdf", "PowerCharge X PCX-100 sales reference v4", "8 Sep 2026", "reference"),
        KBEntry("KB-04", "SafeCam_Home_notes_for_retail.pdf", "SafeCam Home retail support notes", "22 Oct 2026", "reference"),
        KBEntry("KB-05", "Sep26_customer_care_review.pdf", "Customer Care September review", "5 Oct 2026, updated 22 Oct 2026", "company_record"),
        KBEntry("KB-06", "FW_4471_charging_stops.pdf", "FW: #4471 charging stops (email + ticket capture)", "13 May 2026", "historical_case"),
        KBEntry("KB-07", "Screen_TravelPlug_post_181125.pdf", "Saved TownSquare post about TravelPlug 30", "18 Nov 2025", "historical_case"),
        KBEntry("KB-08", "RE_TravelPlug_social_followup.pdf", "RE: TravelPlug post (response emails)", "18-21 Nov 2025", "historical_case"),
        KBEntry("KB-09", "SafeCam_account_case_120226.pdf", "SC-219 SafeCam account review (email + timeline capture)", "12-13 Feb 2026", "historical_case"),
        KBEntry("KB-10", "Replies_working_notes_AK.pdf", "Reply notes, working copy (Anna Keller)", "7 Jul 2026", "informal_note"),
        KBEntry("KB-11", "VN3_visit_note_Jul26.pdf", "VN-3 supplier visit note", "21 Jul 2026", "company_record"),
        KBEntry("KB-12", "RE_costs_for_PowerCharge_returns.pdf", "RE: costs for PowerCharge returns (Finance)", "30 Sep 2026", "planning_assumption"),
        KBEntry("KB-13", "PCX_stock_export_22Oct.csv", "PCX-100 stock export", "22 Oct 2026", "company_record"),
    )
}

_KB_ID = re.compile(r"^KB-\d{2}$")


def kb_source(source_id: str, version: int) -> Source:
    """The registry entry as a contracts.Source (origin 'kb'), for A1 to register."""
    e = SOURCE_REGISTRY[source_id]
    return Source(
        source_id=e.source_id,
        title=e.title,
        file=f"knowledge_base/ACME_company_files/{e.file}",
        origin="kb",
        date=e.date,
        category=e.category,
        time_relevance=e.time_relevance,
        reliability_note="ACME knowledge base file",
        added_in_version=version,
    )


def unknown_kb_ids(ids: list[str]) -> list[str]:
    """KB-xx IDs in `ids` that are not in the registry (non-KB IDs are ignored)."""
    return [i for i in ids if _KB_ID.match(i) and i not in SOURCE_REGISTRY]


def entry_header(e: KBEntry) -> str:
    """Header written at the top of each extracted file (and parsed back by tests)."""
    return (
        f"# {e.source_id} · {e.title}\n\n"
        f"source_id: {e.source_id}\n"
        f"file: {e.file}\n"
        f"date: {e.date}\n"
        f"category: {e.category}\n"
        f"time_relevance: {e.time_relevance}\n"
    )


def load_kb_text(source_id: str) -> str:
    path = SOURCE_REGISTRY[source_id].extracted_path
    if not path.exists():
        raise FileNotFoundError(f"{path} missing. Run: python scripts/extract_kb.py")
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def load_kb_block() -> str:
    """All 13 KB files in registry order, each wrapped in a <document> tag.

    Byte-identical across calls and processes, so it can be the cached prefix
    of every agent's system prompt (see llm.py).
    """
    parts = [
        "<knowledge_base>\n"
        "ACME company files. Cite them by source_id (KB-01 ... KB-13). "
        "Files in category historical_case are precedents, not evidence about the current incident. "
        "Lines starting with [Extraction note: ...] were added when the files were converted to text "
        "and are not part of the original document.\n"
    ]
    for sid in SOURCE_REGISTRY:
        parts.append(f'<document source_id="{sid}">\n{load_kb_text(sid)}\n</document>\n')
    parts.append("</knowledge_base>")
    return "\n".join(parts)
