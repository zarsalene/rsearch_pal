"""Sprint 08: the literature review builder."""
import io
import json

from app import db, game, writing
from helpers import upload, wait_ready

TODAY = "2026-10-09"


def read(client, h, sample_pdfs, name="a.pdf"):
    pid = upload(client, h, sample_pdfs[name].path)
    wait_ready(client, h, pid)
    return pid


def setup_papers(client, h, fake_ai, sample_pdfs):
    a, b = read(client, h, sample_pdfs, "a.pdf"), read(client, h, sample_pdfs, "b.pdf")
    client.post(f"/api/papers/{a}/meta/extract", headers=h)
    subs = [db.add_sub_question(t)["id"] for t in ("What data exists?", "Which method works best?", "How do we measure it?")]
    db.set_tags(a, "", [subs[0]])
    db.set_tags(b, "", [subs[0], subs[1]])
    return a, b, subs


def test_count_words_does_not_count_quotes():
    text = "I think this is important.\n> Our system uses a hypothesis agent (Smith, 2024, p. 2)\nThe method is simple."
    assert writing.count_words(text) == 5 + 4  # the quote line is not a word of the student
    assert writing.count_words("") == 0 and writing.quote_lines(text) == ["Our system uses a hypothesis agent (Smith, 2024, p. 2)"]


def test_the_outline_has_one_section_for_each_sub_question(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    a, b, subs = setup_papers(client, h, fake_ai, sample_pdfs)
    n_ai = len(fake_ai.calls)
    doc = client.post("/api/review-doc/outline", headers=h).json()
    assert len(fake_ai.calls) == n_ai  # no AI text in the outline
    assert [s["heading"] for s in doc["sections"]] == ["What data exists?", "Which method works best?", "How do we measure it?"]
    assert [s["sub_question_id"] for s in doc["sections"]] == subs
    s1, s2, s3 = doc["sections"]
    assert [c["paper_id"] for g in s1["sources"] for c in g["cards"]] == [a, b] or {c["paper_id"] for g in s1["sources"] for c in g["cards"]} == {a, b}
    assert {c["paper_id"] for g in s2["sources"] for c in g["cards"]} == {b} and s3["sources"] == []
    quotes = [q for g in s1["sources"] for c in g["cards"] if c["paper_id"] == a for q in c["quotes"]]
    assert quotes and all(q["quote"] and q["page"] >= 1 and q["cite"].startswith("(Smith & Wei, 2024, p. ") for q in quotes)  # each quote has its citation
    assert not any("encrypted" in q["quote"] for q in quotes)  # the hidden claim has no verified quote
    again = client.post("/api/review-doc/outline", headers=h).json()
    assert len(again["sections"]) == 3  # a second outline adds nothing


def test_the_sources_are_grouped_by_the_type_of_link(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    a, b, subs = setup_papers(client, h, fake_ai, sample_pdfs)
    db.set_setting("link:" + ":".join(sorted([a, b])), json.dumps({"a": a, "b": b, "relation": "same_method", "evidence": []}))
    doc = client.post("/api/review-doc/outline", headers=h).json()
    groups = doc["sections"][0]["sources"]
    assert [g["label"] for g in groups] == ["Same method"] and len(groups[0]["cards"]) == 2


def test_the_outline_without_sub_questions_makes_one_section(client, auth_headers):
    doc = client.post("/api/review-doc/outline", headers=auth_headers).json()
    assert [s["heading"] for s in doc["sections"]] == ["Literature review"]


def test_save_a_section_and_export_markdown_with_citations(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    a, b, subs = setup_papers(client, h, fake_ai, sample_pdfs)
    doc = client.post("/api/review-doc/outline", headers=h).json()
    sid = doc["sections"][0]["id"]
    quote = doc["sections"][0]["sources"][0]["cards"][0]["quotes"][0]
    text = f"Several papers study this question.\n> {quote['quote']} {quote['cite']}\nThe data is small."
    r = client.put(f"/api/review-doc/sections/{sid}", headers=h, json={"text": text})
    assert r.status_code == 200, r.text
    assert r.json()["words"] == 5 + 4 and r.json()["unverified_quotes"] == [] and r.json()["words_today"] == 9
    md = client.get("/api/review-doc/export", headers=h, params={"format": "md"})
    assert md.status_code == 200 and "attachment" in md.headers["content-disposition"]
    assert "# Literature review" in md.text and "## What data exists?" in md.text and quote["cite"] in md.text
    assert "## References" in md.text and "Smith, J., & Wei, L. (2024)." in md.text
    ieee = client.get("/api/review-doc/export", headers=h, params={"format": "md", "style": "ieee"}).text
    assert "[1] J. Smith, L. Wei" in ieee
    assert client.get("/api/review-doc/export", headers=h, params={"format": "pdf"}).status_code == 400
    assert client.get("/api/review-doc/export", headers=h, params={"style": "x"}).status_code == 400


def test_export_docx(client, auth_headers, fake_ai, sample_pdfs):
    from docx import Document
    h = auth_headers
    a, b, subs = setup_papers(client, h, fake_ai, sample_pdfs)
    sid = client.post("/api/review-doc/outline", headers=h).json()["sections"][0]["id"]
    client.put(f"/api/review-doc/sections/{sid}", headers=h, json={"text": "My own words about the data.\n> A quote of the paper (Smith & Wei, 2024, p. 2)"})
    r = client.get("/api/review-doc/export", headers=h, params={"format": "docx"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.openxmlformats")
    d = Document(io.BytesIO(r.content))
    texts = [p.text for p in d.paragraphs]
    assert "What data exists?" in texts and "My own words about the data." in texts and "References" in texts


def test_truth_a_quote_that_the_student_changed_is_marked(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    a, b, subs = setup_papers(client, h, fake_ai, sample_pdfs)
    sid = client.post("/api/review-doc/outline", headers=h).json()["sections"][0]["id"]
    good = "> Our system uses a hypothesis agent and a validation agent. (Smith & Wei, 2024, p. 2)"
    bad = "> Our system never uses any agent at all and always fails. (Smith & Wei, 2024, p. 2)"
    r = client.put(f"/api/review-doc/sections/{sid}", headers=h, json={"text": f"{good}\n{bad}"}).json()
    assert r["unverified_quotes"] == ["Our system never uses any agent at all and always fails. (Smith & Wei, 2024, p. 2)"]  # the changed quote is not in the PDF
    assert client.get("/api/review-doc", headers=h).json()["sections"][0]["unverified_quotes"] == r["unverified_quotes"]


def test_words_feed_the_daily_goal_and_the_level_author(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    doc = client.post("/api/review-doc/outline", headers=h).json()
    sid = doc["sections"][0]["id"]
    g = client.post("/api/goals", headers=h, json={"text": "Write 200 words", "kind": "words", "target": 200, "date": db_today()}).json()
    client.put(f"/api/review-doc/sections/{sid}", headers=h, json={"text": "word " * 120})
    goals = client.get("/api/goals", headers=h, params={"date": db_today()}).json()
    assert goals[0]["progress"] == 120 and goals[0]["target"] == 200 and goals[0]["done"] is False  # the student checks the goal
    client.put(f"/api/review-doc/sections/{sid}", headers=h, json={"text": "word " * 80})  # a shorter text: no new words
    client.put(f"/api/review-doc/sections/{sid}", headers=h, json={"text": "word " * 150})  # 70 new words
    assert client.get("/api/goals", headers=h, params={"date": db_today()}).json()[0]["progress"] == 190
    assert db.sections_written(300) == 0 and game.counts()["sections"] == 0
    client.put(f"/api/review-doc/sections/{sid}", headers=h, json={"text": "word " * 300 + "\n> a quote that is long and not counted at all here"})
    assert db.sections_written(300) == 1 and game.counts()["sections"] == 1  # the condition of the level Author
    nxt = game.level_info(5000, {"cards": 5, "feynman": 3, "links": 10, "critical": 10, "gaps": 1, "sections": 1, "outline": None})
    assert nxt["name"] == "Author" and nxt["next"]["conditions"][0]["available"] is False
    assert g["id"]


def db_today():
    return game.local_date(db.now())


def test_sections_can_be_added_renamed_ordered_and_deleted(client, auth_headers):
    h = auth_headers
    client.post("/api/review-doc/outline", headers=h)
    s2 = client.post("/api/review-doc/sections", headers=h, json={"heading": "Introduction"}).json()
    s3 = client.post("/api/review-doc/sections", headers=h, json={"heading": "Conclusion"}).json()
    first = client.get("/api/review-doc", headers=h).json()["sections"][0]
    order = [s3["id"], first["id"], s2["id"]]
    assert [s["id"] for s in client.put("/api/review-doc/order", headers=h, json={"ids": order}).json()["sections"]] == order
    assert client.put(f"/api/review-doc/sections/{s2['id']}", headers=h, json={"heading": "  The   start "}).json()["heading"] == "The start"
    assert client.put(f"/api/review-doc/sections/{s2['id']}", headers=h, json={"heading": " "}).status_code == 400
    assert client.put(f"/api/review-doc/sections/{s2['id']}", headers=h, json={"text": "x" * 60001}).status_code == 400
    assert client.put("/api/review-doc/sections/nope", headers=h, json={"text": "a"}).status_code == 400
    assert client.post("/api/review-doc/sections", headers=h, json={"heading": ""}).status_code == 400
    assert client.put("/api/review-doc/title", headers=h, json={"title": "My review"}).json()["doc"]["title"] == "My review"
    assert client.delete(f"/api/review-doc/sections/{s3['id']}", headers=h).status_code == 200
    assert client.delete(f"/api/review-doc/sections/{s3['id']}", headers=h).status_code == 404
    assert len(client.get("/api/review-doc", headers=h).json()["sections"]) == 2


def test_login_and_switch(client, auth_headers):
    h = auth_headers
    assert client.get("/api/review-doc").status_code == 401
    client.put("/api/features", headers=h, json={"features": {"litreview": False}})
    assert client.get("/api/review-doc", headers=h).status_code == 403 and client.post("/api/review-doc/outline", headers=h).status_code == 403
    assert client.get("/api/review-doc/export", headers=h).status_code == 403


def test_the_text_of_the_student_is_backed_up(client, auth_headers):
    h = auth_headers
    sid = client.post("/api/review-doc/outline", headers=h).json()["sections"][0]["id"]
    client.put(f"/api/review-doc/sections/{sid}", headers=h, json={"text": "My text, in my words."})
    backup = client.get("/api/export", headers=h).json()
    assert backup["review_doc"]["sections"][0]["text"] == "My text, in my words."
    with db.conn() as c:
        c.execute("DELETE FROM review_sections")
    client.post("/api/import", headers=h, json=backup)
    client.post("/api/import", headers=h, json=backup)  # a second import does not change a document that has text
    secs = client.get("/api/review-doc", headers=h).json()["sections"]
    assert len(secs) == 1 and secs[0]["text"] == "My text, in my words."
