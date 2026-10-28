# SIP Discovery (NL_discoveryengine_SIP)

A prototype RAG chatbot that answers one kind of question: **what do real people say about starting, pausing or stopping a SIP?**
Answers come only from public Groww Play Store reviews and Reddit posts about SIPs and mutual funds.

- Short answer (3 sentences at most), **one** citation link, a "Last updated from sources" line, and an expandable "See what people said" list.
- **Facts-only. No investment advice.** Buy/sell, prediction and returns questions get a polite refusal. Personal details (PAN, Aadhaar, phone, email, OTP) are declined and never echoed.
- Hinglish/Hindi questions are rewritten to English by Gemini before search. Answers are always English.

## How it works
`load -> chunk -> embed (all-MiniLM-L6-v2) -> ChromaDB -> retrieve -> Gemini answer -> Streamlit UI`

See [PRD.md](PRD.md), [architecture.md](architecture.md) and [problemstatement.txt](problemstatement.txt). Test results: [data/tests/results/test_report.md](data/tests/results/test_report.md).

## Run it
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then paste your GEMINI_API_KEY
# put the four source CSVs in data/raw/ (see problemstatement.txt), then:
python src/load.py && python src/chunk.py && python src/embed.py && python src/store.py
streamlit run src/app.py
python -m pytest
```

## About the data
The dataset is a small, hand-picked sample (Groww Play Store reviews rated 1-3 stars, plus 27 Reddit threads), so it does not represent all investors.
The raw reviews and posts were written by other people and are **not redistributed** in this repository; `data/raw/` and `data/chunks/` are git-ignored.
To rebuild, collect your own copy of the four files listed in `problemstatement.txt`.

## License
MIT for the code (see [LICENSE](LICENSE)). The license does not cover the third-party review and Reddit text.
