# Sprint 03 — Thesis title and question helper

| | |
|---|---|
| **Length** | 2 weeks |
| **Branch** | `sprint-03-direction` |
| **Depends on** | Sprint 00 |
| **Report ideas** | B1 Thesis subject title, B2 Research question helper, Idea 0 PhD stage |

## 1. Goal

The student has a clear thesis title, a clear main question, and 3-5 sub-questions. Each paper is linked to a sub-question. The app knows the stage of the PhD.

## 2. Scope

**In:** B1, B2, Idea 0, tag papers and cards with sub-questions.

**Out:** Today dashboard (Sprint 04). Gap finder (Sprint 09).

## 3. Development

### Backend
1. Table `project(id, title, question, stage, updated_at)`. One row (one thesis).
2. Table `sub_questions(id, text, position)`.
3. Table `project_history(id, field, old_value, new_value, changed_at)`. Each change of title or question writes one row.
4. Table `paper_tags(paper_id, card_id, sub_question_id)`.
5. Endpoints:
   - `GET/PUT /api/project` (title, question, stage).
   - `GET /api/project/history`.
   - `GET/POST/PUT/DELETE /api/sub-questions`.
   - `PUT /api/papers/{pid}/tags`.
6. **Question helper** `POST /api/project/question-check` with `{question}`:
   - The AI checks the question with **FINER** (Feasible, Interesting, Novel, Ethical, Relevant). For each letter: `ok`, `weak`, with one sentence why.
   - It checks if the question is too wide or too vague.
   - It gives 3 narrower versions. All are labelled **AI suggestion**.
   - The AI does not save anything. The student chooses.
7. **Sub-question helper** `POST /api/project/split` → the AI suggests 3-5 sub-questions.
8. **Coverage** `GET /api/project/coverage` → number of papers for each sub-question.

### Frontend
1. Thesis title and main question in a thin bar at the top of each page. Click → edit.
2. New page `Project.jsx` (the question helper) in steps:
   1. Write your question.
   2. See the FINER check.
   3. Choose or edit one of the 3 versions.
   4. Make the sub-questions.
3. History view: a timeline of all versions of title and question.
4. On the card page and in the library: chips to tag a paper with sub-questions.
5. Coverage bar for each sub-question (example: "SQ2: 1 paper" in orange).
6. Settings: choose the PhD stage (Year 1, Year 2-3, Final year).

## 4. Tests

| Type | Test |
|------|------|
| API | Change the title 2 times → history has 2 rows with the old values. |
| API | Sub-questions: create, edit, reorder, delete. |
| API | Tag a paper → coverage counts it. |
| API | `/question-check` returns 5 FINER items and 3 versions with the label "AI suggestion". |
| API | `/question-check` does not change the saved question. |
| Frontend unit | Title bar shows the title and opens the edit field. |
| E2E | Full helper path: write → check → choose → sub-questions → tag 2 papers → see coverage. |

(No truth test: this sprint does not show quotes. All AI text is labelled "AI suggestion".)

## 5. Manual checklist

- [ ] With a vague question ("AI in health"), the helper says "too wide" and gives good narrow versions.
- [ ] With a good question, the helper does not force a change.
- [ ] The title bar does not take too much space on a small screen.

## 6. Done gate

Definition of Done in the [overview](README.md). The owner writes the real thesis title and question in the app.

## 7. Demo

Start with a vague question. Use the helper. End with a clear question and 4 sub-questions. Tag papers. Show the coverage.
