"""Research_Pal API."""
import logging, re, threading, time
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from . import auth, cards, chat, config, db, features, files, links, llm, mindmap, pdf, ste, tts, vectors, words

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
            card = cards.generate(pid, pages, chunks, p["purpose"], db.get_setting("thesis_question"), meta, p.get("focus") or "")
            old = db.get_card(pid)
            for keep in ("notes", "mindmap"):  # notes and the mind map are not part of the reading. A new reading must keep them.
                if old and old.get(keep):
                    card[keep] = old[keep]
            db.save_card(pid, card)
            vectors.index_card(pid, cards.card_text(card))
            db.update_paper(pid, status="ready", error="", title=card["title"] or p["title"], n_pages=len(pages))
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
            card = cards.generate(pid, pages, chunks, x["purpose"], db.get_setting("thesis_question"), "", x["focus"])
            for keep in ("mindmap",):  # a new reading keeps the mind map of this card
                if x["card"] and x["card"].get(keep):
                    card[keep] = x["card"][keep]
            db.update_extra(cid, status="ready", error="", card=card)
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
        "thesis_question": db.get_setting("thesis_question"), "max_upload_mb": config.MAX_UPLOAD_BYTES // (1024 * 1024),
    }


class SettingsIn(BaseModel):
    thesis_question: str = ""


@app.put("/api/settings", dependencies=[Depends(auth.require_auth)])
def put_settings(body: SettingsIn):
    db.set_setting("thesis_question", body.thesis_question.strip()[:500])
    return {"ok": True}


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
    have = files.ids()
    return [paper_view(p, have) for p in db.list_papers()]


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


# ---------- listen (text to speech) ----------
class TTSIn(BaseModel):
    text: str


@app.post("/api/tts", dependencies=[Depends(auth.require_auth), Depends(features.require("tts"))])
def speak(body: TTSIn):
    """The voice of a short text, as a WAV file. The model is small and runs on the server CPU."""
    try:
        audio = tts.speak(body.text)
    except tts.TTSError as e:
        raise HTTPException(503 if "voice" in str(e).lower() else 400, str(e))
    return Response(audio, media_type="audio/wav", headers={"Cache-Control": "private, max-age=3600"})


@app.get("/api/papers/{pid}/read/{n}", dependencies=[Depends(auth.require_auth), Depends(features.require("tts"))])
def read_page(pid: str, n: int):
    """The text of one PDF page, in short passages for the voice. The page asks the voice for one passage at a time."""
    must_get(pid)
    pages = db.get_pages(pid)
    if not 1 <= n <= len(pages):
        raise HTTPException(404, "Page not found.")
    return {"page": n, "n_pages": len(pages), "passages": tts.passages(pages[n - 1])}


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
            return links.explain(body.a, body.b, body.refresh)
    except chat.ChatError as e:
        raise HTTPException(400, str(e))
    except llm.LLMError as e:
        raise HTTPException(502, str(e))


@app.get("/api/graph", dependencies=[Depends(auth.require_auth)])
def graph():
    return links.build_graph()


@app.get("/api/export", dependencies=[Depends(auth.require_auth)])
def export():
    papers = []
    for p in db.list_papers():
        d = {k: p[k] for k in ("id", "filename", "title", "purpose", "focus", "n_pages", "created_at")}
        d["pages"], d["card"] = db.get_pages(p["id"]), db.get_card(p["id"])
        d["extra_cards"] = [{"id": x["id"], "focus": x["focus"], "purpose": x["purpose"], "card": x["card"]} for x in db.list_extra(p["id"]) if x["card"]]
        papers.append(d)
    glossary = [{k: g[k] for k in ("id", "term", "explanation", "source", "paper_id", "page", "created_at")} for g in db.glossary_list()]
    return {"version": 1, "thesis_question": db.get_setting("thesis_question"), "papers": papers, "glossary": glossary, "ai_log": db.ai_log_list(100000)["rows"]}


@app.post("/api/import", dependencies=[Depends(auth.require_auth)])
def import_backup(data: dict, background: BackgroundTasks):
    if data.get("version") != 1 or not isinstance(data.get("papers"), list):
        raise HTTPException(400, "This is not a Research_Pal backup file.")
    added = 0
    if data.get("thesis_question") and not db.get_setting("thesis_question"):
        db.set_setting("thesis_question", str(data["thesis_question"])[:500])
    for d in data["papers"]:
        pid = str(d.get("id", ""))
        if not pid.isalnum() or len(pid) > 32 or db.get_paper(pid):
            continue
        db.add_paper(pid, str(d.get("filename", "paper.pdf"))[:200], str(d.get("purpose", ""))[:500], str(d.get("focus") or "")[:200])
        db.update_paper(pid, title=str(d.get("title", ""))[:300], n_pages=int(d.get("n_pages") or 0), status="queued")
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
        background.add_task(reindex_paper, pid)
        added += 1
    for g in data.get("glossary") or []:  # the words and the AI use log are part of the backup. A row that exists is skipped.
        try:
            if str(g.get("source")) in ("paper", "ai") and str(g.get("id", "")).isalnum():
                db.glossary_add(str(g["term"])[:80], str(g["explanation"])[:3000], str(g["source"]), str(g.get("paper_id", "")), int(g.get("page") or 0), str(g["id"]), float(g.get("created_at") or 0) or None)
        except (KeyError, TypeError, ValueError, *db.INTEGRITY_ERRORS):
            pass
    for r in data.get("ai_log") or []:
        try:
            row = {"time": float(r["time"]), "feature": str(r["feature"])[:40], "paper_id": str(r.get("paper_id", ""))[:200], "provider": str(r["provider"])[:40], "model": str(r["model"])[:100]}
            if not db.ai_log_has(row):
                db.ai_log_add(row["feature"], row["paper_id"], row["provider"], row["model"], row["time"])
        except (KeyError, TypeError, ValueError):
            pass
    return {"added": added}
