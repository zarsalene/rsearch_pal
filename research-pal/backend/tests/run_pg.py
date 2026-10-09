"""Run the whole backend test suite on Postgres (your Supabase project). Each test is a new user with a new schema, dropped at the end.
Usage:  python tests/run_pg.py [pytest arguments]
It reads SUPABASE_URL, SUPABASE_SERVICE_KEY and DATABASE_URL from backend/.env. It needs network access."""
import os, subprocess, sys
from pathlib import Path

backend = Path(__file__).resolve().parent.parent
env = dict(os.environ)
for line in (backend / ".env").read_text(encoding="utf-8-sig").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env.setdefault(k, v)
if not env.get("DATABASE_URL") or not env.get("SUPABASE_SERVICE_KEY"):
    sys.exit("Set DATABASE_URL and SUPABASE_SERVICE_KEY in backend/.env")
env.update(RP_TEST_PG="1", RP_PG_URL=env.get("SUPABASE_URL") or "https://example.supabase.co",
           RP_PG_SERVICE_KEY=env["SUPABASE_SERVICE_KEY"], RP_PG_DATABASE_URL=env["DATABASE_URL"])
sys.exit(subprocess.call([sys.executable, "-m", "pytest", "-q", *sys.argv[1:]], cwd=backend, env=env))
