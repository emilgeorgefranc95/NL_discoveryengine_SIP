"""One-off: seed data/manual/corrections.csv with the places where the analyst's hand labels (golden set: 20 items, plus 6 YouTube items)
differ from the engine's CURRENT (round 2) output. One row per differing field. Add further human corrections to the CSV by hand: pipeline/export.py
applies them and the Validation page lists them.

Run from discovery_engine/:  .venv/bin/python pipeline/seed_corrections.py
"""
import csv
import glob
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

D = Path(__file__).resolve().parent.parent / "data"
norm = lambda s: re.sub(r"\s+", " ", str(s or "")).strip().lower()

src = {}
for f in glob.glob(str(D / "coding/batches/*.json")):
    for it in json.load(open(f, encoding="utf-8")):
        src[it["id"]] = it
by_text = {}
for i, it in src.items():
    by_text.setdefault(norm(it["text"])[:200], []).append(i)
v2 = {}
for f in ("rd", "ps", "yt"):
    for line in open(D / f"coding/merged_{f}.jsonl", encoding="utf-8"):
        r = json.loads(line)
        v2[r["id"]] = r

FIELDS = ["item_id", "source", "field", "ai_value", "human_value", "reason", "corrected_by", "date_added"]
out = []
for name, label in (("golden_set_LABELLED.csv", "golden set (20 items)"), ("yt_golden_LABELLED.csv", "YouTube golden set (6 items)")):
    path = D / "golden" / name
    when = date.fromtimestamp(path.stat().st_mtime).isoformat()
    for g in pd.read_csv(path).fillna("").to_dict("records"):
        ids = by_text.get(norm(g["text"])[:200]) or []
        if len(ids) != 1 or ids[0] not in v2:
            print("not mapped uniquely:", name, norm(g["text"])[:60])
            continue
        i, ai = ids[0], v2[ids[0]]
        h_rel = str(g["YOUR relevant? (Y/P/N)"]).strip().upper()[:1]
        h_qs = sorted({q.upper() for q in re.split(r"[,\s;]+", str(g["YOUR questions (e.g. Q3,Q5)"])) if re.fullmatch(r"[Qq]\d", q)})
        reason = (str(g["YOUR main theme (free text)"]) + ("; " + str(g["notes"])[:140] if str(g["notes"]).strip() else "")).strip("; ")
        by = "analyst, hand labelling of the " + label
        if h_rel and h_rel != ai["relevant"]:
            out.append(dict(item_id=i, source=src[i]["source"], field="relevant", ai_value=ai["relevant"], human_value=h_rel, reason=reason,
                            corrected_by=by, date_added=when))
        if h_rel in ("Y", "P") and sorted(ai["qs"]) != h_qs:
            out.append(dict(item_id=i, source=src[i]["source"], field="qs", ai_value=",".join(sorted(ai["qs"])), human_value=",".join(h_qs), reason=reason,
                            corrected_by=by, date_added=when))

dest = D / "manual" / "corrections.csv"
dest.parent.mkdir(exist_ok=True)
with open(dest, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(out)
print(f"wrote {dest} with {len(out)} corrections:", pd.DataFrame(out).groupby("field").size().to_dict())
