import { useCallback, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api.js";
import Login from "./Login.jsx";
import Library from "./Library.jsx";
import CardView from "./CardView.jsx";
import Chat from "./Chat.jsx";
import Search from "./Search.jsx";
import Graph from "./Graph.jsx";
import Settings from "./Settings.jsx";
import { Icon, Logo } from "./icons.jsx";
import ThemeToggle from "./ThemeToggle.jsx";

const TABS = [
  ["cards", "Card", "doc"],
  ["chat", "Chat", "chat"],
  ["search", "Search", "search"],
  ["links", "Links", "graph"],
  ["settings", "Settings", "sliders"],
];

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());
  const [tab, setTab] = useState("cards");
  const [papers, setPapers] = useState([]);
  const [selected, setSelected] = useState(null);
  const [config, setConfig] = useState(null);
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    try {
      setPapers(await api.papers());
    } catch (e) {
      setNotice(e.message);
    }
  }, []);

  useEffect(() => {
    const out = () => setAuthed(false);
    window.addEventListener("rp-logout", out);
    return () => window.removeEventListener("rp-logout", out);
  }, []);

  useEffect(() => {
    if (!authed) return;
    refresh();
    api.config().then(setConfig).catch(() => {});
  }, [authed, refresh]);

  // Poll while a paper is in progress
  const busy = papers.some((p) => p.status === "queued" || p.status === "processing");
  useEffect(() => {
    if (!authed || !busy) return;
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, [authed, busy, refresh]);

  // Select the first paper when the list loads
  useEffect(() => {
    if (!selected && papers.length) setSelected(papers[0].id);
    if (selected && papers.length && !papers.some((p) => p.id === selected)) setSelected(papers[0].id);
  }, [papers, selected]);

  const openPaper = (id) => {
    setSelected(id);
    setTab("cards");
  };

  if (!authed) {
    return (
      <Login
        onDone={() => {
          setAuthed(true);
        }}
      />
    );
  }

  return (
    <div className="app">
      <header className="bar">
        <div className="brand">
          <Logo size={26} />
          Research Pal
        </div>
        <nav className="tabs" role="tablist" aria-label="Sections">
          {TABS.map(([k, label, icon]) => (
            <button key={k} role="tab" aria-selected={tab === k} aria-label={label} onClick={() => { setTab(k); setNotice(""); }}>
              <Icon name={icon} size={16} />
              <span className="tl">{label}</span>
            </button>
          ))}
        </nav>
        <div className="bar-end">
          <ThemeToggle />
        </div>
      </header>

      {notice && (
        <div className="toast" role="alert">
          <span>{notice}</span>
          <button className="link" onClick={() => setNotice("")}>
            Close
          </button>
        </div>
      )}

      <div className="layout">
        <Library
          papers={papers}
          selectedId={selected}
          config={config}
          onSelect={openPaper}
          onChanged={refresh}
          notify={setNotice}
        />
        <main className="main">
          {tab === "cards" &&
            (selected ? (
              <CardView
                key={selected}
                id={selected}
                onChanged={refresh}
                onDeleted={() => {
                  setSelected(null);
                  refresh();
                }}
                notify={setNotice}
              />
            ) : (
              <div className="empty">
                <Logo size={64} />
                <h2>Start with one paper</h2>
                <p className="sub">Research Pal reads your PDF and fills a card. Each claim shows the quote and the page that prove it.</p>
                <ol className="steps">
                  <li>
                    <span className="n">1</span>
                    <div>
                      <strong>Add a PDF</strong>
                      <span>Use the Library on the left. Write a focus topic if you need only one part.</span>
                    </div>
                  </li>
                  <li>
                    <span className="n">2</span>
                    <div>
                      <strong>Read the card</strong>
                      <span>Start with the verdict. Then check the proof for each claim.</span>
                    </div>
                  </li>
                  <li>
                    <span className="n">3</span>
                    <div>
                      <strong>Ask questions</strong>
                      <span>Use Chat to compare papers. Every answer shows its quotes.</span>
                    </div>
                  </li>
                </ol>
              </div>
            ))}
          {/* The chat stays mounted, so the conversation is not lost when you open a card */}
          <div hidden={tab !== "chat"}>
            <Chat papers={papers} selectedId={selected} onOpenCard={openPaper} notify={setNotice} />
          </div>
          {tab === "search" && <Search onOpenCard={openPaper} notify={setNotice} />}
          {tab === "links" && <Graph onOpenCard={openPaper} notify={setNotice} />}
          {tab === "settings" && (
            <Settings
              config={config}
              onConfig={setConfig}
              onImported={refresh}
              onLogout={() => {
                setToken("");
                setAuthed(false);
              }}
              notify={setNotice}
            />
          )}
        </main>
      </div>
    </div>
  );
}
