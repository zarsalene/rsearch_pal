"""Citations (Sprint 08): BibTeX, RIS, and a citation with a page number in APA or IEEE style.
The data comes from the metadata of the paper. A field that the server could not find in the PDF is empty, and the citation says so."""
import json
import re

STYLES = ("apa", "ieee")


def authors_of(paper: dict) -> list[str]:
    raw = paper.get("authors") or []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "[]")
        except ValueError:
            raw = []
    return [parse_author(a) for a in raw if str(a).strip()]


def parse_author(name: str) -> str:
    """"Jane Smith" -> "Smith, Jane". "Smith, Jane" stays."""
    name = " ".join(str(name).split())
    if "," in name:
        s, _, g = name.partition(",")
        return f"{s.strip()}, {g.strip()}".strip(", ")
    parts = name.split(" ")
    return f"{parts[-1]}, {' '.join(parts[:-1])}".strip(", ") if len(parts) > 1 else name


def surname(author: str) -> str:
    return author.split(",")[0].strip()


def initials(author: str) -> str:
    given = author.partition(",")[2].strip()
    return " ".join(f"{p[0]}." for p in re.split(r"[\s\-]+", given) if p)


def short_title(paper: dict, n: int = 5) -> str:
    return " ".join((paper.get("title") or paper.get("filename") or "Untitled").split()[:n])


def cite(paper: dict, page: int | None = None, style: str = "apa", number: int | None = None) -> dict:
    """A citation with a page. complete=False means that the author or the year is not known: the student must check it."""
    if style not in STYLES:
        raise ValueError("The style must be apa or ieee.")
    authors, year = authors_of(paper), (paper.get("year") or "").strip()
    pg = f", p. {page}" if page else ""
    if style == "ieee":
        text = f"[{number if number else '?'}{pg}]"
        return {"text": text, "complete": bool(number), "style": style}
    names = [surname(a) for a in authors]
    who = names[0] if len(names) == 1 else f"{names[0]} & {names[1]}" if len(names) == 2 else f"{names[0]} et al." if names else f"\"{short_title(paper)}\""
    return {"text": f"({who}, {year or 'n.d.'}{pg})", "complete": bool(authors and year), "style": style}


def reference(paper: dict, style: str = "apa", number: int | None = None) -> str:
    authors, year = authors_of(paper), (paper.get("year") or "").strip() or "n.d."
    title, venue, doi = (paper.get("title") or paper.get("filename") or "Untitled").strip(), (paper.get("venue") or "").strip(), (paper.get("doi") or "").strip()
    link = f" https://doi.org/{doi}" if doi else ""
    if style == "ieee":
        who = ", ".join(f"{initials(a)} {surname(a)}".strip() for a in authors) or "Unknown author"
        return f"[{number}] {who}, \"{title},\"{' ' + venue + ',' if venue else ''} {year}.{link}".replace(" ,", ",")
    names = [f"{surname(a)}, {initials(a)}".strip(", ") for a in authors]
    who = names[0] if len(names) == 1 else (", ".join(names[:-1]) + ", & " + names[-1]) if names else "Unknown author"
    return f"{who} ({year}). {title}.{' ' + venue + '.' if venue else ''}{link}"


def _bib(text: str) -> str:
    return re.sub(r"([&%$#_])", r"\\\1", str(text)).replace("{", "\\{").replace("}", "\\}")


def to_bibtex(papers: list[dict]) -> str:
    out, used = [], set()
    for p in papers:
        key = p.get("cite_key") or f"paper{p['id'][:6]}"
        while key in used:
            key += "x"
        used.add(key)
        fields = []
        authors = authors_of(p)
        if authors:
            fields.append(("author", " and ".join(authors)))
        fields.append(("title", "{" + _bib(p.get("title") or p.get("filename") or "Untitled") + "}"))
        if p.get("year"):
            fields.append(("year", p["year"]))
        if p.get("venue"):
            fields.append(("journal", _bib(p["venue"])))
        if p.get("doi"):
            fields.append(("doi", p["doi"]))
        kind = "article" if p.get("venue") else "misc"
        body = ",\n".join(f"  {k} = {{{v}}}" if k != "title" else f"  {k} = {v}" for k, v in fields)
        out.append(f"@{kind}{{{key},\n{body}\n}}")
    return "\n\n".join(out) + ("\n" if out else "")


def to_ris(papers: list[dict]) -> str:
    out = []
    for p in papers:
        lines = ["TY  - JOUR" if p.get("venue") else "TY  - GEN"]
        lines += [f"AU  - {a}" for a in authors_of(p)]
        lines.append(f"TI  - {p.get('title') or p.get('filename') or 'Untitled'}")
        if p.get("year"):
            lines.append(f"PY  - {p['year']}")
        if p.get("venue"):
            lines.append(f"JO  - {p['venue']}")
        if p.get("doi"):
            lines.append(f"DO  - {p['doi']}")
        lines.append("ER  - ")
        out.append("\n".join(lines))
    return "\n".join(out) + ("\n" if out else "")
