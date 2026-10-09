# Research_Pal: Sprint Plan

**Source:** [IMPROVEMENT_REPORT.md](../../IMPROVEMENT_REPORT.md). The idea codes (A1, B2, C4 ...) come from this report.
**Language:** ASD-STE100 Simplified Technical English.

## How the sprints work

Each sprint is a **small separate project**. It has its own goal, its own development, its own tests, and its own done gate. Do not start the next sprint before the gate of the current sprint is passed.

```
  Plan  ──►  Develop  ──►  Test  ──►  Demo  ──►  Gate  ──►  next sprint
   1 day      ~6 days      ~2 days    0.5 day    pass?
                             ▲                    │ no
                             └────── fix ─────────┘
```

- **Length:** 2 weeks for each sprint (Sprint 0: 1 week).
- **Branch:** one git branch for each sprint, `sprint-NN-name`. Merge into `main` only when the gate passes.
- **Tag:** after the merge, tag the version `v0.NN.0`. So you can go back to any sprint.
- **Feature switch:** each new feature has a switch in Settings, so a problem in a new feature does not block the app.

## The sprints

| # | Name | Report ideas | Phase | Weeks |
|---|------|--------------|-------|-------|
| [00](sprint-00-test-foundation.md) | Test foundation | — | Base | 1 |
| [01](sprint-01-simple-and-words.md) | Simple mode and word helper | A3, A4, H1 | 1. Understand | 2 |
| [02](sprint-02-feynman-and-quiz.md) | Feynman mode and quiz | A1, A2, A5 | 1. Understand | 2 |
| [03](sprint-03-direction.md) | Thesis title and question helper | B1, B2, Idea 0 | 2. Direction | 2 |
| [04](sprint-04-today.md) | Today dashboard and daily habits | B3, C6, C7, F3 | 2. Direction | 2 |
| [05](sprint-05-game-core.md) | Game core: XP, levels, streaks | C2, C5, C8, C9, C10 | 3. Motivation | 2 |
| [06](sprint-06-garden-and-map.md) | Knowledge Garden and Expedition map | C4, C1 | 3. Motivation | 2 |
| [07](sprint-07-quests.md) | Quests, boss fights, companion | C3, C11 | 3. Motivation | 2 |
| [08](sprint-08-writing-1.md) | Citations and literature review builder | D3, D1 | 4. Writing | 2 |
| [09](sprint-09-writing-2.md) | Gap finder, writing coach, critical reading | D2, D4, H2 | 4. Writing | 2 |
| [10](sprint-10-find-papers.md) | Add by DOI, import, triage | E1, E3, E4 | 5. Papers | 2 |
| [11](sprint-11-suggest-and-plan.md) | Suggestions, timeline, weekly review, journal | E2, F1, F2, F4 | 5. Plan | 2 |
| [12](sprint-12-supervisor-and-release.md) | Supervisor pack, email, release | G1, G2 | 6. People | 2 |

**Total:** about 25 weeks (6 months) for one developer.

## Test levels (the same in each sprint)

| Level | Tool | What it checks |
|-------|------|----------------|
| Unit (backend) | `pytest` | One function. Example: the FSRS date, the XP rules. |
| API (backend) | `pytest` + FastAPI `TestClient` + **fake AI** | Each new endpoint. No real AI call, so the test is fast and the same each time. |
| Truth test | `pytest` + fake AI that gives a **false quote** | The "no wrong data" rule. A false quote must be hidden or labelled. **Required for each AI feature.** |
| Unit (frontend) | `Vitest` + React Testing Library | One component. |
| End to end | `Playwright` | A full user path in a real browser. |
| Manual | Checklist in the sprint file | What a person must see and feel (clear, simple, kind). |
| Real AI smoke test | Script, run by hand | 3 real papers with the real AI. Read the result. |

## Definition of Done (for each sprint)

A sprint is done only when **all** items are true:

1. All tests pass in CI (old tests and new tests).
2. Each new AI feature has a truth test.
3. Each new AI text passes the `ste.py` check.
4. The manual checklist of the sprint is complete.
5. The real AI smoke test is done on 3 papers, with no wrong quote shown as verified.
6. The README has a short section for each new feature (in STE).
7. The demo is done, and the owner says "pass".
8. The branch is merged and tagged.

## Rules for all sprints

1. **No wrong data.** Each claim has a verified quote, or a clear label (AI suggestion, AI opinion).
2. **The student thinks; the AI helps.** The AI does not write the thesis.
3. **Simple first.** All AI text follows ASD-STE100.
4. **Points only for real work.**
5. **Be kind.** No guilt, no public ranking.
6. **Privacy.** Unpublished ideas are private by default.
