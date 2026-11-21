"""Streamlit UI, headless (streamlit.testing AppTest), stub agents only: no API cost."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src import pipeline

APP = str(Path(__file__).resolve().parent.parent / "src" / "app.py")


@pytest.fixture(autouse=True)
def tmp_cases(tmp_path, monkeypatch):
    monkeypatch.setenv("ACME_CASES_DIR", str(tmp_path))
    return tmp_path


def _app() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    at.toggle[0].set_value(True).run()  # stub agents
    return at


def test_empty_app_shows_new_case():
    at = _app()
    assert at.header[0].value == "New case"
    assert at.selectbox[0].value == "➕ New case"


def test_first_turn_creates_case_v1_and_chat_history(tmp_cases):
    at = _app()
    at.chat_input[0].set_value("Customers in Germany report PCX-100 chargers getting hot").run()
    assert not at.exception
    assert at.session_state.case_id == "CASE-001"
    assert (tmp_cases / "CASE-001" / "state_v1.json").exists()
    chat = pipeline.load_chat("CASE-001")
    assert [m["role"] for m in chat] == ["user", "assistant"]
    assert chat[1]["version"] == 1 and "Report v1" in chat[1]["content"]
    assert at.header[0].value == "CASE-001"
    sidebar_text = " ".join(m.value for m in at.sidebar.markdown)
    assert "Risk: High" in sidebar_text  # st.badge renders as markdown
    assert "**v1**" in sidebar_text


def test_question_turn_adds_no_version(tmp_cases):
    at = _app()
    at.chat_input[0].set_value("Customers in Germany report PCX-100 chargers getting hot").run()
    at.chat_input[0].set_value("Why is the risk High?").run()
    assert not at.exception
    assert sorted(p.name for p in (tmp_cases / "CASE-001").glob("state_v*.json")) == ["state_v1.json"]
    chat = pipeline.load_chat("CASE-001")
    assert len(chat) == 4 and chat[3]["version"] is None


def test_switching_back_to_new_case():
    at = _app()
    at.chat_input[0].set_value("Customers in Germany report PCX-100 chargers getting hot").run()
    at.selectbox[0].set_value("➕ New case").run()
    assert not at.exception
    assert at.session_state.case_id is None and at.header[0].value == "New case"
