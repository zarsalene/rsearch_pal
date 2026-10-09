"""PDF files. One-user mode: a folder on the disk. Multi-user mode: the private bucket "pdfs" in Supabase Storage.
In the bucket, each file is at <user id>/<paper id>.pdf, so users never share a path."""
import io
from pathlib import Path

import httpx

from . import auth, config

_BUCKET = "pdfs"


def _remote() -> bool:
    return config.USE_PG


def _local(pid: str) -> Path:
    return config.PDF_DIR / f"{pid}.pdf"


def _url(pid: str) -> str:
    return f"{config.SUPABASE_URL}/storage/v1/object/{_BUCKET}/{auth.current_user()}/{pid}.pdf"


def _headers() -> dict:
    return {"Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}", "apikey": config.SUPABASE_SERVICE_KEY}


class StorageError(Exception):
    """The file store did not answer. The message is for the user."""


def save(pid: str, data: bytes) -> None:
    if not _remote():
        config.PDF_DIR.mkdir(parents=True, exist_ok=True)
        _local(pid).write_bytes(data)
        return
    try:
        r = httpx.post(_url(pid), content=data, headers={**_headers(), "Content-Type": "application/pdf", "x-upsert": "true"}, timeout=120)
    except httpx.HTTPError:
        raise StorageError("Cannot reach the file store. Try again.")
    if r.status_code >= 300:
        raise StorageError(f"The file store refused the PDF (HTTP {r.status_code}).")


def read(pid: str) -> bytes | None:
    if not _remote():
        p = _local(pid)
        return p.read_bytes() if p.exists() else None
    try:
        r = httpx.get(_url(pid), headers=_headers(), timeout=120)
    except httpx.HTTPError:
        raise StorageError("Cannot reach the file store. Try again.")
    return r.content if r.status_code == 200 else None


def source(pid: str):
    """What pypdf reads: a path (local) or a file in memory (remote). None when there is no file."""
    if not _remote():
        return _local(pid) if _local(pid).exists() else None
    data = read(pid)
    return io.BytesIO(data) if data is not None else None


def exists(pid: str) -> bool:
    if not _remote():
        return _local(pid).exists()
    try:
        return httpx.head(_url(pid), headers=_headers(), timeout=30).status_code == 200
    except httpx.HTTPError:
        return False


def ids() -> set[str]:
    """The paper ids that have a file. One call for a whole list."""
    if not _remote():
        return {p.stem for p in config.PDF_DIR.glob("*.pdf")} if config.PDF_DIR.exists() else set()
    try:
        r = httpx.post(f"{config.SUPABASE_URL}/storage/v1/object/list/{_BUCKET}", headers=_headers(), timeout=30,
                       json={"prefix": auth.current_user(), "limit": 1000, "offset": 0})
        return {x["name"][:-4] for x in r.json() if str(x.get("name", "")).endswith(".pdf")} if r.status_code == 200 else set()
    except (httpx.HTTPError, ValueError):
        return set()


def delete(pid: str) -> None:
    if not _remote():
        _local(pid).unlink(missing_ok=True)
        return
    try:
        httpx.delete(_url(pid), headers=_headers(), timeout=30)
    except httpx.HTTPError:
        pass  # the paper is gone from the database. A file that stays is harmless and private.
