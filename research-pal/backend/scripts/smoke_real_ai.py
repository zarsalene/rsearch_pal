"""Real AI smoke test. Read the result with your own eyes. It is not part of CI.
It reads some real PDFs with the real AI (the keys of backend/.env), prints each card, and checks the rule "no wrong data":
no quote that the server shows as verified may be missing from the PDF.
Usage:   python scripts/smoke_real_ai.py paper1.pdf paper2.pdf paper3.pdf [--fast-embeddings]
Result:  exit code 0 = the check passed. 1 = a wrong quote shows as verified, or a paper failed. 2 = not run (no key, or no PDF).
The data goes to a temporary folder. Your own library is not touched. The text of the PDFs goes to your AI provider."""
import argparse, os, re, sys, tempfile, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # a Windows console cannot print every character of a paper
BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND), str(BACKEND / "tests")]

ap = argparse.ArgumentParser()
ap.add_argument("pdfs", nargs="*", help="the PDF files to read (3 are best)")
ap.add_argument("--fast-embeddings", action="store_true", help="use the test embeddings (no 80 MB download). The search is worse; the quote check is the same.")
ap.add_argument("--timeout", type=int, default=300, help="seconds to wait for each paper")
args = ap.parse_args()

# Settings that are not secret. The API keys come from backend/.env. These values win over .env.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="research-pal-smoke-")
os.environ.setdefault("APP_PASSWORD", "smoke-password-123")
os.environ.setdefault("SECRET_KEY", "s" * 40)
if args.fast_embeddings:
    os.environ["EMBEDDING_BACKEND"] = "hash"

from fastapi.testclient import TestClient

from app import db, llm, main
from helpers import assert_no_false_quote

FIELDS = ("problem", "method", "result", "limitation")


def show(card: dict) -> int:
    """Print a card. Return the number of claims that the server shows as verified."""
    print(f"  title:   {card['title']}\n  verdict: {card['verdict']}  (model: {card['model']})")
    shown = 0
    for name in FIELDS:
        f = card["fields"][name]
        shown += f["status"] in ("verified", "check")
        print(f"  {name:<10} [{f['status']}] {(f['answer'] or '(hidden) ' + f['draft'])[:150]}")
        for e in f["evidence"]:
            print(f"      p.{e['page']:<3} {'verified ' if e['verified'] else 'NOT FOUND'} {e['quote'][:100]}")
        if f["unverified_numbers"]:
            print(f"      numbers that the PDF does not have: {', '.join(f['unverified_numbers'])}")
    return shown


def numbers(text: str) -> list[str]:
    return sorted(re.findall(r"\d+(?:[.,]\d+)?", text or ""))


def check_simple_and_words(client, h, pid, card, name) -> list[str]:
    """Simple mode and the word helper on a real paper. Print the texts. Return the problems."""
    problems = []
    for field in ("method", "result"):
        f = card["fields"].get(field) or {}
        if f.get("status") not in ("verified", "check"):
            continue
        r = client.post(f"/api/papers/{pid}/simplify", headers=h, json={"field": field})
        if r.status_code != 200:
            print(f"  simple {field}: error {r.status_code} {r.text[:120]}")
            continue
        s = r.json()
        print(f"  simple {field}: {'OK' if s['ok'] else 'kept the original (' + s['reason'] + ')'}\n      before: {f['answer'][:160]}\n      after:  {s['text'][:240]}")
        if numbers(s["text"]) != numbers(f["answer"]):  # the server must never allow this
            problems.append(f"{name}: THE SIMPLE TEXT OF {field} CHANGED A NUMBER")
    for term in (card.get("keywords") or [])[:2]:
        r = client.post(f"/api/papers/{pid}/define", headers=h, json={"term": term})
        if r.status_code == 200:
            d = r.json()
            print(f"  word '{term}': [{d['label']}{' p.' + str(d['page']) if d['page'] else ''}] {d['explanation'][:200]}")
        else:
            print(f"  word '{term}': error {r.status_code} {r.text[:120]}")
    return problems


def main_run() -> int:
    pdfs = [Path(p) for p in args.pdfs]
    if not pdfs or not all(p.is_file() for p in pdfs):
        print("Give the path of at least one PDF file. Example: python scripts/smoke_real_ai.py a.pdf b.pdf c.pdf")
        return 2
    with TestClient(main.app) as client:
        if not llm.ready():
            print("smoke test not run: no keys. Set GEMINI_API_KEY or GROQ_API_KEY in backend/.env.")
            return 2
        print("AI chain:", ", ".join(f"{p['provider']}:{p['model']}" for p in llm.status()), f"| embeddings: {os.environ.get('EMBEDDING_BACKEND', 'default')}")
        token = client.post("/api/login", json={"password": os.environ["APP_PASSWORD"]}).json()["token"]
        h = {"Authorization": "Bearer " + token}
        problems, total_shown = [], 0
        for path in pdfs:
            print(f"\n== {path.name}")
            t0 = time.time()
            r = client.post("/api/papers", headers=h, files={"file": (path.name, path.read_bytes(), "application/pdf")}, data={"purpose": "What does this paper show?"})
            if r.status_code != 200:
                problems.append(f"{path.name}: upload refused: {r.text[:150]}")
                print("  ", problems[-1])
                continue
            pid = r.json()["id"]
            while time.time() - t0 < args.timeout:
                got = client.get(f"/api/papers/{pid}", headers=h).json()
                if got["paper"]["status"] in ("ready", "error"):
                    break
                time.sleep(2)
            if got["paper"]["status"] != "ready":
                problems.append(f"{path.name}: {got['paper']['status']} {got['paper'].get('error', '')}")
                print("  ", problems[-1])
                continue
            total_shown += show(got["card"])
            try:  # the truth rule: a quote that shows as verified must be in the text of the PDF
                assert_no_false_quote(got["card"], pages=db.get_pages(pid))
                print(f"  truth check: OK ({time.time() - t0:.0f} s)")
            except AssertionError as e:
                problems.append(f"{path.name}: WRONG QUOTE SHOWN AS VERIFIED. {str(e)[:200]}")
                print("  ", problems[-1])
            problems += check_simple_and_words(client, h, pid, got["card"], path.name)
    print("\n" + "=" * 60)
    if problems:
        print("RESULT: FAILED")
        for p in problems:
            print(" -", p)
        return 1
    print(f"RESULT: OK. {len(pdfs)} papers read. {total_shown} claims shown with a verified quote. No wrong quote shown as verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main_run())
