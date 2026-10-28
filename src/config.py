"""Paths, file specs and constants for the SIP Discovery pipeline (see architecture.md)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW_DIR = DATA / "raw"
CHUNKS_DIR = DATA / "chunks"
EMBEDDINGS_DIR = DATA / "embeddings"
VECTORDB_DIR = DATA / "vectordb"
TESTS_DATA_DIR = DATA / "tests"

# ---- phase 1: the four corpus files (the only input), read from data/raw/ ----
# kind: "evidence" rows are quotable and cited; "theme_summary" rows are AI-written summaries used as context only.
FILES = {
    "ps_reviews": {
        "file": "playstore_relevant_reviews.csv",
        "kind": "evidence",
        "source": None,                      # the file has its own `source` column
        "expected_rows": 899,
        "required": ["id", "source", "app", "date", "star_rating", "helpful_votes", "text", "relevance",
                     "issues", "questions", "summary", "source_link"],
        "content_cols": ["text"],            # a row with all of these empty is dropped
        "text_cols": ["text", "summary"],
    },
    "ps_issues": {
        "file": "playstore_top_issues.csv",
        "kind": "theme_summary",
        "source": "Play Store top issue",
        "expected_rows": 30,
        "required": ["rank", "issue", "code", "reviews", "what_people_say",
                     "why_it_matters_for_sip_continuation", "example_quotes"],
        "content_cols": ["what_people_say", "example_quotes"],
        "text_cols": ["issue", "what_people_say", "why_it_matters_for_sip_continuation", "example_quotes"],
    },
    "rd_raw": {
        "file": "reddit_raw_all.csv",
        "kind": "evidence",
        "source": None,
        "expected_rows": 1545,
        "required": ["id", "source", "subreddit", "type", "thread_id", "thread_title", "date", "date_basis",
                     "score", "text", "source_link"],
        "content_cols": ["text"],
        "text_cols": ["text", "thread_title"],
    },
    "rd_issues": {
        "file": "reddit_top_issues.csv",
        "kind": "theme_summary",
        "source": "Reddit top issue",
        "expected_rows": 30,
        "required": ["rank", "issue", "code", "mentions", "threads", "what_people_say",
                     "why_it_matters_for_sip_continuation", "example_quotes"],
        "content_cols": ["what_people_say", "example_quotes"],
        "text_cols": ["issue", "what_people_say", "why_it_matters_for_sip_continuation", "example_quotes"],
    },
}

# Rows whose whole text is one of these are removed (Reddit placeholders for deleted content).
PLACEHOLDER_TEXTS = {"[deleted]", "[removed]"}

# Column names that would mean personal identifiers (usernames) are present. The loader refuses to run if it finds one.
FORBIDDEN_COLUMNS = {"author", "username", "user_name", "user", "reviewer", "name of the reviewer",
                     "name of the commentor", "name of the commenter"}

# ---- phase 2: chunking ----
MAX_EMBED_TOKENS = 256          # all-MiniLM-L6-v2 reads at most 256 word-pieces (counted with the model's own tokenizer); longer rows are split
EMBED_CHAR_BUDGET = 1000        # first guess for the size of a split part (about 4 characters per word-piece); refined by token counts
SPLIT_OVERLAP_CHARS = 150       # a split part repeats the last sentence of the previous part if it is this short or shorter
MIN_PART_TEXT_CHARS = 400       # smallest text budget a split part may have, even with a long prefix
SHORT_TEXT_CHARS = 30           # evidence rows with less cleaned text than this are kept but not indexed
CHUNKS_FILE = CHUNKS_DIR / "chunks.jsonl"
CHUNK_REPORT_FILE = CHUNKS_DIR / "chunk_report.json"

# ---- phase 3-4: embedding and vector store ----
COLLECTION_NAME = "sip_evidence"
VECTORDB_MANIFEST = VECTORDB_DIR / "manifest.json"

# ---- phase 5: retrieval logic ----
MAX_QUESTION_CHARS = 1000
MIN_QUESTION_CHARS = 3
TOP_N_SEARCH = 30               # chunks fetched from ChromaDB before ranking
TOP_K_EVIDENCE = 6              # evidence chunks returned
MAX_PER_THREAD = 2              # at most this many chunks from one Reddit thread
MAX_PER_SOURCE = 4              # at most this many of the 6 from one source, when the other source has candidates
MAX_THEME_CONTEXT = 3           # theme-summary chunks returned as context (searched separately from the evidence)
MIN_RESULT_CHARS = 0            # evidence chunks with less displayed text than this are not returned (0 = off); phase 6 tests this
# Evidence gate: the best evidence chunk must be at least this similar to the question. Calibrated in phase 6 (28 Oct 2026):
# 0.38 is the highest threshold that blocked every general or nonsense out-of-scope question and still let 97% of the tuning-half
# in-scope questions through; the holdout gave the same figures. It cannot separate finance questions the data does not cover.
MIN_SIMILARITY = 0.38

GEMINI_MODEL_DEFAULT = "gemini-3.5-flash-lite"     # override with GEMINI_MODEL in .env
GEMINI_MODEL_FALLBACKS = ("gemini-3.1-flash-lite",)  # tried in order if the first model is unavailable (names change over time)
GEMINI_TIMEOUT_MS = 10000
PLAY_STORE_PAGE = "https://play.google.com/store/apps/details?id=com.nextbillion.groww"
EDU_LINKS = {   # domain roots only, to be confirmed by the owner (PRD open question)
    "advice": ("https://www.mutualfundssahihai.com/", "AMFI Mutual Funds Sahi Hai (investor education)"),
    "prediction": ("https://investor.sebi.gov.in/", "SEBI Investor website (investor education)"),
    "returns": ("https://www.amfiindia.com/", "AMFI (links to every fund house's official factsheets)"),
}
EXAMPLE_QUESTIONS = [
    "Why do people pause or stop their SIP?",
    "What do SIP investors check once they have started?",
    "What do people want from the app that is missing?",
]

# ---- answer step (PRD milestone 6): one Gemini call that checks the intent and writes the answer ----
ANSWER_MAX_SENTENCES = 3
ANSWER_MAX_CHARS = 600
SOURCE_CHARS_IN_PROMPT = 800    # each source chunk is cut to this many characters before it goes to Gemini
GEMINI_ANSWER_TIMEOUT_MS = 30000
GEMINI_ANSWER_MAX_TOKENS = 900
GEMINI_ANSWER_ATTEMPTS = 2      # a second try (with the problems listed) if the first answer breaks a rule

# ---- shared constants used by later phases ----
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
