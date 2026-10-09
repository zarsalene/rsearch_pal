# Sprint 08 report: Citations and literature review builder

| | |
|---|---|
| **Branch** | `sprint-08-writing-1` (on top of `main` at `v0.07.0`) |
| **Ideas** | D3 Citation export, D1 Literature review builder |
| **Status** | Ready for the gate. |

## 1. What I built

| Part | What it does | Files |
|------|--------------|-------|
| Metadata | New columns on `papers`: `authors, year, venue, doi, cite_key` (and `meta_check`, `meta_source`). The DOI comes from a rule. The AI proposes authors, year and venue. The server keeps a value only if the first pages of the PDF have it. A value that fails is not saved, and the field shows "Check". The student can edit. A student edit is never replaced. | `backend/app/metadata.py` |
| Citations | BibTeX, RIS, a citation with page in APA or IEEE, a reference list. | `backend/app/cite.py` |
| Endpoints | `POST /api/papers/{pid}/meta/extract`, `PUT /api/papers/{pid}/meta`, `GET /api/export/bibtex`, `GET /api/export/ris`, `GET /api/papers/{pid}/cite?page=&style=`. | `main.py` |
| Review builder | Tables `review_doc`, `review_sections`, `writing_log`. Outline with one section for each sub-question (headings only), the cards of each section grouped by link type with their checked quotes, a saved text, order, add, delete. A check that finds changed quotes. Export to Markdown and Word. | `backend/app/writing.py`, `db.py`, `main.py` |
| Words and game | Words that the student wrote (quote lines excluded) feed the daily goal "words". A section of 300 words or more is the skill for the level **Author**, for the map region Writing Coast and for the quest "A first section". | `db.py`, `game.py`, `journey.py`, `quests.py` |
| UI | Metadata block and "Copy citation" on the card, BibTeX and RIS buttons in the library, the **Write** tab (outline, editor with autosave and a draft in the browser, cards and quotes with Insert, export). | `MetaBlock.jsx`, `Write.jsx`, `CardView.jsx`, `Library.jsx`, `Today.jsx` |
| Switches | `cite`, `litreview`. | `features.py` |
| Backup | Metadata and the review document are in the backup. | `main.py` |

## 2. Test results

```
pytest -q            208 passed   (Sprint 07: 185 tests)
npm test             Write.test.jsx 7 passed; the other files passed before this sprint
npm run build        built
npm run e2e          14 passed
```

- **Unit:** BibTeX and RIS are parsed again and valid (special characters are escaped, two papers with one key get two keys). APA with 1, 2 and 3 or more authors, IEEE, missing data.
- **Truth:** the fake AI says year 2019, the PDF says 2024 → the year is not saved, the field shows "Check". An author that is not in the PDF is dropped. A venue that is not in the PDF is not saved. A quote that the student changed by hand is marked "not in your PDFs".
- **API:** outline with 3 sub-questions gives 3 sections with the correct cards, with no AI call. Grouping by link type. A section text is saved and exported to Markdown and Word with citations and references. The words feed the goal. 300 words give the level skill.
- **Frontend unit:** insert a quote → the citation with the page is in the editor. Autosave after a pause. A draft comes back after a reload.
- **E2E:** fill the metadata → export BibTeX → make the outline → write → insert 2 quotes with citations → autosave → reload keeps the text → export Markdown.
- **CI:** see section 6.

## 3. Differences from the sprint file

| Sprint file | What I did | Why |
|-------------|-----------|-----|
| "Fill from the first page of the PDF (AI + check)" | Same, with a button ("Fill from the PDF"), not at each upload. The DOI is found by a rule, not by the AI. | No new AI call at each upload. |
| `GET /api/review-doc/export?format=md|docx` | Same, plus `style=apa|ieee`. Word needs the package `python-docx` (added to `requirements.txt`). | |
| "Drag to reorder" | Drag and drop, and up/down buttons. | Keyboard users need buttons. |
| "Section ≥ 300 words" | Words outside quote lines. | The quotes are not words of the student. |
| The outline "grouped by link type" | A paper goes to the group of its strongest saved link to another paper of the section. A paper with no link goes to "Other". | One card cannot be in two groups. |
| Feature names | `cite`, `litreview`. The quest "A first section" unlocks with `litreview`. | Sprint 07 prepared it. |
| Map region "Writing Coast" and the quest | They read `review_sections` now (sections of 300 words or more). | Replaces the stub of Sprint 07. |

## 4. Manual checklist

- [ ] **Owner:** import the BibTeX file into Zotero → no error.
- [ ] **Owner:** the metadata is correct on 5 real papers (check by hand).
- [ ] **Owner:** the editor does not lose text on a page reload (a test checks this; try it with your own text).
- [ ] **Owner:** you write one real section of your literature review in the app (gate of the sprint file).

## 5. Known problems and risks

1. **The metadata AI is not run on real papers by me.** The real-paper smoke test was not run in this sprint: the AI providers refuse long papers (known limit). The truth rule works with the fake AI. Check 5 papers by hand.
2. **A year that is on the first page but is not the year of the paper** (for example a copyright year) can pass the check. The student must look at the "Check" and the value.
3. **Author names with a particle** ("van Dijk") can be put in the wrong order. Edit the field.
4. **The check of quotes** looks for the quote text (without the citation at the end) in all your PDFs. A quote of fewer than 3 words is always "not found".
5. **IEEE numbers** follow the order of the library. If you delete a paper, the numbers change.
6. **Word export** uses the default style of the `python-docx` package. It is plain.

## 6. CI result

(see the run of the branch on GitHub)
