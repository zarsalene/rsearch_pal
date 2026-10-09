# Sprint 04 report: Today dashboard and daily habits

| | |
|---|---|
| **Branch** | `sprint-04-today` |
| **Ideas** | B3 Today dashboard, C6 Daily goals, C7 Wins journal, F3 Focus timer |
| **Status** | Ready for the gate. Built in its own git worktree, on top of Sprint 03. |

## 1. What I built

| Part | What it does | Files |
|------|--------------|-------|
| Tables | `goals`, `wins`, `focus_sessions` (all with a date of the student). | `backend/app/db.py` |
| Next best action | `GET /api/today/next`. Four rules, no AI (plus "Add your first paper" when the library is empty). | `backend/app/today.py` |
| Today data | `GET /api/today?date=`: title, question, goals, next action, focus minutes, running session, win of today, one random past win. | `main.py` |
| Goals | `GET/POST/PUT/DELETE /api/goals`. 10 goals per day at most. | `main.py` |
| Wins | `GET/POST/DELETE /api/wins` (`before=` for the past wins). | `main.py` |
| Focus | `POST /api/focus/start`, `POST /api/focus/stop`, `GET /api/focus/active`, `GET /api/focus?date=`. The server counts the minutes with its own clock (limit 600 minutes). The page cannot send minutes. | `main.py`, `today.py` |
| Page | `Today.jsx`: first page after login. Next best action (one big button), goals, focus timer, win, past wins, focus time, 4 "Coming soon" boxes. | `frontend/src/Today.jsx`, `FocusTimer.jsx`, `timer.js`, `today.css` |
| Switch | `today` (on by default). When off, the first page is the card page. | `features.py` |
| Backup | Goals, wins and focus sessions are in the backup file. | `main.py` |

## 2. Test results

```
pytest -q            118 passed, 1 warning in 38.5s   (Sprint 03 + 02 + 01: 105 tests)
npm test             Test Files 8 passed (8) / Tests 48 passed (48)
npm run build        built
npm run e2e          10 passed (1.7m)
```

- **Rules of the next action:** one test for each rule, and the order (rule 1 wins over rule 2).
- **Focus:** start and stop count the minutes with a test clock. A second start gives an error. A stop without a start gives "No focus session is running." A forgotten session has a limit of 600 minutes.
- **The page cannot write trusted data:** the test sends `minutes: 999` to `/focus/start`. The server ignores it.
- **Kind words:** a test scans the texts of the next action for words of blame ("missed", "behind", "lazy", "failed", "late", "only").
- **Timer (unit tests with a fake clock):** counts down, switches to rest, then waits. It is right after a long pause of the tab. It goes on after a reload.
- **E2E:** Today is the first page → add and check a goal → start and stop the timer → write a win → past wins.
- **CI:** see section 6.

This sprint has no AI feature, so it has no truth test and no smoke test with the real AI.

## 3. Differences from the sprint file

| Sprint file | What I did | Why |
|-------------|-----------|-----|
| Rule list of 4 | A 5th rule at the start of rule 4: with no paper, "Add your first paper". | An empty app should not ask for a win. |
| `focus_sessions(id, start, end, minutes, task_text, paper_id)` | I added `date`, `planned`, `goal_id`. | The date of the student, the plan, and the link to a goal. |
| Date | The page sends its own date (`?date=`). | The server can be in another time zone (Render is in UTC). |
| Goals "kind" | `papers`, `words`, `focus`, `free` are labels. The student checks the goal. | Counting words and papers by itself would be wrong data. Real counts come with the points in Sprint 05. |
| Focus "Sound" | A short beep, off by default. | |
| E2E | After login, the tests open the Card tab first. | Today is the first page. |

## 4. Manual checklist

- [ ] **Owner:** the Today page loads in less than 1 second. (Agent: it makes one request and no AI call. I did not measure the time in a browser.)
- [ ] **Owner:** the page is calm. One main action is clear.
- [ ] **Owner:** the timer works when the browser tab is in the background. (Agent: the unit test with a fake clock passes. The real tab test is yours.)
- [ ] **Owner:** the page works on a phone screen. (The grid has one column below 820 px.)
- [ ] **Owner:** you use the Today page for 3 days and give feedback (gate of the sprint file).

## 5. Demo steps

1. Open the app. Read the next best action. Click the big button.
2. Add 3 goals. Check one.
3. Start the focus timer (try 1 minute in the field "Focus"). Stop it.
4. Write your win. Click "Show my past wins".

## 6. Known problems and risks

1. **The timer starts from the clock of your computer.** After a reload, it uses the start time of the server. If the two clocks differ by some seconds, the time is a little wrong.
2. **No notification** at the end of a phase when the tab is in the background. The title of the tab shows the time. The sound is optional.
3. **Rules of the next action are simple.** "Explain this paper" can come before the paper is useful to you. Rule 3 picks the newest paper without an attempt.
4. **Streak, Level, Quest, Review** are empty boxes ("Coming soon").
5. Ports 8001 and 5174 were used by another process on my computer, so I ran the e2e tests with `E2E_API_PORT=8104 E2E_APP_PORT=5304`.
