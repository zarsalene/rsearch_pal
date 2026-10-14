import { useState } from "react";
import { api } from "./api.js";
import { Icon } from "./icons.jsx";

// Mark the words of the query inside a passage, so the student sees at once why it matched.
function Highlight({ text, query }) {
  const words = [...new Set(query.toLowerCase().split(/\W+/).filter((w) => w.length >= 3))];
  if (!words.length) return text;
  const re = new RegExp(`(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  return text.split(re).map((part, i) => (i % 2 ? <mark key={i}>{part}</mark> : part));
}

export default function Search({ onOpenCard, notify }) {
  const [q, setQ] = useState("");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [asked, setAsked] = useState("");

  const go = async (e) => {
    e.preventDefault();
    if (q.trim().length < 2) return;
    setBusy(true);
    try {
      setRes(await api.search(q));
      setAsked(q);
    } catch (err) {
      notify(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section>
      <h1>Search</h1>
      <p className="lead">You get passages from your own PDFs, with the page number. The AI does not write these results, so they cannot be wrong facts.</p>
      <form onSubmit={go} className="searchfield">
        <Icon name="search" size={18} />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Example: how do they validate a hypothesis?" aria-label="Search" />
        <button className="btn" disabled={busy}>
          {busy ? "Searching…" : "Search"}
        </button>
      </form>
      {res && res.length === 0 && <p className="muted">No passage found. Upload more papers or use other words.</p>}
      <ul className="results">
        {(res || []).map((r, i) => (
          <li key={i}>
            <div className="rhead">
              <strong>{r.title}</strong>
              <span className="chip">p. {r.page}</span>
              <span className="match" title={`${Math.round(r.score * 100)}% match`}>
                <span className="bar" style={{ width: Math.max(8, Math.min(100, Math.round(r.score * 100))) + "%" }} />
              </span>
              <span className="muted small">{Math.round(r.score * 100)}% match</span>
            </div>
            <p className="passage">
              <Highlight text={r.text.length > 420 ? r.text.slice(0, 420) + "…" : r.text} query={asked} />
            </p>
            <div className="row">
              <button className="link" onClick={() => onOpenCard(r.paper_id)}>
                Open the card
              </button>
              <button className="link" onClick={() => api.openPdf(r.paper_id, r.page).catch((e) => notify(e.message))}>
                Open the PDF at page {r.page}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
