"""Phase 3 checks (architecture.md, 'Done when'). Run from rag-chatbot-new/:  .venv/bin/python -m pytest tests/test_embed.py -q
Needs data/embeddings/ (run src/embed.py first)."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import config as C  # noqa: E402
import embed  # noqa: E402


@pytest.fixture(scope="module")
def saved():
    vectors = np.load(embed.VECTORS_FILE)
    ids = json.loads(embed.IDS_FILE.read_text())
    meta = json.loads(embed.META_FILE.read_text())
    chunks = embed.load_indexed_chunks()
    return vectors, ids, meta, chunks


@pytest.fixture(scope="module")
def model():
    return embed.load_model()


def test_one_vector_per_indexed_chunk_in_the_same_order(saved):
    vectors, ids, meta, chunks = saved
    assert vectors.shape == (len(chunks), 384) == (meta["chunks_embedded"], meta["vector_size"])
    assert ids == [c["chunk_id"] for c in chunks] and len(set(ids)) == len(ids)
    assert vectors.dtype == np.float32


def test_vectors_are_unit_length_finite_and_non_zero(saved):
    vectors, *_ = saved
    assert np.isfinite(vectors).all()
    norms = np.linalg.norm(vectors, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-4) and (norms > 0).all()


def test_no_text_is_cut_off_by_the_model_window(saved):
    *_, meta, chunks = saved
    assert meta["texts_longer_than_model_window"] == 0


def test_short_and_unindexed_chunks_are_not_embedded(saved):
    _, ids, _, _ = saved
    all_chunks = [json.loads(line) for line in open(C.CHUNKS_FILE, encoding="utf-8")]
    unindexed = {c["chunk_id"] for c in all_chunks if not c["indexed"]}
    assert unindexed and not unindexed & set(ids)


def test_vectors_match_the_current_chunk_file_and_model(saved):
    _, _, meta, _ = saved
    assert not embed.is_stale()
    assert meta["model"] == C.EMBEDDING_MODEL and meta["vectors_sha256"] == embed.file_sha256(embed.VECTORS_FILE)


def test_re_embedding_a_sample_reproduces_the_saved_vectors(saved, model):
    vectors, _, _, chunks = saved
    idx = list(range(0, len(chunks), 37))
    again = embed.embed_texts(model, [chunks[i]["embed_text"] for i in idx])
    assert np.allclose(again, vectors[idx], atol=1e-5)


def test_nearest_neighbours_are_on_the_same_topic(saved):
    """Play Store reviews carry issue tags. For one review per topic, most of its 5 nearest reviews share the tag."""
    vectors, ids, _, chunks = saved
    tags = {i: set(t.strip() for t in c["issues"].split(";") if t.strip()) for i, c in enumerate(chunks)
            if c["source"] == "Play Store review"}
    for topic in ("AUTOPAY_MANDATE_FAIL", "REDEMPTION_DELAY", "KYC_ONBOARDING_BLOCK", "SIP_DEBITED_NOT_INVESTED"):
        members = [i for i, t in tags.items() if topic in t]
        assert len(members) >= 10, topic
        agreed = []
        for q in members[:8]:
            sims = vectors @ vectors[q]
            sims[q] = -1
            top = [i for i in np.argsort(-sims) if i in tags][:5]
            agreed.append(sum(topic in tags[i] for i in top))
        assert np.mean(agreed) >= 2.0, (topic, agreed)       # random chance would give well under 1


def test_a_question_finds_a_chunk_on_the_topic(saved, model):
    vectors, ids, _, chunks = saved
    q = embed.embed_texts(model, ["Why does my SIP autopay keep failing?"])[0]
    top = [chunks[i] for i in np.argsort(-(vectors @ q))[:5]]
    assert any("autopay" in c["embed_text"].lower() or "mandate" in c["embed_text"].lower() for c in top)
