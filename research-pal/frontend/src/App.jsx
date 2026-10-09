import { useCallback, useEffect, useRef, useState } from "react";
import { api, getToken, setToken } from "./api.js";
import Login from "./Login.jsx";
import Library from "./Library.jsx";
import CardView from "./CardView.jsx";
import Chat from "./Chat.jsx";
import Search from "./Search.jsx";
import LinksTab from "./LinksTab.jsx";
import Settings from "./Settings.jsx";
import { Icon, Logo } from "./icons.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import LevelToggle from "./LevelToggle.jsx";
import Glossary from "./Glossary.jsx";
import WordHelper from "./WordHelper.jsx";
import { setSimpleEnabled } from "./level.js";
import { initNative, tap } from "./native.js";

const PHONE = "(max-width: 820px)";

const TABS = [
  ["cards", "Card", "doc"],
  ["chat", "Chat", "chat"],
  ["search", "Search", "search"],
  ["glossary", "Glossary", "book"],
  ["links", "Links", "graph"],
  ["settings", "Settings", "sliders"],
];

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());
  const [tab, setTab] = useState("cards");
  const [papers, setPapers] = useState([]);
  const [selected, setSelected] = useState(null);
  const [config, setConfig] = useState(null);
  const [features, setFeatures] = useState(null);
  const [glossKey, setGlossKey] = useState(0); // changes when a word is saved, so the Glossary page reloads
  const [notice, setNotice] = useState("");
  // The library can open and close. The choice is saved in this browser.
  const [libOpen, setLibOpen] = useState(() => {
    try {
      const saved = localStorage.getItem("rp-library");
      // On a phone the library is a drawer. It starts closed, so the card is the first thing you see.
      if (!saved && window.matchMedia(PHONE).matches) return false;
      return saved !== "closed";
    } catch {
      return true;
    }
  });
  // The Android back button closes the drawer first. It gives true when it closed something.
  const backRef = useRef(() => false);
  backRef.current = () => {
    if (libOpen && window.matchMedia(PHONE).matches) {
      setLibOpen(false);
      return true;
    }
    return false;
  };
  useEffect(() => {
    initNative(() => backRef.current());
  }, []);
  const toggleLib = () =>
    setLibOpen((v) => {
      try {
        localStorage.setItem("rp-library", v ? "closed" : "open");
      } catch {}
      return !v;
    });

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
    api.features().then(setFeatures).catch(() => {});
  }, [authed, refresh]);

  // The switch "Simple mode" in Settings turns the whole Simple function off.
  useEffect(() => {
    setSimpleEnabled(features?.find((f) => f.name === "simple")?.enabled !== false);
  }, [features]);

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
    // On a phone the library takes the whole width. Close it, so the card is visible.
    if (window.matchMedia(PHONE).matches) setLibOpen(false);
  };

  // A feature that is switched off in Settings has no tab. While the list loads, all features show.
  const on = (name) => features?.find((f) => f.name === name)?.enabled !== false;
  const shownTabs = TABS.filter(([k]) => (k !== "chat" || on("chat")) && (k !== "glossary" || on("glossary")));
  const page = (tab === "chat" && !on("chat")) || (tab === "glossary" && !on("glossary")) ? "cards" : tab;

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
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="bar">
        <div className="brand">
          <button className={"iconbtn" + (libOpen ? " on" : "")} onClick={toggleLib} aria-expanded={libOpen} aria-controls="library" aria-label={libOpen ? "Close the library" : "Open the library"} title={libOpen ? "Close the library" : "Open the library"}>
            <Icon name="sidebar" size={18} />
          </button>
          <Logo size={26} />
          <span className="brand-name">Research Pal</span>
        </div>
        <nav className="tabs" role="tablist" aria-label="Sections">
          {shownTabs.map(([k, label, icon]) => (
            <button key={k} role="tab" aria-selected={tab === k} aria-label={label} onClick={() => { setTab(k); setNotice(""); tap(); }}>
              <Icon name={icon} size={16} />
              <span className="tl">{label}</span>
            </button>
          ))}
        </nav>
        <div className="bar-end">
          {on("simple") && <LevelToggle />}
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

      {/* On a phone the library is a drawer. A tap outside it closes it. */}
      <button className={"scrim" + (libOpen ? " on" : "")} tabIndex={-1} aria-hidden="true" onClick={() => setLibOpen(false)} />
      <div className={"layout" + (libOpen ? "" : " collapsed")}>
        <Library
          papers={papers}
          selectedId={selected}
          config={config}
          onSelect={openPaper}
          onChanged={refresh}
          notify={setNotice}
        />
        <main className="main" id="main" tabIndex={-1}>
          {page === "cards" &&
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
          {on("chat") && (
            <div hidden={page !== "chat"}>
              <Chat papers={papers} selectedId={selected} onOpenCard={openPaper} notify={setNotice} />
            </div>
          )}
          {page === "glossary" && <Glossary reloadKey={glossKey} notify={setNotice} />}
          {tab === "search" && <Search onOpenCard={openPaper} notify={setNotice} />}
          {tab === "links" && <LinksTab onOpenCard={openPaper} notify={setNotice} />}
          {tab === "settings" && (
            <Settings
              config={config}
              features={features}
              onFeatures={setFeatures}
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
      {/* The word box. It opens when you select a word in a card or in the chat. */}
      <WordHelper paperId={on("glossary") && (page === "cards" || page === "chat") ? selected || "" : ""} notify={setNotice} onSaved={() => setGlossKey((k) => k + 1)} />
    </div>
  );
}
