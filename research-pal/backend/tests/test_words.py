"""Word helper (A4) and glossary. A definition of the paper comes from the PDF. Without it, the AI explains and the answer has the label "AI explanation"."""
from app import db as db_mod, llm, words
from helpers import upload, wait_ready

DEFINE_AI = "You explain a word or a short term"  # the start of the prompt of the word helper


def one_page(*sentences):
    return [" ".join(sentences)]


def test_find_a_definition_in_the_text():
    cases = {
        "hypothesis": ("The agent tests it. A hypothesis is a short claim about an attack.", "A hypothesis is a short claim"),
        "recall": ("Recall refers to the share of attacks that the system finds.", "Recall refers to"),
        "BERT": ("We use Bidirectional Encoder Representations from Transformers (BERT) for the text.", "(BERT)"),
        "OpTC": ("The OpTC (Operationally Transparent Cyber) dataset has many logs.", "Operationally Transparent"),
        "baseline": ("We call this method the baseline of the study.", "We call this method the baseline"),
        "F1": ("The score is called F1 in the paper.", "called F1"),
        "ATT&CK": ("MITRE ATT&CK is a public knowledge base of attack techniques.", "ATT&CK is a public"),
    }
    for term, (text, expect) in cases.items():
        got = words.find_definition(one_page(text), term)
        assert got and expect in got["text"] and got["page"] == 1, (term, got)


def test_a_sentence_that_only_uses_the_word_is_not_a_definition():
    text = one_page("The hypothesis agent reads the logs.", "The baseline reaches 72.0 percent precision.", "We did not use recall here.")
    for term in ("hypothesis", "baseline", "recall", "precision"):
        assert words.find_definition(text, term) is None, term


def test_the_first_best_definition_wins_and_the_page_is_right():
    book = ["Nothing here.", "We define the baseline as the best old method. A baseline is a method for a comparison."]
    got = words.find_definition(book, "baseline")
    assert got["page"] == 2 and got["text"].startswith("We define the baseline")


def test_bad_terms():
    for bad in ("", " ", "a", "x" * 81, "...", "()"):
        try:
            words.clean_term(bad)
            raise AssertionError(bad)
        except words.WordError:
            pass
    assert words.clean_term('  "Sysmon  logs," ') == "Sysmon logs"


def read(client, h, sample_pdfs):
    pid = upload(client, h, sample_pdfs["a.pdf"].path)
    wait_ready(client, h, pid)
    return pid


def test_a_word_that_the_paper_defines(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs)
    n = len(fake_ai.calls)
    r = client.post(f"/api/papers/{pid}/define", headers=auth_headers, json={"term": "hypothesis"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["label"] == "From the paper" and d["source"] == "paper" and d["page"] == 2 and d["known"] is True
    assert d["explanation"] == "A hypothesis is a short claim about a possible attack."
    assert len(fake_ai.calls) == n  # the paper answers. No AI call.
    assert d["saved_id"] == ""
    assert d["explanation"] in " ".join(sample_pdfs["a.pdf"].pages[1].split())  # the text is in the PDF, on page 2


def test_a_word_that_the_paper_does_not_define(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs)
    fake_ai.when(DEFINE_AI, {"explanation": "An ontology is a map of the ideas of a field."})
    d = client.post(f"/api/papers/{pid}/define", headers=auth_headers, json={"term": "ontology"}).json()
    assert d["label"] == "AI explanation" and d["source"] == "ai" and d["page"] == 0 and d["explanation"].startswith("An ontology is a map")
    assert "<term>ontology</term>" in fake_ai.calls[-1]["user"]


def test_a_word_that_the_paper_uses_but_does_not_define(client, auth_headers, fake_ai, sample_pdfs):
    """The AI gets the sentences of the paper as context. The answer has the label "AI explanation"."""
    pid = read(client, auth_headers, sample_pdfs)
    d = client.post(f"/api/papers/{pid}/define", headers=auth_headers, json={"term": "Sysmon"}).json()
    assert d["label"] == "AI explanation" and d["mentions"] and d["mentions"][0]["page"] == 2
    assert "[page 2]" in fake_ai.calls[-1]["user"] and "Sysmon" in fake_ai.calls[-1]["user"]


def test_the_ai_explanation_passes_the_simple_check(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs)
    long = "An ontology is a formal map of the ideas of a field of study and it also shows how each idea links to the other ideas of the field."
    fake_ai.when(DEFINE_AI, {"explanation": long})
    fake_ai.when("technical editor", {"explanation": "An ontology is a map of ideas. It shows how each idea links to the others."})
    d = client.post(f"/api/papers/{pid}/define", headers=auth_headers, json={"term": "ontology"}).json()
    assert d["explanation"] == "An ontology is a map of ideas. It shows how each idea links to the others."


def test_the_ai_does_not_know_the_term(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs)
    fake_ai.when(DEFINE_AI, {"explanation": words.UNKNOWN})
    d = client.post(f"/api/papers/{pid}/define", headers=auth_headers, json={"term": "zzqx"}).json()
    assert d["known"] is False and d["mentions"] == []
    assert client.post("/api/glossary", headers=auth_headers, json={"term": "zzqx", "paper_id": pid}).status_code == 400  # nothing to save


def test_bad_define_requests(client, auth_headers, fake_ai, sample_pdfs):
    pid = read(client, auth_headers, sample_pdfs)
    assert client.post(f"/api/papers/{pid}/define", headers=auth_headers, json={"term": "a"}).status_code == 400
    assert client.post("/api/papers/nope/define", headers=auth_headers, json={"term": "ontology"}).status_code == 404
    assert client.post(f"/api/papers/{pid}/define", json={"term": "ontology"}).status_code == 401
    fake_ai.when(DEFINE_AI, llm.LLMError("The AI is down."))
    assert client.post(f"/api/papers/{pid}/define", headers=auth_headers, json={"term": "ontology"}).status_code == 502


def test_glossary(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    assert client.get("/api/glossary", headers=h).json() == []
    # the page can send only the term and the paper. It cannot send an explanation or a source.
    r = client.post("/api/glossary", headers=h, json={"term": "hypothesis", "paper_id": pid, "explanation": "A lie.", "source": "paper", "page": 9})
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["term"] == "hypothesis" and g["source"] == "paper" and g["label"] == "From the paper" and g["page"] == 2 and "A lie." not in g["explanation"]
    assert g["paper_title"] == sample_pdfs["a.pdf"].title
    again = client.post("/api/glossary", headers=h, json={"term": "Hypothesis", "paper_id": pid}).json()
    assert again["id"] == g["id"]  # the same word, one row
    fake_ai.when(DEFINE_AI, {"explanation": "An ontology is a map of ideas."})
    ai = client.post("/api/glossary", headers=h, json={"term": "ontology", "paper_id": pid}).json()
    assert ai["source"] == "ai" and ai["label"] == "AI explanation"
    assert [x["term"] for x in client.get("/api/glossary", headers=h).json()] == ["hypothesis", "ontology"]  # in the order of the alphabet
    assert [x["term"] for x in client.get("/api/glossary", headers=h, params={"q": "MAP"}).json()] == ["ontology"]
    assert client.post(f"/api/papers/{pid}/define", headers=h, json={"term": "hypothesis"}).json()["saved_id"] == g["id"]
    assert client.delete(f"/api/glossary/{g['id']}", headers=h).status_code == 200
    assert client.delete(f"/api/glossary/{g['id']}", headers=h).status_code == 404
    assert client.post("/api/glossary", headers=h, json={"term": "ontology", "paper_id": "nope"}).status_code == 404
    assert client.get("/api/glossary").status_code == 401


def test_a_word_stays_when_its_paper_goes(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    client.post("/api/glossary", headers=h, json={"term": "hypothesis", "paper_id": pid})
    client.delete(f"/api/papers/{pid}", headers=h)
    rows = client.get("/api/glossary", headers=h).json()
    assert [r["term"] for r in rows] == ["hypothesis"] and rows[0]["paper_title"] == ""


def test_the_switch_turns_the_glossary_off(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    client.put("/api/features", headers=h, json={"features": {"glossary": False}})
    assert client.post(f"/api/papers/{pid}/define", headers=h, json={"term": "hypothesis"}).status_code == 403
    assert client.get("/api/glossary", headers=h).status_code == 403


def test_backup_keeps_the_glossary(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    g = client.post("/api/glossary", headers=h, json={"term": "hypothesis", "paper_id": pid}).json()
    backup = client.get("/api/export", headers=h).json()
    assert [x["id"] for x in backup["glossary"]] == [g["id"]]
    client.delete(f"/api/glossary/{g['id']}", headers=h)
    client.post("/api/import", headers=h, json=backup)
    client.post("/api/import", headers=h, json=backup)  # a second import adds nothing
    rows = client.get("/api/glossary", headers=h).json()
    assert [(r["id"], r["explanation"]) for r in rows] == [(g["id"], g["explanation"])]
    assert db_mod.glossary_find("hypothesis", pid)["source"] == "paper"
