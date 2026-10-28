"""Phase 5: retrieval logic (backend only; no answer is written here).

Given a question, return the best evidence from the vector store, or a clear status:
    ok | refused_advice | declined_pii | not_enough_evidence | invalid_input

Steps (architecture.md, Phase 5): validate -> PII screen -> advice/prediction/returns screen -> Hinglish/Hindi rewrite
to English (Gemini) -> embed -> search -> rank and tidy -> evidence gate -> pick one citation -> result object.

    python src/retrieve.py "Why do people stop their SIP?"
    python src/retrieve.py "SIP kyun band karte hain log?" --json
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import screen  # noqa: E402

HINGLISH_WORDS = {
    "kya", "kyun", "kyu", "kaise", "kaisa", "kab", "kahan", "kaun", "konsa", "kaunsa", "hai", "hain", "nahi", "nhi", "karna",
    "karte", "karta", "karti", "kar", "karun", "karu", "mein", "mai", "mujhe", "mera", "meri", "mere", "tum", "aap", "log",
    "logon", "paisa", "paise", "band", "bandh", "chalu", "jari", "rok", "ka", "ki", "ke", "ko", "se", "par", "toh", "aur",
    "ya", "lekin", "bhi", "raha", "rahi", "rahe", "hota", "hoti", "hote", "wala", "wali", "kuch", "sab", "bahut", "zyada",
    "kam", "pehle", "baad", "abhi", "sahi", "galat", "chahiye", "milta", "milte", "mila", "diya", "liya", "kiya", "gaya",
    "gayi", "lagta", "dikhta", "batao", "samajh", "tarah", "wajah", "isliye", "kyunki", "agar", "jab", "tab",
}
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


# ---------------------------------------------------------------- language handling (step 4)
def needs_rewrite(question: str) -> bool:
    """True for Hindi (Devanagari) or Roman-script Hindi (Hinglish): two or more common Hindi words."""
    if DEVANAGARI.search(question):
        return True
    words = re.findall(r"[a-z]+", question.lower())
    return sum(w in HINGLISH_WORDS for w in words) >= 2


def _gemini_key():
    try:
        from dotenv import load_dotenv
        load_dotenv(C.ROOT / ".env")
    except ImportError:
        pass
    return os.environ.get("GEMINI_API_KEY", "").strip()


def rewrite_to_english(question: str):
    """Ask Gemini to rewrite a Hindi/Hinglish question as a plain English question. Returns (text or None, note).
    The model output is treated as untrusted text: one short line, and it is screened again by the caller."""
    key = _gemini_key()
    if not key:
        return None, "unavailable: GEMINI_API_KEY is not set in .env"
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None, "unavailable: google-genai is not installed"
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=C.GEMINI_TIMEOUT_MS))
    prompt = ("Rewrite the user's question below as one plain English question. Keep its meaning and its framing: if the user asks "
              "what people say, think, report or experience, the English question must also ask what people say, think, report or "
              "experience (for example 'What do people say about ...?'). Never turn it into a question about what someone should do. "
              "Do not answer it. Do not add anything. Output only the English question.\n\nQuestion: " + question)
    models = [os.environ.get("GEMINI_MODEL") or C.GEMINI_MODEL_DEFAULT, *C.GEMINI_MODEL_FALLBACKS]
    last = "no model tried"
    for model in dict.fromkeys(models):                 # first working model wins
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt, config=types.GenerateContentConfig(temperature=0, max_output_tokens=300))
            text = re.sub(r"\s+", " ", (resp.text or "")).strip().strip('"')
            if text and len(text) <= 300:
                return text, f"used ({model})"
            last = "empty or overlong rewrite"
        except Exception as e:  # network, quota, bad key, model gone: try the next model, else fall back
            last = type(e).__name__
    return None, f"failed: {last}"


# ---------------------------------------------------------------- search (steps 5-6)
class Retriever:
    """Loads the embedding model and the stored collection once, then answers searches."""

    def __init__(self):
        self._model = None
        self._col = None
        self._manifest = None

    def _ready(self):
        if self._model is None:
            import embed
            import store
            self._model = embed.load_model()
            self._col = store.open_collection()
            self._manifest = json.loads(C.VECTORDB_MANIFEST.read_text(encoding="utf-8"))

    @property
    def last_updated(self) -> str:
        self._ready()
        return self._manifest["latest_item_date"]

    def search(self, text: str, n: int = C.TOP_N_SEARCH):
        """Top-n chunks by cosine similarity (1 - cosine distance), best first."""
        self._ready()
        import embed
        q = embed.embed_texts(self._model, [text])[0]
        r = self._col.query(query_embeddings=[q.tolist()], n_results=n, include=["documents", "metadatas", "distances"])
        hits = []
        for cid, doc, md, dist in zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0]):
            hits.append({"id": cid, "text": doc, "similarity": round(1.0 - float(dist), 4), **md})
        return hits


    def search_themes(self, text: str, n: int = 6):
        """Theme summaries (analyst-written, dataset-wide patterns) most similar to the question, searched on their own so that
        they are not crowded out by the many evidence chunks."""
        self._ready()
        import embed
        q = embed.embed_texts(self._model, [text])[0]
        r = self._col.query(query_embeddings=[q.tolist()], n_results=n, where={"kind": "theme_summary"},
                            include=["documents", "metadatas", "distances"])
        return [{"id": cid, "text": doc, "similarity": round(1.0 - float(dist), 4), **md}
                for cid, doc, md, dist in zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0])]


_DEFAULT = None


def get_retriever() -> Retriever:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Retriever()
    return _DEFAULT


# ---------------------------------------------------------------- ranking (step 7)
def rank_hits(hits, top_k: int = C.TOP_K_EVIDENCE):
    """Return (evidence, theme_context) from the raw search hits."""
    evidence = [h for h in hits if h["kind"] == "evidence" and len(h["text"]) >= C.MIN_RESULT_CHARS]
    themes = [h for h in hits if h["kind"] == "theme_summary"]

    best_by_parent = {}                       # split parts of one row: keep only the best part
    for h in evidence:                        # hits are sorted best first
        best_by_parent.setdefault(h["parent_id"], h)
    ordered = list(best_by_parent.values())

    chosen, per_thread, per_source = [], {}, {}
    sources_present = {h["source"].split()[0] for h in ordered}          # "Play Store" vs "Reddit"
    for h in ordered:
        fam = h["source"].split()[0]
        tid = h.get("thread_id", "")
        if tid and per_thread.get(tid, 0) >= C.MAX_PER_THREAD:
            continue
        if len(sources_present) > 1 and per_source.get(fam, 0) >= C.MAX_PER_SOURCE:
            continue
        chosen.append(h)
        per_thread[tid] = per_thread.get(tid, 0) + 1
        per_source[fam] = per_source.get(fam, 0) + 1
        if len(chosen) == top_k:
            break
    if len(chosen) < top_k:                   # not enough after the source cap: fill from the rest
        for h in ordered:
            if h not in chosen and (not h.get("thread_id") or per_thread.get(h["thread_id"], 0) < C.MAX_PER_THREAD):
                chosen.append(h)
                per_thread[h.get("thread_id", "")] = per_thread.get(h.get("thread_id", ""), 0) + 1
                if len(chosen) == top_k:
                    break
    chosen.sort(key=lambda h: -h["similarity"])
    return chosen, themes[:C.MAX_THEME_CONTEXT]


# ---------------------------------------------------------------- result object (steps 8-10)
def _chunk_out(h):
    keep = ("source", "date", "date_basis", "subreddit", "thread_id", "thread_title", "star_rating", "score",
            "issues", "source_link", "part")
    return {"id": h["id"], "text": h["text"], "similarity": h["similarity"], **{k: h[k] for k in keep if k in h}}


def _base(status, retriever_last_updated=None):
    return {"status": status, "message": None, "link": None, "link_label": None, "question_english": None,
            "chunks": [], "theme_context": [], "citation": None, "citation_label": None,
            "last_updated": retriever_last_updated, "rewrite_used": False, "rewrite_note": "not needed",
            "best_similarity": None, "threshold": C.MIN_SIMILARITY}


def _last_updated():
    try:
        return json.loads(C.VECTORDB_MANIFEST.read_text(encoding="utf-8"))["latest_item_date"]
    except (OSError, KeyError, ValueError):
        return None


REFUSAL_TEXT = {
    "advice": "I only report what people say about SIPs and mutual funds, so I can't tell you what to buy, sell, "
              "stop or continue. For neutral guidance, please use the investor education link below.",
    "prediction": "I can't predict markets or returns. I only report what people have said. "
                  "For neutral guidance, please use the investor education link below.",
    "returns": "I don't calculate or compare returns. For a fund's performance, please see its official factsheet "
               "(link below).",
}
PII_TEXT = ("I can't process personal details such as PAN, Aadhaar, account numbers, OTPs, emails or phone numbers. "
            "Please remove them and ask again.")
INVALID_TEXT = f"Please type a question (between {C.MIN_QUESTION_CHARS} and {C.MAX_QUESTION_CHARS} characters)."
NO_EVIDENCE_TEXT = ("I don't have enough evidence in the data to answer that. I can answer questions about why people "
                    "start, pause or stop SIPs, what they check, what confuses them and what they want from the app.")


def _refusal(kind):
    link, label = C.EDU_LINKS[kind]
    r = _base("refused_advice", _last_updated())
    r.update(message=REFUSAL_TEXT[kind], link=link, link_label=label, refusal_type=kind)
    return r


def retrieve(question, retriever=None, rewrite_fn=None, top_k: int = C.TOP_K_EVIDENCE):
    """Run the full retrieval pipeline for one question and return the result object (a dict)."""
    q = question.strip() if isinstance(question, str) else ""
    # 1. validate
    if len(q) < C.MIN_QUESTION_CHARS or len(q) > C.MAX_QUESTION_CHARS or not re.search(r"\w", q):
        r = _base("invalid_input", _last_updated())
        r["message"] = INVALID_TEXT
        return r
    # 2. personal details: never searched, logged or echoed
    if screen.screen_pii(q):
        r = _base("declined_pii", _last_updated())
        r["message"] = PII_TEXT
        return r
    # 3. advice / prediction / returns
    kind = screen.screen_advice(q)
    if kind:
        return _refusal(kind)
    # 4. Hinglish / Hindi -> English (Gemini); the rewrite is screened again because it is model output
    search_text, used, note = q, False, "not needed"
    if needs_rewrite(q):
        english, note = (rewrite_fn or rewrite_to_english)(q)
        if english:
            if screen.screen_pii(english):
                r = _base("declined_pii", _last_updated())
                r["message"] = PII_TEXT
                return r
            kind = screen.screen_advice(english)
            if kind:
                return _refusal(kind)
            search_text, used = english, True
    # 5-6. embed and search
    retriever = retriever or get_retriever()
    hits = retriever.search(search_text)
    # 7. rank and tidy
    evidence, themes = rank_hits(hits, top_k)
    r = _base("ok", retriever.last_updated)
    r.update(question_english=search_text, rewrite_used=used, rewrite_note=note)
    # 8. evidence gate
    best = evidence[0]["similarity"] if evidence else None
    r["best_similarity"] = best
    if best is None or best < C.MIN_SIMILARITY:
        r.update(status="not_enough_evidence", message=NO_EVIDENCE_TEXT)
        r["related_questions"] = C.EXAMPLE_QUESTIONS
        return r
    # 9-10. citation = the top evidence chunk's link
    top = evidence[0]
    r["chunks"] = [_chunk_out(h) for h in evidence]
    themes = retriever.search_themes(search_text)
    r["theme_context"] = [{"id": h["id"], "issue_code": h.get("issue_code", ""), "count": h.get("count"),
                           "text": h["text"], "similarity": h["similarity"], "source": h["source"]}
                          for h in themes if h["similarity"] >= C.MIN_SIMILARITY][:C.MAX_THEME_CONTEXT]
    r["citation"] = top["source_link"]
    r["citation_label"] = (f"Reddit thread in r/{top['subreddit']}" if top["source"].startswith("Reddit")
                           else "Groww on Google Play (Play Store reviews)")
    return r


# ---------------------------------------------------------------- command line
def _print(r, show: int):
    print(f"status: {r['status']}")
    if r["status"] == "ok":
        print(f"searched as: {r['question_english']}  (rewrite: {r['rewrite_note']})")
        print(f"best similarity {r['best_similarity']} (gate {r['threshold']}) | last updated {r['last_updated']}")
        print(f"citation: {r['citation']}  [{r['citation_label']}]")
        for i, c in enumerate(r["chunks"], 1):
            when = c.get("date") or "undated"
            where = f"r/{c['subreddit']}" if c.get("subreddit") else f"{c.get('star_rating', '?')}-star review"
            print(f"\n{i}. [{c['similarity']}] {c['id']}  ({where}, {when})")
            print("   " + c["text"][:show].replace("\n", " ") + ("..." if len(c["text"]) > show else ""))
        for t in r["theme_context"]:
            print(f"\n   theme context: [{t['similarity']}] {t['text'][:show]}  (count {t['count']})")
    else:
        print(r["message"])
        if r.get("link"):
            print(f"link: {r['link']}  [{r['link_label']}]")
        if r["status"] == "not_enough_evidence":
            print(f"(best similarity {r['best_similarity']}, gate {r['threshold']})")


def main():
    ap = argparse.ArgumentParser(description="Search the SIP evidence store.")
    ap.add_argument("question")
    ap.add_argument("--json", action="store_true", help="print the full result object as JSON")
    ap.add_argument("--show", type=int, default=260, help="characters of each chunk to print")
    a = ap.parse_args()
    r = retrieve(a.question)
    print(json.dumps(r, indent=2, ensure_ascii=False)) if a.json else _print(r, a.show)


if __name__ == "__main__":
    main()
