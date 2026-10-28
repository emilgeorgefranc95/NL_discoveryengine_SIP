"""Phase 2 checks (architecture.md, 'Done when'). Run from rag-chatbot-new/:  .venv/bin/python -m pytest tests/test_chunk.py -q"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import chunk  # noqa: E402
import config as C  # noqa: E402
import load  # noqa: E402


@pytest.fixture(scope="module")
def built():
    table, load_rep = load.load_all(write_report=False)
    chunks, stats = chunk.build_chunks(table)
    return table, chunks, chunk.make_report(chunks, stats, load_rep)


def test_every_loaded_row_has_a_chunk(built):
    table, chunks, rep = built
    expected = {f"{r.file_key}:{r.row_id}" for r in table.itertuples()}
    assert {c["parent_id"] for c in chunks} == expected
    assert rep["source_rows_represented"] == len(table) == 2466


def test_each_chunk_traces_to_exactly_one_source_row(built):
    table, chunks, _ = built
    key = {f"{r.file_key}:{r.row_id}": (r.source_file, int(r.row_number)) for r in table.itertuples()}
    for c in chunks:
        assert key[c["parent_id"]] == (c["source_file"], c["row_number"])
    assert len({c["chunk_id"] for c in chunks}) == len(chunks)


def test_no_indexed_chunk_exceeds_the_embedding_window(built):
    _, chunks, rep = built
    assert rep["indexed_chunks_over_budget"] == []
    assert max(chunk.n_tokens(c["embed_text"]) for c in chunks if c["indexed"]) <= C.MAX_EMBED_TOKENS


def test_valid_source_and_links(built):
    _, chunks, _ = built
    for c in chunks:
        assert c["source"] in chunk.VALID_SOURCES
        if c["kind"] == "evidence":
            assert c["source_link"].startswith("http"), c["chunk_id"]
        else:
            assert c["source_link"] == ""
        assert c["kind"] == ("theme_summary" if "top issue" in c["source"] else "evidence")


def test_short_rows_kept_but_not_indexed(built):
    _, chunks, _ = built
    short = [c for c in chunks if c["is_short"]]
    assert short and all(not c["indexed"] and c["embed_text"] == "" for c in short)
    assert all(c["source"] == "Reddit comment" for c in short)
    assert all(c["indexed"] and c["embed_text"] for c in chunks if not c["is_short"])


def test_usernames_masked_and_image_links_stripped(built):
    _, chunks, rep = built
    for c in chunks:
        assert not chunk.USER_MENTION.search(c["text"]) and not chunk.USER_MENTION.search(c["embed_text"]), c["chunk_id"]
        assert not chunk.IMAGE_URL.search(c["embed_text"]), c["chunk_id"]
    assert rep["user_mentions_masked"] >= 18 and rep["image_links_stripped"] >= 1


def test_split_parts_are_numbered_and_cover_the_original(built):
    table, chunks, rep = built
    assert rep["rows_split"] > 0
    by_parent = {}
    for c in chunks:
        by_parent.setdefault(c["parent_id"], []).append(c)
    orig = {f"{r.file_key}:{r.row_id}": r.text for r in table.itertuples()}
    for pid, parts in by_parent.items():
        if len(parts) == 1:
            assert parts[0]["part"] == "1/1" and "#p" not in parts[0]["chunk_id"]
            continue
        assert [p["part"] for p in parts] == [f"{i}/{len(parts)}" for i in range(1, len(parts) + 1)]
        words = set(chunk.strip_images(chunk.mask_users(orig[pid])[0])[0].split())
        got = set(" ".join(p["text"] for p in parts).split())
        assert words <= got, pid            # no word of the original is lost


def test_split_text_function():
    s = " ".join(f"This is sentence number {i} of a long post." for i in range(60))
    parts = chunk.split_text(s, 300)
    assert all(len(p) <= 300 for p in parts) and len(parts) > 1
    assert "sentence number 59" in parts[-1]
    long_word = "x" * 2500
    assert all(len(p) <= 300 for p in chunk.split_text(long_word, 300))
    assert chunk.split_text("short", 300) == ["short"]


def test_embed_text_prefixes(built):
    _, chunks, _ = built
    by_src = {}
    for c in chunks:
        if c["indexed"]:
            by_src.setdefault(c["source"], c)
    assert by_src["Play Store review"]["embed_text"].startswith("Play Store review, ")
    assert by_src["Reddit post"]["embed_text"].startswith("Reddit post in r/")
    c = by_src["Reddit comment"]["embed_text"]
    assert c.startswith("Reddit comment in r/") and "Thread: " not in c      # the thread title is not embedded (phase 6 tuning)
    assert "||" not in by_src["Play Store top issue"]["embed_text"]


def test_thread_title_is_kept_as_metadata_but_not_embedded(built):
    _, chunks, _ = built
    comments = [c for c in chunks if c["source"] == "Reddit comment" and c["thread_title"] == "Do SIPs really work?"]
    assert comments and all("Do SIPs really work" not in c["embed_text"] for c in comments)


def test_text_is_original_wording(built):
    _, chunks, _ = built
    assert any("toh ab to rahe ho" in c["text"] for c in chunks)          # Hinglish untouched
    assert any(c["source"] == "Reddit comment" and "[user]" in c["text"] for c in chunks)


def test_run_is_deterministic(tmp_path):
    a = chunk.write_chunks(chunk.build_chunks(load.load_all(write_report=False)[0])[0], tmp_path / "a.jsonl")
    b = chunk.write_chunks(chunk.build_chunks(load.load_all(write_report=False)[0])[0], tmp_path / "b.jsonl")
    assert a == b
