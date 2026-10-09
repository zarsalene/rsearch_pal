"""Import of a BibTeX or RIS file (Sprint 10), for example an export of Zotero.
An entry becomes a paper in the library if its PDF is in the upload (matched by file name or DOI). Else it goes to the "To read" list.
An entry that is in the library already (same DOI or same title) is skipped."""
import re
from pathlib import PurePosixPath

from . import cards, cite

MAX_ENTRIES = 500
MAX_FILE_CHARS = 2_000_000


class ImportError_(Exception):
    """Wrong file. The message is for the user."""


def _clean(s: str) -> str:
    s = re.sub(r"\\[\"'`^~=.]\{?(\w)\}?", r"\1", s or "")  # \"u -> u (the accent is dropped, the letter stays)
    s = re.sub(r"[{}]", "", s).replace("\\&", "&").replace("\\_", "_").replace("~", " ")
    return " ".join(s.split())


def _split_authors(s: str) -> list[str]:
    return [cite.parse_author(_clean(a)) for a in re.split(r"\s+and\s+", s or "") if _clean(a)]


def parse_bibtex(text: str) -> list[dict]:
    out, i, n = [], 0, len(text)
    while True:
        m = re.compile(r"@(\w+)\s*[{(]").search(text, i)
        if not m:
            break
        kind = m.group(1).lower()
        depth, j = 1, m.end()
        while j < n and depth:
            c = text[j]
            depth += (c == "{") - (c == "}")
            j += 1
        body = text[m.end() : j - 1]
        i = j
        if kind in ("comment", "string", "preamble"):
            continue
        fields = {}
        for fm in re.finditer(r"(\w+)\s*=\s*", body):
            k, pos = fm.group(1).lower(), fm.end()
            if pos >= len(body):
                continue
            if body[pos] == "{":
                d, q = 1, pos + 1
                while q < len(body) and d:
                    d += (body[q] == "{") - (body[q] == "}")
                    q += 1
                value = body[pos + 1 : q - 1]
            elif body[pos] == '"':
                q = body.find('"', pos + 1)
                value = body[pos + 1 : q if q > 0 else len(body)]
            else:
                value = re.match(r"[^,\s}]*", body[pos:]).group(0)
            fields.setdefault(k, value)
        out.append(_entry(fields))
        if len(out) >= MAX_ENTRIES:
            break
    return [e for e in out if e["title"]]


def _entry(f: dict) -> dict:
    files = [p.strip() for p in re.split(r";", f.get("file", "")) if p.strip()]
    names = []
    for p in files:
        parts = [x for x in re.split(r"(?<!\\):", p) if x]
        path = max(parts, key=len) if parts else p  # Zotero: "Description:path:mime"
        names.append(PurePosixPath(path.replace("\\", "/")).name)
    year = re.search(r"(19|20)\d\d", f.get("year", "") or f.get("date", ""))
    return {"title": _clean(f.get("title", "")), "authors": _split_authors(f.get("author", "")), "year": year.group(0) if year else "",
            "venue": _clean(f.get("journal") or f.get("booktitle") or f.get("publisher") or ""), "doi": re.sub(r"^https?://(dx\.)?doi\.org/", "", _clean(f.get("doi", "")), flags=re.I).lower(),
            "abstract": _clean(f.get("abstract", "")), "files": [x for x in names if x.lower().endswith(".pdf")]}


def parse_ris(text: str) -> list[dict]:
    out, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Z0-9])\s{2}-\s?(.*)$", line)
        if not m:
            continue
        tag, val = m.group(1), m.group(2).strip()
        if tag == "TY":
            cur = {"title": "", "authors": [], "year": "", "venue": "", "doi": "", "abstract": "", "files": []}
        elif cur is None:
            continue
        elif tag in ("TI", "T1") and not cur["title"]:
            cur["title"] = _clean(val)
        elif tag in ("AU", "A1"):
            cur["authors"].append(cite.parse_author(val))
        elif tag in ("PY", "Y1", "DA") and not cur["year"]:
            y = re.search(r"(19|20)\d\d", val)
            cur["year"] = y.group(0) if y else ""
        elif tag in ("JO", "JF", "T2", "JA") and not cur["venue"]:
            cur["venue"] = _clean(val)
        elif tag == "DO":
            cur["doi"] = re.sub(r"^https?://(dx\.)?doi\.org/", "", val, flags=re.I).lower()
        elif tag in ("AB", "N2") and not cur["abstract"]:
            cur["abstract"] = _clean(val)
        elif tag in ("L1", "UR") and val.lower().endswith(".pdf"):
            cur["files"].append(PurePosixPath(val.replace("\\", "/")).name)
        elif tag == "ER":
            out.append(cur)
            cur = None
            if len(out) >= MAX_ENTRIES:
                break
    return [e for e in out if e["title"]]


def parse(name: str, text: str) -> list[dict]:
    if len(text) > MAX_FILE_CHARS:
        raise ImportError_("The file is too large.")
    low = (name or "").lower()
    entries = parse_ris(text) if low.endswith(".ris") else parse_bibtex(text) if low.endswith((".bib", ".bibtex")) else None
    if entries is None:
        entries = parse_bibtex(text) or parse_ris(text)
    if not entries:
        raise ImportError_("The app found no entry in this file. Use a .bib or .ris file.")
    return entries


def match_pdf(entry: dict, pdfs: dict[str, bytes]) -> str | None:
    """The name of the uploaded PDF that belongs to the entry: by the file name in the entry, by the DOI in the name, or by the title in the name."""
    by_lower = {k.lower(): k for k in pdfs}
    for f in entry["files"]:
        if f.lower() in by_lower:
            return by_lower[f.lower()]
    doi_slug = re.sub(r"[^a-z0-9]", "", entry["doi"])
    title_norm = cards.norm(entry["title"])
    for low, name in by_lower.items():
        stem = cards.norm(re.sub(r"\.pdf$", "", low))
        if doi_slug and doi_slug in re.sub(r"[^a-z0-9]", "", low):
            return name
        if title_norm and len(title_norm.split()) >= 3 and (title_norm in stem or stem in title_norm and len(stem.split()) >= 3):
            return name
    return None
