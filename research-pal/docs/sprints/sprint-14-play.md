# Sprint 14 — Real game: Duck Island

| | |
|---|---|
| **Length** | 2 weeks |
| **Branch** | `sprint-14-play` |
| **Depends on** | Sprint 05 (points), Sprint 07 (Duck), Sprint 13 (avatar) |
| **Report ideas** | Owner request: a real game, not only challenges |

## 1. Goal

A small game that the student plays for fun, inside the app. The student walks with the Duck on an island, plays short mini-games, wins coins and decorates the island. The mini-games use the quotes and the words of the student's own papers, so play also helps memory.

## 2. Rules

- **Play gives no points, no levels and no badges.** Those come only from real, verified work (Sprint 05).
- **Coins** come from two sources: real work (1 coin for each 5 points) and mini-games (limit of 15 coins each day).
- **No wrong data.** A mini-game uses only a quote that the server checks again in the PDF text. A false quote is never in a round.
- **The server keeps the answers.** The page gets them only after the round is finished. A round pays one time only.
- **No guilt.** No timer, no lives, no loss, no ranking. A full daily limit only means: play for fun, no more coins today. The student can stop a round at any time without a penalty.
- **Access.** The island works with the mouse, the keyboard and a screen reader (buttons do the same as walking).

## 3. Scope

**In:** the island (2D canvas, a Duck that walks), two mini-games (Quote Hunt, Word Match), coins, a shop with 9 items, decoration, backup, a switch.

**Out:** sound, multiplayer, any public view, play with the AI.

## 4. Development

### Backend (`play.py`)
1. Tables `play_rounds` (a round with its questions and answers, its score and its coins) and `play_items` (the items that the student has, and their place).
2. `Quote Hunt`: a quote from a quiz question or a saved word → which paper? `Word Match`: a word of the glossary → which meaning? Rounds of 5 questions (minimum 2).
3. Coins: work coins + play coins − price of the items. The perfect-round bonus is 2 coins for a round of 3 questions or more.
4. Endpoints: `GET /api/play`, `POST /api/play/rounds`, `POST /api/play/rounds/{id}/finish`, `POST /api/play/buy`, `PUT /api/play/items/{code}`.
5. Backup: finished rounds and items are in the backup.
6. Switch `play`.

### Frontend (`Play.jsx`)
1. The island on a canvas. Walk with the arrow keys, W A S D or a click. Step on a place to open it.
2. Buttons for each place (Quote Hunt, Word Match, Shop, Decorate).
3. Round panel with the result and the source (title, page, quote) of each question.
4. Shop and decoration panels.
5. Section "Play" on the Journey page.

## 5. Tests

| Type | Test |
|------|------|
| API | A round has questions and no answers. |
| **Truth** | A quote that is not in the PDF (or is in another paper) never appears in a round. |
| API | A round pays one time only. A bad answer list is refused. |
| API | The daily limit stops the coins, not the play. |
| API | Play gives no points, no level and no badge. |
| API | The shop: not enough coins is refused with a kind message; an item is bought one time. |
| API | Place an item only on a free place of the island. |
| API | The switch turns the game off. The backup keeps coins and items. |
| Unit | Coins, a round, the result with sources, a stop without penalty, buy, place, walk with the keys. |
| E2E | Play Quote Hunt, see the sources, buy a flower, place it. The points do not change. |

## 6. Manual checklist

- [ ] It is fun to walk and to play. It is not childish.
- [ ] Nothing in the game makes the student feel bad.
- [ ] The island works on a phone.

## 7. Done gate

Definition of Done in the [overview](README.md). The owner plays for a week and says which mini-games to add.
