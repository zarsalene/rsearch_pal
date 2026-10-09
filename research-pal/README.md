# Research_Pal

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
- Gemini (default): https://aistudio.google.com/apikey. Set `GEMINI_API_KEY`. Change the model with `GEMINI_MODEL`.
- **Fallback:** if Gemini gives an error (limit, outage, wrong key), the server asks Groq (`LLM_FALLBACK=groq`) for the same request. Gemini rests for 60 seconds (`LLM_COOLDOWN`), then the server uses it again. A provider without a key is skipped. The card shows which model made it.
- **Saved answers:** the server saves each AI answer in the database. The same request gets the saved answer and does not call the AI. "Read again" on a card always asks the AI again. Settings has a button to delete the saved answers.
- Groq: https://console.groq.com/keys (free plan). Default model: `llama-3.3-70b-versatile`.
- Or OpenRouter: https://openrouter.ai/keys. Set `LLM_PROVIDER=openrouter` and `OPENROUTER_API_KEY`.
  Free model names change often. Check the current name and set `LLM_MODEL`.

### 2. Put the code on GitHub
Create a private repository and push this folder.

### 3. Backend on Render
1. Render → New → Web Service → select your repository. Root directory: `research-pal/backend` (if your repository has the app at the top, use `backend`). Runtime: Python. Build: `pip install -r requirements.txt`. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Plan: Free. Health check path: `/api/health`.
2. Set the variables: `APP_PASSWORD` (long), `SECRET_KEY` (at least 24 random characters), `GEMINI_API_KEY`, `GROQ_API_KEY`, `LLM_PROVIDER=gemini`, `LLM_FALLBACK=groq`, `FRONTEND_ORIGIN` (you set the real value in step 5), `PYTHON_VERSION=3.11.9`.
3. Deploy. Test: open `https://YOUR-API.onrender.com/api/health`. You must see `{"ok":true}`.

### 4. Frontend on Vercel
1. Vercel → Add New → Project → select the repository. Root directory: `research-pal/frontend` (or `frontend` if the app is at the top of your repository).
2. Variable: `VITE_API_URL` = your Render address (no slash at the end).
3. Deploy. You get an address like `https://research-pal.vercel.app`.

### 5. Connect the two
In Render, set `FRONTEND_ORIGIN` = your Vercel address (no slash at the end). Redeploy. Open the Vercel address and sign in.

## Free plan limits (read this)

| Limit | What happens | What to do |
|---|---|---|
| Render free disk is temporary | Papers and cards disappear when the server restarts or you deploy again | Download a backup in **Settings** every week. Restore it after a reset. A paid Render disk removes the problem. |
| Render free server sleeps after 15 min | The first request needs up to one minute | Wait. The login page tells you. |
| Render free server has 512 MB of memory | The embedding model needs most of it. If the server stops during an upload, memory is the reason | Upload one paper at a time. Or use a paid plan, or another host with more memory. |
| Groq free plan has rate limits | You see "free limit is reached" | Wait one minute and click Retry. Lower `LLM_CONTEXT_CHARS` if it continues. |

## Privacy (you wrote: very sensitive data)

- Search and links run on your server only. The embeddings never leave it.
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
- **CI:** GitHub runs all tests on each push. See `.github/workflows/ci.yml`.
- **Real AI smoke test:** `python scripts/smoke_real_ai.py paper1.pdf paper2.pdf paper3.pdf`. It reads real papers with your AI key. You read the result.

## Feature switches

Each feature has a switch in **Settings → Features**. Switch a feature off if it gives a problem. The tab goes away and the server refuses the calls of that feature. Your data stays. The switches are: **Chat**, **Simple mode**, **Explain it to me**, **Like I am 12**, **Quiz me** and **Word helper and glossary**.

## Later (your list)

LaTeX paper writing with best practices, and presentations. The cards, with their verified quotes, are the right base for both: the writing tool can cite only claims that passed the check.
