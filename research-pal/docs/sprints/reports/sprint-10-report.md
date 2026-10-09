# Sprint 10 report: Add by DOI, import, triage

| | |
|---|---|
| **Branch** | `sprint-10-find-papers` (on top of `main` at `v0.09.0`) |
| **Ideas** | E1 Add by DOI / arXiv / title, E3 Import Zotero / BibTeX, E4 Reading triage |
| **Status** | Ready for the gate. The manual checks with real DOIs and the real Zotero library are for the owner (section 4). |

## 1. What I built

| Part | What it does | Files |
|------|--------------|-------|
| Sources | Clients for OpenAlex, arXiv, Unpaywall and Semantic Scholar (fallback). Timeout 15 s, 2 retries, a cache of 1 hour, a clear message for each failure. A page that is not a PDF (a login page) is refused. | `backend/app/sources.py` |
| Add by DOI | `POST /api/papers/from-id` with a DOI, an arXiv link or a title. With a free PDF: the normal reading. Without: status `no_pdf` and `POST /api/papers/{id}/pdf` to upload. A paper that exists is not added again. | `main.py` |
| Metadata check | Source metadata has the name of its source. After the PDF is read, each value is checked in the PDF. An unconfirmed value stays in the list "Check". A PDF with another DOI than the one asked is flagged. | `main.py` (`apply_source_meta`) |
| Import | `POST /api/import/bib` (BibTeX or RIS, with optional PDFs). A PDF is matched by file name, DOI or title. No PDF: the entry goes to To read. A paper that exists is skipped. | `backend/app/bibimport.py` |
| Triage | A score of 0 to 100 from the embeddings and the shared words, and a reason with the words. No AI. Scores are made again when the question changes. | `backend/app/triage.py` |
| To read | Table `to_read`, endpoints to list, mark "not useful", "Read now" and upload. | `db.py`, `main.py` |
| UI | "Add by DOI, link or title" in the library, "Import from Zotero or BibTeX" in Settings, the **To read** tab, "Upload the PDF" on a paper without PDF. | `ToRead.jsx`, `Library.jsx`, `Settings.jsx`, `CardView.jsx` |
| Switch, backup | `findpapers`. The To read list is in the backup. | `features.py`, `main.py` |

## 2. Test results

```
pytest -q            266 passed   (main at v0.09.0: 239 tests; test_sources.py: 27 tests, all with recorded answers)
npm test             ToRead.test.jsx: 4 tests
npm run build        built
npm run e2e          17 passed (the fake server serves recorded answers from the sources)
```

## 3. Rules kept

- No network in the tests. `sources.fetch` is replaced by recorded answers (`tests/recorded_sources.py`).
- Truth: a value from a source that the PDF does not show is marked "Check". It is never shown as checked.
- A source gives metadata, not claims. The card still comes from the PDF with checked quotes.
- Free APIs only. Unpaywall needs `CONTACT_EMAIL`. Without it, the app uses the other sources.
- The score is not AI. The reason shows the words, so the student can check it.

## 4. Open points for the owner (manual checklist)

- [ ] Try 10 real DOIs of your field. Tell me how many get a PDF (the plan wants at least 6).
- [ ] Import your real Zotero library (BibTeX plus the files folder).
- [ ] Look at the top 5 of the To read list. Do they make sense?
- Set `CONTACT_EMAIL` in `backend/.env` (and on Render) to get more free PDFs.
