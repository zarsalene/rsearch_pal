import { useCallback, useEffect, useState } from "react";
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

const TABS = [
  ["cards", "Card", "doc"],
  ["chat", "Chat", "chat"],
  ["search", "Search", "search"],
  ["links", "Links", "graph"],
  ["project", "Thesis", "flag"],
  ["settings", "Settings", "sliders"],
];

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());
  const [tab, setTab] = useState("cards");
  const [papers, setPapers] = useState([]);
  const [selected, setSelected] = useState(null);
  const [config, setConfig] = useState(null);
  const [features, setFeatures] = useState(null);
  const [project, setProject] = useState(null); // the thesis: title, question, stage
  const [subQuestions, setSubQuestions] = useState([]);
  const [notice, setNotice] = useState("");
  // The library can open and close. The choice is saved in this browser.
  const [libOpen, setLibOpen] = useState(() => {
    try {
      return localStorage.getItem("rp-library") !== "closed";
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
  const shownTabs = TABS.filter(([k]) => (k !== "chat" || on("chat")) && (k !== "project" || on("direction")));
  const page = (tab === "chat" && !on("chat")) || (tab === "project" && !on("direction")) ? "cards" : tab;
  const paperTags = papers.find((p) => p.id === selected)?.tags || {};

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
          <button className={"iconbtn" + (libOpen ? " on" : "")} onClick={toggleLib} aria-expanded={libOpen} aria-controls="library" aria-label={libOpen ? "Close the library" : "Open the library"} title={libOpen ? "Close the library" : "Open the library"}>
            <Icon name="sidebar" size={18} />
          </button>
          <Logo size={26} />
          Research Pal
        </div>
        <nav className="tabs" role="tablist" aria-label="Sections">
          {shownTabs.map(([k, label, icon]) => (
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

      {on("direction") && <ThesisBar project={project} onSave={saveThesis} onOpenHelper={() => setTab("project")} />}

      <div className={"layout" + (libOpen ? "" : " collapsed")}>
        <Library
          papers={papers}
          selectedId={selected}
          config={config}
          subQuestions={on("direction") ? subQuestions : []}
          onSelect={openPaper}
          onChanged={refresh}
          notify={setNotice}
        />
        <main className="main">
          {page === "cards" &&
            (selected ? (
              <CardView
                key={selected}
                id={selected}
                subQuestions={on("direction") ? subQuestions : []}
                tags={paperTags}
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
