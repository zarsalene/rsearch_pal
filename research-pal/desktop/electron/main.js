// Research Pal desktop window (Electron). It starts the Python server (desktop/app.py) and shows its page.
// The server and the UI are the same as in `python desktop/app.py`. Only the window is different.
const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn, execFileSync } = require("child_process");
const fs = require("fs");
const http = require("http");
const path = require("path");

// Installed app (the .exe): its own Python and the server files are in resources/. In development: the project folder.
const PACKED = app.isPackaged;
const ROOT = PACKED ? path.join(process.resourcesPath, "server") : path.resolve(__dirname, "..", "..");
const PORT = process.env.RESEARCH_PAL_PORT || "8765";
const URL_ = `http://127.0.0.1:${PORT}`;
const HOME = process.env.RESEARCH_PAL_HOME || path.join(process.env.LOCALAPPDATA || ROOT, "ResearchPal");
let server = null; // only set when this window started the server, so it stops it when you close the window

const health = () =>
  new Promise((ok) => {
    const r = http.get(URL_ + "/api/health", { timeout: 1500 }, (res) => (res.resume(), ok(res.statusCode === 200)));
    r.on("error", () => ok(false));
    r.on("timeout", () => (r.destroy(), ok(false)));
  });

function python() {
  if (PACKED) return path.join(process.resourcesPath, "python", "python.exe");
  const venv = path.join(ROOT, ".venv", "Scripts", "python.exe");
  return process.env.RESEARCH_PAL_PYTHON || (fs.existsSync(venv) ? venv : "python");
}

async function startServer() {
  if (await health()) return; // the server runs already: only open a window
  fs.mkdirSync(HOME, { recursive: true });
  const log = fs.openSync(path.join(HOME, "server.log"), "w");
  // -I (installed app only): ignore PYTHON* variables of this computer
  const args = [...(PACKED ? ["-I"] : []), path.join(ROOT, "desktop", "app.py"), "--no-window"];
  server = spawn(python(), args, { cwd: ROOT, windowsHide: true, stdio: ["ignore", log, log] });
  server.on("exit", () => (server = null));
  for (let i = 0; i < 120 && server; i++) {
    if (await health()) return;
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`The server did not start. Read this file:\n${path.join(HOME, "server.log")}`);
}

const stopServer = () => {
  if (!server) return;
  try { execFileSync("taskkill", ["/pid", String(server.pid), "/T", "/F"], { stdio: "ignore" }); } catch {}
  server = null;
};

if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on("second-instance", () => {
    const w = BrowserWindow.getAllWindows()[0];
    if (w) (w.isMinimized() && w.restore(), w.focus());
  });
  app.whenReady().then(async () => {
    try {
      await startServer();
    } catch (e) {
      dialog.showErrorBox("Research Pal", e.message);
      return app.quit();
    }
    const win = new BrowserWindow({
      width: 1320, height: 880, minWidth: 400, title: "Research Pal", backgroundColor: "#0B0B0E", autoHideMenuBar: true,
      ...(PACKED ? {} : { icon: path.join(ROOT, "web", "public", "logo.png") }), // the .exe has its icon inside
    });
    // The page opens the PDF in a new window (about:blank, then a blob address). Other links go to your browser.
    win.webContents.setWindowOpenHandler(({ url }) => {
      if (!url || url.startsWith("about:") || url.startsWith("blob:") || url.startsWith(URL_)) return { action: "allow" };
      if (/^https?:/.test(url)) shell.openExternal(url);
      return { action: "deny" };
    });
    win.loadURL(URL_);
  });
  app.on("window-all-closed", () => app.quit());
  app.on("will-quit", stopServer);
}
