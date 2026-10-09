# Sprint 11 — Suggestions, timeline, weekly review, journal

| | |
|---|---|
| **Length** | 2 weeks |
| **Branch** | `sprint-11-suggest-and-plan` |
| **Depends on** | Sprint 10 (sources, To read list), Sprint 04 (goals) |
| **Report ideas** | E2 Suggest next papers, F1 PhD timeline, F2 Weekly review, F4 Research journal |

## 1. Goal

The app suggests the next papers. The student plans the full PhD, stops each week to look back, and keeps a memory of each decision.

## 2. Scope

**In:** E2, F1, F2, F4. Fill the map regions "Method Workshop" and "Data Mines".

**Out:** Supervisor pack (Sprint 12).

## 3. Development

### Backend
1. **Suggestions** `GET /api/suggestions`:
   - For each paper in the library, get its references and the papers that cite it (OpenAlex).
   - Score a candidate by: how many library papers link to it, and the triage score (Sprint 10).
   - Reason in plain text: "Cited by 4 of your papers", "Cites 3 of your papers".
   - Run in the background once a day. Results go to the "To read" list with source `suggested`.
2. **Timeline:** table `milestones(id, title, due, done, position)` and `milestone_tasks(id, milestone_id, week, text, done)`. Default milestones by stage: proposal, first paper, thesis draft, defense. `POST /api/milestones/{id}/split` → the AI suggests weekly tasks (**AI suggestion**, the student edits).
3. **Weekly review:** table `weekly_reviews(id, week, done, blocked, learned, next_goal, mood)`. Mood 1-5.
4. **Journal:** table `journal(id, date, kind, text, paper_ids, card_ids)`. `kind` = `idea`, `experiment`, `decision`, `result`.
5. Map: Method Workshop fills with `decision` entries; Data Mines fills with `experiment` and `result` entries.
6. Game: XP for a weekly review (15) and a journal entry (3, max 5 each day).

### Frontend
1. "To read" tab: suggestions with a small "Suggested" tag and the reason.
2. New page `Plan.jsx`:
   - Timeline (a horizontal line with milestones and dates). Today marker.
   - Weekly tasks of the current milestone.
   - Journal (list + new entry; link a card or a paper).
3. Friday: Today page shows "Weekly review (5 minutes)". A short form with 5 questions.
4. Mood chart over the weeks (simple line). Only the student sees it.

## 4. Tests

| Type | Test |
|------|------|
| Unit | Suggestion score with recorded OpenAlex data. |
| Unit | A paper already in the library is never suggested. |
| API | Milestones CRUD; split → tasks labelled "AI suggestion". |
| API | Weekly review: one for each week; a second one updates the first. |
| API | Journal entry with links to cards → map regions change. |
| E2E | Make a milestone → split it → check a task → write a journal entry → see the map. |
| E2E | Friday → weekly review form → saved. |

## 5. Manual checklist

- [ ] The suggestions for the real library of the owner are relevant (at least 5 of the top 10).
- [ ] The timeline is clear at a glance.
- [ ] The weekly review takes less than 5 minutes.

## 6. Done gate

Definition of Done in the [overview](README.md). The owner enters the real PhD milestones and does one weekly review.

## 7. Demo

Show 5 suggestions with reasons. Make the timeline to the defense. Write a decision in the journal. Do the weekly review.
