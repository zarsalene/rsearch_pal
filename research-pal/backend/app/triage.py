"""Reading triage (Sprint 10). A fit score from 0 to 100 for a paper that the student did not read yet.
The score compares the abstract (or the title) with the main question and with each sub-question. No AI call: only the embeddings that the app has
and the words that both texts share. The reason says which question fits and with which words, so the student can check it."""
import math
import re

from . import db, vectors

STOP = set("a an the of and or in on for to with by from at as is are be this that these those it its we our can how what which who why when do does did not no into than then there their about between using use used based study paper approach method methods".split())
EMBED_WEIGHT, WORD_WEIGHT = 0.6, 0.4


def words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9][a-z0-9\-]{2,}", (text or "").lower()) if w not in STOP]


def _cos(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def targets() -> list[dict]:
    """The main question and the sub-questions. label: how the reason names them."""
    out = []
    q = (db.thesis_question() or "").strip()
    if q:
        out.append({"label": "your main question", "text": q})
    for i, s in enumerate(db.list_sub_questions(), 1):
        out.append({"label": f"SQ{i}", "text": s["text"]})
    return out


def score(text: str, tgts: list[dict] | None = None) -> dict:
    """{"score": 0-100, "reason": "..."}. text: the abstract, or the title when there is no abstract."""
    tgts = targets() if tgts is None else tgts
    if not tgts:
        return {"score": 0, "reason": "Write your question in the Thesis tab to get a fit score."}
    if len((text or "").split()) < 3:
        return {"score": 0, "reason": "This item has no abstract, so the app cannot rate it."}
    vecs = vectors.embed([text] + [t["text"] for t in tgts])
    doc_words = set(words(text))
    best = None
    for t, v in zip(tgts, vecs[1:]):
        tw = set(words(t["text"]))
        shared = sorted(tw & doc_words, key=lambda w: (-len(w), w))
        overlap = len(shared) / len(tw) if tw else 0.0
        fit = EMBED_WEIGHT * min(1.0, max(0.0, _cos(vecs[0], v)) * 2) + WORD_WEIGHT * min(1.0, overlap * 1.5)
        if best is None or fit > best[0]:
            best = (fit, t, shared)
    fit, t, shared = best
    value = max(0, min(100, round(fit * 100)))
    if shared and value >= 10:
        return {"score": value, "reason": f"Fits {t['label']}: '{', '.join(shared[:3])}'"}
    return {"score": value, "reason": "No clear fit with your question."}
