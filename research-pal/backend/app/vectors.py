"""Vector store (ChromaDB). Embeddings come from a backend that you choose with EMBEDDING_BACKEND:
default = local MiniLM model (no data goes out, but it needs about 400 MB of memory),
gemini = Gemini embedding API (very low memory, the text of the chunks goes to Google),
hash = tests only."""
import hashlib, math, re, threading, time

import chromadb
import httpx
from chromadb.config import Settings

from . import config, llm

_lock = threading.Lock()
_client = None
_ef = None
_dim = 384


def _hash_embed(text: str) -> list[float]:
    """Simple word-hash vectors. For tests only."""
    v = [0.0] * _dim
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        h = int(hashlib.md5(w.encode()).hexdigest(), 16)
        v[h % _dim] += 1.0 if (h >> 20) & 1 else -1.0
        v[(h >> 8) % _dim] += 0.5
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _gemini_embed(texts: list[str], query: bool) -> list[list[float]]:
    """Gemini embeddings. Up to 100 texts in one call. The vectors are normalised (needed when the size is below 3072)."""
    key = config.GEMINI_API_KEY
    if not key:
        raise llm.LLMUnavailable("GEMINI_API_KEY is missing. The server needs it for the embeddings.")
    model, task = config.GEMINI_EMBED_MODEL, "RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
    out: list[list[float]] = []
    for i in range(0, len(texts), 100):
        body = {"requests": [
            {"model": f"models/{model}", "content": {"parts": [{"text": t[:8000] or " "}]},
             "taskType": task, "outputDimensionality": config.GEMINI_EMBED_DIM}
            for t in texts[i : i + 100]
        ]}
        for attempt in range(4):
            try:
                r = httpx.post(url, json=body, headers={"x-goog-api-key": key}, timeout=60)
            except httpx.HTTPError:
                raise llm.LLMUnavailable("Cannot reach Gemini for the embeddings. Try again in a minute.")
            if r.status_code == 429 and attempt < 3:
                time.sleep(2 * (attempt + 1))  # free limit: wait and try again
                continue
            break
        if r.status_code != 200:
            raise llm.LLMUnavailable(f"Gemini embeddings failed (HTTP {r.status_code}). The free limit may be reached. Try again in a minute.")
        for e in r.json()["embeddings"]:
            v = [float(x) for x in e["values"]]
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
    return out


def embed(texts: list[str], query: bool = False) -> list[list[float]]:
    global _ef
    if config.EMBEDDING_BACKEND == "hash":
        return [_hash_embed(t) for t in texts]
    if config.EMBEDDING_BACKEND == "gemini":
        return _gemini_embed(texts, query)
    with _lock:
        if _ef is None:
            from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
            _ef = DefaultEmbeddingFunction()
    return [[float(x) for x in v] for v in _ef(texts)]


def _col(name: str):
    global _client
    with _lock:
        if _client is None:
            config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
            _client = chromadb.PersistentClient(path=str(config.CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
    if config.EMBEDDING_BACKEND == "gemini":
        name = f"{name}_gemini{config.GEMINI_EMBED_DIM}"  # the vector size differs from the local model
    return _client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"}, embedding_function=None)


def index_chunks(paper_id: str, chunks: list[dict]) -> None:
    col = _col("chunks")
    col.delete(where={"paper_id": paper_id})
    for i in range(0, len(chunks), 48):
        part = chunks[i : i + 48]
        col.add(
            ids=[f"{paper_id}:{c['id']}" for c in part],
            documents=[c["text"] for c in part],
            embeddings=embed([c["text"] for c in part]),
            metadatas=[{"paper_id": paper_id, "page": c["page"], "idx": c["idx"]} for c in part],
        )


def query_paper(paper_id: str, query: str, n: int = 4) -> list[dict]:
    col = _col("chunks")
    r = col.query(query_embeddings=embed([query], query=True), n_results=n, where={"paper_id": paper_id})
    return [{"page": m["page"], "idx": m["idx"], "text": d} for d, m in zip(r["documents"][0], r["metadatas"][0])]


def search(query: str, n: int = 8) -> list[dict]:
    col = _col("chunks")
    if col.count() == 0:
        return []
    r = col.query(query_embeddings=embed([query], query=True), n_results=min(n, col.count()))
    out = []
    for d, m, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0]):
        out.append({"paper_id": m["paper_id"], "page": m["page"], "text": d, "score": round(1 - float(dist), 3)})
    return out


def index_card(paper_id: str, text: str) -> None:
    col = _col("cards")
    col.upsert(ids=[paper_id], documents=[text], embeddings=embed([text]), metadatas=[{"paper_id": paper_id}])


def card_embeddings() -> dict[str, list[float]]:
    col = _col("cards")
    if col.count() == 0:
        return {}
    r = col.get(include=["embeddings"])
    return {i: [float(x) for x in e] for i, e in zip(r["ids"], r["embeddings"])}


def delete_paper(paper_id: str) -> None:
    _col("chunks").delete(where={"paper_id": paper_id})
    try:
        _col("cards").delete(ids=[paper_id])
    except Exception:
        pass
