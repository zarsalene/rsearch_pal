# Sprint 06 — Knowledge Garden and Expedition map

| | |
|---|---|
| **Length** | 2 weeks |
| **Branch** | `sprint-06-garden-and-map` |
| **Depends on** | Sprint 02 (`review_items`), Sprint 05 (game engine) |
| **Report ideas** | C4 Knowledge Garden (spaced review), C1 PhD Expedition map |

## 1. Goal

The student does not forget what he or she read. The student sees the full PhD road and where he or she is on it.

## 2. Scope

**In:** spaced review with FSRS, garden view, Expedition map with 6 regions.

**Out:** Quests on the map (Sprint 07).

## 3. Development

### Backend
1. Add the open FSRS library (Python package `fsrs`) to `requirements.txt`.
2. Add columns to `review_items`: `due, stability, difficulty, reps, lapses, last_review`.
3. Make review items from: quiz questions (Sprint 02), glossary words (Sprint 01), and one "main idea" item for each card.
4. Endpoints:
   - `GET /api/review/due` → items due today.
   - `POST /api/review/{id}` with `{rating}` (Again, Hard, Good, Easy) → FSRS sets the next date.
5. Plant state for each paper: `fresh`, `ok`, `dry` (from the due dates). A plant never dies.
6. XP: 2 for each review (max 20 each day).
7. **Map** `GET /api/journey/map` → percent for each region:

| Region | Fills with |
|--------|-----------|
| Question Peak | Title + question + sub-questions (Sprint 03) |
| Literature Forest | Cards ready and Feynman passes, for each sub-question |
| Method Workshop | Journal entries (Sprint 11) — 0% until then |
| Data Mines | Journal "experiment" entries (Sprint 11) |
| Writing Coast | Review sections written (Sprint 08) |
| Defense Castle | Thesis outline + practice (later) |

### Frontend
1. New page `Review.jsx`: one item at a time. Show the question → student thinks → "Show answer" → 4 buttons.
2. Garden view: a grid of plants, one for each paper. Color by state. Click → review this paper only.
3. Today page: fill the box "Review: 7 cards due".
4. `Journey.jsx` (part 2): the map. Simple SVG with 6 regions on a path. Each region fills with color. Click a region → what to do to fill it.

## 4. Tests

| Type | Test |
|------|------|
| Unit | FSRS: rating "Good" → due date later than "Hard". |
| Unit | Plant state from due dates. |
| Unit | Map percent for each region with test data. |
| API | `/review/due` returns only items with `due ≤ today`. |
| API | Rate an item → new due date saved; XP added (max 20/day). |
| **Truth** | Each review item shows a quote that is verified in the PDF; an item without a verified quote is not created. |
| Frontend unit | Review card: hidden answer → "Show answer" → buttons. |
| E2E | Today → Review → rate 3 items → count goes down → garden updates. |

## 5. Manual checklist

- [ ] A review session of 10 items takes less than 5 minutes.
- [ ] Dry plants look calm, not sad or alarming.
- [ ] The map is clear on a phone screen.
- [ ] The map shows "0%" regions as "Not started", with a kind first step.

## 6. Done gate

Definition of Done in the [overview](README.md). The owner does review sessions on 5 days.

## 7. Demo

Show 10 items due. Do the review. Show the garden become fresh. Open the map. Show the Literature Forest grow.
