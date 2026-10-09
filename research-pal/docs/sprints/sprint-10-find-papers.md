# Sprint 10 — Add by DOI, import, triage

| | |
|---|---|
| **Length** | 2 weeks |
| **Branch** | `sprint-10-find-papers` |
| **Depends on** | Sprint 03 (question for triage), Sprint 08 (metadata) |
| **Report ideas** | E1 Add by DOI / arXiv / title, E3 Import Zotero / BibTeX, E4 Reading triage |

## 1. Goal

The library grows fast and the student reads the best papers first.

## 2. Scope

**In:** add a paper from DOI, arXiv link or title; import BibTeX/RIS (with PDFs if present); "To read" list with a fit score.

**Out:** Suggestions of new papers (Sprint 11).

## 3. Development

### Backend
1. Module `backend/app/sources.py` with clients for free APIs:
   - **OpenAlex** (metadata, abstract, open access link).
   - **arXiv** (PDF).
   - **Unpaywall** (free PDF from DOI; needs an email in `.env`).
   - **Semantic Scholar** (fallback).
   - Timeouts, retries and a cache for each call.
2. `POST /api/papers/from-id` with `{doi | arxiv | title}`:
   - Find metadata. Find a free PDF. If found → normal upload pipeline. If not → paper with status `no_pdf` and a "Upload the PDF" button.
3. `POST /api/import` with a `.bib` or `.ris` file (and optional Zotero folder of PDFs): match PDFs by file name or DOI. Skip papers that already exist (same DOI or title).
4. Table `to_read(id, doi, title, abstract, score, reason, added_at, status)`.
5. **Triage score:** compare the abstract with the main question and each sub-question (vectors that exist). Score 0-100, and the reason: "Fits SQ2: 'validation agent'". No AI call needed.

### Frontend
1. Library: button "Add by DOI / link / title" (one field).
2. Settings: "Import from Zotero / BibTeX".
3. New tab "To read": list sorted by score, with the reason. Buttons "Read now" (upload / fetch) and "Not useful".

## 4. Tests

| Type | Test |
|------|------|
| Unit | Each API client with **recorded** answers (no real network in CI). |
| Unit | DOI, arXiv ID and title are found in the input text correctly. |
| API | `/from-id` with a DOI that has a free PDF → paper is processed. |
| API | `/from-id` with no free PDF → status `no_pdf`. |
| API | Import a `.bib` with 10 entries, 2 already in the library → 8 added. |
| API | Network timeout → clear error, no crash. |
| Unit | Triage: an abstract about the question scores higher than an abstract about cooking. |
| E2E | Paste a DOI → paper appears → card is made. |

## 5. Manual checklist

- [ ] 10 real DOIs of the field of the owner: at least 6 get a PDF.
- [ ] Import of the real Zotero library of the owner works.
- [ ] The top 5 of the "To read" list make sense.

## 6. Done gate

Definition of Done in the [overview](README.md). The owner imports the real library.

## 7. Demo

Import a BibTeX file. Paste one DOI. Open "To read". Read the top paper first.
