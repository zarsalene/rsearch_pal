import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import { Icon } from "./icons.jsx";

// The words that you looked up and saved. Each word shows where the explanation comes from.
export default function Glossary({ reloadKey, notify }) {
  const [items, setItems] = useState(null);
  const [q, setQ] = useState("");

  const load = useCallback(async () => {
    try {
      setItems(await api.glossary());
    } catch (e) {
      notify(e.message);
      setItems([]);
    }
  }, [notify]);
  useEffect(() => {
    load();
  }, [load, reloadKey]);

  const shown = (items || []).filter((g) => !q.trim() || `${g.term} ${g.explanation}`.toLowerCase().includes(q.trim().toLowerCase()));
  const remove = async (g) => {
    try {
      await api.deleteGlossary(g.id);
      setItems((list) => list.filter((x) => x.id !== g.id));
    } catch (e) {
      notify(e.message);
    }
  };

  return (
    <section className="glossary">
      <h1>Glossary</h1>
      <p className="lead">The words that you saved. Select a word in a card or in the chat to add one.</p>
      {items?.length > 0 && (
        <label className="filter">
          <Icon name="search" size={14} />
          <input type="text" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search your words…" aria-label="Search your words" />
        </label>
      )}
      {items === null && <p className="muted">Loading…</p>}
      {items?.length === 0 && (
        <div className="empty-list">
          <p>No word yet.</p>
          <p className="small muted">Open a card and select a word. A small box opens. Click “Save to glossary”.</p>
        </div>
      )}
      {items?.length > 0 && !shown.length && <p className="muted">No word matches “{q}”.</p>}
      <ul className="gloss-list">
        {shown.map((g) => (
          <li key={g.id} className="gloss-item">
            <div className="gloss-head">
              <h3>{g.term}</h3>
              <span className={"badge " + (g.source === "paper" ? "b-ok" : "b-info")}>{g.label}</span>
              {g.page > 0 && g.paper_title && (
                <button className="chip" title="Open the PDF at this page" onClick={() => api.openPdf(g.paper_id, g.page).catch((e) => notify(e.message))}>
                  p. {g.page}
                </button>
              )}
              <button className="link gloss-del" onClick={() => remove(g)} aria-label={`Delete ${g.term}`}>
                <Icon name="trash" size={14} /> Delete
              </button>
            </div>
            <p className="answer">{g.explanation}</p>
            {g.paper_title && <p className="small muted">From: {g.paper_title}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}
