# Sprint 05 — Game core: XP, levels, streaks

| | |
|---|---|
| **Length** | 2 weeks |
| **Branch** | `sprint-05-game-core` |
| **Depends on** | Sprints 02, 03, 04 (the actions that give XP) |
| **Report ideas** | C2 Skill levels, C5 Kind streaks, C8 Milestone badges, C9 Personal records, C10 Own rewards |

## 1. Goal

Real research work gives visible progress. The game follows the golden rule: **points only for real work that the app can verify.**

## 2. Scope

**In:** XP engine, 6 skill levels, kind streaks with rest tokens, milestone badges, personal records, own rewards.

**Out:** Map (Sprint 06). Quests (Sprint 07).

## 3. Development

### Backend
1. New module `backend/app/game.py`. All game rules are in this one file, so they are easy to change.
2. Table `xp_events(id, time, action, ref_id, xp)`. An event is written **only** by the server, after a verified action. Examples:

| Action | XP | Verified when |
|--------|----|---------------|
| Card ready | 10 | All main fields have a verified quote. |
| Feynman attempt passed | 25 | Score ≥ 70%. |
| Quiz answered correctly | 5 | Server marks it correct. |
| Link explained | 10 | Link has verified quotes in both PDFs. |
| Focus session | 1 for each 5 min | Session ≥ 20 minutes. |
| Win written | 2 | Max one for each day. |

3. **No double XP:** one `(action, ref_id)` gives XP one time only.
4. **Levels** (Explorer → Reader → Critic → Connector → Author → Doctor). Each level needs XP **and** a skill condition (see report C2). Example: Reader = 3 Feynman attempts passed. Critic and later levels unlock when their features exist (Sprints 08-09).
5. **Kind streak:** a day counts if it has ≥ 1 XP event. 2 rest tokens each week. Weekend off by default (setting).
6. **Badges:** table `badges(id, code, earned_at)`. Rare milestones only: First card, First Feynman pass, 7-day streak, 30-day streak, 100 cards, 1 year.
7. **Records:** this week vs. last week; this month vs. last month (XP, focus minutes, cards).
8. **Own rewards:** table `rewards(id, text, condition, earned_at, claimed)`.
9. `GET /api/game` returns level, XP, next level needs, streak, tokens, badges, records.

### Frontend
1. Today page: fill the boxes Level and Streak.
2. New page `Journey.jsx` (part 1): level card, list of badges, records, own rewards.
3. Small, calm animation when the student goes up a level or gets a badge. Setting to switch off animations.
4. Kind text only. Example after a lost streak: "Welcome back. Your knowledge is still here."

## 4. Tests

| Type | Test |
|------|------|
| Unit | Each XP rule in the table. |
| Unit | Same action 2 times → XP one time. |
| Unit | Streak: Mon, Tue, (Wed rest token), Thu → streak 4. |
| Unit | Streak: weekend off → not broken. |
| Unit | Level needs XP **and** the skill condition. |
| **Truth** | A card with a hidden (not verified) claim does not give "Card ready" XP. |
| **Truth** | The client cannot send XP. No endpoint writes `xp_events` directly. |
| API | `/api/game` returns correct data after a set of actions. |
| E2E | Do a Feynman pass → see XP go up → see the level card change. |

## 5. Manual checklist

- [ ] The game feels like a reward, not a pressure.
- [ ] No text makes the student feel guilty.
- [ ] Animations can be switched off.
- [ ] Records compare only with the past of the same student.

## 6. Done gate

Definition of Done in the [overview](README.md). The owner uses the app for 1 week and says the game is "motivating, not stressful".

## 7. Demo

Start at Explorer. Make cards, pass a Feynman check. Go up to Reader. Show the streak with a rest day.
