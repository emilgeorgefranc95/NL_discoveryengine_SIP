"""Phase 6 tuning experiment (tuning half only): can a small change improve the ranking?

    python tests/experiment_variants.py build      builds variant results for the dev questions and judging pools for new pairs
    python tests/experiment_variants.py compare    prints dev precision of baseline and variants (after judging)

Variants:  min100 = evidence chunks with under 100 characters of text are not returned
           notitle = Reddit comments are embedded without their thread title (re-embedded into a temporary store)
Hinglish questions reuse the baseline Gemini rewrites, so only the ranking changes.
"""
import csv
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
import chromadb  # noqa: E402
from chromadb.config import Settings  # noqa: E402

import chunk as CH  # noqa: E402
import config as C  # noqa: E402
import embed  # noqa: E402
import retrieve as R  # noqa: E402
import score_retrieval_eval as S  # noqa: E402
import store  # noqa: E402

RES, JUD, Q = C.TESTS_DATA_DIR / "results", C.TESTS_DATA_DIR / "judgments", C.TESTS_DATA_DIR / "questions"


def notitle_text(c):
    if c["source"] != "Reddit comment":
        return c["embed_text"]
    return f"Reddit comment in r/{c['subreddit']}. " + CH.strip_images(c["text"])[0]


def build_variant_store(name, transform):
    chunks = embed.load_indexed_chunks()
    model = embed.load_model()
    vecs = embed.embed_texts(model, [transform(c) for c in chunks])
    d = RES / f"variant_{name}"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    client = chromadb.PersistentClient(path=str(d), settings=Settings(anonymized_telemetry=False))
    col = client.create_collection(C.COLLECTION_NAME, embedding_function=None,
                                   configuration={"hnsw": {"space": "cosine", "sync_threshold": 100, "batch_size": 100}})
    for i in range(0, len(chunks), 100):
        part = chunks[i:i + 100]
        col.add(ids=[c["chunk_id"] for c in part], embeddings=vecs[i:i + 100].tolist(), documents=[c["text"] for c in part],
                metadatas=[store.build_metadata(c) for c in part])
    return model, col


def run_dev(ret, base):
    C.MIN_SIMILARITY = -1.0
    out = []
    for q in base["relevance"] + base["hinglish"]:
        if q["split"] != "dev":
            continue
        fn = None
        if q["qid"].startswith("H"):
            eng = q["question_english"]
            fn = lambda _q, e=eng: (e, "reused baseline rewrite")  # noqa: E731
        r = R.retrieve(q["question"], retriever=ret, rewrite_fn=fn)
        out.append({"qid": q["qid"], "split": "dev", "chunks": [{"id": c["id"], "similarity": c["similarity"], "source": c["source"],
                    "thread_id": c.get("thread_id", ""), "text": c["text"], "source_link": c.get("source_link", "")} for c in r["chunks"]]})
    return out


def pool(name, rows, J):
    meta = {q["qid"]: q for q in csv.DictReader((Q / "relevance_en.csv").open(encoding="utf-8"))}
    meta.update({q["qid"]: q for q in csv.DictReader((Q / "hinglish.csv").open(encoding="utf-8"))})
    todo, seen = [], set()
    for q in rows:
        for c in q["chunks"][:5]:
            pid = f"{q['qid']}|{c['id']}"
            if pid not in J and pid not in seen:
                seen.add(pid)
                todo.append({"pid": pid, "question": meta[q["qid"]]["question"], "intent": meta[q["qid"]]["intent"],
                             "source": c["source"], "chunk": c["text"][:900]})
    for i in range(0, len(todo), 60):
        with (JUD / f"pool_{name}_{i // 60 + 1:02d}.jsonl").open("w", encoding="utf-8") as f:
            for r in todo[i:i + 60]:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(todo)


def main():
    cmd = sys.argv[1]
    base = json.loads((RES / "run_baseline.json").read_text(encoding="utf-8"))["sets"]
    J = S.load_judgments()
    if cmd == "build":
        ret = R.Retriever()
        ret.search("warm up")
        C.MIN_RESULT_CHARS = 100
        rows = run_dev(ret, base)
        (RES / "variant_min100.json").write_text(json.dumps(rows), encoding="utf-8")
        print("min100: new pairs to judge:", pool("min100", rows, J))
        C.MIN_RESULT_CHARS = 0
        model, col = build_variant_store("notitle", notitle_text)
        v = R.Retriever()
        v._model, v._col, v._manifest = model, col, json.loads(C.VECTORDB_MANIFEST.read_text())
        rows = run_dev(v, base)
        (RES / "variant_notitle.json").write_text(json.dumps(rows), encoding="utf-8")
        print("notitle: new pairs to judge:", pool("notitle", rows, J))
    else:
        dev = [q for q in base["relevance"] + base["hinglish"] if q["split"] == "dev"]
        print("DEV precision @5 (strict / lenient / hit@3 lenient), 40 questions (20 English + 20 Hinglish)")
        for name, rows in (("baseline", dev), ("min100", json.loads((RES / "variant_min100.json").read_text())),
                           ("notitle", json.loads((RES / "variant_notitle.json").read_text()))):
            p = S.prec(rows, J)
            src = [J.get(f"{q['qid']}|{c['id']}") for q in rows for c in q["chunks"][:5]]
            reddit = sum(1 for q in rows for c in q["chunks"][:5] if c["source"].startswith("Reddit"))
            print(f"  {name:9s} {p['p@5_strict']} / {p['p@5_lenient']} / {p['hit@3_lenient']}   (unjudged {p['unjudged_pairs']}, Reddit share {reddit / len(src):.2f})")


if __name__ == "__main__":
    main()
