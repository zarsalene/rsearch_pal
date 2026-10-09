# Sprint 09 — Gap finder, writing coach, critical reading

| | |
|---|---|
| **Length** | 2 weeks |
| **Branch** | `sprint-09-writing-2` |
| **Depends on** | Sprint 08 (review builder) |
| **Report ideas** | D2 Gap finder, D4 Writing coach, H2 Critical reading check |

## 1. Goal

The student finds the gap of the field, judges the quality of papers, and gets feedback to write better. The AI gives feedback; it does not rewrite.

## 2. Scope

**In:** D2, D4, H2. Unlock the levels "Critic" and "Connector".

**Out:** Nothing more in writing.

## 3. Development

### Backend
1. **Gap finder** `POST /api/gaps` with `{sub_question_id}` or `{paper_ids}`:
   - Uses the cards and the saved links (`links.py`).
   - Returns 3 lists: `agree`, `disagree`, `gap`. Each `agree`/`disagree` point has one verified quote from each paper.
   - Each `gap` point has the label **AI opinion** and a reason. The student can mark it "confirmed" or "not a gap".
   - Table `gaps(id, sub_question_id, text, reason, status, created_at)`.
2. **Writing coach** `POST /api/coach` with `{text}`:
   - 4 checks: clear, logical, sourced, simple style.
   - "Sourced": find each claim without a citation. Check each citation against the library (paper exists, page exists, quote is on this page).
   - "Simple style": reuse `ste.py` rules (long sentences, passive voice, filler words). No AI needed for this part.
   - Returns comments with the position in the text. **No rewritten text.** The server refuses an AI answer that contains a full rewrite (more than 15 words copied in a row of new text).
3. **Critical reading** `POST /api/papers/{pid}/critique`:
   - Checklist (based on CASP): question clear? method fits? sample size? bias risk? results support the claims? can it be reproduced (data, code)?
   - Each answer: `yes`, `no`, `unclear`, with a verified quote. No quote → `unclear`.
   - Label **AI opinion**. The student can change each answer.
   - Table `critiques(paper_id, json, edited, created_at)`.
4. Game: Critic = 10 critiques edited or confirmed by the student. Connector = 10 explained links + 1 confirmed gap.

### Frontend
1. `Write.jsx` (part 2): tab "Gaps" with 3 columns (agree / disagree / gap). Button "Use this gap" → adds it to the outline.
2. `Write.jsx`: button "Coach" in the editor. Comments show at the side, like a review in a word processor.
3. Card page: new tab "Quality" with the checklist.

## 4. Tests

| Type | Test |
|------|------|
| **Truth** | Gap finder: an `agree` point with a false quote is dropped. |
| **Truth** | Critique: an answer with a false quote becomes `unclear`. |
| **Truth** | Coach: a citation to page 9 of a paper with 4 pages → comment "page not found". |
| Unit | Coach style check: long sentence and filler word found without AI. |
| Unit | Coach answer with a full rewrite → refused. |
| API | Gap marked "confirmed" → Connector condition counts it. |
| API | 10 edited critiques → Critic level unlocks. |
| E2E | Run gaps on a sub-question → use a gap → see it in the outline. |
| E2E | Write a paragraph with no citation → coach marks the claim. |

## 5. Manual checklist

- [ ] On a real group of 5 papers, the gaps make sense to the owner.
- [ ] The coach comments are short, kind and useful.
- [ ] The critique on a real weak paper finds at least one real weak point.

## 6. Done gate

Definition of Done in the [overview](README.md). The owner confirms one real gap for the thesis.

## 7. Demo

Run the gap finder on one sub-question. Confirm a gap. Write about it. Run the coach. Fix the comments. Show the Critic level.
