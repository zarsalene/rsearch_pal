# Sprint 00 — Test foundation

| | |
|---|---|
| **Length** | 1 week |
| **Branch** | `sprint-00-test-foundation` |
| **Depends on** | Nothing |
| **Report ideas** | None (base for all sprints) |

## 1. Goal

Make a test base that all next sprints use. Today there is one end-to-end backend test (`backend/tests/test_pipeline.py`) and no frontend test. After this sprint, each new feature can be tested fast and in the same way.

## 2. Scope

**In:**
- Split the backend test into shared fixtures and test files.
- A fake AI that each test can control.
- Frontend unit tests (Vitest).
- End-to-end tests (Playwright).
- CI that runs all tests on each push.
- A real AI smoke test script.
- Feature switches in Settings.

**Out:** No new user feature.

## 3. Development

### Backend
1. Make `backend/tests/conftest.py`:
   - A fixture `client`: a `TestClient` with a temporary `DATA_DIR`.
   - A fixture `fake_ai`: replaces the call in `llm.py`. The test gives the answer that the fake AI returns.
   - A fixture `sample_pdfs`: makes the test PDFs with `reportlab` (move the code from `test_pipeline.py`).
2. Keep `test_pipeline.py` working with the new fixtures.
3. Add `pytest` and `reportlab` to a new file `backend/requirements-dev.txt`.
4. Add a helper `assert_no_false_quote(response)` for the truth tests.
5. Add a table `features(name, enabled)` and endpoint `GET/PUT /api/features`.

### Frontend
1. Add `vitest`, `@testing-library/react`, `jsdom`. Add script `"test": "vitest run"`.
2. Add one first test: `ThemeToggle` changes the theme.
3. Add `@playwright/test`. Add script `"e2e": "playwright test"`.
4. First e2e test: log in → upload a PDF → see the card (backend runs with the fake AI, see below).
5. Add a "Features" section in `Settings.jsx` with a switch for each feature.

### Tools
1. `backend/scripts/fake_server.py`: starts the backend with the fake AI, for Playwright.
2. `backend/scripts/smoke_real_ai.py`: uploads 3 real PDFs with the real AI and prints each card with the quote check result.
3. `.github/workflows/ci.yml`: backend tests, frontend tests, build, e2e.

## 4. Tests

| Type | Test |
|------|------|
| API | Old pipeline test still passes. |
| API | `/api/features` reads and writes a switch. |
| Truth | Fake AI gives a quote that is not in the PDF → the claim is hidden. (This test exists; move it to the new form.) |
| Frontend unit | ThemeToggle test passes. |
| E2E | Login → upload → card visible. |
| CI | A push to the branch runs all tests and shows green. |

## 5. Manual checklist

- [ ] `pytest` runs in less than 60 seconds.
- [ ] `npm test` and `npm run e2e` run on the computer of the developer.
- [ ] The smoke test script runs with a real API key and prints a clear result.
- [ ] A feature switch in Settings works.

## 6. Done gate

- All items of the Definition of Done in the [overview](README.md).
- A new developer can read `docs/TESTING.md` (write it in this sprint) and run all tests in 10 minutes.

## 7. Demo

Show CI green. Break one quote check on purpose. Show that CI becomes red. Fix it.
