"""Phase 1: data loading.

Reads the four corpus files from data/raw/, checks them, cleans the text lightly, drops rows with no content,
and returns one table. Writes data/chunks/load_report.json.

    python src/load.py
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

DATE_FULL = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_MONTH = re.compile(r"^\d{4}-\d{2}$")

# Counts only (never values) of things the PRD says must not be stored. Chunking decides what to do about them.
PII_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone_10_digit": re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"),
    "pan": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "aadhaar_12_digit": re.compile(r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)"),
    "reddit_username_mention": re.compile(r"(?<![\w/])/?u/[A-Za-z0-9_-]{3,}"),
}


def clean_text(value: str) -> str:
    """Collapse line breaks and runs of spaces into single spaces. Nothing else is changed."""
    return re.sub(r"\s+", " ", value).strip()


def normalise_date(value: str):
    """Return (date, valid). Accepts YYYY-MM-DD or YYYY-MM; blank is valid (unknown)."""
    v = value.strip()
    if not v:
        return "", True
    if DATE_FULL.match(v) or DATE_MONTH.match(v):
        return v, True
    return "", False


def load_file(key: str, raw_dir: Path):
    """Load one corpus file. Returns (kept_dataframe, file_report)."""
    spec = C.FILES[key]
    path = Path(raw_dir) / spec["file"]
    if not path.exists():
        raise FileNotFoundError(f"{key}: {path} not found")
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")

    forbidden = [c for c in df.columns if c.strip().lower() in C.FORBIDDEN_COLUMNS]
    if forbidden:
        raise ValueError(f"{key}: personal-identifier column(s) present: {forbidden}")
    missing = [c for c in spec["required"] if c not in df.columns]
    if missing:
        raise ValueError(f"{key}: missing required column(s): {missing}")

    rows_read = len(df)
    for col in df.columns:
        df[col] = df[col].map(clean_text) if col in spec["text_cols"] else df[col].str.strip()
    df.insert(0, "row_number", range(1, rows_read + 1))
    df.insert(0, "source_file", spec["file"])
    df.insert(0, "file_key", key)

    if spec["source"]:
        df["source"] = spec["source"]
    df["kind"] = spec["kind"]
    if "id" in df.columns:
        df["row_id"] = df["id"]
    else:
        df["row_id"] = [f"{key}-rank{int(r):02d}" for r in df["rank"]]

    # dates (evidence files only)
    bad_dates = 0
    if "date" in df.columns:
        parsed = df["date"].map(normalise_date)
        bad_dates = int((~parsed.map(lambda t: t[1])).sum())
        df["date"] = parsed.map(lambda t: t[0])
        if "date_basis" not in df.columns:
            df["date_basis"] = df["date"].map(lambda d: "" if not d else "exact")
        df.loc[df["date"] == "", "date_basis"] = "unknown"
    else:
        df["date"] = ""
        df["date_basis"] = ""

    # drop rows with no content
    empty = (df[spec["content_cols"]] == "").all(axis=1)
    placeholder = pd.Series(False, index=df.index)
    if "text" in df.columns:
        placeholder = df["text"].str.lower().isin(C.PLACEHOLDER_TEXTS)
    dropped_empty = int(empty.sum())
    dropped_placeholder = int((placeholder & ~empty).sum())
    keep = ~(empty | placeholder)
    kept = df[keep].reset_index(drop=True)

    duplicate_ids = int(kept["row_id"].duplicated().sum())
    pii = {name: 0 for name in PII_PATTERNS}
    if "text" in kept.columns:
        for name, pat in PII_PATTERNS.items():
            pii[name] = int(kept["text"].str.contains(pat).sum())

    report = {
        "file": spec["file"],
        "kind": spec["kind"],
        "rows_read": rows_read,
        "expected_rows": spec["expected_rows"],
        "matches_expected": rows_read == spec["expected_rows"],
        "dropped_empty": dropped_empty,
        "dropped_deleted_or_removed": dropped_placeholder,
        "rows_kept": len(kept),
        "duplicate_row_ids": duplicate_ids,
        "invalid_dates_blanked": bad_dates,
        "rows_without_date": int((kept["date"] == "").sum()) if kept["kind"].eq("evidence").any() else None,
        "pii_scan_rows_flagged": pii,
    }
    return kept, report


def load_all(raw_dir: Path = C.RAW_DIR, write_report: bool = True):
    """Load all four files into one table (union of columns, blanks as empty strings)."""
    frames, reports = [], {}
    for key in C.FILES:
        kept, rep = load_file(key, raw_dir)
        frames.append(kept)
        reports[key] = rep
    table = pd.concat(frames, ignore_index=True).fillna("")
    total = {
        "rows_read": sum(r["rows_read"] for r in reports.values()),
        "rows_kept": len(table),
        "rows_dropped": sum(r["rows_read"] for r in reports.values()) - len(table),
        "all_counts_match_expected": all(r["matches_expected"] for r in reports.values()),
    }
    full = {"raw_dir": str(raw_dir), "files": reports, "total": total}
    if write_report:
        C.CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
        (C.CHUNKS_DIR / "load_report.json").write_text(json.dumps(full, indent=2), encoding="utf-8")
    return table, full


def main():
    table, rep = load_all()
    print(f"Loaded {rep['total']['rows_kept']} of {rep['total']['rows_read']} rows "
          f"({rep['total']['rows_dropped']} dropped). Counts match expected: {rep['total']['all_counts_match_expected']}")
    for key, r in rep["files"].items():
        print(f"  {key:11s} read {r['rows_read']:5d}  kept {r['rows_kept']:5d}  "
              f"dropped empty {r['dropped_empty']}, deleted/removed {r['dropped_deleted_or_removed']}")
    print("Report: data/chunks/load_report.json")


if __name__ == "__main__":
    main()
