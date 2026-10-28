"""Phase 6: runs the test sets against the retrieval backend and builds judging pools.

    python tests/run_retrieval_eval.py run  --tag baseline [--min-chars N]
    python tests/run_retrieval_eval.py pool --tag baseline [--splits dev,hold] [--per-batch 60]

'run' writes data/tests/results/run_<tag>.json. For relevance, Hinglish and out-of-scope questions the evidence gate is switched
off, so the best chunks and their similarity are always recorded (the gate is judged afterwards from the similarities).
Refusal and PII questions run with the normal settings. For Hinglish questions the Gemini rewrite is done first and timed
separately, so the retrieval time excludes it.
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import config as C  # noqa: E402
import retrieve as R  # noqa: E402

Q = C.TESTS_DATA_DIR / "questions"
RES = C.TESTS_DATA_DIR / "results"
JUD = C.TESTS_DATA_DIR / "judgments"


def read(name):
    return list(csv.DictReader((Q / name).open(encoding="utf-8")))


def chunk_row(c):
    return {"id": c["id"], "similarity": c["similarity"], "source": c["source"], "thread_id": c.get("thread_id", ""),
            "date": c.get("date", ""), "source_link": c.get("source_link", ""), "text": c["text"]}


def run_one(ret, question, rewrite_fn=None):
    t = time.perf_counter()
    r = R.retrieve(question, retriever=ret, rewrite_fn=rewrite_fn)
    return r, round(time.perf_counter() - t, 3)


def cmd_run(a):
    RES.mkdir(parents=True, exist_ok=True)
    C.MIN_RESULT_CHARS = a.min_chars
    ret = R.Retriever()
    ret.search("warm up")                                    # load the model once before timing
    out = {"tag": a.tag, "min_result_chars": a.min_chars, "provisional_gate": C.MIN_SIMILARITY, "sets": {}}
    gate = C.MIN_SIMILARITY

    C.MIN_SIMILARITY = -1.0                                  # gate off: record the best chunks whatever their score
    rel = []
    for q in read("relevance_en.csv"):
        r, secs = run_one(ret, q["question"])
        rel.append({"qid": q["qid"], "split": q["split"], "question": q["question"], "status": r["status"], "secs": secs,
                    "best_similarity": r["best_similarity"], "chunks": [chunk_row(c) for c in r["chunks"]],
                    "citation": r["citation"], "last_updated": r["last_updated"], "themes": len(r["theme_context"])})
    out["sets"]["relevance"] = rel

    hi = []
    reuse = {}
    if a.reuse_rewrites:                                     # keep the Gemini rewrites of an earlier run, so only the ranking differs
        reuse = {h["qid"]: h for h in json.loads((RES / f"run_{a.reuse_rewrites}.json").read_text(encoding="utf-8"))["sets"]["hinglish"]}
    for q in read("hinglish.csv"):
        t = time.perf_counter()
        if q["qid"] in reuse:
            english, note = reuse[q["qid"]]["question_english"], reuse[q["qid"]]["rewrite_note"]
            rw_secs = reuse[q["qid"]]["rewrite_secs"]
        else:
            english, note = R.rewrite_to_english(q["question"])
            rw_secs = round(time.perf_counter() - t, 3)
        r, secs = run_one(ret, q["question"], rewrite_fn=lambda _q, e=english, n=note: (e, n))
        hi.append({"qid": q["qid"], "en_qid": q["en_qid"], "split": q["split"], "question": q["question"],
                   "question_english": r["question_english"], "rewrite_note": note, "rewrite_secs": rw_secs,
                   "status": r["status"], "secs": secs, "best_similarity": r["best_similarity"],
                   "chunks": [chunk_row(c) for c in r["chunks"]], "citation": r["citation"]})
    out["sets"]["hinglish"] = hi

    oos = []
    for q in read("out_of_scope.csv"):
        r, secs = run_one(ret, q["question"])
        oos.append({"qid": q["qid"], "split": q["split"], "kind": q["kind"], "question": q["question"], "status": r["status"],
                    "secs": secs, "best_similarity": r["best_similarity"], "refusal_type": r.get("refusal_type"),
                    "top": [chunk_row(c) for c in r["chunks"][:2]]})
    out["sets"]["out_of_scope"] = oos

    C.MIN_SIMILARITY = gate                                  # normal settings for the screens
    ref = []
    for q in read("refusal.csv"):
        r, secs = run_one(ret, q["question"])
        ref.append({"qid": q["qid"], "question": q["question"], "expected": q["expected"], "kind": q["kind"], "language": q["language"],
                    "status": r["status"], "refusal_type": r.get("refusal_type"), "secs": secs, "rewrite_note": r["rewrite_note"],
                    "question_english": r["question_english"]})
    out["sets"]["refusal"] = ref
    ref2 = []
    for q in read("refusal_round2.csv"):                      # written after the first screen fix: an unseen check
        r, secs = run_one(ret, q["question"])
        ref2.append({"qid": q["qid"], "question": q["question"], "expected": q["expected"], "kind": q["kind"], "language": q["language"],
                     "status": r["status"], "refusal_type": r.get("refusal_type"), "secs": secs, "rewrite_note": r["rewrite_note"],
                     "question_english": r["question_english"]})
    out["sets"]["refusal_round2"] = ref2
    pii = []
    for q in read("pii.csv"):
        r, secs = run_one(ret, q["question"])
        blob = json.dumps(r, ensure_ascii=False)
        pii.append({"qid": q["qid"], "question": q["question"], "expected": q["expected"], "status": r["status"], "secs": secs,
                    "echoed_question": q["question"] in blob})
    out["sets"]["pii"] = pii
    path = RES / f"run_{a.tag}.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    first = RES / "first_run_screens.json"                   # kept untouched: the screens' score before any fix
    if not first.exists():
        first.write_text(json.dumps({"refusal": ref, "pii": pii}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def cmd_screens(a):
    """Re-run only the screen sets (refusal rounds 1-3, personal details) with the current rules; writes screens_<tag>.json."""
    C.MIN_RESULT_CHARS = 0
    ret = R.Retriever()
    ret.search("warm up")
    out = {"tag": a.tag, "sets": {}}
    for name in ("refusal", "refusal_round2", "refusal_round3"):
        rows = []
        for q in read(f"{name}.csv"):
            r, secs = run_one(ret, q["question"])
            rows.append({"qid": q["qid"], "question": q["question"], "expected": q["expected"], "kind": q["kind"],
                         "language": q["language"], "status": r["status"], "refusal_type": r.get("refusal_type"),
                         "rewrite_note": r["rewrite_note"], "question_english": r["question_english"]})
        out["sets"][name] = rows
    pii = []
    for q in read("pii.csv"):
        r, secs = run_one(ret, q["question"])
        pii.append({"qid": q["qid"], "question": q["question"], "expected": q["expected"], "status": r["status"],
                    "echoed_question": q["question"] in json.dumps(r, ensure_ascii=False)})
    out["sets"]["pii"] = pii
    oos = []
    for q in read("out_of_scope.csv"):
        r, secs = run_one(ret, q["question"])
        oos.append({"qid": q["qid"], "split": q["split"], "kind": q["kind"], "question": q["question"], "status": r["status"],
                    "best_similarity": r["best_similarity"]})
    out["sets"]["out_of_scope"] = oos
    (RES / f"screens_{a.tag}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote data/tests/results/screens_{a.tag}.json")


def judged_pids():
    done = {}
    for f in JUD.glob("judged_*.jsonl"):
        for line in f.open(encoding="utf-8"):
            if line.strip():
                j = json.loads(line)
                done[j["pid"]] = j["score"]
    return done


def cmd_pool(a):
    run = json.loads((RES / f"run_{a.tag}.json").read_text(encoding="utf-8"))
    splits = set(a.splits.split(","))
    meta = {q["qid"]: q for q in read("relevance_en.csv")}
    meta.update({q["qid"]: q for q in read("hinglish.csv")})
    done = judged_pids()
    todo, seen = [], set()
    for setname in ("relevance", "hinglish"):
        for q in run["sets"][setname]:
            if q["split"] not in splits:
                continue
            for c in q["chunks"][:5]:                         # precision is measured on the top 5
                pid = f"{q['qid']}|{c['id']}"
                if pid in done or pid in seen:
                    continue
                seen.add(pid)
                todo.append({"pid": pid, "question": q["question"], "intent": meta[q["qid"]]["intent"], "source": c["source"],
                             "chunk": c["text"][:900]})
    JUD.mkdir(parents=True, exist_ok=True)
    n = 0
    for i in range(0, len(todo), a.per_batch):
        n += 1
        with (JUD / f"pool_{a.tag}_{n:02d}.jsonl").open("w", encoding="utf-8") as f:
            for row in todo[i:i + a.per_batch]:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{len(todo)} pairs to judge in {n} batches (already judged: {len(done)})")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--tag", required=True); r.add_argument("--min-chars", type=int, default=0)
    r.add_argument("--reuse-rewrites", default=None, help="tag of an earlier run whose Hinglish rewrites are reused")
    p = sub.add_parser("pool"); p.add_argument("--tag", required=True); p.add_argument("--splits", default="dev,hold")
    p.add_argument("--per-batch", type=int, default=60)
    sc = sub.add_parser("screens"); sc.add_argument("--tag", required=True)
    a = ap.parse_args()
    {"run": cmd_run, "pool": cmd_pool, "screens": cmd_screens}[a.cmd](a)


if __name__ == "__main__":
    main()
