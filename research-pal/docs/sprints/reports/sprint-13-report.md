# Sprint 13 report: 3D avatar (level look)

| | |
|---|---|
| **Branch** | `sprint-13-avatar` (on top of `main` at `v0.08.0`) |
| **Ideas** | Owner request: a 3D avatar in the game |
| **Status** | Ready for the gate. |

## 1. What I built

| Part | What it does | Files |
|------|--------------|-------|
| Looks | Six items, one for each level. The look comes only from the level. | `frontend/src/avatar.js` |
| 3D character | A low-poly character made with three.js from simple shapes. It turns with the pointer and by itself. three.js loads only when the card shows. The renderer is cleaned up on close. | `frontend/src/Avatar3D.jsx` |
| Fallback | A flat picture with the same items when the browser has no WebGL. | `Avatar3D.jsx` |
| Journey page | An Avatar card next to the Level card. It names the next item. A "Hide avatar" button keeps its choice in the browser. | `Journey.jsx`, `App.jsx` |
| Switch | `avatar` in Settings → Features. | `features.py` |

## 2. Test results

```
pytest -q            209 passed   (Sprint 08: 208 tests)
npm test             78 passed (Avatar.test.jsx: 6 tests)
npm run build        built
npm run e2e          14 passed
```

## 3. Rules kept

- The avatar shows only the level. The level needs real, verified work.
- The avatar never gets sad. Items are never removed. A test checks that a higher level keeps all earlier items.
- No public view, no ranking.
- Animation stops for "reduce motion" and when the student switches animations off.

## 4. Open points for the owner

- Look at the character on a real phone. Tell me if you want other colors or shapes.
- Sprint 14 will let the student buy extra items with play coins. The level look stays the base.
