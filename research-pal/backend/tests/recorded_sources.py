"""Recorded answers of the free sources (OpenAlex, arXiv, Unpaywall, Semantic Scholar). CI makes no network call: `fake_net` serves these answers."""
import json

AUTOMA_DOI = "10.1234/automa.2024.01"

OPENALEX_AUTOMA = {
    "id": "https://openalex.org/W100", "referenced_works": ["https://openalex.org/W201", "https://openalex.org/W202", "https://openalex.org/W203"],
    "title": "AUTOMA: Multi-agent threat hunting", "publication_year": 2024, "doi": f"https://doi.org/{AUTOMA_DOI}",
    "authorships": [{"author": {"display_name": "Jane Smith"}}, {"author": {"display_name": "Li Wei"}}],
    "primary_location": {"source": {"display_name": "Journal of Cyber Tests"}},
    "best_oa_location": {"pdf_url": "https://files.example.org/automa.pdf"}, "open_access": {"oa_url": "https://files.example.org/automa.html"},
    "abstract_inverted_index": {"We": [0], "present": [1], "AUTOMA,": [2], "a": [3], "multi": [4], "agent": [5], "system": [6], "for": [7], "cyber": [8], "threat": [9], "hunting.": [10]},
}
# A paper with a wrong author: the PDF does not name this person. The app must flag the field.
OPENALEX_WRONG_AUTHOR = {**OPENALEX_AUTOMA, "authorships": [{"author": {"display_name": "Nobody Atall"}}]}
OPENALEX_NO_PDF = {
    "id": "https://openalex.org/W101", "referenced_works": ["https://openalex.org/W201", "https://openalex.org/W203"],
    "title": "A closed paper about threat hunting", "publication_year": 2023, "doi": "https://doi.org/10.9999/closed.1",
    "authorships": [{"author": {"display_name": "Ana Closed"}}], "primary_location": {"source": {"display_name": "Closed Journal"}},
    "best_oa_location": None, "open_access": {}, "abstract_inverted_index": {"A": [0], "closed": [1], "study": [2], "of": [3], "threat": [4], "hunting": [5], "agents.": [6]},
}
UNPAYWALL_EMPTY = {"best_oa_location": None, "oa_locations": []}
UNPAYWALL_FREE = {"best_oa_location": {"url_for_pdf": "https://repo.example.org/closed.pdf"}, "oa_locations": []}

ARXIV_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title>Attention for logs
 in security</title><summary>We use attention to read security logs.</summary>
<published>2023-05-04T10:00:00Z</published><author><name>Ada Lovelace</name></author><author><name>Alan Turing</name></author>
</entry></feed>""".encode()
ARXIV_NOT_FOUND = b"""<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>"""

S2_AUTOMA = {"title": "AUTOMA: Multi-agent threat hunting", "year": 2024, "authors": [{"name": "Jane Smith"}, {"name": "Li Wei"}], "venue": "Journal of Cyber Tests",
             "abstract": "We present AUTOMA.", "openAccessPdf": {"url": "https://files.example.org/automa.pdf"}, "externalIds": {"DOI": AUTOMA_DOI}}

BIB = r"""
@article{smith2024,
  title = {{AUTOMA}: Multi-agent threat hunting},
  author = {Smith, Jane and Wei, Li},
  year = {2024}, journal = {Journal of Cyber Tests}, doi = {10.1234/automa.2024.01},
  abstract = {We present AUTOMA, a multi agent system for cyber threat hunting.},
  file = {Full Text:files/12/automa.pdf:application/pdf}
}
@article{pasta2020,
  title = "Cooking pasta with tomatoes", author = "Rossi, Mario", year = 2020, journal = {Kitchen Notes},
  abstract = {How to cook pasta with tomato sauce and basil for dinner.}
}
"""


def many_bib(n: int) -> str:
    return "\n".join(f"@article{{k{i}, title = {{Study number {i} about network logs and agents}}, author = {{Doe, John}}, year = {{2022}}, doi = {{10.5555/study.{i}}}, abstract = {{Network logs and agents in study {i}.}}}}" for i in range(n))


RIS = """TY  - JOUR
TI  - Reading logs with agents
AU  - Doe, John
AU  - Roe, Jane
PY  - 2021///
JO  - Log Journal
DO  - 10.7777/ris.1
AB  - Agents read network logs.
ER  -
"""


def _work(wid: str, title: str, doi: str, abstract: str) -> dict:
    inv = {w: [i] for i, w in enumerate(abstract.split())}
    return {"id": f"https://openalex.org/{wid}", "title": title, "publication_year": 2022, "doi": f"https://doi.org/{doi}" if doi else None,
            "authorships": [{"author": {"display_name": "Ann Author"}}], "primary_location": {"source": {"display_name": "Some Journal"}},
            "best_oa_location": None, "open_access": {}, "abstract_inverted_index": inv, "referenced_works": []}


# The candidates of the suggestions. W201 is cited by both library papers. W301 cites both. W202 is in the library already (same DOI).
CANDIDATES = {
    "W201": _work("W201", "Hunting threats with agents in network logs", "10.2000/w201", "Agents hunt cyber threats in network logs"),
    "W202": _work("W202", "A paper that you have already", AUTOMA_DOI, "Already in the library"),
    "W203": _work("W203", "Cooking pasta with tomatoes", "10.2000/w203", "How to cook pasta with tomato sauce and basil"),
    "W301": _work("W301", "Validation agents for threat hunting", "10.2000/w301", "A validation agent checks each hypothesis of a threat hunting system"),
}
CITED_BY = {"W100": ["W301", "W9"], "W101": ["W301"]}  # W9 is not in CANDIDATES: OpenAlex gives no record for it


def route(url: str, params: dict | None, pdf_bytes: bytes, free: bool = True):
    """(status, content type, body) for a recorded call."""
    params = params or {}
    j = lambda o, s=200: (s, "application/json", json.dumps(o).encode())
    if url.startswith("https://api.openalex.org/works/doi:"):
        doi = url.split("doi:")[1]
        if doi == AUTOMA_DOI:
            return j(OPENALEX_AUTOMA)
        if doi == "10.9999/closed.1":
            return j(OPENALEX_NO_PDF)
        if doi == "10.1111/wrongauthor":
            return j(OPENALEX_WRONG_AUTHOR)
        return j({}, 404)
    if url == "https://api.openalex.org/works" and str(params.get("filter", "")).startswith("cites:"):
        return j({"results": [{"id": f"https://openalex.org/{i}"} for i in CITED_BY.get(params["filter"].split(":")[1], [])]})
    if url == "https://api.openalex.org/works" and str(params.get("filter", "")).startswith("openalex:"):
        ids = params["filter"].split(":")[1].split("|")
        return j({"results": [CANDIDATES[i] for i in ids if i in CANDIDATES]})
    if url == "https://api.openalex.org/works":
        q = params.get("search", "").lower()
        return j({"results": [OPENALEX_AUTOMA]} if "automa" in q else {"results": []})
    if url.startswith("https://api.unpaywall.org/v2/"):
        return j(UNPAYWALL_FREE if free and "closed" in url else UNPAYWALL_EMPTY)
    if url == "https://export.arxiv.org/api/query":
        return (200, "application/atom+xml", ARXIV_ATOM if params.get("id_list") == "2305.01234" else ARXIV_NOT_FOUND)
    if url.startswith("https://api.semanticscholar.org/graph/v1/paper/DOI:"):
        return j(S2_AUTOMA if AUTOMA_DOI in url else {}, 200 if AUTOMA_DOI in url else 404)
    if url.startswith("https://api.semanticscholar.org"):
        return j({"data": []})
    if url in ("https://files.example.org/automa.pdf", "https://arxiv.org/pdf/2305.01234", "https://repo.example.org/closed.pdf"):
        return (200, "application/pdf", pdf_bytes)
    if url == "https://files.example.org/login":
        return (200, "text/html", b"<html>Please log in</html>")
    return (404, "text/plain", b"")
