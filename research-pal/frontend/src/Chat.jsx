import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api.js";
import { Icon, Logo } from "./icons.jsx";
import SimpleText from "./SimpleText.jsx";

const MAX_PAPERS = 10;
const STATUS = {
  verified: ["ok", "Checked in the papers"],
  check: ["warn", "Check the numbers"],
  unverified: ["bad", "Not verified. No quote was found in the PDF."],
  no_evidence: ["muted", "No proof found"],
};
const EXAMPLES = ["What problem does this paper solve?", "Which datasets and metrics do they use?", "Compare the methods of the selected papers."];

function Bubble({ m, papers, picked, onAdd, notify, onOpenCard }) {
  const [badge, label] = STATUS[m.status] || ["muted", m.status];
  const canAdd = m.status === "verified" || m.status === "check";
  const firstOk = m.evidence.find((e) => e.verified)?.paper_id;
  const [target, setTarget] = useState(firstOk && picked.includes(firstOk) ? firstOk : picked[0] || "");
  const titleOf = (id) => papers.find((p) => p.id === id)?.title || "this paper";
  const options = papers.filter((p) => picked.includes(p.id) || p.id === firstOk);

  return (
    <div className="msg bot">
      <Logo size={26} />
      <div className="bubble">
        <span className={"badge b-" + badge}>{label}</span>
        <SimpleText text={m.answer} load={() => api.simplifyText(m.answer)} className={"answer" + (canAdd ? "" : " muted")} />
        {m.unverified_numbers?.length > 0 && (
          <p className="warn-line">Not found in the papers: {m.unverified_numbers.join(", ")}. Compare with the tables before you use this.</p>
        )}
        {m.evidence.length > 0 && (
          <div className="evidence">
            {m.evidence.map((e, i) => (
              <blockquote key={i} className={e.verified ? "" : "q-bad"}>
                <span>{e.quote}</span>
                {e.verified ? (
                  <button className="chip" title="Open the PDF at this page" onClick={() => api.openPdf(e.paper_id, e.page).catch((x) => notify(x.message))}>
                    {picked.length > 1 ? `${e.title.slice(0, 28)}${e.title.length > 28 ? "…" : ""} · ` : ""}p. {e.page}
                  </button>
                ) : (
                  <span className="chip bad">Quote not found in the PDF</span>
                )}
              </blockquote>
            ))}
          </div>
        )}
        {canAdd && (
          <div className="addbar">
            {m.added.map((id) => (
              <span key={id} className="added">
                <Icon name="check" size={15} /> Added to “{titleOf(id).slice(0, 40)}”{" "}
                <button className="link" onClick={() => onOpenCard(id)}>
                  Open the card
                </button>
              </span>
            ))}
            {options.length > 0 && (
              <>
                {options.length > 1 && (
                  <select value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Card">
                    {options.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.title.slice(0, 60)}
                      </option>
                    ))}
                  </select>
                )}
                <button className="btn small tint" disabled={!target || m.added.includes(target)} onClick={() => onAdd(target)}>
                  <Icon name="plus" size={15} /> Add to {options.length > 1 ? "this card" : "the card"}
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Ask questions about the papers that you select. Add a good answer to a card as a note.
export default function Chat({ papers, selectedId, onOpenCard, notify }) {
  const ready = useMemo(() => papers.filter((p) => p.status === "ready"), [papers]);
  const [picked, setPicked] = useState([]);
  const touched = useRef(false);
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef(null);

  // Start with the paper that is open on the card, until the student chooses
  useEffect(() => {
    if (touched.current) return;
    const first = ready.find((p) => p.id === selectedId) || ready[0];
    setPicked(first ? [first.id] : []);
  }, [ready, selectedId]);
  const live = picked.filter((id) => ready.some((p) => p.id === id));

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [msgs, busy]);

  const toggle = (id) => {
    touched.current = true;
    setPicked((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : cur.length >= MAX_PAPERS ? cur : [...cur, id]));
  };
  const setAll = (ids) => {
    touched.current = true;
    setPicked(ids.slice(0, MAX_PAPERS));
  };

  const send = async (question) => {
    question = question.trim();
    if (question.length < 2 || busy || !live.length) return;
    const history = msgs.filter((m) => !m.error).map((m) => ({ role: m.role, content: m.role === "user" ? m.text : m.answer }));
    setMsgs((cur) => [...cur, { role: "user", text: question }]);
    setText("");
    setBusy(true);
    try {
      const r = await api.chat(question, live, history);
      setMsgs((cur) => [...cur, { role: "assistant", question, added: [], ...r }]);
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };

  const add = async (index, pid) => {
    const m = msgs[index];
    try {
      await api.addNote(pid, { question: m.question, answer: m.answer, evidence: m.evidence });
      setMsgs((cur) => cur.map((x, i) => (i === index ? { ...x, added: [...x.added, pid] } : x)));
    } catch (e) {
      notify(e.message);
    }
  };

  return (
    <section className="chat" data-words>
      <h1>Chat</h1>
      <p className="lead">Ask about the papers that you select. Each answer shows quotes from the PDFs. Add a good answer to a card as a note.</p>

      <details className="picker" open={!live.length || !msgs.length}>
        <summary>
          <Icon name="doc" size={16} /> {live.length ? `${live.length} paper${live.length > 1 ? "s" : ""} selected` : "Select the papers"}
        </summary>
        {ready.length === 0 ? (
          <p className="muted small">No paper is ready. Add a PDF on the left, then wait for its card.</p>
        ) : (
          <>
            <div className="row pick-actions">
              <button className="link" onClick={() => setAll(ready.map((p) => p.id))}>
                Select all
              </button>
              <button className="link" onClick={() => setAll([])}>
                Select none
              </button>
              <span className="muted small">Up to {MAX_PAPERS} papers</span>
            </div>
            <ul className="pick-list">
              {ready.map((p) => (
                <li key={p.id}>
                  <label>
                    <input type="checkbox" checked={live.includes(p.id)} onChange={() => toggle(p.id)} disabled={!live.includes(p.id) && live.length >= MAX_PAPERS} />
                    <span>{p.title}</span>
                  </label>
                </li>
              ))}
            </ul>
          </>
        )}
      </details>

      <div className="thread" aria-live="polite">
        {msgs.length === 0 && live.length > 0 && (
          <div className="sugg-q">
            {EXAMPLES.map((q) => (
              <button key={q} className="kwchip" onClick={() => send(q)}>
                {q}
              </button>
            ))}
          </div>
        )}
        {msgs.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="msg me">
              <div className="bubble">{m.text}</div>
            </div>
          ) : (
            <Bubble key={i} m={m} papers={ready} picked={live} onAdd={(pid) => add(i, pid)} notify={notify} onOpenCard={onOpenCard} />
          )
        )}
        {busy && (
          <div className="msg bot">
            <Logo size={26} />
            <div className="bubble thinking">
              <span className="typing" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
              The AI reads the passages…
            </div>
          </div>
        )}
        <div ref={end} />
      </div>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          send(text);
        }}
      >
        <input
          value={text}
          maxLength={1000}
          onChange={(e) => setText(e.target.value)}
          placeholder={live.length ? "Ask about the selected papers…" : "Select a paper first"}
          aria-label="Question"
          disabled={!live.length}
        />
        <button className="btn send" aria-label={busy ? "Reading" : "Ask"} title="Ask" disabled={busy || !live.length || text.trim().length < 2}>
          <Icon name="arrowup" size={18} />
        </button>
      </form>
      {msgs.length > 0 && (
        <button className="link clear" onClick={() => setMsgs([])}>
          Clear the chat
        </button>
      )}
    </section>
  );
}
