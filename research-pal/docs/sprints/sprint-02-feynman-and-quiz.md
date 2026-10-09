# Sprint 02 — Feynman mode and quiz

| | |
|---|---|
| **Length** | 2 weeks |
| **Branch** | `sprint-02-feynman-and-quiz` |
| **Depends on** | Sprint 01 (simple level of `ste.py`, glossary) |
| **Report ideas** | A1 Explain it to me, A2 Explain like I am 12, A5 Ask me questions |

## 1. Goal

The student understands a paper deeply and actively. The student explains the paper, and the app shows the gaps. The app asks questions, and the student answers from memory.

## 2. Scope

**In:** A1, A2, A5. The quiz questions are saved, so Sprint 06 can use them in the spaced review.

**Out:** Spaced review schedule (Sprint 06). XP for these actions (Sprint 05).

## 3. Development

### Backend
1. **A1 Feynman check** `POST /api/papers/{pid}/explain` with `{text, card_id}`:
   - The server cuts the text of the student into claims.
   - For each claim, it finds the best passages of the paper.
   - The AI marks each claim: `correct`, `partly`, `wrong`, `not in paper`. Each mark has a quote.
   - The server checks each quote (same check as the cards). A mark without a verified quote becomes `cannot check`.
   - The server lists the main card fields that the student did not mention (`missing`).
   - Table `explanations(id, paper_id, card_id, text, result_json, score, created_at)`.
2. **A2 Like I am 12** `POST /api/papers/{pid}/eli12` with `{field, card_id}`: simple text + one example + one analogy. The analogy has the label **AI suggestion**. The technical term stays in a second line.
3. **A5 Quiz** `POST /api/papers/{pid}/quiz` → 3-5 questions. Each question has a verified quote as the answer source. A question without a verified quote is dropped.
   - Table `review_items(id, kind, paper_id, question, answer, quote, page, created_at)`. `kind` = `quiz` or `glossary`.
   - `POST /api/quiz/{id}/answer` with `{answer}` → AI marks it, returns the correct quote and page.

### Frontend
1. Card page, new tab **Understand** with 3 parts: "Explain it to me", "Like I am 12", "Quiz me".
2. Feynman result: the text of the student with colors (green, orange, red). Click a color → see the quote and page. List of missing points.
3. History of attempts with the score, so the student sees progress.
4. Quiz: one question at a time, then the correct answer with the quote.

## 4. Tests

| Type | Test |
|------|------|
| Unit | Text cut into claims: 3 sentences → 3 claims. |
| API | `/explain` returns marks, missing fields and a score; it saves an attempt. |
| **Truth** | Fake AI marks a claim `correct` with a false quote → mark becomes `cannot check`. |
| **Truth** | Fake AI makes a quiz question with a false quote → the question is dropped. |
| API | `/eli12` returns the label "AI suggestion" for the analogy. |
| API | `/quiz/{id}/answer`: wrong answer → returns the correct quote and page. |
| Frontend unit | Feynman result shows 3 colors correctly. |
| E2E | Write an explanation → see the colors → do the quiz → see the result. |

## 5. Manual checklist

- [ ] On 3 real papers, write a correct explanation → mostly green.
- [ ] Write an explanation with one wrong number → this claim is red.
- [ ] The quiz questions are about important points, not small details.
- [ ] The tone is kind ("Good start. 2 points are missing.").

## 6. Done gate

Definition of Done in the [overview](README.md). The owner tries the Feynman mode on one paper of his or her own field and says "useful".

## 7. Demo

Take the hardest paper of the library. Explain it in 5 lines. Show the gaps. Fix them. Score goes up. Do the quiz.
