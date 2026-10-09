# Sprint 09 report: Gap finder, writing coach, critical reading

| | |
|---|---|
| **Branch** | `sprint-09-writing-2` (on top of `main` at `v0.14.0`) |
| **Ideas** | D2 Gap finder, D4 Writing coach, H2 Critical reading check |
| **Status** | Ready for the gate. |

## 1. What I built

| Part | What it does | Files |
|------|--------------|-------|
| Gap finder | Compares the papers of a sub-question. Lists: agree, disagree, gap. A point of "agree" or "disagree" is kept only if checked quotes cover two papers at least. A gap has the label "AI opinion" and a reason. The student confirms a gap or says "not a gap". "Use this gap" adds a heading to the outline. | `backend/app/gaps.py`, `Gaps.jsx` |
| Writing coach | Comments on one section: citations against the library (paper, page, quote on the page), claims without a citation, style rules (no AI), and clear / logical notes from the AI. The server refuses a comment that gives new text. | `backend/app/coach.py`, `Write.jsx` |
| Quality check | A checklist of 6 items. A "yes" or "no" needs a checked quote, else the answer is "Unclear". The student changes answers, adds notes and confirms. | `backend/app/critique.py`, `Quality.jsx` |
| Game links | A confirmed gap counts for the level Connector. Ten checks count for the level Critic. | `game.py`, `quests.py` |
| Switches | `gaps`, `coach`, `critique`. | `features.py` |
| Backup | Gap runs, gaps and quality checks are in the backup. | `main.py` |
| Bug fixes | `db.gap_runs_all` and `db.critiques_all` called the database again inside the lock (a deadlock in the backup). The coach split `p. 9` as the end of a sentence. The e2e test of Duck Island raced; it now waits for each question. | `db.py`, `coach.py`, `e2e/app.spec.js` |

## 2. Test results

```
pytest -q            239 passed   (main at v0.14.0: 224 tests; test_gaps_coach_critique.py: 15 tests)
npm test             91 passed (Quality.test.jsx: 5 tests)
npm run build        built
npm run e2e          16 passed
```

## 3. Rules kept

- Truth tests: a point with a false quote is dropped; a citation to page 9 of a paper with 4 pages is marked; an answer without a checked quote is "Unclear".
- The coach never writes text for the student (a test checks that a rewrite is refused).
- Every AI text has the label "AI opinion" or a "checked" label. Each AI text passes the `ste.py` check.
- The AI parts work or fail kindly: when the AI is down, the rule-based checks of the coach still show.

## 4. Open points for the owner

- Try the coach on a real paragraph. Tell me which style rules are too strict.
- The gap finder sees only a part of each paper (the best passages). Read the quotes before you trust a gap.
