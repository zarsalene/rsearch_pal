# Sprint 06 report: Knowledge Garden and Expedition map

| | |
|---|---|
| **Branch** | `sprint-06-garden-and-map` (on top of Sprint 05) |
| **Ideas** | C4 Knowledge Garden (spaced review), C1 PhD Expedition map |
| **Status** | Ready for the gate. |

## 1. What I built

| Part | What it does | Files |
|------|--------------|-------|
| FSRS | The package `fsrs` (6.x, added to `requirements.txt`). Intervals in whole days (no learning steps in minutes). "Again" comes back the next day. | `backend/app/review.py` |
| Review items | `review_items` has the new columns `due, stability, difficulty, reps, lapses, last_review, fsrs_json`. Old rows get their date and are due. Items: quiz questions, glossary words, and one **main idea** item for each card. | `db.py`, `review.py` |
| Endpoints | `GET /api/review/due`, `GET /api/review/garden`, `POST /api/review/{id}` (again, hard, good, easy). | `main.py` |
| Plants | `fresh`, `ok`, `dry` from the due dates. A paper with no item is fresh. A plant never dies. | `review.py` |
| Points | 2 points for each review, 20 a day at most. The server refuses a review of an item that is not due. | `game.py` |
| Map | `GET /api/journey/map`: 6 regions with percent, state, detail and first step. The regions of later sprints read their tables (`journal`, `lit_sections`) when they exist. | `backend/app/journey.py` |
| Review page | The garden (one plant for each paper), "Review N due items", one item at a time, the four buttons. | `frontend/src/Review.jsx` |
| Map | SVG picture with rings, and a list under it for a phone. A click shows the first step and a "Go there" button. | `ExpeditionMap.jsx` |
| Today | The box "Review: N items due". | `Today.jsx` |
| Switches | `review` (Knowledge Garden) and `map` (PhD Expedition map), both on. | `features.py` |
| Backup | The dates of the review are in the backup. | `main.py` |

## 2. Test results

```
pytest -q            165 passed in 47s   (Sprint 05: 145 tests)
npm test             Test Files 10 passed (10) / Tests 65 passed (65)
npm run build        built
npm run e2e          12 passed (1.7m)
```

- **FSRS:** "Good" gives a later date than "Hard". The intervals grow with each good answer. A lapse is counted. A wrong rating gives an error.
- **Plants:** fresh, ok (1 and 2 days late), dry (3 days or more), a paper with no item is fresh.
- **Due:** only items with a date of today or earlier. A rated item is not due. An item that is not due cannot be rated (no way to farm points).
- **Points:** 2 for each review. 12 items in one day give 10 times 2 points (the rest give 0).
- **Truth tests:** the main idea item uses only a quote that is verified in the PDF (checked with `assert_no_false_quote`). A card with only false quotes gives no item. Items of the AI (a word) have the label "AI explanation" and no quote.
- **Map:** the percent of each region with test data, the kind first steps, the regions of later sprints with a test table.
- **Data:** a Sprint 02 database (review items without the new columns) opens, and its items are due. The words and main ideas get their dates back from a backup.
- **E2E:** Today box → Review → rate all items → the count goes to 0 → the garden is fresh → the map shows the road.
- **CI:** see section 8.

This sprint has no new AI call. So there is no new smoke test with the real AI.

## 3. Differences from the sprint file

| Sprint file | What I did | Why |
|-------------|-----------|-----|
| Columns `due, stability, difficulty, reps, lapses, last_review` | Same, and `fsrs_json` (the full state of the FSRS card). | The library needs its full state to compute the next date. |
| Plant states | `fresh`, `ok` (needs water), `dry` (3 days or more late). | The sprint file gives no rule. |
| One map switch? | The map has its own switch, `map`. | Each feature has a switch. |
| Region percents | My own formulas (see `journey.py`): Peak = title 25 + question 25 + 3 sub-questions 50. Forest = for each sub-question: 2 papers with a ready card (half) and 1 Feynman pass (half). | The file gives no formula. |
| "Cards ready and Feynman passes, for each sub-question" | A paper counts for a sub-question when it has a tag for it (Sprint 03). | Uses the tags. |
| Main idea items | Made when you open the review (idempotent). | No new hook in the card code. |
| Glossary items with an AI explanation | They stay items, with the label "AI explanation" and no quote. | The truth test of the sprint file is about items that show a quote of the paper. |

## 4. Manual checklist

- [ ] **Owner:** a review session of 10 items takes less than 5 minutes.
- [ ] **Owner:** the dry plants look calm, not sad or alarming. (The icon has a warm color and a dashed border. The word is "A little dry".)
- [ ] **Owner:** the map is clear on a phone screen. (Below 640 px the picture hides and a list shows the same data.)
- [ ] **Owner:** a region at 0% says "Not started" and gives a kind first step. (A test checks the texts.)
- [ ] **Owner:** you do review sessions on 5 days (gate of the sprint file).

## 5. Demo steps

1. Open **Today**. The box Review shows the items due. Click **Water your plants**.
2. Click **Review N due items**. Think, click **Show answer**, then rate. Do 10 items.
3. See the garden: the plants are fresh.
4. Open **Journey**. Click Literature Forest. Read the first step. Tag a paper to a sub-question and explain it. Look again: the forest has more color.

## 6. Known problems and risks

1. **Intervals are in whole days.** I chose no learning steps in minutes. A new item rated "Good" comes back after 2 days. This suits a daily review. A student who wants minutes needs another setting.
2. **The words and the main ideas get new ids after a restore.** The backup matches them by kind and reference, not by id. A restore on a server that already has other items can match an item with another old schedule only when the reference is the same.
3. **Old work counts.** All old quiz questions and words are due on the first day. A student with many items gets a long first list (50 items at most in one list).
4. **The map formulas are my first guess** (see section 3).
5. **The map regions Method Workshop, Data Mines and Writing Coast stay at 0%** until Sprints 08 and 11 make their tables. I will connect them then.
6. **FSRS gives the same dates for the same answers.** I turned the random "fuzz" off, so a test can check the dates.

## 7. CI result

The run of the branch passed: https://github.com/zarsalene/rsearch_pal/actions/runs/37957822836
