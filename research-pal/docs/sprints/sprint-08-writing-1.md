# Sprint 08 — Citations and literature review builder

| | |
|---|---|
| **Length** | 2 weeks |
| **Branch** | `sprint-08-writing-1` |
| **Depends on** | Sprint 03 (sub-questions and tags) |
| **Report ideas** | D3 Citation export, D1 Literature review builder |

## 1. Goal

The student goes from many cards to a first draft of the literature review, with correct citations and page numbers. The student writes; the AI does not write for the student.

## 2. Scope

**In:** paper metadata (authors, year, venue, DOI), BibTeX and RIS export, copy citation with page, literature review builder with outline and editor.

**Out:** Gap finder and writing coach (Sprint 09).

## 3. Development

### Backend
1. Add columns to `papers`: `authors, year, venue, doi, cite_key`. Fill them from the first page of the PDF (AI + check that each value is in the PDF text). The student can edit them.
2. Module `backend/app/cite.py`:
   - `to_bibtex(papers)`, `to_ris(papers)`.
   - `cite(paper, page, style)` → "(Smith et al., 2024, p. 3)". Styles: APA, IEEE.
3. Endpoints: `GET /api/export/bibtex`, `GET /api/export/ris`, `GET /api/papers/{pid}/cite?page=3&style=apa`.
4. Table `review_doc(id, title, updated_at)` and `review_sections(id, doc_id, position, heading, sub_question_id, text)`.
5. `POST /api/review-doc/outline`: makes one section for each sub-question. In each section, it lists the cards tagged with this sub-question, grouped by link type (same problem, same method ...). No AI text in the outline, only headings and the quotes of the cards.
6. `PUT /api/review-doc/sections/{id}`: save the text of the student.
7. `GET /api/review-doc/export?format=md|docx`: export with the citations.
8. Game: unlock the level "Author" condition: one section with ≥ 300 words written by the student.

### Frontend
1. Card page: metadata block (edit) and button "Copy citation" on each page chip.
2. Library: button "Export BibTeX / RIS".
3. New page `Write.jsx` (part 1):
   - Left: outline (drag to reorder).
   - Middle: text editor for each section.
   - Right: the cards and quotes of this section. Click a quote → insert it with the citation.
   - Word count (feeds the daily goal "words").

## 4. Tests

| Type | Test |
|------|------|
| Unit | `to_bibtex` and `to_ris`: output is valid (parse it again). |
| Unit | `cite`: APA and IEEE with 1, 2, and 3+ authors. |
| **Truth** | Fake AI returns year "2019" but the PDF says "2024" → the year is not saved, the field shows "Check". |
| API | Outline: 3 sub-questions → 3 sections with the correct cards. |
| API | Section text saved and exported to Markdown with citations. |
| API | Word count feeds the "words" goal. |
| Frontend unit | Insert a quote → citation with page in the editor. |
| E2E | Make outline → write a section → insert 2 quotes → export Markdown. |

## 5. Manual checklist

- [ ] Import the BibTeX file into Zotero → no error.
- [ ] Metadata is correct on 5 real papers (check by hand).
- [ ] The editor does not lose text on a page reload (autosave).

## 6. Done gate

Definition of Done in the [overview](README.md). The owner writes one real section of the literature review in the app.

## 7. Demo

Export BibTeX to Zotero. Make the outline. Write one section with 3 quotes. Export it.
