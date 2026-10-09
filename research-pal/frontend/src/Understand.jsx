import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import { Icon } from "./icons.jsx";

const MARKS = [
  ["correct", "Correct"],
  ["partly", "Partly correct"],
  ["wrong", "Wrong"],
  ["not_in_paper", "Not in the paper"],
  ["cannot_check", "Cannot check"],
];
const MARK_BADGE = { correct: "b-ok", partly: "b-warn", wrong: "b-bad", not_in_paper: "b-info", cannot_check: "b-muted" };

// The text of the student, claim by claim. The color shows the mark. A click opens the proof.
export function ClaimText({ claims, activeId, onPick }) {
  return (
    <p className="claimtext">
      {claims.map((c) => (
        <button key={c.id} type="button" className={"claim mark-" + c.mark + (activeId === c.id ? " on" : "")} aria-pressed={activeId === c.id} title={c.label} aria-label={c.text + " (" + c.label + ")"} onClick={() => onPick(c.id)}>
          {c.text}
        </button>
      ))}{" "}
    </p>
  );
}

function PageChip({ paperId, page, notify }) {
  return (
    <button className="chip" title="Open the PDF at this page" onClick={() => api.openPdf(paperId, page).catch((e) => notify(e.message))}>
      p. {page}
    </button>
  );
}

function ClaimDetail({ claim, paperId, notify }) {
  return (
    <div className="claimdetail" role="region" aria-label="Proof for the selected claim">
      <span className={"badge " + MARK_BADGE[claim.mark]}>{claim.label}</span>
      <p className="answer small-answer">{claim.comment}</p>
      {claim.verified && claim.quote && (
        <div className="evidence">
          <blockquote>
            <span>{claim.quote}</span>
            <PageChip paperId={paperId} page={claim.page} notify={notify} />
          </blockquote>
        </div>
      )}
      {claim.source === "server" && <p className="small muted">The server checked the numbers in the text of the PDF.</p>}
      {claim.mark === "not_in_paper" && <p className="small muted">This is an opinion of the AI. Check it in the paper yourself.</p>}
      {claim.mark === "cannot_check" && <p className="small muted">The server shows no mark here, because it found no proof in the PDF.</p>}
    </div>
  );
}

export function ExplainResult({ result, paperId, notify }) {
  const [active, setActive] = useState(null);
  useEffect(() => setActive(null), [result.id]);
  const claim = result.claims.find((c) => c.id === active);
  return (
    <div className="explain-result">
      <div className="scorebar">
        <strong className="score" aria-label={`Score ${result.score} of 100`}>
          {result.score}
          <span>/100</span>
        </strong>
        <p className="kindmsg">{result.message}</p>
      </div>
      {result.xp_gained > 0 && <p className="xpnote">+{result.xp_gained} points. A Feynman check passed. Well done.</p>}
      <h3>Your explanation</h3>
      <ClaimText claims={result.claims} activeId={active} onPick={setActive} />
      <div className="marklegend">
        {MARKS.filter(([k]) => result.counts?.[k]).map(([k, label]) => (
          <span key={k} className={"claim mark-" + k + " legend"}>
            {label}: {result.counts[k]}
          </span>
        ))}
      </div>
      {claim ? <ClaimDetail claim={claim} paperId={paperId} notify={notify} /> : <p className="small muted">Click a colored sentence to see why.</p>}
      {result.missing.length > 0 && (
        <div className="missing">
          <h3>Points that you did not mention</h3>
          <ul>
            {result.missing.map((m) => (
              <li key={m.field}>
                <strong>{m.label}:</strong> {m.answer} {m.page > 0 && <PageChip paperId={paperId} page={m.page} notify={notify} />}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function when(t) {
  return new Date(t * 1000).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function Explain({ paperId, cardId, notify }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await api.explanations(paperId, cardId));
    } catch (e) {
      notify(e.message);
    }
  }, [paperId, cardId, notify]);
  useEffect(() => {
    setResult(null);
    loadHistory();
  }, [loadHistory]);

  const check = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      setResult(await api.explain(paperId, text, cardId));
      await loadHistory();
    } catch (err) {
      notify(err.message);
    } finally {
      setBusy(false);
    }
  };
  const remove = async (id) => {
    try {
      await api.deleteExplanation(id);
      if (result?.id === id) setResult(null);
      await loadHistory();
    } catch (e) {
      notify(e.message);
    }
  };

  return (
    <div>
      <p className="lead">Explain the main idea of the paper in your own words. Do not copy from the PDF. The AI shows what is right and what is missing. You write the text, not the AI.</p>
      <form onSubmit={check}>
        <label htmlFor="explain-text" className="field-label">
          Your explanation
        </label>
        <textarea id="explain-text" rows={7} maxLength={3000} value={text} onChange={(e) => setText(e.target.value)} placeholder="Example: The authors build a system with two agents. The first agent proposes attacks. The second agent tests them." />
        <div className="row">
          <button className="btn" disabled={busy || text.trim().length < 10}>
            {busy ? "Checking…" : "Check my explanation"}
          </button>
          <span className="small muted">{text.length} of 3000 characters</span>
        </div>
      </form>
      {result && <ExplainResult result={result} paperId={paperId} notify={notify} />}
      {history.length > 0 && (
        <div className="history">
          <h3>Your attempts</h3>
          <p className="small muted" aria-label="Scores in time order">
            Progress: {[...history].reverse().map((h) => h.score).join(" → ")}
          </p>
          <ul>
            {history.map((h) => (
              <li key={h.id}>
                <span className="small muted">{when(h.created_at)}</span> <strong>{h.score}/100</strong>
                <span className="htext">{h.text.slice(0, 90)}{h.text.length > 90 ? "…" : ""}</span>
                <button className="link" onClick={() => setResult(h.result)}>
                  Show
                </button>
                <button className="link" onClick={() => remove(h.id)} aria-label={`Delete the attempt of ${when(h.created_at)}`}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

const ELI_FIELDS = ["problem", "method", "result", "limitation", "use"];
const FIELD_LABEL = { problem: "Problem", method: "Method", result: "Result", limitation: "Limitation", use: "Use", verdict_reason: "Verdict" };

function Eli12({ paperId, cardId, card, notify }) {
  const options = [...ELI_FIELDS.filter((k) => {
    const f = card?.fields?.[k];
    return f?.answer && ["verified", "check", "suggestion"].includes(f.status) && !f.edited;
  }), ...(card?.verdict_reason ? ["verdict_reason"] : [])];
  const [field, setField] = useState(options[0] || "");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  useEffect(() => setRes(null), [field, cardId]);

  const go = async () => {
    setBusy(true);
    try {
      setRes(await api.eli12(paperId, field, cardId));
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };
  if (!options.length) return <p className="muted">This card has no checked text to explain yet.</p>;

  return (
    <div>
      <p className="lead">Choose one part of the card. You get a simple text, one example and one analogy. The simple text keeps the facts. The example and the analogy are ideas of the AI.</p>
      <div className="row">
        <label htmlFor="eli-field" className="small muted">
          Part of the card
        </label>
        <select id="eli-field" value={field} onChange={(e) => setField(e.target.value)}>
          {options.map((k) => (
            <option key={k} value={k}>
              {FIELD_LABEL[k]}
            </option>
          ))}
        </select>
        <button className="btn" disabled={busy || !field} onClick={go}>
          {busy ? "Explaining…" : "Explain it like I am 12"}
        </button>
      </div>
      {res && (
        <div className="eli-result">
          <h3>In simple words</h3>
          {res.simple.ok ? <p className="answer">{res.simple.text}</p> : <p className="muted">{res.simple.message}</p>}
          {res.term_line && <p className="small termline">{res.term_line}</p>}
          {res.example && (
            <>
              <h3>
                An example <span className="badge b-info">{res.example.label}</span>
              </h3>
              <p className="answer">{res.example.text}</p>
            </>
          )}
          {res.analogy && (
            <>
              <h3>
                An analogy <span className="badge b-info">{res.analogy.label}</span>
              </h3>
              <p className="answer">{res.analogy.text}</p>
            </>
          )}
          {(res.example || res.analogy) && <p className="small muted">The example and the analogy are not from the paper.</p>}
          <details>
            <summary className="small">The original text</summary>
            <p className="answer">{res.original}</p>
          </details>
        </div>
      )}
    </div>
  );
}

function Quiz({ paperId, cardId, notify }) {
  const [saved, setSaved] = useState([]);
  const [queue, setQueue] = useState([]); // the questions of this round
  const [i, setI] = useState(0);
  const [answer, setAnswer] = useState("");
  const [res, setRes] = useState(null);
  const [marks, setMarks] = useState([]);
  const [busy, setBusy] = useState("");
  const [note, setNote] = useState("");

  const loadSaved = useCallback(async () => {
    try {
      setSaved(await api.quizList(paperId));
    } catch (e) {
      notify(e.message);
    }
  }, [paperId, notify]);
  useEffect(() => {
    setQueue([]);
    setI(0);
    setMarks([]);
    setRes(null);
    loadSaved();
  }, [loadSaved, cardId]);

  const start = (qs) => {
    setQueue(qs);
    setI(0);
    setMarks([]);
    setRes(null);
    setAnswer("");
    setNote("");
  };
  const make = async () => {
    setBusy("make");
    try {
      const out = await api.makeQuiz(paperId, cardId);
      if (out.questions.length) start(out.questions);
      else setNote(out.message || "There are no new questions. Practice your saved questions.");
      await loadSaved();
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy("");
    }
  };
  const submit = async (e) => {
    e.preventDefault();
    setBusy("answer");
    try {
      const r = await api.answerQuiz(queue[i].id, answer);
      setRes(r);
      setMarks((m) => [...m, r.mark]);
      await loadSaved();
    } catch (err) {
      notify(err.message);
    } finally {
      setBusy("");
    }
  };
  const next = () => {
    setI(i + 1);
    setRes(null);
    setAnswer("");
  };

  const done = queue.length > 0 && i >= queue.length;
  const good = marks.filter((m) => m === "correct").length;
  return (
    <div>
      <p className="lead">Answer from memory. Then the app shows the correct answer, with the quote and the page of the paper.</p>
      {!queue.length && (
        <div className="row">
          <button className="btn" disabled={!!busy} onClick={make}>
            {busy === "make" ? "Making questions…" : "Make new questions"}
          </button>
          {saved.length > 0 && (
            <button className="btn ghost" disabled={!!busy} onClick={() => start(saved)}>
              Practice {saved.length} saved {saved.length === 1 ? "question" : "questions"}
            </button>
          )}
        </div>
      )}
      {note && <p className="muted" role="status">{note}</p>}
      {queue.length > 0 && !done && (
        <form onSubmit={submit} className="quizcard">
          <p className="small muted">
            Question {i + 1} of {queue.length}
          </p>
          <h3 className="quizq">{queue[i].question}</h3>
          {!res && (
            <>
              <textarea rows={3} maxLength={1000} value={answer} onChange={(e) => setAnswer(e.target.value)} aria-label="Your answer" placeholder="Write your answer from memory." autoFocus />
              <div className="row">
                <button className="btn" disabled={busy === "answer" || !answer.trim()}>
                  {busy === "answer" ? "Checking…" : "Check my answer"}
                </button>
              </div>
            </>
          )}
          {res && (
            <div className="quizres">
              <span className={"badge " + MARK_BADGE[res.mark]}>{res.label}</span>
              <p>{res.comment}</p>
              <p>
                <strong>Correct answer:</strong> {res.correct_answer}
              </p>
              <div className="evidence">
                <blockquote>
                  <span>{res.quote}</span>
                  <PageChip paperId={paperId} page={res.page} notify={notify} />
                </blockquote>
              </div>
              <div className="row">
                <button type="button" className="btn" onClick={next} autoFocus>
                  {i + 1 < queue.length ? "Next question" : "See the result"}
                </button>
              </div>
            </div>
          )}
        </form>
      )}
      {done && (
        <div className="quizdone" role="status">
          <h3>Result</h3>
          <p>
            {good} of {queue.length} {queue.length === 1 ? "answer was" : "answers were"} correct.{" "}
            {good === queue.length ? "Well done." : "Good work. Read the quotes again, then try once more."}
          </p>
          <div className="row">
            <button className="btn" onClick={() => start(saved.length ? saved : queue)}>
              Practice again
            </button>
            <button className="btn ghost" onClick={() => setQueue([])}>
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// The card page has a tab "Understand" with three parts. A part that is switched off in Settings has no tab.
export default function Understand({ paperId, cardId, card, parts, notify }) {
  const all = [
    ["feynman", "Explain it to me"],
    ["eli12", "Like I am 12"],
    ["quiz", "Quiz me"],
  ].filter(([k]) => parts[k]);
  const [part, setPart] = useState(all[0]?.[0] || "");
  const current = all.some(([k]) => k === part) ? part : all[0]?.[0];
  if (!current) return <p className="muted">All parts of Understand are switched off. Switch them on in Settings → Features.</p>;
  return (
    <section className="understand" aria-label="Understand this paper">
      <div className="subtabs" role="tablist" aria-label="Ways to understand the paper">
        {all.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={current === k} onClick={() => setPart(k)}>
            {label}
          </button>
        ))}
      </div>
      {current === "feynman" && <Explain paperId={paperId} cardId={cardId} notify={notify} />}
      {current === "eli12" && <Eli12 paperId={paperId} cardId={cardId} card={card} notify={notify} />}
      {current === "quiz" && <Quiz paperId={paperId} cardId={cardId} notify={notify} />}
    </section>
  );
}
