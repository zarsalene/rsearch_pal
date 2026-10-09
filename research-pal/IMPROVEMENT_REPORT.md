# Research_Pal: Improvement Report

**Goal:** Make Research_Pal the best partner for a PhD student, from the first day to the defense.
**Method:** An interview of 13 questions with the product owner (9 October 2026), plus a short check of research on learning and motivation.
**Language:** ASD-STE100 Simplified Technical English, the same rule that the app uses for its AI texts.

---

## 1. Summary

Research_Pal is strong today. It reads PDFs, fills reading cards, checks each quote against the PDF, links papers, and makes mind maps. Its rule "no wrong data" is its best quality. Keep this rule in every new feature.

The app helps the student **read**. It does not yet help the student **understand deeply, find a direction, stay motivated, and write**. This report gives 40 ideas in 8 groups to close these gaps.

| # | Group | Main pain that it solves | Priority |
|---|-------|--------------------------|----------|
| A | Understand (Feynman tools) | Papers are hard and not fun | **1 (first)** |
| B | Direction (title, question, Today) | No clear question | 2 |
| C | Motivation (game system) | Low motivation | 3 |
| D | Writing | Writing is hard | 4 |
| E | Find papers | Too many papers | 5 |
| F | Plan and time | Lost in a long project | 5 |
| G | People (supervisor) | The PhD is lonely | 6 |
| H | Trust and ethics | AI risk, weak papers | All phases |

---

## 2. Who is the user

**Answer:** A PhD student at **all stages** (Question 1).

**Why it is important:** The needs change during a PhD.

| Stage | Main work | What the app must give |
|-------|-----------|------------------------|
| Year 1 | Find the topic, read a lot | Question helper, triage, Feynman tools |
| Year 2-3 | Experiments, papers | Research journal, gap finder, links |
| Final year | Thesis, defense | Literature review builder, citations, AI use statement |

**Idea 0 — Stage setting.** In Settings, the student selects the stage. The "Today" page and the quests change with the stage. Example: in Year 1 the app suggests reading quests; in the final year it suggests writing quests.

---

## 3. The pains (Question 2)

The owner selected all pains:

1. Too many papers. The student forgets what each paper said.
2. No clear research question.
3. Writing is hard.
4. Low motivation.
5. **Added by the owner:** papers are hard to understand, and research is not fun.

Each group below solves one or more of these pains.

---

## 4. Group A — Understand (Priority 1)

**Why first:** These tools use the cards, quotes and passages that the app already has. So they are fast to build and give value on day one. They also attack pain 5 (hard and not fun), which the owner added.

**Research base:**
- **Feynman technique:** "If you cannot explain it in simple words, you do not understand it." Explaining shows the gaps in your knowledge.
- **Retrieval practice:** to answer a question from memory makes memory stronger than to read again (Roediger and Karpicke, 2006, the "testing effect").
- **Self-explanation:** a student who explains a text to himself or herself learns more than a student who only reads it.

### A1. "Explain it to me" (Feynman mode)
- **What:** On a card, the student writes the main idea of the paper in simple words, with no copy from the PDF. The AI compares the text with the PDF. It shows: correct parts (green), missing parts (orange), wrong parts (red with the correct quote and page).
- **Why:** This is the core of the Feynman method. The student finds his or her own gaps.
- **How in the app:** New button on the card page. Use the passages from `vectors.py` and the quote check that exists. Save each attempt, so the student sees progress.

### A2. "Explain like I am 12"
- **What:** A button on each card field gives a simple version, with one example and one analogy from daily life.
- **Why:** A simple picture first makes the technical version easier to learn after.
- **How:** The text must still keep the technical terms in a second line ("The paper calls this ..."). Label the analogy as **AI suggestion**, because an analogy is not in the PDF.

### A3. Simplified answers everywhere
- **What:** A switch "Simple / Expert" for the chat, links and mind map.
- **Why:** The owner asked for simplified answers in general.
- **How:** `ste.py` already checks the AI text with ASD-STE100 rules. Add a "simple level" with a lower word limit (example: 12 words in a sentence) and a rule to explain each technical term.

### A4. Word helper
- **What:** The student selects a hard word, formula or abbreviation. A small box explains it in 1-3 sentences, and shows where the paper defines it (page link).
- **Why:** Unknown words stop the reading. A fast answer keeps the flow.
- **How:** First search the paper for the definition (search that exists). Only if not found, ask the AI and label it **AI explanation**. Keep a personal glossary of all looked-up words; the glossary feeds the spaced review (C4).

### A5. "Ask me questions" (quiz)
- **What:** After the card is ready, the AI asks 3-5 short questions about the paper. A wrong answer shows the correct quote and page.
- **Why:** Retrieval practice. It also makes reading active and more fun.
- **How:** Make questions only from verified quotes. A question without a verified quote is not shown. The questions go into the spaced review deck (C4).

---

## 5. Group B — Direction (Priority 2)

### B1. Thesis subject title
- **What:** The thesis title shows at the top of each page. The student can change it at any time. The app keeps each old version with its date.
- **Why:** The owner asked for it. The title reminds the student of the goal each day. The history shows how the thinking grew; this helps in the defense ("Why did you change your focus?").
- **How:** New table `project(title, question, sub_questions, stage, updated_at)` and a table `project_history`.

### B2. Research question helper
- **What:** A guided process in steps:
  1. Write a first question freely.
  2. The app checks it with the **FINER** rule: Feasible, Interesting, Novel, Ethical, Relevant. It also checks if the question is too wide or too vague.
  3. The app suggests 3 narrower versions. The student chooses or edits; the AI does not choose.
  4. The student cuts the main question into 3-5 sub-questions.
- **Why:** The owner chose "Help me find it" (Question 3). A clear question is the base of the full PhD. FINER is a common rule taught in research methods courses.
- **How:** Each paper and each card can be tagged with a sub-question. Then the app can show "Sub-question 2 has only 1 paper" (link to the gap finder, D2). Keep the history of the question (as B1).

### B3. "Today" dashboard (home page)
- **What:** The first page shows:
  - The thesis title and the main question.
  - The 3 tasks of today.
  - The review cards due today (C4).
  - The level, the streak, and the current quest (Group C).
  - One "next best action". Example: "Card 'Smith 2024' has no Limitation. Find it?"
- **Why:** The owner chose this (Question 12). A clear start removes the question "What must I do now?", which is a big cause of lost time.
- **How:** New React page `Today.jsx`. The library stays one click away.

---

## 6. Group C — Motivation and game system (Priority 3)

The owner asked: "Be creative. Search for the best way to make games." This section is the result.

### What research says

| Finding | Source | Rule for the design |
|---------|--------|---------------------|
| Gamification gives a small but real gain for learning (Hedges' g = 0.26). | [Meta-analysis, ETR&D 2023](https://link.springer.com/doi/10.1007/s11423-023-10337-7) | Use it, but do not expect magic. |
| Games work when they give 3 feelings: competence ("I can"), autonomy ("I choose"), relatedness ("I am not alone"). This is Self-Determination Theory. | [Sailer and Homner, 2020](https://link.springer.com/article/10.1007/S10648-019-09498-W) | Each game part must give one of the 3 feelings. |
| Points, badges and leaderboards can support or damage these feelings. | [DiGRA review](https://dl.digra.org/index.php/dl/article/download/2773/2757/2817) | Points must show real skill. No public leaderboard. |
| For PhD writing, a gamified app made students feel better about writing, but it did not always add words. | [UGA dissertation](https://openscholar.uga.edu/record/18013/files/oshea_brian_p_201905_phd.pdf) | The game is for joy and habit. Measure real output also. |
| Graduate writers use points and "achievements" to make hard work feel lighter. | [Harvard GSAS](https://gsas.harvard.edu/news/gamifying-research-and-writing), [UCR](https://gsrc.ucr.edu/blog/2022/08/10/level-your-writing-3-ways-gamify-your-writing-practice) | Let the student set his or her own rewards. |

**Golden rule of the game:** *Points come only from real research work that the app can verify.* No point for a click. No point for AI work that the student did not check. This rule fits the "no wrong data" rule of the app.

### C1. The PhD Expedition (progress map)
- **What:** The PhD is a map of a world with 6 regions:
  1. **Question Peak** — title, question, sub-questions.
  2. **Literature Forest** — papers read and understood.
  3. **Method Workshop** — methods and research journal.
  4. **Data Mines** — experiments and results.
  5. **Writing Coast** — chapters and papers.
  6. **Defense Castle** — thesis ready, defense prepared.
- Each region fills with color as the work is done. The student sees the full road, and where he or she is.
- **Why:** A long project with no visible progress kills motivation. The map gives **competence** and a clear direction.

### C2. Skill levels (not only points)
- **What:** 6 levels that show real research skills:

| Level | Name | How to reach it (examples) |
|-------|------|----------------------------|
| 1 | Explorer | 5 cards with checked quotes |
| 2 | Reader | 3 papers passed in Feynman mode (A1) |
| 3 | Critic | 10 critical reading checks (H2) |
| 4 | Connector | 10 explained links + 1 gap found (D2) |
| 5 | Author | 1 literature review section written |
| 6 | Doctor | Thesis outline complete, defense practice done |

- **Why:** A level name tells the student what he or she can now do. This is **competence**, not only a score.

### C3. Quests (with choice)
- **What:** Each week, the app offers **3 quests**. The student chooses one or two. Examples:
  - "Find 3 papers that disagree on the same point."
  - "Explain your hardest paper to a 12-year-old (A2 + A1)."
  - "Write the gap of your field in 5 lines."
  - "Send your supervisor pack this week."
- **Boss fights:** The student marks a very hard paper as a "Boss". To defeat it: pass the quiz (A5) and the Feynman check (A1). The reward is a special badge with the paper name.
- **Why:** The choice gives **autonomy**. The quests change with the PhD stage (Idea 0).

### C4. Knowledge Garden (spaced review)
- **What:** Each card, quiz question and glossary word is a plant. A short review "waters" the plant. A plant that is not reviewed for a long time looks dry (it does not die). The app shows the cards due today.
- **Why:** Without review, we forget most of what we read in a few weeks. Spaced review is one of the best proven ways to remember.
- **How:** Use the open **FSRS** algorithm (the algorithm of Anki) to set the next review date. Review items come from A4 and A5.

### C5. Kind streaks
- **What:** A streak counts the days with real work. The student gets 2 "rest tokens" each week. A rest day does not break the streak. Weekends can be off by default.
- **Why:** A normal streak makes guilt and stress. Burnout is a real risk in a PhD. A kind streak keeps the habit with no guilt.

### C6. Daily goals
- **What:** Small goals that the student sets. Example: "Read 1 paper, write 200 words, 1 focus session."
- **Why:** Small goals are easy to start. Each small success gives energy for the next.

### C7. Wins journal
- **What:** Each day, the student writes one small win (one line). On a bad day, the app shows past wins. The wins go into the supervisor pack (G1).
- **Why:** PhD students often feel that they do nothing. A list of wins shows the truth.

### C8. Badges for milestones only
- **What:** Few badges, and only for important moments: "First gap found", "First paper submitted", "100 cards", "Boss defeated", "1 year of PhD".
- **Why:** Many small badges lose value. A few rare badges feel real.

### C9. Personal records, not leaderboards
- **What:** Compare the student with his or her own past: "This month you wrote 30% more than last month." No public ranking.
- **Why:** A ranking against other people causes stress and damages motivation.

### C10. Own rewards
- **What:** The student writes his or her own rewards. Example: "Level 3 = a dinner out." The app reminds the student when the reward is earned.
- **Why:** A personal reward has more value than an app badge (Harvard GSAS idea).

### C11. Study companion (optional)
- **What:** A small character ("Duck") lives in the app. The student explains ideas to it (the "rubber duck" method). The Duck reacts to progress and gives kind messages on bad days.
- **Why:** This makes the Feynman method fun, and it gives a small feeling of company (**relatedness**).

---

## 7. Group D — Writing (Priority 4)

**Rule:** The AI helps the student write. It does **not** write for the student. This protects the learning and the academic honesty of the student.

### D1. Literature review builder
- **What:** The student groups cards by sub-question or by theme. The app makes an outline. Each section shows the checked quotes and page numbers of its papers. The student writes the text.
- **Why:** The jump from many notes to one text is the hardest step. An outline with sources removes the "blank page" fear.

### D2. Gap finder
- **What:** The app compares the cards of a group and shows 3 lists: where papers **agree**, where they **disagree**, and what **nobody did yet** (the gap). Each point has quotes from each paper.
- **Why:** A PhD must add something new. A clear gap is the base of the contribution.
- **How:** Use the link types of `links.py` (same problem, same method, can be compared). The gap is always labelled **AI opinion**; the student must confirm it.

### D3. Citation export
- **What:** Export BibTeX and Zotero (RIS). Copy a citation with the page number in one click.
- **Why:** Citations take time and errors are common. A correct citation with page is a sign of quality.

### D4. Writing coach
- **What:** The student pastes a paragraph. The AI gives feedback on 4 points: Is it clear? Is the argument logical? Does each claim have a source? Is the style simple? The AI does not rewrite the paragraph.
- **Why:** Feedback makes the student a better writer. A rewrite makes the student dependent.
- **How:** Reuse the rules of `ste.py` for the style check. Check each citation in the paragraph against the library.

---

## 8. Group E — Find papers (Priority 5)

### E1. Add by DOI, arXiv link or title
- **What:** Paste a DOI or a title. The app finds the data and the free PDF.
- **Why:** Upload one by one is slow.
- **How:** Free APIs: OpenAlex, Semantic Scholar, arXiv, Unpaywall.

### E2. Suggest next papers
- **What:** From the cards, the app suggests papers that cite them, or that they cite. Each suggestion has a reason ("Cited by 4 of your papers").
- **Why:** This is the "snowball" method that researchers use, but done fast.

### E3. Import Zotero / BibTeX
- **What:** Bring the existing library in one step.
- **Why:** Most students already have a library. A new app must not ask them to start again.

### E4. Reading triage
- **What:** A "To read" list. Each paper gets a fast score: how much it fits the main question and the sub-questions. The student reads the best first.
- **Why:** There are always more papers than time. Triage protects the time of the student.
- **How:** Compare the abstract with the question (vector search that exists). Show the reason for the score.

---

## 9. Group F — Plan and time (Priority 5)

### F1. PhD timeline
- **What:** Big milestones (proposal, first paper, thesis, defense) with dates. Each milestone is cut into weekly tasks.
- **Why:** A big goal with no small steps causes delay. Small steps make the road clear.

### F2. Weekly review
- **What:** Each Friday, 5 short questions: What did I finish? Where am I blocked? What did I learn? What is next week's goal? How do I feel?
- **Why:** A short weekly stop keeps the direction. The answers feed the supervisor pack (G1).

### F3. Focus timer
- **What:** A Pomodoro timer (example: 25 minutes work, 5 minutes rest), linked to a task or a paper. The app counts the real deep-work time.
- **Why:** Deep work is the real currency of research. The timer protects it and gives honest data for the game (C2, C6).

### F4. Research journal
- **What:** A dated log of ideas, experiments and decisions, with links to cards.
- **Why:** In the final year, the student must explain each decision in the method chapter and in the defense. The journal keeps this memory.

### F5. Other planning idea
- The owner selected "Other" without detail. **Open point:** ask the owner for this idea.

---

## 10. Group G — People (Priority 6)

### G1. Supervisor meeting pack
- **What:** One click makes a short report: what I did, what I found, where I am stuck, my questions. It uses the weekly review (F2), the wins (C7) and the journal (F4).
- **Why:** Good meetings need preparation. A clear pack makes short meetings useful, and the supervisor sees the progress.

### G2. Ready email (added by the owner)
- **What:** The app makes a ready email to the supervisor from the pack. The student edits it and sends it from his or her own email program (a "mailto" link or copy button).
- **Why:** Many students delay contact with the supervisor because the email is hard to write. A ready draft removes this block.
- **How:** The app does not send the email itself. The student always reads and sends it.

---

## 11. Group H — Trust and ethics (all phases)

### H1. AI use log
- **What:** The app records each place where the AI helped (card, simple version, gap, writing feedback). The student can export a clear **AI use statement** for the thesis.
- **Why:** Many universities now ask students to declare their use of AI. A log makes this easy and honest.
- **How:** New table `ai_log(time, feature, paper_id, model)`. The `llm.py` module already sees each AI call.

### H2. Critical reading check
- **What:** For each paper: sample size, risk of bias, can I reproduce it, are the claims supported by the data? The result is a quality note with reasons, and a quote for each reason.
- **Why:** A PhD student must judge papers, not only summarize them. This skill is the step from "Reader" to "Critic" (C2).
- **How:** Use known checklists (example: CASP checklists) as a base. The quality note is an **AI opinion** and the student can change it.

---

## 12. Build plan

The detailed plan is in 13 sprints. Each sprint is a separate project with development, tests and a done gate: see [docs/sprints/README.md](docs/sprints/README.md).

| Phase | Content | Why in this order |
|-------|---------|-------------------|
| **1. Understand** | A1-A5, H1 (AI log from the start) | Uses the data that exists. Fast value. The AI log must start early to record all uses. |
| **2. Direction** | B1-B3, Idea 0 | Gives the student a goal and a home page. The game needs these. |
| **3. Motivation** | C1-C11, F3 | The game connects all the other tools. |
| **4. Writing** | D1-D4, H2 | Needs many cards and sub-questions to work well. |
| **5. Papers and plan** | E1-E4, F1, F2, F4 | Makes the library grow faster and the work more regular. |
| **6. People** | G1, G2 | Uses data from the weekly review, wins and journal. |

### New data (summary)
- `project`, `project_history` — title, question, sub-questions, stage.
- `review_items` — quiz questions, glossary words, FSRS dates.
- `explanations` — Feynman attempts and scores.
- `goals`, `quests`, `xp_events`, `wins`, `streaks`.
- `journal`, `milestones`, `weekly_reviews`.
- `ai_log`.

### New pages (summary)
- `Today.jsx` (home), `Journey.jsx` (map and levels), `Review.jsx` (garden), `Write.jsx` (review builder, gap finder, coach), `Plan.jsx` (timeline, weekly review, journal), `Supervisor.jsx` (pack and email).

---

## 13. Rules for all new features

1. **No wrong data.** Each claim has a verified quote, or it has a clear label (AI suggestion, AI opinion).
2. **The student thinks; the AI helps.** The AI checks, asks and gives feedback. It does not write the thesis.
3. **Simple first.** All AI text follows ASD-STE100 (`ste.py`). The "Simple" mode goes further.
4. **Points only for real work.** No point for a click or for unchecked AI work.
5. **Be kind.** No guilt, no public ranking, rest days are normal.
6. **Privacy.** Unpublished ideas are private by default.

---

## 14. Open points

1. Question 10: the owner selected "Other" with no text. Ask for this planning idea.
2. Decide if the Study companion (C11) is in phase 3 or later.
3. Decide how to measure success. Proposal: papers understood (A1 passed), words written each week, review cards kept, and a monthly question to the student: "How do you feel about your PhD?" (1-5).

---

## Sources

- Meta-analysis of gamification in learning, Educational Technology Research and Development, 2023: https://link.springer.com/doi/10.1007/s11423-023-10337-7
- Sailer and Homner, The gamification of learning: a meta-analysis, 2020: https://link.springer.com/article/10.1007/S10648-019-09498-W
- Reward mechanisms and psychological needs, DiGRA: https://dl.digra.org/index.php/dl/article/download/2773/2757/2817
- O'Shea, gamified writing app dissertation, University of Georgia, 2019: https://openscholar.uga.edu/record/18013/files/oshea_brian_p_201905_phd.pdf
- Harvard GSAS, Gamifying research and writing: https://gsas.harvard.edu/news/gamifying-research-and-writing
- UC Riverside GSRC, Level up your writing: https://gsrc.ucr.edu/blog/2022/08/10/level-your-writing-3-ways-gamify-your-writing-practice
- Roediger and Karpicke, 2006, Test-enhanced learning (retrieval practice). General knowledge, not checked online in this session.
- FSRS spaced repetition algorithm (open source, used by Anki). General knowledge, not checked online in this session.
