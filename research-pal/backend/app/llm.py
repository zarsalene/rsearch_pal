"""AI through an OpenAI-compatible API (Gemini, Groq, OpenRouter or Ollama).
Gemini is the default. If a provider fails, the next provider in the chain answers. The next call tries the first one again."""
import hashlib, json, logging, re, threading, time
from contextlib import contextmanager

import httpx

from . import config, db

log = logging.getLogger("research_pal")


class LLMError(Exception):
    """Error with a message that the user can read."""


class LLMTooLarge(LLMError):
    """The request is bigger than the limit of the provider. The caller can send less text."""


class LLMUnavailable(LLMError):
    """The provider cannot answer now: limit reached, outage, wrong key or no connection."""


_lock = threading.Lock()
_down_until: dict[str, float] = {}  # provider name -> time when we try it again
_used = threading.local()


@contextmanager
def cache_scope(tag: str = "", fresh: bool = False):
    """Saved answers. The same request gets the saved answer, so the AI is not called again.
    tag: the paper id. When you delete the paper, its saved answers go too.
    fresh: ask the AI again and replace the saved answer (for the button "Read again")."""
    old = getattr(_used, "scope", ("", False))
    _used.scope = (tag, fresh)
    try:
        yield
    finally:
        _used.scope = old


@contextmanager
def ai_context(feature: str, paper_id: str = ""):
    """Say which feature and which paper an AI call is for. The AI use log keeps it. paper_id can be a list of ids with commas."""
    old = getattr(_used, "ctx", ("other", ""))
    _used.ctx = (feature, paper_id)
    try:
        yield
    finally:
        _used.ctx = old


def _log_call(p: dict) -> None:
    """The AI use log. One row for each answer of a provider. A saved answer (cache hit) writes no row."""
    feature, paper_id = getattr(_used, "ctx", ("other", ""))
    try:
        db.ai_log_add(feature, paper_id, p["name"], p["model"])
    except Exception:  # the log must never stop the app
        log.exception("Could not write the AI use log")


def _cache_key(p: dict, messages: list[dict], max_tokens: int | None) -> str:
    raw = json.dumps({"p": p["name"], "m": p["model"], "msgs": messages, "mt": max_tokens or config.LLM_MAX_TOKENS}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_get(key: str):
    try:
        return db.cache_get(key)
    except Exception:  # a broken cache must never stop the app
        log.exception("Could not read a saved AI answer")
        return None


def _cache_put(key: str, tag: str, p: dict, out: dict) -> None:
    try:
        db.cache_put(key, tag, p["name"], p["model"], out)
    except Exception:
        log.exception("Could not save an AI answer")


_choice: dict | None = None  # what the student chose in Settings: {"primary": "gemini", "fallbacks": ["groq"], "models": {"gemini": "..."}}


def load_choice() -> None:
    """Read the choice of the student from the database. Call it at start-up."""
    global _choice
    try:
        data = json.loads(db.get_setting("ai_choice") or "null")
    except ValueError:
        data = None
    _choice = _clean_choice(data) if data else None


def _clean_choice(data) -> dict | None:
    """Keep only known providers and safe model names. A wrong choice never breaks the chain."""
    if not isinstance(data, dict) or data.get("primary") not in config.PROVIDERS:
        return None
    primary = data["primary"]
    fallbacks = []
    for n in data.get("fallbacks") or []:
        if n in config.PROVIDERS and n != primary and n not in fallbacks:
            fallbacks.append(n)
    models = {}
    for n, m in (data.get("models") or {}).items():
        m = str(m).strip()
        if n in config.PROVIDERS and m and len(m) <= 100 and re.fullmatch(r"[\w.:/\-]+", m):
            models[n] = m
    return {"primary": primary, "fallbacks": fallbacks[:3], "models": models}


def set_choice(data) -> dict | None:
    """Save the choice (or None = use the settings of the server). The choice works at once."""
    global _choice
    _choice = _clean_choice(data) if data else None
    db.set_setting("ai_choice", json.dumps(_choice) if _choice else "")
    with _lock:
        _down_until.clear()
    return _choice


def choice() -> dict:
    """The choice that works now, and if the student made it."""
    chain = _chain()
    return {"primary": chain[0]["name"], "fallbacks": [p["name"] for p in chain[1:]], "models": {p["name"]: p["model"] for p in chain}, "custom": _choice is not None}


def _chain() -> list[dict]:
    """The providers in order. API keys come from the server environment only."""
    if _choice:
        return config.build_chain([_choice["primary"], *_choice["fallbacks"]], _choice["models"], legacy=False)
    # no choice: the settings of the server. The first key is read live, so a changed setting works at once.
    return [({**p, "key": config.LLM_API_KEY} if i == 0 else p) for i, p in enumerate(config.LLM_CHAIN)]


def _has_key(p: dict) -> bool:
    return p["name"] == "ollama" or bool(p["key"])


def ready() -> bool:
    return any(_has_key(p) for p in _chain())


def used_model() -> str:
    """The provider and model that made the last answer in this thread. Used to label the card."""
    first = _chain()[0]
    return getattr(_used, "label", None) or f"{first['name']}:{first['model']}"


def status() -> list[dict]:
    """For the settings page: each provider, its model, and if it has a key."""
    now = time.time()
    with _lock:
        down = dict(_down_until)
    return [{"provider": p["name"], "model": p["model"], "ready": _has_key(p), "paused": down.get(p["name"], 0) > now} for p in _chain()]


def options() -> list[dict]:
    """Every provider that the student can choose, with its models and if the server has its key."""
    keys = {p["name"]: _has_key(p) for p in config.build_chain(list(config.PROVIDERS), legacy=False)}
    return [{"provider": n, "ready": keys[n], "default_model": config.build_chain([n], legacy=False)[0]["model"],
             "models": config.MODEL_SUGGESTIONS.get(n, [])} for n in config.PROVIDERS]


def parse_json(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    if a == -1 or b <= a:
        raise LLMError("The AI answer was not in the right format. Click Retry.")
    try:
        return json.loads(t[a : b + 1])
    except json.JSONDecodeError as e:
        raise LLMError("The AI answer was not in the right format. Click Retry.") from e


def _error_message(r) -> str:
    try:
        return str(r.json().get("error", {}).get("message", ""))[:300]
    except Exception:
        try:
            first = r.json()[0] if isinstance(r.json(), list) else {}  # Gemini can send a list
            return str(first.get("error", {}).get("message", ""))[:300]
        except Exception:
            return ""


def _too_large(r) -> bool:
    if r.status_code == 413:
        return True
    low = _error_message(r).lower()
    return r.status_code in (400, 429) and ("request too large" in low or "reduce your message size" in low or "context length" in low or "context_length" in low)


def _call(p: dict, messages: list[dict], max_tokens: int | None, fast: bool) -> dict:
    """One provider. fast=True means another provider can answer, so a limit or an outage does not make us wait."""
    headers = {"Content-Type": "application/json"}
    if p["key"]:
        headers["Authorization"] = "Bearer " + p["key"]
    if p["name"] == "openrouter":
        headers["X-Title"] = "Research_Pal"
    body = {"model": p["model"], "messages": messages, "temperature": 0.1,
            "max_tokens": max_tokens or config.LLM_MAX_TOKENS, "response_format": {"type": "json_object"}}
    if config.LLM_REASONING_EFFORT and "gpt-oss" in p["model"].lower():
        body["reasoning_effort"] = config.LLM_REASONING_EFFORT
    url = p["base_url"] + "/chat/completions"
    last = ""
    for attempt in range(3 if fast else 6):
        try:
            r = httpx.post(url, json=body, headers=headers, timeout=config.LLM_TIMEOUT)
        except httpx.TimeoutException:
            last = "The AI provider did not answer in time."
            if fast:
                raise LLMUnavailable(last)
            time.sleep(2 * (attempt + 1))
            continue
        except httpx.HTTPError as e:
            raise LLMUnavailable("The server cannot reach the AI provider.") from e
        if _too_large(r):
            raise LLMTooLarge("The paper text is too large for the AI provider limit.")
        if r.status_code == 400:
            # some models do not know one of these options. Remove them one by one.
            for opt in ("response_format", "reasoning_effort"):
                if opt in body:
                    body.pop(opt)
                    break
            else:
                raise LLMError(f"AI provider error 400. {_error_message(r)}".strip())
            continue
        if r.status_code in (401, 403):
            raise LLMUnavailable("The AI provider refused the API key. Check the key on the server.")
        if r.status_code in (429, 500, 502, 503, 504):
            last = "The AI provider is busy or the free limit is reached. Wait one minute, then click Retry."
            if fast:
                raise LLMUnavailable(last)  # do not wait: the next provider answers now
            try:
                wait = float(r.headers.get("retry-after", 2 ** (attempt + 1)))
            except ValueError:
                wait = 2 ** (attempt + 1)
            if attempt < 5:
                time.sleep(min(wait, 30))
            continue
        if r.status_code >= 400:
            raise LLMError(f"AI provider error {r.status_code}. {_error_message(r)}".strip())
        try:
            choice = r.json()["choices"][0]
            content = choice["message"].get("content") or ""
        except Exception as e:
            raise LLMError("The AI provider sent an unexpected answer.") from e
        if choice.get("finish_reason") == "length":
            # the AI used all output tokens (thinking + answer). The JSON is cut. Give more room.
            last = "The AI answer was cut. Click Retry."
            body["max_tokens"] = min(int(body["max_tokens"] * 1.5), 32000)
            continue
        try:
            return parse_json(content)
        except LLMError as e:
            last = str(e)  # bad JSON: ask again, the answer can differ
            continue
    raise LLMError(last or "The AI provider did not answer.")


def chat_json(messages: list[dict], max_tokens: int | None = None) -> dict:
    ready_chain = [p for p in _chain() if _has_key(p)]
    if not ready_chain:
        keys = " or ".join(p["key_env"] for p in (config.PROVIDERS[c["name"]] for c in config.LLM_CHAIN) if p["key_env"]) or "LLM_API_KEY"
        raise LLMError(f"The AI key is missing. Set {keys} on the server.")

    # A provider that failed a short time ago waits. If all wait, we try them all again.
    now = time.time()
    with _lock:
        active = [p for p in ready_chain if _down_until.get(p["name"], 0) <= now] or ready_chain

    tag, fresh = getattr(_used, "scope", ("", False))
    failures = []
    for i, p in enumerate(active):
        key = _cache_key(p, messages, max_tokens)
        if not fresh:
            saved = _cache_get(key)
            if saved is not None:
                _used.label = f"{p['name']}:{p['model']}"
                return saved
        try:
            out = _call(p, messages, max_tokens, fast=i < len(active) - 1)
        except LLMTooLarge:
            raise  # the caller sends less text. A second provider does not help.
        except LLMError as e:
            failures.append((p, e))
            if isinstance(e, LLMUnavailable) and config.LLM_COOLDOWN > 0:
                with _lock:
                    _down_until[p["name"]] = time.time() + config.LLM_COOLDOWN
            continue
        with _lock:
            _down_until.pop(p["name"], None)  # it works again
        _used.label = f"{p['name']}:{p['model']}"
        _cache_put(key, tag, p, out)
        _log_call(p)
        return out

    if len(failures) == 1:
        raise failures[0][1]
    raise LLMError(" ".join(f"{p['name'].capitalize()}: {e}" for p, e in failures))
