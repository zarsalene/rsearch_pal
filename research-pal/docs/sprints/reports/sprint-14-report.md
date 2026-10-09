# Sprint 14 report: Real game: Duck Island

| | |
|---|---|
| **Branch** | `sprint-14-play` (on top of `sprint-13-avatar`) |
| **Ideas** | Owner request: a real game, not only challenges |
| **Status** | Ready for the gate. |

## 1. What I built

| Part | What it does | Files |
|------|--------------|-------|
| Island | A 12 x 8 island on a canvas. The Duck walks with the arrow keys, W A S D or a click. Three places: Quote Hunt, Word Match, Shop. | `frontend/src/Play.jsx` |
| Mini-games | Quote Hunt (quote → paper) and Word Match (word → meaning). Rounds of up to 5 questions. Only quotes that the server checks again in the PDF text. The result shows title, page and quote. | `backend/app/play.py` |
| Coins | 1 coin for each 5 points of real work, plus coins from play (limit 15 a day, bonus 2 for a perfect round of 3 or more). | `play.py` |
| Shop and decoration | 9 items. Buy one time. Place on a free tile. | `play.py`, `Play.jsx` |
| Backup | Finished rounds and items. | `main.py` |
| Switch | `play`. | `features.py` |
| Tests fix | The Sprint 08 e2e test of the Write tab was flaky: it reloaded before the save with both quotes. It now waits for that save. | `e2e/app.spec.js` |

## 2. Test results

```
pytest -q            224 passed   (Sprint 13: 209 tests; test_play.py: 15 tests)
npm test             86 passed (Play.test.jsx: 8 tests)
npm run build        built
npm run e2e          15 passed
```

## 3. Rules kept

- Play gives no points, levels or badges. A test checks it, and the e2e test checks that the points do not change.
- Truth test: a quote that is not in the PDF, or that is in another paper, never appears in a round.
- The answers stay on the server until a round is finished. A round pays one time only.
- No timer, no lives, no loss. Stop at any time without a penalty. A full daily limit says "play for fun".
- The island has buttons for each place, so the keyboard and a screen reader can use it.

## 4. Open points for the owner

- Play the island for a week. Tell me which mini-games to add (for example: order the steps of a method, fill a missing word of a quote).
- The island is flat (2D). The 3D avatar is on the Journey page. We can put the avatar on the island later.
- The e2e data has only 2 checked quotes, so rounds there have 2 questions. A real library has more.
