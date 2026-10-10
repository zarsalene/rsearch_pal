import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { api, getToken, setToken } from "./api.js";
import Login from "./Login.jsx";
import Library from "./Library.jsx";
import CardView from "./CardView.jsx";
import Chat from "./Chat.jsx";
import Search from "./Search.jsx";
import Graph from "./Graph.jsx";
import Settings from "./Settings.jsx";
import Project from "./Project.jsx";
import ThesisBar from "./ThesisBar.jsx";
import { Icon, Logo } from "./icons.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import LevelToggle from "./LevelToggle.jsx";
import Glossary from "./Glossary.jsx";
import Today from "./Today.jsx";
import Journey from "./Journey.jsx";
import ToRead from "./ToRead.jsx";
import Plan from "./Plan.jsx";
import Review from "./Review.jsx";
import Write from "./Write.jsx";
import GameWatcher from "./GameWatcher.jsx";
import { applyAnimations } from "./game.js";
import WordHelper from "./WordHelper.jsx";
import { setSimpleEnabled } from "./level.js";
import MoreSheet from "./MoreSheet.jsx";
import { initNative, tap } from "./native.js";
import { isPhone, usePhone } from "./phone.js";

const TABS = [
  ["today", "Today", "target"],
  ["review", "Review", "refresh"],
  ["journey", "Journey", "chart"],
  ["toread", "To read", "layers"],
  ["plan", "Plan", "check"],
  ["cards", "Card", "doc"],
  ["chat", "Chat", "chat"],
  ["search", "Search", "search"],
  ["glossary", "Glossary", "book"],
  ["write", "Write", "layers"],
  ["links", "Links", "graph"],
  ["project", "Thesis", "flag"],
  ["settings", "Settings", "sliders"],
];

// On a phone the bottom bar has these tabs. The other pages are in the sheet "More".
const DOCK = ["today", "cards", "chat", "search"];

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());
  const [tab, setTab] = useState("today"); // Today is the home page
  const [papers, setPapers] = useState([]);
  const [selected, setSelected] = useState(null);
  const [config, setConfig] = useState(null);
  const [features, setFeatures] = useState(null);
  const [project, setProject] = useState(null); // the thesis: title, question, stage
  const [subQuestions, setSubQuestions] = useState([]);
  const [glossKey, setGlossKey] = useState(0); // changes when a word is saved, so the Glossary page reloads
  const [notice, setNotice] = useState("");
  const [more, setMore] = useState(false); // the sheet "More" of the phone
  const phone = usePhone();
  // The library can open and close. The choice is saved in this browser.
  const [libOpen, setLibOpen] = useState(() => {
    try {
      const saved = localStorage.getItem("rp-library");
      // On a phone the library is a drawer. It starts closed, so the card is the first thing you see.
      if (!saved && isPhone()) return false;
      return saved !== "closed";
    } catch {
      return true;
    }
  });
  const toggleLib = () =>
    setLibOpen((v) => {
      try {
        localStorage.setItem("rp-library", v ? "closed" : "open");
      } catch {}
      return !v;
    });

  const closeLib = () => setLibOpen(false);
  // The Android back button closes the sheet or the drawer first. The ref always has the newest state.
  const live = useRef({});
  live.current = { libOpen, more };
  useEffect(
    () =>
      initNative(() => {
        const { libOpen: open, more: sheet } = live.current;
        if (sheet) {
          setMore(false);
          return true;
        }
        if (open && isPhone()) {
          setLibOpen(false);
          return true;
        }
        return false;
      }),
    [],
  );

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
    api.project().then(setProject).catch(() => {});
    api.subQuestions().then(setSubQuestions).catch(() => {}); // the server refuses this call when the feature is off
  }, [authed, refresh]);

  // The app comes back from the background (the phone was locked, or you used another app): the papers are fresh again.
  useEffect(() => {
    if (!authed) return;
    const onVisible = () => document.visibilityState === "visible" && refresh();
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [authed, refresh]);

  // The question has one saved copy. Each page that changes it uses this function.
  const changeProject = useCallback((p) => {
    setProject(p);
    setConfig((c) => (c ? { ...c, thesis_question: p.question } : c));
  }, []);
  const saveThesis = async (changes) => {
    try {
      changeProject(await api.saveProject(changes));
      return true;
    } catch (e) {
      setNotice(e.message);
      return false;
    }
  };
  useEffect(() => applyAnimations(), []);
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
    if (window.matchMedia("(max-width: 820px)").matches) setLibOpen(false);
  };

  // A feature that is switched off in Settings has no tab. While the list loads, all features show.
  const on = (name) => features?.find((f) => f.name === name)?.enabled !== false;
  const hidden = { write: !on("litreview"), today: !on("today"), review: !on("review"), journey: !on("game") && !on("map"), chat: !on("chat"), project: !on("direction"), glossary: !on("glossary"), toread: !on("findpapers"), plan: !on("plan") }; // a tab of a feature that is switched off
  const shownTabs = TABS.filter(([k]) => !hidden[k]);
  const page = hidden[tab] ? "cards" : tab;
  const dockTabs = phone ? shownTabs.filter(([k]) => DOCK.includes(k)) : shownTabs;
  const moreTabs = phone ? shownTabs.filter(([k]) => !DOCK.includes(k)) : [];
  const moreActive = more || moreTabs.some(([k]) => k === tab);
  const go = (k) => {
    setTab(k);
    setNotice("");
    setMore(false);
  };
  const paperTags = papers.find((p) => p.id === selected)?.tags || {};
  // The big button of the Today page opens the right place.
  const goAction = (a) => {
    if ((a.kind === "fill" || a.kind === "explain") && a.paper_id) openPaper(a.paper_id);
    else if (a.kind === "find_paper") setTab(on("direction") ? "project" : "cards");
    else if (a.kind === "add_paper") {
      setLibOpen(true);
      setTab("cards");
      setNotice("Click Add paper in the library. Then choose a PDF.");
    }
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
          {dockTabs.map(([k, label, icon]) => (
            <button key={k} role="tab" aria-selected={tab === k} aria-label={label} title={label} onClick={() => { go(k); tap(); }}>
              {/* One pill moves from tab to tab. This shows where you are, and where you go. */}
              {tab === k && <motion.span layoutId="tabpill" className="tabpill" transition={{ type: "spring", stiffness: 520, damping: 40 }} />}
              <Icon name={icon} size={16} />
              <span className="tl">{label}</span>
            </button>
          ))}
          {moreTabs.length > 0 && (
            <button role="tab" aria-selected={moreActive} aria-haspopup="dialog" aria-expanded={more} aria-label="More" title="More" onClick={() => { setMore(!more); tap(); }}>
              {moreActive && <motion.span layoutId="tabpill" className="tabpill" transition={{ type: "spring", stiffness: 520, damping: 40 }} />}
              <Icon name="dots" size={16} />
              <span className="tl">More</span>
            </button>
          )}
        </nav>
        <div className="bar-end">
          {on("simple") && <LevelToggle />}
          {!phone && <ThemeToggle />}
        </div>
      </header>
      <MoreSheet open={more} tabs={moreTabs} current={tab} onPick={go} onClose={() => setMore(false)} />

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
            <button className="link" onClick={() => setNotice("")}>
              Close
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {on("direction") && <ThesisBar project={project} onSave={saveThesis} onOpenHelper={() => setTab("project")} />}

      {/* On a phone the library is a drawer. A tap outside it closes it. */}
      <button className={"scrim" + (libOpen ? " on" : "")} tabIndex={-1} aria-hidden="true" onClick={closeLib} />
      <div className={"layout" + (libOpen ? "" : " collapsed")}>
        <Library
          papers={papers}
          selectedId={selected}
          config={config}
          subQuestions={on("direction") ? subQuestions : []}
          citeOn={on("cite")}
          findOn={on("findpapers")}
          onSelect={openPaper}
          onChanged={refresh}
          notify={setNotice}
          onClose={closeLib}
        />
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
                subQuestions={on("direction") ? subQuestions : []}
                tags={paperTags}
                parts={{ feynman: on("feynman"), eli12: on("eli12"), quiz: on("quiz"), duck: on("duck"), boss: on("quests"), cite: on("cite"), critique: on("critique") }}
                onHideDuck={async () => {
                  try {
                    setFeatures(await api.setFeatures({ duck: false }));
                  } catch (e) {
                    setNotice(e.message);
                  }
                }}
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
                      <span>Use the Library. Write a focus topic if you need only one part.</span>
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
          {page === "today" && <Today papers={papers} onAction={goAction} gameOn={on("game")} reviewOn={on("review")} questsOn={on("quests") && on("game")} planOn={on("plan")} onOpenReview={() => setTab("review")} notify={setNotice} />}
          {page === "review" && <Review notify={setNotice} />}
          {page === "write" && <Write notify={setNotice} onChanged={() => {}} gapsOn={on("gaps")} coachOn={on("coach")} />}
          {page === "journey" && <Journey notify={setNotice} avatarOn={on("avatar")} playOn={on("play")} mapOn={on("map")} gameOn={on("game")} questsOn={on("quests") && on("game")} onGo={(target) => setTab(hidden[target] ? "cards" : target)} />}
          {page === "glossary" && <Glossary reloadKey={glossKey} notify={setNotice} />}
          {page === "toread" && <ToRead onChanged={refresh} notify={setNotice} suggestOn={on("suggest")} />}
          {page === "plan" && <Plan notify={setNotice} papers={papers} />}
          {tab === "search" && <Search onOpenCard={openPaper} notify={setNotice} />}
          {tab === "links" && <Graph onOpenCard={openPaper} notify={setNotice} />}
          {page === "project" && <Project project={project} subQuestions={subQuestions} onProject={changeProject} onSubQuestions={setSubQuestions} notify={setNotice} />}
          {tab === "settings" && (
            <Settings
              config={config}
              project={on("direction") ? project : null}
              onProject={changeProject}
              features={features}
              onFeatures={(list) => {
                setFeatures(list);
                api.subQuestions().then(setSubQuestions).catch(() => setSubQuestions([])); // the list is empty while the feature is off
              }}
              onConfig={setConfig}
              onImported={refresh}
              onLogout={() => {
                api.signOut();
                setAuthed(false);
              }}
              notify={setNotice}
            />
          )}
              </motion.div>
            )}
          </AnimatePresence>
          {/* The chat stays mounted, so the conversation is not lost when you open a card */}
          {on("chat") && (
            <div hidden={page !== "chat"}>
              <Chat papers={papers} selectedId={selected} onOpenCard={openPaper} notify={setNotice} />
            </div>
          )}
        </main>
      </div>
      {on("game") && <GameWatcher tick={tab} />}
      {/* The word box. It opens when you select a word in a card or in the chat. */}
      <WordHelper paperId={on("glossary") && (page === "cards" || page === "chat") ? selected || "" : ""} notify={setNotice} onSaved={() => setGlossKey((k) => k + 1)} />
    </div>
  );
}
