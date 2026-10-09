# Sprint 02 report: Feynman mode and quiz

| | |
|---|---|
| **Branch** | `sprint-02-feynman-and-quiz` |
| **Ideas** | A1 Explain it to me, A2 Explain like I am 12, A5 Ask me questions |
| **Status** | Ready for the gate. Built in its own git worktree, so it did not touch your working folder. |

## 1. What I built

| Idea | What it does | Files |
|------|--------------|-------|
| A1 | `POST /api/papers/{pid}/explain`. The text of the student is cut into claims. The best passages of the paper go to the AI. The AI marks each claim and gives a quote. The server checks each quote in the PDF and each number. It lists the missing main points, gives a score and a kind message, and saves the attempt (table `explanations`). | `backend/app/understand.py`, `main.py` |
| A2 | `POST /api/papers/{pid}/eli12`. A simple text, one example, one analogy. Example and analogy: label **AI suggestion**. Terms: only terms that are in the paper. | `understand.py` |
| A5 | `POST /api/papers/{pid}/quiz` (3 to 5 questions), `POST /api/quiz/{id}/answer`. Table `review_items(kind quiz or glossary)`. A glossary word is also a review item. | `understand.py`, `db.py` |
| UI | Card page: tabs **Card / Understand**. Understand has 3 parts. Colored sentences, proof panel, missing points, history of attempts, one question at a time, result. | `frontend/src/Understand.jsx`, `understand.css`, `CardView.jsx` |
| Switches | `feynman`, `eli12`, `quiz` (all on by default). | `features.py` |
| Backup | Attempts and quiz questions are in the backup file. | `main.py` |
| Fix | `vectors.query_paper` tries again, and makes the index again from the saved text, when ChromaDB fails by chance (see section 5). | `backend/app/vectors.py` |

## 2. How the server protects the facts

- **Feynman mark:** `correct`, `partly` and `wrong` need a quote that the server finds in the PDF. If not, the mark becomes `cannot_check` and the quote is not shown.
- **Numbers:** if a claim has a number that is not in the paper, the server marks it `wrong` itself (source: server), whatever the AI said.
- **Quiz:** a question is dropped without a verified quote. It is also dropped when the answer has a number that the quote does not have. The answers stay on the server until the student answers.
- **Quiz mark:** if the student writes a number that the source does not have, the mark cannot be "correct".
- **Like I am 12:** the example and the analogy must not add a number. The simple text must keep numbers and names.
- **Comments of the AI** go through the ASD-STE100 check. The AI never writes the explanation for the student.

## 3. Test results

```
pytest -q            77 passed, 1 warning in 26.73s   (Sprint 01: 59 tests)
npm test             Test Files 4 passed (4) / Tests 16 passed (16)
npm run build        built
npm run e2e          6 passed (1.6m)
```

Truth tests (new): a mark with a false quote → `cannot_check`; a quiz question with a false quote → dropped; a number that is not in the PDF → `wrong` with source "server"; a quiz answer with a new number → not "correct"; a number change in the example → refused.

## 4. Smoke test (real AI)

One real paper (Attention Is All You Need):
- Feynman check on the card text plus one false claim ("99.99 percent accuracy"): two sentences **correct** with pages 1 and 3, the false sentence **wrong**. Score 80/100.
- Like I am 12: simple text OK, a sensible example and analogy.
- Quiz: 4 questions about the problem, the method, the BLEU result and the training time. Each has a verified quote and page.

The second paper (BERT) failed: the AI provider refuses its size (known problem of Sprint 00 and 01, Gemini model retired and Groq limit). The Definition of Done asks for 3 papers. This stays an Owner item.

## 5. A bug that I found and fixed

The first search of a new server can fail with "Nothing found on disk" (ChromaDB). My end-to-end test hit it at the first call of `/explain`. The same risk exists for chat, links and the word helper. `vectors.query_paper` now tries 5 times, and after 3 failures it makes the index of the paper again from the saved text. A test covers this (`test_a_search_that_fails_by_chance_is_tried_again`). I did not find the root cause in ChromaDB.

## 6. Differences from the sprint file

| Sprint file | What I did | Why |
|-------------|-----------|-----|
| Marks: `correct`, `partly`, `wrong`, `not in paper`; `cannot check` for a false quote | Same. | |
| "The server lists the main card fields that the student did not mention" | A rule without AI: words of the checked answer that the student also used (at least 2 words or 25%). | Cheap, same every time. It can miss a synonym. |
| Score | 60% accuracy of the claims that the server could check + 40% coverage of the main points. | The file gives no rule. |
| `review_items` columns | I added `card_id`, `ref_id`, `last_mark`, `tries`. | The spaced review of Sprint 06 needs them. |
| Quiz answers | Answers are not sent with the questions. | The student answers from memory. |
| `/eli12` | Also `terms`: the technical terms of the paper. | "The paper calls this …" line. |
| Three switches | `feynman`, `eli12`, `quiz`. | Each feature has a switch. |

## 7. Manual checklist

- [ ] **Owner:** on 3 real papers, write a correct explanation → mostly green. (Agent: 1 paper, with text from the card.)
- [ ] **Owner:** write an explanation with one wrong number → this claim is red. (Agent: tested with a false number, in a test and with the real AI.)
- [ ] **Owner:** the quiz questions are about important points, not small details. (Agent: 4 questions on a real paper looked right.)
- [ ] **Owner:** the tone is kind. Example: "Good start. 1 point is missing."
- [ ] **Owner:** you try the Feynman mode on one paper of your own field and say "useful".

## 8. Demo steps

1. Open your hardest paper. Click **Understand**, then **Explain it to me**.
2. Write 5 lines about the paper. Click **Check my explanation**. Look at the colors. Click a red sentence.
3. Read **Points that you did not mention**. Add them to your text. Check again. The score goes up. Open **Your attempts**.
4. Click **Like I am 12**, choose Method.
5. Click **Quiz me**, **Make new questions**. Answer from memory. Read the correct quote.

## 9. Known problems and risks

1. **Gemini model retired / Groq limit** (see Sprint 00 and 01 reports): long papers fail with the real AI.
2. **The "missing points" rule is simple.** A student can use other words and still get "missing".
3. **The AI can mark a claim "correct" with a true quote that does not fully prove it.** The server checks only that the quote is in the PDF. The student should click the sentence and read the quote.
4. **Score is a guide, not a grade.**
5. **ChromaDB** can still fail by chance. The retry reduces the risk.
