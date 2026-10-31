"""SIP discovery engine dashboard.

Standalone: app/run.sh   (or: cd app && ../.venv/bin/streamlit run streamlitapp.py)
As tabs inside the chatbot app: the repo-root streamlit_app.py imports this module and calls inject_css() and PAGES[name]().

Reads ONLY data/export/ (built by pipeline/export.py). Every number on every page comes from that folder; the only model call is the
written answer on "Ask the data", which is built from retrieved items and cites them.
"""
import html
import json
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import askdata  # noqa: E402

_HERE = Path(__file__).resolve().parent
EXPORT = next(p for p in (_HERE / "export", _HERE.parent / "data" / "export") if p.exists())   # in the repo: dashboard/export

# Okabe-Ito palette: distinguishable with the common forms of colour blindness. Meaning is never carried by colour alone (labels, symbols).
BLUE, ORANGE, GREEN, VERMILLION, PURPLE, SKY, GREY = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#6B7280"
SRC_COL = {"Reddit": BLUE, "Play Store": ORANGE, "YouTube": GREEN}
CLASS_COL = {"voluntary": BLUE, "involuntary": VERMILLION, "mixed": PURPLE}
SOURCES = ("Reddit", "Play Store", "YouTube")
SEV_SYMBOL = {"High": "●●●", "Medium": "●●○", "Low": "●○○", "Unclear": "?"}

@st.cache_data
def load(stamp):
    meta = json.load(open(EXPORT / "meta.json", encoding="utf-8"))
    tables = json.load(open(EXPORT / "tables.json", encoding="utf-8"))
    ev = pd.read_csv(EXPORT / "evidence.csv", keep_default_na=False, dtype={"age": str})
    ev["is_relevant"] = ev["is_relevant"].astype(str).str.lower().eq("true")
    ev["lapse"] = ev["lapse"].astype(str).str.lower().eq("true")
    return meta, tables, ev


META, T, EV = load(max(f.stat().st_mtime for f in EXPORT.glob("*.json")))
THEMES = T["themes"]
fmt = lambda n: f"{int(n):,}"
esc = lambda s: html.escape(str(s or ""))

def inject_css():
    st.markdown(f"""
<style>
  .block-container {{ padding-top: 1.4rem; max-width: 1500px; }}
  h1 {{ font-size: 1.7rem !important; line-height: 1.25 !important; }}
  .banner {{ background:#EEF4FA; border-left:5px solid {BLUE}; padding:.55rem .9rem; border-radius:6px; font-size:.92rem; margin-bottom:.9rem; }}
  .banner b {{ color:#0B3D66; }}
  .quote {{ border-left:3px solid {BLUE}; padding:.15rem .75rem; margin:.45rem 0; font-size:.93rem; }}
  .quote small {{ color:{GREY}; display:block; margin-top:.1rem; }}
  .draft {{ background:#FFF6E0; border-left:5px solid {ORANGE}; padding:.5rem .8rem; border-radius:6px; font-size:.88rem; margin:.4rem 0 .9rem; }}
  table.t {{ border-collapse:collapse; width:100%; font-size:.84rem; }}
  table.t th {{ text-align:left; background:#F3F4F6; padding:.45rem .5rem; border-bottom:2px solid #D1D5DB; position:sticky; top:0; }}
  table.t td {{ padding:.45rem .5rem; border-bottom:1px solid #E5E7EB; vertical-align:top; }}
  table.t td.n, table.t th.n {{ text-align:right; white-space:nowrap; }}
  .bar {{ height:7px; background:{BLUE}; border-radius:3px; margin-top:3px; }}
  table.t td.q {{ min-width:190px; max-width:230px; }}
  table.opp {{ font-size:.78rem; }}
  table.opp th, table.opp td {{ padding:.4rem .3rem; }}
  .tiny {{ color:{GREY}; font-size:.76rem; }}
  .strip {{ margin:-.3rem 0 .7rem; font-size:.9rem; }}
  .strip .lab {{ color:{GREY}; font-size:.78rem; }}
  .lowc {{ background:#FDECEA; color:#8A2A0B; padding:0 .35rem; border-radius:4px; font-size:.75rem; white-space:nowrap; }}
</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ shared pieces
def banner():
    m = META
    st.markdown(f"<div class='banner'>Data as of <b>{pd.Timestamp(m['as_of']).strftime('%d %b %Y')}</b> · <b>{fmt(m['tagged'])}</b> tagged · "
                f"<b>{fmt(m['relevant'])}</b> relevant (rated Y or P)</div>", unsafe_allow_html=True)
    with st.expander("What do tagged and relevant mean?"):
        st.write(m["definitions"]["tagged"])
        st.write(m["definitions"]["relevant"])
        st.write(m["definitions"]["lapse_story"])


def source_strip(label, split):
    """The split by source behind a headline number, so a reader sees how much of it is Reddit, Play Store or YouTube."""
    parts = " &nbsp;·&nbsp; ".join(f"<b style='color:{SRC_COL[g]}'>■</b> {g} <b>{fmt(split.get(g, 0))}</b>" for g in SOURCES)
    st.markdown(f"<div class='strip'><span class='lab'>{esc(label)}</span><br>{parts}</div>", unsafe_allow_html=True)


def subtheme_block(parent):
    sub = T["subthemes"][parent]
    rows = [x for x in sub["subs"] if x["items"] > 0]
    head = ("<tr><th>Sub-theme</th><th class='n'>Items</th><th class='n'>Reddit</th><th class='n'>Play Store</th><th class='n'>YouTube</th>"
            "<th>Example quote</th></tr>")
    body = "".join(f"<tr><td><b>{esc(x['label'])}</b></td><td class='n'>{fmt(x['items'])}</td><td class='n'>{x['by_source']['Reddit']}</td>"
                   f"<td class='n'>{x['by_source']['Play Store']}</td><td class='n'>{x['by_source']['YouTube']}</td>"
                   f"<td class='q'>{quote_html(dict(x['quote'], match=x['quote'].get('match', True))) if x['quote'] else ''}</td></tr>" for x in rows)
    st.markdown(f"<div style='overflow-x:auto'><table class='t opp'>{head}{body}</table></div>", unsafe_allow_html=True)
    st.caption(f"{fmt(sub['items'])} relevant items carry this bucket. An item can fall in more than one sub-theme, so the rows add up to more than the bucket. "
               "Sub-themes are found by keyword rules on the verified quote and the first 600 characters of the text.")
    if sub["items"] < 10:
        st.caption(f"Only {sub['items']} items carry this bucket, too few to read as a pattern. Complaints about how the app works are rare in this evidence, "
                   "because the Play Store reviews were chosen for being about SIPs and mutual funds.")


def draft_note(text):
    st.markdown(f"<div class='draft'><b>Draft judgement.</b> {esc(text)}</div>", unsafe_allow_html=True)


def quote_html(q):
    link = f" · <a href='{esc(q['link'])}' target='_blank'>open</a>" if q.get("link") else ""
    near = "" if q.get("match", True) else " · closest available quote; it may not name this theme"
    return f"<div class='quote'>“{esc(q['quote'])}”<small>{esc(q['source'])}, {esc(q['date'])}{link}{esc(near)}</small></div>"


def text_table(df):
    """Small tables with long text: full text wraps instead of being cut off. Numbers get thousands separators."""
    head = "".join(f"<th>{esc(c)}</th>" for c in df.columns)
    body = ""
    for row in df.itertuples(index=False):
        body += "<tr>" + "".join(f"<td class='{'n' if isinstance(v, (int, float)) and not isinstance(v, bool) else ''}'>"
                                 f"{esc(fmt(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v)}</td>" for v in row) + "</tr>"
    st.markdown(f"<div style='overflow-x:auto'><table class='t'>{head and '<tr>' + head + '</tr>'}{body}</table></div>", unsafe_allow_html=True)


def theme_label(code):
    return THEMES.get(code, code.replace("_", " ").capitalize())


def style(fig, h=360, legend=True):
    fig.update_layout(template="plotly_white", height=h, margin=dict(l=10, r=10, t=30, b=40), font=dict(size=13),
                      legend=dict(orientation="h", y=-0.3, x=0) if legend else None, showlegend=legend)
    return fig


# ------------------------------------------------------------------ 1. overview
def page_overview():
    cf = dict(T["combined_funnel"])
    st.title(f"The engine read {fmt(cf['Collected'])} public posts, reviews and comments and kept {fmt(META['relevant'])} as evidence")
    banner()
    source_strip("Kept as evidence (relevant), by source", T["headline"]["p1"]["relevant"])
    st.subheader("How it works")
    dot = """digraph G { rankdir=LR; bgcolor="transparent"; nodesep=0.25;
      node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=12, margin="0.18,0.1", color="#0072B2", fillcolor="#EEF4FA"];
      edge [color="#6B7280", arrowsize=0.7];
      a [label="1  Collect\\nReddit, Play Store,\\nYouTube comments"];
      b [label="2  Filter\\nSIP keywords and\\nfirst-hand language"];
      c [label="3  Code (Claude)\\nrelevance, questions,\\nthemes, one quote"];
      d [label="4  Validate (script)\\nlabels, quote word\\nfor word in source"];
      e [label="5  Quantify\\ncounts as ranges,\\nopportunity scores"];
      f [label="6  Use\\nthis dashboard and\\nAsk the data", fillcolor="#FFF6E0", color="#E69F00"];
      a -> b -> c -> d -> e -> f; }"""
    st.graphviz_chart(dot, width="stretch")
    st.caption("Claude does the reading and coding. Scripts do the counting and checking. No count on this dashboard comes from a language model.")

    st.subheader("Sources and volumes")
    rows = []
    for g in SOURCES:
        d = T["dates"][g]
        rows.append({"Source": g, "Tagged": META["by_source"][g]["tagged"], "Relevant": META["by_source"][g]["relevant"],
                     "Earliest item": d["first"], "Latest item": d["last"]})
    rows.append({"Source": "All sources", "Tagged": META["tagged"], "Relevant": META["relevant"],
                 "Earliest item": min(T["dates"][g]["first"] for g in SOURCES), "Latest item": META["as_of"]})
    text_table(pd.DataFrame(rows))
    ex = T["exclusions"]
    st.caption("All Reddit items came from an automatic scan of five subreddits, filtered and ranked by rules. No threads were hand-picked, so there is nothing "
               f"\"curated\" to exclude. Replies written by the platform are excluded ({ex['coded']['excluded']} found among the {fmt(ex['coded']['checked'])} coded items).")

    st.subheader("From everything collected to what counts as evidence")
    labels, vals = [k for k, _ in T["combined_funnel"]], [v for _, v in T["combined_funnel"]]
    fig = go.Figure(go.Funnel(y=labels, x=vals, text=[f"{fmt(v)}" for v in vals], textinfo="text+percent previous", marker=dict(color=[SKY, BLUE, BLUE, GREEN, GREEN])))
    st.plotly_chart(style(fig, 330, False), width="stretch")
    with st.expander("Funnel for each source (table)", expanded=False):
        tabs = st.tabs(list(T["funnel"]))
        for tab, g in zip(tabs, T["funnel"]):
            with tab:
                text_table(pd.DataFrame(T["funnel"][g], columns=["Stage", "Items"]))
    st.caption("Round 1 coded Reddit only. Round 2 re-coded the Reddit items round 1 kept (plus the hand-labelled set) and coded Play Store and "
               "YouTube once. The headline counts use the final round, so tagged and relevant mean the same thing everywhere.")

    st.subheader("Date coverage")
    years = sorted({int(y) for g in SOURCES for y in T["dates"][g]["by_year"]})
    fig = go.Figure()
    for g in SOURCES:
        by = {int(k): v for k, v in T["dates"][g]["by_year"].items()}
        fig.add_bar(x=[str(y) for y in years], y=[by.get(y, 0) for y in years], name=g, marker_color=SRC_COL[g])
    fig.update_layout(barmode="stack", yaxis_title="Relevant items", xaxis_title="Year of the post, review or comment")
    st.plotly_chart(style(fig, 330), width="stretch")
    st.caption("Play Store reviews cover 2025 to 2026 only. Reddit is concentrated in 2023 to 2026. YouTube includes older top comments. YouTube only shows ages such as "
               "\"2 years ago\", so its dates are estimates (shown as \"about\" a month or year).")

    st.subheader("Models used")
    text_table(pd.DataFrame(T["models"]).rename(columns={"step": "Step", "model": "Model", "role": "What it does"}))


# ------------------------------------------------------------------ 2. opportunity ranking
def opp_table(rows):
    head = ("<tr><th>#</th><th>Theme</th><th class='n'>Posts</th><th class='n'>% of relevant</th><th>Severity</th><th>Branch</th>"
            "<th>Fixable?</th><th class='n'>Score</th><th>Quote 1</th><th>Quote 2</th></tr>")
    body = ""
    for n, r in enumerate(rows, 1):
        qs = r["quotes"] + [None] * (2 - len(r["quotes"]))
        sev_note = (f"{r['lapse_stories']} of {r['known_outcome']} lapsed" if r["severity"] != "Unclear" else f"only {r['known_outcome']} state an outcome")
        body += (f"<tr><td>{n}</td><td><b>{esc(r['label'])}</b><div class='tiny'>Reddit {r['by_source']['Reddit']} · Play Store "
                 f"{r['by_source']['Play Store']} · YouTube {r['by_source']['YouTube']}</div></td>"
                 f"<td class='n'>{fmt(r['posts'])}</td><td class='n'>{r['pct']}%</td>"
                 f"<td>{SEV_SYMBOL[r['severity']]} {esc(r['severity'])}<div class='tiny'>{esc(sev_note)}</div></td>"
                 f"<td><b>{esc(r['branch'])}</b><div class='tiny'>{esc(r['branch_name'])}</div></td><td><b>{esc(r['fixable'])}</b><div class='tiny'>{esc(r['fixable_why'])}</div></td>"
                 f"<td class='n'><b>{r['score']}</b><div class='bar' style='width:{r['score']}%'></div></td>"
                 f"<td class='q'>{quote_html(qs[0]) if qs[0] else ''}</td><td class='q'>{quote_html(qs[1]) if qs[1] else ''}</td></tr>")
    return f"<div style='overflow-x:auto'><table class='t opp'>{head}{body}</table></div>"


def page_opportunities():
    c, a = T["opportunities"]["causes"], T["opportunities"]["after_stop"]
    st.title(f"{c[0]['label']} ranks first among causes of lapse; {a[0]['label'].lower()} leads the problems after stopping")
    banner()
    source_strip(f"“{c[0]['label']}” (top cause), items by source", T["headline"]["p2"]["cause"])
    source_strip(f"“{a[0]['label']}” (top problem after stopping), items by source", T["headline"]["p2"]["after_stop"])
    draft_note("Severity bands, fixable ratings and metric-tree branches are the analyst's first read, set in pipeline/rules.py and meant to be "
               "tested in interviews. Counts and quotes are measured.")
    with st.expander("How to read the tables", expanded=False):
      st.markdown("*Posts* = relevant items carrying the theme. *Severity* = the share of items with a stated outcome whose author "
                "actually stopped, paused or reduced (High 45% or more, Medium 30% to 45%, Low below 30%; Unclear when fewer than 10 items state an "
                "outcome). *Fixable* = whether the brief's limits allow a fix: no fund or stock recommendations, no fear, FOMO or urgency. "
                "*Score* = % of relevant × severity share × fixable weight (High 1.0, Medium 0.6, Low 0.25), scaled so the top row in each table is 100. "
                "It orders rows for discussion; it is not a forecast.")
    st.subheader("Causes: why the SIP stops or is not kept going")
    st.markdown(opp_table(c), unsafe_allow_html=True)
    st.subheader("Problems after stopping: what goes wrong when someone exits or tries to come back")
    st.markdown(opp_table(a), unsafe_allow_html=True)
    st.subheader("What is inside the vague buckets")
    st.caption("Broad rows such as “hard to use the app” or “no control” are split into sub-themes. Open one to see the split by source and an example quote.")
    for parent in T["vague_pages"]["page2"]:
        sub = T["subthemes"][parent]
        with st.expander(f"{sub['label']}: {fmt(sub['items'])} items", expanded=False):
            subtheme_block(parent)


# ------------------------------------------------------------------ 3. nine questions
def page_questions():
    Q = T["questions"]
    most = max(Q, key=lambda q: Q[q]["items"])
    least = min(Q, key=lambda q: Q[q]["items"])
    st.title(f"Evidence is deepest for {most} ({fmt(Q[most]['items'])} items) and thinnest for {least} ({fmt(Q[least]['items'])} items)")
    banner()
    hl = T["headline"]["p3"]
    source_strip(f"{hl['most_q']} (most evidence), items by source", hl["most"])
    source_strip(f"{hl['least_q']} (least evidence), items by source", hl["least"])
    st.caption("An item can carry several questions, so counts overlap. Each quote below comes only from items tagged for that question.")
    for q, e in Q.items():
        with st.container(border=True):
            st.markdown(f"#### {q}. {e['question']}")
            st.markdown(f"**{e['finding']}**")
            left, right = st.columns([3, 2])
            ch = e["chart"]
            fig = go.Figure()
            if ch["kind"] == "stack":
                for g in SOURCES:
                    fig.add_bar(y=ch["x"], x=ch["series"][g], name=g, orientation="h", marker_color=SRC_COL[g])
                fig.update_layout(barmode="stack", xaxis_title="Items")
            else:
                for name, v in ch["series"].items():
                    fig.add_bar(x=ch["x"], y=v, name=name, marker_color=BLUE)
                fig.update_layout(yaxis_title="Items" if q == "Q7" else "% of items tagged Q8")
            with left:
                st.plotly_chart(style(fig, 320, ch["kind"] == "stack"), width="stretch", key=f"dash_q{q}")
            with right:
                for lab, val in e["numbers"]:
                    st.metric(lab, val if isinstance(val, str) else fmt(val))
                st.caption("Split by source: " + " · ".join(f"{g} {e['by_source'][g]}" for g in SOURCES))
            for qt in e["quotes"]:
                st.markdown(quote_html(qt), unsafe_allow_html=True)
            for parent in T["vague_pages"]["page3"].get(q, []):
                with st.expander(f"Inside “{T['subthemes'][parent]['label']}” ({fmt(T['subthemes'][parent]['items'])} items)", expanded=False):
                    subtheme_block(parent)


# ------------------------------------------------------------------ 4. metric tree
def page_tree():
    tr = T["tree"]
    rs = tr["reason_split"]
    allv = rs["all"]
    tot = sum(allv.values())
    ps = rs["by_source"]["Play Store"]
    hv = T["headline"]["p4"]
    st.title(f"Voluntary reasons dominate on Reddit ({hv['voluntary_pct']['Reddit']}%) and YouTube ({hv['voluntary_pct']['YouTube']}%), "
             f"but not in Play Store reviews ({hv['voluntary_pct']['Play Store']}%)")
    banner()
    source_strip(f"Items with a stated reason (the base of each percentage; {100 * allv['voluntary'] / tot:.0f}% voluntary overall, which mostly reflects the source mix)",
                 hv["base"])
    draft_note("The five branches and the voluntary or involuntary rule are a first decomposition from the evidence. Replace them with your Part 2 "
               "tree in pipeline/rules.py and re-export.")
    st.markdown(f"**Goal:** {tr['goal']}.")
    with st.expander("Definitions: voluntary, involuntary, mixed", expanded=False):
      st.markdown(f"**Voluntary** = the investor chooses to stop, pause or reduce (cash pressure, market fall, a better option). "
                "**Involuntary** = the SIP stops working without that choice (failed debit, mandate or KYC block, platform charge). "
                "**Mixed** = both appear in one item. Items with no lapse-related theme are left out of this split.")
    lines = "\n".join(f'b{i} [label="{b}  {v["name"]}\\n{fmt(v["posts"])} items ({v["pct"]}%)"];\n goal -> b{i};' for i, (b, v) in enumerate(tr["branches"].items()))
    dot = ('digraph G { rankdir=LR; bgcolor="transparent"; node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=12, '
           'color="#0072B2", fillcolor="#EEF4FA", margin="0.18,0.1"]; edge [color="#6B7280"]; goal [label="12-month SIP continuation\\n(first-time investors)", '
           'fillcolor="#FFF6E0", color="#E69F00"];\n' + lines + "}")
    st.subheader("Items per branch")
    st.graphviz_chart(dot, width="stretch")
    fig = go.Figure()
    names = [f"{b} {v['name']}" for b, v in tr["branches"].items()]
    for g in SOURCES:
        fig.add_bar(y=names[::-1], x=[tr["by_source"][g][b]["posts"] for b in tr["branches"]][::-1], name=g, orientation="h", marker_color=SRC_COL[g])
    fig.update_layout(barmode="stack", xaxis_title="Relevant items with a theme in the branch")
    st.plotly_chart(style(fig, 340), width="stretch")
    with st.expander("Which themes sit in each branch"):
        for b, ts in tr["branch_themes"].items():
            st.markdown(f"**{b} {tr['branches'][b]['name']}:** " + ", ".join(ts))

    st.subheader("Voluntary versus involuntary, by source")
    fig = go.Figure()
    for k in ("voluntary", "involuntary", "mixed"):
        fig.add_bar(y=list(SOURCES)[::-1], x=[100 * rs["by_source"][g][k] / max(1, sum(rs["by_source"][g].values())) for g in SOURCES][::-1],
                    name=k.capitalize(), orientation="h", marker_color=CLASS_COL[k],
                    text=[f"{rs['by_source'][g][k]}" for g in SOURCES][::-1], textposition="inside")
    fig.update_layout(barmode="stack", xaxis_title="% of items with a stated reason (labels show item counts)", xaxis_range=[0, 100])
    st.plotly_chart(style(fig, 280), width="stretch")
    st.caption("Reddit is almost all voluntary: people write about choices. App reviews are mostly about failures. The mix depends on where people "
               "write, so the overall split mainly reflects the source mix.")

    st.subheader("Per tagger: the two coding rounds on the same Reddit items")
    tg = tr["taggers"]
    fig = go.Figure()
    for key, col in (("r1", SKY), ("r2", BLUE)):
        d = tg[key]
        fig.add_bar(x=["Voluntary", "Involuntary", "Mixed"], y=[d["split"][k] for k in ("voluntary", "involuntary", "mixed")], name=d["label"], marker_color=col,
                    text=[d["split"][k] for k in ("voluntary", "involuntary", "mixed")], textposition="outside")
    fig.update_layout(barmode="group", yaxis_title="Items")
    st.plotly_chart(style(fig, 320), width="stretch")
    comp = pd.DataFrame({"Branch": [f"{b} {v['name']}" for b, v in tg["r2"]["branches"].items()],
                         tg["r1"]["label"]: [tg["r1"]["branches"][b]["posts"] for b in tg["r1"]["branches"]],
                         tg["r2"]["label"]: [tg["r2"]["branches"][b]["posts"] for b in tg["r2"]["branches"]]})
    text_table(comp)
    st.caption(f"Both rounds used Claude with different instructions, applied to the same {fmt(tg['n_common'])} Reddit items. "
               "The tagger here means the coding round, not a different model.")


# ------------------------------------------------------------------ 5. segments & sources
def seg_chart(rows, title_unit="% lapsed"):
    fig = go.Figure()
    fig.add_bar(x=[r["group"] for r in rows], y=[r["lapse_pct"] or 0 for r in rows], marker_color=[GREY if r["low_confidence"] else BLUE for r in rows],
                marker_pattern_shape=["/" if r["low_confidence"] else "" for r in rows],
                text=[f"{r['lapse_stories']} of {r['items']}" + (" ⚠" if r["low_confidence"] else "") for r in rows], textposition="outside")
    fig.update_layout(yaxis_title="% of relevant items that are lapse stories")
    return style(fig, 320, False)


def page_segments():
    sg = T["segments"]
    dims = sg["dimensions"]
    low = sum(r["low_confidence"] for rows in dims.values() for r in rows if r["group"] != "Not stated")
    total = sum(1 for rows in dims.values() for r in rows if r["group"] != "Not stated")
    st.title(f"{low} of {total} segment groups have fewer than {META['low_confidence_below']} lapse stories, so most comparisons are low confidence")
    banner()
    source_strip("Lapse stories, by source (Play Store is below the low-confidence line)", T["headline"]["p5"]["lapse"])
    s = sg["stated"]
    st.markdown(f"<div class='draft'><b>Read this first.</b> Age, income and money source are missing from many items. Across all relevant items "
                f"age is stated in {s['Age']['All']:.0f}%, income in {s['Income']['All']:.0f}% and money source in {s['Money source']['All']:.0f}%. "
                f"In Play Store reviews almost none state them ({s['Age']['Play Store']:.0f}%, {s['Income']['Play Store']:.0f}% and "
                f"{s['Money source']['Play Store']:.0f}%), and in YouTube comments only {s['Income']['YouTube']:.0f}% state income. Reddit states them most "
                f"({s['Income']['Reddit']:.0f}% income), but Reddit skews salaried. Treat every group below as a proxy, not a population.</div>", unsafe_allow_html=True)
    st.markdown(f"A **lapse story** is a relevant item whose author stopped, paused or reduced their SIP. Groups with fewer than "
                f"**{META['low_confidence_below']}** lapse stories are marked low confidence (grey, hatched bars and a ⚠).")
    st.subheader("How often each detail is stated")
    text_table((pd.DataFrame(s).T[["Reddit", "Play Store", "YouTube", "All"]].round(0).astype(int).astype(str) + "%").reset_index().rename(columns={"index": "Detail"}))
    st.subheader("Proxy comparisons")
    tabs = st.tabs(list(dims) + ["Source"])
    for tab, (name, rows) in zip(tabs, list(dims.items()) + [("Source", sg["by_source"])]):
        with tab:
            shown = [r for r in rows if r["group"] != "Not stated"]
            st.plotly_chart(seg_chart(shown), width="stretch", key=f"dash_seg{name}")
            df = pd.DataFrame(rows).rename(columns={"group": "Group", "items": "Relevant items", "lapse_stories": "Lapse stories", "lapse_pct": "% lapsed",
                                                    "top_reasons": "Most common stated reasons (lapse stories)"})
            df["Confidence"] = ["Low (under %d lapse stories)" % META["low_confidence_below"] if r["low_confidence"] else "Usable" for r in rows]
            text_table(df.drop(columns=["low_confidence"]))
    st.caption("Experience compares first-timers with people who already invest; the brief's target group is first-time investors. "
               "Groups are not mutually exclusive across tabs.")


# ------------------------------------------------------------------ 6. evidence explorer
def page_explorer():
    ev = EV[EV.is_relevant & (EV.quote.str.len() > 0)].copy()
    ev["Themes"] = ev.themes.map(lambda s: ", ".join(theme_label(t) for t in s.split(",") if t))
    top = st.container()
    banner_slot = top.empty()
    c1, c2, c3, c4 = st.columns(4)
    sources = c1.multiselect("Source", list(SOURCES), default=list(SOURCES), key="dash_src")
    strong = c2.selectbox("Relevance", ["Y or P (relevant)", "Y only (strong)"], key="dash_rel")
    yrs = c3.slider("Year", 2018, 2026, (2021, 2026), key="dash_year")
    outcomes = c4.multiselect("Outcome", sorted(ev.outcome.unique()), default=[], key="dash_outcome")
    c5, c6, c7, c8 = st.columns(4)
    qsel = c5.multiselect("Question", list(META["questions"]), default=[], format_func=lambda q: f"{q} {META['questions'][q][:34]}", key="dash_q")
    tsel = c6.multiselect("Theme", sorted({t for s in ev.themes for t in s.split(",") if t}), default=[], format_func=theme_label, key="dash_theme")
    conf = c7.multiselect("Confidence", ["H", "M", "L"], default=[], key="dash_conf")
    text = c8.text_input("Search the quote", key="dash_search")
    d = ev[ev.source_group.isin(sources) & ev.year.between(*yrs)]
    if strong.startswith("Y only"):
        d = d[d.relevant == "Y"]
    if outcomes:
        d = d[d.outcome.isin(outcomes)]
    if qsel:
        d = d[d.qs.map(lambda s: any(q in s.split(",") for q in qsel))]
    if tsel:
        d = d[d.themes.map(lambda s: any(t in s.split(",") for t in tsel))]
    if conf:
        d = d[d.confidence.isin(conf)]
    if text:
        d = d[d.quote.str.contains(text, case=False, regex=False)]
    d = d.sort_values(["severity", "date"], ascending=[False, False], kind="stable")   # most severe outcome first, newest first within each
    with banner_slot.container():
        st.title(f"{fmt(len(d))} of {fmt(META['relevant'])} relevant items match the filters; most severe outcomes first")
        banner()
        source_strip("Matching items, by source", {g: int((d.source_group == g).sum()) for g in SOURCES})
    st.caption("Default: relevant items from 2021 onward. Severity order: stopped, paused, reduced, considering stopping, then everything else. "
               "Every quote is copied word for word from the source and checked by script.")
    view = d[["outcome", "source_label", "date_label", "quote", "Themes", "qs", "stage", "confidence", "link"]].rename(columns={
        "outcome": "Outcome", "source_label": "Source", "date_label": "Date", "quote": "Verified quote", "qs": "Questions", "stage": "Stage", "confidence": "Confidence",
        "link": "Link"})
    view["Outcome"] = view["Outcome"].str.replace("_", " ").str.capitalize()
    st.dataframe(view, hide_index=True, width="stretch", height=620,
                 column_config={"Link": st.column_config.LinkColumn("Link", display_text="open"), "Verified quote": st.column_config.TextColumn(width="large"),
                                "Themes": st.column_config.TextColumn(width="medium")})
    st.download_button("Download these rows (CSV)", view.to_csv(index=False).encode("utf-8"), "evidence_filtered.csv", "text/csv", key="dash_download")


# ------------------------------------------------------------------ 7. ask the data
@st.cache_resource(show_spinner="Loading the search model (first time only)...")
def get_index(stamp):
    return askdata.Index()


def page_ask():
    st.title(f"Ask the data: answers come only from the {fmt(META['relevant'])} relevant items, with numbered citations")
    banner()
    source_strip("Items the answers can draw on, by source", T["headline"]["p7"]["relevant"])
    st.markdown("Ask what people say, for example *Why do people stop a SIP after losing a job?* or *SIP band karne ke kya reasons hain?* "
                "The answer is written only from the most similar items and cites them. If the data does not cover the question it says so. "
                "It does not give investment advice, predict markets or calculate returns.")
    used = st.session_state.setdefault("dash_asked", 0)
    left = askdata.SESSION_LIMIT - used
    daily_left = askdata.DAILY_CAP - askdata.daily_used()
    st.caption(f"{max(left, 0)} of {askdata.SESSION_LIMIT} questions left in this session · {max(daily_left, 0)} left today across all visitors")
    with st.form("dash_ask", clear_on_submit=False):
        question = st.text_input("Your question", max_chars=askdata.MAX_QUESTION_CHARS, placeholder="What do people say about failed SIP autopay?", key="dash_question_box")
        go_ = st.form_submit_button("Ask", type="primary")
    if go_:
        if left <= 0:
            st.session_state.dash_result = dict(status="limit", message=f"You have used all {askdata.SESSION_LIMIT} questions for this session. Reload the page to start again.", hits=[])
        elif daily_left <= 0:
            st.session_state.dash_result = dict(status="limit", message="The daily limit for this app has been reached. Please try again tomorrow.", hits=[])
        else:
            with st.spinner("Searching the evidence..."):
                res = askdata.ask(question, get_index(max(f.stat().st_mtime for f in EXPORT.glob("*"))))
            if res["status"] in ("answered", "not_covered", "unavailable"):
                st.session_state.dash_asked = used + 1
                askdata.count_daily()
            st.session_state.dash_result = res
            st.session_state.dash_question = question if res["status"] != "declined_pii" else ""
        st.rerun()
    res = st.session_state.get("dash_result")
    if not res:
        return
    st.divider()
    if st.session_state.get("dash_question"):
        st.markdown(f"**You asked:** {esc(st.session_state.dash_question)}")
    s = res["status"]
    if s == "answered":
        st.markdown(f"<div class='quote' style='border-left-color:{GREEN};font-size:1.02rem'>{esc(res['answer'])}</div>", unsafe_allow_html=True)
        st.caption(f"Written by {res['model']} from the numbered items below. Check the citations against the sources.")
    elif s in ("refused", "declined_pii", "invalid", "limit"):
        st.info(res["message"])
    else:
        st.warning(res["message"])
    if res["hits"]:
        st.markdown("**Items used** (most similar first)")
        for h in res["hits"]:
            cited = s == "answered" and h["rank"] in res.get("cited", [])
            link = f" · <a href='{esc(h['link'])}' target='_blank'>open</a>" if h.get("link") else ""
            st.markdown(f"<div class='quote' style='border-left-color:{GREEN if cited else BLUE}'><b>[{h['rank']}]</b> {'cited · ' if cited else ''}“{esc(h['quote'])}”"
                        f"<small>{esc(h['source_label'])}, {esc(h['date_label'])} · similarity {h['similarity']:.2f}{link}</small></div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ 8. validation
def page_validation():
    v = T["validation"]
    g1, g2 = v["golden"]["round1"], v["golden"]["round2_from_log"]
    st.title(f"The engine matched the hand labeller on relevance for {g2['relevance']} of {g2['n']} items, but tag agreement is the weak point "
             f"(precision {g2['precision']}%, recall {g2['recall']}%)")
    banner()
    gc = T["headline"]["p8"]["golden"]
    st.markdown(f"<div class='strip'><span class='lab'>Golden set mix: 20 items, plus 6 YouTube comments labelled separately</span><br>"
                f"<b style='color:{SRC_COL['Reddit']}'>■</b> Reddit posts <b>{gc.get('reddit_post', 0)}</b> &nbsp;·&nbsp; "
                f"<b style='color:{SRC_COL['Reddit']}'>■</b> Reddit comments <b>{gc.get('reddit_comment', 0)}</b> &nbsp;·&nbsp; "
                f"<b style='color:{SRC_COL['Play Store']}'>■</b> Play Store reviews <b>{gc.get('playstore_review', 0)}</b> &nbsp;·&nbsp; "
                f"<b style='color:{SRC_COL['YouTube']}'>■</b> YouTube comments <b>{gc.get('YouTube comment', 0)}</b></div>", unsafe_allow_html=True)
    st.subheader("Prompt versions")
    pv = pd.DataFrame(v["prompt_versions"]).rename(columns={"round": "Round", "codebook": "Codebook", "change": "What it asks for", "problem": "What went wrong"})
    text_table(pv)

    st.subheader("Golden set: 20 items labelled by hand before seeing any engine output")
    rows = [{"Measure": "Relevant vs not relevant", "Round 1": f"{g1['relevance']} of {g1['n']}", "Round 2 (from the Evidence Log)": f"{g2['relevance']} of {g2['n']}"},
            {"Measure": "Exact Y / P / N", "Round 1": f"{g1['exact']} of {g1['n']}", "Round 2 (from the Evidence Log)": f"{g2['exact']} of {g2['n']}"},
            {"Measure": "Question tags: precision", "Round 1": f"{g1['precision']}%", "Round 2 (from the Evidence Log)": f"{g2['precision']}%"},
            {"Measure": "Question tags: recall", "Round 1": f"{g1['recall']}%", "Round 2 (from the Evidence Log)": f"{g2['recall']}%"},
            {"Measure": "Items with an identical question set", "Round 1": f"{g1['identical']} of {g1['n']}", "Round 2 (from the Evidence Log)": f"{g2['identical']} of {g2['n']}"}]
    text_table(pd.DataFrame(rows))
    y = v["golden"]["youtube"]
    st.caption(f"Round 1 is recomputed from the golden-set file and matches the log. Round 2 figures are taken from the Evidence Log. Round 2 was tuned on "
               f"these same 20 items, so its scores are not an independent test, and one item moves a score by 5 points. YouTube: {y['n']} hand-labelled items, "
               f"relevance matched on {y['relevance']}, precision {y['precision']}%, recall {y['recall']}%.")

    st.subheader("Model agreement: round 1 versus round 2")
    ag = v["agreement"]
    fig = go.Figure(go.Bar(x=list(ag["per_question"]), y=list(ag["per_question"].values()), marker_color=BLUE,
                           text=[f"{x:.0f}%" for x in ag["per_question"].values()], textposition="outside"))
    fig.update_layout(yaxis_title="Items tagged by both ÷ tagged by either (%)", yaxis_range=[0, 100])
    st.plotly_chart(style(fig, 320, False), width="stretch")
    st.caption(f"Over {fmt(ag['items'])} Reddit items coded in both rounds; theme overlap {ag['theme_overlap']:.0f}%. Both rounds use Claude, so this measures how "
               "consistent the instructions are, not an independent second opinion. Relevance agreement is not reported: round 2 only re-coded items "
               "round 1 had kept, so it would look near perfect for the wrong reason.")

    st.subheader("AI corrections")
    st.caption("Output that the checking script or a rule changed.")
    text_table(pd.DataFrame(v["ai_corrections"]).rename(columns={"what": "What", "n": "Items", "fix": "What happened"}))

    st.subheader("Tag review: 20 posts read for each suspicious tag")
    st.caption("Tags were picked because their quotes least often mention the tag's own subject. For each, 20 items (16 for confusion, all it has) were read and judged "
               "right, partly right or wrong, then a rule was written and logged. The read was done by Claude, not by a human, and the rules were tuned on "
               "these same items, so the last two columns are optimistic. A human spot check of the removed items would confirm them. Log: data/manual/ai_tag_review.csv.")
    rl = pd.DataFrame(T["review_log"])
    text_table(rl.assign(Removed=lambda d: d.removed.astype(str) + " of " + d.items_with_tag.astype(str),
                         WrongRemoved=lambda d: d.wrong_removed.astype(str) + " of " + d.wrong.astype(str),
                         RightRemoved=lambda d: d.right_removed.astype(str) + " of " + d.right.astype(str))
               [["label", "checked", "right", "partial", "wrong", "Removed", "WrongRemoved", "RightRemoved"]]
               .rename(columns={"label": "Tag", "checked": "Read", "right": "Right", "partial": "Partly", "wrong": "Wrong", "Removed": "Removed by the rule",
                                "WrongRemoved": "Wrong ones removed", "RightRemoved": "Right ones removed"}))
    with st.expander("The rule for each tag", expanded=False):
        for r in T["review_log"]:
            st.markdown(f"**{r['label']}.** {r['rule']}")

    st.subheader("Human corrections")
    ct = T["corrections"]
    ef = ct["effect"]
    st.markdown(f"**{ct['n']} corrections to {ct['items']} items** are applied from `{ct['file']}` ({', '.join(f'{n} {k}' for k, n in ct['by_field'].items())}). "
                f"Effect: relevant {fmt(ef['relevant_before'])} → {fmt(ef['relevant_after'])}, strong {fmt(ef['strong_before'])} → {fmt(ef['strong_after'])}, "
                f"tagged unchanged at {fmt(ef['tagged'])}. These come from the golden-set labelling, where the analyst's label differed from the engine's. "
                "Add a row to the file to record another correction, then re-export.")
    with st.expander(f"All {ct['n']} corrections", expanded=False):
        text_table(pd.DataFrame(ct["rows"]).rename(columns={"item_id": "Item", "source": "Source", "field": "Field", "ai_value": "Engine said",
                                                            "human_value": "Analyst says", "reason": "Reason", "corrected_by": "Corrected by", "date_added": "Date"}))
    with st.expander("Codebook changes made after the golden set", expanded=False):
        text_table(pd.DataFrame(v["human_corrections"]).rename(columns={"what": "What", "fix": "What changed"}))

    st.subheader("Exclusions: platform staff replies")
    ex = T["exclusions"]
    st.markdown(f"{esc(ex['rule'])}")
    col = ex["collected"]
    st.markdown(f"- **Coded items:** {ex['coded']['excluded']} of {fmt(ex['coded']['checked'])} removed.\n"
                f"- **All collected text, scanned with the same rule:** Reddit posts {col['reddit_posts']['flagged']} of {fmt(col['reddit_posts']['checked'])}, "
                f"Reddit comments {col['reddit_comments']['flagged']} of {fmt(col['reddit_comments']['checked'])}, YouTube {col['youtube']['flagged']} of "
                f"{fmt(col['youtube']['checked'])}. None of the flagged text had been coded.\n"
                f"- **Play Store:** {fmt(ex['play_store']['raw_with_developer_reply'])} of {fmt(ex['play_store']['raw_reviews'])} reviews have a developer reply, stored in a "
                f"separate column. Of the {ex['play_store']['coded_checked']} coded reviews checked, {ex['play_store']['coded_text_containing_the_reply']} contain that reply text.")
    st.caption("Authors of Reddit and YouTube items were never stored, so staff replies can only be found by their wording.")

    with st.expander(f"Consistency checks: {sum(c['passed'] for c in T['consistency'])} of {len(T['consistency'])} passed", expanded=False):
        text_table(pd.DataFrame(T["consistency"]).assign(passed=lambda d: d.passed.map({True: "Passed", False: "FAILED"}))
                   .rename(columns={"check": "Check", "passed": "Result", "detail": "Detail"}))

    st.subheader("Biases and limits")
    for k, txt in v["biases"]:
        st.markdown(f"- **{k}.** {txt}")


# ------------------------------------------------------------------ navigation
PAGES = {"1 · Overview & how it works": page_overview, "2 · Opportunity ranking": page_opportunities, "3 · The nine questions": page_questions,
         "4 · Metric tree": page_tree, "5 · Segments & sources": page_segments, "6 · Evidence explorer": page_explorer, "7 · Ask the data": page_ask,
         "8 · Validation & limitations": page_validation}
names = list(PAGES)


def standalone():
    st.set_page_config(page_title="SIP discovery engine", page_icon="🔎", layout="wide")
    inject_css()
    qp = st.query_params.get("page", "1")
    start = int(qp) - 1 if str(qp).isdigit() and 1 <= int(qp) <= len(names) else 0
    with st.sidebar:
        st.markdown("### SIP discovery engine")
        choice = st.radio("Page", names, index=start, label_visibility="collapsed")
        st.caption("Why Indian first-time investors pause, reduce or stop SIPs. Public posts, reviews and comments, coded by AI and checked by script.")
    st.query_params["page"] = str(names.index(choice) + 1)
    PAGES[choice]()


if __name__ == "__main__":
    standalone()
