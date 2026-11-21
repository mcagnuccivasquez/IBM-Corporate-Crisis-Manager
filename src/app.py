"""ACME Crisis Manager: Streamlit chat UI (A0 spec §6).

    streamlit run src/app.py
    (Windows, without activating the venv: .\\.venv\\Scripts\\python.exe -m streamlit run src/app.py)

Thin UI: every turn goes through src.pipeline.run_turn. The UI only shows the chat,
the per-agent progress, the report versions with PDF downloads, and the risk badge.
Chat history is stored per case in cases/<case_id>/chat.jsonl.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # `streamlit run src/app.py` puts src/ on the path, not the repo root
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from src import pipeline  # noqa: E402

RISK_COLORS = {"Low": "green", "Medium": "yellow", "High": "orange", "Critical": "red"}
NEW_CASE = "➕ New case"
FILE_TYPES = ["pdf", "png", "jpg", "jpeg", "txt", "md"]

st.set_page_config(page_title="ACME Crisis Manager", page_icon="🛡️", layout="wide")
st.session_state.setdefault("case_id", None)
st.session_state.setdefault("pending", [])  # messages of a new case before it has an ID


def risk_badge(level: str | None, label: str = "Risk") -> None:
    if level:
        st.badge(f"{label}: {level}", color=RISK_COLORS.get(level, "gray"))
    else:
        st.badge(f"{label}: not assessed yet", color="gray")


def pdf_download(pdf_path: str | None, key: str, label: str = "Download PDF") -> None:
    if not pdf_path:
        return
    path = Path(pdf_path) if Path(pdf_path).is_absolute() else ROOT / pdf_path
    if path.exists():
        st.download_button(label, data=path.read_bytes(), file_name=path.name, mime="application/pdf",
                           key=key, icon=":material/download:")


def show_message(msg: dict, idx: int) -> None:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("attachments"):
            st.caption("📎 " + ", ".join(msg["attachments"]))
        if msg.get("error"):
            with st.expander("Error details"):
                st.code(msg["error"])
        pdf_download(msg.get("pdf_path"), key=f"chat-pdf-{idx}", label=f"Download report v{msg.get('version')}")


# ---------------------------------------------------------------------------
# Sidebar: cases, versions, settings
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🛡️ ACME Crisis Manager")
    st.caption("Drafts and recommends only: it never sends statements, notifications or recalls.")

    cases = pipeline.list_cases()
    options = [NEW_CASE] + cases
    current = st.session_state.case_id if st.session_state.case_id in cases else NEW_CASE
    choice = st.selectbox("Case", options, index=options.index(current))
    if choice != current:
        st.session_state.case_id = None if choice == NEW_CASE else choice
        st.session_state.pending = []
        st.rerun()

    case_id = st.session_state.case_id
    state = pipeline.load_state(case_id) if case_id else None
    if state:
        risk_badge(state.risk.level if state.risk else None)
        if state.risk:
            st.caption(f"Evidence confidence: {state.risk.evidence_confidence}")
        st.caption(f"Status: **{state.status}** · focus: {state.focus or 'none'}")
        st.subheader("Report versions")
        for v in range(state.version, 0, -1):
            sv = pipeline.load_state(case_id, v)
            level = sv.risk.level if sv and sv.risk else "?"
            st.markdown(f"**v{v}** · {level}")
            pdf_download(sv.report.pdf_path if sv and sv.report else None, key=f"side-pdf-{v}", label=f"report_v{v}.pdf")

    st.divider()
    use_stubs = st.toggle("Stub agents (no API cost)", value=False,
                          help="Use fixture outputs for every agent. Off: real agents where they exist, stubs for the rest.")
    used = pipeline.load_agents(use_stubs).used
    with st.expander("Agents in use"):
        for slot, impl in used.items():
            st.markdown(f"- **{slot}**: {'stub' if impl == 'stub' else impl}")


# ---------------------------------------------------------------------------
# Main: chat
# ---------------------------------------------------------------------------

if case_id:
    st.header(f"{case_id}" + (" · closed" if state and state.status == "closed" else ""))
else:
    st.header("New case")
    st.markdown("Describe the incident and attach any evidence (screenshots, PDFs, text). "
                "The agents assess it and write **Report v1**. Later messages add evidence, report "
                "action updates, ask questions, or close the case.")

history = pipeline.load_chat(case_id) if case_id else st.session_state.pending
for i, msg in enumerate(history):
    show_message(msg, i)

prompt = st.chat_input("Describe new evidence, an action update, or ask a question…",
                       accept_file="multiple", file_type=FILE_TYPES)

if prompt:
    text = getattr(prompt, "text", prompt) or ""
    files = list(getattr(prompt, "files", []) or [])
    user_msg = {"role": "user", "content": text or "(attachment)", "attachments": [f.name for f in files]}
    show_message(user_msg, len(history))

    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for f in files:  # run_turn copies them into cases/<id>/inputs/
            p = Path(tmp) / Path(f.name).name
            p.write_bytes(f.getvalue())
            paths.append(p)

        with st.chat_message("assistant"):
            with st.status("Starting…", expanded=True) as status:
                def on_step(step: str) -> None:
                    status.update(label=f"{step}…")
                    status.write(f"⏳ {step}")

                result = pipeline.run_turn(text, paths, case_id, use_stubs=use_stubs, on_step=on_step)
                if result.error:
                    status.update(label="Analysis failed", state="error", expanded=True)
                elif result.new_version:
                    status.update(label=f"Report v{result.version} ready", state="complete", expanded=False)
                else:
                    status.update(label="Answered (no new report version)", state="complete", expanded=False)

    bot_msg = {"role": "assistant", "content": result.reply, "version": result.version if result.new_version else None,
               "pdf_path": result.pdf_path, "error": result.error, "intents": result.intents}
    if result.case_id:
        for m in st.session_state.pending:  # a new case just got its ID: keep its first messages
            pipeline.append_chat(result.case_id, m)
        st.session_state.pending = []
        pipeline.append_chat(result.case_id, user_msg)
        pipeline.append_chat(result.case_id, bot_msg)
        st.session_state.case_id = result.case_id
    else:
        st.session_state.pending += [user_msg, bot_msg]
    st.rerun()
