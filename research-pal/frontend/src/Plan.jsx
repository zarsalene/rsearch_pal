import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";

const KINDS = [
  ["idea", "Idea"],
  ["experiment", "Experiment"],
  ["decision", "Decision"],
  ["result", "Result"],
];
const MOODS = ["Very low", "Low", "Okay", "Good", "Very good"];

const fmt = (iso) => new Date(iso + "T12:00:00").toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });

// ------------------------------------------------------------------ weekly review
// Five short questions. Private: only you see the answers and the mood. A week without a review has no penalty.
export function WeeklyReview({ notify, onSaved, title = "Weekly review", compact = false }) {
  const [data, setData] = useState(null);
  const [f, setF] = useState({ done: "", blocked: "", learned: "", next_goal: "", mood: 3 });
  const [note, setNote] = useState("");
  const load = useCallback(
    () =>
      api
        .weeklyReview()
        .then((d) => {
          setData(d);
          if (d.this_week) setF({ done: d.this_week.done, blocked: d.this_week.blocked, learned: d.this_week.learned, next_goal: d.this_week.next_goal, mood: d.this_week.mood });
        })
        .catch((e) => notify(e.message)),
    [notify],
  );
  useEffect(() => {
    load();
  }, [load]);
  const save = async (e) => {
    e.preventDefault();
    try {
      const r = await api.saveReview(f);
      setNote(r.xp_gained ? `Saved. +${r.xp_gained} points. Well done.` : "Saved.");
      await load();
      onSaved?.();
    } catch (err) {
      notify(err.message);
    }
  };
  if (!data) return null;
  const Q = [
    ["done", "What did you do this week?"],
    ["blocked", "What blocked you?"],
    ["learned", "What did you learn?"],
    ["next_goal", "What is your goal for next week?"],
  ];
  return (
    <section className="today-block weekly" aria-label={title}>
      <h2>{title}</h2>
      {!compact && <p className="small muted">About 5 minutes. Only you see this. Your answers help you look back.</p>}
      <form onSubmit={save}>
        {Q.map(([k, label]) => (
          <div key={k} className="inwrap">
            <label htmlFor={"wr-" + k}>{label}</label>
            <textarea id={"wr-" + k} rows={2} maxLength={1000} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />
          </div>
        ))}
        <fieldset className="mood">
          <legend>How was the week?</legend>
          {MOODS.map((m, i) => (
            <label key={m} className={f.mood === i + 1 ? "on" : ""}>
              <input type="radio" name="mood" checked={f.mood === i + 1} onChange={() => setF({ ...f, mood: i + 1 })} /> {m}
            </label>
          ))}
        </fieldset>
        <button className="btn">{data.this_week ? "Update the review" : "Save the review"}</button>
        {note && (
          <span role="status" className="small ok">
            {" "}
            {note}
          </span>
        )}
      </form>
    </section>
  );
}

// Shows only from Friday, when this week has no review yet.
export function FridayReview({ notify, onSaved }) {
  const [due, setDue] = useState(false);
  useEffect(() => {
    api.weeklyReview().then((d) => setDue(d.due)).catch(() => {});
  }, []);
  return due ? <WeeklyReview notify={notify} onSaved={() => { setDue(false); onSaved?.(); }} title="Weekly review (5 minutes)" compact /> : null;
}

export function MoodChart({ reviews }) {
  if (reviews.length < 2) return <p className="small muted">The mood chart shows after 2 reviews. Only you see it.</p>;
  const W = 520, H = 110, P = 14;
  const pts = reviews.map((r, i) => [P + (i * (W - 2 * P)) / (reviews.length - 1), H - P - ((r.mood - 1) * (H - 2 * P)) / 4]);
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} className="moodchart" role="img" aria-label={`Mood by week: ${reviews.map((r) => `${r.week} ${MOODS[r.mood - 1]}`).join(", ")}`}>
        <polyline points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke="currentColor" strokeWidth="2" />
        {pts.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r="4" fill="currentColor" />
        ))}
      </svg>
      <figcaption className="small muted">Your mood in each week. Only you see this.</figcaption>
    </figure>
  );
}

// ------------------------------------------------------------------ timeline
function TimelineBar({ plan }) {
  const ms = plan.milestones;
  if (!ms.length) return null;
  const dates = [plan.today, ...ms.map((m) => m.due)].map((d) => new Date(d + "T12:00:00").getTime());
  const lo = Math.min(...dates), hi = Math.max(...dates);
  const pos = (iso) => (hi === lo ? 50 : 4 + (92 * (new Date(iso + "T12:00:00").getTime() - lo)) / (hi - lo));
  return (
    <div className="timeline" role="img" aria-label={`Timeline from today to ${fmt(ms[ms.length - 1].due)}: ${ms.map((m) => `${m.title} on ${fmt(m.due)}${m.done ? ", done" : ""}`).join("; ")}`}>
      <div className="tline" />
      <div className="tnow" style={{ left: pos(plan.today) + "%" }}>
        <span>Today</span>
      </div>
      {ms.map((m, i) => (
        <div key={m.id} className={"tmile" + (m.done ? " done" : "") + (i % 2 ? " low" : "")} style={{ left: pos(m.due) + "%" }}>
          <span className="tdot" />
          <span className="tlabel">
            {m.title}
            <small>{fmt(m.due)}</small>
          </span>
        </div>
      ))}
    </div>
  );
}

function Milestone({ m, onChange, notify }) {
  const [busy, setBusy] = useState(false);
  const [week, setWeek] = useState("");
  const [text, setText] = useState("");
  const run = async (fn) => {
    try {
      await fn();
      await onChange();
    } catch (e) {
      notify(e.message);
    }
  };
  const byWeek = {};
  for (const t of m.tasks) (byWeek[t.week] = byWeek[t.week] || []).push(t);
  return (
    <li className={"milestone" + (m.done ? " done" : "")}>
      <div className="row">
        <input type="checkbox" checked={m.done} aria-label={`Done: ${m.title}`} onChange={(e) => run(() => api.editMilestone(m.id, { done: e.target.checked }))} />
        <strong>{m.title}</strong>
        <label className="small muted">
          Due{" "}
          <input type="date" value={m.due} onChange={(e) => e.target.value && run(() => api.editMilestone(m.id, { due: e.target.value }))} aria-label={`Due date: ${m.title}`} />
        </label>
        <span className="small muted">
          {m.done ? "Done." : m.days_left >= 0 ? `${m.days_left} days left.` : "The date has passed. Change the date if your plan changed."} {m.tasks_done} of {m.tasks.length} tasks done.
        </span>
        <button className="btn small ghost" disabled={busy} onClick={async () => {
          setBusy(true);
          await run(() => api.splitMilestone(m.id));
          setBusy(false);
        }}>
          {busy ? "Planning…" : "Suggest weekly tasks"}
        </button>
        <button className="btn small ghost" onClick={() => confirm(`Delete the milestone "${m.title}" and its tasks?`) && run(() => api.deleteMilestone(m.id))}>
          Delete
        </button>
      </div>
      {Object.keys(byWeek).sort().map((w) => (
        <div key={w} className="tweek">
          <h4 className="small">Week of {fmt(w)}</h4>
          <ul>
            {byWeek[w].map((t) => (
              <li key={t.id}>
                <input type="checkbox" checked={t.done} aria-label={`Done: ${t.text}`} onChange={(e) => run(() => api.editTask(t.id, { done: e.target.checked }))} />
                <input
                  className="tasktext"
                  defaultValue={t.text}
                  aria-label={`Task: ${t.text}`}
                  onBlur={(e) => e.target.value.trim() && e.target.value !== t.text && run(() => api.editTask(t.id, { text: e.target.value }))}
                />
                {t.label && <span className="small tag">{t.label}</span>}
                <button className="iconbtn" aria-label={`Delete the task: ${t.text}`} onClick={() => run(() => api.deleteTask(t.id))}>
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault();
          if (!text.trim()) return;
          run(() => api.addTask(m.id, week || undefined, text)).then(() => setText(""));
        }}
      >
        <input type="text" value={text} placeholder="Add your own task" aria-label={`New task for ${m.title}`} onChange={(e) => setText(e.target.value)} />
        <input type="date" value={week} aria-label="Week of the task" onChange={(e) => setWeek(e.target.value)} />
        <button className="btn small ghost">Add</button>
      </form>
    </li>
  );
}

function Timeline({ notify, plan, reload }) {
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const add = async (e) => {
    e.preventDefault();
    try {
      await api.addMilestone(title, due);
      setTitle("");
      setDue("");
      reload();
    } catch (err) {
      notify(err.message);
    }
  };
  return (
    <section className="today-block" aria-label="Timeline">
      <h2>Timeline</h2>
      <p className="small muted">Your PhD road, from today to the defense. You own the plan. The AI only suggests weekly tasks, and you can change them.</p>
      {plan.milestones.length === 0 ? (
        <p>
          <button className="btn" onClick={() => api.makeDefaults().then(reload).catch((e) => notify(e.message))}>
            Make the milestones for my stage
          </button>{" "}
          <span className="small muted">You can change each one. Set your stage in Settings.</span>
        </p>
      ) : (
        <>
          <TimelineBar plan={plan} />
          <ol className="milestones">
            {plan.milestones.map((m) => (
              <Milestone key={m.id} m={m} onChange={reload} notify={notify} />
            ))}
          </ol>
        </>
      )}
      <form className="row" onSubmit={add}>
        <input type="text" value={title} placeholder="New milestone" aria-label="New milestone" onChange={(e) => setTitle(e.target.value)} />
        <input type="date" value={due} aria-label="Due date of the new milestone" onChange={(e) => setDue(e.target.value)} />
        <button className="btn small" disabled={!title.trim() || !due}>
          Add milestone
        </button>
      </form>
    </section>
  );
}

// ------------------------------------------------------------------ journal
function Journal({ notify, papers }) {
  const [entries, setEntries] = useState([]);
  const [kind, setKind] = useState("");
  const [f, setF] = useState({ kind: "idea", text: "", paper_ids: [] });
  const [note, setNote] = useState("");
  const load = useCallback(() => api.journal(kind).then(setEntries).catch((e) => notify(e.message)), [kind, notify]);
  useEffect(() => {
    load();
  }, [load]);
  const add = async (e) => {
    e.preventDefault();
    try {
      const r = await api.addJournal(f);
      setNote(r.xp_gained ? `Saved. +${r.xp_gained} points.` : "Saved.");
      setF({ ...f, text: "", paper_ids: [] });
      load();
    } catch (err) {
      notify(err.message);
    }
  };
  return (
    <section className="today-block" aria-label="Research journal">
      <h2>Research journal</h2>
      <p className="small muted">Write what you think, test, decide and find. In one year, you will know why you chose a method. Decisions fill the Method Workshop on the map. Experiments and results fill the Data Mines.</p>
      <form onSubmit={add}>
        <div className="row">
          <label className="small" htmlFor="jkind">
            Kind
          </label>
          <select id="jkind" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>
            {KINDS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <textarea rows={3} value={f.text} aria-label="Journal entry" placeholder="What happened? Why?" maxLength={2000} onChange={(e) => setF({ ...f, text: e.target.value })} />
        {papers.length > 0 && (
          <label className="small">
            Link a paper{" "}
            <select value="" aria-label="Link a paper" onChange={(e) => e.target.value && !f.paper_ids.includes(e.target.value) && setF({ ...f, paper_ids: [...f.paper_ids, e.target.value] })}>
              <option value="">Choose…</option>
              {papers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title || p.filename}
                </option>
              ))}
            </select>
          </label>
        )}
        {f.paper_ids.length > 0 && <span className="small muted"> Linked: {f.paper_ids.map((id) => papers.find((p) => p.id === id)?.title || id).join(", ")}</span>}{" "}
        <button className="btn small" disabled={!f.text.trim()}>
          Save the entry
        </button>
        {note && (
          <span role="status" className="small ok">
            {" "}
            {note}
          </span>
        )}
      </form>
      <div className="row">
        <label className="small muted" htmlFor="jfilter">
          Show
        </label>
        <select id="jfilter" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">All kinds</option>
          {KINDS.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </div>
      {entries.length === 0 ? (
        <p className="muted">No entry yet.</p>
      ) : (
        <ul className="journal">
          {entries.map((e) => (
            <li key={e.id}>
              <span className={"tag kind-" + e.kind}>{e.label}</span> <span className="small muted">{fmt(e.date)}</span>
              <p>{e.text}</p>
              {e.papers.length > 0 && <p className="small muted">Papers: {e.papers.map((p) => p.title).join(", ")}</p>}
              <button className="link" onClick={() => confirm("Delete this entry?") && api.deleteJournal(e.id).then(load).catch((err) => notify(err.message))}>
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ the page
export default function Plan({ notify, papers = [] }) {
  const [plan, setPlan] = useState(null);
  const [reviews, setReviews] = useState([]);
  const load = useCallback(() => {
    api.plan().then(setPlan).catch((e) => notify(e.message));
    api.weeklyReview().then((d) => setReviews(d.reviews)).catch(() => {});
  }, [notify]);
  useEffect(() => {
    load();
  }, [load]);
  if (!plan) return <p className="muted">Loading…</p>;
  return (
    <section className="plan">
      <h1>Plan</h1>
      <Timeline notify={notify} plan={plan} reload={load} />
      <WeeklyReview notify={notify} onSaved={load} />
      <section className="today-block" aria-label="Mood">
        <h2>Your weeks</h2>
        <MoodChart reviews={reviews} />
      </section>
      <Journal notify={notify} papers={papers} />
    </section>
  );
}
