# Sprint 04 — Today dashboard and daily habits

| | |
|---|---|
| **Length** | 2 weeks |
| **Branch** | `sprint-04-today` |
| **Depends on** | Sprint 03 (title, question) |
| **Report ideas** | B3 Today dashboard, C6 Daily goals, C7 Wins journal, F3 Focus timer |

## 1. Goal

When the app opens, the student sees at once: the goal, the tasks of today, and one next best action. Small daily habits start.

## 2. Scope

**In:** B3, C6, C7, F3.

**Out:** Streak, level and quest on the dashboard (empty boxes now; filled in Sprints 05-07). Review cards due (Sprint 06).

## 3. Development

### Backend
1. Table `goals(id, date, text, kind, target, done)`. `kind` = `papers`, `words`, `focus`, `free`.
2. Table `wins(id, date, text)`.
3. Table `focus_sessions(id, start, end, minutes, task_text, paper_id)`.
4. Endpoints: `GET/POST/PUT/DELETE /api/goals`, `GET/POST /api/wins`, `POST /api/focus/start`, `POST /api/focus/stop`.
5. **Next best action** `GET /api/today/next`. Rules, no AI (fast and free). In order:
   1. A card has a "Not found" field → "Search the paper again".
   2. A sub-question has 0 or 1 paper → "Find a paper for SQ2".
   3. A paper has no Feynman attempt → "Explain 'Smith 2024' in your words".
   4. Else → "Write your win of the day".
6. `GET /api/today` returns title, question, today's goals, next action, focus minutes today, a random past win.

### Frontend
1. New page `Today.jsx`. It is the home page after login. Blocks:
   - Title + question.
   - 3 goals of today (check boxes).
   - Next best action (one big button).
   - Focus timer.
   - "Win of the day" field.
   - Empty boxes for Streak, Level, Quest, Review (with the text "Coming soon").
2. Focus timer: 25/5 by default, the student can change it. Link the session to a goal or a paper. Sound at the end (option).
3. On a bad day: a button "Show my past wins" shows 5 old wins.

## 4. Tests

| Type | Test |
|------|------|
| Unit | Next best action: each of the 4 rules with test data. |
| API | Create 3 goals, mark one done → `/api/today` shows 1/3. |
| API | Focus start + stop → a session with the correct minutes. |
| API | Stop without start → clear error. |
| API | Win saved → shows in the "past wins". |
| Frontend unit | Timer counts down and switches to rest. |
| E2E | Login → Today page is the first page → check a goal → start and stop a short timer → write a win. |

## 5. Manual checklist

- [ ] The Today page loads in less than 1 second.
- [ ] The page is calm, not crowded. One main action is clear.
- [ ] The timer works when the browser tab is in the background.
- [ ] The page works on a phone screen.

## 6. Done gate

Definition of Done in the [overview](README.md). The owner uses the Today page for 3 days and gives feedback.

## 7. Demo

Open the app. Read the next best action. Do it. Run a focus session. Write a win.
