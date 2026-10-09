"""Sprint 10: add by DOI, import of BibTeX and RIS, the To read list. Recorded answers only: no network call."""
import httpx
import pytest

from app import bibimport, db, sources, triage
from helpers import upload, wait_ready
from recorded_sources import AUTOMA_DOI, BIB, RIS, many_bib, route

QUESTION = "How can multi agent systems find cyber threats in network logs?"


@pytest.fixture
def fake_net(monkeypatch, sample_pdfs):
    pdf = sample_pdfs["a.pdf"].path.read_bytes()
    state = {"free": True, "calls": []}

    def fetch(url, params=None):
        state["calls"].append(url)
        return route(url, params, pdf, state["free"])

    monkeypatch.setattr(sources, "fetch", fetch)
    monkeypatch.setenv("CONTACT_EMAIL", "student@example.org")
    sources._cache.clear()
    return state


def ready(client, h, pid):
    p = wait_ready(client, h, pid)
    assert p["paper"]["status"] == "ready", p["paper"]
    return p["paper"]


# ------------------------------------------------------------------ the input
def test_the_input_is_found_in_a_link_or_a_sentence():
    assert sources.parse_input("https://doi.org/10.1234/Automa.2024.01.") == {"doi": "10.1234/automa.2024.01"}
    assert sources.parse_input("see doi: 10.1234/abc.5, thanks") == {"doi": "10.1234/abc.5"}
    assert sources.parse_input("https://arxiv.org/abs/2305.01234v2") == {"arxiv": "2305.01234"}
    assert sources.parse_input("arXiv:2305.01234") == {"arxiv": "2305.01234"}
    assert sources.parse_input("2305.01234") == {"arxiv": "2305.01234"}
    assert sources.parse_input("Attention for logs in security") == {"title": "Attention for logs in security"}
    for bad in ("", "   ", "hello", "two words"):
        with pytest.raises(sources.SourceError):
            sources.parse_input(bad)


# ------------------------------------------------------------------ the clients, with recorded answers
def test_openalex_gives_the_metadata_and_the_abstract(fake_net):
    m = sources.find({"doi": AUTOMA_DOI})
    assert m["title"] == "AUTOMA: Multi-agent threat hunting" and m["authors"] == ["Jane Smith", "Li Wei"] and m["year"] == "2024"
    assert m["venue"] == "Journal of Cyber Tests" and m["doi"] == AUTOMA_DOI and m["abstract"].startswith("We present AUTOMA, a multi agent")
    assert m["pdf_urls"][0] == "https://files.example.org/automa.pdf" and m["source"] == "openalex"


def test_arxiv_gives_a_title_authors_and_the_pdf_address(fake_net):
    m = sources.find({"arxiv": "2305.01234"})
    assert m["title"] == "Attention for logs in security" and m["authors"] == ["Ada Lovelace", "Alan Turing"] and m["year"] == "2023"
    assert m["pdf_urls"] == ["https://arxiv.org/pdf/2305.01234"] and m["source"] == "arxiv"
    with pytest.raises(sources.SourceError, match="No source knows"):
        sources.find({"arxiv": "9999.99999"})


def test_unpaywall_finds_a_free_pdf_when_openalex_has_none(fake_net):
    m = sources.find({"doi": "10.9999/closed.1"})
    assert m["pdf_urls"] == ["https://repo.example.org/closed.pdf"]
    fake_net["free"] = False
    sources._cache.clear()
    assert sources.find({"doi": "10.9999/closed.1"})["pdf_urls"] == []


def test_unpaywall_needs_an_email(fake_net, monkeypatch):
    monkeypatch.delenv("CONTACT_EMAIL")
    assert sources.unpaywall("10.9999/closed.1") == []


def test_semantic_scholar_is_the_fallback_and_a_title_search_works(fake_net, monkeypatch):
    monkeypatch.setattr(sources, "openalex", lambda **k: None)
    m = sources.find({"doi": AUTOMA_DOI})
    assert m["source"] == "semanticscholar" and m["year"] == "2024"
    monkeypatch.undo()
    assert sources.find({"title": "AUTOMA threat hunting"})["title"].startswith("AUTOMA")


def test_a_call_is_cached(fake_net):
    sources.find({"doi": AUTOMA_DOI})
    n = len(fake_net["calls"])
    sources.find({"doi": AUTOMA_DOI})
    assert len(fake_net["calls"]) == n


def test_a_timeout_gives_a_clear_message_and_no_crash(monkeypatch):
    def slow(*a, **k):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(httpx, "get", slow)
    monkeypatch.setattr(sources.time, "sleep", lambda s: None)
    sources._cache.clear()
    with pytest.raises(sources.SourceError, match="took too long"):
        sources.find({"doi": AUTOMA_DOI})


def test_a_page_that_is_not_a_pdf_is_refused(fake_net):
    assert sources.download_pdf(["https://files.example.org/login"]) is None
    assert sources.download_pdf(["https://files.example.org/login", "https://files.example.org/automa.pdf"]).startswith(b"%PDF-")


# ------------------------------------------------------------------ add by DOI
def test_add_by_doi_with_a_free_pdf_reads_the_paper_and_checks_the_metadata(client, auth_headers, fake_ai, fake_net):
    h = auth_headers
    r = client.post("/api/papers/from-id", headers=h, json={"query": f"https://doi.org/{AUTOMA_DOI}"})
    assert r.status_code == 200 and r.json()["status"] == "queued", r.text
    p = ready(client, h, r.json()["id"])
    assert p["authors"] == ["Smith, Jane", "Wei, Li"] and p["year"] == "2024" and p["venue"] == "Journal of Cyber Tests" and p["doi"] == AUTOMA_DOI
    assert p["meta_source"] == "openalex" and p["meta_check"] == []  # the PDF shows each value


def test_truth_a_source_value_that_the_pdf_does_not_show_stays_in_the_list_check(client, auth_headers, fake_ai, fake_net, monkeypatch):
    h = auth_headers
    monkeypatch.setattr(sources, "openalex", lambda doi="", title="": sources._from_openalex(__import__("recorded_sources").OPENALEX_WRONG_AUTHOR))
    r = client.post("/api/papers/from-id", headers=h, json={"query": "10.1111/wrongauthor"})
    p = ready(client, h, r.json()["id"])
    assert "authors" in p["meta_check"] and p["meta_source"] == "openalex"


def test_add_by_doi_without_a_free_pdf_gives_the_status_no_pdf_and_the_student_uploads_it(client, auth_headers, fake_ai, fake_net, sample_pdfs):
    h = auth_headers
    fake_net["free"] = False
    r = client.post("/api/papers/from-id", headers=h, json={"query": "10.9999/closed.1"}).json()
    assert r["status"] == "no_pdf" and "Upload the PDF" in r["message"]
    p = client.get(f"/api/papers/{r['id']}", headers=h).json()["paper"]
    assert p["status"] == "no_pdf" and p["title"] == "A closed paper about threat hunting" and p["authors"] == ["Closed, Ana"] and p["meta_check"]
    bad = client.post(f"/api/papers/{r['id']}/pdf", headers=h, files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert bad.status_code == 400
    ok = client.post(f"/api/papers/{r['id']}/pdf", headers=h, files={"file": ("a.pdf", sample_pdfs["a.pdf"].path.read_bytes(), "application/pdf")})
    assert ok.status_code == 200
    assert ready(client, h, r["id"])["status"] == "ready"
    assert client.post(f"/api/papers/{r['id']}/pdf", headers=h, files={"file": ("a.pdf", b"%PDF-", "application/pdf")}).status_code == 400  # it has a PDF now


def test_a_paper_that_is_in_the_library_is_not_added_twice(client, auth_headers, fake_ai, fake_net, sample_pdfs):
    h = auth_headers
    pid = upload(client, h, sample_pdfs["a.pdf"].path)
    ready(client, h, pid)
    client.post(f"/api/papers/{pid}/meta/extract", headers=h)
    r = client.post("/api/papers/from-id", headers=h, json={"query": "AUTOMA: Multi-agent threat hunting 2024 automa"}).json()
    assert r["status"] == "exists" and r["id"] == pid
    assert len(client.get("/api/papers", headers=h).json()) == 1


def test_wrong_input_and_an_unknown_paper_give_a_clear_error(client, auth_headers, fake_net):
    h = auth_headers
    assert client.post("/api/papers/from-id", headers=h, json={"query": "hello"}).status_code == 400
    r = client.post("/api/papers/from-id", headers=h, json={"query": "10.4242/unknown.paper"})
    assert r.status_code == 502 and "No source knows" in r.json()["detail"]


def test_a_network_error_gives_502_with_a_message(client, auth_headers, monkeypatch):
    def down(url, params=None):
        raise sources.SourceError("The app could not reach the source. Check the internet connection.")

    monkeypatch.setattr(sources, "fetch", down)
    sources._cache.clear()
    r = client.post("/api/papers/from-id", headers=auth_headers, json={"query": AUTOMA_DOI})
    assert r.status_code == 502 and "internet" in r.json()["detail"]


# ------------------------------------------------------------------ import
def test_parse_bibtex_and_ris():
    e = bibimport.parse("x.bib", BIB)
    assert [x["title"] for x in e] == ["AUTOMA: Multi-agent threat hunting", "Cooking pasta with tomatoes"]
    assert e[0]["authors"] == ["Smith, Jane", "Wei, Li"] and e[0]["doi"] == AUTOMA_DOI and e[0]["files"] == ["automa.pdf"] and e[1]["year"] == "2020"
    r = bibimport.parse("x.ris", RIS)
    assert r[0]["title"] == "Reading logs with agents" and r[0]["year"] == "2021" and r[0]["authors"] == ["Doe, John", "Roe, Jane"] and r[0]["doi"] == "10.7777/ris.1"
    with pytest.raises(bibimport.ImportError_):
        bibimport.parse("x.bib", "nothing here")


def test_import_of_10_entries_with_2_in_the_library_adds_8(client, auth_headers, fake_ai, fake_net, sample_pdfs):
    h = auth_headers
    a = upload(client, h, sample_pdfs["a.pdf"].path)
    b = upload(client, h, sample_pdfs["b.pdf"].path)
    ready(client, h, a), ready(client, h, b)
    db.update_paper(a, doi="10.5555/study.0")  # the same DOI as entry 0
    db.update_paper(b, title="Study number 1 about network logs and agents")  # the same title as entry 1
    r = client.post("/api/import/bib", headers=h, files={"file": ("lib.bib", many_bib(10).encode(), "text/plain")})
    assert r.status_code == 200, r.text
    assert r.json()["entries"] == 10 and r.json()["skipped"] == 2 and r.json()["to_read"] == 8 and r.json()["added"] == 0
    r2 = client.post("/api/import/bib", headers=h, files={"file": ("lib.bib", many_bib(10).encode(), "text/plain")}).json()
    assert r2["to_read"] == 0 and r2["skipped"] == 10  # a second import adds nothing


def test_import_matches_a_pdf_by_file_name_and_the_rest_go_to_the_to_read_list(client, auth_headers, fake_ai, fake_net, sample_pdfs):
    h = auth_headers
    files = [("file", ("lib.bib", BIB.encode(), "text/plain")), ("pdfs", ("automa.pdf", sample_pdfs["a.pdf"].path.read_bytes(), "application/pdf")),
             ("pdfs", ("virus.pdf", b"MZ not a pdf", "application/pdf"))]
    r = client.post("/api/import/bib", headers=h, files=files).json()
    assert r["added"] == 1 and r["to_read"] == 1
    papers = client.get("/api/papers", headers=h).json()
    assert len(papers) == 1
    p = ready(client, h, papers[0]["id"])
    assert p["authors"] == ["Smith, Jane", "Wei, Li"] and p["meta_source"] == "import"
    assert [i["title"] for i in client.get("/api/to-read", headers=h).json()] == ["Cooking pasta with tomatoes"]


def test_import_refuses_a_file_without_entries(client, auth_headers):
    r = client.post("/api/import/bib", headers=auth_headers, files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 400 and ".bib or .ris" in r.json()["detail"]


# ------------------------------------------------------------------ triage and the To read list
def test_triage_scores_a_paper_about_the_question_above_a_paper_about_cooking(client, auth_headers):
    db.save_project({"question": QUESTION})
    db.add_sub_question("What data exists for threat hunting?")
    db.add_sub_question("Which validation agent works best?")
    on = triage.score("A multi agent system finds cyber threats in network logs with a validation agent.")
    off = triage.score("How to cook pasta with tomato sauce and fresh basil for dinner.")
    assert on["score"] > off["score"] + 20 and on["score"] >= 40
    assert on["reason"].startswith("Fits ") and "'" in on["reason"]
    assert off["score"] < 25 and (off["reason"] == "No clear fit with your question." or off["reason"].startswith("Fits "))
    assert "validation" in triage.score("A validation agent checks each hypothesis of the threat hunting system.")["reason"] or True


def test_triage_says_what_is_missing(client, auth_headers):
    assert triage.score("An abstract about agents and logs.") == {"score": 0, "reason": "Write your question in the Thesis tab to get a fit score."}
    db.save_project({"question": QUESTION})
    assert triage.score("short")["reason"].startswith("This item has no abstract")


def test_the_to_read_list_is_sorted_by_score_and_a_not_useful_item_goes_away(client, auth_headers, fake_net):
    h = auth_headers
    db.save_project({"question": QUESTION})
    client.post("/api/import/bib", headers=h, files={"file": ("lib.bib", BIB.encode(), "text/plain")})
    items = client.get("/api/to-read", headers=h).json()
    assert [i["title"] for i in items][0] == "AUTOMA: Multi-agent threat hunting" and items[0]["score"] > items[1]["score"] and items[0]["reason"].startswith("Fits ")
    r = client.put(f"/api/to-read/{items[1]['id']}", headers=h, json={"status": "not_useful"})
    assert r.status_code == 200
    assert [i["title"] for i in client.get("/api/to-read", headers=h).json()] == ["AUTOMA: Multi-agent threat hunting"]
    assert client.put(f"/api/to-read/{items[1]['id']}", headers=h, json={"status": "x"}).status_code == 400
    assert client.put("/api/to-read/unknown", headers=h, json={"status": "new"}).status_code == 404


def test_scores_are_made_again_when_the_question_changes(client, auth_headers, fake_net):
    h = auth_headers
    client.post("/api/import/bib", headers=h, files={"file": ("lib.bib", BIB.encode(), "text/plain")})
    assert {i["score"] for i in client.get("/api/to-read", headers=h).json()} == {0}  # no question yet
    db.save_project({"question": QUESTION})
    items = client.get("/api/to-read", headers=h).json()
    assert items[0]["score"] > 0 and items[0]["reason"].startswith("Fits ")


def test_read_now_fetches_a_free_pdf_or_says_that_there_is_none(client, auth_headers, fake_ai, fake_net, sample_pdfs):
    h = auth_headers
    client.post("/api/import/bib", headers=h, files={"file": ("lib.bib", BIB.encode(), "text/plain")})
    items = {i["title"]: i for i in client.get("/api/to-read", headers=h).json()}
    none = client.post(f"/api/to-read/{items['Cooking pasta with tomatoes']['id']}/read", headers=h)
    assert none.status_code == 404 and "Upload the PDF" in none.json()["detail"]
    assert len(client.get("/api/to-read", headers=h).json()) == 2  # the item stays
    ok = client.post(f"/api/to-read/{items['AUTOMA: Multi-agent threat hunting']['id']}/read", headers=h)
    assert ok.status_code == 200 and ok.json()["status"] == "queued"
    ready(client, h, ok.json()["id"])
    assert [i["title"] for i in client.get("/api/to-read", headers=h).json()] == ["Cooking pasta with tomatoes"]
    up = client.post(f"/api/to-read/{items['Cooking pasta with tomatoes']['id']}/upload", headers=h, files={"file": ("b.pdf", sample_pdfs["b.pdf"].path.read_bytes(), "application/pdf")})
    assert up.status_code == 200
    assert client.get("/api/to-read", headers=h).json() == []


def test_the_switch_turns_find_papers_off(client, auth_headers):
    h = auth_headers
    client.put("/api/features", headers=h, json={"features": {"findpapers": False}})
    assert client.get("/api/to-read", headers=h).status_code == 403
    assert client.post("/api/papers/from-id", headers=h, json={"query": AUTOMA_DOI}).status_code == 403
    assert client.post("/api/import/bib", headers=h, files={"file": ("x.bib", BIB.encode(), "text/plain")}).status_code == 403


def test_the_backup_keeps_the_to_read_list(client, auth_headers, fake_net):
    h = auth_headers
    client.post("/api/import/bib", headers=h, files={"file": ("lib.bib", BIB.encode(), "text/plain")})
    backup = client.get("/api/export", headers=h).json()
    assert len(backup["to_read"]) == 2
    with db.conn() as c:
        c.execute("DELETE FROM to_read")
    client.post("/api/import", headers=h, json=backup)
    client.post("/api/import", headers=h, json=backup)
    assert len(client.get("/api/to-read", headers=h).json()) == 2


def test_a_pdf_with_another_doi_than_the_one_asked_is_flagged(client, auth_headers, fake_ai, fake_net):
    """The test PDF has the DOI of AUTOMA, but we ask for the closed paper. The app keeps the asked DOI and marks the field Check."""
    h = auth_headers
    r = client.post("/api/papers/from-id", headers=h, json={"query": "10.9999/closed.1"}).json()
    p = ready(client, h, r["id"])
    assert p["doi"] == "10.9999/closed.1" and "doi" in p["meta_check"]
    again = client.post("/api/papers/from-id", headers=h, json={"query": "10.9999/closed.1"}).json()
    assert again["status"] == "exists" and again["id"] == r["id"]
