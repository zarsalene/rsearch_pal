# Sprint 01 — Simple mode and word helper

| | |
|---|---|
| **Length** | 2 weeks |
| **Branch** | `sprint-01-simple-and-words` |
| **Depends on** | Sprint 00 |
| **Report ideas** | A3 Simplified answers, A4 Word helper, H1 AI use log |

## 1. Goal

The student understands each text of the app. A hard word gets a fast explanation. Each AI call is recorded from now on, for an honest AI use statement.

## 2. Scope

**In:**
- A3: switch "Simple / Expert" for card, chat, links and mind map.
- A4: word helper with a personal glossary.
- H1: AI use log (record only; the export comes in Sprint 12).

**Out:** Feynman mode and quiz (Sprint 02).

## 3. Development

### Backend
1. **`ste.py`:** add a level `simple`. Rules: maximum 12 words in a sentence, explain each technical term, keep the term in brackets. Keep the rule "no number or name changes in a rewrite".
2. **New endpoint** `POST /api/papers/{pid}/simplify` with `{field, card_id}`. Returns the simple version. Cache it in `llm_cache`.
3. **Word helper** `POST /api/papers/{pid}/define` with `{term}`:
   - Step 1: search the paper for a definition (exact words + vectors). If found → return the passage + page, label **From the paper**.
   - Step 2: if not found → ask the AI, label **AI explanation**.
4. **Glossary** table `glossary(id, term, explanation, source, paper_id, page, created_at)`. Endpoints `GET/POST/DELETE /api/glossary`.
5. **AI log** table `ai_log(id, time, feature, paper_id, provider, model)`. Write one row in `llm.py` for each AI call (not for a cache hit). Endpoint `GET /api/ai-log`.

### Frontend
1. Switch "Simple / Expert" in the top bar. The browser remembers it.
2. On the card page, in Simple mode, each field shows the simple text, and a small link "Show the original".
3. Select a word in a card or in the chat → a small box with the explanation and the page chip. Button "Save to glossary".
4. New page `Glossary.jsx`: list, search, delete.

## 4. Tests

| Type | Test |
|------|------|
| Unit | `ste.py` simple level: a sentence of 18 words fails; a sentence of 10 words passes. |
| Unit | A rewrite that changes a number is refused. |
| API | `/simplify` returns a text and saves it in the cache (second call = no AI call). |
| API | `/define` with a word that the paper defines → label "From the paper" and the correct page. |
| API | `/define` with a word that is not in the paper → label "AI explanation". |
| **Truth** | Fake AI simple text changes "91.4" to "90" → the server refuses the text and keeps the original. |
| API | Each AI call writes one row in `ai_log`; a cache hit writes no row. |
| Frontend unit | Simple switch changes the text of a field. |
| E2E | Select a word → box opens → save → word is on the Glossary page. |

## 5. Manual checklist

- [ ] On 3 real papers, the simple text is easier to read and keeps all numbers.
- [ ] The word helper box opens in less than 3 seconds.
- [ ] The labels "From the paper" and "AI explanation" are clear.

## 6. Done gate

Definition of Done in the [overview](README.md), and the owner reads 3 simple cards and says "clear".

## 7. Demo

Open a hard paper. Switch to Simple. Select a hard word. Save it. Open the Glossary.
