"""Streamlit UI (PRD FR9). Run: .venv/bin/streamlit run src/app.py

The page only shows what generate.answer() returns: the short answer, ONE citation link, the "Last updated from sources"
line and an expandable "See what people said" list (Hinglish text is shown as written). Nothing is stored: the question
is kept only in memory for the current page, and never shown again when it contained personal details.
"""
import html
import re
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import generate as G  # noqa: E402
import retrieve as R  # noqa: E402

GREEN, DARK, SOFT = "#00B386", "#44475B", "#EAF8F4"

st.set_page_config(page_title="SIP Discovery", page_icon="🌱", layout="centered")
st.markdown(f"""
<style>
  .block-container {{ max-width: 760px; padding-top: 2rem; }}
  h1 {{ color: {GREEN}; }}
  .note {{ background: {SOFT}; color: {DARK}; border-left: 4px solid {GREEN}; padding: .6rem .9rem; border-radius: 6px; font-size: .92rem; }}
  .answer {{ border: 1px solid #E0E4EA; border-radius: 10px; padding: 1rem 1.2rem; font-size: 1.05rem; line-height: 1.55; }}
  .meta {{ color: #7C7E8C; font-size: .85rem; margin-top: .5rem; }}
  .src {{ border-left: 3px solid {GREEN}; padding: .2rem .8rem; margin: .6rem 0; }}
  .src b {{ color: {DARK}; font-size: .85rem; }}
  .src p {{ margin: .15rem 0 0 0; white-space: pre-wrap; font-size: .92rem; }}
  div.stButton > button {{ border: 1px solid {GREEN}; color: {GREEN}; background: white; }}
  div.stButton > button:hover {{ background: {GREEN}; color: white; border-color: {GREEN}; }}
  div.stButton > button[kind="primary"] {{ background: {GREEN}; color: white; }}
</style>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Loading the search index...")
def get_retriever():
    return R.Retriever()


def ask(question: str):
    st.session_state.result = G.answer(question, retriever=get_retriever())
    st.session_state.question = question


def esc(text: str) -> str:
    return html.escape(re.sub(r"[ \t]+", " ", text or "").strip())


def show_sources(sources):
    if not sources:
        return
    with st.expander(f"See what people said ({len(sources)} sources)"):
        for s in sources:
            st.markdown(f"<div class='src'><b>{esc(s['label'])}</b><p>{esc(s['text'])}</p></div>", unsafe_allow_html=True)


def show_result(res):
    status = res["status"]
    if status == "answered":
        st.markdown(f"<div class='answer'>{esc(res['answer'])}</div>", unsafe_allow_html=True)
        st.markdown(f"Source: [{res['citation_label']}]({res['citation']})")
    elif status == "answer_unavailable":
        st.warning(res["message"])
    elif status == "refused_advice":
        st.info(res["message"])
        if res.get("link"):
            st.markdown(f"Learn more: [{res['link_label']}]({res['link']})")
    else:                                                    # invalid input, personal details, not enough evidence
        st.info(res["message"])
        if status == "not_enough_evidence":
            st.caption("Try one of these instead:")
            for q in C.EXAMPLE_QUESTIONS:
                st.markdown(f"- {q}")
    if res.get("last_updated_line"):
        st.markdown(f"<div class='meta'>{esc(res['last_updated_line'])}</div>", unsafe_allow_html=True)
    show_sources(res.get("sources"))


st.title("SIP Discovery")
st.write("Ask what real people say about starting, pausing or stopping a SIP. Answers come only from "
         "Play Store reviews and Reddit posts about Groww and SIPs.")
st.markdown("<div class='note'><b>Facts-only. No investment advice.</b> This is a small, hand-picked sample "
            "of public reviews and posts. It does not represent all investors.</div>", unsafe_allow_html=True)
st.write("")

st.caption("Try an example:")
for i, q in enumerate(C.EXAMPLE_QUESTIONS):
    if st.button(q, key=f"ex{i}", use_container_width=True):
        ask(q)

with st.form("ask", clear_on_submit=False):
    typed = st.text_input("Your question", placeholder="For example: What do people say about autopay failing?",
                          max_chars=C.MAX_QUESTION_CHARS)
    submitted = st.form_submit_button("Ask", type="primary")
if submitted:
    ask(typed)

res = st.session_state.get("result")
if res:
    st.divider()
    if res["status"] != "declined_pii" and st.session_state.get("question"):   # never echo personal details back
        st.markdown(f"**You asked:** {esc(st.session_state.question)}")
    if res.get("rewrite_used") and res.get("question_english"):
        st.caption(f"Understood as: {res['question_english']}")
    show_result(res)
    if res["status"] == "declined_pii":
        st.session_state.question = ""
