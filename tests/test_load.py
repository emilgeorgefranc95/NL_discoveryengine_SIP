"""Phase 1 checks (architecture.md, 'Done when'). Run from rag-chatbot-new/:  .venv/bin/python -m pytest tests/test_load.py -q"""
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import config as C  # noqa: E402
import load  # noqa: E402


@pytest.fixture(scope="module")
def loaded():
    return load.load_all(write_report=False)


def test_row_counts_match_the_four_files(loaded):
    _, rep = loaded
    assert {k: r["rows_read"] for k, r in rep["files"].items()} == {
        "ps_reviews": 899, "ps_issues": 30, "rd_raw": 1545, "rd_issues": 30}
    assert rep["total"]["all_counts_match_expected"]


def test_kept_equals_read_minus_dropped(loaded):
    table, rep = loaded
    for key, r in rep["files"].items():
        assert r["rows_kept"] == r["rows_read"] - r["dropped_empty"] - r["dropped_deleted_or_removed"], key
        assert (table["file_key"] == key).sum() == r["rows_kept"], key
    assert len(table) == rep["total"]["rows_kept"]


def test_reddit_deleted_and_empty_rows_are_dropped(loaded):
    table, rep = loaded
    r = rep["files"]["rd_raw"]
    assert r["dropped_empty"] + r["dropped_deleted_or_removed"] == 38
    assert not table["text"].str.lower().isin(C.PLACEHOLDER_TEXTS).any()
    assert not ((table["kind"] == "evidence") & (table["text"] == "")).any()


def test_no_username_column_anywhere(loaded):
    table, _ = loaded
    assert not {c.lower() for c in table.columns} & C.FORBIDDEN_COLUMNS


def test_every_row_traces_to_its_source(loaded):
    table, _ = loaded
    assert (table["source_file"] != "").all() and (table["row_number"].astype(int) > 0).all()
    assert table["row_id"].is_unique
    assert set(table["source"]) == {"Play Store review", "Reddit post", "Reddit comment",
                                    "Play Store top issue", "Reddit top issue"}
    assert set(table["kind"]) == {"evidence", "theme_summary"}


def test_evidence_rows_have_links_and_text_is_cleaned(loaded):
    table, _ = loaded
    ev = table[table["kind"] == "evidence"]
    assert (ev["source_link"].str.startswith("http")).all()
    assert not ev["text"].str.contains(r"\n|\r|\s{2}", regex=True).any()


def test_dates_are_valid_or_blank(loaded):
    table, _ = loaded
    ok = table["date"].str.fullmatch(r"\d{4}-\d{2}-\d{2}|\d{4}-\d{2}|")
    assert ok.all()
    reddit = table[table["file_key"] == "rd_raw"]
    assert set(reddit["date_basis"]) <= {"exact", "estimated (month)", "unknown"}


def test_hinglish_and_emoji_text_is_not_altered(loaded):
    table, _ = loaded
    assert table["text"].str.contains("toh ab to rahe ho", regex=False).any()


def test_loader_is_repeatable(loaded):
    a, _ = loaded
    b, _ = load.load_all(write_report=False)
    pd.testing.assert_frame_equal(a, b)


def test_missing_column_fails_loudly(tmp_path):
    for f in C.RAW_DIR.glob("*.csv"):
        shutil.copyfile(f, tmp_path / f.name)
    p = tmp_path / "reddit_raw_all.csv"
    p.write_text(p.read_text(encoding="utf-8-sig").replace("thread_title", "thread_name", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="missing required column"):
        load.load_all(raw_dir=tmp_path, write_report=False)


def test_username_column_is_refused(tmp_path):
    for f in C.RAW_DIR.glob("*.csv"):
        shutil.copyfile(f, tmp_path / f.name)
    p = tmp_path / "playstore_relevant_reviews.csv"
    p.write_text(p.read_text(encoding="utf-8-sig").replace("source_link", "author", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="personal-identifier"):
        load.load_all(raw_dir=tmp_path, write_report=False)


def test_loader_reads_only_data_raw():
    assert C.RAW_DIR.name == "raw" and C.RAW_DIR.parent.name == "data"
    assert {s["file"] for s in C.FILES.values()} == {p.name for p in C.RAW_DIR.glob("*.csv")}
