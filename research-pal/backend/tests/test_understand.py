"""Sprint 02: Feynman check (A1), like I am 12 (A2) and quiz (A5)."""
import sqlite3

from app import config, db, llm, understand
from helpers import assert_no_false_quote, upload, wait_ready
from pdfs import INVENTED_QUOTE

EXPLAIN_AI = "to check an explanation of a paper"  # the start of the prompt of the Feynman check
ELI12_AI = "like the student is 12 years old"
QUIZ_AI = "write questions that the student answers from memory"
MARK_AI = "You mark the answer of a student"
GOOD = "The system uses a hypothesis agent. It reaches a precision of 91.4 percent. The recall is 95.0 percent. It also cooks pasta."


def read(client, h, sample_pdfs, name="a.pdf"):
    pid = upload(client, h, sample_pdfs[name].path)
    return pid, wait_ready(client, h, pid)


def test_split_claims():
    assert len(understand.split_claims("The system has two agents. The first agent reads logs. It finds 3 attacks.")) == 3
    assert understand.split_claims("- First point about the paper.\n- Second point about the paper.\n3) Third point here now.") == [
        "First point about the paper.", "Second point about the paper.", "Third point here now."]
    assert understand.split_claims("Yes! Right! Okay then.") == []  # fewer than 3 words
    assert len(understand.split_claims("Claim number one is here. " * 30)) == understand.MAX_CLAIMS


def test_explain(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid, got = read(client, h, sample_pdfs)
    r = client.post(f"/api/papers/{pid}/explain", headers=h, json={"text": GOOD})
    assert r.status_code == 200, r.text
    res = r.json()
    marks = [c["mark"] for c in res["claims"]]
    assert marks == ["correct", "correct", "wrong", "not_in_paper"], marks
    c1, c3 = res["claims"][0], res["claims"][2]
    assert c1["verified"] and c1["page"] == 2 and "hypothesis agent" in c1["quote"] and c1["label"] == "Correct"
    # the number 95.0 is not in the paper: the server marks the claim "wrong", whatever the AI said
    assert c3["source"] == "server" and "95.0" in c3["comment"] and c3["quote"] == ""
    assert [m["field"] for m in res["missing"]] == ["problem"] and res["missing"][0]["answer"] == got["card"]["fields"]["problem"]["answer"]
    assert res["score"] == 67 and res["message"].startswith("Good start. 1 point is missing.") and "1 claim needs a second look" in res["message"]
    assert_no_false_quote({"claims": [{**c, "status": "verified" if c["verified"] else "x", "evidence": [{"quote": c["quote"], "verified": c["verified"]}]}
                                      for c in res["claims"] if c["quote"]]}, pages=db.get_pages(pid))

    # the attempt is saved. The history shows the progress.
    hist = client.get(f"/api/papers/{pid}/explanations", headers=h).json()
    assert [(x["id"], x["score"], x["text"]) for x in hist] == [(res["id"], 67, GOOD)]
    better = "Analysts spend many hours on manual log review. The system uses a hypothesis agent and a validation agent. It reaches a precision of 91.4 percent and a recall of 84.2 percent."
    r2 = client.post(f"/api/papers/{pid}/explain", headers=h, json={"text": better}).json()
    assert r2["missing"] == [] and r2["score"] > res["score"]
    assert [x["score"] for x in client.get(f"/api/papers/{pid}/explanations", headers=h).json()] == [r2["score"], 67]  # newest first
    assert client.get(f"/api/papers/{pid}/explanations", headers=h, params={"card_id": "other"}).json() == []
    assert client.delete(f"/api/explanations/{res['id']}", headers=h).status_code == 200
    assert client.delete(f"/api/explanations/{res['id']}", headers=h).status_code == 404
    assert len(client.get(f"/api/papers/{pid}/explanations", headers=h).json()) == 1


def test_truth_a_mark_with_a_false_quote_becomes_cannot_check(client, auth_headers, fake_ai, sample_pdfs):
    pid, _ = read(client, auth_headers, sample_pdfs)
    res = client.post(f"/api/papers/{pid}/explain", headers=auth_headers, json={"text": "This is a false quote claim about the paper."}).json()
    c = res["claims"][0]
    assert c["mark"] == "cannot_check" and c["verified"] is False and c["quote"] == "" and "could not find the quote" in c["comment"]
    assert INVENTED_QUOTE not in str(res)  # the false quote never reaches the page
    assert res["counts"]["cannot_check"] == 1
    assert "could not check" in res["message"]  # a kind message, no wrong mark


def test_a_mark_with_no_quote_is_not_trusted(client, auth_headers, fake_ai, sample_pdfs):
    pid, _ = read(client, auth_headers, sample_pdfs)
    fake_ai.when(EXPLAIN_AI, {"claims": [{"id": 1, "mark": "wrong", "quote": "", "page": 1, "comment": "No."}, {"id": 2, "mark": "great"}]})
    res = client.post(f"/api/papers/{pid}/explain", headers=auth_headers, json={"text": "The agent reads many logs daily. The tool is fast and clear."}).json()
    assert [c["mark"] for c in res["claims"]] == ["cannot_check", "cannot_check"]


def test_the_comment_is_checked_with_the_ste_rules(client, auth_headers, fake_ai, sample_pdfs):
    pid, _ = read(client, auth_headers, sample_pdfs)
    long = "You wrote a good sentence about the agents of the system and it is also very close to the text of the paper that the authors wrote."
    fake_ai.when(EXPLAIN_AI, {"claims": [{"id": 1, "mark": "correct", "quote": "Our system uses a hypothesis agent and a validation agent.", "page": 2, "comment": long}]})
    fake_ai.when("technical editor", {"1": "You wrote a good sentence. It is close to the paper."})
    res = client.post(f"/api/papers/{pid}/explain", headers=auth_headers, json={"text": "The system uses a hypothesis agent and a validation agent."}).json()
    assert res["claims"][0]["comment"] == "You wrote a good sentence. It is close to the paper."


def test_explain_bad_requests(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid, _ = read(client, h, sample_pdfs)
    n = len(fake_ai.calls)
    assert client.post(f"/api/papers/{pid}/explain", headers=h, json={"text": "  "}).status_code == 400
    assert client.post(f"/api/papers/{pid}/explain", headers=h, json={"text": "Yes. No."}).status_code == 400
    assert client.post(f"/api/papers/{pid}/explain", headers=h, json={"text": "word " * 700}).status_code == 400
    assert client.post(f"/api/papers/{pid}/explain", headers=h, json={"text": GOOD, "card_id": "nope"}).status_code == 400
    assert client.post("/api/papers/nope/explain", headers=h, json={"text": GOOD}).status_code == 404
    assert client.post(f"/api/papers/{pid}/explain", json={"text": GOOD}).status_code == 401
    assert len(fake_ai.calls) == n  # a wrong request makes no AI call
    fake_ai.when(EXPLAIN_AI, llm.LLMError("The AI is down."))
    assert client.post(f"/api/papers/{pid}/explain", headers=h, json={"text": GOOD}).status_code == 502
    client.put("/api/features", headers=h, json={"features": {"feynman": False}})
    assert client.post(f"/api/papers/{pid}/explain", headers=h, json={"text": GOOD}).status_code == 403
    assert client.get(f"/api/papers/{pid}/explanations", headers=h).status_code == 403


def test_score():
    assert understand.score_of(["correct", "correct"], 0, 3) == 100
    assert understand.score_of(["wrong", "wrong"], 3, 3) == 0
    assert understand.score_of(["cannot_check", "not_in_paper"], 0, 3) == 40  # the server could not check: no penalty for accuracy, but no credit
    assert understand.score_of(["partly"], 1, 2) == round(100 * (0.6 * 0.5 + 0.4 * 0.5))


# ------------------------------------------------------------------ A2
def test_eli12(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid, got = read(client, h, sample_pdfs)
    r = client.post(f"/api/papers/{pid}/eli12", headers=h, json={"field": "method"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["simple"]["ok"] and d["simple"]["text"].startswith("Simple: ") and d["original"] == got["card"]["fields"]["method"]["answer"]
    assert d["example"]["label"] == "AI suggestion" and d["analogy"]["label"] == "AI suggestion"  # not from the paper
    assert d["terms"] == ["hypothesis agent"] and d["term_line"] == "The paper calls this: hypothesis agent."
    assert "AI suggestion" not in str(d["simple"])


def test_eli12_keeps_the_numbers_and_the_terms_of_the_paper(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid, _ = read(client, h, sample_pdfs)
    fake_ai.when(ELI12_AI, {"simple": "It reaches 90 percent.", "example": "It is like 100 apples.", "analogy": "It is like a race of 91.4 runners.", "terms": ["quantum blockchain", "Precision"]})
    d = client.post(f"/api/papers/{pid}/eli12", headers=h, json={"field": "result"}).json()
    assert d["simple"]["ok"] is False and d["simple"]["text"] == "" and "changed a number" in d["simple"]["message"]  # 91.4 became 90
    assert d["example"] is None  # a new number (100): refused
    assert d["analogy"]["text"] == "It is like a race of 91.4 runners."  # the number is in the text: allowed
    assert d["terms"] == ["Precision"]  # the AI invented "quantum blockchain": not in the paper


def test_eli12_bad_requests(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid = upload(client, h, sample_pdfs["a.pdf"].path, purpose="How do others validate hypotheses?")
    wait_ready(client, h, pid)
    assert client.post(f"/api/papers/{pid}/eli12", headers=h, json={"field": "question"}).status_code == 400  # the question of the student
    assert client.post(f"/api/papers/{pid}/eli12", headers=h, json={"field": "limitation"}).status_code == 400  # hidden
    assert client.post(f"/api/papers/{pid}/eli12", headers=h, json={"field": "nope"}).status_code == 400
    assert client.post(f"/api/papers/{pid}/eli12", headers=h, json={"field": "method", "card_id": "nope"}).status_code == 400
    client.put("/api/features", headers=h, json={"features": {"eli12": False}})
    assert client.post(f"/api/papers/{pid}/eli12", headers=h, json={"field": "method"}).status_code == 403


# ------------------------------------------------------------------ A5
def test_quiz_drops_a_question_with_a_false_quote(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid, _ = read(client, h, sample_pdfs)
    r = client.post(f"/api/papers/{pid}/quiz", headers=h, json={})
    assert r.status_code == 200, r.text
    qs = r.json()["questions"]
    assert [q["question"] for q in qs] == ["What does the hypothesis agent read?", "Which dataset do the authors use?"]  # the third has a false quote
    assert all("answer" not in q and "quote" not in q for q in qs)  # the answers stay on the server
    rows = db.review_list(pid, "quiz")
    assert len(rows) == 2 and all(r["kind"] == "quiz" and r["quote"] and r["page"] for r in rows)
    assert_no_false_quote({"evidence": [{"quote": r["quote"], "verified": True, "paper_id": pid}] for r in rows}, pages={pid: db.get_pages(pid)}, invented=[INVENTED_QUOTE])
    assert all(r["quote"] != INVENTED_QUOTE for r in rows)
    listed = client.get(f"/api/papers/{pid}/quiz", headers=h).json()
    assert [q["question"] for q in listed] == [q["question"] for q in qs] and listed[0]["tries"] == 0 and "answer" not in listed[0]
    # the same questions again: they exist, so there is no new row
    assert client.post(f"/api/papers/{pid}/quiz", headers=h, json={}).json()["questions"] == []
    assert len(db.review_list(pid, "quiz")) == 2


def test_quiz_drops_an_answer_with_a_number_that_the_quote_does_not_have(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid, _ = read(client, h, sample_pdfs)
    fake_ai.when(QUIZ_AI, {"questions": [{"question": "What precision does AUTOMA reach?", "answer": "It reaches 99.9 percent.",
                                          "quote": "AUTOMA reaches a precision of 91.4 percent and a recall of 84.2 percent.", "page": 3}]})
    out = client.post(f"/api/papers/{pid}/quiz", headers=h, json={}).json()
    assert out["questions"] == [] and "no question" in out["message"]


def test_answer_a_question(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid, _ = read(client, h, sample_pdfs)
    qs = client.post(f"/api/papers/{pid}/quiz", headers=h, json={}).json()["questions"]
    wrong = client.post(f"/api/quiz/{qs[0]['id']}/answer", headers=h, json={"answer": "It reads emails."}).json()
    assert wrong["mark"] == "wrong" and wrong["label"] == "Wrong"
    assert wrong["correct_answer"] == "It reads Sysmon logs." and wrong["page"] == 2 and "reads Sysmon" in wrong["quote"]  # the correct quote and page
    good = client.post(f"/api/quiz/{qs[0]['id']}/answer", headers=h, json={"answer": "It reads the Sysmon logs."}).json()
    assert good["mark"] == "correct" and good["comment"] == "Good answer."
    row = client.get(f"/api/papers/{pid}/quiz", headers=h).json()[0]
    assert row["tries"] == 2 and row["last_mark"] == "correct"
    # a number that the source does not have: not "correct"
    fake_ai.when(MARK_AI, {"mark": "correct", "comment": "Right."})
    assert client.post(f"/api/quiz/{qs[1]['id']}/answer", headers=h, json={"answer": "The OpTC dataset with 77 logs."}).json()["mark"] == "partly"
    # wrong requests
    assert client.post(f"/api/quiz/{qs[0]['id']}/answer", headers=h, json={"answer": " "}).status_code == 400
    assert client.post(f"/api/quiz/{qs[0]['id']}/answer", headers=h, json={"answer": "x" * 1001}).status_code == 400
    assert client.post("/api/quiz/nope/answer", headers=h, json={"answer": "x"}).status_code == 404
    assert client.post(f"/api/quiz/{qs[0]['id']}/answer", json={"answer": "x"}).status_code == 401
    fake_ai.when(MARK_AI, {"mark": "maybe", "comment": ""})  # a wrong mark of the AI: the server decides
    assert client.post(f"/api/quiz/{qs[1]['id']}/answer", headers=h, json={"answer": "The OpTC dataset."}).json()["mark"] == "partly"
    assert client.delete(f"/api/quiz/{qs[1]['id']}", headers=h).status_code == 200
    assert client.delete(f"/api/quiz/{qs[1]['id']}", headers=h).status_code == 404
    client.put("/api/features", headers=h, json={"features": {"quiz": False}})
    assert client.post(f"/api/papers/{pid}/quiz", headers=h, json={}).status_code == 403


# ------------------------------------------------------------------ data
def test_a_word_in_the_glossary_is_a_review_item(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid, _ = read(client, h, sample_pdfs)
    g = client.post("/api/glossary", headers=h, json={"term": "hypothesis", "paper_id": pid}).json()
    items = db.review_list(pid, "glossary")
    assert len(items) == 1 and items[0]["question"] == "hypothesis" and items[0]["ref_id"] == g["id"] and items[0]["quote"] == g["explanation"] and items[0]["page"] == 2
    client.post("/api/glossary", headers=h, json={"term": "Hypothesis", "paper_id": pid})  # the same word: still one item
    assert len(db.review_list(pid, "glossary")) == 1
    client.delete(f"/api/papers/{pid}", headers=h)  # the word stays with the paper gone
    assert len(db.review_list(None, "glossary")) == 1
    client.delete(f"/api/glossary/{g['id']}", headers=h)
    assert db.review_list(None, "glossary") == []


def test_words_saved_before_this_sprint_get_a_review_item(client):
    old = config.DATA_DIR / "old.sqlite3"
    c = sqlite3.connect(old)
    c.executescript("CREATE TABLE glossary(id TEXT PRIMARY KEY, term TEXT, explanation TEXT, source TEXT, paper_id TEXT, page INTEGER DEFAULT 0, created_at REAL);"
                    "INSERT INTO glossary VALUES('g1','recall','Recall is the share of attacks that the system finds.','paper','p1',3,1.0);")
    c.commit()
    c.close()
    real = config.DB_PATH
    try:
        config.DB_PATH = old
        db.init()
        db.init()  # a second start adds nothing
        items = db.review_list(None, "glossary")
        assert [(i["question"], i["page"], i["ref_id"]) for i in items] == [("recall", 3, "g1")]
    finally:
        config.DB_PATH = real


def test_deleting_a_paper_deletes_its_attempts_and_questions(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid, _ = read(client, h, sample_pdfs)
    client.post(f"/api/papers/{pid}/explain", headers=h, json={"text": GOOD})
    client.post(f"/api/papers/{pid}/quiz", headers=h, json={})
    client.delete(f"/api/papers/{pid}", headers=h)
    assert db.explanation_list(pid) == [] and db.review_list(pid, "quiz") == []


def test_backup_keeps_the_attempts_and_the_questions(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid, _ = read(client, h, sample_pdfs)
    res = client.post(f"/api/papers/{pid}/explain", headers=h, json={"text": GOOD}).json()
    qs = client.post(f"/api/papers/{pid}/quiz", headers=h, json={}).json()["questions"]
    backup = client.get("/api/export", headers=h).json()
    assert [e["id"] for e in backup["explanations"]] == [res["id"]] and len(backup["quiz"]) == len(qs) == 2
    assert "quote" in backup["quiz"][0]
    client.delete(f"/api/explanations/{res['id']}", headers=h)
    client.delete(f"/api/quiz/{qs[0]['id']}", headers=h)
    client.post("/api/import", headers=h, json=backup)
    client.post("/api/import", headers=h, json=backup)  # a second import adds nothing
    assert [e["id"] for e in db.explanation_list(pid)] == [res["id"]] and len(db.review_list(pid, "quiz")) == 2
