"""Phase 4: vector store (ChromaDB).

Loads the indexed chunks (phase 2) and their vectors (phase 3) into one local ChromaDB collection, `sip_evidence`,
with cosine distance. The vectors come from phase 3, so Chroma never embeds anything itself. The collection is dropped
and rebuilt on every run, so a rebuild always gives the same result. Writes data/vectordb/manifest.json.

    python src/store.py              build and verify (exit code 0 only if every check passes)

Other phases use:  open_collection()
"""
import json
import re
import shutil
import sqlite3
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import embed  # noqa: E402

import chromadb  # noqa: E402
from chromadb.config import Settings  # noqa: E402

BATCH = 100


# ---------------------------------------------------------------- access
def get_client():
    """Telemetry off. Data stays in data/vectordb/."""
    C.VECTORDB_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(C.VECTORDB_DIR), settings=Settings(anonymized_telemetry=False))


def open_collection():
    """The stored collection. embedding_function=None: only our own phase 3 vectors are ever used."""
    return get_client().get_collection(C.COLLECTION_NAME, embedding_function=None)


# ---------------------------------------------------------------- records
def build_metadata(c: dict) -> dict:
    """Chroma metadata must be flat primitives, so blank values are left out and numbers stay numbers."""
    md = {
        "source": c["source"], "kind": c["kind"], "parent_id": c["parent_id"], "part": c["part"],
        "date": c["date"], "date_basis": c["date_basis"], "subreddit": c["subreddit"],
        "thread_id": c["thread_id"], "thread_title": c["thread_title"], "issues": c["issues"],
        "questions": c["questions"], "source_link": c["source_link"], "source_file": c["source_file"],
        "row_number": int(c["row_number"]), "issue_code": c["issue_code"],
        "star_rating": c["star_rating"], "score": c["score"], "count": c["count"],
    }
    return {k: v for k, v in md.items() if v != ""}


def latest_item_date(chunks) -> str:
    """Newest exact (YYYY-MM-DD) date among evidence chunks. Estimated months and undated rows are ignored."""
    exact = [c["date"] for c in chunks if c["kind"] == "evidence" and len(c["date"]) == 10 and c["date_basis"] == "exact"]
    return max(exact) if exact else ""


def load_inputs():
    """Read the indexed chunks and vectors, and refuse to build from stale or mismatched inputs."""
    chunks = embed.load_indexed_chunks()
    vectors = np.load(embed.VECTORS_FILE).astype(np.float32)
    ids = json.loads(embed.IDS_FILE.read_text(encoding="utf-8"))
    if embed.is_stale():
        raise RuntimeError("vectors are stale (chunks.jsonl changed since embedding); run src/embed.py")
    if ids != [c["chunk_id"] for c in chunks] or vectors.shape != (len(chunks), 384):
        raise RuntimeError("chunks, ids and vectors do not line up; rebuild phases 2 and 3")
    return chunks, vectors


# ---------------------------------------------------------------- build
UUID_DIR = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def remove_orphan_index_folders() -> list:
    """Rebuilding drops the old collection but ChromaDB can leave its index folder behind. Delete folders inside
    data/vectordb/ that are named like a segment id but are not registered in the database."""
    con = sqlite3.connect(f"file:{C.VECTORDB_DIR / 'chroma.sqlite3'}?mode=ro", uri=True)
    live = {r[0] for r in con.execute("select id from segments")}
    con.close()
    removed = []
    for d in C.VECTORDB_DIR.iterdir():
        if d.is_dir() and UUID_DIR.match(d.name) and d.name not in live:
            shutil.rmtree(d)
            removed.append(d.name)
    return removed


def build():
    chunks, vectors = load_inputs()
    client = get_client()
    try:
        client.delete_collection(C.COLLECTION_NAME)
    except Exception:  # first run: nothing to delete
        pass
    col = client.create_collection(
        C.COLLECTION_NAME, embedding_function=None,
        configuration={"hnsw": {"space": "cosine", "sync_threshold": 100, "batch_size": 100}},
        metadata={"description": "SIP Discovery evidence chunks (Play Store and Reddit)"})
    for i in range(0, len(chunks), BATCH):
        part = chunks[i:i + BATCH]
        col.add(ids=[c["chunk_id"] for c in part],
                embeddings=vectors[i:i + BATCH].tolist(),
                documents=[c["text"] for c in part],
                metadatas=[build_metadata(c) for c in part])
    removed = remove_orphan_index_folders()
    emb_meta = json.loads(embed.META_FILE.read_text(encoding="utf-8"))
    manifest = {
        "collection": C.COLLECTION_NAME, "record_count": col.count(), "distance": "cosine",
        "model": emb_meta["model"], "chunks_sha256": emb_meta["chunks_sha256"],
        "vectors_sha256": emb_meta["vectors_sha256"],
        "by_source": dict(Counter(c["source"] for c in chunks)),
        "latest_item_date": latest_item_date(chunks),
        "built_on": date.today().isoformat(), "chromadb_version": chromadb.__version__,
        "orphan_index_folders_removed": len(removed),
    }
    C.VECTORDB_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return col, chunks, vectors, manifest


# ---------------------------------------------------------------- verify
def verify(chunks, vectors, sample: int = 50):
    """Return a list of (check, passed, detail). Used by the CLI; tests/test_store.py repeats these independently."""
    col = open_collection()
    out = [("record count equals indexed chunks", col.count() == len(chunks), f"{col.count()} vs {len(chunks)}")]
    got = col.get(ids=[c["chunk_id"] for c in chunks], include=["documents", "metadatas"])
    by_id = {i: (d, m) for i, d, m in zip(got["ids"], got["documents"], got["metadatas"])}
    bad = [c["chunk_id"] for c in chunks
           if c["chunk_id"] not in by_id or by_id[c["chunk_id"]][0] != c["text"]
           or by_id[c["chunk_id"]][1] != build_metadata(c)]
    out.append(("every record's document and metadata match the chunk file", not bad, f"{len(bad)} differ"))
    rng = np.random.default_rng(0)
    idx = rng.choice(len(chunks), size=min(sample, len(chunks)), replace=False)
    miss = 0
    text_of = {c["chunk_id"]: c["embed_text"] for c in chunks}
    for i in idx:
        r = col.query(query_embeddings=[vectors[i].tolist()], n_results=1)
        top = r["ids"][0][0]
        miss += not (top == chunks[i]["chunk_id"] or text_of[top] == chunks[i]["embed_text"])   # identical texts tie
    out.append((f"a chunk's own vector finds that chunk first ({len(idx)} sampled)", miss == 0, f"{miss} misses"))
    cfg = col.configuration
    space = (cfg.get("hnsw") or {}).get("space") if isinstance(cfg, dict) else None
    out.append(("distance is cosine", space == "cosine", str(space)))
    return out


def main():
    col, chunks, vectors, manifest = build()
    print(f"Built collection '{manifest['collection']}': {manifest['record_count']} records "
          f"({manifest['distance']}), latest item date {manifest['latest_item_date']}")
    print("  by source:", manifest["by_source"])
    results = verify(chunks, vectors)
    for name, ok, detail in results:
        print(f"  [{'ok' if ok else 'FAIL'}] {name} ({detail})")
    print("Written: data/vectordb/ and manifest.json")
    sys.exit(0 if all(ok for _, ok, _ in results) else 1)


if __name__ == "__main__":
    main()
