"""Sprint 09: gap finder, writing coach and critical reading check."""
from app import coach, db, game, llm
from helpers import assert_no_false_quote, upload, wait_ready

GAP_AI = "You compare papers for a PhD student"
COACH_AI = "You give feedback on one paragraph"
CRIT_AI = "You help a PhD student to judge the quality of ONE paper"


def read(client, h, sample_pdfs, name="a.pdf"):
    pid = upload(client, h, sample_pdfs[name].path)
    wait_ready(client, h, pid)
    return pid


def two_papers(client, h, sample_pdfs):
    a, b = read(client, h, sample_pdfs, "a.pdf"), read(client, h, sample_pdfs, "b.pdf")
    s = db.add_sub_question("What methods exist?")["id"]
    db.set_tags(a, "", [s])
    db.set_tags(b, "", [s])
    return a, b, s


# ------------------------------------------------------------------ gap finder
def test_gap_finder_keeps_only_points_with_verified_quotes_in_two_papers(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    a, b, s = two_papers(client, h, sample_pdfs)
    r = client.post("/api/gaps", headers=h, json={"sub_question_id": s})
    assert r.status_code == 200, r.text
    out = r.json()
    # truth: the second "agree" point and the "disagree" point have a false quote for one paper. They are dropped.
    assert [p["point"] for p in out["agree"]] == ["Both papers describe a method."] and out["disagree"] == []
    point = out["agree"][0]
    assert {e["paper_id"] for e in point["evidence"]} == {a, b} and all(e["verified"] for e in point["evidence"])
    pages = {a: db.get_pages(a), b: db.get_pages(b)}
    assert_no_false_quote({"evidence": point["evidence"]}, pages=pages, invented=["The pasta must cook for two hours in cold milk."])
    g = out["gap"][0]
    assert g["label"] == "AI opinion" and g["reason"] and g["status"] == "new" and "encrypted" in g["point"]
    assert client.get("/api/gaps", headers=h, params={"sub_question_id": s}).json()["gap"][0]["id"] == g["id"]  # saved
    assert client.get("/api/gaps", headers=h, params={"sub_question_id": "other"}).json()["run_id"] is None


def test_a_gap_is_confirmed_by_the_student_and_counts_for_connector(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    a, b, s = two_papers(client, h, sample_pdfs)
    gid = client.post("/api/gaps", headers=h, json={"sub_question_id": s}).json()["gap"][0]["id"]
    assert game.counts()["gaps"] == 0  # the AI opinion alone counts for nothing
    r = client.put(f"/api/gaps/{gid}", headers=h, json={"status": "confirmed"}).json()
    assert r["status"] == "confirmed" and r["label"] == "AI opinion" and game.counts()["gaps"] == 1
    nxt = game.level_info(500, {"cards": 5, "feynman": 3, "links": 10, "critical": 10, "gaps": game.counts()["gaps"], "sections": 0, "outline": None})
    assert nxt["name"] == "Connector"  # 10 explained links and 1 confirmed gap
    client.put(f"/api/gaps/{gid}", headers=h, json={"status": "not_gap"})
    assert game.counts()["gaps"] == 0
    assert client.put(f"/api/gaps/{gid}", headers=h, json={"status": "maybe"}).status_code == 400
    assert client.put("/api/gaps/nope", headers=h, json={"status": "confirmed"}).status_code == 400


def test_use_a_gap_adds_a_section_to_the_outline(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    a, b, s = two_papers(client, h, sample_pdfs)
    gid = client.post("/api/gaps", headers=h, json={"sub_question_id": s}).json()["gap"][0]["id"]
    sec = client.post(f"/api/gaps/{gid}/use", headers=h).json()
    assert sec["heading"] == "Nobody tested the systems on encrypted traffic." and sec["text"] == "" and sec["sub_question_id"] == s  # headings only: the student writes
    assert sec["id"] in [x["id"] for x in client.get("/api/review-doc", headers=h).json()["sections"]]
    assert client.post("/api/gaps/nope/use", headers=h).status_code == 404


def test_gap_finder_requests(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    a = read(client, h, sample_pdfs)
    s = db.add_sub_question("One paper only?")["id"]
    db.set_tags(a, "", [s])
    n = len(fake_ai.calls)
    assert client.post("/api/gaps", headers=h, json={"sub_question_id": s}).status_code == 400  # one paper is not enough
    assert client.post("/api/gaps", headers=h, json={}).status_code == 400
    assert client.post("/api/gaps", headers=h, json={"sub_question_id": "nope"}).status_code == 400
    assert client.post("/api/gaps", headers=h, json={"paper_ids": [a, "nope"]}).status_code == 400
    assert client.post("/api/gaps", headers=h, json={"paper_ids": [a] * 3}).status_code == 400  # the same paper 3 times is one paper
    assert len(fake_ai.calls) == n  # a wrong request makes no AI call
    b = read(client, h, sample_pdfs, "b.pdf")
    assert client.post("/api/gaps", headers=h, json={"paper_ids": [a, b]}).status_code == 200  # papers that you choose
    fake_ai.when(GAP_AI, llm.LLMError("The AI is down."))
    assert client.post("/api/gaps", headers=h, json={"paper_ids": [a, b]}).status_code == 502
    assert client.post("/api/gaps", json={"paper_ids": [a, b]}).status_code == 401
    client.put("/api/features", headers=h, json={"features": {"gaps": False}})
    assert client.post("/api/gaps", headers=h, json={"paper_ids": [a, b]}).status_code == 403 and client.get("/api/gaps", headers=h).status_code == 403


def test_the_points_of_the_gap_finder_pass_the_ste_check(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    a, b, s = two_papers(client, h, sample_pdfs)
    long = "Nobody tested the two systems of the papers on the encrypted traffic of a real network and it is also not clear if they work well on other data."
    fake_ai.when(GAP_AI, {"agree": [], "disagree": [], "gap": [{"point": long, "reason": "Both papers use one dataset."}]})
    fake_ai.when("technical editor", {"g0": "Nobody tested the two systems on encrypted traffic. It is not clear if they work on other data."})
    assert client.post("/api/gaps", headers=h, json={"sub_question_id": s}).json()["gap"][0]["point"].startswith("Nobody tested the two systems on encrypted traffic.")


# ------------------------------------------------------------------ writing coach: the rules (no AI)
def test_the_style_check_needs_no_ai(client, fake_ai):
    text = ("The system is very fast and it reads the logs of the network and then it sends each log to the second agent which checks them all today. "
            "The logs are read by the agent. It doesn't scale; it is cheap.")
    out = coach.review(text, use_ai=False)
    assert fake_ai.calls == []  # no AI call
    msgs = [c["comment"] for c in out["comments"] if c["kind"] == "style"]
    assert any("words" in m for m in msgs) and any("Filler" in m and "very" in m for m in msgs) and any("passive" in m for m in msgs)
    assert any("contractions" in m for m in msgs) and any("semicolon" in m for m in msgs)
    for c in out["comments"]:  # each comment has a place in the text
        assert text[c["start"]:c["end"]] == c["sentence"] or text[c["start"]:c["end"]].startswith(c["sentence"][:30])
    assert out["rewrite"] == "" and "decide" in out["message"]


def test_a_claim_without_a_citation_is_marked_and_a_claim_with_one_is_not(client, fake_ai):
    out = coach.review("AUTOMA reaches a precision of 91.4 percent on the OpTC dataset. The weather is nice today.\nOther authors report a similar result (Smith, 2024).", use_ai=False)
    sourced = [c for c in out["comments"] if c["kind"] == "sourced" and c["source"] == "rule"]
    assert [c["sentence"][:12] for c in sourced] == ["AUTOMA reach"] and "citation" in sourced[0]["comment"]


def test_truth_a_citation_to_page_9_of_a_paper_with_4_pages(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    a = read(client, h, sample_pdfs)
    client.post(f"/api/papers/{a}/meta/extract", headers=h)
    text = ("The system uses two agents (Smith & Wei, 2024, p. 9).\n"
            "The authors tested one dataset (Smith & Wei, 2024, p. 3).\n"
            "Another group built a similar tool (Nobody, 2020).\n"
            "> Our system uses a hypothesis agent and a validation agent. (Smith & Wei, 2024, p. 3)\n"
            "> Our system uses a hypothesis agent and a validation agent. (Smith & Wei, 2024, p. 2)\n"
            "The first paper is the base [1, p. 2]. The tenth paper is not there [10].")
    out = client.post("/api/coach", headers=h, json={"text": text}).json()
    msgs = [c["comment"] for c in out["comments"] if c["source"] == "server"]
    assert any(m.startswith("Page 9 not found") and "has 4 pages" in m for m in msgs)  # page 9 of a paper with 4 pages
    assert any("(Nobody, 2020) is not a paper of your library" in m for m in msgs)
    assert any("not on page 3" in m for m in msgs)  # the quote is on page 2
    assert any("[10] is not a paper of your library" in m for m in msgs)
    assert len(msgs) == 4  # the good citations get no comment


# ------------------------------------------------------------------ writing coach: the AI part never rewrites
def test_truth_the_coach_refuses_a_comment_that_is_a_rewrite(client, auth_headers, fake_ai):
    text = "Many studies show that agents help analysts. The system reads the logs and sends each log to the second agent. The result is good."
    out = client.post("/api/coach", headers=auth_headers, json={"text": text}).json()
    ai = [c for c in out["comments"] if c["source"] == "ai"]
    assert [c["kind"] for c in ai] == ["clear", "logical"] and out["refused"] == 1  # the rewrite of sentence 2 is refused
    assert not any("better version" in c["comment"] or "the second agent for a check" in c["comment"] for c in out["comments"])
    assert out["rewrite"] == "" and ai[0]["comment"] == "What does the word many mean here?"


def test_what_a_rewrite_looks_like():
    text = "The system reads the logs and then sends them to the agent."
    assert coach.looks_like_rewrite('Here is a better version: "The system reads the logs and sends them."', text)
    assert coach.looks_like_rewrite('Try: "The system reads each network log and then it sends every log to the second agent for a deep check"', text)  # new text of more than 8 words
    assert coach.looks_like_rewrite("word " * 41, text)
    assert not coach.looks_like_rewrite('Is "the logs and then sends them" clear for a reader?', text)  # a short quote of the student is fine
    assert not coach.looks_like_rewrite("Which paper says this? Add the citation.", text)


def test_the_comments_of_the_coach_pass_the_ste_check(client, auth_headers, fake_ai):
    long = "You should think about the way in which the first sentence of the paragraph links to the claim that comes after it because the reader may not follow."
    fake_ai.when(COACH_AI, {"comments": [{"sentence": 1, "kind": "logical", "comment": long}]})
    fake_ai.when("technical editor", {"0": "Check the link between the first sentence and the claim. The reader may not follow."})
    out = client.post("/api/coach", headers=auth_headers, json={"text": "The agents help analysts a lot. The claim comes after it."}).json()
    assert [c["comment"] for c in out["comments"] if c["source"] == "ai"] == ["Check the link between the first sentence and the claim. The reader may not follow."]


def test_the_coach_works_when_the_ai_is_down_and_checks_the_input(client, auth_headers, fake_ai):
    h = auth_headers
    fake_ai.when(COACH_AI, llm.LLMError("The AI is down."))
    out = client.post("/api/coach", headers=h, json={"text": "The system is very fast. It reaches 91.4 percent."}).json()
    assert "did not work" in out["note"] and out["comments"]  # the rule checks stay
    assert client.post("/api/coach", headers=h, json={"text": "Short."}).status_code == 400
    assert client.post("/api/coach", headers=h, json={"text": "x " * 3100}).status_code == 400
    assert client.post("/api/coach", json={"text": "A text that is long enough here."}).status_code == 401
    client.put("/api/features", headers=h, json={"features": {"coach": False}})
    assert client.post("/api/coach", headers=h, json={"text": "A text that is long enough here."}).status_code == 403


# ------------------------------------------------------------------ critical reading
def test_critique_answers_need_a_verified_quote(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    r = client.post(f"/api/papers/{pid}/critique", headers=h)
    assert r.status_code == 200, r.text
    c = r.json()
    by = {i["key"]: i for i in c["items"]}
    assert c["label"] == "AI opinion" and list(by) == ["question", "method", "sample", "bias", "support", "reproduce"]
    assert by["question"]["answer"] == "yes" and by["question"]["verified"] and by["question"]["page"] == 1
    assert by["sample"]["answer"] == "unclear" and by["sample"]["quote"] == "" and by["sample"]["verified"] is False  # truth: a false quote makes the answer "unclear"
    assert by["bias"]["answer"] == "unclear" and by["reproduce"]["answer"] == "no" and by["reproduce"]["page"] == 3
    quotes = [{"quote": i["quote"], "verified": True, "paper_id": pid} for i in c["items"] if i["quote"]]
    assert_no_false_quote({"evidence": quotes}, pages={pid: db.get_pages(pid)}, invented=["The authors tested on thousands of hospital patients every day."])
    assert client.get(f"/api/papers/{pid}/critique", headers=h).json()["items"][0]["key"] == "question"
    assert client.get("/api/papers/nope/critique", headers=h).status_code == 404


def test_the_student_changes_and_confirms_a_critique_and_ten_give_the_level_critic(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    assert client.put(f"/api/papers/{pid}/critique", headers=h, json={"answers": {}}).status_code == 400  # run the check first
    client.post(f"/api/papers/{pid}/critique", headers=h)
    assert db.critiques_done() == 0  # an AI opinion that nobody looked at counts for nothing
    r = client.put(f"/api/papers/{pid}/critique", headers=h, json={"answers": {"sample": {"answer": "no", "note": "20 test cases only."}}}).json()
    sample = next(i for i in r["items"] if i["key"] == "sample")
    assert sample["answer"] == "no" and sample["note"] == "20 test cases only." and sample["edited"] is True and r["edited"] is True and r["label"] == "AI opinion"
    assert client.put(f"/api/papers/{pid}/critique", headers=h, json={"answers": {"sample": {"answer": "maybe"}}}).status_code == 400
    assert game.counts()["critical"] == 1
    for i in range(9):  # 9 more checks, confirmed by the student
        db.critique_save(f"paper{i}", {"items": []}, edited=False, confirmed=True)
    assert game.counts()["critical"] == 10
    lvl = game.level_info(300, {**game.counts(), "cards": 5, "feynman": 3})
    assert lvl["name"] == "Critic" and lvl["next"]["name"] == "Connector"
    client.put("/api/features", headers=h, json={"features": {"critique": False}})
    assert client.post(f"/api/papers/{pid}/critique", headers=h).status_code == 403


def test_a_critique_is_deleted_with_its_paper_and_kept_in_the_backup(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    client.post(f"/api/papers/{pid}/critique", headers=h)
    client.put(f"/api/papers/{pid}/critique", headers=h, json={"answers": {}, "confirm": True})
    a, b, s = two_papers(client, h, sample_pdfs)
    client.post("/api/gaps", headers=h, json={"sub_question_id": s})
    backup = client.get("/api/export", headers=h).json()
    assert [c["paper_id"] for c in backup["critiques"]] == [pid] and backup["critiques"][0]["confirmed"] and len(backup["gaps"]) == 1 and len(backup["gap_runs"]) == 1
    client.delete(f"/api/papers/{pid}", headers=h)
    assert db.critique_get(pid) is None
    with db.conn() as c:
        c.execute("DELETE FROM gaps")
        c.execute("DELETE FROM gap_runs")
    client.post("/api/import", headers=h, json=backup)
    client.post("/api/import", headers=h, json=backup)
    assert len(db.gaps_list()) == 1 and db.critique_get(pid)["confirmed"] is True
