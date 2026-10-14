"""Build the UI for the desktop app into desktop/ui.

It uses the same code as the web app (the web/ folder), with other build settings:
- the API address is relative (the desktop server gives the page and the API from one address),
- Supabase is off (no email login),
- the PWA service worker is removed (the page needs a fresh login token at each start).
web/dist (web and phone) is not touched.
"""
import os, re, shutil, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEB = HERE.parent / "web"
OUT = HERE / "ui"


def main() -> None:
    # An empty value is set on purpose: web/.env cannot replace a variable that exists.
    env = {**os.environ, "VITE_API_URL": "/", "VITE_SUPABASE_URL": "", "VITE_SUPABASE_ANON_KEY": ""}
    subprocess.run([shutil.which("npx") or "npx.cmd", "vite", "build", "--outDir", str(OUT), "--emptyOutDir"], cwd=WEB, env=env, check=True)

    for f in [*OUT.glob("sw.js*"), *OUT.glob("workbox-*.js*"), OUT / "registerSW.js", OUT / "manifest.webmanifest"]:
        f.unlink(missing_ok=True)
    page = OUT / "index.html"
    html = page.read_text(encoding="utf-8")
    html = re.sub(r'<link rel="manifest"[^>]*>', "", html)
    html = re.sub(r'<script id="vite-plugin-pwa:register-sw"[^>]*></script>', "", html)
    page.write_text(html, encoding="utf-8")

    # Check: no Supabase address in the build, and the API address is relative.
    js = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in (OUT / "assets").glob("*.js"))
    if "supabase.co" in js:
        raise SystemExit("The build still has a Supabase address. The desktop UI must not use Supabase.")
    if "localhost:8000" in js:
        raise SystemExit("The build still has the address localhost:8000. The API address must be relative.")
    print(f"Desktop UI is ready in {OUT}")


if __name__ == "__main__":
    main()
