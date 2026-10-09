"""Login. One-user mode: the password gives a signed token with an expiry date.
Multi-user mode (SUPABASE_URL is set): Supabase gives the token. The server asks Supabase who the user is."""
import base64, contextvars, hashlib, hmac, json, secrets, time
from collections import defaultdict, deque

import httpx
from fastapi import Header, HTTPException, Request

from . import config

_attempts: dict[str, deque] = defaultdict(deque)


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token() -> str:
    payload = _b64(json.dumps({"exp": int(time.time()) + config.TOKEN_TTL_SECONDS}).encode())
    sig = _b64(hmac.new(config.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).digest())
    return payload + "." + sig


def verify_token(token: str) -> bool:
    try:
        payload, sig = token.split(".", 1)
        good = _b64(hmac.new(config.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return False
        return json.loads(_unb64(payload))["exp"] > time.time()
    except Exception:
        return False


def check_password(request: Request, password: str) -> bool:
    """Limit wrong attempts: 8 per minute for each IP address."""
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    q = _attempts[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= 8:
        raise HTTPException(429, "Too many attempts. Wait one minute.")
    ok = secrets.compare_digest(password.encode(), config.APP_PASSWORD.encode())
    if not ok:
        q.append(now)
        time.sleep(0.8)
    return ok


LOCAL_USER = "local"  # the user id in one-user mode
_user: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default=LOCAL_USER)
_seen: dict[str, tuple[float, str]] = {}  # token -> (time, user id). Saves one call to Supabase for each request.
_SEEN_SECONDS = 60


def current_user() -> str:
    """The id of the user who makes this request. Background jobs get the same value (see run_as)."""
    return _user.get()


def set_user(uid: str) -> None:
    _user.set(uid)


def run_as(uid: str, fn, *args, **kwargs):
    """Run fn with a given user. Use it in threads: a new thread does not get the user by itself."""
    _user.set(uid)
    return fn(*args, **kwargs)


async def _supabase_user(token: str) -> str:
    hit = _seen.get(token)
    if hit and time.time() - hit[0] < _SEEN_SECONDS:
        return hit[1]
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{config.SUPABASE_URL}/auth/v1/user", headers={"Authorization": f"Bearer {token}", "apikey": config.SUPABASE_SERVICE_KEY})
    except httpx.HTTPError:
        raise HTTPException(503, "Cannot reach the login service. Try again.")
    if r.status_code != 200:
        raise HTTPException(401, "Not signed in.")
    u = r.json()
    email = (u.get("email") or "").lower()
    if config.ALLOWED_EMAILS and email not in config.ALLOWED_EMAILS:
        raise HTTPException(403, "This email is not allowed to use the app.")
    if len(_seen) > 500:
        _seen.clear()
    _seen[token] = (time.time(), u["id"])
    return u["id"]


async def require_auth(authorization: str = Header(default="")) -> str:
    """Async on purpose: the user id is set in the context of the request, so the route (in a thread) sees it."""
    token = authorization[7:] if authorization.lower().startswith("bearer ") else ""
    if config.MULTI_USER:
        if not token:
            raise HTTPException(401, "Not signed in.")
        uid = await _supabase_user(token)
    else:
        if not token or not verify_token(token):
            raise HTTPException(401, "Not signed in.")
        uid = LOCAL_USER
    _user.set(uid)
    return uid
