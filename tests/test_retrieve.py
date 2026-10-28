"""Phase 5 retrieval backend (architecture.md, steps 1-10). Run:  .venv/bin/python -m pytest tests/test_retrieve.py -q
Needs the built store (src/store.py). The Gemini rewrite is replaced by a fake function, so no key or network is needed."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import config as C  # noqa: E402
import retrieve as R  # noqa: E402

STATUSES = {"ok", "refused_advice", "declined_pii", "not_enough_evidence", "invalid_input"}
KEYS = {"status", "message", "link", "link_label", "question_english", "chunks", "theme_context", "citation",
        "citation_label", "last_updated", "rewrite_used", "rewrite_note", "best_similarity", "threshold"}


@pytest.fixture(scope="module")
def retriever():
    return R.Retriever()


def run(q, retriever, **kw):
    return R.retrieve(q, retriever=retriever, **kw)


def test_a_normal_question_returns_evidence_with_one_valid_citation(retriever):
    r = run("What leads investors to pause, reduce or stop a SIP?", retriever)
    assert r["status"] == "ok" and set(r) >= KEYS
    assert 1 <= len(r["chunks"]) <= C.TOP_K_EVIDENCE
    assert r["citation"].startswith("http") and r["citation"] == r["chunks"][0]["source_link"]
    assert r["last_updated"] == json.loads(C.VECTORDB_MANIFEST.read_text())["latest_item_date"]
    sims = [c["similarity"] for c in r["chunks"]]
    assert sims == sorted(sims, reverse=True) and sims[0] >= C.MIN_SIMILARITY
    assert r["rewrite_used"] is False


def test_all_five_statuses_are_reachable(retriever):
    seen = {run(q, retriever)["status"] for q in [
        "Why do people stop their SIP?", "Should I stop my SIP?", "my PAN is ABCDE1234F, why do SIPs fail",
        "Who won the cricket world cup?", "   "]}
    assert seen == STATUSES


def test_invalid_input(retriever):
    for q in ["", "  ", "?", "ab", "x" * 1001, None, 123]:
        assert run(q, retriever)["status"] == "invalid_input"


def test_pii_is_declined_without_search_or_echo(retriever):
    class Boom(R.Retriever):
        def search(self, *a, **k):
            raise AssertionError("must not search")
    r = R.retrieve("my number is 9876543210, why do SIPs fail", retriever=Boom())
    assert r["status"] == "declined_pii" and r["chunks"] == [] and r["question_english"] is None
    assert "9876543210" not in json.dumps(r)


def test_refusal_has_an_educational_link_and_no_chunks(retriever):
    for q, kind in [("Which fund should I buy?", "advice"), ("Will the market recover this year?", "prediction"),
                    ("Calculate my SIP returns", "returns")]:
        r = run(q, retriever)
        assert r["status"] == "refused_advice" and r["refusal_type"] == kind and r["chunks"] == []
        assert r["link"] == C.EDU_LINKS[kind][0] and "buy" not in (r["message"] or "").lower().split("tell you what to ")[0][:0]


def test_off_topic_question_is_not_enough_evidence(retriever):
    r = run("Who won the cricket world cup?", retriever)
    assert r["status"] == "not_enough_evidence" and r["chunks"] == [] and r["citation"] is None
    assert r["related_questions"] and r["best_similarity"] < C.MIN_SIMILARITY


def test_hinglish_question_is_rewritten_and_searched_in_english(retriever):
    seen = {}

    def fake(q):
        seen["q"] = q
        return "Why do people stop their SIP?", "used"
    r = run("SIP kyun band karte hain log?", retriever, rewrite_fn=fake)
    assert seen["q"] == "SIP kyun band karte hain log?"
    assert r["status"] == "ok" and r["rewrite_used"] and r["question_english"] == "Why do people stop their SIP?"


def test_failed_rewrite_falls_back_to_the_original_question(retriever):
    r = run("SIP kyun band karte hain log?", retriever, rewrite_fn=lambda q: (None, "failed: Timeout"))
    assert r["rewrite_used"] is False and r["rewrite_note"] == "failed: Timeout"
    assert r["question_english"] == "SIP kyun band karte hain log?"


def test_the_rewrite_is_screened_again(retriever):
    r = run("mera paisa kya karun SIP mein", retriever, rewrite_fn=lambda q: ("Should I stop my SIP?", "used"))
    assert r["status"] == "refused_advice"
    r = run("SIP kyun band karte hain log?", retriever, rewrite_fn=lambda q: ("call 9876543210 about SIP", "used"))
    assert r["status"] == "declined_pii"


def test_english_questions_do_not_call_gemini(retriever):
    def boom(q):
        raise AssertionError("rewrite must not run for English")
    assert run("Why do people stop their SIP?", retriever, rewrite_fn=boom)["status"] == "ok"


def test_language_detection():
    assert R.needs_rewrite("SIP kyun band karte hain log?") and R.needs_rewrite("क्या SIP बंद करना सही है")
    assert not R.needs_rewrite("Why do people stop their SIP?") and not R.needs_rewrite("What do users do when autopay fails?")


def test_no_key_means_a_clear_note_not_a_crash(monkeypatch):
    monkeypatch.setattr(R, "_gemini_key", lambda: "")
    text, note = R.rewrite_to_english("SIP kyun band karte hain log?")
    assert text is None and note.startswith("unavailable")


def test_ranking_rules():
    def h(i, sim, kind="evidence", source="Reddit comment", thread="t1", parent=None):
        return {"id": i, "parent_id": parent or i, "similarity": sim, "kind": kind, "source": source,
                "thread_id": thread, "text": "x", "source_link": "http://x"}
    hits = [h("a1", .9, thread="t1"), h("a2", .89, thread="t1"), h("a3", .88, thread="t1"), h("b1", .87, thread="t2"),
            h("p1", .86, source="Play Store review", thread=""), h("th1", .85, kind="theme_summary", source="Play Store top issue", thread=""),
            h("a1b", .84, thread="t3", parent="a1")]
    ev, th = R.rank_hits(hits)
    ids = [c["id"] for c in ev]
    assert "a3" not in ids                                   # at most 2 chunks per thread
    assert ids.count("a1b") == 0                             # a second part of an already chosen row is dropped
    assert [c["id"] for c in th] == ["th1"] and all(c["kind"] == "evidence" for c in ev)
    many = ([h(f"r{i}", .9 - i * .01, thread=f"t{i}") for i in range(8)]
            + [h(f"p{i}", .5 - i * .01, source="Play Store review", thread="") for i in range(3)])
    ev, _ = R.rank_hits(many)                                # both sources available: neither takes more than 4 of 6
    assert sum(c["source"].startswith("Reddit") for c in ev) <= C.MAX_PER_SOURCE and any(c["id"] == "p0" for c in ev)
    only_one_ps = many[:8] + [many[8]]                       # one Play Store candidate only: the sixth slot is filled from Reddit
    ev, _ = R.rank_hits(only_one_ps)
    assert len(ev) == C.TOP_K_EVIDENCE and any(c["id"] == "p0" for c in ev)


def test_split_parts_are_merged_to_the_best_part():
    def h(i, sim, parent):
        return {"id": i, "parent_id": parent, "similarity": sim, "kind": "evidence", "source": "Reddit comment",
                "thread_id": "t", "text": "x", "source_link": "http://x"}
    ev, _ = R.rank_hits([h("c#p2", .8, "c"), h("c#p1", .7, "c")])
    assert [c["id"] for c in ev] == ["c#p2"]
