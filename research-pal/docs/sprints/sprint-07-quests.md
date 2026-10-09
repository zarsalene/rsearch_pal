# Sprint 07 — Quests, boss fights, companion

| | |
|---|---|
| **Length** | 2 weeks |
| **Branch** | `sprint-07-quests` |
| **Depends on** | Sprint 05 (game engine), Sprint 06 (map) |
| **Report ideas** | C3 Quests and boss fights, C11 Study companion |

## 1. Goal

The student chooses weekly missions that fit the PhD stage. Hard papers become "bosses" to defeat. A small companion makes the Feynman method fun.

## 2. Scope

**In:** quest engine, weekly choice of 3 quests, boss fights, "Duck" companion (with a switch to hide it).

**Out:** Quests that need writing features (they unlock in Sprints 08-09).

## 3. Development

### Backend
1. File `backend/app/quests.json`: the list of quests. Each quest has: `code, title, text, stage, condition, xp, unlock_feature`. Example:
   - `disagree_3`: "Find 3 papers that disagree on the same point." Condition: 3 links of type "can be compared" with a student note.
   - `eli12_hard`: "Explain your hardest paper to a 12-year-old." Condition: one A2 view + one Feynman pass on a boss paper.
   - `supervisor_pack`: unlocks in Sprint 12.
2. Table `quests_active(id, code, week, chosen_at, done_at)`.
3. Each Monday: the server picks 3 quests that fit the stage and the unlocked features. The student chooses 1 or 2.
4. The server checks the conditions after each XP event (in `game.py`).
5. **Boss:** column `is_boss` on `papers`. Defeated when: quiz ≥ 80% **and** Feynman ≥ 80%. Badge "Boss defeated: <paper title>".
6. **Companion messages:** a small list of kind messages by event (level up, back after a pause, boss defeated). No AI call; fixed STE texts.

### Frontend
1. Today page: fill the Quest box. On Monday: "Choose your quests" (3 cards).
2. `Journey.jsx` (part 3): quest log, done quests, bosses.
3. Card page: button "Mark as boss". Boss papers show a small crown in the library.
4. The Duck: a small icon at the bottom of the Feynman tab. The text field says "Explain it to Duck". The Duck shows a message after an event. Setting: show / hide.

## 4. Tests

| Type | Test |
|------|------|
| Unit | Quest pick: Year 1 student gets reading quests, not writing quests. |
| Unit | Locked feature → quest is not offered. |
| Unit | Each quest condition with test data. |
| Unit | Boss defeated only when both scores ≥ 80%. |
| API | Choose 2 of 3 quests → a third choice is refused. |
| API | Quest done → XP and done date. |
| **Truth** | A quest that needs links counts only links with verified quotes. |
| E2E | Monday → choose a quest → do it → see "Quest done". |
| E2E | Mark a boss → pass quiz and Feynman → see the badge. |

## 5. Manual checklist

- [ ] The quests feel useful for the real PhD, not like busy work.
- [ ] The Duck is fun, but not childish. Hide works.
- [ ] A missed quest gives no penalty.

## 6. Done gate

Definition of Done in the [overview](README.md). The owner does 2 weeks of quests and says which quests to keep or remove.

## 7. Demo

Choose 2 quests. Mark the hardest paper as a boss. Explain it to the Duck. Defeat the boss.
