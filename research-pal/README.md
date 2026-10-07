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
1. Render → New → Blueprint → select your repository. (Or New → Web Service, root directory `backend`.)
2. Set the variables: `APP_PASSWORD` (long), `GROQ_API_KEY`, `FRONTEND_ORIGIN` (you set the real value in step 5). `SECRET_KEY` is generated.
3. Deploy. Test: open `https://YOUR-API.onrender.com/api/health`. You must see `{"ok":true}`.

### 4. Frontend on Vercel
1. Vercel → Add New → Project → select the repository. Root directory: `frontend`.
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
- Public hosting (Render, Vercel) also means your data is on their servers.
- For truly private reading: run the backend on your own computer with Ollama
  (`LLM_PROVIDER=ollama`, `ollama pull llama3.1:8b`). No text leaves your computer.
- The app has one password, a 14-day login, limits on wrong passwords, and refuses to start without a strong password and secret.

## Tests

```bash
cd backend
pip install reportlab
python tests/test_pipeline.py
```
The test uses a fake AI. It checks the PDF reading, the quote check, the hiding of false claims, search, links, backup and restore.

## Later (your list)

LaTeX paper writing with best practices, and presentations. The cards, with their verified quotes, are the right base for both: the writing tool can cite only claims that passed the check.
