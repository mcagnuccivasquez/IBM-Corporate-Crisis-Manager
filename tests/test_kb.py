"""KB registry, extracted files and the cached KB block."""

import re
import sys
from collections import Counter
from pathlib import Path

import pytest

from src.contracts import KB_SOURCE_IDS, Source
from src.kb import KB_DIR, SOURCE_REGISTRY, kb_source, load_kb_block, unknown_kb_ids

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import extract_kb  # noqa: E402


def test_registry_matches_project_md():
    assert tuple(SOURCE_REGISTRY) == KB_SOURCE_IDS  # KB-01..KB-13, in order
    for e in SOURCE_REGISTRY.values():
        assert (KB_DIR / e.file).exists(), e.file
    assert SOURCE_REGISTRY["KB-07"].time_relevance == "historical"
    assert SOURCE_REGISTRY["KB-10"].category == "informal_note"
    assert SOURCE_REGISTRY["KB-12"].category == "planning_assumption"


@pytest.mark.parametrize("sid", KB_SOURCE_IDS)
def test_extracted_file_has_header(sid):
    e = SOURCE_REGISTRY[sid]
    text = e.extracted_path.read_text(encoding="utf-8")
    for field, value in [("source_id", sid), ("file", e.file), ("date", e.date), ("category", e.category)]:
        assert f"\n{field}: {value}\n" in text, f"{sid}: header field {field}"


@pytest.mark.parametrize("sid", KB_SOURCE_IDS)
def test_extracted_files_are_up_to_date(sid):
    """Committed files equal a fresh extraction (catches edits by hand or stale output)."""
    e = SOURCE_REGISTRY[sid]
    fresh = extract_kb.extract_csv(e) if e.file.endswith(".csv") else extract_kb.extract_pdf(e)
    assert e.extracted_path.read_text(encoding="utf-8").endswith(fresh.strip() + "\n")


def _words(text: str) -> Counter:
    return Counter(re.findall(r"[A-Za-z0-9€%#@]+", text))


@pytest.mark.parametrize("sid", [s for s in KB_SOURCE_IDS if SOURCE_REGISTRY[s].file.endswith(".pdf")])
def test_no_pdf_text_lost(sid):
    """Every word of the PDF text layer survives, except the repeated page headers/numbers."""
    import pymupdf

    e = SOURCE_REGISTRY[sid]
    doc = pymupdf.open(KB_DIR / e.file)
    raw = "\n".join(
        line
        for page in doc
        for line in page.get_text().splitlines()
        if not extract_kb._HEADER_LINE.match(line.strip()) and not line.strip().isdigit()
    )
    missing = _words(raw) - _words(e.extracted_path.read_text(encoding="utf-8"))
    assert not missing, f"{sid}: words lost in extraction: {dict(missing)}"


def test_kb_block_is_deterministic_and_complete():
    block = load_kb_block()
    load_kb_block.cache_clear()
    assert load_kb_block() == block  # byte-identical -> prompt-cache stable
    for sid in KB_SOURCE_IDS:
        assert f'<document source_id="{sid}">' in block
    assert block.index("KB-01") < block.index("KB-13")
    assert 2_000 < len(block.split()) < 10_000  # sanity: whole KB, a few thousand words


def test_kb_source_is_a_valid_contract_source():
    s = kb_source("KB-11", version=1)
    assert isinstance(s, Source)
    assert s.origin == "kb" and s.category == "company_record" and s.added_in_version == 1


def test_unknown_kb_ids():
    assert unknown_kb_ids(["KB-01", "KB-14", "U-03", "KB-99"]) == ["KB-14", "KB-99"]
