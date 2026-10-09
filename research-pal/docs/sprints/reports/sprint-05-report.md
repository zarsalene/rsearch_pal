# Sprint 05 report: Game core

| | |
|---|---|
| **Branch** | `sprint-05-game-core` (built on top of `sprint-04-today`) |
| **Ideas** | C2 Skill levels, C5 Kind streaks, C8 Milestone badges, C9 Personal records, C10 Own rewards |
| **Status** | Ready for the gate. |

## 1. What I built

| Part | What it does | Files |
|------|--------------|-------|
| XP engine | All rules in one file. `xp_events` has a UNIQUE key on (action, ref_id): a second row for the same action is impossible. | `backend/app/game.py`, `db.py` |
| Hooks | The server gives XP after it verified the action: card ready (`process_paper`, `process_extra`, `fill`), Feynman pass (`/explain`), correct quiz answer, link with quotes in both PDFs, focus session, win. A problem in the game never stops the real work. | `main.py` |
| Levels | 6 levels. Each needs XP and a skill. | `game.py` |
| Kind streak | 2 rest tokens each week, weekend off by default, a kind message after a pause. The day of an event follows the time zone of the student. | `game.py` |
| Badges, records, rewards | Tables `badges`, `rewards`. 6 badges. Records compare only with the own past. Own rewards with the conditions `level:N`, `xp:N`, `streak:N`, `cards:N`. | `game.py`, `main.py` |
| API | `GET /api/game`, `GET /api/game/events`, `PUT /api/game/settings`, `POST/DELETE /api/rewards`, `POST /api/rewards/{id}/claim`. No endpoint writes XP. | `main.py` |
| UI | `Journey.jsx` (level card, streak, badges, records, own rewards, where the points came from, animation switch). The boxes Level and Streak on the Today page are filled. A calm message for a new level or badge (`GameWatcher.jsx`). | `frontend/src/` |
| Switch | `game` (on). While it is off, no XP is given. | `features.py` |
| Backup | Points, badges, rewards and the weekend setting are in the backup. | `main.py` |

## 2. Test results

```
pytest -q            145 passed in 44.9s   (Sprint 04: 118 tests)
npm test             Test Files 9 passed (9) / Tests 58 passed (58)
npm run build        built
npm run e2e          11 passed (1.4m)
```

- **Each XP rule** has a test (card, Feynman, quiz, link, focus, win). **Same action 2 times gives XP one time** (also: a second attempt on the same paper, the same question, the same link in the other order).
- **Streak tests:** Mon, Tue, (Wed rest token), Thu gives 4. The third missing day in a week ends it. Weekend off: not broken. The tokens start again each week. Today without points does not end the streak.
- **Level:** XP alone is not enough. The skill alone is not enough.
- **Truth tests:** a card with a hidden claim gives no XP. A link with one false quote gives no XP. A Feynman score under 70 gives no XP. The client cannot send XP: no route has "xp" in its path, only `/api/game/settings` writes under `/api/game`, and extra fields like `xp: 9999` in other requests are ignored.
- **Kind words:** a test scans the texts of the game for words of blame and of ranking.
- **E2E:** Feynman pass, "+25 points", Journey (level card, 1 of 3 Feynman checks, badge, streak, an own reward that you can claim), then the Today boxes.
- **CI:** see section 8.

This sprint has no AI feature of its own. The XP rules use the verification of earlier sprints. So there is no new smoke test with the real AI.

## 3. A bug that I found and fixed

My CSS file had an animation called `rise`, the same name as the animation of the main page. The main page moved to the side. Playwright showed it with a screenshot. I renamed my animation. Also, nine tabs did not fit on a 1280 px screen: on a screen narrower than 1500 px, only the open tab shows its label.

## 4. Differences from the sprint file

| Sprint file | What I did | Why |
|-------------|-----------|-----|
| Level table of the report: Explorer needs 5 cards | Explorer is the start level. **Reader** needs 100 points + 5 cards with checked quotes + 3 Feynman checks. Critic 250, Connector 450, Author 700, Doctor 1000 points, with the skills from the report. | The demo says "Start at Explorer". The point numbers are my choice. You can change them in `game.py`. |
| Levels from Critic | They need counters (critical reading checks, gaps, sections, outline) that do not exist yet. The level stays locked and the page says "this part of the app is not built yet". | Sprints 08 and 09 build them. |
| "Feynman attempt passed: 25 XP" | One time for each **paper**. | More attempts on the same paper would be a way to farm points. |
| `xp_events(id, time, action, ref_id, xp)` | Added `date` and the UNIQUE key. | The day of the student, and no double XP. |
| Success metric | The owner chose "papers understood" only. It is the count "Feynman checks passed" on the Journey page. | Owner decision. |
| Animation setting | In the browser (localStorage), on the Journey page. | It is a setting of the device. |

## 5. Manual checklist

- [ ] **Owner:** the game feels like a reward, not a pressure. (You use the app for 1 week: gate of the sprint file.)
- [ ] **Owner:** no text makes you feel guilty. (A test checks the words. You read the texts.)
- [ ] **Owner:** animations can be switched off. (A test checks the switch.)
- [ ] **Owner:** the records compare only with your own past. (Yes: there is no other data.)
- [ ] **Owner:** do the point values and the level steps feel right? Tell me, and I change `game.py`.

## 6. Demo steps

1. Open **Journey**. You are an Explorer with 0 points.
2. Make cards with checked quotes. Open a card, click **Understand**, explain the paper, and pass the check (70 or more).
3. Open **Journey** again: points, the badge "First Feynman pass", the way to Reader.
4. Add your own reward: "A coffee", condition `xp:20`. Claim it.
5. Show the streak. Explain the rest tokens and the weekend setting.

## 7. Known problems and risks

1. **The point values and level steps are my first guess.** Change them in one place (`game.py`).
2. **The levels Critic and higher cannot be reached yet.** This is on purpose.
3. **The time zone** comes from the browser. If you use the app from two time zones, the day of an event can be different by one.
4. **A game can push a student to work for points.** The rules give points only after checks, and each action gives points one time. The Journey page says what counts.
5. **Older work gives no points.** Cards and Feynman checks made before this sprint give no points. A "Read again" on a card gives its card points.
6. **A rest day keeps the streak.** A student who works 5 days in a week keeps the streak with 2 rest days. This is the kind rule of the sprint file.

## 8. CI result

(see the run of the branch on GitHub)
