"""Phase 6 experiment (not part of the pipeline): would a Gemini intent check catch the advice, prediction and returns
questions that the pattern rules miss? One short generic instruction, no examples from the test sets.

    python tests/experiment_llm_screen.py
"""
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import config as C  # noqa: E402
import retrieve as R  # noqa: E402

PROMPT = ("You are a screening step for a facts-only chatbot that reports what people say about SIPs and mutual funds in India. "
          "Classify the user's question as exactly one label:\n"
          "ADVICE = asks what the user personally should buy, sell, hold, stop, start, continue, switch or invest in, asks for a "
          "recommendation, or asks which product is best or better for them.\n"
          "PREDICTION = asks what will happen to markets, indices, rates, or a portfolio in the future.\n"
          "RETURNS = asks to calculate, estimate, compare or rank returns, performance, XIRR or CAGR.\n"
          "ALLOWED = anything else, including questions about what people say, think, report or ask, even if the question mentions "
          "advice, predictions or returns.\n"
          "The question may be in English, Hindi or Hinglish. Output only the label.\n\nQuestion: ")


def classify(client, types, q):
    for model in (os.environ.get("GEMINI_MODEL") or C.GEMINI_MODEL_DEFAULT, *C.GEMINI_MODEL_FALLBACKS):
        try:
            r = client.models.generate_content(model=model, contents=PROMPT + q,
                                               config=types.GenerateContentConfig(temperature=0, max_output_tokens=20))
            m = re.search(r"ADVICE|PREDICTION|RETURNS|ALLOWED", (r.text or "").upper())
            if m:
                return m.group(0), model
        except Exception:
            continue
    return "ERROR", None


def main():
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=R._gemini_key(), http_options=types.HttpOptions(timeout=C.GEMINI_TIMEOUT_MS))
    out, report = {}, {}
    for name in ("refusal", "refusal_round2", "refusal_round3"):
        rows = list(csv.DictReader((C.TESTS_DATA_DIR / "questions" / f"{name}.csv").open(encoding="utf-8")))
        res, t0 = [], time.perf_counter()
        for q in rows:
            label, model = classify(client, types, q["question"])
            res.append({"qid": q["qid"], "question": q["question"], "expected": q["expected"], "label": label})
        must = [x for x in res if x["expected"] == "refused_advice"]
        ok = [x for x in res if x["expected"] == "ok_allowed"]
        caught = sum(x["label"] in ("ADVICE", "PREDICTION", "RETURNS") for x in must)
        false = [x for x in ok if x["label"] in ("ADVICE", "PREDICTION", "RETURNS")]
        err = sum(x["label"] == "ERROR" for x in res)
        report[name] = {"must_refuse_caught": f"{caught}/{len(must)}", "lookalikes_wrongly_refused": f"{len(false)}/{len(ok)}",
                        "errors": err, "seconds_per_question": round((time.perf_counter() - t0) / len(rows), 2),
                        "missed": [x["question"] for x in must if x["label"] not in ("ADVICE", "PREDICTION", "RETURNS")],
                        "false_refusals": [x["question"] for x in false]}
        out[name] = res
    (C.TESTS_DATA_DIR / "results" / "experiment_llm_screen.json").write_text(json.dumps({"report": report, "rows": out}, indent=1, ensure_ascii=False))
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
