"""Combined entry point: the SIP Discovery chatbot plus the discovery-engine dashboard, as separate tabs in one UI.

The chatbot is src/app.py and is NOT modified: it runs unchanged inside the first tab. The dashboard (dashboard/streamlitapp.py) supplies the other
tabs and reads only dashboard/export/. Only the selected tab runs, so opening the chatbot never loads the dashboard and the reverse.

Run:  streamlit run streamlit_app.py
"""
import runpy
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="SIP Discovery", page_icon="🌱", layout="wide")

CHAT, DASHBOARD = "💬 Chatbot", "📊 Dashboard"
PAGES = {                                             # dashboard tab label -> dashboard page
    "1 Overview": "1 · Overview & how it works", "2 Opportunities": "2 · Opportunity ranking", "3 Nine questions": "3 · The nine questions",
    "4 Metric tree": "4 · Metric tree", "5 Segments": "5 · Segments & sources", "6 Evidence": "6 · Evidence explorer",
    "7 Ask the data": "7 · Ask the data", "8 Validation": "8 · Validation & limitations",
}
st.markdown("<div style='height:1.3rem'></div>", unsafe_allow_html=True)       # keeps the tab bar clear of Streamlit's top bar
wanted = st.query_params.get("view")
view = st.segmented_control("View", [CHAT, DASHBOARD], default=wanted if wanted in (CHAT, DASHBOARD) else CHAT, key="main_view",
                            label_visibility="collapsed") or CHAT
st.query_params["view"] = view

if view == CHAT:
    _real = st.set_page_config
    st.set_page_config = lambda *a, **k: None         # the chatbot sets its own page config; the combined app already did
    try:
        runpy.run_path(str(ROOT / "src" / "app.py"), run_name="__main__")
    finally:
        st.set_page_config = _real
else:
    wanted_page = st.query_params.get("page")
    page = st.segmented_control("Dashboard page", list(PAGES), default=wanted_page if wanted_page in PAGES else "1 Overview", key="dash_page",
                                label_visibility="collapsed") or "1 Overview"
    st.query_params["page"] = page
    sys.path.insert(0, str(ROOT / "dashboard"))
    import streamlitapp as dash                       # noqa: E402 (imported only when the dashboard tab is opened)
    dash.inject_css()
    dash.PAGES[PAGES[page]]()
