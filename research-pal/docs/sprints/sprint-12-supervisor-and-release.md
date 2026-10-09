# Sprint 12 — Supervisor pack, email, release

| | |
|---|---|
| **Length** | 2 weeks |
| **Branch** | `sprint-12-supervisor-and-release` |
| **Depends on** | Sprint 04 (wins), Sprint 11 (weekly review, journal), Sprint 01 (AI log) |
| **Report ideas** | G1 Supervisor meeting pack, G2 Ready email, H1 AI use statement export |

## 1. Goal

The student prepares a good supervisor meeting in one click and sends a clear email. The student can export an honest AI use statement. The full app is stable and released as version 1.0.

## 2. Scope

**In:** G1, G2, AI use statement export, the quest `supervisor_pack`, a full regression test, release.

**Out:** New features. This sprint closes the plan.

## 3. Development

### Backend
1. **Pack** `POST /api/supervisor/pack` with `{since}` (default: last meeting date):
   - Sections: What I did (goals done, papers read, words written), What I found (new cards, confirmed gaps, journal results), Where I am stuck (weekly review "blocked"), My questions (student field), Next steps (next goal, next milestone tasks), Wins.
   - Facts come from the data, not from the AI. The AI only makes the text short and clear (STE). Each number in the text must match the data.
   - Table `meetings(id, date, pack_md, email_md, sent)`.
2. **Email** `POST /api/supervisor/email` → subject + body (STE, polite, short). The app does **not** send it.
3. **AI use statement** `GET /api/ai-log/statement` → a short text from `ai_log`: features used, number of uses, models, dates. Plus a CSV of the full log.
4. Quest `supervisor_pack` unlocks.

### Frontend
1. New page `Supervisor.jsx`: pack preview (edit each section), field "My questions", button "Make email".
2. Email view: subject and body (edit), buttons "Copy" and "Open in my email program" (`mailto:` link).
3. Settings: supervisor name and email; date of last meeting.
4. Settings: "AI use statement" → preview + download.

### Release work
1. Full regression: run all tests of Sprints 00-11.
2. Performance check: library with 200 papers; Today page < 1 s; search < 2 s.
3. Update the README (STE) with all features.
4. Update `render.yaml` and the deploy steps.
5. Backup and restore of the data folder (test it).
6. Tag `v1.0.0`.

## 4. Tests

| Type | Test |
|------|------|
| **Truth** | Pack: fake AI changes "3 papers" to "5 papers" → the server refuses the text and uses the plain data text. |
| API | Pack with no data → kind text "A quiet week. That is normal." |
| API | Email has a subject and a body; no send action exists in the server. |
| API | AI statement counts match the `ai_log` rows. |
| E2E | Make pack → edit a section → make email → copy. |
| Regression | All old tests pass. |
| Performance | Load test with 200 papers (script). |
| Restore | Backup → delete data → restore → all papers and cards return. |

## 5. Manual checklist

- [ ] The owner sends a real pack to a real supervisor. The supervisor finds it clear.
- [ ] The AI statement is correct for 1 month of use.
- [ ] A full "first day to defense" walk through the app works with no error.

## 6. Done gate

Definition of Done in the [overview](README.md), plus:
- Regression, performance and restore tests pass.
- Version `v1.0.0` is tagged and deployed.

## 7. Demo

Full story: open Today → do a quest → review the garden → write a section → run the coach → make the supervisor pack → open the email.
