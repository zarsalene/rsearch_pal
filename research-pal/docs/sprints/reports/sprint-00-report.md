# Sprint 00 report: Test foundation

| | |
|---|---|
| **Branch** | `sprint-00-test-foundation` (pushed to `origin`, not merged, not tagged) |
| **Date** | 9 October 2026 |
| **Status** | Ready for the gate. The owner must run the demo and the "Owner" items. |

## 1. What I built

This sprint has no report idea. It is the test base for all next sprints. It has no new user feature, except the feature switches.

| Part | What it does | Files |
|------|--------------|-------|
| Test fixtures | `client`, `auth_headers`, `fake_ai`, `sample_pdfs`. Each test has its own empty data folder. A test can never call a real AI or the network. | `backend/tests/conftest.py`, `fake_ai.py`, `pdfs.py`, `helpers.py` |
| Fake AI | `fake_ai.when("text", answer)` gives the test control of the answer. Without a rule, it gives the scripted answers for the test PDFs. | `backend/tests/fake_ai.py` |
| Truth helper | `assert_no_false_quote(response, pages, invented)` | `backend/tests/helpers.py` |
| Test files | The old `test_pipeline.py` is split into 8 files. 28 tests. | `backend/tests/test_*.py` |
| Truth tests | Card (invented quote, false number), chat (invented quote, false number), link (invented quotes), notes (the client says "verified"). | `backend/tests/test_truth.py` |
| Feature switches | Table `features`, `GET/PUT /api/features`, `features.require("name")` for an endpoint, "Features" section in Settings. | `backend/app/features.py`, `db.py`, `main.py`, `frontend/src/Settings.jsx`, `App.jsx`, `api.js` |
| Frontend tests | Vitest and Testing Library: ThemeToggle (2 tests), Settings switches (4 tests). | `frontend/src/*.test.jsx`, `src/test/setup.js`, `vite.config.js` |
| End-to-end tests | Playwright: wrong password, login + upload + card (with a truth check in the browser), feature switch. | `frontend/e2e/app.spec.js`, `playwright.config.js` |
| Fake server | Starts the backend with the fake AI for Playwright. It also writes the test PDFs. | `backend/scripts/fake_server.py` |
| Smoke test | Reads real PDFs with the real AI and checks that no wrong quote shows as verified. | `backend/scripts/smoke_real_ai.py` |
| CI | Backend tests, frontend tests, build, end-to-end tests. | `.github/workflows/ci.yml` |
| Docs | How to run all tests. | `docs/TESTING.md`, `README.md` (Tests and Feature switches) |
| Dev packages | `pytest`, `reportlab` | `backend/requirements-dev.txt` |

The first commit also adds `IMPROVEMENT_REPORT.md` and `docs/sprints/` to git. They were not in git before.

## 2. Test results

I ran all commands on my computer (Windows 11, Python 3.14, Node 24). These are the real output lines.

```
pytest -q                 28 passed, 1 warning in 10.93s
npm test                  Test Files  2 passed (2) / Tests  6 passed (6)
npm run build             ✓ built in 8.40s
npm run e2e               3 passed (17.6s)
```

- **Stability:** I ran `pytest` 25 times in a row. All 25 runs passed.
- **Old tests:** all old checks of `test_pipeline.py` still pass. I did not change any check. I moved them into the new files.
- **Truth test works:** I broke the quote check on purpose (in `cards.py`, `verify_field`). Then 3 tests failed: `test_all` and 2 tests of `test_truth.py`. I restored the file. All tests passed again.
- **CI:** see section 8.

## 3. Smoke test (real AI)

I used 3 public papers from arXiv: "Attention Is All You Need", ResNet (1512.03385) and BERT. I did not use your own PDFs.

| Paper | Result |
|-------|--------|
| Attention Is All You Need | Read. Truth check OK. 3 claims shown with verified quotes. The server marked one quote of Result and the Limitation quote "NOT FOUND", so it hid the Limitation. |
| BERT | Read. Truth check OK. 2 claims shown. The server hid Method and Limitation. Their quotes contain non-breaking hyphens, so I think this is why they did not match. |
| ResNet | **Not read.** Both AI providers refused (see section 7). I tried 3 times. |

**Result:** no wrong quote showed as verified in the 2 papers that were read. The third paper is not tested. The Definition of Done asks for 3 papers. See the Owner item in section 5.

## 4. Differences from the sprint file

| Sprint file | What I did | Why |
|-------------|-----------|-----|
| "Keep `test_pipeline.py` working" | It works with pytest. `python tests/test_pipeline.py` does not work any more. | The tests need fixtures. I updated the README. |
| Split into fixtures and test files | Eight test files. The check of the AI choice moved to `test_settings.py`. | Small files are easier to read. |
| Fixture `client` with a temporary `DATA_DIR` | `client` plus an automatic fixture `isolated`. It also gives each test a fake search index. | ChromaDB failed by chance when the tests made many collections (2 failures in 6 runs, then also in memory). A small fake collection (`fake_vectors.py`) fixed it. `vectors.py` still runs. `test_vectors_real.py` checks the real ChromaDB. |
| "A switch for each feature" | A list `REGISTRY` in `features.py`. It has one entry: **Chat**. | No feature switch existed. The owner must see one work. Chat is small and safe. It is on by default. |
| `features(name, enabled)` table, `GET/PUT /api/features` | Same. `GET` gives a list. `PUT` takes `{"features": {"chat": false}}`. An unknown name gives error 400 and saves nothing. | I made the format clear. |
| Chat switch | When off: no Chat tab, and `POST /api/chat` gives error 403. | The server must refuse, not only the page. |
| Smoke script "uploads 3 real PDFs" | You give the PDF paths. The script runs the app inside one process, with a temporary data folder. | Your own library is not touched. |
| Test with `reportlab` PDFs | The e2e test uses the PDFs of `fake_server.py`. They are in `frontend/e2e/.generated/` (not in git). | No binary file in git. |

## 5. Manual checklist

- [x] `pytest` runs in less than 60 seconds. (Agent: 10.93 s.) **Owner:** run it on your computer.
- [x] `npm test` and `npm run e2e` run. (Agent: yes, on this computer.) **Owner:** run both on your computer. You need `npx playwright install chromium` one time, and the `PYTHON` setting. See `docs/TESTING.md`.
- [ ] **Owner:** run the smoke script with your real API key on 3 papers. The agent did 2 of 3. Command: `python scripts/smoke_real_ai.py a.pdf b.pdf c.pdf`.
- [x] A feature switch in Settings works. (Agent: the e2e test switches Chat off and on.) **Owner:** look at it. Open Settings, then Features. Switch Chat off. The Chat tab goes away. Switch it on.
- [ ] **Owner:** read `docs/TESTING.md`. Can you run all tests in 10 minutes?
- [ ] **Owner:** the Settings page looks right in light and dark mode. The Features section is easy to read.
- [ ] **Owner:** decide about the Gemini model (section 7).

## 6. Demo steps

1. Open the page **Actions** of the GitHub repository. Open the run of the branch `sprint-00-test-foundation`. Show that all jobs are green.
2. Break the quote check on purpose. In `backend/app/cards.py`, function `verify_field`, change the line `n_ok += ok` to `n_ok += 1; ok = True`.
3. Run `pytest` in `backend/`. Three tests fail: `test_all` and two tests of `test_truth.py`.
4. Commit and push. The CI run turns red.
5. Restore the line. Push again. The CI run turns green.
6. Show the Settings page: switch Chat off, then on.

## 7. Known problems and risks

1. **The Gemini default model is retired for your key.** `gemini-2.5-flash` gives error 404 ("no longer available to new users"). Every request goes to Groq. Groq's free plan limits a request to 8000 tokens. A long paper (ResNet) fails with "The AI provider refuses even a small part of the paper." `gemini-3.8-flash` answered a small test request. **Action for the owner:** choose a new Gemini model in Settings → AI models, or tell me to change the default in `config.py`. I did not change it. It is outside this sprint.
2. **Gemini free limit.** At the time of the smoke test, Gemini 3.8 answered "busy or free limit reached" for the long paper. This can be a short wait or a daily limit.
3. **Quotes with special hyphens.** In the smoke test, the AI wrote `‑` (non-breaking hyphen) in some quotes. I think the PDF has `-`, but I did not check this. The server then marks a good quote "not found" and hides a good claim. This is safe (no wrong data) but it hides true claims. The check in `cards.norm` could treat these characters as equal. This is a possible improvement for a later sprint. I did not change it.
4. **ChromaDB.** It breaks by chance when a process makes and deletes many collections. The app makes 2 collections one time, so I think it is safe. I did not see a failure in the app. Only the tests had it.
5. **CI is new.** It passed one time. I cannot run GitHub Actions on my computer, so I did not test its failure path.
6. **`npm install` printed an audit notice** for the dev packages. I did not review it.
7. **Your working copy has changes that I did not make.** The deleted files `graphify-out/*` (staged), and the changes in `research-pal/.gitignore` and the root `.gitignore`. I did not commit them.
8. **Line endings.** Git warns that LF changes to CRLF on Windows. This is not a problem for the tests.

## 8. CI result

The first CI run of the branch passed (commit `d9dde99`, Ubuntu, Python 3.11, Node 20):

- Backend tests (pytest): success, 41 seconds.
- Frontend tests, build and end-to-end tests: success, 90 seconds.
- Run: https://github.com/zarsalene/rsearch_pal/actions/runs/37929516391

I did not test the "red" case in CI. I tested it on my computer (section 2). The demo shows it in CI.
