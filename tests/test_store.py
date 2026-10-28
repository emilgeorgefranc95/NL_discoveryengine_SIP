"""Phase 4 checks (architecture.md, 'Done when'). Run from rag-chatbot-new/:  .venv/bin/python -m pytest tests/test_store.py -q
Needs the built store (run src/store.py first)."""
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import config as C  # noqa: E402
import embed  # noqa: E402
import store  # noqa: E402


@pytest.fixture(scope="module")
def inputs():
    chunks = embed.load_indexed_chunks()
    vectors = np.load(embed.VECTORS_FILE)
    return chunks, vectors


@pytest.fixture(scope="module")
def col():
    return store.open_collection()


@pytest.fixture(scope="module")
def manifest():
    return json.loads(C.VECTORDB_MANIFEST.read_text())


def test_count_equals_indexed_chunks(col, inputs):
    chunks, _ = inputs
    assert col.count() == len(chunks) == json.loads(C.VECTORDB_MANIFEST.read_text())["record_count"]


def test_store_survives_a_restart():
    """A brand-new Python process opens the same folder and finds the same count and a known record."""
    code = ("import sys; sys.path.insert(0, 'src'); import store; c = store.open_collection(); "
            "r = c.get(ids=['ps_reviews:PS2-4175'], include=['documents', 'metadatas']); "
            "print(c.count(), len(r['ids']), r['metadatas'][0]['source'])")
    out = subprocess.run([sys.executable, "-c", code], cwd=C.ROOT, capture_output=True, text=True, check=True)
    n = json.loads(C.VECTORDB_MANIFEST.read_text())["record_count"]
    assert out.stdout.strip().splitlines()[-1] == f"{n} 1 Play Store review"


def test_key_fields_of_every_record_match_the_chunk_file(col, inputs):
    chunks, _ = inputs
    got = col.get(ids=[c["chunk_id"] for c in chunks], include=["documents", "metadatas"])
    assert got["ids"] == [c["chunk_id"] for c in chunks] or set(got["ids"]) == {c["chunk_id"] for c in chunks}
    by_id = {i: (d, m) for i, d, m in zip(got["ids"], got["documents"], got["metadatas"])}
    for c in chunks:
        doc, md = by_id[c["chunk_id"]]
        assert doc == c["text"], c["chunk_id"]
        assert md["source"] == c["source"] and md["parent_id"] == c["parent_id"] and md["kind"] == c["kind"]
        assert md.get("source_link", "") == c["source_link"] and md.get("date", "") == c["date"]
        assert md.get("thread_id", "") == c["thread_id"] and md.get("subreddit", "") == c["subreddit"]


def test_full_metadata_of_a_sample_matches(col, inputs):
    chunks, _ = inputs
    sample = chunks[::43][:50]
    got = col.get(ids=[c["chunk_id"] for c in sample], include=["metadatas"])
    for i, md in zip(got["ids"], got["metadatas"]):
        c = next(x for x in sample if x["chunk_id"] == i)
        assert md == store.build_metadata(c)


def test_metadata_values_are_flat_primitives(col):
    got = col.get(limit=col.count(), include=["metadatas"])
    for md in got["metadatas"]:
        assert all(isinstance(v, (str, int, float, bool)) for v in md.values())


def test_a_chunks_own_vector_finds_that_chunk_first(col, inputs):
    chunks, vectors = inputs
    rng = np.random.default_rng(1)
    text_of = {c["chunk_id"]: c["embed_text"] for c in chunks}
    for i in rng.choice(len(chunks), size=100, replace=False):
        r = col.query(query_embeddings=[vectors[i].tolist()], n_results=1)
        top = r["ids"][0][0]
        # a few short replies from different threads have identical embedded text (identical vectors): a tie is fine
        assert top == chunks[i]["chunk_id"] or text_of[top] == chunks[i]["embed_text"]
        assert r["distances"][0][0] < 1e-3


def test_stored_vectors_equal_the_saved_vectors(col, inputs):
    chunks, vectors = inputs
    sample = list(range(0, len(chunks), 97))
    got = col.get(ids=[chunks[i]["chunk_id"] for i in sample], include=["embeddings"])
    order = {i: k for k, i in enumerate(got["ids"])}
    for i in sample:
        assert np.allclose(got["embeddings"][order[chunks[i]["chunk_id"]]], vectors[i], atol=1e-5)


def test_distance_is_cosine(col):
    assert col.configuration["hnsw"]["space"] == "cosine"


def test_a_question_returns_a_relevant_chunk_with_its_source(col):
    from embed import embed_texts, load_model
    q = embed_texts(load_model(), ["Why does autopay for my SIP keep failing?"])[0]
    r = col.query(query_embeddings=[q.tolist()], n_results=5, include=["documents", "metadatas", "distances"])
    assert any("autopay" in d.lower() or "mandate" in d.lower() for d in r["documents"][0])
    assert all(m["source_link"].startswith("http") for m in r["metadatas"][0] if m["kind"] == "evidence")


def test_manifest_matches_the_inputs(manifest, col):
    emb = json.loads(embed.META_FILE.read_text())
    assert manifest["record_count"] == col.count()
    assert manifest["chunks_sha256"] == emb["chunks_sha256"] == embed.file_sha256(C.CHUNKS_FILE)
    assert manifest["vectors_sha256"] == emb["vectors_sha256"]
    assert manifest["model"] == C.EMBEDDING_MODEL and manifest["distance"] == "cosine"


def test_latest_date_equals_the_newest_dated_row_in_the_raw_files(manifest):
    """Computed from the raw csv files, independently of the chunk file."""
    newest = ""
    ps = list(csv.DictReader(open(C.RAW_DIR / "playstore_relevant_reviews.csv", encoding="utf-8-sig")))
    newest = max([r["date"] for r in ps if len(r["date"]) == 10] + [newest])
    rd = list(csv.DictReader(open(C.RAW_DIR / "reddit_raw_all.csv", encoding="utf-8-sig")))
    newest = max([r["date"] for r in rd if len(r["date"]) == 10 and r["date_basis"] == "exact"] + [newest])
    assert manifest["latest_item_date"] == newest


def test_build_refuses_stale_vectors(monkeypatch):
    monkeypatch.setattr(embed, "is_stale", lambda: True)
    with pytest.raises(RuntimeError, match="stale"):
        store.load_inputs()


def test_a_rebuild_gives_the_same_store(tmp_path, monkeypatch, col):
    """Build into a temporary folder and compare every record with the real store."""
    monkeypatch.setattr(C, "VECTORDB_DIR", tmp_path / "db")
    monkeypatch.setattr(C, "VECTORDB_MANIFEST", tmp_path / "manifest.json")
    new_col, chunks, _, _ = store.build()
    ids = [c["chunk_id"] for c in chunks]
    a = col.get(ids=ids, include=["documents", "metadatas", "embeddings"])
    b = new_col.get(ids=ids, include=["documents", "metadatas", "embeddings"])
    ia, ib = {i: k for k, i in enumerate(a["ids"])}, {i: k for k, i in enumerate(b["ids"])}
    for i in ids[::7]:
        assert a["documents"][ia[i]] == b["documents"][ib[i]] and a["metadatas"][ia[i]] == b["metadatas"][ib[i]]
        assert np.allclose(a["embeddings"][ia[i]], b["embeddings"][ib[i]])
    assert new_col.count() == col.count()


def test_no_orphan_index_folders_are_left_behind():
    import sqlite3
    con = sqlite3.connect(f"file:{C.VECTORDB_DIR / 'chroma.sqlite3'}?mode=ro", uri=True)
    live = {r[0] for r in con.execute("select id from segments")}
    folders = {d.name for d in C.VECTORDB_DIR.iterdir() if d.is_dir() and store.UUID_DIR.match(d.name)}
    assert folders and folders <= live
