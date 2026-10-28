# PRD: SIP Discovery, a RAG chatbot prototype

Owner: Emil | Status: Draft v1 | Date: 28 Oct 2026
Source of truth for scope: `problemstatement.txt` in this folder. If the two ever disagree, `problemstatement.txt` wins.

## 1. Summary

SIP Discovery is a small chatbot that answers questions about **what real people say about investing in SIPs and mutual funds in India**. It answers only from four data files (Play Store reviews and Reddit discussions about Groww and SIPs), in at most three plain sentences, and always shows one source link. It reports what people say. It never gives investment advice.

It is a prototype built to test RAG (retrieval-augmented generation), and it supports a PM project on lifting 12-month SIP continuation for first-time investors.

## 2. Problem

Qualitative evidence about why people start, pause, reduce or stop SIPs sits in thousands of scattered reviews and forum posts. A PM cannot read it all, and a summary written once goes stale and cannot be asked a follow-up. We want to ask a question in plain language and get a short, sourced answer.

## 3. Goals and non-goals

**Goals**
- Answer SIP / mutual fund questions from the four data files, with a visible source.
- Keep answers short, neutral and checkable (the user can open the sources).
- Refuse advice, prediction and portfolio questions politely, with an educational link.
- Prove the RAG pipeline end to end: load, chunk, embed, store, retrieve, answer.

**Non-goals**
- No investment advice, fund recommendations, return calculations or market predictions.
- No data beyond the four files. No live scraping, no web search.
- No login, user accounts, chat history or analytics in v1.
- Not a production system. No scale, security hardening or SLAs promised.

## 4. Users

| User | Need |
|---|---|
| PM / researcher (primary) | Quick, sourced answers on SIP behaviour to shape product thinking |
| Reviewer or mentor | Try the prototype and see that answers are grounded and safe |

## 5. Corpus (only these four files)

| # | File | What it is | Size |
|---|---|---|---|
| 1 | `data/New Dataset/Playstore/playstore_relevant_reviews.csv` | Groww Play Store reviews (1 to 3 stars) about SIPs / mutual funds | 899 rows |
| 2 | `data/New Dataset/Playstore/playstore_top_issues.csv` | Top 30 issues from those reviews, with counts and example quotes | 30 rows |
| 3 | `data/New Dataset/Reddit/reddit_raw_all.csv` | Reddit posts and comments from 67 SIP-related threads across 14 subreddits (unfiltered, some off-topic rows) | 1,545 rows |
| 4 | `data/New Dataset/Reddit/reddit_top_issues.csv` | Top 30 issues from the Reddit data, with counts and example quotes | 30 rows |

Data notes that shape the product:
- Play Store rows have no per-review link. The source link for these answers goes to the Groww app page on Google Play, and the review text is shown in the expandable section.
- Reddit rows link to the thread.
- Reddit dates are partial: 17 of 67 threads exact, 41 estimated to the month, 9 undated.
- The data is almost entirely English. Reddit usernames were removed.

## 6. User stories

1. As a PM, I ask "Why do people pause or stop their SIP?" and get a short answer with a source.
2. As a PM, I click the source link to read the original reviews or discussion behind the answer.
3. As a user, I ask in Hinglish and still get an English answer.
4. As a reviewer, I ask "Should I stop my SIP?" and get a polite refusal with an educational link, not an opinion.
5. As a user, I ask something the data cannot answer and the bot says so instead of guessing.

## 7. Functional requirements

**FR1. Ask a question.** One text box and a Search button. Questions up to 1,000 characters.

**FR2. Answer from the data first.** The answer is built only from retrieved chunks. It summarises the pattern and does not paste the full text of reviews or posts.

**FR3. Answer format.**
- At most 3 sentences, plain English, neutral tone.
- Ends with "Last updated from sources: <date>", using the latest date in the data files.
- Shows exactly one citation link (the most relevant source): the Reddit thread, or the Groww Play Store page for review-based answers.

**FR4. See the sources.** An expandable "See what people said" section shows the short excerpts the answer came from (source type, date if known, text). Hinglish excerpts are shown as written. This is where the user checks the answer.

**FR5. Hinglish and Hindi questions.** A Hinglish or Hindi question is first rewritten into plain English by Gemini, and that English version is used for search. The answer is always in English.

**FR6. Refusals.** The bot refuses, politely and without lecturing, when asked to:
- recommend, buy, sell, hold or stop anything ("Should I stop my SIP?", "Which fund should I buy?");
- predict the market or returns ("Will the market recover this year?");
- compute or compare returns or performance.
The refusal says the bot is facts-only, and links to an educational page (for example the AMFI "Mutual Funds Sahi Hai" site or the SEBI investor page) or the official factsheet page for performance questions. Exact links to be confirmed in design.

**FR7. Not enough evidence.** If nothing in the data matches well, the bot says it does not have enough evidence and suggests a related question. It does not guess and does not use outside knowledge.

**FR8. Privacy.** If a question contains PAN, Aadhaar, an account number, an OTP, an email or a phone number, the bot declines to process it, does not echo it back, and does not store it.

**FR9. Tiny UI.**
- Welcome line.
- Three example questions the user can click.
- Note: "Facts-only. No investment advice."
- Groww-style colours (Groww green and clean white / dark neutrals), Streamlit.

## 8. How it works (RAG pipeline)

**Ingestion (run once, offline)**
1. Load the four files.
2. Chunk by the structure of the data. One review, one Reddit post or comment, or one issue row is one chunk. Each chunk keeps its metadata (source, subreddit, date, link, issue tags).
3. Embed each chunk with `sentence-transformers/all-MiniLM-L6-v2`.
4. Store vectors and metadata in ChromaDB.

**Answering (per question)**
1. Screen the question (PII, advice, prediction, return queries).
2. If Hinglish or Hindi, rewrite to English with Gemini.
3. Embed the question with the same model and retrieve the most similar chunks from ChromaDB.
4. If the best match is too weak, return "not enough evidence".
5. Otherwise send the question and the retrieved chunks to Gemini with strict instructions: answer only from the chunks, at most 3 sentences, no advice, no numbers that are not in the chunks.
6. Show the answer, one citation link, the date line, and the expandable sources.

LLM: Gemini (API key in a local `.env` file, never committed).

## 9. Quality bar and success metrics

| Metric | Target for the prototype |
|---|---|
| Advice / prediction / return requests refused | 100% on the edge-case test set |
| Answers with exactly one valid citation link | 100% |
| Answers within 3 sentences | 100% |
| Answers whose claims are supported by the retrieved chunks | at least 90% on a hand-checked sample of 30 questions |
| Relevant results in top 5 for the example questions | at least 60% on a small labelled set |
| Hinglish questions: relevant top-5 vs the English equivalent | within 10 points (benchmark: 0.63 English; Hinglish without rewriting was 0.08 to 0.17) |
| Response time | under 8 seconds typical on a laptop |

## 10. Edge cases to test

Advice and prediction (English, Hindi, Hinglish); PII in the question; empty or very long input; off-topic questions (cricket, politics, crypto, stock tips); definitional finance questions ("what is NAV"), which the data may not cover; questions the data cannot answer; a very vague question; questions asking for numbers or return comparisons; prompt-injection attempts ("ignore your rules"); mixed-language questions; repeated identical questions; the Gemini call failing or timing out.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| The bot makes up facts | Answer only from retrieved chunks, show sources, refuse when evidence is weak |
| Reviews or posts are read as advice | Prompt forbids advice; refusal rules; "Facts-only" note |
| Raw Reddit file has off-topic rows | Relevance gate on similarity; "not enough evidence" fallback |
| Play Store answers cannot link to one review | Link to the app page and show the review text in the expandable section |
| Hinglish questions retrieve poorly | Gemini rewrite to English before search |
| Partial Reddit dates make "last updated" imprecise | State the date as "latest date in the data"; accepted by owner |
| Data is a small, hand-picked sample (67 threads, 1 app) | State this in the UI note and in the README; do not claim it represents all investors |
| Gemini free-tier limits or outage | Show a friendly error; retrieval results can still be shown |

## 12. Out of scope for v1

Chat history, follow-up questions that rely on earlier turns, user feedback buttons, other apps (Zerodha, Paytm Money and others), YouTube or Twitter data, analytics, deployment to a public URL.

## 13. Milestones (one step at a time, on the owner's go-ahead)

1. PRD (this document), then architecture.
2. Data loading and chunking.
3. Embedding.
4. Vector store (ChromaDB).
5. Retrieval, screening and the "not enough evidence" gate.
6. Gemini answer step and the Hinglish rewrite.
7. Streamlit UI.
8. Edge-case testing and a short test report.

## 14. Open questions

- Which two educational links to use for refusals (AMFI "Mutual Funds Sahi Hai" and SEBI investor education are the proposal) and which official factsheet link for performance questions.
- Whether to show the similarity score in a developer view for testing.
- Whether to host a public demo after testing (not needed for v1).
