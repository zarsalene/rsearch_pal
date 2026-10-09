"""Sprint 08: metadata of the papers, BibTeX, RIS and citations."""
import io
import json
import re

from app import cite, db, metadata
from helpers import upload, wait_ready
from pdfs import PAPERS

META_AI = "You read the first page of a research paper"


def paper(**kw):
    return {"id": "abcdef123456", "title": "Validation agents", "filename": "v.pdf", "authors": [], "year": "", "venue": "", "doi": "", "cite_key": "", **kw}


def read(client, h, sample_pdfs, name="a.pdf"):
    pid = upload(client, h, sample_pdfs[name].path)
    wait_ready(client, h, pid)
    return pid


def test_authors_are_written_as_surname_first():
    assert cite.parse_author("Jane Smith") == "Smith, Jane"
    assert cite.parse_author("Smith, Jane") == "Smith, Jane"
    assert cite.parse_author("Jean Paul van Dijk") == "Dijk, Jean Paul van" or cite.surname(cite.parse_author("Jean Paul van Dijk")) == "Dijk"
    assert cite.parse_author("Plato") == "Plato" and cite.initials("Smith, Jane Mary") == "J. M."


def test_cite_apa_with_1_2_and_3_or_more_authors():
    one, two, three = (paper(authors=a, year="2024") for a in (["Smith, Jane"], ["Smith, Jane", "Wei, Li"], ["Smith, Jane", "Wei, Li", "Roe, Max"]))
    assert cite.cite(one, 3)["text"] == "(Smith, 2024, p. 3)"
    assert cite.cite(two, 3)["text"] == "(Smith & Wei, 2024, p. 3)"
    assert cite.cite(three, 3)["text"] == "(Smith et al., 2024, p. 3)" and cite.cite(three, 3)["complete"] is True
    assert cite.cite(three)["text"] == "(Smith et al., 2024)"  # no page


def test_cite_ieee_and_missing_data():
    p = paper(authors=["Smith, Jane"], year="2024")
    assert cite.cite(p, 3, "ieee", 7)["text"] == "[7, p. 3]"
    assert cite.cite(paper(), 2)["text"] == '("Validation agents", n.d., p. 2)' and cite.cite(paper(), 2)["complete"] is False  # the student must check
    try:
        cite.cite(p, 1, "chicago")
        raise AssertionError("must fail")
    except ValueError:
        pass


def parse_bibtex(text):
    entries = {}
    for m in re.finditer(r"@(\w+)\{([^,]+),\n(.*?)\n\}", text, re.S):
        fields = dict(re.findall(r"^\s*(\w+) = \{(.*)\},?$", m.group(3), re.M))
        entries[m.group(2)] = {"type": m.group(1), **fields}
    return entries


def parse_ris(text):
    out, cur = [], {}
    for line in text.splitlines():
        tag, _, val = line.partition("  - ")
        if tag == "ER":
            out.append(cur)
            cur = {}
        elif tag:
            cur.setdefault(tag, []).append(val)
    return out


def test_bibtex_and_ris_are_valid_when_parsed_again():
    papers = [paper(authors=["Smith, Jane", "Wei, Li"], year="2024", venue="Journal of Tests", doi="10.1234/x.1", cite_key="smith2024validation", title="Cats & dogs: 100% safe"),
              paper(id="zzzzzz999999", title="No data", cite_key="")]
    bib = parse_bibtex(cite.to_bibtex(papers))
    a = bib["smith2024validation"]
    assert a["type"] == "article" and a["author"] == "Smith, Jane and Wei, Li" and a["year"] == "2024" and a["journal"] == "Journal of Tests" and a["doi"] == "10.1234/x.1"
    assert "\\&" in a["title"] and "\\%" in a["title"]  # special characters are escaped
    assert bib["paperzzzzzz"]["type"] == "misc" and "year" not in bib["paperzzzzzz"]
    ris = parse_ris(cite.to_ris(papers))
    assert ris[0]["TY"] == ["JOUR"] and ris[0]["AU"] == ["Smith, Jane", "Wei, Li"] and ris[0]["PY"] == ["2024"] and ris[0]["DO"] == ["10.1234/x.1"]
    assert ris[1]["TY"] == ["GEN"] and ris[1]["TI"] == ["No data"]
    assert cite.to_bibtex([]) == "" and cite.to_ris([]) == ""
    twice = cite.to_bibtex([paper(cite_key="same"), paper(id="b" * 12, cite_key="same")])
    assert len(parse_bibtex(twice)) == 2  # two papers with one key: the second key is changed


def test_references():
    p = paper(authors=["Smith, Jane", "Wei, Li"], year="2024", venue="Journal of Tests", doi="10.1234/x.1")
    assert cite.reference(p) == "Smith, J., & Wei, L. (2024). Validation agents. Journal of Tests. https://doi.org/10.1234/x.1"
    assert cite.reference(p, "ieee", 4).startswith('[4] J. Smith, L. Wei, "Validation agents,"')


# ------------------------------------------------------------------ the metadata of a paper
def test_metadata_is_read_and_checked_against_the_pdf(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    r = client.post(f"/api/papers/{pid}/meta/extract", headers=h)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["authors"] == ["Smith, Jane", "Wei, Li"] and p["year"] == "2024" and p["venue"] == "Journal of Cyber Tests"
    assert p["doi"] == "10.1234/automa.2024.01" and p["cite_key"] == "smith2024automa" and p["meta_check"] == [] and p["meta_source"] == "ai"
    assert client.get(f"/api/papers/{pid}", headers=h).json()["paper"]["year"] == "2024"


def test_truth_a_year_that_the_pdf_does_not_have_is_not_saved(client, auth_headers, fake_ai, sample_pdfs):
    """The fake AI says 2019. The PDF says 2024. The year is not saved, and the field shows "Check"."""
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    fake_ai.when(META_AI, {"authors": ["Jane Smith", "John Nobody"], "year": "2019", "venue": "The Journal of Invented Things"})
    p = client.post(f"/api/papers/{pid}/meta/extract", headers=h).json()
    assert p["year"] == "" and "year" in p["meta_check"]
    assert p["venue"] == "" and "venue" in p["meta_check"]  # not in the PDF
    assert p["authors"] == ["Smith, Jane"] and "authors" in p["meta_check"]  # "John Nobody" is not in the PDF: dropped, and the field says Check
    assert p["doi"] == "10.1234/automa.2024.01" and "doi" not in p["meta_check"]  # a rule found it
    assert p["cite_key"].startswith("paper")  # no year: no key from the data
    assert cite.cite(db.get_paper(pid), 2)["complete"] is False  # a citation says so


def test_a_paper_without_metadata_shows_check_for_each_field(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid = read(client, h, sample_pdfs, "b.pdf")
    p = client.post(f"/api/papers/{pid}/meta/extract", headers=h).json()
    assert p["authors"] == [] and p["year"] == "" and sorted(p["meta_check"]) == ["authors", "doi", "venue", "year"]


def test_the_student_edits_the_metadata_and_a_new_reading_keeps_it(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    client.post(f"/api/papers/{pid}/meta/extract", headers=h)
    p = client.put(f"/api/papers/{pid}/meta", headers=h, json={"year": "2023", "authors": ["Jane Smith"], "doi": "https://doi.org/10.1234/new.9"}).json()
    assert p["year"] == "2023" and p["authors"] == ["Smith, Jane"] and p["doi"] == "10.1234/new.9" and p["meta_source"] == "student"
    q = client.post(f"/api/papers/{pid}/meta/extract", headers=h).json()
    assert q["year"] == "2023" and q["authors"] == ["Smith, Jane"] and q["venue"] == "Journal of Cyber Tests"  # the empty field is filled, the edit stays
    for bad in ({"year": "24"}, {"doi": "no doi"}, {"authors": ["x" * 101]}, {"authors": ["A B"] * 31}):
        assert client.put(f"/api/papers/{pid}/meta", headers=h, json=bad).status_code == 400
    assert client.put("/api/papers/nope/meta", headers=h, json={"year": "2020"}).status_code == 404


def test_the_cite_keys_are_unique(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    a, a2 = read(client, h, sample_pdfs), read(client, h, sample_pdfs)
    keys = [client.post(f"/api/papers/{p}/meta/extract", headers=h).json()["cite_key"] for p in (a, a2)]
    assert keys == ["smith2024automa", "smith2024automa2"]


def test_export_and_cite_endpoints(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    a, b = read(client, h, sample_pdfs, "a.pdf"), read(client, h, sample_pdfs, "b.pdf")
    client.post(f"/api/papers/{a}/meta/extract", headers=h)
    bib = client.get("/api/export/bibtex", headers=h)
    assert bib.status_code == 200 and "attachment" in bib.headers["content-disposition"] and set(parse_bibtex(bib.text)) == {"smith2024automa", f"paper{b[:6]}"}
    ris = client.get("/api/export/ris", headers=h)
    assert len(parse_ris(ris.text)) == 2
    assert client.get(f"/api/papers/{a}/cite", headers=h, params={"page": 3}).json() == {"text": "(Smith & Wei, 2024, p. 3)", "complete": True, "style": "apa"}
    assert client.get(f"/api/papers/{a}/cite", headers=h, params={"page": 3, "style": "ieee"}).json()["text"] == "[1, p. 3]"
    nb = client.get(f"/api/papers/{b}/cite", headers=h, params={"page": 2}).json()
    assert nb["complete"] is False and "n.d." in nb["text"]
    assert client.get(f"/api/papers/{a}/cite", headers=h, params={"style": "x"}).status_code == 400
    assert client.get("/api/export/bibtex").status_code == 401
    client.put("/api/features", headers=h, json={"features": {"cite": False}})
    assert client.get("/api/export/ris", headers=h).status_code == 403 and client.post(f"/api/papers/{a}/meta/extract", headers=h).status_code == 403


def test_backup_keeps_the_metadata(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid = read(client, h, sample_pdfs)
    client.post(f"/api/papers/{pid}/meta/extract", headers=h)
    backup = client.get("/api/export", headers=h).json()
    assert json.loads(backup["papers"][0]["meta"]["authors"]) == ["Smith, Jane", "Wei, Li"]
    client.delete(f"/api/papers/{pid}", headers=h)
    client.post("/api/import", headers=h, json=backup)
    p = client.get(f"/api/papers/{pid}", headers=h).json()["paper"]
    assert p["year"] == "2024" and p["authors"] == ["Smith, Jane", "Wei, Li"] and p["cite_key"] == "smith2024automa"
    assert PAPERS["a.pdf"][0].startswith("AUTOMA")
