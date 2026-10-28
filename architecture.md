# Architecture: SIP Discovery (RAG chatbot prototype)

Version: 1.0 | Date: 28 Oct 2026 | Based on: `PRD.md` (and `problemstatement.txt`). Nothing outside the PRD is added.

This document covers the six phases the owner asked for: **data loading, chunking, embedding, vector store, retrieval logic, retrieval testing.** The Gemini answer step, the Streamlit UI and the full edge-case test run are later PRD milestones (6 to 8). Here they appear only as the interface the retrieval phase hands over to.

---

## 1. System overview

```
INGESTION (run once, offline)

 4 CSV files ──> [1 Load] ──> [2 Chunk] ──> [3 Embed] ──> [4 Vector store]
  (corpus)        clean,        1 row =       all-MiniLM-    ChromaDB
                  validate      1 chunk       L6-v2          (on disk)

RETRIEVAL (per question)

 Question ──> screen (PII, advice,   ──> [Gemini rewrite   ──> embed ──> search ──> rank, de-dupe ──> evidence ──> result
              prediction, returns)       if Hinglish/Hindi]      (same model)  Chroma   by thread        gate        object
                    │                                                                                                   │
                    └── refuse / decline (no search) ───────────────────────────────────────────────────────────────────┘
                                                                                                                         │
                                       later phases (not in this document): Gemini answer  ──> Streamlit UI <──────────────┘
```

Principles taken from the PRD:
- The corpus is only the four files. No other data, no web search.
- Every result carries enough metadata to show one citation link and the "See what people said" excerpts.
- Facts only. Advice, prediction and return questions never reach the search.
- If the match is weak, say so ("not enough evidence"). Never fall back to outside knowledge.

## 2. Tech stack

| Part | Choice |
|---|---|
| Language | Python 3.11+ |
| Data handling | pandas |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, truncates input beyond 256 word-pieces, about 1,000 characters) |
| Vector store | ChromaDB (persistent, local folder, cosine distance) |
| LLM (query rewrite now, answer later) | Gemini, key in a local `.env` (never committed) |
| UI (later) | Streamlit |

## 3. Folder layout (inside `rag-chatbot-new/`)

Data and code are in separate folders. Nothing generated is ever written into `src/`, and no code lives in `data/`.

```
rag-chatbot-new/
│
├── problemstatement.txt          scope (the PRD wins if they disagree)
├── PRD.md
├── architecture.md               this file
├── requirements.txt              Python packages
├── .env.example                  GEMINI_API_KEY= (copy to .env; .env is never committed)
├── .gitignore                    .env, data/vectordb/, data/embeddings/, __pycache__/
│
├── data/                         ALL data lives here
│   ├── raw/                      the four corpus files, read-only copies (the only input)
│   │   ├── playstore_relevant_reviews.csv
│   │   ├── playstore_top_issues.csv
│   │   ├── reddit_raw_all.csv
│   │   └── reddit_top_issues.csv
│   ├── chunks/                   phase 1-2 output
│   │   ├── load_report.json      rows read / kept / dropped, per file
│   │   ├── chunks.jsonl          one record per chunk, with metadata
│   │   └── chunk_report.json     counts by source, split rows, short rows
│   ├── embeddings/               phase 3 output
│   │   ├── vectors.npy           one 384-number row per indexed chunk
│   │   ├── ids.json              chunk_id for each row of vectors.npy
│   │   └── embedding_meta.json   model name, hash of chunks.jsonl
│   ├── vectordb/                 phase 4 output (ChromaDB on disk)
│   │   ├── chroma files...
│   │   └── manifest.json         record count, model, latest data date
│   └── tests/                    phase 6 material
│       ├── questions/            labelled question sets (relevance, Hinglish, refusal, PII, out-of-scope)
│       ├── judgments/            relevance judgments
│       └── results/              scores and the test report
│
├── src/                          ALL code lives here
│   ├── config.py                 paths, model name, thresholds, refusal links, constants
│   ├── load.py                   phase 1  data loading
│   ├── chunk.py                  phase 2  chunking
│   ├── embed.py                  phase 3  embedding
│   ├── store.py                  phase 4  vector store (build and open)
│   ├── screen.py                 phase 5  PII, advice, prediction and returns screens
│   ├── retrieve.py               phase 5  retrieval logic (command line: python src/retrieve.py "question")
│   ├── generate.py               later (milestone 6)  Gemini answer step
│   └── app.py                    Streamlit UI (built)
│
└── tests/                        test scripts (code only; their data is in data/tests/)
    ├── test_load.py
    ├── test_chunk.py
    ├── test_embed.py
    ├── test_store.py
    └── run_retrieval_eval.py     phase 6  scores retrieval and writes data/tests/results/
```

**Raw data.** `data/raw/` holds read-only copies of the four corpus files (checked identical to the originals under `data/New Dataset/` on 28 Oct 2026). The pipeline reads only from `data/raw/`; the originals stay untouched. If the corpus files change, copy them in again and rebuild phases 1 to 4.

**Rebuild order.** Everything under `chunks/`, `embeddings/` and `vectordb/` is generated, can be deleted at any time, and is rebuilt by running `load.py`, `chunk.py`, `embed.py`, `store.py` in that order.

---

## Phase 1: Data loading

**Purpose.** Read the four files into one clean, validated table, and fail loudly if anything is wrong.

**Input.** The four CSVs, read from `data/raw/`:

| Key | File | Rows | Used as |
|---|---|---|---|
| `ps_reviews` | `data/raw/playstore_relevant_reviews.csv` | 899 | evidence |
| `ps_issues` | `data/raw/playstore_top_issues.csv` | 30 | theme summary |
| `rd_raw` | `data/raw/reddit_raw_all.csv` | 1,545 | evidence |
| `rd_issues` | `data/raw/reddit_top_issues.csv` | 30 | theme summary |

**Process.**
1. Read each file as UTF-8 (the files carry a BOM, so use `utf-8-sig`), keep every value as text.
2. Check the required columns exist for each file (listed in `config.py`). Stop with a clear error if a column is missing.
3. Add `source_file` and `row_number` to every row so each chunk can be traced back to its line.
4. Normalise text: trim whitespace, collapse line breaks into single spaces, remove nothing else (Hinglish and emoji stay as written).
5. Parse dates to `YYYY-MM-DD` or `YYYY-MM`; keep `date_basis` (exact, estimated month, unknown) for Reddit; leave blank when unknown.
6. Remove rows that carry no content: empty text, `[deleted]`, `[removed]`. Count them in the report (expected: 38 in `rd_raw`).
7. Write a load report: rows read, rows kept, rows dropped and why, per file.

**Output.** One in-memory table (and `data/chunks/load_report.json`).

**Done when.**
- Row counts equal the table above (899 / 30 / 1,545 / 30) before step 6.
- Rows kept = rows read minus the dropped empty or deleted rows, and the report says so.
- No username column exists in the loaded data (usernames were removed upstream; the loader asserts it).
- The loader reads only the four files in `data/raw/`.

**As built (28 Oct 2026).** `src/config.py`, `src/load.py`, `tests/test_load.py` (12 checks, all pass). Run: `.venv/bin/python src/load.py`. Result: 2,504 rows read, **2,466 kept, 38 dropped** (Reddit: 1 empty, 37 "[deleted]/[removed]"); all four row counts match. The loader returns one table (union of columns, plus `file_key`, `source_file`, `row_number`, `row_id`, `kind`; issue files get `source` = "Play Store top issue" / "Reddit top issue"). Findings passed to Phase 2 (the loader reports them but does not change the text):
- 180 Reddit rows (9 undated threads) have no date.
- 18 Reddit rows mention another user as `u/name` inside the text (no email, phone or PAN found; the two Aadhaar-pattern hits are false alarms from image-link codes). Chunking should mask `u/name` mentions.
- Some Reddit rows contain image links (for example `preview.redd.it/...`); chunking should strip them from `embed_text`.

---

## Phase 2: Chunking

**Purpose.** Turn each row into a retrievable chunk with metadata. The PRD rule applies: **chunk by the structure of the data, one row = one chunk.**

**What the data looks like (checked on 28 Oct):**
- Play Store reviews: 307 characters median, longest 665. All fit the model window.
- Issue rows: 500 to 730 characters. All fit.
- Reddit rows: median 97 characters, but **451 of 1,545 are under 30 characters** (replies such as "Yes" or "Thanks"), and 78 are over 1,000 characters (longest 2,153), which is more than the model reads.

**Chunk types.**

| Chunk type | Made from | Role in answers |
|---|---|---|
| `Play Store review` | a row of `ps_reviews` | evidence (quotable, cited) |
| `Reddit post`, `Reddit comment` | a row of `rd_raw` | evidence (quotable, cited) |
| `Play Store top issue`, `Reddit top issue` | a row of the issue files | **theme summary**: gives counts and framing, used as supporting context, not as the cited source (they are AI-written summaries of the other files) |

**Chunk record (what is stored for every chunk).**

| Field | Meaning |
|---|---|
| `chunk_id` | stable id, for example `ps_reviews:PS3-0412` or `rd_raw:1p1l3ec-c014` |
| `parent_id` | the original row id (same as `chunk_id` unless the row was split) |
| `part` | `1/1`, or `2/3` for a split row |
| `kind` | `evidence` or `theme_summary` |
| `source` | Play Store review, Reddit post, Reddit comment, Play Store top issue, Reddit top issue |
| `text` | the text shown to the user (for split rows, that part's text) |
| `embed_text` | the text that is embedded (see below) |
| `date`, `date_basis` | as loaded |
| `subreddit`, `thread_id`, `thread_title` | Reddit only |
| `star_rating`, `score` | Play Store stars; Reddit score |
| `issues`, `questions` | issue tags and question tags, when the file has them (the Reddit raw file has none) |
| `source_link` | Reddit thread URL; for Play Store rows, the Groww Play Store page; for issue rows, empty (the answer cites an evidence chunk instead) |
| `is_short` | true when the cleaned text is under 30 characters |

**Rules.**
1. **One row = one chunk** for every row that fits the model window.
2. **Long rows are split** (only the 78 Reddit rows over 1,000 characters): cut at paragraph, then sentence boundaries into parts of at most about 900 characters with a small overlap, each part keeping the same `parent_id`. This is the single departure from "one row = one chunk", and the reason is technical: the embedding model ignores everything past about 1,000 characters, so an unsplit long post would be searchable by its opening only. Results are merged back by `parent_id` at retrieval.
3. **Short Reddit rows (under 30 characters)** are kept in the chunk file with `is_short = true` but are **not embedded or indexed**. A reply such as "Yes" has no meaning on its own and would only add noise. They remain in the data for the record. (This affects about 450 rows and is reported in the chunk report.)
4. **`embed_text` is built per source** so short or context-dependent rows are searchable:
   - Play Store review: `Play Store review, {stars}-star. {summary}. {text}`
   - Reddit post or comment: `Reddit r/{subreddit}. Thread: {thread_title}. {text}` (the thread title gives short replies their context)
   - Issue rows: `{issue}. {what_people_say}. {example_quotes}`
5. No text is rewritten, translated or summarised during chunking. `text` is always the original wording.
6. Chunk ids are deterministic, so a rebuild gives the same ids.

**Output.** `data/chunks/chunks.jsonl` and `chunk_report.json` (counts by source and kind, number split, number short, longest chunk, median length).

**Done when.**
- Every non-dropped input row appears as at least one chunk, and every chunk traces to exactly one source row.
- No indexed chunk's `embed_text` exceeds the model window (about 1,000 characters), with the exceptions listed in the report (none expected).
- Every chunk has a valid `source` and, for evidence chunks, a non-empty `source_link`.
- Two runs produce identical files (same hash).

**As built (28 Oct 2026).** `src/chunk.py`, settings in `src/config.py`, `tests/test_chunk.py` (12 checks). Run: `.venv/bin/python src/chunk.py`. Result: 2,466 rows became **2,589 chunks: 2,168 indexed, 421 short and not indexed.**
- Indexed: 899 Play Store reviews, 1,104 Reddit comments, 105 Reddit post chunks, 30 + 30 theme summaries (2,108 evidence, 60 theme summary).
- **Length is measured in word-pieces with the model's own tokenizer, not in characters.** A first version used a 1,000-character budget and the embedding phase found 20 chunks (number-heavy or symbol-heavy posts) that still ran past the model's 256 word-piece window. The chunker now checks the real count and re-splits until every chunk fits: **77 long Reddit rows were split into 200 parts**, none over the window (longest 255, median 90). Parts are cut at sentence boundaries with a one-sentence overlap. Phase 1 already collapsed line breaks, so paragraph cuts are not possible.
- **22 `u/name` mentions masked** to `u/[user]` in both the displayed text and the embedded text. **21 image links stripped** from the embedded text (including one inside a theme-summary quote). The displayed text keeps image links.
- The short-row count is 421. **280 of them are not real comments**: scraper markers such as "[+3 more replies]" and "> [deleted]". The rest are one-word replies and emoji. All stay in `chunks.jsonl` with `indexed = false`.
- `chunks.jsonl` is deterministic (same SHA-256 on every run; the hash is in `chunk_report.json`).
- **Changed in Phase 6 (28 Oct 2026): Reddit comments are embedded without their thread title** (`Reddit comment in r/{subreddit}. {text}`); the title stays in the metadata. See the Phase 6 note below. After the change: 2,151 indexed chunks (899 Play Store reviews, 1,087 Reddit comments, 105 Reddit post chunks, 30 + 30 theme summaries); 69 long Reddit rows split into 175 parts.
- Additions to the chunk record beyond the table above: `indexed`, `source_file`, `row_number`, `issue_code` and `count` (the review or mention count, theme summaries only).

---

## Phase 3: Embedding

**Purpose.** Convert each indexed chunk into a vector.

**Input.** `chunks.jsonl`, indexed chunks only (not `is_short`).

**Process.**
1. Load `sentence-transformers/all-MiniLM-L6-v2` on CPU. Set the maximum sequence length to 256.
2. Encode every `embed_text` in batches of 32.
3. Normalise vectors to length 1 (so cosine similarity equals a dot product).
4. Save `vectors.npy` (one row per chunk, 384 columns) and `ids.json` (the `chunk_id` for each row, in the same order).
5. Save the model name, vector size and a hash of `chunks.jsonl` next to the vectors, so a stale embedding file is detected.

**Rules.**
- The same model is used later for questions. The model name lives in `config.py` only.
- No query-time or document-time prefixes (this model does not use them).
- Embedding is deterministic, and no API is called.

**Output.** `data/embeddings/vectors.npy`, `ids.json`, `embedding_meta.json`.

**Done when.**
- Vector count equals the number of indexed chunks, each of size 384, all unit length (within rounding).
- No NaN values; no all-zero vectors.
- A sanity check: the nearest neighbours of three known chunks (for example an autopay-failure review) are on the same topic.
- Re-running gives the same vectors.

**As built (28 Oct 2026).** `src/embed.py`, `tests/test_embed.py` (8 checks; 32 pass across the three test files). Run: `.venv/bin/python src/embed.py` (about 35 seconds on a laptop CPU). Result: **2,168 vectors of 384 numbers**, all unit length, no NaN or zero vectors, none of the texts longer than the model window. Two full runs produce byte-identical `vectors.npy`. `embedding_meta.json` records the model, the SHA-256 of `chunks.jsonl` and of `vectors.npy`, and `embed.is_stale()` reports when the vectors no longer match the chunk file. The sanity check is automatic: for four Play Store topics (autopay failure, slow withdrawal, KYC block, debited-but-not-invested) at least 2 of the 5 nearest reviews to a topic review carry the same tag on average, and the question "Why does my SIP autopay keep failing?" returns an autopay or mandate chunk in its top 5. Installed for this phase: `numpy`, `sentence-transformers` (with PyTorch) in `.venv`.

---

## Phase 4: Vector store (ChromaDB)

**Purpose.** Persist the vectors with their metadata so they can be searched later.

**Design.**
- ChromaDB `PersistentClient` in `data/vectordb/`.
- One collection, `sip_evidence`, cosine distance, `embedding_function=None` (we supply our own vectors, so Chroma never embeds anything itself).
- Each record: `id = chunk_id`, `embedding` from phase 3, `document = text`, `metadata` = the chunk record fields that are useful for filtering and display (`source`, `kind`, `parent_id`, `part`, `date`, `date_basis`, `subreddit`, `thread_id`, `thread_title`, `star_rating`, `score`, `issues`, `questions`, `source_link`). Chroma metadata must be simple values, so list fields are stored as a `;`-joined string.
- Telemetry off.

**Process.**
1. Create the collection fresh (delete and rebuild if it exists; rebuilds are always from phase 3 output, never edited by hand).
2. Add the records in batches of 100.
3. Write `manifest.json`: collection name, record count, embedding model, hash of `chunks.jsonl`, date built, latest data date (the date for "Last updated from sources").

**Output.** `data/vectordb/` and `manifest.json`.

**Done when.**
- The collection count equals the number of indexed chunks.
- The store survives a restart: a new process reads the same count and returns the right record for a known id.
- Every record's metadata matches the chunk file (spot check of 50, plus an automatic compare of all ids).
- A test search for a known review's own text returns that review first.
- The latest data date in the manifest matches the newest dated row in the files.

**As built (28 Oct 2026).** `src/store.py`, `tests/test_store.py` (13 checks; 45 pass across the four test files). Run: `.venv/bin/python src/store.py` (builds, then verifies; exit code 0 only if every check passes). Installed for this phase: `chromadb` 1.5.9 in `.venv`. Result: collection `sip_evidence` with **2,168 records** (899 Play Store reviews, 1,104 Reddit comments, 105 Reddit post chunks, 30 + 30 theme summaries), cosine distance, telemetry off, `embedding_function=None`. `manifest.json` records the count, the model, the SHA-256 of the chunk file and the vectors, the counts by source and `latest_item_date`.
- **Latest data date: 2026-10-19** (a Play Store review). It is the newest *exact* date among evidence rows. Estimated Reddit months and the undated rows are ignored, so "Last updated from sources" never shows a guessed date. The test recomputes it from the raw csv files independently.
- Metadata is flat: blank values are left out, numbers (`star_rating`, `score`, `count`, `row_number`) stay numbers, and `issues` and `questions` are `;`-joined strings.
- The build refuses to run if the vectors are stale or the ids do not line up with the chunk file.
- Rebuilding drops the old collection but ChromaDB can leave the old index folder behind. The build now deletes any index folder in `data/vectordb/` that is not registered in the database, and a test checks that only live folders remain (found and fixed during the 28 Oct persistence review).
- Checks that pass: count equals indexed chunks; a brand-new Python process reads the same count and a known record (restart test); every document and key metadata field matches the chunk file, and the full metadata of a 50-record sample; stored vectors equal the saved vectors; a chunk's own vector returns that chunk first (100 sampled, distance below 0.001); a rebuild into a temporary folder reproduces the same records; a test question about autopay failure returns an autopay or mandate chunk with a source link.
- `data/vectordb/` and `data/embeddings/` are in `.gitignore` because they can be rebuilt.

---

## Phase 5: Retrieval logic

**Purpose.** Given a question, return the best evidence or a clear status. This phase produces a **result object**. It does not write the final answer (that is the later Gemini step).

**Steps, in order.**

1. **Validate.** Empty input, whitespace only, or more than 1,000 characters returns `invalid_input`.
2. **PII screen.** Pattern checks for PAN, Aadhaar (12 digits), account-number-like digit runs, OTP wording with digits, email addresses and phone numbers. A hit returns `declined_pii`. The question is not searched, not logged and not echoed in the result.
3. **Advice, prediction and returns screen.** Pattern and keyword rules (English, Hindi, Hinglish) for: buy, sell, hold or stop recommendations ("should I...", "which fund..."), market or return predictions ("will the market..."), and return calculation or comparison. A hit returns `refused_advice` with a facts-only message and an educational link (AMFI "Mutual Funds Sahi Hai" or the SEBI investor page; the official factsheet page for performance questions). Exact links live in `config.py`.
4. **Language handling.** If the question is Hinglish or Hindi (Devanagari script, or Roman-script Hindi words detected by a word list), Gemini rewrites it into plain English. The English version is used for search; the original is kept only for display in the current session. If Gemini fails or the key is missing, search with the original question and mark `rewrite_used = false`.
5. **Embed the question** with the same model as phase 3 (normalised).
6. **Search.** Ask ChromaDB for the top 30 chunks by cosine similarity. Short-row and non-indexed chunks cannot appear.
7. **Rank and tidy.**
   - Merge parts of the same split row (`parent_id`), keep the best part.
   - At most 2 chunks per Reddit thread, so one long thread cannot fill the answer.
   - Keep a mix of sources when scores are close (Play Store and Reddit), so an answer is not one-sided without reason.
   - Evidence chunks fill the result. Up to 2 theme-summary chunks are added as separate context.
   - No re-ranker model and no extra scoring beyond this (keep it simple).
8. **Evidence gate.** If the best evidence chunk's similarity is below the threshold, return `not_enough_evidence` with a related-question hint. The threshold is set in phase 6 from labelled examples, not guessed. If the question is about SIPs but not in the data, it falls here.
9. **Choose the citation.** The single link comes from the top evidence chunk: the Reddit thread URL, or the Groww Play Store page for a Play Store chunk. If the top chunk is a theme summary, the citation is taken from the best evidence chunk.
10. **Build the result object.**

```
status:            ok | refused_advice | declined_pii | not_enough_evidence | invalid_input
message:           text for non-ok statuses (polite, facts-only)
link:              educational link (refusals) or null
question_english:  the English search text (null for PII)
chunks:            up to 6 evidence chunks, best first
                   (id, source, date, text, similarity, source_link, issues)
theme_context:     up to 2 theme-summary chunks (issue, counts)
citation:          one source link (the top evidence chunk)
last_updated:      latest date in the data (from manifest.json)
rewrite_used:      true | false
```

**Rules.**
- Nothing outside the four files ever enters the result.
- PII and advice screens run before any model or search call.
- The evidence gate is applied before anything is handed to the answer step.
- Retrieval never calls Gemini for anything except the rewrite in step 4.

**Done when.** All five statuses are reachable, a normal question returns evidence with a valid citation, and the result object matches the structure above (checked by phase 6).

**As built (28 Oct 2026).** `src/screen.py`, `src/retrieve.py`, retrieval settings in `src/config.py`, `tests/test_screen.py` and `tests/test_retrieve.py` (79 checks; 125 pass across the whole project). Installed for this phase: `google-genai`, `python-dotenv`. Backend only, no UI and no answer text. Run: `.venv/bin/python src/retrieve.py "your question"` (add `--json` for the full result object).
- All ten steps are implemented as specified. All five statuses are reachable (`ok`, `refused_advice`, `declined_pii`, `not_enough_evidence`, `invalid_input`). Python callers use `retrieve.retrieve(question)`.
- **Screens** run before any model or search call. The PII screen covers email, phone (also written with a space), PAN, Aadhaar, long account or card numbers and OTPs, and never echoes the value. The advice screen refuses buy/sell/hold/stop requests, market predictions and return calculations in English, Hinglish and Hindi, and allows questions about what people say ("Why do people stop their SIP?"). It was checked against 20 refusals and 16 safe questions; one false alarm found during the build ("how do people decide which fund to pick") was fixed.
- **Hinglish/Hindi:** detected by Devanagari script or two or more common Hindi words. Gemini rewrites the question into English. Default model `gemini-3.5-flash-lite` (about 1.5 seconds per call), with `gemini-3.1-flash-lite` as a fallback; set `GEMINI_MODEL` in `.env` to override. The first guess, `gemini-2.5-flash`, turned out to be retired for this key (404), so the code tries models in order and the model used is recorded in `rewrite_note`. **Checked on 28 Oct with the owner's existing key** (copied from the old project's `.env` into `rag-chatbot-new/.env`, mode 600, git-ignored): five Hinglish questions were rewritten correctly and retrieved on-topic Play Store reviews and Reddit threads. The rewrite is screened again for PII and advice. If the key is missing or the call fails, the original question is searched and `rewrite_note` says why.
- **Ranking:** top 30 by cosine similarity; split parts of one row are merged; at most 2 chunks per Reddit thread; at most 4 of the 6 from one source when the other source has candidates (a short list of one source still fills all 6); up to 2 theme summaries returned separately as context; no re-ranker.
- **Evidence gate: provisional 0.38** (`MIN_SIMILARITY` in `config.py`). On a first look, in-scope questions scored 0.40 to 0.85 and unrelated ones (cricket, weather, cooking) 0.14 to 0.39. **Known limit:** general finance questions that are not about SIP behaviour ("how does compound interest work" 0.65, "how to open a demat account" 0.67) score like in-scope ones, so the gate cannot block them. The answer step must say "not enough evidence" when the retrieved chunks do not answer the question. Phase 6 calibrates the threshold properly.
- **Observed quality (smoke test, not the formal evaluation):** questions about app problems that Play Store reviews describe (autopay or mandate failure, support, withdrawals) return on-topic reviews. Broad behaviour questions ("why do people start a SIP") return Reddit replies that are only loosely related, often short context-dependent comments, because the thread title in each Reddit chunk's embedded text makes every reply in a SIP-titled thread look similar to a generic SIP question. Phase 6 measures this and decides whether to tune it (for example a minimum length for result chunks, or a lighter thread-title prefix).

---

## Phase 6: Retrieval testing

**Purpose.** Prove that retrieval meets the PRD bar before the answer step and UI are built. This phase tests retrieval only. The full edge-case run on the finished chatbot is PRD milestone 8.

**Test sets** (stored in `data/tests/`):

| Set | Contents | Size |
|---|---|---|
| Relevance set | Questions covering the five example questions in the PRD and paraphrases, plus questions on autopay, support, redemption, step-up, fund choice, checking habits, jargon, taxes. For each, the chunks judged relevant. | about 40 questions |
| Hinglish set | The same topics asked in Hinglish and mixed language (reusing the 40 pairs from the embedding benchmark) | about 40 questions |
| Refusal set | Advice, prediction and return-comparison questions in English, Hindi and Hinglish, plus lookalike safe questions that must NOT be refused | about 40 questions |
| PII set | Questions containing PAN, Aadhaar, account numbers, OTPs, emails and phone numbers (synthetic values), plus safe lookalikes | about 20 questions |
| Out-of-scope set | Cricket, politics, crypto, stock tips, general finance definitions, nonsense | about 25 questions |

**Method.**
1. Split the relevance questions into a **tuning half** (used to set the evidence threshold and ranking rules) and a **holdout half** (never used for tuning, reported separately).
2. Relevance of the top results is judged against a written rubric (2 = directly answers, 1 = partly, 0 = not) by reviewers independent of the person who built the ranking. The owner spot-checks a sample, because AI reviewers are not human.
3. Report: precision at 5 (strict: only score 2; lenient: score 1 or 2), hit at 3, split by source and by question type; Hinglish versus English.
4. Calibrate the evidence threshold on the tuning half: choose the value that lets in the in-scope questions and blocks the out-of-scope set. Report the ones that still slip through.
5. Check structure: every `ok` result has one valid citation link, no more than 2 chunks per thread, no PII echoed, `last_updated` present.

**Acceptance (from the PRD).**

| Check | Target |
|---|---|
| Advice, prediction and return requests refused | 100% of the refusal set; 0 lookalike safe questions refused |
| PII questions declined and not echoed | 100% of the PII set |
| Relevant results in top 5 on the holdout half | at least 60% (lenient) |
| Hinglish versus English | within 10 points |
| `ok` results with exactly one valid citation | 100% |
| Out-of-scope questions blocked by the gate | reported honestly; the ones that pass are listed, with the reason |
| Response time of retrieval (excluding Gemini) | under 2 seconds typical |

**Output.** `data/tests/` (question sets, judgments, results) and a short test report: what passed, what failed, what was tuned, and known weak spots. Failures are reported, not hidden.

**Done when.** The report is written and every acceptance row is either met or listed with its gap and a decision from the owner.

**As built (28 Oct 2026).** Full report: `data/tests/results/test_report.md`. Scripts in `tests/`: `build_test_sets.py`, `run_retrieval_eval.py`, `score_retrieval_eval.py`, `experiment_variants.py`, `experiment_llm_screen.py`. Test sets in `data/tests/questions/` (40 English, 40 Hinglish, 88 refusal in three rounds, 20 PII, 25 out-of-scope); 619 question-chunk pairs judged blind by AI reviewers (87% exact agreement with a second reviewer on 60 pairs); 30 pairs for the owner to check in `owner_spot_check.csv`.
- **Met:** holdout relevance (English 79%, Hinglish 84% at least partly relevant, target 60%); Hinglish within 10 points of English; one valid citation in 80 of 80 results; retrieval 0.011 s median (Gemini rewrite adds about 2 s for Hinglish); personal details 20 of 20 declined without echo.
- **Not met:** (1) advice, prediction and return refusals: the pattern rules caught only 7 of 16 on a fresh unseen set (and 19 of 28 on the first run). A Gemini intent check caught 58 of 60 with no false refusals in an experiment; not wired in, **owner decision** (it would send every English question to Gemini). (2) Out-of-scope: all 12 general or nonsense questions are blocked at the 0.38 gate, but 11 of 13 finance questions the data does not cover pass, which the threshold cannot fix.
- **Gate:** 0.38 confirmed (97% of dev and 100% of holdout in-scope questions pass; all general out-of-scope blocked).
- **Tuning change adopted:** Reddit comments embedded without the thread title. Tuning-half "at least partly relevant" 64% to 74.5%; holdout 62% to 79% (English) and 64% to 84% (Hinglish). Strict (directly answers) is still modest: 35% English, 50% Hinglish on the holdout; Play Store results are strong (77% direct), Reddit results weaker (21% direct).

**Answer step (PRD milestone 6), built 28 Oct 2026.** `src/generate.py`, `tests/test_generate.py` (15 checks; 142 pass across the project), evaluation in `tests/run_answer_eval.py`. Run: `.venv/bin/python src/generate.py "your question"` (add `--json` for the full object). Flow: the quick rules run first (invalid input, personal details, advice patterns, evidence gate; none of these reach Gemini) and then **one Gemini call** decides whether the question asks for advice, a prediction or a return calculation (it refuses on any doubt) or whether the sources do not answer it, and otherwise writes the answer. The answer is then checked by code: at most 3 sentences, no links, no advice wording, no number that is not in the sources; one retry with the problems listed; if it still fails, or Gemini is down, the sources are shown without an answer (`answer_unavailable`). The single citation is the link of the best-ranked source the answer used; the date line comes from the data. Hinglish questions use two Gemini calls (rewrite, then answer). Statuses: `answered`, `refused_advice` (with `guard` = rules or llm), `declined_pii`, `invalid_input`, `not_enough_evidence`, `answer_unavailable`.
- **Results:** refusal sets 60 of 60 refused (rules 52, Gemini 8), 1 of 28 safe lookalikes wrongly refused (1 to 2 across runs); 0 of 80 legitimate questions refused, 75 answered; 65 sentences judged: 82% fully supported, 18% partly, 0% unsupported. Details in `data/tests/results/test_report.md`, section 9.
- **Changes made to earlier phases while building it:** (1) theme summaries are embedded by title and description only (not their example quotes) and searched separately from the evidence (up to 3 returned as context), because otherwise they almost never reached the answer step; evidence ranking is unchanged. (2) The Hinglish rewrite prompt keeps the "what do people say" framing and never turns a question into "what should people do". (3) The advice rule "which fund is best" now fires only at the start of a question.
- The vector store was rebuilt for (1): still 2,151 indexed chunks.

---

## 4. What the retrieval phase hands to the later phases

- To the **Gemini answer step** (PRD milestone 6): the result object above. That step may use only the `chunks` and `theme_context` it is given, write at most 3 sentences with no advice, and add the single `citation` and the `last_updated` line.
- To the **Streamlit UI** (milestone 7): the status, message, link, the one citation, and the chunk excerpts for the "See what people said" section (Hinglish text shown as written).

## 5. Risks specific to this design

| Risk | Handling |
|---|---|
| Many Reddit rows are off-topic or very short | Short rows are not indexed; the evidence gate blocks weak matches |
| Raw Reddit rows have no issue tags | Their `embed_text` includes the thread title; the issue files add theme context |
| Issue files are AI-written summaries | They are used only as context, never as the cited source |
| Play Store has no per-review link | The citation goes to the Groww Play Store page, and the review text appears in the expandable section |
| Hinglish questions retrieve poorly with this model | Gemini rewrite before search; tested in phase 6 |
| Stale vectors after a data change | Hash check between chunks, embeddings and the store |
| Threshold set by guesswork | Calibrated on a tuning set and reported on a holdout set in phase 6 |

## 6. Build order and sign-off

Phases are built one at a time, in order, and each is signed off by the owner before the next starts: **1 load, 2 chunk, 3 embed, 4 store, 5 retrieval logic, 6 retrieval testing.** Each phase has its own "done when" checks above.

### UI (PRD milestone 7) — as built (28 Oct 2026)

`src/app.py` (Streamlit), theme in `.streamlit/config.toml` (Groww green `#00B386`, white and dark neutral). Run: `.venv/bin/streamlit run src/app.py` (add `--server.port N` if 8501 is taken). The page calls `generate.answer()` and shows only its result: welcome line, the note "Facts-only. No investment advice.", three clickable example questions (from `config.EXAMPLE_QUESTIONS`), a question box, the short answer, ONE citation link, the "Last updated from sources" line and an expandable "See what people said" list (Hinglish rows shown as written). Refusals show the polite message and the educational link; "not enough evidence" suggests the example questions; a question with personal details is declined and never shown back. Nothing is stored. The Retriever (model and collection) loads once per server via `st.cache_resource`. Checked with Streamlit's `AppTest` (answer, advice refusal, PAN decline with no echo, example-button click) and in the browser.
