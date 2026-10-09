# Sprint 13 — 3D avatar (level look)

| | |
|---|---|
| **Length** | 1 week |
| **Branch** | `sprint-13-avatar` |
| **Depends on** | Sprint 05 (levels), Sprint 06 (Journey page) |
| **Report ideas** | Owner request: a 3D avatar in the game |

## 1. Goal

The student sees a small 3D character on the Journey page. The character shows the level of the student. Each new level adds one item. The student turns the character with the mouse or the finger.

## 2. Scope

**In:** one low-poly character made with three.js, six looks (one for each level), a switch in Settings, a button to hide it, a fallback picture when the browser has no WebGL.

**Out:** buying items (Sprint 14), a custom character editor, any sound.

## 3. Rules

- The look comes only from the level. The level comes only from real work.
- The avatar never gets sad, sick or poor. A lost streak changes nothing. Items are never taken away.
- No public view. The avatar is only for the student.
- Animation stops when the student switches animations off or the browser asks for "reduce motion".

## 4. Development

1. `frontend/src/avatar.js`: the table of looks (level index → items and colors), `lookFor(level)`, `webglOk()`.
2. `frontend/src/Avatar3D.jsx`: builds the character from simple shapes. Loads three.js only when needed (dynamic import), so the first page load stays small. Turn with the pointer. Cleans up the renderer when the page closes.
3. `AvatarFallback`: a flat SVG with the same items, used when WebGL fails.
4. `Journey.jsx`: show the avatar in the Level card, with the name of the next item.
5. Feature switch `avatar` (backend `features.py`) and a "Hide avatar" button (saved in the browser).

## 5. The six looks

| Level | Item added |
|-------|-----------|
| Explorer | Backpack |
| Reader | Glasses and a book |
| Critic | Magnifying glass |
| Connector | Rope with a knot |
| Author | Pen and a scroll |
| Doctor | Doctor cap and a gold star |

## 6. Tests

| Type | Test |
|------|------|
| Unit | `lookFor` gives only the items of the level and of the levels before it. |
| Unit | An unknown level gives the Explorer look. |
| Unit | The avatar shows the fallback when WebGL is not there. |
| Unit | "Hide avatar" removes it and the choice is kept. |
| API | The `avatar` switch is in the feature list and can be switched off. |
| E2E | Journey page: the avatar picture and the name of the next item are visible. |

## 7. Manual checklist

- [ ] The character is nice to see and is not childish.
- [ ] It turns smoothly. It does not use much power when the tab is hidden.
- [ ] No text of the avatar makes the student feel bad.

## 8. Done gate

Definition of Done in the [overview](README.md).
