import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { getToken, setToken } from "./api.js";
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
import Play from "./Play.jsx";
import GameBar from "./GameBar.jsx";
import GameLayer from "./GameLayer.jsx";
import { setSimpleEnabled } from "./level.js";
import { initNative, tap } from "./native.js";
import { featureOn, isPhone, useApp } from "./store.js";

const TABS = [
  ["cards", "Card", "doc"],
  ["chat", "Chat", "chat"],
  ["search", "Search", "search"],
  ["glossary", "Glossary", "book"],
  ["links", "Links", "graph"],
  ["play", "Play", "trophy"],
  ["settings", "Settings", "sliders"],
];

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());
  const { tab, papers, selected, config, features, glossKey, notice, libOpen } = useApp();
  const { setTab, notify, setConfig, setFeatures, bumpGlossary, toggleLibrary, closeLibrary, refresh, refreshGame, select, openPaper, load } = useApp.getState();

  // The Android back button closes the drawer first. The function reads the store at the moment of the press, so it is never old.
  useEffect(
    () =>
      initNative(() => {
        const { libOpen: open, closeLibrary: close } = useApp.getState();
        if (open && isPhone()) {
          close();
          return true;
        }
        return false;
      }),
    [],
  );

  useEffect(() => {
    const out = () => setAuthed(false);
    window.addEventListener("rp-logout", out);
    return () => window.removeEventListener("rp-logout", out);
  }, []);

  useEffect(() => {
    if (authed) load();
  }, [authed, load]);

  // The app comes back from the background (the phone was locked, or you used another app): the papers are fresh again.
  useEffect(() => {
    if (!authed) return;
    const onVisible = () => document.visibilityState === "visible" && refresh();
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [authed, refresh]);

  // The switch "Simple mode" in Settings turns the whole Simple function off.
  useEffect(() => {
    setSimpleEnabled(featureOn(features, "simple"));
  }, [features]);

  // Poll while a paper is in progress
  const busy = papers.some((p) => p.status === "queued" || p.status === "processing");
  useEffect(() => {
    if (!authed || !busy) return;
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, [authed, busy, refresh]);

  // The game looks again when a paper becomes ready (a new card earns XP), and when the student did work on the server (a note, a link, a word).
  const wasBusy = useRef(false);
  useEffect(() => {
    if (wasBusy.current && !busy) refreshGame();
    wasBusy.current = busy;
  }, [busy, refreshGame]);
  useEffect(() => {
    if (!authed) return undefined;
    let timer;
    const onWork = () => {
      clearTimeout(timer);
      timer = setTimeout(refreshGame, 900);
    };
    window.addEventListener("rp-work", onWork);
    return () => {
      window.removeEventListener("rp-work", onWork);
      clearTimeout(timer);
    };
  }, [authed, refreshGame]);

  // Select the first paper when the list loads
  useEffect(() => {
    if (!selected && papers.length) select(papers[0].id);
    if (selected && papers.length && !papers.some((p) => p.id === selected)) select(papers[0].id);
  }, [papers, selected, select]);

  const on = (name) => featureOn(features, name);
  const shownTabs = TABS.filter(([k]) => (k !== "chat" || on("chat")) && (k !== "glossary" || on("glossary")) && (k !== "play" || on("game")));
  const page = (tab === "chat" && !on("chat")) || (tab === "glossary" && !on("glossary")) || (tab === "play" && !on("game")) ? "cards" : tab;

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
          <button className={"iconbtn" + (libOpen ? " on" : "")} onClick={toggleLibrary} aria-expanded={libOpen} aria-controls="library" aria-label={libOpen ? "Close the library" : "Open the library"} title={libOpen ? "Close the library" : "Open the library"}>
            <Icon name="sidebar" size={18} />
          </button>
          <Logo size={26} />
          <span className="brand-name">Research Pal</span>
        </div>
        <nav className="tabs" role="tablist" aria-label="Sections">
          {shownTabs.map(([k, label, icon]) => (
            <button
              key={k}
              role="tab"
              aria-selected={tab === k}
              aria-label={label}
              onClick={() => {
                setTab(k);
                tap();
              }}
            >
              {/* One pill moves from tab to tab. This shows where you are, and where you go. */}
              {tab === k && <motion.span layoutId="tabpill" className="tabpill" transition={{ type: "spring", stiffness: 520, damping: 40 }} />}
              <Icon name={icon} size={16} />
              <span className="tl">{label}</span>
            </button>
          ))}
        </nav>
        <div className="bar-end">
          {on("game") && <GameBar />}
          {on("simple") && <LevelToggle />}
          <ThemeToggle />
        </div>
      </header>

      <AnimatePresence>
        {notice && (
          <motion.div
            className="toast"
            role="alert"
            initial={{ opacity: 0, y: -16, x: "-50%", scale: 0.96 }}
            animate={{ opacity: 1, y: 0, x: "-50%", scale: 1 }}
            exit={{ opacity: 0, y: -10, x: "-50%" }}
            transition={{ type: "spring", stiffness: 420, damping: 32 }}
          >
            <span>{notice}</span>
            <button className="link" onClick={() => notify("")}>
              Close
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* On a phone the library is a drawer. A tap outside it closes it. */}
      <button className={"scrim" + (libOpen ? " on" : "")} tabIndex={-1} aria-hidden="true" onClick={closeLibrary} />
      <div className={"layout" + (libOpen ? "" : " collapsed")}>
        <Library papers={papers} selectedId={selected} config={config} onSelect={openPaper} onChanged={refresh} notify={notify} onClose={closeLibrary} />
        <main className="main" id="main" tabIndex={-1}>
          {/* A page fades in and slides up a little when you change the tab. The chat is outside, so it stays mounted. */}
          <AnimatePresence mode="wait" initial={false}>
            {page !== "chat" && (
              <motion.div key={page} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6, transition: { duration: 0.1 } }} transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}>
                {page === "cards" &&
                  (selected ? (
                    <CardView
                      key={selected}
                      id={selected}
                      onChanged={refresh}
                      onDeleted={() => {
                        select(null);
                        refresh();
                      }}
                      notify={notify}
                    />
                  ) : (
                    <div className="empty">
                      <Logo size={64} />
                      <h2>Start with one paper</h2>
                      <p className="sub">Research Pal reads your PDF and fills a card. Each claim shows the quote and the page that prove it.</p>
                      <ol className="steps">
                        {[
                          ["Add a PDF", "Use the Library. Write a focus topic if you need only one part."],
                          ["Read the card", "Start with the verdict. Then check the proof for each claim."],
                          ["Ask questions", "Use Chat to compare papers. Every answer shows its quotes."],
                        ].map(([title, text], i) => (
                          <motion.li key={title} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 + i * 0.09, type: "spring", stiffness: 260, damping: 26 }}>
                            <span className="n">{i + 1}</span>
                            <div>
                              <strong>{title}</strong>
                              <span>{text}</span>
                            </div>
                          </motion.li>
                        ))}
                      </ol>
                    </div>
                  ))}
                {page === "glossary" && <Glossary reloadKey={glossKey} notify={notify} />}
                {page === "search" && <Search onOpenCard={openPaper} notify={notify} />}
                {page === "links" && <LinksTab onOpenCard={openPaper} notify={notify} />}
                {page === "play" && <Play notify={notify} />}
                {page === "settings" && (
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
                    notify={notify}
                  />
                )}
              </motion.div>
            )}
          </AnimatePresence>
          {/* The chat stays mounted, so the conversation is not lost when you open a card */}
          {on("chat") && (
            <div hidden={page !== "chat"}>
              <Chat papers={papers} selectedId={selected} onOpenCard={openPaper} notify={notify} />
            </div>
          )}
        </main>
      </div>
      {on("game") && <GameLayer />}
      {/* The word box. It opens when you select a word in a card or in the chat. */}
      <WordHelper paperId={on("glossary") && (page === "cards" || page === "chat") ? selected || "" : ""} notify={notify} onSaved={bumpGlossary} />
    </div>
  );
}
