"""Research_Pal API."""
import json, logging, re, threading, time
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from . import files, bibimport, sources, triage, auth, cards, chat, config, db, features, links, llm, mindmap, cite, coach, companion, critique, game, gaps, journey, metadata, pdf, play, project, quests, review, ste, today, understand, vectors, words, writing

log = logging.getLogger("research_pal")
PROCESS_LOCK = threading.Lock()  # one paper at a time: small servers have little memory


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.check_required()
    if not config.USE_PG:
        config.PDF_DIR.mkdir(parents=True, exist_ok=True)
    db.init()
    yield


app = FastAPI(title="Research_Pal", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=config.FRONTEND_ORIGINS, allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------- processing ----------
def game_event(fn, *args):
    """Give XP for a verified action. A problem in the game must never stop the real work, and a switched-off game gives no XP."""
    try:
        if features.is_enabled("game"):
            return fn(*args)
    except Exception:
        log.exception("Game event failed")
    return False


def process_paper(pid: str, fresh: bool = False) -> None:
    """fresh=True asks the AI again. Otherwise the same request gets its saved answer."""
    with PROCESS_LOCK, llm.cache_scope(pid, fresh), llm.ai_context("card", pid):
        try:
            db.update_paper(pid, status="processing", error="")
            p = db.get_paper(pid)
            if not p:
                return
            pages, meta = db.get_pages(pid), ""
            if not pages:
                pages, meta = pdf.extract_pages(files.source(pid))
                db.save_pages(pid, pages)
            chunks = pdf.chunk_pages(pages)
            vectors.index_chunks(pid, [c for c in chunks if not c["refs"]])
            card = cards.generate(pid, pages, chunks, p["purpose"], db.thesis_question(), meta, p.get("focus") or "")
            old = db.get_card(pid)
            for keep in ("notes", "mindmap"):  # notes and the mind map are not part of the reading. A new reading must keep them.
                if old and old.get(keep):
                    card[keep] = old[keep]
            db.save_card(pid, card)
            vectors.index_card(pid, cards.card_text(card))
            db.update_paper(pid, status="ready", error="", title=card["title"] or p["title"], n_pages=len(pages))
            game_event(game.check_card, pid)
        except (pdf.PdfError, llm.LLMError) as e:
            db.update_paper(pid, status="error", error=str(e))
        except Exception:
            log.exception("Unexpected error for paper %s", pid)
            db.update_paper(pid, status="error", error="Unexpected server error. Click Retry. If it continues, check the server log.")


def reindex_paper(pid: str) -> None:
    """After an import: rebuild the search index from saved text. No AI call."""
    with PROCESS_LOCK:
        try:
            pages, card = db.get_pages(pid), db.get_card(pid)
            chunks = pdf.chunk_pages(pages)
            vectors.index_chunks(pid, [c for c in chunks if not c["refs"]])
            if card:
                vectors.index_card(pid, cards.card_text(card))
            db.update_paper(pid, status="ready" if card else "error", error="" if card else "Imported paper has no card.")
        except Exception:
            log.exception("Reindex error %s", pid)
            db.update_paper(pid, status="error", error="Could not rebuild the search index. Click Retry.")


def paper_view(p: dict, have: set[str] | None = None) -> dict:
    """have: the ids of the papers with a PDF file (one call for a whole list). Without it, ask for this paper."""
    p = dict(p)
    p["authors"] = cite.authors_of(p)
    try:
        p["meta_check"] = json.loads(p.get("meta_check") or "[]")
    except ValueError:
        p["meta_check"] = []
    p["has_pdf"] = (p["id"] in have) if have is not None else files.exists(p["id"])
    return p


def card_list(p: dict) -> list[dict]:
    """The cards of one paper: the first card (id "") and the other cards. The card page shows them as tabs."""
    items = [{"id": "", "focus": p.get("focus") or "", "status": p["status"]}]
    for x in db.list_extra(p["id"]):
        items.append({"id": x["id"], "focus": x["focus"], "purpose": x["purpose"], "status": x["status"]})
    return items


def process_extra(pid: str, cid: str, fresh: bool = False) -> None:
    """Make one more card of a paper. It uses the saved text of the paper, so there is no new upload."""
    with PROCESS_LOCK, llm.cache_scope(pid, fresh), llm.ai_context("card", pid):
        try:
            db.update_extra(cid, status="processing", error="")
            x = db.get_extra(pid, cid)
            pages = db.get_pages(pid)
            if not x:
                return
            if not pages:
                raise pdf.PdfError("The text of this paper is not on the server. Use Read again on the first card.")
            chunks = pdf.chunk_pages(pages)
            card = cards.generate(pid, pages, chunks, x["purpose"], db.thesis_question(), "", x["focus"])
            for keep in ("mindmap",):  # a new reading keeps the mind map of this card
                if x["card"] and x["card"].get(keep):
                    card[keep] = x["card"][keep]
            db.update_extra(cid, status="ready", error="", card=card)
            game_event(game.check_card, pid, cid)
        except (pdf.PdfError, llm.LLMError) as e:
            db.update_extra(cid, status="error", error=str(e))
        except Exception:
            log.exception("Unexpected error for card %s", cid)
            db.update_extra(cid, status="error", error="Unexpected server error. Click Retry. If it continues, check the server log.")


def extra_view(pid: str, cid: str) -> dict:
    """One more card, in the same shape as the first card: the card page does not need to know the difference."""
    p = must_get(pid)
    x = db.get_extra(pid, cid)
    if not x:
        raise HTTPException(404, "Card not found.")
    view = {**paper_view(p), "status": x["status"], "error": x["error"], "focus": x["focus"], "purpose": x["purpose"]}
    card = x["card"]
    if card and card.get("mindmap"):  # the map is built from the card each time, so it is always in step
        card["mindmap"] = mindmap.build_card(card)
    return {"paper": view, "card": card, "card_list": card_list(p)}


def must_get(pid: str) -> dict:
    p = db.get_paper(pid)
    if not p:
        raise HTTPException(404, "Paper not found.")
    return p


# ---------- auth ----------
class LoginIn(BaseModel):
    password: str


@app.get("/api/health")
def health():
    db.ping()  # a free Supabase project pauses after 7 days without use. The keep-alive job calls this every 10 minutes.
    return {"ok": True}


@app.post("/api/login")
def login(body: LoginIn, request: Request):
    if config.MULTI_USER:
        raise HTTPException(404, "Password login is off. Sign in with your email.")
    if not auth.check_password(request, body.password):
        raise HTTPException(401, "Wrong password.")
    return {"token": auth.make_token()}


# ---------- info and settings ----------
@app.get("/api/config", dependencies=[Depends(auth.require_auth)])
def get_config():
    return {
        "provider": llm.choice()["primary"], "model": llm.choice()["models"][llm.choice()["primary"]], "llm_ready": llm.ready(), "providers": llm.status(),
        "ai_choice": llm.choice(), "ai_options": llm.options(),
        "saved_answers": db.cache_count(),
        "embeddings": config.EMBEDDING_BACKEND, "link_threshold": config.LINK_THRESHOLD,
        "thesis_question": db.thesis_question(), "max_upload_mb": config.MAX_UPLOAD_BYTES // (1024 * 1024),
    }


class SettingsIn(BaseModel):
    thesis_question: str = ""


@app.put("/api/settings", dependencies=[Depends(auth.require_auth)])
def put_settings(body: SettingsIn):
    """The research question is part of the thesis project now. This call stays for old clients."""
    db.save_project({"question": " ".join(body.thesis_question.split())[:project.MAX_QUESTION]})
    return {"ok": True}


# ---------- thesis: title, question, stage, sub-questions, tags ----------
def project_view() -> dict:
    return {**db.get_project(), "stages": [{"value": k, "label": v} for k, v in db.STAGES.items()]}


class ProjectIn(BaseModel):
    title: str | None = None  # a field that you leave out keeps its saved value
    question: str | None = None
    stage: str | None = None


@app.get("/api/project", dependencies=[Depends(auth.require_auth)])
def get_project():
    return project_view()


@app.put("/api/project", dependencies=[Depends(auth.require_auth)])
def put_project(body: ProjectIn):
    changes = {}
    if body.title is not None:
        changes["title"] = " ".join(body.title.split())
        if len(changes["title"]) > project.MAX_TITLE:
            raise HTTPException(400, f"The title is longer than {project.MAX_TITLE} characters.")
    if body.question is not None:
        changes["question"] = " ".join(body.question.split())
        if len(changes["question"]) > project.MAX_QUESTION:
            raise HTTPException(400, f"The question is longer than {project.MAX_QUESTION} characters.")
    if body.stage is not None:
        if body.stage not in db.STAGES:
            raise HTTPException(400, "Unknown PhD stage.")
        changes["stage"] = body.stage
    db.save_project(changes)
    return project_view()


direction = [Depends(auth.require_auth), Depends(features.require("direction"))]


@app.get("/api/project/history", dependencies=direction)
def project_history():
    return db.project_history()


class QuestionIn(BaseModel):
    question: str = ""


@app.post("/api/project/question-check", dependencies=direction)
def question_check(body: QuestionIn):
    """The FINER check and 3 narrower versions. The AI saves nothing: the student chooses."""
    try:
        return project.question_check(body.question)
    except project.ProjectError as e:
        raise HTTPException(400, str(e))
    except llm.LLMError as e:
        raise HTTPException(502, str(e))


class SplitIn(BaseModel):
    question: str | None = None  # without it, the saved question is used


@app.post("/api/project/split", dependencies=direction)
def project_split(body: SplitIn):
    """3 to 5 sub-questions for the main question. The AI saves nothing."""
    try:
        return project.split(db.thesis_question() if body.question is None else body.question)
    except project.ProjectError as e:
        raise HTTPException(400, str(e))
    except llm.LLMError as e:
        raise HTTPException(502, str(e))


@app.get("/api/project/coverage", dependencies=direction)
def project_coverage():
    cov = db.coverage()
    for s in cov["sub_questions"]:
        s["level"] = project.coverage_level(s["papers"])
    return cov


class SubQuestionIn(BaseModel):
    text: str


class SubQuestionPatch(BaseModel):
    text: str | None = None
    position: int | None = None  # the new place in the list, 0 = first


@app.get("/api/sub-questions", dependencies=direction)
def list_sub_questions():
    return db.list_sub_questions()


@app.post("/api/sub-questions", dependencies=direction)
def add_sub_question(body: SubQuestionIn):
    try:
        text = project.clean_text(body.text, project.MAX_SUB_TEXT, "sub-question")
    except project.ProjectError as e:
        raise HTTPException(400, str(e))
    if len(db.list_sub_questions()) >= db.MAX_SUB_QUESTIONS:
        raise HTTPException(400, f"A thesis can have {db.MAX_SUB_QUESTIONS} sub-questions at most.")
    return db.add_sub_question(text)


@app.put("/api/sub-questions/{sid}", dependencies=direction)
def put_sub_question(sid: str, body: SubQuestionPatch):
    try:
        text = None if body.text is None else project.clean_text(body.text, project.MAX_SUB_TEXT, "sub-question")
    except project.ProjectError as e:
        raise HTTPException(400, str(e))
    sub = db.update_sub_question(sid, text, body.position)
    if not sub:
        raise HTTPException(404, "Sub-question not found.")
    return sub


@app.delete("/api/sub-questions/{sid}", dependencies=direction)
def delete_sub_question(sid: str):
    if not db.delete_sub_question(sid):
        raise HTTPException(404, "Sub-question not found.")
    return {"ok": True}


class TagsIn(BaseModel):
    sub_question_ids: list[str] = []
    card_id: str = ""  # "" = the first card of the paper


@app.put("/api/papers/{pid}/tags", dependencies=direction)
def put_tags(pid: str, body: TagsIn):
    """Link a card of the paper to sub-questions. The new list replaces the old list."""
    must_get(pid)
    if body.card_id and not db.get_extra(pid, body.card_id):
        raise HTTPException(404, "Card not found.")
    known = {s["id"] for s in db.list_sub_questions()}
    if any(s not in known for s in body.sub_question_ids):
        raise HTTPException(400, "Unknown sub-question.")
    db.set_tags(pid, body.card_id, body.sub_question_ids)
    return {"tags": db.all_tags().get(pid, {})}


class AiChoiceIn(BaseModel):
    primary: str
    fallbacks: list[str] = []
    models: dict[str, str] = {}


@app.put("/api/ai", dependencies=[Depends(auth.require_auth)])
def put_ai(body: AiChoiceIn):
    """Choose the default AI, the fallbacks and the model of each. The keys stay in the server environment."""
    if body.primary not in config.PROVIDERS:
        raise HTTPException(400, "Unknown AI provider.")
    if any(n not in config.PROVIDERS for n in body.fallbacks):
        raise HTTPException(400, "Unknown fallback provider.")
    for n, m in body.models.items():
        if m.strip() and not (n in config.PROVIDERS and len(m.strip()) <= 100 and re.fullmatch(r"[\w.:/\-]+", m.strip())):
            raise HTTPException(400, f"The model name for {n} is not valid. Use letters, digits and . : / - _ only.")
    llm.set_choice(body.model_dump())
    return get_config()


@app.delete("/api/ai", dependencies=[Depends(auth.require_auth)])
def reset_ai():
    """Go back to the AI settings of the server (.env)."""
    llm.set_choice(None)
    return get_config()


class FeaturesIn(BaseModel):
    features: dict[str, bool]


@app.get("/api/features", dependencies=[Depends(auth.require_auth)])
def get_features():
    return features.listing()


@app.put("/api/features", dependencies=[Depends(auth.require_auth)])
def put_features(body: FeaturesIn):
    """Switch features on or off. Data stays: a switch only hides or blocks the feature."""
    features.set_many(body.features)
    return features.listing()


@app.delete("/api/cache", dependencies=[Depends(auth.require_auth)])
def clear_cache():
    """Forget all saved AI answers. Cards, mind maps and notes stay."""
    db.cache_clear()
    return {"ok": True}


# ---------- papers ----------
@app.post("/api/papers", dependencies=[Depends(auth.require_auth)])
async def upload(background: BackgroundTasks, file: UploadFile = File(...), purpose: str = Form(""), focus: str = Form("")):
    pid = db.new_id()
    parts, size = [], 0
    while chunk := await file.read(1024 * 1024):
        if not parts and not chunk.startswith(b"%PDF-"):
            raise HTTPException(400, "This file is not a PDF.")
        size += len(chunk)
        if size > config.MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"The file is larger than {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
        parts.append(chunk)
    if size == 0:
        raise HTTPException(400, "The file is empty.")
    try:
        files.save(pid, b"".join(parts))
    except files.StorageError as e:
        raise HTTPException(503, str(e))
    db.add_paper(pid, (file.filename or "paper.pdf")[:200], purpose.strip()[:500], focus.strip()[:200])
    background.add_task(process_paper, pid)
    return {"id": pid, "status": "queued"}


@app.get("/api/papers", dependencies=[Depends(auth.require_auth)])
def list_papers():
    tags = db.all_tags()  # {card id: [sub-question ids]} for each paper. The first card has the id "".
    have = files.ids()
    return [{**paper_view(p, have), "tags": tags.get(p["id"], {})} for p in db.list_papers()]


@app.get("/api/papers/{pid}", dependencies=[Depends(auth.require_auth)])
def get_paper(pid: str):
    p = must_get(pid)
    card = db.get_card(pid)
    if card and card.get("mindmap"):  # the map is built from all cards of the paper each time, so it is always in step
        card["mindmap"] = mindmap.build(pid)
    return {"paper": paper_view(p), "card": card, "card_list": card_list(p)}


@app.get("/api/papers/{pid}/pdf", dependencies=[Depends(auth.require_auth)])
def get_pdf(pid: str):
    must_get(pid)
    try:
        data = files.read(pid)
    except files.StorageError as e:
        raise HTTPException(503, str(e))
    if data is None:
        raise HTTPException(404, "The PDF file is not on the server.")
    return Response(data, media_type="application/pdf")


@app.get("/api/papers/{pid}/page/{n}", dependencies=[Depends(auth.require_auth)])
def get_page(pid: str, n: int):
    must_get(pid)
    pages = db.get_pages(pid)
    if not 1 <= n <= len(pages):
        raise HTTPException(404, "Page not found.")
    return {"page": n, "text": pages[n - 1]}


class RegenIn(BaseModel):
    purpose: str | None = None
    focus: str | None = None
    fresh: bool = False  # True: ask the AI again, even if the same request has a saved answer


@app.post("/api/papers/{pid}/regenerate", dependencies=[Depends(auth.require_auth)])
def regenerate(pid: str, body: RegenIn, background: BackgroundTasks):
    p = must_get(pid)
    if p["status"] in ("queued", "processing"):
        raise HTTPException(409, "This paper is in progress.")
    if body.purpose is not None:
        db.update_paper(pid, purpose=body.purpose.strip()[:500])
    if body.focus is not None:
        db.update_paper(pid, focus=body.focus.strip()[:200])
    db.update_paper(pid, status="queued", error="")
    background.add_task(process_paper, pid, body.fresh)
    return {"id": pid, "status": "queued"}


class CardPatch(BaseModel):
    fields: dict[str, str] = {}
    verdict: str | None = None


@app.patch("/api/papers/{pid}/card", dependencies=[Depends(auth.require_auth)])
def patch_card(pid: str, body: CardPatch):
    must_get(pid)
    card = db.get_card(pid)
    if not card:
        raise HTTPException(404, "This paper has no card yet.")
    for name, text in body.fields.items():
        if name not in cards.FIELD_LABELS:
            raise HTTPException(400, f"Unknown field: {name}")
        f = card["fields"].setdefault(name, {"evidence": []})
        f.update(answer=text.strip()[:3000], status="edited", edited=True)
    if body.verdict is not None:
        if body.verdict not in cards.VERDICTS | {""}:
            raise HTTPException(400, "Unknown verdict.")
        card["verdict"] = body.verdict
    db.save_card(pid, card)
    vectors.index_card(pid, cards.card_text(card))
    return card


class NoteIn(BaseModel):
    question: str = ""
    answer: str
    evidence: list[dict] = []


@app.post("/api/papers/{pid}/notes", dependencies=[Depends(auth.require_auth)])
def add_note(pid: str, body: NoteIn):
    """Add an answer from the chat to the card of this paper."""
    must_get(pid)
    card = db.get_card(pid)
    if not card:
        raise HTTPException(404, "This paper has no card yet.")
    try:
        note = chat.make_note(body.question, body.answer, body.evidence)
    except chat.ChatError as e:
        raise HTTPException(400, str(e))
    note["created_at"] = time.time()
    card.setdefault("notes", []).append(note)
    db.save_card(pid, card)
    return card


@app.delete("/api/papers/{pid}/notes/{nid}", dependencies=[Depends(auth.require_auth)])
def delete_note(pid: str, nid: str):
    must_get(pid)
    card = db.get_card(pid)
    if not card:
        raise HTTPException(404, "This paper has no card yet.")
    card["notes"] = [n for n in card.get("notes", []) if n.get("id") != nid]
    db.save_card(pid, card)
    return card


@app.post("/api/papers/{pid}/mindmap", dependencies=[Depends(auth.require_auth)])
def make_mindmap(pid: str):
    """The mind map of the paper, built from its cards. No AI call. With several cards, each card is one branch."""
    p = must_get(pid)
    card = db.get_card(pid)
    if not card:
        raise HTTPException(404, "This paper has no card yet.")
    if p["status"] in ("queued", "processing"):
        raise HTTPException(409, "This paper is in progress.")
    card["mindmap"] = mindmap.build(pid)
    db.save_card(pid, card)
    return card


@app.delete("/api/papers/{pid}/mindmap", dependencies=[Depends(auth.require_auth)])
def delete_mindmap(pid: str):
    must_get(pid)
    card = db.get_card(pid)
    if not card:
        raise HTTPException(404, "This paper has no card yet.")
    card.pop("mindmap", None)
    db.save_card(pid, card)
    return card


# ---------- search again for the fields that were not found ----------
class FillIn(BaseModel):
    fields: list[str] | None = None  # None = every field that is "not found"


def run_fill(pid: str, card: dict, names: list[str] | None) -> list[str]:
    """One AI call with excerpts chosen for the missing fields. Returns the names that now have a checked answer."""
    pages = db.get_pages(pid)
    if not pages:
        raise HTTPException(400, "The text of this paper is not on the server. Use Read again first.")
    with PROCESS_LOCK, llm.cache_scope(pid), llm.ai_context("card", pid):
        try:
            return cards.fill_missing(pid, pages, pdf.chunk_pages(pages), card, names)
        except pdf.PdfError as e:
            raise HTTPException(400, str(e))
        except llm.LLMError as e:
            raise HTTPException(502, str(e))


@app.post("/api/papers/{pid}/fill", dependencies=[Depends(auth.require_auth)])
def fill_card(pid: str, body: FillIn):
    p = must_get(pid)
    card = db.get_card(pid)
    if not card:
        raise HTTPException(404, "This paper has no card yet.")
    if p["status"] in ("queued", "processing"):
        raise HTTPException(409, "This paper is in progress.")
    filled = run_fill(pid, card, body.fields)
    latest = db.get_card(pid) or card  # read again: the student can edit during the AI call
    for n in filled:
        if latest["fields"].get(n, {}).get("status") == "not_found":  # do not replace an edit of the student
            latest["fields"][n] = card["fields"][n]
    db.save_card(pid, latest)
    vectors.index_card(pid, cards.card_text(latest))
    game_event(game.check_card, pid)
    return {"card": latest, "filled": filled, "missing": cards.missing_fields(latest)}


@app.post("/api/papers/{pid}/cards/{cid}/fill", dependencies=[Depends(auth.require_auth)])
def fill_extra_card(pid: str, cid: str, body: FillIn):
    p = must_get(pid)
    x = db.get_extra(pid, cid)
    if not x or not x["card"]:
        raise HTTPException(404, "This card is not ready.")
    if x["status"] in ("queued", "processing") or p["status"] in ("queued", "processing"):
        raise HTTPException(409, "This card is in progress.")
    filled = run_fill(pid, x["card"], body.fields)
    latest = (db.get_extra(pid, cid) or x)["card"] or x["card"]
    for n in filled:
        if latest["fields"].get(n, {}).get("status") == "not_found":
            latest["fields"][n] = x["card"]["fields"][n]
    db.update_extra(cid, card=latest)
    game_event(game.check_card, pid, cid)
    return {"card": latest, "filled": filled, "missing": cards.missing_fields(latest)}


# ---------- more cards for one paper ----------
class NewCardIn(BaseModel):
    focus: str = ""
    purpose: str = ""


@app.post("/api/papers/{pid}/cards", dependencies=[Depends(auth.require_auth)])
def add_card(pid: str, body: NewCardIn, background: BackgroundTasks):
    """Another card for the same paper, with its own focus topic. No new upload."""
    p = must_get(pid)
    focus, purpose = body.focus.strip()[:200], body.purpose.strip()[:500]
    if not focus and not purpose:
        raise HTTPException(400, "Write a focus topic or a reason for the new card.")
    if p["status"] != "ready" and not db.get_pages(pid):
        raise HTTPException(409, "Wait until the first card of this paper is ready.")
    if len(db.list_extra(pid)) >= db.MAX_EXTRA_CARDS:
        raise HTTPException(400, f"A paper can have {db.MAX_EXTRA_CARDS + 1} cards at most.")
    if focus and focus.lower() in {(p.get("focus") or "").lower(), *(x["focus"].lower() for x in db.list_extra(pid))}:
        raise HTTPException(409, "This paper has a card with this focus topic already.")
    cid = db.add_extra(pid, focus, purpose)
    background.add_task(process_extra, pid, cid)
    return {"id": cid, "status": "queued"}


@app.get("/api/papers/{pid}/cards/{cid}", dependencies=[Depends(auth.require_auth)])
def get_extra_card(pid: str, cid: str):
    return extra_view(pid, cid)


@app.post("/api/papers/{pid}/cards/{cid}/regenerate", dependencies=[Depends(auth.require_auth)])
def regenerate_extra(pid: str, cid: str, body: RegenIn, background: BackgroundTasks):
    must_get(pid)
    x = db.get_extra(pid, cid)
    if not x:
        raise HTTPException(404, "Card not found.")
    if x["status"] in ("queued", "processing"):
        raise HTTPException(409, "This card is in progress.")
    change = {}
    if body.purpose is not None:
        change["purpose"] = body.purpose.strip()[:500]
    if body.focus is not None:
        change["focus"] = body.focus.strip()[:200]
    if not (change.get("focus", x["focus"]) or change.get("purpose", x["purpose"])):
        raise HTTPException(400, "A card needs a focus topic or a reason. To read the whole paper, use the first card.")
    db.update_extra(cid, status="queued", error="", **change)
    background.add_task(process_extra, pid, cid, body.fresh)
    return {"id": cid, "status": "queued"}


@app.patch("/api/papers/{pid}/cards/{cid}", dependencies=[Depends(auth.require_auth)])
def patch_extra_card(pid: str, cid: str, body: CardPatch):
    must_get(pid)
    x = db.get_extra(pid, cid)
    if not x or not x["card"]:
        raise HTTPException(404, "This card is not ready.")
    card = x["card"]
    for name, text in body.fields.items():
        if name not in cards.FIELD_LABELS:
            raise HTTPException(400, f"Unknown field: {name}")
        f = card["fields"].setdefault(name, {"evidence": []})
        f.update(answer=text.strip()[:3000], status="edited", edited=True)
    if body.verdict is not None:
        if body.verdict not in cards.VERDICTS | {""}:
            raise HTTPException(400, "Unknown verdict.")
        card["verdict"] = body.verdict
    db.update_extra(cid, card=card)
    return card


@app.post("/api/papers/{pid}/cards/{cid}/mindmap", dependencies=[Depends(auth.require_auth)])
def make_extra_mindmap(pid: str, cid: str):
    """The mind map of this card, built from the card. No AI call."""
    p = must_get(pid)
    x = db.get_extra(pid, cid)
    if not x or not x["card"]:
        raise HTTPException(404, "This card is not ready.")
    if x["status"] in ("queued", "processing") or p["status"] in ("queued", "processing"):
        raise HTTPException(409, "This card is in progress.")
    x["card"]["mindmap"] = mindmap.build_card(x["card"])
    db.update_extra(cid, card=x["card"])
    return x["card"]


@app.delete("/api/papers/{pid}/cards/{cid}/mindmap", dependencies=[Depends(auth.require_auth)])
def delete_extra_mindmap(pid: str, cid: str):
    must_get(pid)
    x = db.get_extra(pid, cid)
    if not x or not x["card"]:
        raise HTTPException(404, "This card is not ready.")
    x["card"].pop("mindmap", None)
    db.update_extra(cid, card=x["card"])
    return x["card"]


@app.delete("/api/papers/{pid}/cards/{cid}", dependencies=[Depends(auth.require_auth)])
def delete_extra_card(pid: str, cid: str):
    must_get(pid)
    if not db.get_extra(pid, cid):
        raise HTTPException(404, "Card not found.")
    db.delete_extra(pid, cid)
    return {"ok": True}


@app.delete("/api/papers/{pid}", dependencies=[Depends(auth.require_auth)])
def delete_paper(pid: str):
    must_get(pid)
    vectors.delete_paper(pid)
    db.delete_paper(pid)
    files.delete(pid)
    return {"ok": True}


# ---------- simple mode ----------
SIMPLE_MESSAGES = {
    "changed_fact": "The server kept the original text. The simple version changed a number or a name.",
    "not_simple": "The server kept the original text. The AI could not make it simpler.",
    "empty": "There is no text to simplify.",
}


def simple_answer(result: dict) -> dict:
    return {**result, "label": "AI simplification", "message": SIMPLE_MESSAGES.get(result["reason"], "")}


def run_simplify(text: str, paper_id: str = "") -> dict:
    try:
        with llm.cache_scope(paper_id), llm.ai_context("simplify", paper_id):
            return simple_answer(ste.simplify(text))
    except llm.LLMError as e:
        raise HTTPException(502, str(e))


class SimplifyFieldIn(BaseModel):
    field: str
    card_id: str = ""  # "" is the first card of the paper


SIMPLE_TEXTS = ("verdict_reason", "inferred_limitations")  # texts of the AI on the card, besides the fields


@app.post("/api/papers/{pid}/simplify", dependencies=[Depends(auth.require_auth), Depends(features.require("simple"))])
def simplify_field(pid: str, body: SimplifyFieldIn):
    """The simple version of one text of the AI on a card. The server reads the text from the card, so the page cannot send another text."""
    must_get(pid)
    if body.card_id:
        x = db.get_extra(pid, body.card_id)
        card = x["card"] if x else None
    else:
        card = db.get_card(pid)
    if not card:
        raise HTTPException(404, "This card is not ready.")
    if body.field in SIMPLE_TEXTS:
        text = str(card.get(body.field) or "").strip()
    elif body.field in cards.FIELD_LABELS:
        f = (card.get("fields") or {}).get(body.field) or {}
        if f.get("kind") == "user" or f.get("edited"):
            raise HTTPException(400, "This is your own text. The AI does not rewrite it.")
        text = "" if f.get("status") in ("not_stated", "not_found") else str(f.get("answer") or "").strip()
    else:
        raise HTTPException(400, f"Unknown field: {body.field}")
    if not text:
        raise HTTPException(400, "This field has no text to simplify.")
    return run_simplify(text, pid)


class SimplifyTextIn(BaseModel):
    text: str


@app.post("/api/simplify", dependencies=[Depends(auth.require_auth), Depends(features.require("simple"))])
def simplify_text(body: SimplifyTextIn):
    """The simple version of a text of the AI in the chat, the links or the mind map. The same safety check applies."""
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "There is no text to simplify.")
    if len(text) > 3000:
        raise HTTPException(400, "The text is longer than 3000 characters.")
    return run_simplify(text)


# ---------- Today: goals, wins, focus timer ----------
def run_today(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except today.TodayError as e:
        raise HTTPException(400, str(e))


TODAY = [Depends(auth.require_auth), Depends(features.require("today"))]


@app.get("/api/today", dependencies=TODAY)
def get_today(date: str | None = None):
    return run_today(lambda: today.today(today.clean_date(date)))


@app.get("/api/today/next", dependencies=TODAY)
def get_today_next(date: str | None = None):
    return run_today(lambda: today.next_action(today.clean_date(date)))


class GoalIn(BaseModel):
    text: str
    kind: str = "free"
    target: int = 0
    date: str | None = None


class GoalPatch(BaseModel):
    text: str | None = None
    target: int | None = None
    done: bool | None = None


@app.get("/api/goals", dependencies=TODAY)
def list_goals(date: str | None = None):
    return run_today(lambda: db.goals_list(today.clean_date(date)))


@app.post("/api/goals", dependencies=TODAY)
def add_goal(body: GoalIn):
    return run_today(lambda: today.add_goal(today.clean_date(body.date), body.text, body.kind, body.target))


@app.put("/api/goals/{gid}", dependencies=TODAY)
def update_goal(gid: str, body: GoalPatch):
    if not db.goal_get(gid):
        raise HTTPException(404, "Goal not found.")
    text = run_today(today.clean_text, body.text, today.MAX_GOAL_TEXT, "goal") if body.text is not None else None
    return db.goal_update(gid, text=text, target=body.target, done=body.done)


@app.delete("/api/goals/{gid}", dependencies=TODAY)
def delete_goal(gid: str):
    if not db.goal_delete(gid):
        raise HTTPException(404, "Goal not found.")
    return {"ok": True}


class WinIn(BaseModel):
    text: str
    date: str | None = None


@app.get("/api/wins", dependencies=TODAY)
def list_wins(limit: int = 5, before: str | None = None):
    return db.wins_list(min(max(limit, 1), 200), before=run_today(today.clean_date, before) if before else None)


@app.post("/api/wins", dependencies=TODAY)
def add_win(body: WinIn):
    date = run_today(today.clean_date, body.date)
    win = db.win_add(date, run_today(today.clean_text, body.text, today.MAX_WIN_TEXT, "win"))
    game_event(game.check_win, date)  # 2 XP, one time for each day
    return win


@app.delete("/api/wins/{wid}", dependencies=TODAY)
def delete_win(wid: str):
    if not db.win_delete(wid):
        raise HTTPException(404, "Win not found.")
    return {"ok": True}


class FocusIn(BaseModel):
    task_text: str = ""
    paper_id: str = ""
    goal_id: str = ""
    planned_minutes: int = 25
    date: str | None = None


@app.post("/api/focus/start", dependencies=TODAY)
def focus_start(body: FocusIn):
    return run_today(lambda: today.start_focus(body.task_text, body.paper_id, body.planned_minutes, body.goal_id, today.clean_date(body.date)))


@app.post("/api/focus/stop", dependencies=TODAY)
def focus_stop():
    session = run_today(today.stop_focus)
    game_event(game.check_focus, session)  # a session of 20 minutes or more
    return session


@app.get("/api/focus/active", dependencies=TODAY)
def focus_active():
    return {"session": db.focus_active()}


@app.get("/api/focus", dependencies=TODAY)
def focus_sessions(date: str | None = None):
    d = run_today(today.clean_date, date)
    return {"date": d, "minutes": db.focus_minutes(d), "sessions": db.focus_list(d)}


# ---------- understand: Feynman check, like I am 12, quiz ----------
def run_understand(pid: str, feature: str, fn, *args):
    must_get(pid)
    try:
        with llm.cache_scope(pid), llm.ai_context(feature, pid):
            return fn(pid, *args)
    except understand.UnderstandError as e:
        raise HTTPException(400, str(e))
    except llm.LLMError as e:
        raise HTTPException(502, str(e))


class ExplainIn(BaseModel):
    text: str
    card_id: str = ""


@app.post("/api/papers/{pid}/explain", dependencies=[Depends(auth.require_auth), Depends(features.require("feynman"))])
def explain_paper(pid: str, body: ExplainIn):
    """The Feynman check. The student explains the paper. The server checks each mark of the AI against the PDF."""
    was_boss_down = bool((db.get_paper(pid) or {}).get("boss_defeated_at"))
    result = run_understand(pid, "explain", understand.explain, body.text, body.card_id)
    result["xp_gained"] = game.XP["feynman_pass"] if game_event(game.check_feynman, pid, result["score"]) else 0
    game_event(quests.check_bosses)  # a better score can defeat a boss (the points can do it first)
    p = db.get_paper(pid)
    result["boss_defeated"] = p["title"] if p.get("boss_defeated_at") and not was_boss_down else ""
    return result


@app.get("/api/papers/{pid}/explanations", dependencies=[Depends(auth.require_auth), Depends(features.require("feynman"))])
def list_explanations(pid: str, card_id: str | None = None):
    must_get(pid)
    return [{"id": e["id"], "card_id": e["card_id"], "text": e["text"], "score": e["score"], "created_at": e["created_at"], "result": e["result"]}
            for e in db.explanation_list(pid, card_id)]


@app.delete("/api/explanations/{eid}", dependencies=[Depends(auth.require_auth), Depends(features.require("feynman"))])
def delete_explanation(eid: str):
    if not db.explanation_delete(eid):
        raise HTTPException(404, "Attempt not found.")
    return {"ok": True}


class Eli12In(BaseModel):
    field: str
    card_id: str = ""


@app.post("/api/papers/{pid}/eli12", dependencies=[Depends(auth.require_auth), Depends(features.require("eli12"))])
def eli12_field(pid: str, body: Eli12In):
    out = run_understand(pid, "eli12", understand.eli12, body.field, body.card_id)
    db.activity_add("eli12_view", pid)  # a quest can ask for it
    game_event(game.refresh)
    return out


class QuizIn(BaseModel):
    card_id: str = ""


@app.post("/api/papers/{pid}/quiz", dependencies=[Depends(auth.require_auth), Depends(features.require("quiz"))])
def make_quiz(pid: str, body: QuizIn):
    """New questions. Each question has a quote that the server found in the PDF. The answers stay on the server until the student answers."""
    return run_understand(pid, "quiz", understand.make_quiz, body.card_id)


@app.get("/api/papers/{pid}/quiz", dependencies=[Depends(auth.require_auth), Depends(features.require("quiz"))])
def list_quiz(pid: str):
    must_get(pid)
    return [{"id": r["id"], "question": r["question"], "last_mark": r["last_mark"], "tries": r["tries"], "card_id": r["card_id"]} for r in db.review_list(pid, "quiz")]


class AnswerIn(BaseModel):
    answer: str


@app.post("/api/quiz/{rid}/answer", dependencies=[Depends(auth.require_auth), Depends(features.require("quiz"))])
def answer_quiz(rid: str, body: AnswerIn):
    item = db.review_get(rid)
    if not item or item["kind"] != "quiz":
        raise HTTPException(404, "Question not found.")
    try:
        with llm.cache_scope(item["paper_id"]), llm.ai_context("quiz", item["paper_id"]):
            was_boss_down = bool((db.get_paper(item["paper_id"]) or {}).get("boss_defeated_at"))
            result = understand.mark_answer(rid, body.answer)
            if result["mark"] == "correct":
                game_event(game.award, "quiz_correct", rid)
            game_event(quests.check_bosses)  # the quiz can defeat a boss
            p = db.get_paper(item["paper_id"])
            result["boss_defeated"] = p["title"] if p.get("boss_defeated_at") and not was_boss_down else ""
            return result
    except understand.UnderstandError as e:
        raise HTTPException(400, str(e))
    except llm.LLMError as e:
        raise HTTPException(502, str(e))


@app.delete("/api/quiz/{rid}", dependencies=[Depends(auth.require_auth), Depends(features.require("quiz"))])
def delete_quiz(rid: str):
    item = db.review_get(rid)
    if not item or item["kind"] != "quiz":
        raise HTTPException(404, "Question not found.")
    with db.conn() as c:
        c.execute("DELETE FROM review_items WHERE id=?", (rid,))
    return {"ok": True}


# ---------- word helper and glossary ----------
class DefineIn(BaseModel):
    term: str


def define_term(pid: str, term: str) -> dict:
    must_get(pid)
    try:
        with llm.cache_scope(pid), llm.ai_context("define", pid):
            return words.define(pid, term)
    except words.WordError as e:
        raise HTTPException(400, str(e))
    except llm.LLMError as e:
        raise HTTPException(502, str(e))


@app.post("/api/papers/{pid}/define", dependencies=[Depends(auth.require_auth), Depends(features.require("glossary"))])
def define(pid: str, body: DefineIn):
    out = define_term(pid, body.term)
    saved = db.glossary_find(out["term"], pid)
    return {**out, "saved_id": saved["id"] if saved else ""}


class GlossaryIn(BaseModel):
    term: str
    paper_id: str


def glossary_view(g: dict) -> dict:
    return {**g, "label": words.FROM_PAPER if g["source"] == "paper" else words.FROM_AI, "paper_title": g.get("paper_title") or ""}


@app.get("/api/glossary", dependencies=[Depends(auth.require_auth), Depends(features.require("glossary"))])
def list_glossary(q: str = ""):
    return [glossary_view(g) for g in db.glossary_list(q)]


@app.post("/api/glossary", dependencies=[Depends(auth.require_auth), Depends(features.require("glossary"))])
def add_glossary(body: GlossaryIn):
    """Save a word. The server makes the explanation again, so the page cannot write a text and call it "From the paper"."""
    out = define_term(body.paper_id, body.term)
    if not out["known"]:
        raise HTTPException(400, "The AI does not know this term, so there is nothing to save.")
    g = db.glossary_add(out["term"], out["explanation"], out["source"], body.paper_id, out["page"])
    return glossary_view({**g, "paper_title": must_get(body.paper_id)["title"]})


@app.delete("/api/glossary/{gid}", dependencies=[Depends(auth.require_auth), Depends(features.require("glossary"))])
def delete_glossary(gid: str):
    if not db.glossary_delete(gid):
        raise HTTPException(404, "Word not found.")
    return {"ok": True}


# ---------- citations and metadata ----------
CITE = [Depends(auth.require_auth), Depends(features.require("cite"))]
LIT = [Depends(auth.require_auth), Depends(features.require("litreview"))]


@app.post("/api/papers/{pid}/meta/extract", dependencies=CITE)
def meta_extract(pid: str):
    """Read authors, year, venue and DOI from the first pages. The server keeps only what the PDF has. A field that it could not check shows "Check"."""
    must_get(pid)
    try:
        with llm.cache_scope(pid), llm.ai_context("meta", pid):
            return paper_view(metadata.extract(pid))
    except metadata.MetaError as e:
        raise HTTPException(400, str(e))
    except llm.LLMError as e:
        raise HTTPException(502, str(e))


class MetaIn(BaseModel):
    authors: list[str] | None = None
    year: str | None = None
    venue: str | None = None
    doi: str | None = None


@app.put("/api/papers/{pid}/meta", dependencies=CITE)
def meta_edit(pid: str, body: MetaIn):
    must_get(pid)
    try:
        return paper_view(metadata.edit(pid, body.model_dump(exclude_none=True)))
    except metadata.MetaError as e:
        raise HTTPException(400, str(e))


def library_papers() -> list[dict]:
    return sorted(db.list_papers(), key=lambda p: p["created_at"])


@app.get("/api/export/bibtex", dependencies=CITE)
def export_bibtex():
    return Response(cite.to_bibtex(library_papers()), media_type="application/x-bibtex; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="research-pal.bib"'})


@app.get("/api/export/ris", dependencies=CITE)
def export_ris():
    return Response(cite.to_ris(library_papers()), media_type="application/x-research-info-systems; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="research-pal.ris"'})


@app.get("/api/papers/{pid}/cite", dependencies=CITE)
def paper_cite(pid: str, page: int | None = None, style: str = "apa"):
    """A citation with a page, for example (Smith et al., 2024, p. 3). complete=false: the author or the year is missing, check the metadata."""
    p = must_get(pid)
    if style not in cite.STYLES:
        raise HTTPException(400, "The style must be apa or ieee.")
    number = [x["id"] for x in library_papers()].index(pid) + 1
    return cite.cite(p, page, style, number)


# ---------- gap finder, writing coach, critical reading ----------
GAPS = [Depends(auth.require_auth), Depends(features.require("gaps"))]


class GapRunIn(BaseModel):
    sub_question_id: str | None = None
    paper_ids: list[str] | None = None


@app.post("/api/gaps", dependencies=GAPS)
def run_gaps(body: GapRunIn):
    """Where the papers agree, where they disagree, and the gap. A point with no verified quotes in two papers is dropped. A gap is an AI opinion."""
    try:
        with llm.cache_scope(""), llm.ai_context("gaps", ",".join(body.paper_ids or [])):
            return gaps.run(body.sub_question_id, body.paper_ids)
    except gaps.GapError as e:
        raise HTTPException(400, str(e))
    except llm.LLMError as e:
        raise HTTPException(502, str(e))


@app.get("/api/gaps", dependencies=GAPS)
def get_gaps(sub_question_id: str = ""):
    run = db.gap_run_latest(sub_question_id)
    return gaps.view(run["id"]) if run else {"run_id": None, "agree": [], "disagree": [], "gap": []}


class GapStatusIn(BaseModel):
    status: str


@app.put("/api/gaps/{gid}", dependencies=GAPS)
def put_gap(gid: str, body: GapStatusIn):
    try:
        out = gaps.set_status(gid, body.status)
    except gaps.GapError as e:
        raise HTTPException(400, str(e))
    game_event(game.refresh)  # a confirmed gap counts for the level Connector
    return out


@app.post("/api/gaps/{gid}/use", dependencies=GAPS)
def use_gap(gid: str):
    """"Use this gap": a new section in the outline of the literature review. The heading only. You write the text."""
    g = db.gap_get(gid)
    if not g:
        raise HTTPException(404, "Gap not found.")
    return db.review_section_add(db.review_doc()["id"], " ".join(g["text"].split())[:200], g["sub_question_id"] or "")


COACH = [Depends(auth.require_auth), Depends(features.require("coach"))]


class CoachIn(BaseModel):
    text: str


@app.post("/api/coach", dependencies=COACH)
def run_coach(body: CoachIn):
    """Feedback on a paragraph. It gives comments with a place in the text. It gives no rewritten text."""
    try:
        with llm.cache_scope(""), llm.ai_context("coach", ""):
            return coach.review(body.text)
    except coach.CoachError as e:
        raise HTTPException(400, str(e))


CRIT = [Depends(auth.require_auth), Depends(features.require("critique"))]


@app.post("/api/papers/{pid}/critique", dependencies=CRIT)
def run_critique(pid: str):
    must_get(pid)
    try:
        with llm.cache_scope(pid), llm.ai_context("critique", pid):
            return critique.run(pid)
    except critique.CritiqueError as e:
        raise HTTPException(400, str(e))
    except llm.LLMError as e:
        raise HTTPException(502, str(e))


@app.get("/api/papers/{pid}/critique", dependencies=CRIT)
def get_critique(pid: str):
    must_get(pid)
    return critique.view(pid) or {"items": [], "label": critique.LABEL, "paper_id": pid}


class CritiqueEditIn(BaseModel):
    answers: dict = {}
    confirm: bool = False


@app.put("/api/papers/{pid}/critique", dependencies=CRIT)
def edit_critique(pid: str, body: CritiqueEditIn):
    must_get(pid)
    try:
        out = critique.edit(pid, body.answers, body.confirm)
    except critique.CritiqueError as e:
        raise HTTPException(400, str(e))
    game_event(game.refresh)  # an edited or confirmed check counts for the level Critic
    return out


# ---------- literature review builder ----------
def run_writing(fn, *args):
    try:
        return fn(*args)
    except writing.WritingError as e:
        raise HTTPException(400, str(e))


@app.get("/api/review-doc", dependencies=LIT)
def get_review_doc(style: str = "apa"):
    if style not in cite.STYLES:
        raise HTTPException(400, "The style must be apa or ieee.")
    return writing.view(style)


@app.post("/api/review-doc/outline", dependencies=LIT)
def make_outline():
    """One section for each sub-question. Headings only. No AI text. A section that exists keeps its text."""
    writing.outline()
    return writing.view()


class SectionIn(BaseModel):
    text: str | None = None
    heading: str | None = None


@app.put("/api/review-doc/sections/{sid}", dependencies=LIT)
def put_section(sid: str, body: SectionIn):
    s = run_writing(writing.save_text, sid, body.text, body.heading)
    game_event(game.refresh)  # 300 words in a section count for the level Author
    return {**s, "words": writing.count_words(s["text"]), "unverified_quotes": [q["line"] for q in writing.check_quotes(s["text"]) if not q["found"]], "words_today": db.words_on(game.local_date(db.now()))}


@app.post("/api/review-doc/sections", dependencies=LIT)
def add_section(body: SectionIn):
    heading = " ".join((body.heading or "").split())
    if not heading or len(heading) > 200:
        raise HTTPException(400, "The heading must have 1 to 200 characters.")
    return db.review_section_add(db.review_doc()["id"], heading)


@app.delete("/api/review-doc/sections/{sid}", dependencies=LIT)
def delete_section(sid: str):
    if not db.review_section_delete(sid):
        raise HTTPException(404, "Section not found.")
    return {"ok": True}


class OrderIn(BaseModel):
    ids: list[str]


@app.put("/api/review-doc/order", dependencies=LIT)
def put_order(body: OrderIn):
    db.review_sections_order(db.review_doc()["id"], body.ids)
    return writing.view()


class DocTitleIn(BaseModel):
    title: str


@app.put("/api/review-doc/title", dependencies=LIT)
def put_doc_title(body: DocTitleIn):
    title = " ".join(body.title.split())
    if not title or len(title) > 200:
        raise HTTPException(400, "The title must have 1 to 200 characters.")
    db.review_doc_title(title)
    return writing.view()


@app.get("/api/review-doc/export", dependencies=LIT)
def export_review_doc(format: str = "md", style: str = "apa"):
    if style not in cite.STYLES:
        raise HTTPException(400, "The style must be apa or ieee.")
    if format == "md":
        return Response(writing.export_markdown(style), media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="literature-review.md"'})
    if format == "docx":
        return Response(writing.export_docx(style), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": 'attachment; filename="literature-review.docx"'})
    raise HTTPException(400, "The format must be md or docx.")


# ---------- Quests, boss fights, companion ----------
QUESTS = [Depends(auth.require_auth), Depends(features.require("quests"))]


@app.get("/api/quests", dependencies=QUESTS)
def get_quests(date: str | None = None, tz: int | None = None):
    """The quests of this week (3 offered, up to 2 chosen), with the progress. The log of the quests that are done."""
    return quests.summary(run_today(student_today, date, tz))


@app.post("/api/quests/{code}/choose", dependencies=QUESTS)
def choose_quest(code: str, date: str | None = None):
    try:
        quests.choose(run_today(student_today, date), code)
    except quests.QuestError as e:
        raise HTTPException(400, str(e))
    return quests.summary(run_today(student_today, date))


@app.post("/api/quests/{code}/drop", dependencies=QUESTS)
def drop_quest(code: str, date: str | None = None):
    try:
        quests.drop(run_today(student_today, date), code)
    except quests.QuestError as e:
        raise HTTPException(400, str(e))
    return quests.summary(run_today(student_today, date))


class BossIn(BaseModel):
    boss: bool


@app.post("/api/papers/{pid}/boss", dependencies=QUESTS)
def set_boss(pid: str, body: BossIn):
    """Mark a hard paper as a boss, or take the mark away. A boss is defeated when the quiz and the Feynman check both reach 80%."""
    must_get(pid)
    quests.set_boss(pid, body.boss)
    game_event(quests.check_bosses)
    return quests.boss_status(pid)


@app.get("/api/bosses", dependencies=QUESTS)
def get_bosses():
    game_event(quests.check_bosses)
    return quests.bosses()


@app.get("/api/companion", dependencies=[Depends(auth.require_auth), Depends(features.require("duck"))])
def get_companion(event: str = "", seed: str = ""):
    """Duck. Fixed messages, no AI. With an event: the message for it. Without: all the events."""
    return {"message": companion.message(event, seed) if event else "", "events": sorted(companion.MESSAGES)}


# ---------- Knowledge Garden: spaced review, and the Expedition map ----------
REVIEW = [Depends(auth.require_auth), Depends(features.require("review"))]


def student_today(date: str | None, tz: int | None = None) -> str:
    if tz is not None:
        game.set_timezone(tz)
    return today.clean_date(date) if date else game.local_date(db.now())


@app.get("/api/review/due", dependencies=REVIEW)
def review_due(date: str | None = None, tz: int | None = None, paper_id: str | None = None, limit: int = 50):
    d = run_today(student_today, date, tz)
    items, total = review.due_items(d, paper_id, min(max(limit, 1), review.MAX_DUE))
    return {"date": d, "total": total, "items": items}


@app.get("/api/review/garden", dependencies=REVIEW)
def review_garden(date: str | None = None, tz: int | None = None):
    return review.garden(run_today(student_today, date, tz))


class RatingIn(BaseModel):
    rating: str
    date: str | None = None


@app.post("/api/review/{item_id}", dependencies=REVIEW)
def review_rate(item_id: str, body: RatingIn):
    """The student rates an item (again, hard, good, easy). FSRS sets the next date. The server gives the points: 2 for each review, 20 a day at most."""
    try:
        out = review.answer(item_id, body.rating, run_today(student_today, body.date), db.now())
    except review.ReviewError as e:
        raise HTTPException(400, str(e))
    out["xp_gained"] = game.XP["review"] if game_event(game.check_review, item_id, out.pop("reps")) else 0
    return out


@app.get("/api/journey/map", dependencies=[Depends(auth.require_auth), Depends(features.require("map"))])
def journey_map():
    """The six regions of the PhD road, each with a percent, a state and a kind first step."""
    return journey.build()


# ---------- Game: points, levels, streak, badges, own rewards ----------
GAME = [Depends(auth.require_auth), Depends(features.require("game"))]


@app.get("/api/game", dependencies=GAME)
def get_game(date: str | None = None, tz: int | None = None):
    """tz: the offset of the time zone of the student, in minutes (for example 60). It decides which day an XP event belongs to."""
    if tz is not None:
        game.set_timezone(tz)
    game.refresh()
    return run_today(lambda: game.summary(today.clean_date(date) if date else game.local_date(db.now())))


@app.get("/api/game/events", dependencies=GAME)
def game_events(limit: int = 50):
    return [{**e, "label": game.ACTION_LABEL.get(e["action"], e["action"])} for e in db.xp_recent(min(max(limit, 1), 500))]


class GameSettingsIn(BaseModel):
    weekend_off: bool


@app.put("/api/game/settings", dependencies=GAME)
def put_game_settings(body: GameSettingsIn):
    db.set_setting("weekend_off", "1" if body.weekend_off else "0")
    return {"weekend_off": game.weekend_off()}


class RewardIn(BaseModel):
    text: str
    condition: str


@app.post("/api/rewards", dependencies=GAME)
def add_reward(body: RewardIn):
    """Your own reward. Example: "A dinner out" with the condition "level:3". Conditions: level:N, xp:N, streak:N, cards:N."""
    text = run_today(today.clean_text, body.text, 120, "reward")
    if not game.parse_condition(body.condition):
        raise HTTPException(400, "The condition must look like level:3, xp:500, streak:7 or cards:20.")
    r = db.reward_add(text, body.condition.strip().lower())
    game.refresh()
    return db.reward_get(r["id"])


@app.post("/api/rewards/{rid}/claim", dependencies=GAME)
def claim_reward(rid: str):
    r = db.reward_get(rid)
    if not r:
        raise HTTPException(404, "Reward not found.")
    if not r["earned_at"]:
        raise HTTPException(400, "You did not earn this reward yet.")
    db.reward_claim(rid)
    return db.reward_get(rid)


@app.delete("/api/rewards/{rid}", dependencies=GAME)
def delete_reward(rid: str):
    if not db.reward_delete(rid):
        raise HTTPException(404, "Reward not found.")
    return {"ok": True}


# ---------- AI use log ----------
@app.get("/api/ai-log", dependencies=[Depends(auth.require_auth)])
def ai_log(limit: int = 100):
    """Each answer of an AI provider, with the feature and the paper. Saved answers are not in the list, because the AI did not help again."""
    return db.ai_log_list(min(max(limit, 1), 1000))


# ---------- search, links, backup ----------
@app.get("/api/search", dependencies=[Depends(auth.require_auth)])
def search(q: str, limit: int = 8):
    q = q.strip()
    if len(q) < 2:
        return []
    out, titles = [], {}
    for r in vectors.search(q, min(max(limit, 1), 20)):
        t = titles.get(r["paper_id"])
        if t is None:
            p = db.get_paper(r["paper_id"])
            t = titles[r["paper_id"]] = (p or {}).get("title", "")
        r["title"] = t
        out.append(r)
    return out


class ChatIn(BaseModel):
    question: str
    paper_ids: list[str]
    history: list[dict] = []


@app.post("/api/chat", dependencies=[Depends(auth.require_auth), Depends(features.require("chat"))])
def chat_ask(body: ChatIn):
    try:
        with llm.ai_context("chat", ",".join(dict.fromkeys(body.paper_ids))):
            return chat.ask(body.question, body.paper_ids, body.history)
    except chat.ChatError as e:
        raise HTTPException(400, str(e))
    except llm.LLMError as e:
        raise HTTPException(502, str(e))


class ExplainIn(BaseModel):
    a: str
    b: str
    refresh: bool = False


@app.post("/api/links/explain", dependencies=[Depends(auth.require_auth)])
def explain_link(body: ExplainIn):
    """What links two papers, and how they differ. The answer is saved for the pair."""
    if body.a == body.b:
        raise HTTPException(400, "Choose two different papers.")
    for pid in (body.a, body.b):
        if must_get(pid)["status"] != "ready":
            raise HTTPException(409, "A paper is not ready yet.")
    try:
        with llm.cache_scope("", body.refresh), llm.ai_context("link", f"{body.a},{body.b}"):
            out = links.explain(body.a, body.b, body.refresh)
        game_event(game.check_link, body.a, body.b, out.get("evidence", []))  # both PDFs must have a verified quote
        return out
    except chat.ChatError as e:
        raise HTTPException(400, str(e))
    except llm.LLMError as e:
        raise HTTPException(502, str(e))


@app.get("/api/graph", dependencies=[Depends(auth.require_auth)])
def graph():
    return links.build_graph()


@app.get("/api/export", dependencies=[Depends(auth.require_auth)])
def export():
    papers, tags = [], db.all_tags()
    for p in db.list_papers():
        d = {k: p[k] for k in ("id", "filename", "title", "purpose", "focus", "n_pages", "created_at")}
        d["pages"], d["card"] = db.get_pages(p["id"]), db.get_card(p["id"])
        d["extra_cards"] = [{"id": x["id"], "focus": x["focus"], "purpose": x["purpose"], "card": x["card"]} for x in db.list_extra(p["id"]) if x["card"]]
        d["tags"] = tags.get(p["id"], {})
        d["is_boss"], d["boss_defeated_at"] = int(p.get("is_boss") or 0), p.get("boss_defeated_at")
        d["meta"] = {k: p.get(k) or "" for k in ("authors", "year", "venue", "doi", "cite_key", "meta_check", "meta_source")}
        papers.append(d)
    proj = db.get_project()
    glossary = [{k: g[k] for k in ("id", "term", "explanation", "source", "paper_id", "page", "created_at")} for g in db.glossary_list()]
    return {"version": 1, "thesis_question": proj["question"], "papers": papers,
            "project": {"title": proj["title"], "question": proj["question"], "stage": proj["stage"], "sub_questions": db.list_sub_questions()},
            "glossary": glossary, "ai_log": db.ai_log_list(100000)["rows"],
            "explanations": [{k: e[k] for k in ("id", "paper_id", "card_id", "text", "score", "created_at", "result")} for e in db.explanation_list_all()],
            "quiz": [{k: r[k] for k in ("id", "paper_id", "question", "answer", "quote", "page", "card_id", "created_at")} for r in db.review_list(kind="quiz")],
            "gap_runs": [{k: r[k] for k in ("id", "sub_question_id", "paper_ids", "result", "created_at")} for r in db.gap_runs_all()],
            "gaps": [{k: g[k] for k in ("id", "sub_question_id", "text", "reason", "status", "run_id", "created_at")} for g in db.gaps_list()],
            "critiques": [{"paper_id": c["paper_id"], "data": c["data"], "edited": c["edited"], "confirmed": c["confirmed"], "created_at": c["created_at"]} for c in db.critiques_all()],
            "review_doc": {"title": db.review_doc()["title"], "sections": [{k: s[k] for k in ("id", "position", "heading", "sub_question_id", "text")} for s in db.review_sections(db.review_doc()["id"])]},
            "review_state": db.review_state_rows(), "quests_active": db.quests_all(), "activity": db.activity_list(),
            "xp_events": db.xp_all(), "badges": db.badges_list(), "rewards": db.rewards_list(), "weekend_off": game.weekend_off(),
            "goals": db.goals_all(), "wins": db.wins_list(100000), "focus_sessions": db.focus_list(),
            "play_rounds": [r for r in db.play_rounds_all() if r["finished"]], "play_items": db.play_items_list(), "to_read": db.to_read_list()}


def restore_project(data: dict) -> None:
    """A restore fills only what is empty. It never replaces what the student has written. It writes no history."""
    saved, old = db.get_project(), data.get("project") if isinstance(data.get("project"), dict) else {}
    want = {"title": str(old.get("title") or "")[:project.MAX_TITLE], "stage": str(old.get("stage") or ""),
            "question": str(old.get("question") or data.get("thesis_question") or "")[:project.MAX_QUESTION]}
    if want["stage"] not in db.STAGES:
        want["stage"] = ""
    db.save_project({k: v for k, v in want.items() if v and not saved[k]}, record=False)
    if not db.list_sub_questions():
        for s in (old.get("sub_questions") or [])[:db.MAX_SUB_QUESTIONS]:
            sid = str((s or {}).get("id", ""))
            text = " ".join(str((s or {}).get("text", "")).split())[:project.MAX_SUB_TEXT]
            if sid.isalnum() and len(sid) <= 32 and text:
                db.add_sub_question(text, sid)


def restore_tags(pid: str, tags) -> None:
    """Tags of a restored paper. A tag of a sub-question that does not exist is dropped."""
    known = {s["id"] for s in db.list_sub_questions()}
    for cid, ids in (tags if isinstance(tags, dict) else {}).items():
        if isinstance(ids, list) and (not cid or cid in {x["id"] for x in db.list_extra(pid)}):
            db.set_tags(pid, str(cid), [s for s in ids if s in known])


@app.post("/api/import", dependencies=[Depends(auth.require_auth)])
def import_backup(data: dict, background: BackgroundTasks):
    if data.get("version") != 1 or not isinstance(data.get("papers"), list):
        raise HTTPException(400, "This is not a Research_Pal backup file.")
    added = 0
    restore_project(data)
    for d in data["papers"]:
        pid = str(d.get("id", ""))
        if not pid.isalnum() or len(pid) > 32 or db.get_paper(pid):
            continue
        db.add_paper(pid, str(d.get("filename", "paper.pdf"))[:200], str(d.get("purpose", ""))[:500], str(d.get("focus") or "")[:200])
        db.update_paper(pid, title=str(d.get("title", ""))[:300], n_pages=int(d.get("n_pages") or 0), status="queued",
                        is_boss=1 if d.get("is_boss") else 0, boss_defeated_at=d.get("boss_defeated_at"))
        meta = d.get("meta") if isinstance(d.get("meta"), dict) else {}
        if meta:
            db.update_paper(pid, authors=str(meta.get("authors") or "[]")[:4000], year=str(meta.get("year") or "")[:4], venue=str(meta.get("venue") or "")[:200],
                            doi=str(meta.get("doi") or "")[:200], cite_key=str(meta.get("cite_key") or "")[:100], meta_check=str(meta.get("meta_check") or "[]")[:200],
                            meta_source=str(meta.get("meta_source") or "")[:20])
        db.save_pages(pid, [str(t) for t in d.get("pages", [])])
        if isinstance(d.get("card"), dict):
            db.save_card(pid, d["card"])
        for x in d.get("extra_cards") or []:
            xid = str(x.get("id", ""))
            if isinstance(x.get("card"), dict) and xid.isalnum() and len(xid) <= 32:
                try:
                    db.add_extra(pid, str(x.get("focus") or "")[:200], str(x.get("purpose") or "")[:500], xid, x["card"])
                except db.INTEGRITY_ERRORS:
                    pass  # this card id exists already
        restore_tags(pid, d.get("tags"))
        background.add_task(reindex_paper, pid)
        added += 1
    for g in data.get("glossary") or []:  # the words and the AI use log are part of the backup. A row that exists is skipped.
        try:
            if str(g.get("source")) in ("paper", "ai") and str(g.get("id", "")).isalnum():
                db.glossary_add(str(g["term"])[:80], str(g["explanation"])[:3000], str(g["source"]), str(g.get("paper_id", "")), int(g.get("page") or 0), str(g["id"]), float(g.get("created_at") or 0) or None)
        except (KeyError, TypeError, ValueError, *db.INTEGRITY_ERRORS):
            pass
    for e in data.get("explanations") or []:  # the attempts and the quiz questions are part of the backup. A row that exists is skipped.
        try:
            if str(e["id"]).isalnum() and not db.explanation_get(str(e["id"])) and isinstance(e.get("result"), dict):
                db.explanation_add(str(e["paper_id"]), str(e.get("card_id", "")), str(e["text"])[:3000], e["result"], int(e.get("score") or 0), str(e["id"]), float(e.get("created_at") or 0) or None)
        except (KeyError, TypeError, ValueError):
            pass
    for r in data.get("quiz") or []:
        try:
            if str(r["id"]).isalnum() and not db.review_get(str(r["id"])):
                db.review_add("quiz", str(r["paper_id"]), str(r["question"])[:300], str(r["answer"])[:400], str(r["quote"])[:600], int(r.get("page") or 0), str(r.get("card_id", "")), "", str(r["id"]), float(r.get("created_at") or 0) or None)
        except (KeyError, TypeError, ValueError):
            pass
    for r in data.get("gap_runs") or []:  # gaps and quality checks are part of the backup. A row that exists is skipped.
        try:
            if str(r["id"]).isalnum() and not db.gap_run_get(str(r["id"])) and isinstance(r.get("result"), dict):
                db.gap_run_add(str(r.get("sub_question_id") or ""), [str(p) for p in r.get("paper_ids") or []], r["result"], str(r["id"]), float(r.get("created_at") or 0) or None)
        except (KeyError, TypeError, ValueError):
            pass
    for g in data.get("gaps") or []:
        try:
            if str(g["id"]).isalnum() and not db.gap_get(str(g["id"])) and g.get("status") in gaps.STATUSES:
                db.gap_add(str(g.get("sub_question_id") or ""), str(g["text"])[:400], str(g.get("reason") or "")[:400], str(g.get("run_id") or ""), str(g["id"]), g["status"], float(g.get("created_at") or 0) or None)
        except (KeyError, TypeError, ValueError):
            pass
    for c in data.get("critiques") or []:
        try:
            if db.get_paper(str(c["paper_id"])) and not db.critique_get(str(c["paper_id"])) and isinstance(c.get("data"), dict):
                db.critique_save(str(c["paper_id"]), c["data"], bool(c.get("edited")), bool(c.get("confirmed")), float(c.get("created_at") or 0) or None)
        except (KeyError, TypeError, ValueError):
            pass
    doc = data.get("review_doc") if isinstance(data.get("review_doc"), dict) else None
    if doc and not db.review_sections(db.review_doc()["id"]):  # a restore never replaces a document that has sections
        db.review_doc_title(str(doc.get("title") or "Literature review")[:200])
        for s in (doc.get("sections") or [])[:200]:
            if isinstance(s, dict) and str(s.get("heading", "")).strip():
                db.review_section_add(db.review_doc()["id"], str(s["heading"])[:200], str(s.get("sub_question_id") or ""), str(s.get("text") or "")[:writing.MAX_TEXT], str(s["id"]) if str(s.get("id", "")).isalnum() else None)
    for q in data.get("quests_active") or []:  # quests and bosses are part of the backup
        try:
            if quests.by_code(q["code"]) and str(q["id"]).isalnum():
                db.quest_offer(q["code"], str(q["week"]), str(q["id"]), q.get("chosen_at"), q.get("done_at"))
        except (KeyError, TypeError, ValueError):
            pass
    for a in data.get("activity") or []:
        try:
            if str(a["id"]).isalnum() and a["kind"] == "eli12_view":
                db.activity_add("eli12_view", str(a["ref_id"]), str(a["id"]), float(a["time"]), today.clean_date(a["date"]))
        except (KeyError, TypeError, ValueError, today.TodayError):
            pass
    for s in data.get("review_state") or []:  # the dates of the review. The items come from the cards, the quiz and the glossary.
        try:
            db.review_restore_state({"id": str(s["id"]), "kind": str(s["kind"]), "ref_id": str(s.get("ref_id") or ""), "due": float(s["due"]), "stability": s.get("stability"),
                                     "difficulty": s.get("difficulty"), "reps": int(s.get("reps") or 0), "lapses": int(s.get("lapses") or 0),
                                     "last_review": s.get("last_review"), "fsrs_json": s.get("fsrs_json")})
        except (KeyError, TypeError, ValueError):
            pass
    for e in data.get("xp_events") or []:  # points, badges and rewards are part of the backup. The UNIQUE key stops a second row.
        try:
            if str(e["id"]).isalnum() and e["action"] in game.ACTION_LABEL:
                db.xp_restore({"id": str(e["id"]), "time": float(e["time"]), "date": today.clean_date(e["date"]), "action": e["action"], "ref_id": str(e["ref_id"]), "xp": int(e["xp"])})
        except (KeyError, TypeError, ValueError, today.TodayError):
            pass
    for b in data.get("badges") or []:
        try:
            if b["code"] in game.BADGES or str(b["code"]).startswith("boss:"):
                db.badge_restore(b["code"], float(b["earned_at"]))
        except (KeyError, TypeError, ValueError):
            pass
    for r in data.get("rewards") or []:
        try:
            if str(r["id"]).isalnum() and not db.reward_get(str(r["id"])) and game.parse_condition(r["condition"]):
                db.reward_add(str(r["text"])[:120], str(r["condition"]), str(r["id"]), r.get("earned_at"), bool(r.get("claimed")), float(r.get("created_at") or 0) or None)
        except (KeyError, TypeError, ValueError):
            pass
    if data.get("weekend_off") is not None:
        db.set_setting("weekend_off", "1" if data["weekend_off"] else "0")
    for g in data.get("goals") or []:  # goals, wins and focus sessions are part of the backup. A row that exists is skipped.
        try:
            if str(g["id"]).isalnum() and not db.goal_get(str(g["id"])) and g.get("kind") in today.GOAL_KINDS:
                db.goal_add(today.clean_date(g["date"]), str(g["text"])[:today.MAX_GOAL_TEXT], g["kind"], int(g.get("target") or 0), str(g["id"]), bool(g.get("done")), float(g.get("created_at") or 0) or None)
        except (KeyError, TypeError, ValueError, today.TodayError):
            pass
    for w in data.get("wins") or []:
        try:
            if str(w["id"]).isalnum() and not db.win_get(str(w["id"])):
                db.win_add(today.clean_date(w["date"]), str(w["text"])[:today.MAX_WIN_TEXT], str(w["id"]), float(w.get("created_at") or 0) or None)
        except (KeyError, TypeError, ValueError, today.TodayError):
            pass
    for s in data.get("focus_sessions") or []:
        try:
            if str(s["id"]).isalnum() and s.get("end") is not None:
                db.focus_restore({"id": str(s["id"]), "start": float(s["start"]), "end": float(s["end"]), "minutes": int(s.get("minutes") or 0),
                                  "task_text": str(s.get("task_text", ""))[:today.MAX_TASK_TEXT], "paper_id": str(s.get("paper_id", "")), "date": today.clean_date(s["date"]),
                                  "planned": int(s.get("planned") or 0), "goal_id": str(s.get("goal_id", ""))})
        except (KeyError, TypeError, ValueError, today.TodayError):
            pass
    for r in data.get("ai_log") or []:
        try:
            row = {"time": float(r["time"]), "feature": str(r["feature"])[:40], "paper_id": str(r.get("paper_id", ""))[:200], "provider": str(r["provider"])[:40], "model": str(r["model"])[:100]}
            if not db.ai_log_has(row):
                db.ai_log_add(row["feature"], row["paper_id"], row["provider"], row["model"], row["time"])
        except (KeyError, TypeError, ValueError):
            pass
    for r in data.get("to_read") or []:  # the To read list is part of the backup. An item that exists is skipped.
        try:
            if str(r["id"]).isalnum():
                db.to_read_add(r, str(r["id"]), float(r.get("added_at") or 0) or None)
        except (KeyError, TypeError, ValueError):
            pass
    for r in data.get("play_rounds") or []:  # the coins of the mini-games are part of the backup
        try:
            rid = str(r["id"])
            if rid.isalnum() and r["game"] in play.GAMES and not db.play_round_get(rid):
                db.play_round_add(r["game"], r["questions"], str(r["date"]), rid)
                db.play_round_finish(rid, int(r["score"]), int(r["coins"]))
        except (KeyError, TypeError, ValueError):
            pass
    for i in data.get("play_items") or []:
        try:
            if str(i["code"]) in play.PRICE:
                db.play_item_buy(str(i["code"]), float(i.get("bought_at") or 0) or None, int(i.get("x", -1)), int(i.get("y", -1)))
        except (KeyError, TypeError, ValueError):
            pass
    return {"added": added}


# ---------- Duck Island: a game world, mini-games on verified quotes, coins and a shop ----------
PLAY = [Depends(auth.require_auth), Depends(features.require("play"))]


def run_play(fn, *args):
    try:
        return fn(*args)
    except play.PlayError as e:
        raise HTTPException(400, str(e))


@app.get("/api/play", dependencies=PLAY)
def play_state():
    return play.view()


@app.post("/api/play/rounds", dependencies=PLAY)
def play_new_round(body: dict):
    return run_play(play.make_round, str(body.get("game", "")))


@app.post("/api/play/rounds/{rid}/finish", dependencies=PLAY)
def play_finish_round(rid: str, body: dict):
    return run_play(play.finish_round, rid, body.get("answers"))


@app.post("/api/play/buy", dependencies=PLAY)
def play_buy(body: dict):
    return run_play(play.buy, str(body.get("code", "")))


@app.put("/api/play/items/{code}", dependencies=PLAY)
def play_place(code: str, body: dict):
    return run_play(play.place, code, body.get("x"), body.get("y"))


# ---------- Find papers: add by DOI, import BibTeX or RIS, the To read list (Sprint 10) ----------
FIND = [Depends(auth.require_auth), Depends(features.require("findpapers"))]
SOURCE_FIELDS = ("authors", "year", "venue")


class FromIdIn(BaseModel):
    query: str
    add_to_read: bool = False


def apply_source_meta(pid: str, meta: dict, verified: bool) -> None:
    """Save the metadata of a source. It has the label of the source. A value that the PDF does not show stays in the list "Check"."""
    p = db.get_paper(pid)
    if not p or p.get("meta_source") == "student":
        return  # never replace what the student wrote
    raw = {"authors": meta.get("authors") or [], "year": meta.get("year") or "", "venue": meta.get("venue") or ""}
    values = {"authors": [cite.parse_author(a) for a in raw["authors"][:metadata.MAX_AUTHORS] if a], "year": raw["year"] if re.fullmatch(r"(19|20)\d\d", raw["year"]) else "",
              "venue": raw["venue"][:200], "doi": (meta.get("doi") or "").lower()}
    if verified:
        found = metadata.verify(raw, db.get_pages(pid))
        check = [c for c in found["check"] if c != "doi"]  # a value that the PDF does not show stays in the list "Check"
        if found["doi"] and not values["doi"]:
            values["doi"] = found["doi"]
        elif found["doi"] and found["doi"].lower() != values["doi"]:
            check.append("doi")  # the PDF has another DOI than the one that you asked for: maybe a wrong PDF. The student must check.
    else:
        check = list(SOURCE_FIELDS)  # nothing is checked yet: the PDF is not here
    metadata.save(pid, values, sorted(set(check)), meta.get("source") or "source")


def process_from_source(pid: str, meta: dict) -> None:
    process_paper(pid)
    if (db.get_paper(pid) or {}).get("status") == "ready":
        apply_source_meta(pid, meta, True)


def write_pdf(pid: str, data: bytes) -> None:
    try:
        files.save(pid, data)
    except files.StorageError as e:
        raise HTTPException(503, str(e))


def new_paper_from_meta(meta: dict, data: bytes | None, background: BackgroundTasks) -> dict:
    pid = db.new_id()
    db.add_paper(pid, (meta["title"][:80] or "paper") + ".pdf", "", "", "queued" if data else "no_pdf", meta["title"][:300])
    apply_source_meta(pid, meta, False)
    if data:
        write_pdf(pid, data)
        background.add_task(process_from_source, pid, meta)
    return {"id": pid, "status": "queued" if data else "no_pdf", "title": meta["title"]}


def run_sources(fn, *args):
    try:
        return fn(*args)
    except sources.SourceError as e:
        raise HTTPException(502, str(e))


def to_read_item(meta: dict, source: str) -> dict:
    s = triage.score(meta.get("abstract") or meta["title"])
    return {**meta, "score": s["score"], "reason": s["reason"], "source": source}


@app.post("/api/papers/from-id", dependencies=FIND)
def paper_from_id(body: FromIdIn, background: BackgroundTasks):
    """A DOI, an arXiv link or a title. The app finds the metadata and a free PDF. Without a free PDF the paper has the status no_pdf."""
    try:
        query = sources.parse_input(body.query)
    except sources.SourceError as e:
        raise HTTPException(400, str(e))
    meta = run_sources(sources.find, query)
    old = db.paper_exists(meta["doi"], meta["title"])
    if old:
        return {"id": old["id"], "status": "exists", "title": old["title"], "message": "This paper is in your library already."}
    if body.add_to_read:
        item = db.to_read_add(to_read_item(meta, meta["source"]))
        return {"status": "to_read" if item else "exists", "title": meta["title"], "message": "Added to your To read list." if item else "This paper is in your To read list already."}
    data = sources.download_pdf(meta["pdf_urls"])
    out = new_paper_from_meta(meta, data, background)
    out["message"] = "The app is reading the paper." if data else "No free PDF was found. The paper is in your library. Upload the PDF to read it."
    return out


@app.post("/api/papers/{pid}/pdf", dependencies=FIND)
async def upload_pdf_for(pid: str, background: BackgroundTasks, file: UploadFile = File(...)):
    """The student adds the PDF of a paper that has no PDF yet."""
    p = must_get(pid)
    if p["status"] != "no_pdf":
        raise HTTPException(400, "This paper has a PDF already.")
    data = await file.read(config.MAX_UPLOAD_BYTES + 1)
    if not data.startswith(b"%PDF-"):
        raise HTTPException(400, "This file is not a PDF.")
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"The file is larger than {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    write_pdf(pid, data)
    db.update_paper(pid, status="queued", error="")
    meta = {"authors": cite.authors_of(p), "year": p.get("year") or "", "venue": p.get("venue") or "", "doi": p.get("doi") or "", "source": p.get("meta_source") or "source"}
    background.add_task(process_from_source, pid, meta)
    return {"id": pid, "status": "queued"}


@app.post("/api/import/bib", dependencies=FIND)
async def import_bib(background: BackgroundTasks, file: UploadFile = File(...), pdfs: list[UploadFile] = File(default=[])):
    """A .bib or .ris file (for example from Zotero) and, if you like, the PDFs. An entry with its PDF becomes a paper. An entry without a PDF goes to the To read list."""
    raw = await file.read(bibimport.MAX_FILE_CHARS + 1)
    try:
        entries = bibimport.parse(file.filename or "", raw.decode("utf-8", "replace"))
    except bibimport.ImportError_ as e:
        raise HTTPException(400, str(e))
    files: dict[str, bytes] = {}
    for f in pdfs:
        data = await f.read(config.MAX_UPLOAD_BYTES + 1)
        if data.startswith(b"%PDF-") and len(data) <= config.MAX_UPLOAD_BYTES:
            files[(f.filename or "").rsplit("/", 1)[-1]] = data
    added = to_read = skipped = 0
    for e in entries:
        meta = {**e, "source": "import"}
        if db.paper_exists(e["doi"], e["title"]):
            skipped += 1
            continue
        name = bibimport.match_pdf(e, files)
        if name:
            new_paper_from_meta(meta, files[name], background)
            added += 1
        elif db.to_read_add(to_read_item(meta, "import")):
            to_read += 1
        else:
            skipped += 1
    return {"entries": len(entries), "added": added, "to_read": to_read, "skipped": skipped,
            "message": f"{added} added to the library, {to_read} added to the To read list, {skipped} skipped (already there)."}


def rescore_to_read() -> None:
    """The scores depend on the question and the sub-questions. When they change, the scores are made again."""
    import hashlib

    stamp = hashlib.sha1(json.dumps([db.thesis_question(), [s["text"] for s in db.list_sub_questions()]]).encode()).hexdigest()
    if db.get_setting("triage_stamp") == stamp:
        return
    tg = triage.targets()
    for it in db.to_read_list():
        s = triage.score(it["abstract"] or it["title"], tg)
        db.to_read_set(it["id"], score=s["score"], reason=s["reason"])
    db.set_setting("triage_stamp", stamp)


@app.get("/api/to-read", dependencies=FIND)
def get_to_read():
    rescore_to_read()
    return [i for i in db.to_read_list() if i["status"] == "new"]


class ToReadIn(BaseModel):
    status: str


@app.put("/api/to-read/{rid}", dependencies=FIND)
def put_to_read(rid: str, body: ToReadIn):
    if body.status not in ("new", "not_useful"):
        raise HTTPException(400, "The status must be new or not_useful.")
    if not db.to_read_get(rid):
        raise HTTPException(404, "Item not found.")
    db.to_read_set(rid, status=body.status)
    return db.to_read_get(rid)


@app.post("/api/to-read/{rid}/read", dependencies=FIND)
def read_to_read(rid: str, background: BackgroundTasks):
    """Read now: the app looks for a free PDF. If there is none, the item stays and the student uploads the PDF."""
    it = db.to_read_get(rid)
    if not it:
        raise HTTPException(404, "Item not found.")
    old = db.paper_exists(it["doi"], it["title"])
    if old:
        db.to_read_set(rid, status="read")
        return {"id": old["id"], "status": "exists"}
    meta = {"title": it["title"], "authors": it["authors"], "year": it["year"], "venue": it["venue"], "doi": it["doi"], "abstract": it["abstract"], "source": it["source"] or "source", "pdf_urls": []}
    try:
        found = sources.find({"doi": it["doi"]} if it["doi"] else {"title": it["title"]})
        meta["pdf_urls"] = found["pdf_urls"]
    except sources.SourceError:
        pass
    data = sources.download_pdf(meta["pdf_urls"])
    if not data:
        raise HTTPException(404, "No free PDF was found. Upload the PDF yourself.")
    out = new_paper_from_meta(meta, data, background)
    db.to_read_set(rid, status="read")
    return out


@app.post("/api/to-read/{rid}/upload", dependencies=FIND)
async def upload_to_read(rid: str, background: BackgroundTasks, file: UploadFile = File(...)):
    it = db.to_read_get(rid)
    if not it:
        raise HTTPException(404, "Item not found.")
    data = await file.read(config.MAX_UPLOAD_BYTES + 1)
    if not data.startswith(b"%PDF-"):
        raise HTTPException(400, "This file is not a PDF.")
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"The file is larger than {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    meta = {"title": it["title"], "authors": it["authors"], "year": it["year"], "venue": it["venue"], "doi": it["doi"], "source": it["source"] or "source"}
    out = new_paper_from_meta(meta, data, background)
    db.to_read_set(rid, status="read")
    return out
