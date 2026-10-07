"""One-user login. The password gives a signed token with an expiry date."""
import base64, hashlib, hmac, json, secrets, time
from collections import defaultdict, deque

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


def require_auth(authorization: str = Header(default="")) -> None:
    token = authorization[7:] if authorization.lower().startswith("bearer ") else ""
    if not token or not verify_token(token):
        raise HTTPException(401, "Not signed in.")
