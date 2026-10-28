"""Evaluates the answer step (rules first, then one Gemini call that checks the intent and answers).

    python tests/run_answer_eval.py refusal     the three refusal sets (88 questions)
    python tests/run_answer_eval.py answers     the 80 relevance and Hinglish questions: does a legitimate question get answered?
Writes data/tests/results/answer_step_<name>.json.
"""
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import config as C  # noqa: E402
import generate as G  # noqa: E402
import retrieve as R  # noqa: E402

Q = C.TESTS_DATA_DIR / "questions"
RES = C.TESTS_DATA_DIR / "results"
REFUSED = "refused_advice"


def read(name):
    return list(csv.DictReader((Q / name).open(encoding="utf-8")))


def refusal():
    ret = R.Retriever()
    ret.search("warm up")
    out, summary = {}, {}
    for name in ("refusal", "refusal_round2", "refusal_round3"):
        rows = []
        for q in read(f"{name}.csv"):
            o = G.answer(q["question"], retriever=ret)
            rows.append({"qid": q["qid"], "question": q["question"], "expected": q["expected"], "language": q["language"],
                         "status": o["status"], "guard": o["guard"], "decision": o["llm"]["decision"], "calls": o["llm"]["calls"],
                         "note": o["llm"]["note"], "answer": o["answer"]})
            time.sleep(0.2)
        must = [r for r in rows if r["expected"] == "refused_advice"]
        ok = [r for r in rows if r["expected"] == "ok_allowed"]
        caught = [r for r in must if r["status"] == REFUSED]
        false = [r for r in ok if r["status"] == REFUSED]
        summary[name] = {
            "must_refuse_caught": f"{len(caught)}/{len(must)}", "caught_by_rules": sum(r["guard"] == "rules" for r in caught),
            "caught_by_gemini": sum(r["guard"] == "llm" for r in caught),
            "lookalikes_wrongly_refused": f"{len(false)}/{len(ok)}", "false_refusals": [r["question"] for r in false],
            "missed": [r["question"] for r in must if r["status"] != REFUSED],
            "missed_status": dict(Counter(r["status"] for r in must if r["status"] != REFUSED)),
            "lookalike_outcomes": dict(Counter(r["status"] for r in ok)),
            "gemini_unavailable_or_failed": [r["qid"] for r in rows if r["status"] == "answer_unavailable"],
            "gemini_calls": sum(r["calls"] for r in rows)}
        out[name] = rows
    (RES / "answer_step_refusal.json").write_text(json.dumps({"summary": summary, "rows": out}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=1, ensure_ascii=False))


def answers():
    ret = R.Retriever()
    ret.search("warm up")
    final = json.loads((RES / "run_final.json").read_text(encoding="utf-8"))["sets"]
    rewrites = {h["qid"]: h["question_english"] for h in final["hinglish"]}
    rows = []
    items = [(q["qid"], q["question"], q["split"]) for q in read("relevance_en.csv")] + [(q["qid"], q["question"], q["split"]) for q in read("hinglish.csv")]
    for qid, question, split in items:
        fn = (lambda _q, e=rewrites[qid]: (e, "reused")) if (qid in rewrites and "--live" not in sys.argv) else None
        t = time.perf_counter()
        o = G.answer(question, retriever=ret, rewrite_fn=fn)
        rows.append({"qid": qid, "split": split, "question": question, "status": o["status"], "guard": o["guard"],
                     "decision": o["llm"]["decision"], "calls": o["llm"]["calls"], "failed": o["llm"]["attempts_failed"],
                     "answer": o["answer"], "citation": o["citation"], "last_updated_line": o["last_updated_line"],
                     "sources": [s["id"] for s in o["sources"]], "secs": round(time.perf_counter() - t, 2)})
        time.sleep(0.2)
    (RES / "answer_step_answers.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    ans = [r for r in rows if r["status"] == "answered"]
    sent = [len(G.SENTENCE_END.split(r["answer"])) for r in ans]
    print("statuses:", dict(Counter(r["status"] for r in rows)), "| decided by:", dict(Counter(r["guard"] for r in rows)))
    print("answered:", len(ans), "of", len(rows), "| sentences per answer:", dict(Counter(sent)),
          "| with citation + date line:", sum(bool(r["citation"] and r["last_updated_line"]) for r in ans),
          "| needed a retry:", sum(bool(r["failed"]) for r in ans), "| median seconds:", sorted(r["secs"] for r in rows)[len(rows) // 2])
    print("refused by Gemini among legitimate questions:", [(r["qid"], r["question"][:60]) for r in rows if r["status"] == REFUSED])
    print("not enough evidence:", [(r["qid"], r["guard"], r["question"][:50]) for r in rows if r["status"] == "not_enough_evidence"])
    print("unavailable:", [(r["qid"], r["failed"]) for r in rows if r["status"] == "answer_unavailable"])


if __name__ == "__main__":
    {"refusal": refusal, "answers": answers}[sys.argv[1]]()
