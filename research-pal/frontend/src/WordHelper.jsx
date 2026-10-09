import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { Icon } from "./icons.jsx";

const MAX_CHARS = 80;
const MAX_WORDS = 5;
const BOX_HEIGHT = 260; // the height that the box needs at most, in pixels

// Select a word or a short term in a card or in the chat. A small box says what it means.
// The server looks in the paper first (label "From the paper"). If the paper has no definition, the AI explains it (label "AI explanation").
export default function WordHelper({ paperId, notify, onSaved }) {
  const [sel, setSel] = useState(null); // { term, x, y }
  const [res, setRes] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [busy, setBusy] = useState(false);
  const box = useRef(null);

  // Read the selection when the student lets go of the mouse. Only text inside an element with data-words counts.
  useEffect(() => {
    if (!paperId) return;
    const onUp = (e) => {
      if (box.current?.contains(e.target)) return;
      setTimeout(() => {
        const s = window.getSelection();
        const term = (s?.toString() || "").replace(/\s+/g, " ").trim();
        const node = s?.anchorNode?.nodeType === 1 ? s.anchorNode : s?.anchorNode?.parentElement;
        if (!s || s.isCollapsed || !term || term.length < 2 || term.length > MAX_CHARS || term.split(" ").length > MAX_WORDS || !node?.closest("[data-words]")) return;
        const r = s.getRangeAt(0).getBoundingClientRect();
        // The box goes under the word. It stays inside the window, so the buttons are always in reach.
        const y = r.bottom + 8 + BOX_HEIGHT > window.innerHeight ? Math.max(8, window.innerHeight - BOX_HEIGHT - 8) : r.bottom + 8;
        setSel({ term, x: Math.min(Math.max(r.left, 12), Math.max(12, window.innerWidth - 372)), y });
      }, 0);
    };
    const onKey = (e) => e.key === "Escape" && setSel(null);
    const onDown = (e) => {
      if (box.current && !box.current.contains(e.target)) setSel(null);
    };
    document.addEventListener("mouseup", onUp);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mouseup", onUp);
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [paperId]);

  useEffect(() => setSel(null), [paperId]);

  useEffect(() => {
    if (!sel) return;
    let alive = true;
    setRes(null);
    setError("");
    setSaved("");
    api
      .define(paperId, sel.term)
      .then((r) => alive && (setRes(r), setSaved(r.saved_id)))
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [sel?.term, paperId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!sel) return null;

  const save = async () => {
    setBusy(true);
    try {
      const g = await api.addGlossary(sel.term, paperId);
      setSaved(g.id);
      onSaved?.();
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="wordbox" ref={box} style={{ left: sel.x, top: sel.y }} role="dialog" aria-label={`Meaning of ${sel.term}`}>
      <div className="wordbox-head">
        <strong>{sel.term}</strong>
        <button className="iconbtn" onClick={() => setSel(null)} aria-label="Close the word box" title="Close (Esc)">
          <Icon name="x" size={14} />
        </button>
      </div>
      {!res && !error && (
        <p className="small muted" role="status">
          Looking for the meaning…
        </p>
      )}
      {error && <p className="err small" role="alert">{error}</p>}
      {res && (
        <>
          <div className="wordbox-label">
            <span className={"badge " + (res.source === "paper" ? "b-ok" : "b-info")}>{res.label}</span>
            {res.page > 0 && (
              <button className="chip" title="Open the PDF at this page" onClick={() => api.openPdf(paperId, res.page).catch((e) => notify(e.message))}>
                p. {res.page}
              </button>
            )}
          </div>
          <p className="wordbox-text">{res.explanation}</p>
          {res.source === "ai" && <p className="small muted">The AI wrote this. It is not from the paper.</p>}
          {res.source === "ai" && res.mentions?.length > 0 && (
            <p className="small muted">
              The paper uses this word on{" "}
              {[...new Set(res.mentions.map((m) => m.page))].map((p) => (
                <button key={p} className="chip" onClick={() => api.openPdf(paperId, p).catch((e) => notify(e.message))}>
                  p. {p}
                </button>
              ))}
            </p>
          )}
          {res.known && (
            <div className="row">
              <button className="btn small" disabled={busy || !!saved} onClick={save}>
                {saved ? "In your glossary" : busy ? "Saving…" : "Save to glossary"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
