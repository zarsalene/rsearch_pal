# Testing Research_Pal

You can run all tests in 10 minutes. No test calls a real AI. No test needs an API key.

## What you need

- Python 3.11 or newer
- Node.js 20 or newer

## Run the tests

### 1. Backend (pytest)

```bash
cd research-pal/backend
python -m venv ../.venv
../.venv/Scripts/activate          # Windows. On Mac or Linux: source ../.venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Expected: all tests pass in about 15 seconds.

### 2. Frontend (Vitest and Playwright)

```bash
cd research-pal/frontend
npm install
npx playwright install chromium    # one time, about 120 MB
npm test                           # unit tests
npm run build                      # the build must work
npm run e2e                        # tests in a real browser
```

`npm run e2e` starts two servers for you: the backend with a fake AI (port 8001) and the frontend (port 5174).
The backend needs the Python that has the packages of the backend. Tell Playwright where it is:

```bash
# Mac or Linux
PYTHON=../.venv/bin/python npm run e2e
# Windows (PowerShell)
$env:PYTHON = "..\.venv\Scripts\python.exe"; npm run e2e
```

In CI, `python` is the right one, so you need no setting.

## What each test level checks

| Level | Where | What it checks |
|-------|-------|----------------|
| Unit and API | `backend/tests/` | One function, or one endpoint with the real app and a fake AI. |
| Truth | `backend/tests/test_truth.py` | The rule "no wrong data". The fake AI gives a false quote or a false number. The server must hide it or label it. |
| Frontend unit | `frontend/src/*.test.jsx` | One component. |
| End to end | `frontend/e2e/` | A full user path in a real browser. |
| Real AI smoke test | `backend/scripts/smoke_real_ai.py` | Real papers with the real AI. You run it by hand and read the result. |

## The test tools

All tools are in `backend/tests/`. `conftest.py` makes them available to each test.

| Tool | What it does |
|------|--------------|
| `client` | A test client for the real app. Each test has its own empty data folder. |
| `auth_headers` | The headers of a signed-in user. Pass `headers=auth_headers` to each call. |
| `fake_ai` | Replaces the AI. Without a rule, it gives the scripted answers for the test PDFs. |
| `sample_pdfs` | Two test PDFs, made with `reportlab`. `sample_pdfs["a.pdf"].path` is the file. |
| `assert_no_false_quote(response, pages, invented)` | The truth check. Use it in each test of an AI feature. |

### Give the fake AI an answer

```python
def test_my_feature(client, auth_headers, fake_ai):
    # A call whose text contains "You explain how" gets this answer.
    fake_ai.when("You explain how", {"summary": "...", "evidence": [{"paper": 1, "quote": "A quote that is not in the PDF.", "page": 1}]})
    # An exception is raised in the call:
    fake_ai.when("You explain how", llm.LLMError("The AI is down."))
    # fake_ai.calls lists each call. Use it to check that the AI was not called.
```

The last rule that matches wins. A function also works as an answer: `fake_ai.when("text", lambda messages: {...})`.

### Write a truth test

Each AI feature needs one. Use this form:

1. Make the fake AI return a quote that is not in the PDF, or a number that the PDF does not have.
2. Call the endpoint.
3. Check that the server hides the claim, drops it, or labels it.
4. Call `assert_no_false_quote(response, pages=..., invented=[the false quote])`.

See `backend/tests/test_truth.py` for examples.

### The search index in tests

The tests use a small fake of the ChromaDB collection (`tests/fake_vectors.py`).
Reason: ChromaDB breaks by chance when one process makes many collections. The app makes two collections one time, so it is safe. A test run is not.
The code of `vectors.py` still runs. `tests/test_vectors_real.py` checks the real ChromaDB.

## The real AI smoke test

Run it by hand, before you finish a sprint. It sends the text of the PDFs to your AI provider. Use papers that you can share.

```bash
cd research-pal/backend
python scripts/smoke_real_ai.py paper1.pdf paper2.pdf paper3.pdf
```

The script reads the keys from `backend/.env`. It prints each card and checks that no quote shown as verified is missing from the PDF.
Exit code 0 means OK. Exit code 1 means a wrong quote or a failed paper. Exit code 2 means the test did not run (no key).
Add `--fast-embeddings` to skip the 80 MB download of the search model.

## Continuous integration (CI)

`.github/workflows/ci.yml` runs on each push: the backend tests, the frontend tests, the build and the end-to-end tests.
If one test fails, the push shows a red mark on GitHub.

## Fix a failing test

- A truth test fails: a false quote or a false number can reach the student. Fix the code. Never change the test.
- An old test fails after your change: fix your code. Change the old test only when your sprint changes that behavior on purpose. Write the reason in the sprint report.
- An end-to-end test fails in CI: download the `playwright-results` file in the run. It has a screenshot and a trace.
