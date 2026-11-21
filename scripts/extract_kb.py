"""Extract the 12 KB PDFs + the stock CSV into knowledge_base/extracted/KB-xx.md.

Run once from the repo root (re-run only if the KB files change):
    python scripts/extract_kb.py

Output is deterministic: same input -> byte-identical files, so the KB block
stays prompt-cache stable. The generated files are committed.

What the conversion does:
  - drops the repeated page header lines and page numbers
  - converts tables to markdown (merging rows that wrapped onto a second line)
  - marks page breaks as [page N]
  - adds an [Extraction note: ...] where a PDF contains an image. The screenshots in
    KB-06/07/09 have their full text in the PDF text layer, which is kept verbatim;
    the other two images are illustrations with no text.
  - CSV: the original rows as a markdown table, plus totals computed by this script
    (labelled as such)
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.kb import EXTRACTED_DIR, KB_DIR, SOURCE_REGISTRY, KBEntry, entry_header  # noqa: E402

# Verified by viewing each image (2026-11-21). Keyed by (source_id, page number).
IMAGE_NOTES: dict[tuple[str, int], str] = {
    ("KB-01", 1): "Photo of an office and an electronics workbench. Illustration only, contains no text.",
    ("KB-03", 1): "Sales illustration: black charger with two USB-C ports and one USB-A port, a box and a USB-C cable. Contains no text.",
    ("KB-06", 2): "Screenshot of the service desk ticket; the text below is the text of the screenshot. "
    "A copy of the same image is original_screenshots/ticket_4471_capture.png (not an independent source).",
    ("KB-07", 1): "Screenshot of the TownSquare post; the text below is the text of the screenshot. "
    "A copy of the same image is original_screenshots/social_post_181125.png (not an independent source).",
    ("KB-09", 2): "Screenshot of the support console timeline; the text below is the text of the screenshot. "
    "A copy of the same image is original_screenshots/account_case_SC219.png (not an independent source).",
}

# Repeated on every page; kept once (first page) as the document label.
_HEADER_LINE = re.compile(r"^(ACME \| Internal|Mail \| .+|ACME Technologies & Consumer Electronics \| .+)$")


def _clean_cell(text: str | None) -> str:
    return " ".join((text or "").split())


def _cell_text(words: list[tuple], cell: tuple | None) -> str:
    """Words whose centre lies in the cell, in reading order. (table.extract() drops
    the spaces between words in these PDFs, so cells are rebuilt from word boxes.)"""
    if not cell:
        return ""
    box = pymupdf.Rect(cell)
    return _clean_cell(" ".join(w[4] for w in words if _inside(w[:4], box)))


def _table_markdown(page: pymupdf.Page, table) -> str:
    words = sorted(page.get_text("words"), key=lambda w: (w[5], w[6], w[7]))  # block, line, word
    header = [_cell_text(words, c) for c in table.header.cells]
    rows: list[list[str]] = []
    data_rows = table.rows if table.header.external else table.rows[1:]  # header may sit outside the table bbox
    for row in data_rows:
        cells = [_cell_text(words, c) for c in row.cells]
        if rows and not cells[0]:  # continuation of a wrapped row
            rows[-1] = [f"{a} {b}".strip() for a, b in zip(rows[-1], cells)]
        else:
            rows.append(cells)
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def _inside(rect: tuple, box: pymupdf.Rect) -> bool:
    cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
    return box.x0 <= cx <= box.x1 and box.y0 <= cy <= box.y1


def extract_pdf(entry: KBEntry) -> str:
    doc = pymupdf.open(KB_DIR / entry.file)
    out: list[str] = []
    label: list[str] = []
    for pno, page in enumerate(doc, start=1):
        tables = page.find_tables().tables
        boxes = [pymupdf.Rect(t.bbox) for t in tables]
        items: list[tuple[float, int, str]] = []  # (y, kind order, text)

        for t, box in zip(tables, boxes):
            items.append((box.y0, 1, _table_markdown(page, t)))

        images = page.get_image_info()
        image_boxes = [pymupdf.Rect(img["bbox"]) for img in images]
        for img in images:
            note = IMAGE_NOTES.get((entry.source_id, pno))
            if note is None:
                raise SystemExit(f"{entry.source_id} p{pno}: image without a note in IMAGE_NOTES; view it and add one")
            items.append((img["bbox"][1], 0, f"[Extraction note: {note}]"))

        for x0, y0, x1, y1, text, _bno, btype in page.get_text("blocks"):
            if btype != 0 or any(_inside((x0, y0, x1, y1), b) for b in boxes):
                continue
            kept = []
            for line in text.splitlines():
                line = line.strip()
                if not line or line == str(pno):
                    continue
                if _HEADER_LINE.match(line):
                    if pno == 1:
                        label.append(line)
                    continue
                kept.append(line)
            if kept:
                # screenshot text keeps its line breaks (timelines, post + replies); prose is joined
                in_image = any(_inside((x0, y0, x1, y1), b) for b in image_boxes)
                items.append((y0, 2, ("\n" if in_image else " ").join(kept)))

        items.sort(key=lambda it: (round(it[0], 1), it[1]))
        if pno > 1:
            out.append(f"[page {pno}]")
        out.extend(text for _, _, text in items)

    body = "\n\n".join(out)
    doc_label = " · ".join(label)
    return f"Document label: {doc_label}\n\n{body}" if doc_label else body


def extract_csv(entry: KBEntry) -> str:
    with open(KB_DIR / entry.file, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    cols = list(rows[0].keys())
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(r[c] for c in cols) + " |" for r in rows]

    totals: dict[tuple[str, str], int] = defaultdict(int)
    for r in rows:
        totals[(r["batch"], r["quantity_type"])] += int(r["units"])
    batches = sorted({b for b, _ in totals})
    types = sorted({q for _, q in totals})
    summary = ["| batch | " + " | ".join(types) + " | total |", "|---|" + "---|" * (len(types) + 1)]
    for b in batches:
        vals = [totals[(b, q)] for q in types]
        summary.append(f"| {b} | " + " | ".join(f"{v:,}" for v in vals) + f" | {sum(vals):,} |")
    col_tot = [sum(totals[(b, q)] for b in batches) for q in types]
    summary.append("| all | " + " | ".join(f"{v:,}" for v in col_tot) + f" | {sum(col_tot):,} |")

    return (
        "Original rows (CSV):\n\n" + "\n".join(lines) + "\n\n"
        "[Extraction note: totals below were computed by the extraction script from the rows above; "
        "they are not in the original file. delivered_to_channels means delivered to retailers / online "
        "fulfilment, not sold to consumers.]\n\n" + "\n".join(summary)
    )


def main() -> None:
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    for entry in SOURCE_REGISTRY.values():
        body = extract_csv(entry) if entry.file.endswith(".csv") else extract_pdf(entry)
        text = entry_header(entry) + "\n" + body.strip() + "\n"
        entry.extracted_path.write_text(text, encoding="utf-8", newline="\n")
        print(f"{entry.source_id}  {len(text.split()):5d} words  -> {entry.extracted_path.relative_to(KB_DIR.parent.parent)}")


if __name__ == "__main__":
    main()
