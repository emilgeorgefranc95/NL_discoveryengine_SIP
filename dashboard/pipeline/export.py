"""Build data/export/ for the dashboard. This is the only script that reads the pipeline folders; app/streamlitapp.py reads data/export/ only.

Run from discovery_engine/:  .venv/bin/python pipeline/export.py [--no-embed]

Writes:
  evidence.csv       one row per tagged item (2,110), with every label, the verified quote and a short masked excerpt
  tables.json        every number and chart the pages show (definitions come from pipeline/rules.py)
  embeddings.npy     one unit vector per relevant item, plus embed_ids.json (row order)
  meta.json          as-of date, definitions, counts, model names, build time
"""
import csv
import glob
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules as R  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
OUT = D / "export"
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
RELEVANT = ("Y", "P")


def jl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def mask(text):
    t = re.sub(r"\bu/[A-Za-z0-9_-]+", "u/[user]", text or "")
    t = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]", t)
    t = re.sub(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)", "[phone]", t)
    return re.sub(r"\s+", " ", t).strip()


def age_band(a):
    try:
        a = int(str(a).split("-")[0])
    except ValueError:
        return "Not stated"
    return "Under 22" if a < 22 else "22 to 25" if a <= 25 else "26 to 30" if a <= 30 else "31 and over"


def stated(v):
    return str(v or "").strip().lower() not in ("", "unknown", "none", "nan")


# ------------------------------------------------------------------ load
v2 = {}
for f in ("rd", "ps", "yt"):
    for r in jl(D / "coding" / f"merged_{f}.jsonl"):
        v2[r["id"]] = r
v1 = {}
for f in glob.glob(str(D / "coding/v1/merged_*.jsonl")):
    for r in jl(f):
        v1[r["id"]] = r
src = {}
for f in glob.glob(str(D / "coding/batches/*.json")):
    for it in json.load(open(f, encoding="utf-8")):
        src[it["id"]] = it
perma = {}
for f in glob.glob(str(D / "reddit/posts_*.jsonl")) + glob.glob(str(D / "reddit/comments_*.jsonl")):
    for r in jl(f):
        perma[r["id"]] = r.get("permalink")
ytvideo = {"yt_" + r["id"]: r["video_id"] for r in jl(D / "youtube/comments.jsonl")}

# ------------------------------------------------------------------ evidence table
rows = []
for i, r in v2.items():
    s = src[i]
    kind = s["source"]
    seg = r.get("segment") or {}
    th = list(r.get("themes") or [])
    qs = list(r.get("qs") or [])
    if kind != "playstore_review" and "NEED_HUMAN_HELP" in th:
        # analysis rule (also in the Evidence Log): on Reddit and YouTube the author is asking strangers by definition, so this tag is dropped
        th = [t for t in th if t != "NEED_HUMAN_HELP"]
        if "Q9" in qs and not [t for t in th if t.startswith("NEED_")]:
            qs.remove("Q9")
    inv, vol = any(t in R.INVOLUNTARY for t in th), any(t in R.VOLUNTARY for t in th)
    link = ""
    if kind in ("reddit_post", "reddit_comment") and perma.get(i):
        link = "https://www.reddit.com" + perma[i]
    elif kind == "youtube_comment" and i in ytvideo:
        link = f"https://www.youtube.com/watch?v={ytvideo[i]}&lc={i[3:]}"
    elif kind == "playstore_review":
        link = f"https://play.google.com/store/apps/details?id=com.nextbillion.groww&reviewId={i}"
    date = (s.get("date") or "")[:10]
    rows.append(dict(
        id=i, source=kind, source_label=R.SOURCE_LABEL[kind], source_group=R.SOURCE_GROUP[kind],
        subreddit=s.get("subreddit", "") if kind.startswith("reddit") else "", date=date, year=int(date[:4]) if date[:4].isdigit() else 0,
        relevant=r["relevant"], is_relevant=r["relevant"] in RELEVANT, qs=",".join(sorted(qs)), themes=",".join(th),
        stage=r.get("stage", "UNKNOWN"), outcome=r.get("outcome", "UNKNOWN"),
        lapse=r.get("outcome") in R.LAPSE_OUTCOMES and r["relevant"] in RELEVANT,
        severity=R.ITEM_SEVERITY.get(r.get("outcome"), 0),
        income=str(seg.get("income", "UNKNOWN")).upper(), age=str(seg.get("age", "unknown")), age_band=age_band(seg.get("age")),
        money_source=str(seg.get("money_source", "unknown")).lower(), influencer=str(seg.get("influencer", "unknown")).lower(),
        experience=str(seg.get("experience", "UNKNOWN")).upper(),
        reason_class="mixed" if inv and vol else "involuntary" if inv else "voluntary" if vol else "none",
        branches=",".join(sorted({R.THEME_BRANCH[t] for t in th if t in R.THEME_BRANCH})),
        quote=r.get("quote") or "", confidence=r.get("confidence", ""), note=r.get("note", ""), link=link,
        date_label=(("about " + date[:7]) if kind == "youtube_comment" and date else date),
        context=mask(s.get("title", ""))[:160] if kind.startswith("reddit") else "", excerpt=mask(s.get("text", ""))[:600],
    ))
ev = pd.DataFrame(rows)
rel = ev[ev.is_relevant]
N_TAGGED, N_REL = len(ev), len(rel)
assert N_TAGGED == len(v2) and N_REL == sum(r["relevant"] in RELEVANT for r in v2.values())

for _c in ("income", "money_source", "influencer", "experience"):
    ev[_c] = ev[_c].where(ev[_c].map(stated), "Not stated")
rel = ev[ev.is_relevant]
THEME_ALL = sorted({t for ts in rel.themes for t in ts.split(",") if t})


def label(t):
    if t.startswith("OTHER:"):
        return "Other: " + t[6:].strip()
    if t in R.LABEL_OVERRIDES:
        return R.LABEL_OVERRIDES[t]
    return t.replace("_", " ").capitalize() if not t.startswith(("STOP_", "PLAT_", "NEED_", "WORRY_", "CHECK_", "OUT_", "CONT_", "EXP_")) \
        else t.split("_", 1)[1].replace("_", " ").capitalize()


def has(df, theme):
    return df[df.themes.str.split(",").map(lambda x: theme in x)]


def pick_quotes(df, n=2, prefer_lapse=True, theme=None, fam=None, q=None):
    """Verbatim, verified quotes from this subset only. Quotes whose words match the subject (rules.THEME_LEX / QUESTION_LEX) come first,
    then items where the theme comes early in the coding, strong items, lapse stories, high confidence. The second quote comes from a
    different source when one exists."""
    d = df[df.quote.str.len() > 0].copy()

    def supports(r):
        if theme:
            return bool(R.THEME_LEX[theme].search(r.quote)) if theme in R.THEME_LEX else True
        lex = [R.THEME_LEX[t] for t in r.themes.split(",") if t in R.THEME_LEX and fam and t.startswith(fam)]
        return any(x.search(r.quote) for x in lex) or (q in R.QUESTION_LEX and bool(R.QUESTION_LEX[q].search(r.quote)))

    def central(ts):
        ts = [t for t in ts.split(",") if t]
        hits = [k for k, t in enumerate(ts) if (t == theme if theme else bool(fam) and t.startswith(fam))]
        return max(0, 3 - hits[0]) if hits else 0

    d["_ok"] = [supports(r) for r in d.itertuples()]
    if d["_ok"].sum() >= 2:
        d = d[d["_ok"]]
    d["_s"] = d.themes.map(central) * 2 + (d.relevant == "Y").astype(int) * 3 + (d.lapse.astype(int) * 2 if prefer_lapse else 0) + (d.confidence == "H").astype(int)
    d = d.sort_values(["_s", "id"], ascending=[False, True])
    out = []
    for _, r in d.iterrows():
        if len(out) == 1 and r.source_group == out[0]["group"] and (d.source_group != out[0]["group"]).any():
            continue
        out.append(dict(id=r.id, quote=r.quote, source=r.source_label, date=r.date_label, link=r.link, outcome=r.outcome, group=r.source_group, match=bool(r._ok)))
        if len(out) == n:
            break
    return out


# ------------------------------------------------------------------ page 1: overview
def count_lines(pattern):
    return sum(1 for f in glob.glob(str(D / pattern)) for _ in open(f, encoding="utf-8"))


scan_total = scan_match = 0
for f in glob.glob(str(D / "reddit/scan_stats_*.csv")):
    for row in csv.reader(open(f)):
        scan_total += int(row[2]); scan_match += int(row[3])
n_posts_sip = count_lines("reddit/posts_*.jsonl")
n_reddit_comments = count_lines("reddit/comments_*.jsonl")
n_yt_raw = count_lines("youtube/comments.jsonl")
n_ps_raw = len(pd.read_csv(D / "raw/groww_playstore_raw.csv"))
n_ps_kw = len(pd.read_csv(D / "raw/groww_sip_keyword_matches.csv"))
ps_rating = pd.read_csv(D / "coded/playstore_user_vs_ai.csv")["rating"].value_counts().to_dict()
v1_rel = sum(1 for r in v1.values() if r["relevant"] in RELEVANT)
reddit_v2 = ev[ev.source_group == "Reddit"]
grp = lambda g, df=ev: df[df.source_group == g]
funnel = {
    "Reddit": [("Posts scanned in 5 subreddits", scan_total), ("Posts that mention SIP", n_posts_sip),
               ("Coded in round 1 (first-hand filter)", len(v1)), ("Round 1 relevant (Y or P)", v1_rel),
               ("Tagged in round 2", len(reddit_v2)), ("Relevant after round 2", int(reddit_v2.is_relevant.sum()))],
    "Play Store": [("Reviews collected", n_ps_raw), ("Matched SIP or fund keywords", n_ps_kw),
                   ("Rated 4 or 5 by hand (kept for coding)", int(ps_rating.get(5, 0) + ps_rating.get(4, 0))),
                   ("Tagged in round 2", len(grp("Play Store"))), ("Relevant after round 2", int(grp("Play Store").is_relevant.sum()))],
    "YouTube": [("Comments collected", n_yt_raw), ("Passed the first-hand filter", len(grp("YouTube"))),
                ("Tagged in round 2", len(grp("YouTube"))), ("Relevant after round 2", int(grp("YouTube").is_relevant.sum()))],
}
combined = [("Collected", scan_total + n_ps_raw + n_yt_raw), ("Matched keywords or first-hand filter", n_posts_sip + n_ps_kw + len(grp("YouTube"))),
            ("Tagged (final round)", N_TAGGED), ("Relevant (Y or P)", N_REL), ("Strong (Y)", int((rel.relevant == "Y").sum()))]

dates = {}
for g in ("Reddit", "Play Store", "YouTube"):
    d = grp(g, rel)
    d = d[d.date != ""]
    dates[g] = dict(first=d.date.min(), last=d.date.max(), n=int(len(d)), by_year={int(k): int(v) for k, v in d.groupby("year").size().items()})
as_of = ev.date.max()

models = [
    dict(step="Reading and coding", model="Claude Sonnet (parallel agents, about 60 to 70 items each)",
         role="Rates relevance, tags questions and themes, picks one verbatim quote per item. Two rounds with different codebooks."),
    dict(step="Checking the coding", model="Python script (no model)", role="Checks every item: valid labels, one line per input, quote found word for word in the source."),
    dict(step="Finding similar posts (Ask the data)", model=EMBED_MODEL.split("/")[1] + " via fastembed",
         role="Turns the question and each item into a vector so Hinglish and English match by meaning."),
    dict(step="Writing the answer (Ask the data)", model="Google Gemini (gemini-3.5-flash-lite, fallback gemini-3.1-flash-lite)",
         role="Writes a short answer from the retrieved posts only, with numbered citations. Counts and tables never come from a model."),
]

# ------------------------------------------------------------------ page 2: opportunities
n_known_lapse_base = None


def theme_stats(theme):
    d = has(rel, theme)
    known = d[d.outcome != "UNKNOWN"]
    lapse = int(d.lapse.sum())
    return d, dict(theme=theme, label=label(theme), posts=int(len(d)), pct=round(100 * len(d) / N_REL, 1), lapse_stories=lapse,
                   known_outcome=int(len(known)), lapse_share=round(lapse / len(known), 3) if len(known) else None,
                   by_source={g: int((d.source_group == g).sum()) for g in ("Reddit", "Play Store", "YouTube")})


def severity_band(share, known):
    if share is None or known < 10:
        return "Unclear"
    for cut, name in R.SEVERITY_BANDS:
        if share >= cut:
            return name
    return "Low"


def opp_table(themes):
    out = []
    for t in themes:
        d, s = theme_stats(t)
        fix, why = R.FIXABLE[t]
        branch = R.THEME_BRANCH.get(t, "")
        s.update(severity=severity_band(s["lapse_share"], s["known_outcome"]), branch=branch, branch_name=R.METRIC_TREE.get(branch, ""),
                 fixable=fix, fixable_why=why, quotes=pick_quotes(d, 2, theme=t))
        out.append(s)
    base = sum(x["lapse_stories"] for x in out) / max(1, sum(x["known_outcome"] for x in out))
    for s in out:    # score = share of relevant items x how often the authors actually lapsed x fixability. Unclear severity uses the table's average rate.
        sev = s["lapse_share"] if s["severity"] != "Unclear" else base
        s["raw_score"] = s["pct"] * sev * R.FIX_WEIGHT[s["fixable"]]
    top = max((s["raw_score"] for s in out), default=1) or 1
    for s in out:
        s["score"] = round(100 * s["raw_score"] / top)
    return sorted(out, key=lambda s: -s["score"])


opps = dict(causes=opp_table(R.CAUSE_THEMES), after_stop=opp_table(R.AFTER_STOP_THEMES))

# ------------------------------------------------------------------ page 3: the nine questions
QTABLE = {}
for q, text in R.QUESTIONS.items():
    d = rel[rel.qs.str.split(",").map(lambda x: q in x)]
    fam = R.QUESTION_FAMILIES[q]
    cnt = defaultdict(Counter)
    for r in d.itertuples():
        for t in r.themes.split(","):
            if t and (not fam or t.startswith(fam)):
                cnt[t][r.source_group] += 1
    top = sorted(cnt, key=lambda t: -sum(cnt[t].values()))[:8]
    entry = dict(question=text, items=int(len(d)), strong=int((d.relevant == "Y").sum()), pct_of_relevant=round(100 * len(d) / N_REL, 1),
                 by_source={g: int((d.source_group == g).sum()) for g in ("Reddit", "Play Store", "YouTube")},
                 by_source_pct={g: round(100 * (d.source_group == g).sum() / max(1, (rel.source_group == g).sum()), 1)
                                for g in ("Reddit", "Play Store", "YouTube")})
    if q == "Q7":
        oc = d.outcome.value_counts()
        entry["chart"] = dict(kind="bar", x=[o.replace("_", " ").capitalize() for o in oc.index], series={"Items": [int(v) for v in oc.values]})
        entry["finding"] = f"Only {len(d)} items speak to why people continue or drop off, so this question is thin."
        entry["numbers"] = [("Items tagged Q7", len(d)), ("Share of relevant", f"{entry['pct_of_relevant']}%"),
                            ("Still continuing", int((d.outcome == "CONTINUING").sum()))]
    elif q == "Q8":
        fields = [("Income", "income"), ("Age", "age_band"), ("Money source", "money_source"), ("Influencer", "influencer"), ("Experience", "experience")]
        pct = [round(100 * (d[f] != "Not stated").mean(), 1) for _, f in fields]
        entry["chart"] = dict(kind="bar", x=[n for n, _ in fields], series={"Stated (% of Q8 items)": pct})
        entry["finding"] = f"Among the {len(d)} items tagged for segments, age is stated in {pct[1]:.0f}% and income in {pct[0]:.0f}%."
        entry["numbers"] = [("Items tagged Q8", len(d)), ("Age stated", f"{pct[1]:.0f}%"), ("Income stated", f"{pct[0]:.0f}%")]
    else:
        entry["chart"] = dict(kind="stack", x=[label(t) for t in top][::-1],
                              series={g: [cnt[t][g] for t in top][::-1] for g in ("Reddit", "Play Store", "YouTube")})
        lead = top[0] if top else None
        if lead:
            entry["finding"] = f"{label(lead)} is the most common theme for this question: {sum(cnt[lead].values())} of {len(d)} items."
            entry["numbers"] = [("Items tagged", len(d)), ("Share of relevant", f"{entry['pct_of_relevant']}%"),
                                (f"{label(lead)} items", sum(cnt[lead].values()))]
    # quotes only from items tagged for this question, preferring the question's own theme families
    fam_d = d[d.themes.map(lambda s: any(t.startswith(fam) for t in s.split(",") if t))] if fam else d
    entry["quotes"] = pick_quotes(fam_d if len(fam_d) >= 3 else d, 3, prefer_lapse=(q == "Q3"), fam=fam[0] if len(fam) == 1 else None, q=q)
    QTABLE[q] = entry

# ------------------------------------------------------------------ page 4: metric tree
def tree_counts(df):
    out = {}
    for b, name in R.METRIC_TREE.items():
        d = df[df.branches.str.split(",").map(lambda x: b in x)]
        out[b] = dict(name=name, posts=int(len(d)), pct=round(100 * len(d) / max(1, len(df)), 1))
    return out


def class_split(df):
    c = df.reason_class.value_counts()
    return {k: int(c.get(k, 0)) for k in ("voluntary", "involuntary", "mixed")}


def split_by_source(df):
    return {g: class_split(df[df.source_group == g]) for g in ("Reddit", "Play Store", "YouTube")}


# tagger comparison: both rounds' themes on the same Reddit items (those coded in both rounds)
def tagger_df(rec, ids):
    out = []
    for i in ids:
        r = rec[i]
        th = [t for t in r["themes"] if t != "NEED_HUMAN_HELP"]
        inv, vol = any(t in R.INVOLUNTARY for t in th), any(t in R.VOLUNTARY for t in th)
        out.append(dict(id=i, relevant=r["relevant"], reason_class="mixed" if inv and vol else "involuntary" if inv else "voluntary" if vol else "none",
                        branches=",".join(sorted({R.THEME_BRANCH[t] for t in th if t in R.THEME_BRANCH}))))
    df = pd.DataFrame(out)
    return df[df.relevant.isin(RELEVANT)]


common = [i for i in v2 if i in v1 and src[i]["source"].startswith("reddit")]
t1, t2 = tagger_df(v1, common), tagger_df(v2, common)
tree = dict(
    goal="First-time investors who still have an active SIP 12 months after starting",
    branches=tree_counts(rel), by_source={g: tree_counts(rel[rel.source_group == g]) for g in ("Reddit", "Play Store", "YouTube")},
    reason_split=dict(all=class_split(rel), by_source=split_by_source(rel)),
    taggers=dict(n_common=len(common),
                 r1=dict(label=R.TAGGERS["r1"], relevant=int(len(t1)), split=class_split(t1), branches=tree_counts(t1)),
                 r2=dict(label=R.TAGGERS["r2"], relevant=int(len(t2)), split=class_split(t2), branches=tree_counts(t2))),
    branch_themes={b: [label(t) for t, bb in R.THEME_BRANCH.items() if bb == b] for b in R.METRIC_TREE},
)

# ------------------------------------------------------------------ page 5: segments
def seg_rows(field, order=None):
    out = []
    for val, d in rel.groupby(field):
        lap = d[d.lapse]
        top_reasons = Counter(t for ts in lap.themes for t in ts.split(",") if t.startswith("STOP_")).most_common(2)
        out.append(dict(group=val, items=int(len(d)), lapse_stories=int(len(lap)),
                        lapse_pct=round(100 * len(lap) / len(d), 1) if len(d) else None, low_confidence=len(lap) < R.LOW_CONFIDENCE_BELOW,
                        top_reasons=", ".join(f"{label(t)} ({n})" for t, n in top_reasons) or "none stated"))
    return sorted(out, key=lambda r: (r["group"] == "Not stated", -r["items"]))


segments = dict(
    dimensions={name: seg_rows(f) for name, f in [("Income", "income"), ("Age band", "age_band"), ("Money source", "money_source"),
                                                   ("Who influenced them", "influencer"), ("Experience", "experience")]},
    by_source=seg_rows("source_group"),
    stated={name: {g: round(100 * (rel[rel.source_group == g][f] != "Not stated").mean(), 1) for g in ("Reddit", "Play Store", "YouTube")}
            | {"All": round(100 * (rel[f] != "Not stated").mean(), 1)}
            for name, f in [("Income", "income"), ("Age", "age_band"), ("Money source", "money_source"), ("Influencer", "influencer"),
                            ("Experience", "experience")]},
    lapse_by_source={g: int(rel[rel.source_group == g].lapse.sum()) for g in ("Reddit", "Play Store", "YouTube")},
)

# ------------------------------------------------------------------ page 8: validation
def jacc(a, b):
    a, b = set(a), set(b)
    return 1.0 if not a and not b else len(a & b) / len(a | b)


both = [i for i in common]
# Round 2 only re-coded items that round 1 had kept, so agreement on RELEVANCE cannot be measured fairly and is not reported.
agree = dict(
    items=len(both),
    per_question={q: round(100 * sum(q in v1[i]["qs"] and q in v2[i]["qs"] for i in both)
                           / max(1, sum(q in v1[i]["qs"] or q in v2[i]["qs"] for i in both)), 1) for q in R.QUESTIONS},
    theme_overlap=round(100 * np.mean([jacc(v1[i]["themes"], v2[i]["themes"]) for i in both]), 1),
)


def golden_stats(path):
    g = json.load(open(path, encoding="utf-8"))
    ok = lambda x: x in RELEVANT
    tp = sum(len(set(x["me_q"]) & set(x["ai_q"])) for x in g)
    ai = sum(len(x["ai_q"]) for x in g)
    me = sum(len(x["me_q"]) for x in g)
    return dict(n=len(g), relevance=sum(ok(x["me_rel"]) == ok(x["ai_rel"]) for x in g), exact=sum(x["me_rel"] == x["ai_rel"] for x in g),
                precision=round(100 * tp / max(1, ai)), recall=round(100 * tp / max(1, me)),
                identical=sum(set(x["me_q"]) == set(x["ai_q"]) for x in g))


golden = dict(round1=golden_stats(D / "golden/golden_comparison.json"), youtube=golden_stats(D / "golden/yt_golden_comparison.json"),
              # the comparison file holds the round 1 engine labels (it reproduces the log's round 1 column); round 2 figures are from the Evidence Log
              round2_from_log=dict(n=20, relevance=19, exact=15, precision=68, recall=68, identical=7),
              ps_hand_rating=dict(strong=int(ps_rating.get(5, 0)), weaker=int(ps_rating.get(4, 0)), not_relevant=int(ps_rating.get(0, 0))))

flags_r1 = Counter(f for r in v1.values() for f in r.get("flags", []))
flags_r2 = Counter(f for r in v2.values() for f in r.get("flags", []))
human_help_dropped = sum(1 for r in v2.values() if "NEED_HUMAN_HELP" in r.get("themes", []) and True)
validation = dict(
    prompt_versions=[dict(round=a, codebook=b, change=c, problem=d) for a, b, c, d in R.PROMPT_VERSIONS],
    agreement=agree,
    golden=golden,
    ai_corrections=[
        dict(what="Quotes that were not word for word in the source", n=int(flags_r1.get("quote_not_verbatim", 0) + flags_r2.get("quote_not_verbatim", 0)),
             fix="The quote was blanked and flagged by the checking script."),
        dict(what="Themes outside the controlled list", n=int(flags_r1.get("bad_theme", 0) + flags_r2.get("bad_theme", 0)), fix="Removed by the checking script."),
        dict(what='"Needs human help" tags removed from Reddit items', n=int(sum("NEED_HUMAN_HELP" in v2[i].get("themes", [])
                                                                                  for i in v2 if src[i]["source"].startswith("reddit"))),
             fix="Dropped: on Reddit every author is asking strangers, so the tag measured how the data was gathered, not a need."),
        dict(what='"Needs human help" tags removed from YouTube items', n=int(sum("NEED_HUMAN_HELP" in v2[i].get("themes", [])
                                                                                  for i in v2 if src[i]["source"] == "youtube_comment")),
             fix="Dropped for the same reason: commenters are asking the video's creator."),
    ],
    human_corrections=[
        dict(what="Stock-SIP feature requests called off-topic", fix="The codebook now treats any SIP request as in scope (round 2)."),
        dict(what="Themes the quote did not support (income loss, confusion)", fix="Round 2 allows those themes only when the text says so."),
        dict(what="Rich personal posts rated only partly relevant", fix="Round 2 relaxed the relevance rule for posts with personal context."),
        dict(what="Play Store reviews judged by hand for relevance", fix=f"{golden['ps_hand_rating']['strong']} strong, {golden['ps_hand_rating']['weaker']} weaker, "
                                                                       f"{golden['ps_hand_rating']['not_relevant']} not relevant; only 4 and 5 rated reviews were coded in round 2."),
    ],
    biases=[
        ("Selection", "Public posts are not a sample of all investors. People who quietly stop rarely write about it, so continue versus drop off (Q7) is thin."),
        ("Who writes", "Reddit skews salaried, urban and market-aware. Irregular-income investors and students are a small share of items that state income."),
        ("What was coded", "Posts and comments were chosen for first-hand signals, so counts describe experience-type discussion, not all SIP chat."),
        ("Decisions, not outcomes", "Many posts are people deciding whether to stop, and most stage labels are unknown, so change over months (Q2) is thin."),
        ("Small test", "Accuracy is measured on 20 items and round 2 was tuned on them; a fresh holdout of 10 to 12 items would give an independent figure."),
        ("One model family", "Both rounds use Claude, so agreement between rounds measures consistency of instructions, not an independent second opinion."),
        ("Judgement columns", "Severity bands, fixable ratings, metric-tree branches and the voluntary or involuntary split are the analyst's first read (draft)."),
        ("Play Store", f"Only {int(ev[ev.source_group == 'Play Store'].is_relevant.sum())} relevant reviews and {segments['lapse_by_source']['Play Store']} lapse stories, so any Play Store comparison is low confidence."),
        ("YouTube", "Top comments only, short and reactive; only 6 items are hand-labelled. YouTube shows only relative ages (for example \"2 years ago\"), so comment dates are estimates, good to about a month for recent ones and a year for older ones."),
    ],
)

# ------------------------------------------------------------------ write
OUT.mkdir(parents=True, exist_ok=True)
ev.to_csv(OUT / "evidence.csv", index=False, encoding="utf-8")
meta = dict(as_of=as_of, built_at=datetime.now().isoformat(timespec="seconds"), tagged=N_TAGGED, relevant=N_REL, strong=int((rel.relevant == "Y").sum()),
            lapse_stories=int(rel.lapse.sum()), definitions=dict(tagged=R.TAGGED_DEF, relevant=R.RELEVANT_DEF, lapse_story=R.LAPSE_DEF),
            low_confidence_below=R.LOW_CONFIDENCE_BELOW, embed_model=EMBED_MODEL, questions=R.QUESTIONS, metric_tree=R.METRIC_TREE,
            by_source={g: dict(tagged=int((ev.source_group == g).sum()), relevant=int((rel.source_group == g).sum())) for g in ("Reddit", "Play Store", "YouTube")})
tables = dict(funnel=funnel, combined_funnel=combined, dates=dates, models=models, opportunities=opps, questions=QTABLE, tree=tree,
              segments=segments, validation=validation, themes={t: label(t) for t in THEME_ALL})
json.dump(tables, open(OUT / "tables.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
json.dump(meta, open(OUT / "meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"evidence.csv {N_TAGGED} tagged / {N_REL} relevant; as of {as_of}")

if "--no-embed" not in sys.argv:
    from fastembed import TextEmbedding
    model = TextEmbedding(model_name=EMBED_MODEL)
    docs = [f"{r.excerpt[:350]} | {r.quote} | {r.note} | " + ", ".join(label(t) for t in r.themes.split(",") if t) for r in rel.itertuples()]
    vecs = np.array(list(model.embed(docs)), dtype="float32")
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    np.save(OUT / "embeddings.npy", vecs)
    json.dump(list(rel.id), open(OUT / "embed_ids.json", "w"))
    print("embeddings", vecs.shape)
