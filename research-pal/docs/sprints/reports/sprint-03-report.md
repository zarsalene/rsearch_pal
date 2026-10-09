# Sprint 03 report: Thesis title and question helper

| | |
|---|---|
| **Branch** | `sprint-03-direction` (pushed to `origin`, not merged, not tagged) |
| **Date** | 9 October 2026 |
| **Status** | Ready for the gate. The owner must run the demo and the "Owner" items. |

## 1. What I built

Ideas: B1 Thesis subject title, B2 Research question helper, Idea 0 PhD stage, and tags for papers and cards.

| Part | What it does | Files |
|------|--------------|-------|
| Tables | `project` (one row), `sub_questions`, `project_history`, `paper_tags`. `CREATE TABLE IF NOT EXISTS`, no row is dropped. | `backend/app/db.py` |
| Project and history | `GET/PUT /api/project` (title, question, stage). Each change of the title or the question writes one history row with the old value. `GET /api/project/history`. | `db.py`, `main.py` |
| Sub-questions | `GET/POST/PUT/DELETE /api/sub-questions`. `PUT` changes the text or the `position` (reorder). A delete closes the hole and removes the tags. | `db.py`, `main.py` |
| Tags and coverage | `PUT /api/papers/{pid}/tags` (the new list replaces the old one). `GET /api/project/coverage` gives the number of papers for each sub-question and a `level` (none, thin, ok). The list of papers carries the tags. | `db.py`, `main.py` |
| Question helper | `POST /api/project/question-check`: FINER (5 items, `ok` or `weak`, one sentence each), scope (`ok`, `too_wide`, `too_vague`), 3 narrower versions labelled **AI suggestion**. The FINER and scope items are labelled **AI opinion**. It saves nothing. | `backend/app/project.py` |
| Sub-question helper | `POST /api/project/split`: 3 to 5 suggestions labelled **AI suggestion**. It saves nothing. | `project.py` |
| Switch | New feature switch **Thesis direction** (on by default). | `features.py` |
| Backup | Export and import keep the project, the stage, the sub-questions and the tags. Additive: the backup is still version 1. | `main.py` |
| Thesis bar | A thin bar under the top bar on each page. Click it to edit the title and the question. | `frontend/src/ThesisBar.jsx`, `App.jsx` |
| Thesis tab | The helper in 4 steps, the sub-question editor (add, edit, reorder, delete, AI suggestions), coverage bars, history timeline. | `frontend/src/Project.jsx` |
| Tag chips | SQ1, SQ2 ... on the card page (for the open card) and in the library (for the selected paper). | `frontend/src/TagChips.jsx`, `CardView.jsx`, `Library.jsx` |
| Settings | PhD stage (Year 1, Year 2-3, Final year). | `frontend/src/Settings.jsx` |
| Tests | 28 backend tests, 24 frontend tests, 3 e2e tests. See section 2. | `backend/tests/test_direction.py`, `frontend/src/*.test.jsx`, `frontend/e2e/app.spec.js` |
| Docs | README section "Thesis title and question helper", checked with `ste.lint`. | `README.md` |

## 2. Test results

I ran all commands on my computer (Windows 11, Python 3.14, Node 24). These are the real output lines.

```
pytest -q                 56 passed, 1 warning in 17.40s     (28 old + 28 new)
npm test                  Test Files  5 passed (5) / Tests  30 passed (30)     (6 old + 24 new)
npm run build             ✓ built in 7.91s
npm run e2e               6 passed (1.5m)                    (3 old + 3 new)
```

- **Old tests:** all 28 old backend tests, 6 old unit tests and 3 old e2e tests pass. I did not change any old check. I added one mock (`saveProject`) to `Settings.test.jsx`.
- **No truth test.** The sprint file says this sprint shows no quotes. The equivalent rules are tested: the AI saves nothing (`test_question_check_does_not_change_the_saved_question`), every AI text has a label, and a missing or wrong AI rating never becomes "ok" (`test_the_answer_of_the_ai_is_cleaned`).
- **STE check:** a long explanation goes through `ste.enforce` (`test_question_check_explanations_go_through_the_ste_check`).
- **Old databases:** a test starts from a database with the old setting `thesis_question`. The question moves into the project one time, the history stays empty, and the old rows stay.
- **E2E path of the sprint file:** write a vague question → FINER check → choose a version → 4 sub-questions → tag 2 papers → coverage shows "SQ1: 2 papers", "SQ2: 1 paper", "SQ3: No paper yet".
- **CI:** not run. I cannot run GitHub Actions on my computer. The CI file did not change.

## 3. Smoke test (real AI)

The sprint shows no quotes from papers, so I did not read 3 PDFs. I ran the two new AI helpers with the real AI (Gemini then Groq chain from your `backend/.env`, temporary data folder):

| Input | Result |
|-------|--------|
| "AI in health" | Scope `too_wide`. F, I, N weak. E, R ok. 3 narrow versions (breast cancer diagnosis, medication adherence, barriers in primary care). Good. |
| A clear question about validation agents and false alarms | Scope `ok`. All 5 letters `ok`. 3 small refinements. The helper did not force a change. Good. |
| Split of the clear question | 5 sub-questions, all labelled **AI suggestion**. Good. |

One text was odd (see section 7, point 1).

## 4. Differences from the sprint file

| Sprint file | What I did | Why |
|-------------|-----------|-----|
| Table `project(id, title, question, stage, updated_at)` | Same. The old setting `thesis_question` moves into it at start-up. `GET /api/config` still gives `thesis_question`. `PUT /api/settings` still works and writes to the project. | The question was a setting before. Two copies would go out of step. The old setting row stays in the database. |
| Each change of title or question writes a history row | The first value writes a row too (old value empty). A save with no change writes nothing. A restore from a backup writes nothing. | The timeline then shows all versions. |
| `PUT /api/papers/{pid}/tags` | Body: `{sub_question_ids, card_id}`. `card_id` is `""` for the first card. | The table `paper_tags` has a `card_id` column, so each card of a paper can have tags. A paper counts one time in the coverage. |
| 3-5 sub-questions | The AI suggests 3 to 5. The student can have up to 10. | A hard limit of 5 would block a student. |
| Chips "in the library" | The library shows the chips under the selected paper. They tag the **first card**. Other tags show as "SQ1 · SQ2" on each paper. | Simple. A card tab has its own chips on the card page. |
| "All AI text goes through STE" | The explanations (FINER, scope) go through `ste.enforce`. The 3 versions and the sub-questions do not. | They are question texts that the student may use. A rewrite for "max 20 words" could damage the question. |
| Coverage "SQ2: 1 paper in orange" | `level`: none (no paper, grey dashed bar), thin (1 paper, orange), ok (2 or more, green). The server decides the level. | No red for "none": the app must be kind. |
| A switch for each feature | One switch, **Thesis direction**. It blocks the history, the helpers, the sub-questions, the tags and the coverage. `GET/PUT /api/project` stay open. | The title and question were always part of the app. The question stays in Settings when the switch is off. |
| (not in the file) | `playwright.config.js` reads `E2E_API_PORT` and `E2E_APP_PORT` (default 8001 and 5174). | See section 7, point 2. |
| (not in the file) | The default answers of the fake AI know the question helper (`tests/fake_ai.py`). | The e2e test and `fake_server.py` need them. |

## 5. Manual checklist

- [x] With a vague question ("AI in health"), the helper says "too wide" and gives narrow versions. (Agent: yes, real AI, section 3.) **Owner:** try your own vague question.
- [x] With a good question, the helper does not force a change. (Agent: yes, real AI. The page says "Your question looks good. You do not have to change it." and has "Keep my question".) **Owner:** try your real question.
- [x] The title bar does not take too much space on a small screen. (Agent: one line, 34 px high. Below 560 px wide it shows the title only. I looked at one screenshot of the helper at 390 px width.) **Owner:** look on your phone.
- [ ] **Owner:** write your real thesis title and question in the app (gate of the sprint file).
- [ ] **Owner:** the Thesis tab and the title bar look right in light and dark mode.
- [ ] **Owner:** read the text of the helper. Is it clear and kind?
- [ ] **Owner:** run `npm run e2e` on your computer. If another run uses the ports 8001 and 5174, set `E2E_API_PORT` and `E2E_APP_PORT`.

## 6. Demo steps

1. Open the **Thesis** tab. Write "AI in health". Click **Check my question**.
2. Show the FINER check and "Scope: too wide". Every AI text has a label.
3. Click **See narrower versions**. Choose one. Edit the text. Click **Save as my main question**. The title bar shows it.
4. Click **Suggest sub-questions**. Add 4. Edit one, move one, delete one.
5. Open two papers. Click the chips SQ1, SQ2 on their card pages.
6. Open the Thesis tab. Show the coverage. Then click the title bar, change the title, and show the History.
7. Settings → Features: switch **Thesis direction** off and on.

## 7. Known problems and risks

1. **Odd STE rewrite.** In the real AI test, `ste.enforce` changed one sentence to "…from LLM stands for large language model threat hunting." The rewrite passed the safe check (it kept all names and numbers) but it reads badly. The cause is the shared STE rewrite, not this sprint. The text is only an AI opinion, and the student decides. I did not change `ste.py`.
2. **Two sessions in one folder.** Another Claude session (`research-pal-6f`) was changing the same working folder at the same time (glossary, `words.py`, `ste.py`, `llm.py`: it looks like Sprint 01). At the start I made my branch in that folder. For a short time its uncommitted work sat on my branch name. I switched the folder back to `main`, removed my own edits there, and built this sprint in a separate git worktree (`..\sprint-03-wt`). **Its files are not changed and not committed by me.** Its e2e run also used ports 8001 and 5174 at the same time as mine, and my first e2e run failed because of it. I did not stop its processes. I made the ports configurable instead.
3. **Merge conflicts are likely** with Sprint 01. Both sprints change `db.py` (tables), `features.py`, `main.py`, `App.jsx`, `Settings.jsx`, `CardView.jsx`, `Library.jsx`, `api.js`, `styles.css`, `fake_ai.py` and the README. The changes are additive, but whoever merges second must resolve them by hand.
4. **Your working copy.** The staged deletions in `graphify-out/` and the changes in `research-pal/.gitignore` and the root `.gitignore` are not mine. I did not commit them.
5. **The FINER ratings are an AI opinion.** "Novel" is the weakest: the AI does not know all the literature. The prompt tells it to say what it assumes. The page labels all ratings **AI opinion**.
6. **Library chips tag the first card only.** A student who works on a second card tab must use the chips on the card page.
7. **A rating that the AI does not give** becomes "weak" with the text "The AI gave no rating for this letter. Check it yourself." The server never turns a missing rating into "ok".
8. **CI is not run for this branch.** Line-ending warnings (LF to CRLF) appear in git on Windows. They are not a problem for the tests.
