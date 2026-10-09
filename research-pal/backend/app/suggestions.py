"""Suggest the next papers (Sprint 11). The app looks at the references and the citations of the papers of the library (OpenAlex).
A paper that many of your papers cite, or that cites many of your papers, is a good candidate.
Score = 60% links to your library + 40% fit to your question (triage of Sprint 10). The reason says what is true: "Cited by 4 of your papers".
Suggestions go to the To read list with the source "suggested". A paper that is in the library, or was in the list before (also a "not useful" one), is not suggested again."""
import time

from . import db, sources, triage

MAX_LIBRARY_PAPERS = 25
MAX_CANDIDATES = 30
POINTS_PER_LINK = 30
LINK_WEIGHT, FIT_WEIGHT = 0.6, 0.4
EVERY_SECONDS = 24 * 60 * 60


def _reason(cited_by: int, cites: int, fit: str) -> str:
    parts = []
    if cited_by:
        parts.append(f"Cited by {cited_by} of your papers")
    if cites:
        parts.append(f"Cites {cites} of your papers")
    if fit.startswith("Fits "):
        parts.append(fit)
    return ". ".join(parts) if parts else "Related to your papers."


def refresh() -> dict:
    """Find candidates and add them to the To read list. Returns {"added": n, "message": str}."""
    papers = [p for p in db.list_papers() if (p.get("doi") or "").strip()][:MAX_LIBRARY_PAPERS]
    if not papers:
        return {"added": 0, "message": "Suggestions need papers with a DOI. Add papers with a DOI, or check the DOI in the metadata of a card."}
    lib_ids: set[str] = set()
    cited_by_lib: dict[str, int] = {}  # a candidate that your papers cite
    cites_lib: dict[str, int] = {}  # a candidate that cites your papers
    errors = 0
    for p in papers:
        try:
            w = sources.openalex(doi=p["doi"].strip().lower())
            if not w or not w.get("openalex_id"):
                continue
            lib_ids.add(w["openalex_id"])
            for r in set(w.get("references") or []):
                cited_by_lib[r] = cited_by_lib.get(r, 0) + 1
            for c in set(sources.openalex_cited_by(w["openalex_id"])):
                cites_lib[c] = cites_lib.get(c, 0) + 1
        except sources.SourceError:
            errors += 1
    if errors == len(papers):
        return {"added": 0, "message": "The sources did not answer. Try again later."}
    ids = (set(cited_by_lib) | set(cites_lib)) - lib_ids
    links = {i: cited_by_lib.get(i, 0) + cites_lib.get(i, 0) for i in ids}
    top = sorted(ids, key=lambda i: (-links[i], i))[:MAX_CANDIDATES]
    try:
        works = sources.openalex_works(top)
    except sources.SourceError:
        return {"added": 0, "message": "The sources did not answer. Try again later."}
    tg = triage.targets()
    added = 0
    for w in works:
        if not w["title"] or db.paper_exists(w["doi"], w["title"]):
            continue
        fit = triage.score(w["abstract"] or w["title"], tg)
        link_score = min(100, POINTS_PER_LINK * links.get(w["openalex_id"], 0))
        item = {**w, "score": round(LINK_WEIGHT * link_score + FIT_WEIGHT * fit["score"]), "source": "suggested",
                "reason": _reason(cited_by_lib.get(w["openalex_id"], 0), cites_lib.get(w["openalex_id"], 0), fit["reason"])}
        old = db.to_read_find(w["doi"], w["title"])
        if old is None:
            db.to_read_add(item)
            added += 1
        elif old["source"] == "suggested" and old["status"] == "new":  # the daily run updates the score of a suggestion that you did not rate
            db.to_read_set(old["id"], score=item["score"], reason=item["reason"])
    db.set_setting("suggest_last", str(time.time()))
    return {"added": added, "message": f"{added} new {'suggestion' if added == 1 else 'suggestions'} in your To read list." if added else "No new suggestion now."}


def due() -> bool:
    try:
        return time.time() - float(db.get_setting("suggest_last") or 0) > EVERY_SECONDS
    except ValueError:
        return True


def run_if_due() -> None:
    """Called in the background. Once a day. A problem here never stops the app."""
    if due():
        db.set_setting("suggest_last", str(time.time()))  # set first: two calls at once do one run
        try:
            refresh()
        except Exception:
            import logging

            logging.getLogger("research_pal").exception("Suggestions failed")
