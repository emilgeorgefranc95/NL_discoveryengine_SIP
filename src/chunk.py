"""Phase 2: chunking.

Turns the loaded table into chunks. One row = one chunk, except Reddit rows too long for the embedding model,
which are split into parts. Writes data/chunks/chunks.jsonl and data/chunks/chunk_report.json.

    python src/chunk.py
"""
import hashlib
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import load  # noqa: E402

USER_MENTION = re.compile(r"(?<![\w/])/?u/[A-Za-z0-9_-]{3,}")
# image links: redd.it image hosts, imgur, or any URL ending in an image extension (with or without a query string)
IMAGE_URL = re.compile(
    r"https?://(?:preview\.redd\.it|i\.redd\.it|i\.imgur\.com|imgur\.com)/\S*|https?://\S+?\.(?:png|jpe?g|gif|webp)(?:\?\S*)?",
    re.I)
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

VALID_SOURCES = {"Play Store review", "Reddit post", "Reddit comment", "Play Store top issue", "Reddit top issue"}


# ---------------------------------------------------------------- text helpers
_TOKENIZER = None


def n_tokens(text: str) -> int:
    """Length of the text in word-pieces for the embedding model (including its two special tokens)."""
    global _TOKENIZER
    if _TOKENIZER is None:
        from transformers import AutoTokenizer
        _TOKENIZER = AutoTokenizer.from_pretrained(C.EMBEDDING_MODEL)
        _TOKENIZER.model_max_length = 10**6            # we measure length here; silence the truncation warning
    return len(_TOKENIZER(text, add_special_tokens=True, truncation=False)["input_ids"])


def mask_users(text: str):
    """Replace u/name mentions by 'u/[user]' (the PRD forbids storing personal identifiers). Returns (text, n_masked)."""
    return USER_MENTION.subn("u/[user]", text)


def strip_images(text: str):
    """Remove image links (they carry no meaning for search). Returns (text, n_removed)."""
    out, n = IMAGE_URL.subn(" ", text)
    return re.sub(r"\s+", " ", out).strip(), n


def split_text(text: str, limit: int, overlap: int = C.SPLIT_OVERLAP_CHARS):
    """Split text into parts of at most `limit` characters at sentence boundaries. A part starts with the last sentence
    of the previous part when that sentence is short (the overlap). Sentences longer than the limit are cut at spaces."""
    if len(text) <= limit:
        return [text]
    pieces = []
    for sent in SENTENCE_END.split(text):
        while len(sent) > limit:                      # no punctuation to cut on: cut at the last space before the limit
            cut = sent.rfind(" ", 0, limit)
            cut = cut if cut > limit // 2 else limit
            pieces.append(sent[:cut].strip())
            sent = sent[cut:].strip()
        if sent:
            pieces.append(sent)
    parts, cur = [], []
    for p in pieces:
        if cur and len(" ".join(cur + [p])) > limit:
            parts.append(" ".join(cur))
            tail = cur[-1]
            cur = [tail, p] if len(tail) <= overlap and len(tail) + 1 + len(p) <= limit else [p]
        else:
            cur.append(p)
    if cur and (not parts or " ".join(cur) != parts[-1]):
        parts.append(" ".join(cur))
    return parts


def _end(s: str) -> str:
    """Trim trailing spaces and stray punctuation and end the phrase with one full stop, keeping a question or exclamation mark."""
    s = s.strip().rstrip(".;: ")
    return s if s.endswith(("?", "!")) else s + "."


def _int_or_blank(v):
    return int(v) if str(v).strip().lstrip("-").isdigit() else ""


# ---------------------------------------------------------------- per-source prefixes (what is added in front of the text)
def evidence_prefix(row) -> str:
    src = row["source"]
    if src == "Play Store review":
        stars = _int_or_blank(row.get("star_rating", ""))
        head = f"Play Store review, {stars}-star." if stars != "" else "Play Store review."
        summ = row.get("summary", "").strip()
        return f"{head} {_end(summ)} " if summ else f"{head} "
    if src == "Reddit post":
        return f"Reddit post in r/{row['subreddit']}. "
    # Phase 6 tuning (28 Oct 2026): the thread title is NOT embedded. With it, every reply in a SIP-titled thread looked like a
    # match for a generic SIP question; without it, "at least partly relevant" rose from 64% to 74.5% on the tuning half.
    # The title stays in the metadata (thread_title) for display.
    return f"Reddit comment in r/{row['subreddit']}. "


def build_chunks(table):
    """Return (chunks, stats). `table` comes from load.load_all()."""
    chunks = []
    st = Counter()
    for row in table.to_dict("records"):
        kind = row["kind"]
        parent_id = f"{row['file_key']}:{row['row_id']}"
        base = {
            "parent_id": parent_id, "kind": kind, "source": row["source"],
            "source_file": row["source_file"], "row_number": int(row["row_number"]),
            "date": row["date"], "date_basis": row["date_basis"],
            "subreddit": row.get("subreddit", ""), "thread_id": row.get("thread_id", ""),
            "thread_title": row.get("thread_title", ""),
            "star_rating": _int_or_blank(row.get("star_rating", "")), "score": _int_or_blank(row.get("score", "")),
            "issues": row.get("issues", ""), "questions": row.get("questions", ""),
            "issue_code": "", "count": "",
        }

        if kind == "theme_summary":
            fields = [row["issue"], row["what_people_say"], row["example_quotes"].replace(" || ", " ")]
            masked, n = zip(*(mask_users(f) for f in fields))
            st["user_mentions_masked"] += sum(n)
            masked, n_img = zip(*(strip_images(f) for f in masked))
            st["image_links_stripped"] += sum(n_img)
            display = f"{_end(masked[0])} {_end(masked[1])}"
            embed = display     # Phase 6: the example quotes are NOT embedded; they swamped the topic and made summaries match everything
            base.update(issue_code=row["code"], count=_int_or_blank(row.get("reviews") or row.get("mentions")),
                        source_link="")
            chunks.append({**base, "chunk_id": parent_id, "part": "1/1", "text": display, "embed_text": embed,
                           "is_short": False, "indexed": True})
            continue

        # evidence rows
        text, n_masked = mask_users(row["text"])
        st["user_mentions_masked"] += n_masked
        body, n_img = strip_images(text)
        st["image_links_stripped"] += n_img
        base["source_link"] = row["source_link"]
        if len(body) < C.SHORT_TEXT_CHARS:
            chunks.append({**base, "chunk_id": parent_id, "part": "1/1", "text": text, "embed_text": "",
                           "is_short": True, "indexed": False})
            st["short_rows_not_indexed"] += 1
            continue
        prefix = evidence_prefix(row)
        if n_tokens(prefix + body) <= C.MAX_EMBED_TOKENS:
            parts = [body]
        else:
            limit = max(C.MIN_PART_TEXT_CHARS, C.EMBED_CHAR_BUDGET - len(prefix))
            while True:                                   # shrink the parts until every one fits the model window
                parts = split_text(body, limit)
                if all(n_tokens(prefix + p) <= C.MAX_EMBED_TOKENS for p in parts) or limit <= 120:
                    break
                limit = int(limit * 0.85)
            st["rows_split"] += 1
            st["parts_from_split_rows"] += len(parts)
        display_parts = [text] if len(parts) == 1 else parts      # split parts show their own part
        for i, (disp, emb) in enumerate(zip(display_parts, parts), 1):
            cid = parent_id if len(parts) == 1 else f"{parent_id}#p{i}"
            chunks.append({**base, "chunk_id": cid, "part": f"{i}/{len(parts)}", "text": disp,
                           "embed_text": prefix + emb, "is_short": False, "indexed": True})
    return chunks, st


def make_report(chunks, stats, load_rep):
    indexed = [c for c in chunks if c["indexed"]]
    lens = [n_tokens(c["embed_text"]) for c in indexed]
    over = [c["chunk_id"] for c, n in zip(indexed, lens) if n > C.MAX_EMBED_TOKENS]
    short = [c for c in chunks if c["is_short"]]
    return {
        "input_rows_kept_by_loader": load_rep["total"]["rows_kept"],
        "source_rows_represented": len({c["parent_id"] for c in chunks}),
        "chunks_total": len(chunks),
        "chunks_indexed": len(indexed),
        "chunks_not_indexed_short": len(short),
        "by_source_indexed": dict(Counter(c["source"] for c in indexed)),
        "by_source_not_indexed": dict(Counter(c["source"] for c in short)),
        "by_kind_indexed": dict(Counter(c["kind"] for c in indexed)),
        "rows_split": stats["rows_split"],
        "parts_from_split_rows": stats["parts_from_split_rows"],
        "user_mentions_masked": stats["user_mentions_masked"],
        "image_links_stripped": stats["image_links_stripped"],
        "embed_text_tokens": {"median": int(statistics.median(lens)), "p90": sorted(lens)[int(0.9 * len(lens))],
                              "longest": max(lens), "budget": C.MAX_EMBED_TOKENS},
        "indexed_chunks_over_budget": over,
        "short_row_threshold_chars": C.SHORT_TEXT_CHARS,
    }


def write_chunks(chunks, path=C.CHUNKS_FILE):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(write=True):
    table, load_rep = load.load_all(write_report=write)
    chunks, stats = build_chunks(table)
    report = make_report(chunks, stats, load_rep)
    if write:
        report["chunks_file"] = str(C.CHUNKS_FILE.relative_to(C.ROOT))
        report["chunks_sha256"] = write_chunks(chunks)
        C.CHUNK_REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return chunks, report


def main():
    chunks, r = run()
    print(f"{r['source_rows_represented']} rows -> {r['chunks_total']} chunks "
          f"({r['chunks_indexed']} indexed, {r['chunks_not_indexed_short']} short and not indexed)")
    print(f"  split: {r['rows_split']} rows into {r['parts_from_split_rows']} parts | "
          f"u/name masked: {r['user_mentions_masked']} | image links stripped: {r['image_links_stripped']}")
    print(f"  embed_text word-pieces: median {r['embed_text_tokens']['median']}, longest {r['embed_text_tokens']['longest']} "
          f"(window {r['embed_text_tokens']['budget']}); over the window: {len(r['indexed_chunks_over_budget'])}")
    print("  indexed by source:", r["by_source_indexed"])
    print("Written: data/chunks/chunks.jsonl and chunk_report.json")


if __name__ == "__main__":
    main()
