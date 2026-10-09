import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { Icon } from "./icons.jsx";

// Put a quote in the text, on its own line, at the place of the cursor. The line starts with ">" so that it is a quote, not your words.
export function insertQuote(text, pos, quote, cite) {
  const before = text.slice(0, pos), after = text.slice(pos);
  const lead = before && !before.endsWith("\n") ? "\n" : "";
  const tail = after && !after.startsWith("\n") ? "\n" : "";
  const line = `> ${quote} ${cite}`;
  return { text: before + lead + line + "\n" + tail + after, pos: (before + lead + line + "\n").length };
}

export const citeStyle = () => {
  try {
    return localStorage.getItem("rp-cite-style") === "ieee" ? "ieee" : "apa";
  } catch {
    return "apa";
  }
};

function Sources({ section, onInsert }) {
  if (!section.sub_question_id) return <p className="small muted">This section has no sub-question. Add quotes by hand, or use the Copy citation button on a card.</p>;
  if (!section.sources.length) return <p className="small muted">No card has the tag of this sub-question yet. Open a card and tag it.</p>;
  return (
    <div className="sources">
      {section.sources.map((g) => (
        <div key={g.relation} className="srcgroup">
          <h4>{g.label}</h4>
          {g.cards.map((c) => (
            <div key={c.paper_id + c.card_id} className="srccard">
              <strong className="small">{c.title}</strong>
              {c.quotes.length === 0 && <p className="small muted">This card has no checked quote.</p>}
              {c.quotes.map((q, i) => (
                <blockquote key={i}>
                  <span>{q.quote}</span>
                  <span className="small muted">
                    {q.label} · {q.cite}
                    {!q.complete && " · check the metadata"}
                  </span>
                  <button className="btn small ghost" onClick={() => onInsert(q)} aria-label={`Insert quote: ${q.quote.slice(0, 40)}`}>
                    Insert
                  </button>
                </blockquote>
              ))}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

const draftKey = (id) => "rp-draft-" + id;
const readDraft = (id) => {
  try {
    return localStorage.getItem(draftKey(id));
  } catch {
    return null;
  }
};
const writeDraft = (id, text) => {
  try {
    text === null ? localStorage.removeItem(draftKey(id)) : localStorage.setItem(draftKey(id), text);
  } catch {
    /* private mode */
  }
};

export default function Write({ notify, onChanged }) {
  const [doc, setDoc] = useState(null);
  const [selected, setSelected] = useState("");
  const [text, setText] = useState("");
  const [status, setStatus] = useState("");
  const [style, setStyle] = useState(citeStyle);
  const [dragId, setDragId] = useState("");
  const area = useRef(null);
  const timer = useRef(null);
  const current = doc?.sections.find((s) => s.id === selected);

  const load = useCallback(
    async (keep) => {
      try {
        const d = await api.reviewDoc(style);
        setDoc(d);
        const id = keep && d.sections.some((s) => s.id === keep) ? keep : d.sections[0]?.id || "";
        setSelected(id);
        const s = d.sections.find((x) => x.id === id);
        const draft = id ? readDraft(id) : null; // a draft that was not saved (the tab closed too fast) comes back
        setText(draft !== null && s && draft !== s.text ? draft : s?.text || "");
      } catch (e) {
        notify(e.message);
      }
    },
    [style, notify],
  );
  useEffect(() => {
    load(selected);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [style]);

  const save = useCallback(
    async (id, value) => {
      setStatus("Saving…");
      try {
        const r = await api.saveSection(id, { text: value });
        writeDraft(id, null);
        setDoc((d) => d && { ...d, sections: d.sections.map((s) => (s.id === id ? { ...s, text: value, words: r.words, unverified_quotes: r.unverified_quotes } : s)) });
        setStatus("Saved");
        onChanged?.();
      } catch (e) {
        setStatus("Not saved. Your text is kept in this browser.");
        notify(e.message);
      }
    },
    [notify, onChanged],
  );

  const change = (value) => {
    setText(value);
    setStatus("Writing…");
    writeDraft(selected, value);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => save(selected, value), 800);
  };
  const flush = () => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
      if (selected && current && text !== current.text) save(selected, text);
    }
  };
  useEffect(() => () => clearTimeout(timer.current), []);

  const pick = (id) => {
    flush();
    setSelected(id);
    const s = doc.sections.find((x) => x.id === id);
    const draft = readDraft(id);
    setText(draft !== null && draft !== s.text ? draft : s.text);
    setStatus("");
  };
  const run = async (fn, keep) => {
    flush();
    try {
      setDoc(await fn());
      await load(keep);
    } catch (e) {
      notify(e.message);
    }
  };
  const insert = (q) => {
    const pos = area.current ? area.current.selectionStart : text.length;
    const r = insertQuote(text, pos, q.quote, q.cite);
    change(r.text);
    setTimeout(() => area.current?.setSelectionRange(r.pos, r.pos), 0);
  };
  const move = (id, to) => {
    const ids = doc.sections.map((s) => s.id);
    const from = ids.indexOf(id);
    if (to < 0 || to >= ids.length || from === to) return;
    ids.splice(to, 0, ids.splice(from, 1)[0]);
    run(() => api.orderSections(ids), selected);
  };
  const addSection = async () => {
    const heading = prompt("Heading of the new section");
    if (!heading) return;
    try {
      const s = await api.addSection(heading);
      await load(s.id);
    } catch (e) {
      notify(e.message);
    }
  };

  if (!doc) return <p className="muted">Loading…</p>;
  return (
    <section className="write">
      <header className="write-head">
        <h1>{doc.doc.title}</h1>
        <span className="small muted">{doc.words} words in all</span>
        <label className="small muted" htmlFor="cite-style">
          Citation style
        </label>
        <select
          id="cite-style"
          value={style}
          onChange={(e) => {
            try {
              localStorage.setItem("rp-cite-style", e.target.value);
            } catch {
              /* private mode */
            }
            setStyle(e.target.value);
          }}
        >
          <option value="apa">APA</option>
          <option value="ieee">IEEE</option>
        </select>
        <button className="btn small ghost" onClick={() => api.download(`/api/review-doc/export?format=md&style=${style}`, "literature-review.md").catch((e) => notify(e.message))}>
          <Icon name="download" size={14} /> Export Markdown
        </button>
        <button className="btn small ghost" onClick={() => api.download(`/api/review-doc/export?format=docx&style=${style}`, "literature-review.docx").catch((e) => notify(e.message))}>
          <Icon name="download" size={14} /> Export Word
        </button>
      </header>
      <p className="lead">You write the text. The app gives you the headings, your cards and their checked quotes. A line that starts with “&gt;” is a quote. It does not count as your words.</p>

      <div className="write-grid">
        <nav className="outline" aria-label="Outline">
          <div className="row">
            <button className="btn small" onClick={() => run(() => api.makeOutline(), selected)}>
              Make the outline
            </button>
            <button className="btn small ghost" onClick={addSection}>
              Add a section
            </button>
          </div>
          {doc.sections.length === 0 && <p className="small muted">No section yet. Click “Make the outline”. It makes one section for each sub-question.</p>}
          <ol>
            {doc.sections.map((s, i) => (
              <li
                key={s.id}
                draggable
                onDragStart={() => setDragId(s.id)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => dragId && move(dragId, i)}
                className={s.id === selected ? "sel" : ""}
              >
                <button className="osec" onClick={() => pick(s.id)} aria-current={s.id === selected ? "true" : undefined}>
                  <span>{s.heading}</span>
                  <span className="small muted">{s.words} words</span>
                </button>
                <span className="omove">
                  <button className="iconbtn" aria-label={`Move up: ${s.heading}`} disabled={i === 0} onClick={() => move(s.id, i - 1)}>
                    <Icon name="arrowup" size={13} />
                  </button>
                  <button className="iconbtn" aria-label={`Move down: ${s.heading}`} disabled={i === doc.sections.length - 1} onClick={() => move(s.id, i + 1)}>
                    <Icon name="arrow" size={13} className="down" />
                  </button>
                  <button
                    className="iconbtn"
                    aria-label={`Delete the section: ${s.heading}`}
                    onClick={() => confirm(`Delete the section "${s.heading}" and its text?`) && run(() => api.deleteSection(s.id).then(() => api.reviewDoc(style)), "")}
                  >
                    <Icon name="trash" size={13} />
                  </button>
                </span>
              </li>
            ))}
          </ol>
        </nav>

        <div className="editor">
          {current ? (
            <>
              <h2>{current.heading}</h2>
              <label htmlFor="section-text" className="small muted">
                Your text
              </label>
              <textarea id="section-text" ref={area} rows={18} value={text} onChange={(e) => change(e.target.value)} onBlur={flush} spellCheck />
              <p className="small muted" role="status">
                {status} · {current.words} words
              </p>
              {current.unverified_quotes.length > 0 && (
                <p className="warn-line" role="alert">
                  {current.unverified_quotes.length === 1 ? "1 quote is" : `${current.unverified_quotes.length} quotes are`} not in your PDFs. You changed a quote, or it comes from another source. Check it.
                </p>
              )}
            </>
          ) : (
            <p className="muted">Choose a section on the left.</p>
          )}
        </div>

        <aside className="srcpanel" aria-label="Cards and quotes">
          <h3>Cards and quotes</h3>
          {current ? <Sources section={current} onInsert={insert} /> : <p className="small muted">Choose a section.</p>}
        </aside>
      </div>
    </section>
  );
}
