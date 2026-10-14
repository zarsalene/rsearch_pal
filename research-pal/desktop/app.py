"""Research Pal for the desktop.

This is a separate launcher. It does not change the web app or the phone app.
It runs the same backend on this computer and shows the same UI in an app window.

- Papers, cards and the search index stay on this computer (SQLite and ChromaDB on disk).
- There is no Supabase and no login page. The server listens on 127.0.0.1 only.
- Only the AI calls go out: Gemini first. If Gemini fails, OpenRouter answers.

Start it:  python desktop/app.py        (use --no-window to run the server only)
"""
import argparse, json, os, secrets, shutil, subprocess, sys, threading, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent / "backend"
UI = HERE / "ui"
HOST = "127.0.0.1"
PORT = int(os.environ.get("RESEARCH_PAL_PORT", "8765"))  # the port stays the same, so the browser keeps your small settings (theme, simple mode)
HOME = Path(os.environ.get("RESEARCH_PAL_HOME") or Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "ResearchPal")
SETTINGS = HOME / "settings.env"
URL = f"http://{HOST}:{PORT}"

TEMPLATE = """# Research Pal desktop settings. Save this file, then start the app again.
# Free Gemini key: https://aistudio.google.com/apikey
GEMINI_API_KEY=
# OpenRouter key: https://openrouter.ai/keys
OPENROUTER_API_KEY=

# Optional
# GEMINI_MODEL=gemini-3.1-flash-lite
# OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct
# LLM_PROVIDER=gemini
# LLM_FALLBACK=openrouter
"""


def _local_secrets() -> dict:
    """A password and a secret for this computer. The page never asks for them: the launcher gives the page a token."""
    f = HOME / "local.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    if len(d.get("secret_key", "")) < 24 or len(d.get("password", "")) < 8:
        d = {"secret_key": secrets.token_urlsafe(48), "password": secrets.token_urlsafe(24)}
        f.write_text(json.dumps(d), encoding="utf-8")
    return d


def prepare_env() -> bool:
    """Set the environment before the backend is imported. Returns True if settings.env is new.
    Order of priority: real environment variables, then settings.env, then the desktop defaults, then backend/.env (a developer copy)."""
    HOME.mkdir(parents=True, exist_ok=True)
    first_run = not SETTINGS.exists()
    if first_run:
        SETTINGS.write_text(TEMPLATE, encoding="utf-8")
    from dotenv import dotenv_values

    for k, v in dotenv_values(SETTINGS, encoding="utf-8-sig").items():  # utf-8-sig: Notepad can add a BOM
        if v:
            os.environ.setdefault(k, v)
    os.environ.setdefault("GEMINI_MODEL", "gemini-3.1-flash-lite")  # the backend default (gemini-2.5-flash) is closed to new keys
    os.environ.setdefault("LLM_PROVIDER", "gemini")
    os.environ.setdefault("LLM_FALLBACK", "openrouter")
    os.environ.setdefault("EMBEDDING_BACKEND", "default")  # the search model runs on this computer
    os.environ.setdefault("DATA_DIR", str(HOME / "data"))
    # One-user local mode. An empty value is set on purpose: backend/.env cannot replace a variable that exists.
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "DATABASE_URL", "ALLOWED_EMAILS"):
        os.environ[k] = ""
    s = _local_secrets()
    os.environ["APP_PASSWORD"], os.environ["SECRET_KEY"] = s["password"], s["secret_key"]
    os.environ["FRONTEND_ORIGIN"] = URL
    return first_run


def build_app():
    """The backend app, plus the UI files. The UI page gets a login token, so there is no login page."""
    if not (UI / "index.html").exists():
        raise SystemExit("The desktop UI is not built. Run:  python desktop/build_ui.py")
    sys.path.insert(0, str(BACKEND))
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles

    from app import auth, config
    from app.main import app

    if not any(p["key"] for p in config.LLM_CHAIN):
        print(f"No AI key found. Add GEMINI_API_KEY and OPENROUTER_API_KEY in:\n  {SETTINGS}")
        subprocess.Popen(["notepad", str(SETTINGS)])

    index = (UI / "index.html").read_text(encoding="utf-8")

    @app.get("/", include_in_schema=False)
    def home():
        boot = f'<script>try{{localStorage.setItem("research-pal-token",{json.dumps(auth.make_token())})}}catch(e){{}}</script>'
        return HTMLResponse(index.replace("<head>", "<head>" + boot, 1), headers={"Cache-Control": "no-store"})

    app.mount("/", StaticFiles(directory=UI), name="ui")  # after all the /api routes, so it never hides one
    return app


def already_running() -> bool:
    try:
        with urllib.request.urlopen(URL + "/api/health", timeout=1.5) as r:
            return r.status == 200
    except OSError:
        return False


def start_server(app):
    import uvicorn

    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=PORT, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(300):  # up to 30 seconds
        if server.started:
            return server, thread
        if not thread.is_alive():
            raise SystemExit(f"The server did not start. Is port {PORT} in use? Set RESEARCH_PAL_PORT to another number.")
        time.sleep(0.1)
    raise SystemExit("The server did not start in 30 seconds.")


def find_browser() -> Path | None:
    """Edge comes with Windows 11. Chrome works the same way."""
    for p in (r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe", r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
              r"%ProgramFiles%\Google\Chrome\Application\chrome.exe", r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
              r"%LocalAppData%\Google\Chrome\Application\chrome.exe"):
        exe = Path(os.path.expandvars(p))
        if exe.exists():
            return exe
    return None


def open_window() -> subprocess.Popen | None:
    """An app window (no tabs, no address bar) with its own profile, so it does not touch your normal browser."""
    exe = find_browser()
    if not exe:
        return None
    return subprocess.Popen([str(exe), f"--app={URL}", f"--user-data-dir={HOME / 'window'}", "--no-first-run", "--no-default-browser-check",
                             "--disable-background-mode", "--window-size=1320,880"])


def main() -> None:
    ap = argparse.ArgumentParser(description="Research Pal for the desktop")
    ap.add_argument("--no-window", action="store_true", help="run the server only")
    args = ap.parse_args()

    if already_running():  # a second start only opens a second window
        print("Research Pal is already running.")
        if not args.no_window:
            open_window()
        return

    prepare_env()
    server, thread = start_server(build_app())
    print(f"Research Pal runs at {URL}  (data: {os.environ['DATA_DIR']})")
    try:
        win = None if args.no_window else open_window()
        if win:
            win.wait()  # the server stops when you close the window
        else:
            if not args.no_window:
                print("No Edge or Chrome found. Open the address above in a browser.")
            print("Press Ctrl+C to stop.")
            while thread.is_alive():
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.should_exit = True
        thread.join(10)


if __name__ == "__main__":
    main()
