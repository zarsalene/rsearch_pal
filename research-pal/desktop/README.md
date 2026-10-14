# Research Pal for the desktop

A separate copy of the app for one computer. It does not change the web app or the phone app.
It uses the same backend (`backend/`) and the same UI code (`web/`).

## What stays on your computer

- Papers, PDFs, cards, notes and the search index (SQLite and ChromaDB on disk).
- The search model (it runs on your computer).
- There is no Supabase, no email login and no password page. The server listens on `127.0.0.1` only.

## What goes out

Only the AI calls: selected passages of a paper go to **Gemini**. If Gemini fails, **OpenRouter** answers.
Read the data policy of both before you use confidential papers.

## Run it

```bash
python desktop/build_ui.py     # one time, and again after a change in web/
python desktop/app.py          # opens the app window. Close the window to stop the server.
```

`python desktop/app.py --no-window` runs the server only. Open `http://127.0.0.1:8765` in a browser.

### With Electron (own window, own icon)

```bash
cd desktop/electron
npm install      # one time (downloads Electron, about 100 MB)
npm start        # starts the Python server and opens the window. Close the window to stop the server.
```

Electron only replaces the window. The server and the UI are the same. It uses `.venv/Scripts/python.exe` of the project
(or `python`; set `RESEARCH_PAL_PYTHON` to use another one). If the server does not start, read `%LOCALAPPDATA%\ResearchPal\server.log`.
Use `npm start`, not `electron .`: VS Code sets `ELECTRON_RUN_AS_NODE`, and `start.js` removes it.

## Your data and your keys

Everything is in `%LOCALAPPDATA%\ResearchPal\`:

| File | What it holds |
|---|---|
| `settings.env` | `GEMINI_API_KEY` and `OPENROUTER_API_KEY`. The app opens this file the first time, when it finds no key. |
| `data\` | Your database, PDFs and search index. Copy this folder to make a backup. |
| `local.json` | A secret that the app made for this computer. Keep it private. |
| `window\` | The profile of the app window. |

Set `RESEARCH_PAL_HOME` to use another folder. Set `RESEARCH_PAL_PORT` to use another port (default 8765).

In a developer copy, the keys in `backend/.env` also work, when `settings.env` has no value for them.
The Supabase values in `backend/.env` are always ignored here.

## Limits of this version

- It needs Python with the packages of `backend/requirements.txt`, and Node (for `build_ui.py`). There is no installer yet.
- `python desktop/app.py` opens Edge (or Chrome) in app mode. `npm start` in `desktop/electron` opens an Electron window.
- There is no installer yet (no `.exe` that you can give to another person). That needs the Python server packed with PyInstaller and electron-builder.
- The first upload downloads the search model (about 80 MB).
- Any local program on this computer can open the address and get the login token. This is normal for a local app.
