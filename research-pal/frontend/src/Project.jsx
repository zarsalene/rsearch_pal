import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import { Icon } from "./icons.jsx";

const STEPS = ["Write your question", "FINER check", "Choose a version", "Sub-questions"];
const SCOPE = { ok: ["ok", "Scope: good"], too_wide: ["warn", "Scope: too wide"], too_vague: ["warn", "Scope: too vague"] };
const FIELD = { title: "Title", question: "Question" };

function Steps({ step, onGo, reached }) {
  return (
    <ol className="stepper" aria-label="Steps">
      {STEPS.map((s, i) => (
        <li key={s} className={i + 1 === step ? "cur" : i + 1 < step ? "done" : ""}>
          <button type="button" disabled={i + 1 > reached} aria-current={i + 1 === step ? "step" : undefined} onClick={() => onGo(i + 1)}>
            <span className="n">{i + 1}</span>
            <span className="sl">{s}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}

// The AI is a helper. Every AI text has a label, and nothing is saved before the student clicks Save.
function AiLabel({ children = "AI suggestion" }) {
  return <span className="ailabel">{children}</span>;
}

function FinerResult({ check }) {
  const allOk = check.finer.every((i) => i.rating === "ok") && check.scope.status === "ok";
  const [tone, scopeText] = SCOPE[check.scope.status] || SCOPE.ok;
  return (
    <>
      <ul className="finer" aria-label="FINER check">
        {check.finer.map((i) => (
          <li key={i.key}>
            <span className={"letter t-" + (i.rating === "ok" ? "ok" : "warn")} aria-hidden="true">
              {i.letter}
            </span>
            <div>
              <strong>
                {i.name}: {i.rating === "ok" ? "OK" : "Weak"}
              </strong>
              <p>{i.why}</p>
            </div>
          </li>
        ))}
      </ul>
      <div className={"scope t-" + tone} role="status">
        <strong>{scopeText}</strong>
        {check.scope.why && <p>{check.scope.why}</p>}
      </div>
      <p className="small muted">
        <AiLabel>AI opinion</AiLabel> The AI gives its view. It can be wrong. You decide.
      </p>
      {allOk && <p className="goodnote">Your question looks good. You do not have to change it.</p>}
    </>
  );
}

function Coverage({ tick }) {
  const [cov, setCov] = useState(null);
  useEffect(() => {
    api.coverage().then(setCov).catch(() => setCov(null));
  }, [tick]);
  if (!cov?.sub_questions.length) return null;
  const text = (s) => (s.papers === 0 ? "No paper yet" : s.papers === 1 ? "1 paper" : `${s.papers} papers`);
  return (
    <section className="group" aria-label="Coverage">
      <h2>Coverage</h2>
      <p className="muted">How many papers help each sub-question. Link a paper to a sub-question on its card page.</p>
      <ul className="coverage">
        {cov.sub_questions.map((s, i) => (
          <li key={s.id}>
            <span className="cv-label">
              <strong>SQ{i + 1}</strong> {s.text}
            </span>
            <span className={"cv-bar l-" + s.level} role="img" aria-label={`SQ${i + 1}: ${text(s)}`}>
              {[0, 1, 2].map((k) => (
                <span key={k} className={k < s.papers ? "on" : ""} />
              ))}
            </span>
            <span className={"cv-n l-" + s.level}>{text(s)}</span>
          </li>
        ))}
      </ul>
      {cov.untagged > 0 && <p className="small muted">{cov.untagged === 1 ? "1 paper has" : `${cov.untagged} papers have`} no sub-question yet.</p>}
    </section>
  );
}

function History({ project }) {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    api.projectHistory().then(setRows).catch(() => setRows([]));
  }, [project?.title, project?.question]);
  if (!rows.length) return null;
  return (
    <section className="group" aria-label="History">
      <h2>History</h2>
      <p className="muted">Each change of your title or question. The newest is first.</p>
      <ol className="timeline">
        {rows.map((r) => (
          <li key={r.id}>
            <time dateTime={new Date(r.changed_at * 1000).toISOString()}>{new Date(r.changed_at * 1000).toLocaleString()}</time>
            <strong>{FIELD[r.field] || r.field}</strong>
            <p>{r.new_value || <em className="muted">(empty)</em>}</p>
            {r.old_value && <p className="small muted">Before: {r.old_value}</p>}
          </li>
        ))}
      </ol>
    </section>
  );
}

function SubRow({ index, count, s, onSave, onMove, onDelete }) {
  const [text, setText] = useState(s.text);
  useEffect(() => setText(s.text), [s.text]);
  const commit = () => {
    if (text.trim() && text.trim() !== s.text) onSave(s.id, text.trim());
    else setText(s.text);
  };
  return (
    <li className="subrow">
      <strong className="sqn">SQ{index + 1}</strong>
      <input type="text" value={text} maxLength={300} aria-label={`Sub-question ${index + 1}`} onChange={(e) => setText(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()} />
      <button className="iconbtn" disabled={index === 0} onClick={() => onMove(s.id, index - 1)} aria-label={`Move sub-question ${index + 1} up`}>
        <Icon name="arrowup" size={15} />
      </button>
      <button className="iconbtn" disabled={index === count - 1} onClick={() => onMove(s.id, index + 1)} aria-label={`Move sub-question ${index + 1} down`}>
        <span style={{ display: "inline-flex", transform: "rotate(180deg)" }}>
          <Icon name="arrowup" size={15} />
        </span>
      </button>
      <button className="iconbtn" onClick={() => onDelete(s)} aria-label={`Delete sub-question ${index + 1}`}>
        <Icon name="trash" size={15} />
      </button>
    </li>
  );
}

function SubQuestions({ project, subQuestions, reload, notify }) {
  const [suggest, setSuggest] = useState([]);
  const [busy, setBusy] = useState("");
  const [own, setOwn] = useState("");

  const run = async (name, fn) => {
    setBusy(name);
    try {
      return await fn();
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy("");
    }
  };
  const ask = () =>
    run("split", async () => {
      const r = await api.splitQuestion(project.question);
      setSuggest(r.sub_questions);
    });
  const add = (text) =>
    run("add", async () => {
      await api.addSubQuestion(text);
      await reload();
      return true;
    });

  return (
    <section className="group" aria-label="Sub-questions">
      <h2>Your sub-questions</h2>
      <p className="muted">Split the main question into 3 to 5 smaller questions. The answers to all of them answer your main question.</p>
      {subQuestions.length > 0 && (
        <ul className="sublist">
          {subQuestions.map((s, i) => (
            <SubRow
              key={s.id}
              index={i}
              count={subQuestions.length}
              s={s}
              onSave={(id, text) => run("edit", async () => { await api.editSubQuestion(id, { text }); await reload(); })}
              onMove={(id, position) => run("move", async () => { await api.editSubQuestion(id, { position }); await reload(); })}
              onDelete={(x) => confirm(`Delete SQ${i + 1}? The links of papers to it go too.`) && run("del", async () => { await api.deleteSubQuestion(x.id); await reload(); })}
            />
          ))}
        </ul>
      )}
      <form
        className="row addsub"
        onSubmit={async (e) => {
          e.preventDefault();
          if (own.trim() && (await add(own.trim()))) setOwn("");
        }}
      >
        <input type="text" maxLength={300} value={own} onChange={(e) => setOwn(e.target.value)} placeholder="Write a sub-question" aria-label="New sub-question" />
        <button className="btn small" disabled={!own.trim() || !!busy}>
          Add
        </button>
      </form>

      <div className="suggest">
        <button className="btn tint" disabled={!project.question || busy === "split"} onClick={ask}>
          <Icon name="sparkle" size={15} /> {busy === "split" ? "Thinking…" : "Suggest sub-questions"}
        </button>
        {!project.question && <span className="small muted"> Save your main question first.</span>}
        {suggest.length > 0 && (
          <ul className="suglist" aria-label="Suggested sub-questions">
            {suggest.map((s) => (
              <li key={s.text}>
                <span>
                  <AiLabel>{s.label}</AiLabel> {s.text}
                </span>
                <button
                  className="btn small ghost"
                  disabled={!!busy}
                  onClick={async () => {
                    if (await add(s.text)) setSuggest((l) => l.filter((x) => x.text !== s.text));
                  }}
                >
                  Add
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

// The question helper in steps. The AI checks and suggests. The student chooses and saves.
export default function Project({ project, subQuestions, onProject, onSubQuestions, notify }) {
  const [step, setStep] = useState(1);
  const [reached, setReached] = useState(1);
  const [draft, setDraft] = useState("");
  const [check, setCheck] = useState(null);
  const [choice, setChoice] = useState("");
  const [busy, setBusy] = useState(false);
  const [tick, setTick] = useState(0); // a new number makes the coverage load again

  useEffect(() => setDraft((d) => d || project?.question || ""), [project?.question]);

  const go = (n) => {
    setStep(n);
    setReached((r) => Math.max(r, n));
  };
  const reload = useCallback(async () => {
    onSubQuestions(await api.subQuestions());
    setTick((t) => t + 1);
  }, [onSubQuestions]);

  const guard = async (fn) => {
    setBusy(true);
    try {
      return await fn();
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };
  const runCheck = () =>
    guard(async () => {
      const r = await api.questionCheck(draft);
      setCheck(r);
      setChoice(r.question);
      go(2);
    });
  // Save the question that the student chose, then go to the sub-questions.
  const saveQuestion = (text) =>
    guard(async () => {
      const p = await api.saveProject({ question: text });
      onProject(p);
      setDraft(p.question);
      go(4);
    });

  if (!project) return null;

  return (
    <section className="projectpage">
      <h1>Your thesis question</h1>
      <p className="lead">Write your question. The AI checks it and suggests narrower versions. You choose what to keep.</p>
      <Steps step={step} onGo={setStep} reached={reached} />

      {step === 1 && (
        <section className="group" aria-label="Step 1">
          <h2>1. Write your question</h2>
          <p className="muted">Write the main question of your thesis. It is fine if it is not perfect yet.</p>
          <textarea rows={3} maxLength={500} value={draft} onChange={(e) => setDraft(e.target.value)} aria-label="Your question" placeholder="Example: Do validation agents reduce false alarms in threat hunting?" />
          <div className="row">
            <button className="btn" disabled={busy || draft.trim().length < 5} onClick={runCheck}>
              {busy ? "Checking…" : "Check my question"}
            </button>
            {project.question && <button className="btn ghost" onClick={() => go(4)}>Go to the sub-questions</button>}
          </div>
        </section>
      )}

      {step === 2 && check && (
        <section className="group" aria-label="Step 2">
          <h2>2. FINER check</h2>
          <blockquote className="yourq">{check.question}</blockquote>
          <FinerResult check={check} />
          <div className="row">
            <button className="btn" onClick={() => go(3)}>
              See narrower versions
            </button>
            <button className="btn ghost" disabled={busy} onClick={() => saveQuestion(check.question)}>
              Keep my question
            </button>
            <button className="btn ghost" onClick={() => setStep(1)}>
              Edit my question
            </button>
          </div>
        </section>
      )}

      {step === 3 && check && (
        <section className="group" aria-label="Step 3">
          <h2>3. Choose a version</h2>
          <p className="muted">
            <AiLabel /> These versions are ideas. Choose one, or keep your own. You can edit the text before you save.
          </p>
          <div className="versions" role="radiogroup" aria-label="Versions of your question">
            {[{ text: check.question, label: "Your question" }, ...check.versions].map((v, i) => (
              <label key={i} className={"version" + (choice === v.text ? " on" : "")}>
                <input type="radio" name="version" checked={choice === v.text} onChange={() => setChoice(v.text)} />
                <span>
                  {v.label === "Your question" ? <span className="ailabel mine">Your question</span> : <AiLabel>{v.label}</AiLabel>} {v.text}
                </span>
              </label>
            ))}
          </div>
          <label htmlFor="choice" className="field-label">
            Your main question
          </label>
          <textarea id="choice" rows={3} maxLength={500} value={choice} onChange={(e) => setChoice(e.target.value)} />
          <div className="row">
            <button className="btn" disabled={busy || choice.trim().length < 5} onClick={() => saveQuestion(choice)}>
              {busy ? "Saving…" : "Save as my main question"}
            </button>
            <button className="btn ghost" onClick={() => setStep(2)}>
              Back
            </button>
          </div>
        </section>
      )}

      {step === 4 && (
        <>
          <div className="mainq">
            <span className="eyebrow">Your main question</span>
            <p>{project.question || "Not written yet."}</p>
            <button className="link" onClick={() => setStep(1)}>
              Change it
            </button>
          </div>
          <SubQuestions project={project} subQuestions={subQuestions} reload={reload} notify={notify} />
        </>
      )}

      <Coverage tick={tick} />
      <History project={project} />
    </section>
  );
}
