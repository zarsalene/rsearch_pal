# Sprint 07 report: Quests, boss fights, companion

| | |
|---|---|
| **Branch** | `sprint-07-quests` (on top of Sprint 06) |
| **Ideas** | C3 Quests and boss fights, C11 Study companion (Duck, kept in this sprint by the owner) |
| **Status** | Ready for the gate. |

## 1. What I built

| Part | What it does | Files |
|------|--------------|-------|
| Quest list | 16 quests with code, title, text, stage, kind, condition, XP and the feature that unlocks them. | `backend/app/quests.json` |
| Quest engine | Weekly pick of 3 (same input, same quests; quests of the last 3 weeks come last; kinds are mixed). The student chooses 1 or 2. The conditions are checked after each point event. Done: points one time, done date. | `backend/app/quests.py`, `game.py` |
| Locked quests | A quest whose feature does not exist (literature review, gap finder, supervisor pack) is not offered. It unlocks when the feature exists and is on. | `quests.py`, `features.py` |
| Bosses | `papers.is_boss`, `boss_defeated_at`. Defeated at quiz 80% and Feynman 80% (at least 3 answered questions). Badge and 50 points. The quiz and explain answers say "boss defeated". | `quests.py`, `main.py` |
| Duck | Fixed kind messages in ASD-STE100 by event. No AI. | `backend/app/companion.py`, `Duck.jsx` |
| UI | Quest block on Today, quest log and bosses on Journey, "Mark as boss" on the card, crown in the library, Duck in the Understand tab. | `Quests.jsx`, `Duck.jsx`, `CardView.jsx`, `Library.jsx` |
| Switches | `quests`, `duck`. | `features.py` |
| Backup | Quests, bosses, and the views "like I am 12". | `main.py` |

## 2. Test results

```
pytest -q            185 passed   (Sprint 06: 165 tests)
npm test             Test Files 10 passed / Tests 65 passed
npm run build        built
npm run e2e          13 passed (1.4m)
```

- **Pick:** a year-1 student gets reading quests and no writing quest. The stage changes the offer. A locked feature gives no quest, and it unlocks with its switch.
- **Conditions:** each condition with test data, counting only the work of this week.
- **Choose:** 2 of 3 work, a third is refused, a drop has no penalty.
- **Done:** a done quest gives its points one time and a done date. A quest that is not chosen is never done. A missed week gives no penalty.
- **Truth:** the quest "3 links that disagree" counts only links of the type "compares_with" with a verified quote in both PDFs.
- **Boss:** defeated only when both scores are 80% or more (79% is not enough, 75% quiz is not enough, 2 of 2 answers is too few). One victory, one badge, 50 points.
- **Duck:** all messages pass the ASD-STE100 check and have no word of blame. Hiding it works.
- **E2E:** choose 2 of 3 quests, the third button is disabled, drop one, mark a boss (button, crown, Journey list), the Duck message, hide the Duck.
- **CI:** see section 7.

This sprint has no AI feature. So there is no truth test with a fake AI and no smoke test.

## 3. A bug that I found and fixed

The points of a correct quiz answer defeated the boss before my own check ran. So the answer said "no boss defeated". Now the endpoints compare the state of the boss before and after the call.

## 4. Differences from the sprint file

| Sprint file | What I did | Why |
|-------------|-----------|-----|
| "Each Monday the server picks 3 quests" | At the first request of the week. | The server has no scheduler. The result is the same and it is stable all week. |
| `disagree_3`: "with a student note" | Without a note. | Notes on links do not exist. The quote check is the proof. |
| `eli12_hard` | A view "like I am 12" on a boss paper this week + a Feynman pass on a boss paper this week. | The view is saved in a small table `activity`. |
| Quests for later sprints | `lit_section`, `gap_5_lines`, `supervisor_pack` are in the list. They stay locked. | They unlock in Sprints 08, 09 and 12. Their feature names must be `litreview`, `gaps` and `supervisor`. The table names are `lit_sections`, `gap_notes`, `packs_sent`. |
| E2E "Mark a boss, pass quiz and Feynman, see the badge" | The e2e test marks a boss. The victory is tested in the API tests. | The fake AI gives only 2 valid quiz questions. A boss needs 3 answers. |
| E2E "Monday, choose, do, Quest done" | The e2e test chooses, refuses a third and drops. "Quest done" is tested in the API tests. | The 3 offered quests change with the week, so the browser test cannot do them. |

## 5. Manual checklist

- [ ] **Owner:** the quests feel useful for the real PhD, not like busy work. Tell me which to keep or remove (gate: 2 weeks of quests). The list is `backend/app/quests.json`.
- [ ] **Owner:** the Duck is fun, but not childish. Hide works.
- [ ] **Owner:** a missed quest gives no penalty. (A test checks this.)

## 6. Known problems and risks

1. **The quest list is my first guess.** You can change it without code: edit the JSON file.
2. **Quests count the work of the whole week**, also the work before you chose the quest.
3. **The Duck has 2 messages for each event.** The same seed gives the same message.
4. **A deleted paper keeps its boss badge** with the name "a paper".
5. **No notification** when a quest is done: the Today page shows it, and the points show on Journey.

## 7. CI result

(see the run of the branch on GitHub)
