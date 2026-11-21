"""Tests for the A5 report renderer (src/report/render.py).

Run: .venv/bin/python -m pytest tests/test_a5_render.py -v
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.report import render  # noqa: E402

SAMPLE = ROOT / "src" / "report" / "sample_state_v1_TEMPORARY.json"

SECTION_HEADINGS = [
    "1. Situation", "2. Evidence", "3. Risk and reasons", "4. Impacts", "5. Stakeholders",
    "6. Action plan", "7. Outlook if priority actions succeed", "8. Changes since",
    "Appendix A", "Appendix B", "Appendix C",
]


@pytest.fixture
def state():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def make_v2(state, new_level="High"):
    s = copy.deepcopy(state)
    s["version"] = 2
    s["risk"]["previous_level"] = "High"
    s["risk"]["level"] = new_level
    s["changelog"].append({"version": 2, "risk_from": "High", "risk_to": new_level, "new_source_ids": [],
                           "claim_changes": [], "action_changes": ["ACT-002 proposed -> approved"], "summary": None})
    return s


# ---------------------------------------------------------------- structure

def test_all_sections_present(state):
    html = render.render_html(state)
    for heading in SECTION_HEADINGS:
        assert heading in html, heading


def test_section_9_only_when_closed(state):
    assert "9. Case closed" not in render.render_html(state)
    closed = copy.deepcopy(state)
    closed["status"] = "closed"
    closed["closure"] = {"remaining_risk": "Medium", "open_actions": ["ACT-004"], "reopen_conditions": ["New smoke report"]}
    html = render.render_html(closed)
    assert "9. Case closed" in html
    assert "Start the shared incident playbook" in html  # open action resolved to its title
    assert "New smoke report" in html


def test_v1_says_initial_assessment(state):
    assert "Initial assessment" in render.render_html(state)


def test_v2_explains_unchanged_level(state):
    html = render.render_html(make_v2(state, "High"))
    assert "Initial assessment" not in html
    assert "Changes since v1" in html
    assert "(unchanged)" in html


def test_v2_changed_level_not_marked_unchanged(state):
    assert "(unchanged)" not in render.render_html(make_v2(state, "Critical"))


def test_footer_disclaimer_text():
    assert "Does not execute recalls, notifications or public statements" in render.DISCLAIMER


def test_same_state_renders_identically(state):
    assert render.render_html(state) == render.render_html(copy.deepcopy(state))


# ---------------------------------------------------------------- evidence

def test_claim_change_label():
    assert render.claim_change_label({"first_seen_version": 2, "last_changed_version": 2}, 2) == "New in v2"
    assert render.claim_change_label({"first_seen_version": 1, "last_changed_version": 2}, 2) == "Changed in v2"
    assert render.claim_change_label({"first_seen_version": 1, "last_changed_version": 1}, 3) == "No change since v1"
    assert render.claim_change_label({"first_seen_version": 1, "last_changed_version": 2}, 3) == "No change since v2"


# ---------------------------------------------------------------- readability

def test_citation_becomes_small_clickable_reference():
    html = render.linkify("Smoke reported [C-001, U-01].", {"C-001", "U-01"})
    assert '<sup class="cite"><a class="ref" href="#ref-C-001">C-001</a>, <a class="ref" href="#ref-U-01">U-01</a></sup>' in html
    assert "[" not in html


def test_unknown_id_is_not_linked_and_is_marked():
    html = render.linkify("See [C-899].", {"C-001"})
    assert 'ref-unknown">C-899' in html and 'href="#ref-C-899"' not in html


def test_linkify_escapes_html():
    assert "<script>" not in render.linkify("<script>x</script> C-001", {"C-001"})


def test_every_link_has_a_target(state):
    import re
    html = render.render_html(state)
    targets = set(re.findall(r'id="(ref-[^"]+)"', html))
    links = set(re.findall(r'href="#(ref-[^"]+)"', html))
    assert links <= targets, links - targets


def test_sources_are_shown_with_their_title(state):
    html = render.render_html(state)
    assert 'href="#ref-KB-13">KB-13</a> <span class="ref-title">PCX-100 stock export</span>' in html


def test_page_one_blocks_present(state):
    html = render.render_html(state)
    assert "How to read this report" in html
    assert "Priority actions (P1)" in html
    assert "Evidence status" in html


def test_missing_data_is_reported_not_hidden(state):
    s = copy.deepcopy(state)
    del s["stakeholders"]
    del s["impacts"]["economic"]
    html = render.render_html(s)
    assert "Field &#39;stakeholders&#39; is missing from the case data" in html
    assert "Impact domain &#39;economic&#39; is missing from the case data" in html


def test_claims_grouped_into_three_tables(state):
    g = render.group_claims(state["claims"])
    assert [c["claim_id"] for c in g["confirmed"]] == ["C-002", "C-003"]
    assert [c["claim_id"] for c in g["unconfirmed"]] == ["C-001"]
    assert [c["claim_id"] for c in g["disproved_or_misleading"]] == ["C-004"]


def test_unknown_claim_status_is_an_error():
    with pytest.raises(ValueError):
        render.group_claims([{"claim_id": "C-9", "status": "probably"}])


# ---------------------------------------------------------------- actions

def test_actions_sorted_by_priority_then_focus():
    actions = [
        {"action_id": "A", "priority": "P2", "focus_related": True},
        {"action_id": "B", "priority": "P1", "focus_related": False},
        {"action_id": "C", "priority": "P1", "focus_related": True},
        {"action_id": "D", "priority": "P3"},
    ]
    assert [a["action_id"] for a in render.sort_actions(actions)] == ["C", "B", "A", "D"]


def test_actions_without_focus_flag_keep_state_order_within_priority():
    actions = [{"action_id": "X", "priority": "P1"}, {"action_id": "Y", "priority": "P1"}]
    assert [a["action_id"] for a in render.sort_actions(actions)] == ["X", "Y"]


def test_status_labels(state):
    s = copy.deepcopy(state)
    s["actions"][0]["status"] = "verified_effective"
    s["actions"][1]["status"] = "verified_ineffective"
    html = render.render_html(s)
    assert "verified ✓" in html and "verified ✗" in html


# ---------------------------------------------------------------- empty and missing data

def test_empty_state_prints_none_reported():
    minimal = {"case_id": "CASE-X", "version": 1, "status": "open", "risk": {}, "impacts": {}}
    html = render.render_html(minimal)
    assert "None reported" in html
    for heading in SECTION_HEADINGS:
        assert heading in html, heading


def test_cited_but_unregistered_source_is_flagged(state):
    s = copy.deepcopy(state)
    s["actions"][0]["basis_source_ids"] = ["KB-99"]
    html = render.render_html(s)
    assert "Cited but missing from the source register: KB-99" in html


# ---------------------------------------------------------------- PDF file

def test_pdf_path():
    assert render.pdf_path_for({"case_id": "CASE-001", "version": 3}, "cases") == Path("cases/CASE-001/report_v3.pdf")


def test_never_overwrites_existing_version(state, tmp_path):
    existing = render.pdf_path_for(state, tmp_path)
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"old")
    with pytest.raises(FileExistsError):
        render.render_pdf(state, tmp_path)
    assert existing.read_bytes() == b"old"


def test_pdf_is_written(state, tmp_path):
    pytest.importorskip("playwright")
    out = render.render_pdf(state, tmp_path)
    assert out == tmp_path / "CASE-001" / "report_v1.pdf"
    assert out.read_bytes()[:5] == b"%PDF-"
