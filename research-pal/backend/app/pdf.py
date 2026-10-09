"""Read a PDF: text of each page, and small chunks for search."""
import re

from pypdf import PdfReader

from . import config

REF_RE = re.compile(r"^\s*(references|bibliography|reference list)\s*$", re.I | re.M)


class PdfError(Exception):
    """Error that the user can understand and fix."""


def clean(t: str) -> str:
    t = t.replace("\x00", " ")
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def extract_pages(path) -> tuple[list[str], str]:
    """path: a file path, or a file in memory. None means that there is no file."""
    if path is None:
        raise PdfError("The PDF file is not on the server. Upload the paper again.")
    try:
        reader = PdfReader(path if hasattr(path, "read") else str(path))
        if reader.is_encrypted:
            if not reader.decrypt(""):
                raise PdfError("This PDF is protected by a password.")
        n = len(reader.pages)
        if n > config.MAX_PAGES:
            raise PdfError(f"This PDF has {n} pages. The limit is {config.MAX_PAGES}.")
        pages = [clean(p.extract_text() or "") for p in reader.pages]
        meta = ""
        try:
            meta = (reader.metadata.title or "").strip() if reader.metadata else ""
        except Exception:
            meta = ""
    except PdfError:
        raise
    except Exception as e:  # damaged file
        raise PdfError("The server cannot read this PDF file. It may be damaged.") from e
    if sum(len(p) for p in pages) < config.MIN_TEXT_CHARS:
        raise PdfError("This PDF has no text layer (probably a scan). Use a PDF with selectable text.")
    return pages, meta


def chunk_text(t: str, size: int = 1200, overlap: int = 150) -> list[str]:
    out, i = [], 0
    while i < len(t):
        j = min(len(t), i + size)
        if j < len(t):
            k = max(t.rfind(". ", i + size // 2, j), t.rfind("\n", i + size // 2, j))
            if k != -1:
                j = k + 1
        piece = t[i:j].strip()
        if len(piece) > 40:
            out.append(piece)
        if j >= len(t):
            break
        i = max(j - overlap, i + 1)
    return out


def chunk_pages(pages: list[str]) -> list[dict]:
    """Chunks with page numbers. Chunks of the reference list have refs=True."""
    n = len(pages)
    refs_from = None  # (page index, character position)
    for i in range(int(n * 0.4), n):
        m = None
        for m in REF_RE.finditer(pages[i]):
            pass
        if m:
            refs_from = (i, m.start())
            break
    chunks = []
    for i, text in enumerate(pages):
        refs = False
        if refs_from is not None:
            if i > refs_from[0]:
                refs = True
            elif i == refs_from[0]:
                text = text[: refs_from[1]]
        for k, piece in enumerate(chunk_text(text)):
            chunks.append({"id": f"{i + 1}-{k}", "page": i + 1, "idx": k, "text": piece, "refs": refs})
    return chunks
