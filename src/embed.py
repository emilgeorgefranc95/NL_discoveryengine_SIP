"""Phase 3: embedding.

Turns the `embed_text` of every indexed chunk into a 384-number vector with all-MiniLM-L6-v2.
Reads data/chunks/chunks.jsonl, writes data/embeddings/{vectors.npy, ids.json, embedding_meta.json}.

    python src/embed.py
"""
import hashlib
import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

BATCH_SIZE = 32
MAX_SEQ_LENGTH = 256
VECTORS_FILE = C.EMBEDDINGS_DIR / "vectors.npy"
IDS_FILE = C.EMBEDDINGS_DIR / "ids.json"
META_FILE = C.EMBEDDINGS_DIR / "embedding_meta.json"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_indexed_chunks(path: Path = C.CHUNKS_FILE):
    """Return the chunks that are to be embedded (indexed = true), in file order."""
    if not Path(path).exists():
        raise FileNotFoundError(f"{path} not found; run src/chunk.py first")
    chunks = [json.loads(line) for line in open(path, encoding="utf-8")]
    return [c for c in chunks if c["indexed"]]


def load_model(name: str = C.EMBEDDING_MODEL):
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(name, device="cpu")
    model.max_seq_length = MAX_SEQ_LENGTH
    return model


def embed_texts(model, texts, batch_size: int = BATCH_SIZE) -> np.ndarray:
    """Encode texts into unit-length float32 vectors (so cosine similarity = dot product)."""
    vecs = model.encode(list(texts), batch_size=batch_size, normalize_embeddings=True,
                        convert_to_numpy=True, show_progress_bar=False)
    return np.asarray(vecs, dtype=np.float32)


def count_truncated(model, texts) -> int:
    """How many texts are longer than the model window in word-pieces (the model silently ignores the rest)."""
    tok = model.tokenizer
    n = 0
    for i in range(0, len(texts), 256):
        enc = tok(list(texts[i:i + 256]), add_special_tokens=True, truncation=False)["input_ids"]
        n += sum(1 for ids in enc if len(ids) > MAX_SEQ_LENGTH)
    return n


def run(write: bool = True):
    t0 = time.time()
    chunks = load_indexed_chunks()
    texts = [c["embed_text"] for c in chunks]
    ids = [c["chunk_id"] for c in chunks]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate chunk ids; cannot embed")
    model = load_model()
    vectors = embed_texts(model, texts)
    truncated = count_truncated(model, texts)
    norms = np.linalg.norm(vectors, axis=1)
    meta = {
        "model": C.EMBEDDING_MODEL,
        "vector_size": int(vectors.shape[1]),
        "max_seq_length": MAX_SEQ_LENGTH,
        "normalised": True,
        "chunks_embedded": int(vectors.shape[0]),
        "chunks_file": str(C.CHUNKS_FILE.relative_to(C.ROOT)),
        "chunks_sha256": file_sha256(C.CHUNKS_FILE),
        "texts_longer_than_model_window": truncated,
        "norm_min": float(norms.min()), "norm_max": float(norms.max()),
        "nan_values": int(np.isnan(vectors).sum()),
        "built_on": date.today().isoformat(),
        "seconds": round(time.time() - t0, 1),
    }
    if write:
        C.EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
        np.save(VECTORS_FILE, vectors)
        IDS_FILE.write_text(json.dumps(ids), encoding="utf-8")
        meta["vectors_sha256"] = file_sha256(VECTORS_FILE)
        META_FILE.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return vectors, ids, meta


def is_stale() -> bool:
    """True when the saved vectors were made from a different chunks.jsonl than the one on disk."""
    if not META_FILE.exists():
        return True
    return json.loads(META_FILE.read_text())["chunks_sha256"] != file_sha256(C.CHUNKS_FILE)


def main():
    vectors, ids, m = run()
    print(f"Embedded {m['chunks_embedded']} chunks -> {vectors.shape} in {m['seconds']}s ({m['model']})")
    print(f"  unit length: min {m['norm_min']:.6f}, max {m['norm_max']:.6f} | NaN values: {m['nan_values']} | "
          f"texts longer than the model window: {m['texts_longer_than_model_window']}")
    print("Written: data/embeddings/vectors.npy, ids.json, embedding_meta.json")


if __name__ == "__main__":
    main()
