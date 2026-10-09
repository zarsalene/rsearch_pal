"""Find papers from free sources (Sprint 10): OpenAlex, arXiv, Unpaywall and Semantic Scholar.
The student gives a DOI, an arXiv link or a title. We find the metadata and a free PDF.
Rules:
- Each call has a timeout, a retry and a cache. A call that fails gives a clear message, never a crash.
- Metadata from a source has a label (the name of the source). The app checks it again against the PDF when the PDF is there.
- All calls go through `fetch`. The tests replace it with recorded answers, so CI makes no network call."""
import os
import re
import time
import xml.etree.ElementTree as ET

import httpx

from . import config

TIMEOUT = 15
RETRIES = 2
CACHE_SECONDS = 60 * 60
MAX_PDF_BYTES = config.MAX_UPLOAD_BYTES
USER_AGENT = "ResearchPal/1.0 (student reading tool)"

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.I)
ARXIV_RE = re.compile(r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:\s*)((?:\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?)", re.I)
ARXIV_BARE = re.compile(r"^(\d{4}\.\d{4,5})(v\d+)?$")
SOURCES = ("openalex", "arxiv", "semanticscholar")


class SourceError(Exception):
    """A source did not work, or the input is wrong. The message is for the user."""


_cache: dict[tuple, tuple[float, tuple]] = {}


def contact_email() -> str:
    return os.getenv("CONTACT_EMAIL", "").strip()


def fetch(url: str, params: dict | None = None) -> tuple[int, str, bytes]:
    """(status, content type, body). Retry on a timeout or a server error. The tests replace this function."""
    last = "The source did not answer."
    for attempt in range(RETRIES + 1):
        try:
            r = httpx.get(url, params=params, timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT})
        except httpx.TimeoutException:
            last = "The source took too long to answer."
        except httpx.HTTPError:
            last = "The app could not reach the source. Check the internet connection."
        else:
            if r.status_code < 500 and r.status_code != 429:
                return r.status_code, r.headers.get("content-type", ""), r.content
            last = "The source is busy or down. Try again later."
        if attempt < RETRIES:
            time.sleep(0.6 * (attempt + 1))
    raise SourceError(last)


def _get(url: str, params: dict | None = None, cache: bool = True) -> tuple[int, str, bytes]:
    key = (url, tuple(sorted((params or {}).items())))
    hit = _cache.get(key)
    if cache and hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    out = fetch(url, params)
    if cache and out[0] == 200:
        _cache[key] = (time.time(), out)
    return out


def _json(url: str, params: dict | None = None):
    import json

    status, _, body = _get(url, params)
    if status == 404:
        return None
    if status != 200:
        raise SourceError(f"The source answered with an error ({status}).")
    try:
        return json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        raise SourceError("The source gave an answer that the app cannot read.")


# ------------------------------------------------------------------ the input of the student
def parse_input(text: str) -> dict:
    """{"doi": ..} or {"arxiv": ..} or {"title": ..}. A DOI or an arXiv id is found inside a link or a sentence."""
    t = " ".join((text or "").split())
    if not t:
        raise SourceError("Type a DOI, an arXiv link or the title of the paper.")
    m = ARXIV_RE.search(t)
    if m:
        return {"arxiv": re.sub(r"v\d+$", "", m.group(1))}
    m = DOI_RE.search(t)
    if m:
        return {"doi": m.group(1).rstrip(".,;)").lower()}
    m = ARXIV_BARE.match(t)
    if m:
        return {"arxiv": m.group(1)}
    if len(t.split()) < 3:
        raise SourceError("This is not a DOI or an arXiv link. For a title, write at least 3 words.")
    return {"title": t[:300]}


# ------------------------------------------------------------------ clients
def _abstract(inv) -> str:
    if not isinstance(inv, dict):
        return ""
    words = {}
    for w, places in inv.items():
        for p in places if isinstance(places, list) else []:
            words[p] = w
    return " ".join(words[i] for i in sorted(words))


def _from_openalex(w: dict) -> dict:
    loc = w.get("best_oa_location") or {}
    urls = [u for u in (loc.get("pdf_url"), (w.get("open_access") or {}).get("oa_url")) if u]
    source = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
    doi = re.sub(r"^https?://doi\.org/", "", w.get("doi") or "", flags=re.I).lower()
    return {"title": (w.get("title") or "").strip(), "authors": [(a.get("author") or {}).get("display_name", "") for a in w.get("authorships") or []],
            "year": str(w.get("publication_year") or ""), "venue": source, "doi": doi, "abstract": _abstract(w.get("abstract_inverted_index")),
            "pdf_urls": urls, "source": "openalex"}


def openalex(doi: str = "", title: str = "") -> dict | None:
    params = {"mailto": contact_email()} if contact_email() else {}
    if doi:
        w = _json(f"https://api.openalex.org/works/doi:{doi}", params)
        return _from_openalex(w) if w else None
    r = _json("https://api.openalex.org/works", {**params, "search": title, "per-page": 1})
    results = (r or {}).get("results") or []
    return _from_openalex(results[0]) if results else None


def semantic_scholar(doi: str = "", title: str = "", arxiv: str = "") -> dict | None:
    fields = "title,year,authors,venue,abstract,openAccessPdf,externalIds"
    if doi or arxiv:
        p = _json(f"https://api.semanticscholar.org/graph/v1/paper/{'DOI:' + doi if doi else 'ARXIV:' + arxiv}", {"fields": fields})
    else:
        r = _json("https://api.semanticscholar.org/graph/v1/paper/search", {"query": title, "limit": 1, "fields": fields})
        data = (r or {}).get("data") or []
        p = data[0] if data else None
    if not p:
        return None
    pdf = (p.get("openAccessPdf") or {}).get("url")
    return {"title": (p.get("title") or "").strip(), "authors": [a.get("name", "") for a in p.get("authors") or []], "year": str(p.get("year") or ""),
            "venue": p.get("venue") or "", "doi": ((p.get("externalIds") or {}).get("DOI") or doi).lower(), "abstract": p.get("abstract") or "",
            "pdf_urls": [pdf] if pdf else [], "source": "semanticscholar"}


def arxiv(arxiv_id: str) -> dict | None:
    status, _, body = _get("https://export.arxiv.org/api/query", {"id_list": arxiv_id})
    if status != 200:
        raise SourceError(f"arXiv answered with an error ({status}).")
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        raise SourceError("arXiv gave an answer that the app cannot read.")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    e = root.find("a:entry", ns)
    if e is None or not (e.findtext("a:title", "", ns) or "").strip() or "Error" in (e.findtext("a:title", "", ns) or ""):
        return None
    clean = lambda s: " ".join((s or "").split())
    return {"title": clean(e.findtext("a:title", "", ns)), "authors": [clean(a.findtext("a:name", "", ns)) for a in e.findall("a:author", ns)],
            "year": (e.findtext("a:published", "", ns) or "")[:4], "venue": "arXiv", "doi": "", "abstract": clean(e.findtext("a:summary", "", ns)),
            "pdf_urls": [f"https://arxiv.org/pdf/{arxiv_id}"], "source": "arxiv"}


def unpaywall(doi: str) -> list[str]:
    """A free PDF from a DOI. It needs an email in CONTACT_EMAIL (the rule of Unpaywall)."""
    if not contact_email():
        return []
    r = _json(f"https://api.unpaywall.org/v2/{doi}", {"email": contact_email()})
    out = []
    for loc in [(r or {}).get("best_oa_location") or {}] + ((r or {}).get("oa_locations") or []):
        if loc.get("url_for_pdf") and loc["url_for_pdf"] not in out:
            out.append(loc["url_for_pdf"])
    return out


# ------------------------------------------------------------------ the main call
def find(query: dict) -> dict:
    """Metadata and the addresses of free PDFs. Raises SourceError when no source knows the paper."""
    found, errors = None, []
    chain = []
    if query.get("arxiv"):
        chain = [lambda: arxiv(query["arxiv"]), lambda: semantic_scholar(arxiv=query["arxiv"])]
    elif query.get("doi"):
        chain = [lambda: openalex(doi=query["doi"]), lambda: semantic_scholar(doi=query["doi"])]
    else:
        chain = [lambda: openalex(title=query["title"]), lambda: semantic_scholar(title=query["title"])]
    for call in chain:
        try:
            found = call()
        except SourceError as e:
            errors.append(str(e))
            continue
        if found and found["title"]:
            break
        found = None
    if not found:
        if errors and len(errors) == len(chain):
            raise SourceError(errors[0])
        raise SourceError("No source knows this paper. Check the DOI or the title, or upload the PDF yourself.")
    found["authors"] = [a for a in found["authors"] if a]
    if query.get("doi") and not found["doi"]:
        found["doi"] = query["doi"]
    if found["doi"] and not found["pdf_urls"]:
        try:
            found["pdf_urls"] = unpaywall(found["doi"])
        except SourceError:
            pass  # Unpaywall is only a help. The paper stays without a PDF.
    return found


def download_pdf(urls: list[str]) -> bytes | None:
    """The first address that gives a real PDF. None if no address works. A page that is not a PDF (a login page) is refused."""
    for url in urls:
        try:
            status, _, body = _get(url, cache=False)
        except SourceError:
            continue
        if status == 200 and body.startswith(b"%PDF-") and 0 < len(body) <= MAX_PDF_BYTES:
            return body
    return None
