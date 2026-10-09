# Sprint 01 report: Simple mode and word helper

| | |
|---|---|
| **Branch** | `sprint-01-simple-and-words` (pushed to `origin`, not merged, not tagged) |
| **Ideas** | A3 Simplified answers, A4 Word helper, H1 AI use log |
| **Status** | Ready for the gate. The owner must run the demo and the "Owner" items. |

## 1. What I built

| Idea | What it does | Main files |
|------|--------------|-----------|
| A3 | Switch **Expert / Simple** in the top bar. In Simple mode the AI texts of the card (fields, verdict), the chat, the links and the mind map show a simple version. A link shows the original. | `backend/app/ste.py` (level `simple`, `simplify()`), `main.py` (`POST /api/papers/{pid}/simplify`, `POST /api/simplify`), `frontend/src/SimpleText.jsx`, `LevelToggle.jsx`, `level.js` |
| A4 | Select a word → a box with the meaning. Label **From the paper** (a sentence of the PDF, with the page) or **AI explanation**. **Save to glossary**. A **Glossary** tab: list, search, delete. | `backend/app/words.py`, `main.py` (`/define`, `/api/glossary`), `WordHelper.jsx`, `Glossary.jsx` |
| H1 | Table `ai_log`. One row for each real AI answer: time, feature, paper, provider, model. A saved answer writes no row. `GET /api/ai-log`. Settings shows the count. | `backend/app/llm.py` (`ai_context`, `_log_call`), `db.py`, `Settings.jsx` |

More:
- **Feature switches:** `Simple mode` and `Word helper and glossary` (both on by default). The AI use log has no switch, on purpose: a log that you can switch off is not an honest record.
- **Backup:** the glossary and the AI log are now in the backup file. A second import adds nothing twice.
- **Tests:** new tools `http_ai` (a fake provider behind the real `llm.py`). New files `test_simple.py`, `test_words.py`, `test_ai_log.py`, `SimpleText.test.jsx`.
- **Smoke script:** it now also prints the simple version of Method and Result and the meaning of 2 keywords.
- **README:** new sections Simple mode, Word helper and glossary, AI use log, and a privacy line.

## 2. How the server protects the facts

- **Simple text:** the new text is accepted only if all **numbers are the same**, all **names and abbreviations stay**, and the text is not much longer. Otherwise the server returns the original, with a reason.
- **Own text:** the AI never rewrites the question of the student, nor a field that the student edited.
- **The page cannot write trusted data:** the server reads the text to simplify from the card. For "Save to glossary", the page sends only the word and the paper. The server makes the explanation and the label.
- **Word helper:** "From the paper" is used only when a sentence of the PDF has a definition pattern ("X is a…", "X refers to…", "called X", "Full Name (X)" with matching first letters). A sentence that only uses the word does not count.

## 3. Test results

```
pytest -q            59 passed, 1 warning in 21.76s   (Sprint 00: 28 tests)
npm test             Test Files 3 passed (3) / Tests 13 passed (13)
npm run build        ✓ built in 8.11s
npm run e2e          5 passed (1.4m)
```

- **Truth tests:** simple text with 91.4 changed to 90 → original kept. A new number → original kept. A lost name (AUTOMA) → original kept. A rewrite in the STE check with a changed number → refused.
- **I broke the number check on purpose** (`_facts_kept` in `ste.py`). Three truth tests failed. I restored the file.
- **Saved answers:** the second `/simplify` request makes no call to the provider (test with `http_ai`).
- **AI log:** one row for each call, the right feature names (`card`, `chat`, `link`, `simplify`, `define`), no row for a saved answer.
- **CI:** the run of the branch passed: https://github.com/zarsalene/rsearch_pal/actions/runs/37946187799

## 4. Smoke test (real AI)

I used 2 public arXiv papers (Attention Is All You Need, BERT). The third paper (ResNet) could not run: the AI providers refuse its size (see section 7). The Definition of Done asks for 3 papers. This is an Owner item.

| Check | Result |
|-------|--------|
| Truth check (no wrong quote shown as verified) | OK on both papers |
| Simple Method, Attention | OK. It explains "self-attention" and "point-wise layers" in brackets. |
| Simple Result, Attention | OK. It adds "(Bilingual Evaluation Understudy)" after BLEU. The numbers 28.4 and 41.8 stay. |
| Simple Method, BERT | The server kept the original (`not_simple`): the AI text still had long sentences. |
| Simple Result, BERT | The server kept the original (`changed_fact`): the AI changed a number or a name. I did not see which. |
| Word "self-attention", "masked language model" | **AI explanation**, 1 to 3 short sentences. |
| Word "Transformer", "BERT" (first run) | **Bug found:** the helper showed a table row and the title block as "From the paper". I fixed it (section 5). |

## 5. Changes after the real-paper test

The first real papers showed 4 weak points in the word helper. I fixed them and added a test (`test_rules_from_real_papers`):
1. A table row or a title block is not a definition (the sentence must be prose with fewer than 60 words and few digits).
2. "X is the first model…" is a claim, not a definition. "the" is no more a definition cue.
3. An abbreviation matches only if the first letters of the long form are the letters of the abbreviation.
4. The text of the answer starts at the definition, not at the first use of the word.

After the fix, "Transformer" has no definition in the Attention paper (the AI explains it). "GLUE" and "NSP" show a correct sentence. "BERT" still shows the sentence "…called BERT, which stands for…", cut at the right place.

## 6. Differences from the sprint file

| Sprint file | What I did | Why |
|-------------|-----------|-----|
| `/simplify` with `{field, card_id}` | Same. I added `POST /api/simplify {text}` for the chat, the links and the mind map. `field` can also be `verdict_reason`. | A3 asks for the switch in all these places. The same check applies. |
| "Cache it in `llm_cache`" | The existing cache of `llm.py` does this. | Same result, no new code. |
| `/define` step 2 "ask the AI" | The AI also gets up to 3 sentences of the paper that use the word, as context. | A better explanation in the sense of the paper. The label stays "AI explanation". |
| `POST /api/glossary` | Body = `{term, paper_id}` only. | The page must not write a text and call it "From the paper". |
| `ai_log(id, time, feature, paper_id, provider, model)` | Same. `paper_id` can hold several ids with commas (chat, links). | One call can use more than one paper. |
| Frontend unit test "Simple switch changes the text of a field" | Test on the component `SimpleText` (6 tests). | The field uses this component. |
| "Select a word in a card or in the chat" | In the chat, the box uses the paper that is selected in the library. | The chat has no single paper. |
| (not in the file) | The opinion line "AI opinion, not from the paper" has no simple version yet. | Small. The backend supports it (`inferred_limitations`). |

## 7. Manual checklist

- [ ] **Owner:** on 3 real papers, the simple text is easier to read and keeps all numbers. (Agent: 2 papers, see section 4. The numbers stayed: the server refuses a change.)
- [ ] **Owner:** the word helper box opens in less than 3 seconds. (Agent: "From the paper" is instant, no AI call. "AI explanation" took a few seconds on Groq. I did not measure it.)
- [ ] **Owner:** the labels "From the paper" and "AI explanation" are clear.
- [ ] **Owner:** you read 3 simple cards and say "clear" (Done gate of the sprint file).
- [ ] **Owner:** Settings → Features: switch Simple mode and the Word helper off and on.
- [ ] **Owner:** run the smoke script with your key on 3 papers.

## 8. Demo steps

1. Open a hard paper. Click **Simple** in the top bar. Each field changes. Click **Show the original** on one field.
2. Select a hard word in the Method field (example: "hypothesis" in a test PDF, or "GLUE" in BERT). Read the box. Click **Save to glossary**.
3. Select a word that the paper does not define. See the label **AI explanation**.
4. Open the **Glossary** tab. Search for the word. Delete it.
5. Open **Settings**. See "AI use log: The AI helped N times…". Open Settings → Features and switch Simple mode off. The switch in the top bar goes away.

## 9. Known problems and risks

1. **Gemini model is retired** for your key (`gemini-2.5-flash` → error 404). Every request goes to Groq. Its free plan limits a request to 8000 tokens. Long papers (ResNet) fail. `gemini-3.8-flash` worked in a small test. **Decision for the owner:** change the model in Settings → AI models, or I change the default in `config.py`.
2. **The simple text is often refused with real papers** (2 of 4 tries in the smoke test). The reason is safe: a changed number or name, or long sentences. The student sees the original and a short reason. A later sprint can improve the prompt.
3. **Simple text can add an explanation of a term.** The AI wrote it. It is not from the paper. The label says "AI simplification" and the tooltip says it.
4. **Word helper in the chat** uses the paper that is selected in the library, not the paper of the answer.
5. **A paper with a table in the text** can still show a odd sentence as a definition. The checks reduce this. They are rules, not a guarantee. Look at the page chip.
6. **Quotes with special hyphens** (from Sprint 00 report) are still open.
7. Your own changes in the working copy (`graphify-out` deletions, `.gitignore`) are not part of this sprint.
