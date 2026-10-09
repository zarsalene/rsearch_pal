# Research_Pal

**Live app:** https://rsearch-pal-7tor.vercel.app/ &nbsp;|&nbsp; **API:** https://research-pal-api.onrender.com/api/health &nbsp;|&nbsp; **Code:** https://github.com/zarsalene/rsearch_pal

An AI app that reads your research papers and fills a reading card for each one:
**My question, Problem, Method, Result, Limitation, Use.**
It links the cards together and lets you search all your PDFs.

## The most important rule: no wrong data

- The AI must give a quote from the PDF for each claim (Problem, Method, Result, Limitation).
- The server checks each quote against the real text of the PDF. A quote that is not in the PDF is marked and refused.
- A claim without a verified quote is **hidden**. You can open the draft if you want, but it shows in red.
- Each number in Result and Method must appear in the PDF. A missing number gives the warning "Check the numbers".
- "Use", "My question" (when you give none) and the AI opinion on limitations are labelled **AI suggestion** or **AI opinion**.
- Search gives you passages of your own PDFs with the page number. The AI does not write them.

## Chat

The **Chat** tab lets you ask questions about the papers that you select (up to 10). The server finds the best passages of those papers and sends only them to the AI.
The same quote check applies: each answer shows quotes with page numbers, and the server hides or flags a quote that is not in the PDF.
Click **Add to the card** under an answer to save it as a note on the card of a paper. Only quotes that the server can find in the PDF are saved. A new reading of the paper keeps your notes.

## Links and mind map

- **Links tab:** click a line, or "What links them?", and the AI explains the link: the type of link (same problem, same method, same data, builds on, can be compared, complements), what the two papers share, and how they differ. The server checks each quote in both PDFs. The explanation is saved for the pair, so the AI is called only one time for each pair. "Explain again" makes a new one.
- **Mind map:** on a card, click "Make the mind map". The AI splits the paper into its parts (problem, method and its components, data, results, limitations). Each part is a small card with a short explanation and a checked quote. A part without a found quote shows no explanation. A new reading of the paper keeps the map.

The AI can still choose a wrong quote or read a table badly. Always click the page chip (p. 3) and look at the PDF for numbers you will cite.

## Focus topic

Write a topic (example: "the validation agent") when you add a paper, or on the card page at any time.

- The server finds the passages of the paper about this topic (by meaning and by exact words). These passages go to the AI first.
- The AI writes Problem, Method, Result and Limitation about this topic only. A new **Focus** block shows what the paper says about it.
- The same quote check applies. A claim without a verified quote is hidden.
- Clear the topic to read the whole paper again.

## More than one card for one paper

Open a paper, then click **New card** in the tabs above the card. Write a focus topic (example: "the dataset"). The server makes a second card from the text it already saved. There is no new upload.
Each card has its own focus, quotes, edits and mind map. A paper can have 13 cards at most. Search, links and the chat still use the first card of each paper.

## Thesis title and question helper

- **Title bar:** a thin bar under the top bar shows your thesis title and main question. Click it to edit. On a small screen it shows the title only.
- **Thesis tab:** the question helper has four steps.
  1. Write your question.
  2. Read the FINER check: Feasible, Interesting, Novel, Ethical, Relevant. The AI also says if the question is too wide or too vague.
  3. Choose one of 3 narrower versions, or keep your own. Edit the text, then save.
  4. Make 3 to 5 sub-questions. Write them yourself, or ask for AI suggestions and add the ones you like.
- **The AI only suggests.** It saves nothing. Each AI text has a label: **AI suggestion** or **AI opinion**. If your question is good, the helper says so and does not force a change.
- **History:** each change of the title or the question is kept. The Thesis tab shows them in a timeline.
- **Tags and coverage:** on a card page, click the chips SQ1, SQ2 ... to link the card to sub-questions. The library has the same chips for the selected paper. The Thesis tab shows how many papers help each sub-question: no paper, one paper (orange), two papers or more (green).
- **PhD stage:** Settings → PhD stage (Year 1, Year 2-3, Final year).
- **Backup:** the backup file now holds the title, the question, the stage, the sub-questions and the tags. A restore fills only empty fields. It never replaces what you wrote.
- **Switch:** Settings → Features → Thesis direction. When it is off, the bar, the tab, the chips and the calls of the server go away. Your data stays. The question stays in Settings → Your research question.
## Simple mode

The switch **Expert / Simple** is in the top bar. The browser remembers your choice.

- In Simple mode, each text that the AI wrote shows a simple version: the card fields, the verdict, the chat answers, the link explanations and the mind map.
- The simple version has sentences of 12 words at most. It explains each hard term in a short sentence and keeps the term in brackets.
- The server checks the simple version. If a **number** or a **name** is different, the server **keeps the original text** and tells you why.
- A label **AI simplification** shows on each simple text. The AI can add a short explanation of a term. This explanation is not from the paper. The quotes and the page numbers do not change.
- Click **Show the original** to read the first text again.
- The AI never rewrites a text that you wrote or edited.

## Word helper and glossary

Select a word or a short term in a card or in the chat. A small box opens.

- **From the paper:** the server found a sentence in the PDF that defines the word. You see this sentence and its page. The AI did not write it.
- **AI explanation:** the paper has no definition. The AI explains the word. This text is not from the paper.
- Click **Save to glossary** to keep the word. The **Glossary** tab lists your words. You can search and delete them. The backup file holds your glossary.
- The server makes the text again when you save a word. The page cannot send its own text.

## Understand: explain, like I am 12, quiz

Open a card and click **Understand**. There are three parts. Each part has a switch in Settings → Features.

- **Explain it to me.** Write the main idea of the paper in your own words. Do not copy from the PDF. The AI marks each sentence: **Correct** (green), **Partly correct** (orange), **Wrong** (red), **Not in the paper** or **Cannot check** (gray). Click a sentence to see the quote and the page.
  - The server checks each quote in the PDF. A mark without a quote that the server finds becomes **Cannot check**.
  - The server also checks the numbers. A number that is not in the paper makes the sentence **Wrong**, even if the AI said "correct".
  - The app lists the main points of the card that you did not mention. It gives a score from 0 to 100 and a kind message. It saves each attempt, so you see your progress.
  - The AI never writes the explanation for you.
- **Like I am 12.** Choose one part of the card. You get a simple text, one example and one analogy. The example and the analogy have the label **AI suggestion**. They are not from the paper. The server keeps no simple text that changes a number or a name.
- **Quiz me.** The AI asks 3 to 5 questions. Each question has a quote from the PDF as its source. The server drops a question without a verified quote. You answer from memory. Then the app shows the correct answer, the quote and the page. The questions are saved. A later sprint will use them for the spaced review. Words that you save in the glossary are saved in the same way.

The backup file holds your attempts and your questions.

## Today page

**Today** is the first page after you sign in. It uses no AI, so it opens fast.

- **Title and question:** your thesis title and question stay at the top.
- **Next best action:** one big button. The server picks it with simple rules, in this order:
  1. A card has a field that the AI did not find → "Search the paper again".
  2. A sub-question has 0 or 1 paper → "Find a paper for SQ2".
  3. A paper has no explanation of yours → "Explain this paper in your own words".
  4. Else → "Write your win of the day". When you wrote it, the page says that you did enough and that rest is part of the work.
  - With no paper, the action is "Add your first paper".
- **Goals of today:** small goals that you write. Check them when you finish. Three are enough.
- **Focus timer:** 25 minutes of focus and 5 minutes of rest. You can change both. You can link a session to a goal or to a paper. The timer uses the clock, so it is right when the tab is in the background. The server counts the real minutes of each session. The timer asks for no sound unless you switch it on.
- **Win of the day:** write one small win. On a bad day, click **Show my past wins** to see 5 old wins.
- **Streak, Level, Quest and Review:** these boxes are empty now. They come in later sprints.

The page never shows a word of blame. The backup file holds your goals, wins and focus sessions. The switch **Today page** in Settings → Features turns the page off.

## Game: points, levels, streak, badges, rewards

The **Journey** tab shows your progress. The **Today** page shows your level and your streak.

**The golden rule: points come only from real work that the server checked.** The page cannot give points. The server gives a point only once for each action.

| Action | Points | The server gives them when |
|--------|--------|----------------------------|
| Card ready | 10 | Each main field has a quote that the server found in the PDF. A hidden claim gives no points. |
| Feynman check passed | 25 | Your score is 70 or more. One time for each paper. |
| Quiz answer | 5 | The server marks it correct. One time for each question. |
| Link explained | 10 | The explanation has a verified quote in both PDFs. |
| Focus session | 1 for each 5 minutes | The session has 20 minutes or more. |
| Win of the day | 2 | One time for each day. |

- **Levels:** Explorer, Reader, Critic, Connector, Author, Doctor. A level needs points **and** a skill. Example: Reader needs 100 points, 5 cards with checked quotes and 3 Feynman checks passed. The levels from Critic need features that come in later sprints. The page says so.
- **Kind streak:** a day counts when you got at least one point. You have 2 rest tokens each week. A day without work uses a token and keeps your streak. The weekend is off by default (a switch on the Journey page). After a long pause, the page says: "Welcome back. Your knowledge is still here."
- **Badges:** few, on purpose: First card, First Feynman pass, 7-day streak, 30-day streak, 100 cards, 1 year.
- **Records:** this week against last week, this month against last month. You compare with your own past only. There is no ranking.
- **Your own rewards:** write a reward and a condition (`level:3`, `xp:500`, `streak:7` or `cards:20`). The app tells you when you earned it.
- **Animations:** a calm message shows when you reach a new level or badge. You can switch the animations off on the Journey page. The setting "reduce motion" of your device also switches them off.

The backup file holds your points, badges and rewards. The switch **Game** in Settings → Features turns the game off. While it is off, nobody gets points.

## Knowledge Garden: spaced review

Open the **Review** tab. Each paper is a plant. Each review item gets a date for its next review. The app uses the open **FSRS** algorithm (the algorithm of Anki) to choose the date after each of your answers.

- **Items:** your quiz questions, the words of your glossary, and one **main idea** item for each card. The main idea item uses the checked problem and method of the card. Each item that comes from a paper shows a quote that the server found in the PDF. A word that the AI explained has the label **AI explanation** and no quote. A card without a verified quote makes no item.
- **A review:** you see the question. You think. Click **Show answer**. You see the answer, the quote and the page. Then click **Again**, **Hard**, **Good** or **Easy**. A better answer gives a later date.
- **Only due items:** an item shows up on its day. You cannot review it earlier. So each item gives points at most one time each day.
- **Points:** 2 points for each review, 20 points each day at most.
- **Plants:** a plant is **fresh** when nothing is due. It **needs water** when something is due. It is **a little dry** when something is 3 days or more late. A plant never dies. Click a plant to review only this paper.
- The **Today** page has a box that shows how many items are due.
- The backup file holds the dates of your review.

## PhD Expedition map

The **Journey** tab shows the whole road of your PhD as a map with six regions. Each region fills with color as you work. Click a region to see a first step.

| Region | It fills with |
|--------|---------------|
| Question Peak | Your title, your question and your sub-questions. |
| Literature Forest | Cards with checked quotes and Feynman checks passed, for each sub-question. |
| Method Workshop | The research journal (a later sprint). |
| Data Mines | The experiments in the journal (a later sprint). |
| Writing Coast | The sections of your literature review (a later sprint). |
| Defense Castle | Your thesis outline and your defense practice (later). |

A region at 0% says **Not started** and gives a kind first step. There is no blame. On a phone, a list below the picture shows the same data. The switches **Knowledge Garden** and **PhD Expedition map** in Settings → Features turn these parts off.

## Quests, boss fights and Duck

- **Weekly quests:** on the **Today** page, the server offers 3 quests each week. They fit your PhD stage and the features that exist. You choose 1 or 2. A third choice is refused. You can drop a quest at any time. A quest that you do not finish has **no penalty**: it just goes away.
- **Conditions:** the server checks them after each point event. Example: "Find 3 papers that disagree" counts only explained links of the type "can be compared" that have a verified quote in both PDFs. A quest that is done gives points one time and a done date. The **Journey** page has the quest log.
- **Boss fights:** on a card, click **Mark as boss** for a very hard paper. A crown shows in the library. The boss is defeated when your quiz answers and your Feynman check are both 80% or more (at least 3 quiz answers). You get the badge "Boss defeated" with the title and 50 points. The victory stays if you remove the mark.
- **Duck:** in the Understand tab, the field says "Explain it to Duck". Duck shows a short, kind message after your explanation, a boss victory or a quiz. The texts are fixed. There is no AI. Click **Hide Duck**, or use the switch in Settings → Features.
- The switches **Weekly quests and boss fights** and **Duck companion** turn these parts off. The backup file holds your quests and your bosses.

## 3D avatar

The Journey page shows a small 3D character. It shows your level. Each new level adds one item: a backpack, glasses and a book, a magnifying glass, a rope with a knot, a pen and a scroll, and a doctor cap with a gold star.

- Turn the character with the mouse or the finger.
- The avatar never gets sad. A lost streak changes nothing. The app never takes an item away.
- Click **Hide avatar** to hide it. The browser keeps your choice. You can also switch the feature off in **Settings → Features**.
- If your browser cannot show 3D, you see a flat picture with the same items.
- The turning stops when you switch animations off or when your system asks for less motion.

## Duck Island: a game to play

On the Journey page, open **Duck Island**. It is a small game. It is only for fun.

- **Walk:** use the arrow keys, W A S D, or click on the island. The buttons under the picture do the same.
- **Mini-games:** **Quote Hunt** shows a quote from your papers. You choose the paper. **Word Match** shows a word from your glossary. You choose the meaning. A round has up to 5 questions. After the round, you see the source of each question: title, page and quote.
- **Coins:** you win coins from the games (up to 15 each day) and from your real work (1 coin for each 5 points). Use coins in the **Shop** for items. Then **Decorate** the island: walk the Duck to a free tile and press **Place at the Duck**.
- **No points:** play never gives points, levels or badges. Only real work gives them.
- **Only checked material:** the games use only quotes that the app checked in the PDF text.
- **No guilt:** no timer, no lives, nothing is lost. You can stop a round at any time. If the coins of today are full, you can still play for fun.
- You can switch the feature off in **Settings → Features**.

## Citations and the literature review builder

**Metadata.** On a card, the block **Metadata** shows the authors, the year, the venue and the DOI of the paper. Click **Fill from the PDF**.
- The DOI comes from a rule: the server looks for a DOI in the first pages.
- The AI proposes the authors, the year and the venue. The server keeps a value **only if the PDF has it**. A year that is not on the first page is not saved. A field that the server could not check shows **Check**.
- You can edit each field. A field that you wrote stays, also after a new reading.

**Citations.** On each checked quote of a card, click **Copy citation**. You get a citation with the page, for example `(Smith et al., 2024, p. 3)` (APA) or `[2, p. 3]` (IEEE). If the author or the year is missing, the app says so.
- In the library, click **BibTeX** or **RIS** to export all papers. You can import the files in Zotero.

**Write tab.** The literature review builder has three parts:
- **Outline (left):** click **Make the outline**. You get one section for each sub-question. The outline has only headings. You can move, add and delete sections.
- **Editor (middle):** you write the text. The app saves it after each short pause. If the tab closes too fast, the browser keeps a draft, and it comes back. A line that starts with `>` is a quote. It does not count as a word that you wrote.
- **Cards and quotes (right):** the cards that carry the tag of the sub-question, grouped by link type (same method, same data ...). Each quote is a quote that the server checked. Click **Insert** to put it in your text with its citation and page.
- If you change a quote by hand, the editor says that it is not in your PDFs.
- **Export:** Markdown or Word, with a list of references (APA or IEEE).
- The words that you write give progress to the daily goal of the kind "words". A section of 300 words or more counts for the level **Author**.
- The AI writes no text of your review.

The switches **Citations and metadata**, **Literature review builder** in Settings → Features turn these parts off. The backup file holds the metadata and your review.

## AI use log

The app writes one line for each answer of the AI: the time, the feature, the paper and the model. **Settings** shows how many times the AI helped. You can use this record for the AI use statement of your thesis.

- A saved answer writes no line, because the AI did not help again.
- The log has no text of your papers. The backup file holds the log.
- You cannot switch the log off.

## Mind map, missing fields, AI models

- **Mind map:** it is built from the cards, with no AI call. One card: its claims. Several cards: one branch for each card. It follows the cards each time you open the card. Press "Build the mind map" to show it.
- **Not found:** when the AI saw only a part of a long paper, a field can say "Not found in the excerpts". Click "Search the paper again". The server picks new excerpts for that field and keeps the new answer only if its quote is in the PDF.
- **AI models:** in Settings → AI models, choose the default AI, the fallback, and the model of each. The API keys stay in `.env` and never go through the page.
- **Library:** the button at the left of the top bar opens and closes the library. The browser remembers the choice.

## What is in the box

```
backend/    FastAPI + ChromaDB (local) + pypdf. AI through Gemini (default), Groq (fallback), OpenRouter or Ollama.
frontend/   React (Vite).
render.yaml Settings for Render (backend).
```

## Run on your computer (5 minutes)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # then edit: APP_PASSWORD, SECRET_KEY, GEMINI_API_KEY, GROQ_API_KEY
set -a && source .env && set +a
uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend
cp .env.example .env     # VITE_API_URL=http://localhost:8000
npm install
npm run dev              # open http://localhost:5173
```

The first upload downloads the small embedding model (about 80 MB). This happens one time.

## Put it online for free

### 1. Get an AI key
- Gemini (default): https://aistudio.google.com/apikey. Set `GEMINI_API_KEY`. The default model is `gemini-3.1-flash-lite`. Change it with `GEMINI_MODEL`. Old names such as `gemini-2.5-flash` give error 404 for new keys.
- **Fallback:** if Gemini gives an error (limit, outage, wrong key), the server asks Groq (`LLM_FALLBACK=groq`) for the same request. Gemini rests for 60 seconds (`LLM_COOLDOWN`), then the server uses it again. A provider without a key is skipped. The card shows which model made it.
- **Saved answers:** the server saves each AI answer in the database. The same request gets the saved answer and does not call the AI. "Read again" on a card always asks the AI again. Settings has a button to delete the saved answers.
- Groq: https://console.groq.com/keys (free plan). Default model: `llama-3.3-70b-versatile`.
- Or OpenRouter: https://openrouter.ai/keys. Set `LLM_PROVIDER=openrouter` and `OPENROUTER_API_KEY`.
  Free model names change often. Check the current name and set `LLM_MODEL`.

### 2. Put the code on GitHub
Create a private repository and push this folder.

### 3. Backend on Render
1. Render → New → Web Service → select your repository. Root directory: `research-pal/backend` (if your repository has the app at the top, use `backend`). Runtime: Python. Build: `pip install -r requirements.txt`. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Plan: Free. Health check path: `/api/health`.
2. Set the variables: `APP_PASSWORD` (long), `SECRET_KEY` (at least 24 random characters), `GEMINI_API_KEY`, `GROQ_API_KEY`, `LLM_PROVIDER=gemini`, `LLM_FALLBACK=groq`, `EMBEDDING_BACKEND=gemini`, `FRONTEND_ORIGIN` (you set the real value in step 5), `PYTHON_VERSION=3.11.9`.
   `EMBEDDING_BACKEND=gemini` makes the server ask the Gemini API for the search vectors. The server then does not load the local model, which needs too much memory for the free plan. It needs `GEMINI_API_KEY`. Without the key, an upload stops with the message "GEMINI_API_KEY is missing".
3. Deploy. Test: open `https://YOUR-API.onrender.com/api/health`. You must see `{"ok":true}`. (The live app of this project: https://research-pal-api.onrender.com/api/health.)

### 4. Frontend on Vercel
1. Vercel → Add New → Project → select the repository. Root directory: `research-pal/frontend` (or `frontend` if the app is at the top of your repository).
2. Variable: `VITE_API_URL` = your Render address (no slash at the end).
3. Deploy. You get an address like `https://research-pal.vercel.app`. (The live app of this project: https://rsearch-pal-7tor.vercel.app/.)

### 5. Connect the two
In Render, set `FRONTEND_ORIGIN` = your Vercel address (no slash at the end). To allow more addresses, write them with commas, for example `https://YOUR-APP.vercel.app,http://localhost,capacitor://localhost` (the last two are for a phone app). Redeploy. Open the Vercel address and sign in.

## Free plan limits (read this)

| Limit | What happens | What to do |
|---|---|---|
| Render free disk is temporary | Papers and cards disappear when the server restarts or you deploy again | Download a backup in **Settings** every week. Restore it after a reset. A paid Render disk removes the problem. |
| Render free server sleeps after 15 min | The first request needs up to one minute | The GitHub job [keep-alive.yml](../.github/workflows/keep-alive.yml) calls the server every 10 minutes, so it stays awake. For a second safety, add a free monitor (UptimeRobot, 5 minutes) on `/api/health`. A free Render account has 750 server hours each month. One server that is always awake uses about 744, so do not run a second free service. |
| Render free server has 512 MB of memory | The local embedding model needs most of it. If the server stops during an upload, memory is the reason | Set `EMBEDDING_BACKEND=gemini` (see step 3). Upload one paper at a time. Or use a paid plan, or another host with more memory. |
| Groq free plan has rate limits | You see "free limit is reached" | Wait one minute and click Retry. Lower `LLM_CONTEXT_CHARS` if it continues. |
| Large papers | The limits are 25 MB (`MAX_UPLOAD_MB`), 80 pages (`MAX_PAGES`) and 90,000 characters for one card (`LLM_CONTEXT_CHARS`). A larger paper is read in part. | Write a **Focus topic** when you add the paper, or cut the PDF before you upload it. |

## Privacy (you wrote: very sensitive data)

- With the default setting, search and links run on your server only. The embeddings never leave it. With `EMBEDDING_BACKEND=gemini`, the text of the chunks goes to Google to make the vectors.
- To make a card, **selected passages of the paper (not the full PDF file) go to the AI provider** (Groq or OpenRouter). Read their data policy before you use unpublished or confidential papers.
- Simple mode sends one text of a card (or a chat answer) to the AI provider. The word helper sends the word and up to 3 sentences of the paper, only when the paper has no definition.
- Public hosting (Render, Vercel) also means your data is on their servers.
- For truly private reading: run the backend on your own computer with Ollama
  (`LLM_PROVIDER=ollama`, `ollama pull llama3.1:8b`). No text leaves your computer.
- The app has one password, a 14-day login, limits on wrong passwords, and refuses to start without a strong password and secret.

## Tests

All tests use a fake AI. They need no API key and no network. Read [docs/TESTING.md](docs/TESTING.md) for the full steps.

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
pytest                      # backend tests, about 15 seconds
cd ../frontend
npm install
npm test                    # unit tests
npm run e2e                 # tests in a real browser
```

- **Truth tests:** the fake AI gives a false quote or a false number. The tests check that the server hides or labels it.
- **CI:** GitHub runs all tests on each push. See [.github/workflows/ci.yml](../.github/workflows/ci.yml).
- **Real AI smoke test:** `python scripts/smoke_real_ai.py paper1.pdf paper2.pdf paper3.pdf`. It reads real papers with your AI key. You read the result.

## Feature switches

Each feature has a switch in **Settings → Features**. Switch a feature off if it gives a problem. The tab goes away and the server refuses the calls of that feature. Your data stays. The switches are: **Chat**, **Simple mode**, **Explain it to me**, **Like I am 12**, **Quiz me**, **Word helper and glossary**, **Today page**, **Game**, **Knowledge Garden**, **PhD Expedition map**, **Weekly quests and boss fights**, **Duck companion**, **Citations and metadata**, **Literature review builder**, **3D avatar** and **Duck Island**.

## Later (your list)

LaTeX paper writing with best practices, and presentations. The cards, with their verified quotes, are the right base for both: the writing tool can cite only claims that passed the check.
