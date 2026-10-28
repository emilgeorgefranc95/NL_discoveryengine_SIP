"""Phase 6: scores a retrieval run against the judgments and writes data/tests/results/metrics_<tag>.json.

    python tests/score_retrieval_eval.py --tag baseline
"""
import argparse
import csv
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import config as C  # noqa: E402

RES = C.TESTS_DATA_DIR / "results"
JUD = C.TESTS_DATA_DIR / "judgments"
Q = C.TESTS_DATA_DIR / "questions"


def load_judgments(pattern="judged_*.jsonl"):
    J = {}
    for f in sorted(glob.glob(str(JUD / pattern))):
        for line in open(f, encoding="utf-8"):
            if line.strip():
                j = json.loads(line)
                J[j["pid"]] = j["score"]
    return J


def mean(xs):
    xs = list(xs)
    return round(sum(xs) / len(xs), 3) if xs else None


def question_scores(q, J, k=5):
    """Judged scores of the top-k chunks of one question (missing judgments are reported, not hidden)."""
    s = []
    for c in q["chunks"][:k]:
        pid = f"{q['qid']}|{c['id']}"
        s.append(J.get(pid))
    return s


def prec(rows, J, k=5):
    strict, lenient, hit3, hit3s, missing = [], [], [], [], 0
    for q in rows:
        s = question_scores(q, J, k)
        missing += sum(x is None for x in s)
        s = [x if x is not None else 0 for x in s]
        strict.append(sum(x == 2 for x in s) / k)
        lenient.append(sum(x >= 1 for x in s) / k)
        hit3.append(float(any(x >= 1 for x in s[:3])))
        hit3s.append(float(any(x == 2 for x in s[:3])))
    return {"questions": len(rows), "p@5_strict": mean(strict), "p@5_lenient": mean(lenient),
            "hit@3_lenient": mean(hit3), "hit@3_strict": mean(hit3s), "unjudged_pairs": missing}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    run = json.loads((RES / f"run_{a.tag}.json").read_text(encoding="utf-8"))["sets"]
    J = load_judgments()
    rel_meta = {r["qid"]: r for r in csv.DictReader((Q / "relevance_en.csv").open(encoding="utf-8"))}
    en, hi = run["relevance"], run["hinglish"]
    out = {"tag": a.tag}

    # ---- precision by split, language, question type
    blocks = {}
    for name, rows in (("english", en), ("hinglish", hi)):
        blocks[name] = {"all": prec(rows, J), "dev": prec([r for r in rows if r["split"] == "dev"], J),
                        "hold": prec([r for r in rows if r["split"] == "hold"], J)}
    out["precision"] = blocks
    typ = lambda q: rel_meta[q.get("en_qid", q["qid"])]["type"]  # noqa: E731
    out["by_type"] = {name: {t: prec([r for r in rows if typ(r) == t], J) for t in ("behaviour", "platform")}
                      for name, rows in (("english", en), ("hinglish", hi))}
    out["by_type_holdout"] = {name: {t: prec([r for r in rows if typ(r) == t and r["split"] == "hold"], J) for t in ("behaviour", "platform")}
                              for name, rows in (("english", en), ("hinglish", hi))}

    # ---- Hinglish against English on the 20 paired topics
    paired_en = [r for r in en if r["qid"] <= "E20"]
    out["hinglish_vs_english_paired"] = {
        "english_20_topics": prec(paired_en, J), "hinglish_40_questions": prec(hi, J),
        "holdout": {"english": prec([r for r in paired_en if r["split"] == "hold"], J),
                    "hinglish": prec([r for r in hi if r["split"] == "hold"], J)}}

    # ---- by result source (precision of the chunks that came from each source)
    by_src = defaultdict(list)
    for q in en + hi:
        for c in q["chunks"][:5]:
            sc = J.get(f"{q['qid']}|{c['id']}")
            if sc is not None:
                by_src[c["source"].split()[0]].append(sc)
    out["by_source_of_chunk"] = {k: {"chunks": len(v), "share_of_results": round(len(v) / sum(len(x) for x in by_src.values()), 3),
                                     "strict": mean(x == 2 for x in v), "lenient": mean(x >= 1 for x in v)} for k, v in by_src.items()}

    # ---- evidence-gate calibration on the tuning half (dev), then reported on the holdout
    inscope = {"dev": [q["best_similarity"] for q in en + hi if q["split"] == "dev"],
               "hold": [q["best_similarity"] for q in en + hi if q["split"] == "hold"]}
    oos = run["out_of_scope"]
    oos_s = {sp: [q for q in oos if q["split"] == sp] for sp in ("dev", "hold")}
    grid = []
    for t in [round(0.20 + 0.01 * i, 2) for i in range(0, 56)]:
        row = {"threshold": t}
        for sp in ("dev", "hold"):
            row[f"in_scope_pass_{sp}"] = mean(x >= t for x in inscope[sp])
            row[f"oos_pass_{sp}"] = mean(q["best_similarity"] >= t for q in oos_s[sp])
            row[f"oos_general_pass_{sp}"] = mean(q["best_similarity"] >= t for q in oos_s[sp] if q["kind"] in ("general", "nonsense"))
            row[f"oos_finance_pass_{sp}"] = mean(q["best_similarity"] >= t for q in oos_s[sp] if q["kind"] == "finance")
        grid.append(row)
    out["gate_grid"] = grid
    # rule: the highest threshold at which at least 95 percent of tuning-half in-scope questions still pass
    ok = [g for g in grid if g["in_scope_pass_dev"] >= 0.95]
    out["gate_choice_rule"] = "highest threshold with at least 95% of dev in-scope questions passing"
    out["gate_choice"] = max(ok, key=lambda g: g["threshold"]) if ok else None
    out["sim_summary"] = {"in_scope_min": min(inscope["dev"] + inscope["hold"]), "oos_general_max":
                          max(q["best_similarity"] for q in oos if q["kind"] in ("general", "nonsense")),
                          "oos_finance_min": min(q["best_similarity"] for q in oos if q["kind"] == "finance"),
                          "oos_finance_max": max(q["best_similarity"] for q in oos if q["kind"] == "finance")}

    # ---- structure checks on every result
    bad = defaultdict(list)
    for q in en + hi:
        ch = q["chunks"]
        if not ch or not str(q["citation"] or "").startswith("http") or q["citation"] != ch[0]["source_link"]:
            bad["citation"].append(q["qid"])
        per = defaultdict(int)
        for c in ch:
            if c["thread_id"]:
                per[c["thread_id"]] += 1
        if any(v > C.MAX_PER_THREAD for v in per.values()):
            bad["thread_cap"].append(q["qid"])
        if not q.get("last_updated") and q in en:
            bad["last_updated"].append(q["qid"])
        sims = [c["similarity"] for c in ch]
        if sims != sorted(sims, reverse=True):
            bad["order"].append(q["qid"])
    out["structure"] = {"results_checked": len(en) + len(hi), "problems": {k: v for k, v in bad.items()}}

    # ---- speed (retrieval only; the Gemini rewrite is timed separately)
    secs = sorted(q["secs"] for q in en + hi)
    out["speed"] = {"retrieval_median_s": secs[len(secs) // 2], "retrieval_max_s": secs[-1],
                    "gemini_rewrite_median_s": sorted(q["rewrite_secs"] for q in hi)[len(hi) // 2],
                    "gemini_rewrite_max_s": max(q["rewrite_secs"] for q in hi)}
    out["rewrites_used"] = sum(q["rewrite_note"].startswith("used") for q in hi)

    # ---- agreement with the second-opinion judge on 60 pairs
    chk = load_judgments("check_judged_*.jsonl")
    if chk:
        same = sum(J[p] == s for p, s in chk.items())
        bin_same = sum((J[p] >= 1) == (s >= 1) for p, s in chk.items())
        strict_same = sum((J[p] == 2) == (s == 2) for p, s in chk.items())
        out["judge_agreement"] = {"pairs": len(chk), "exact": round(same / len(chk), 3),
                                  "relevant_or_not (1-2 vs 0)": round(bin_same / len(chk), 3),
                                  "directly_answers_or_not (2 vs 0-1)": round(strict_same / len(chk), 3)}
    out["score_distribution"] = {str(s): sum(1 for v in J.values() if v == s) for s in (0, 1, 2)}
    (RES / f"metrics_{a.tag}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    pr = out["precision"]
    print("PRECISION @5 (strict / lenient / hit@3 lenient)")
    for n in ("english", "hinglish"):
        for sp in ("all", "dev", "hold"):
            p = pr[n][sp]
            print(f"  {n:9s} {sp:4s} n={p['questions']:2d}  {p['p@5_strict']} / {p['p@5_lenient']} / {p['hit@3_lenient']}  (unjudged {p['unjudged_pairs']})")
    print("by type (all):", json.dumps(out["by_type"]))
    print("paired:", json.dumps(out["hinglish_vs_english_paired"]))
    print("by source:", json.dumps(out["by_source_of_chunk"]))
    print("gate choice:", out["gate_choice"]); print("sim summary:", out["sim_summary"])
    print("structure:", out["structure"]); print("speed:", out["speed"], "| rewrites used", out["rewrites_used"])
    print("judge agreement:", out.get("judge_agreement")); print("score dist:", out["score_distribution"])


if __name__ == "__main__":
    main()
