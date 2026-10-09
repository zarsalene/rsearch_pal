# Sprint 11 report: Suggestions, timeline, weekly review, journal

| | |
|---|---|
| **Branch** | `sprint-11-suggest-and-plan` (on top of `main` at `v0.10.0`) |
| **Ideas** | E2 Suggest next papers, F1 PhD timeline, F2 Weekly review, F4 Research journal |
| **Status** | Ready for the gate. The manual checks with the real library and the real milestones are for the owner (section 4). |

## 1. What I built

| Part | What it does | Files |
|------|--------------|-------|
| Suggestions | Once a day (in the background, when the To read tab is opened) and on request. It reads the references and the citations of the library papers (OpenAlex). Score = 60% links + 40% fit to the question. The reason is true and plain: "Cited by 4 of your papers", "Cites 3 of your papers". A paper in the library, or one that you rated "not useful", is not suggested again. They go to To read with the source `suggested`. | `backend/app/suggestions.py`, `sources.py` |
| Timeline | Tables `milestones` and `milestone_tasks`. Default milestones by stage. CRUD. "Suggest weekly tasks": the AI proposes at most 3 tasks for each of the next 12 weeks. They have the label "AI suggestion" until the student edits them. A split replaces only the AI tasks that the student did not touch. | `backend/app/plan.py` |
| Weekly review | Table `weekly_reviews`. One review for each week, a second save updates the first. Mood 1 to 5. 15 points one time for each week. Due from Friday. | `plan.py`, `game.py` |
| Journal | Table `journal` with the kinds idea, experiment, decision, result. Links to papers (unknown links are dropped). 3 points, at most 5 entries each day. | `plan.py` |
| Map | Method Workshop fills with decisions. Data Mines fills with experiments and results. (Sprint 06 had these regions as "not available yet".) | `journey.py` |
| UI | The **Plan** tab (timeline, tasks, weekly review, mood chart, journal), the weekly review on the Today page from Friday, the tag "Suggested" and the button "Suggest papers now" in To read. | `Plan.jsx`, `Today.jsx`, `ToRead.jsx` |
| Switches, backup | `plan`, `suggest`. Milestones, tasks, reviews and journal are in the backup. | `features.py`, `main.py` |
| Tests fix | The slow-machine settings of Sprint 10 stay. A test that wrote a table `journal` by hand now uses the real functions. | `test_review.py` |

## 2. Test results

```
pytest -q            284 passed   (main at v0.10.0: 266 tests; test_plan.py: 18 tests)
npm test             105 passed (Plan.test.jsx: 9 tests, ToRead.test.jsx: 5 tests)
npm run build        built
npm run e2e          the new Plan test passed locally; the full run is in CI
```

## 3. Rules kept

- Truth: every AI task has the label "AI suggestion". The student's edit removes the label. The AI never writes thesis text (the prompt forbids it, the tasks are short actions, and each passes the ASD-STE100 check).
- Suggestion reasons come from counts in the data, not from the AI.
- Private and kind: the mood is only for the student. A late milestone and a missed week have no penalty and no red color.
- Points only for real work: 15 for a review (one time for each week), 3 for a journal entry (limit 5 a day).
- No network in the tests: recorded OpenAlex answers.

## 4. Open points for the owner (manual checklist)

- [ ] The suggestions for your real library: are at least 5 of the top 10 relevant? (Your papers need a DOI.)
- [ ] Enter your real PhD milestones. Is the timeline clear at a glance?
- [ ] Do one weekly review. Does it take less than 5 minutes?
- The daily run starts when you open the To read tab (the free server may sleep). Click "Suggest papers now" at any time.
