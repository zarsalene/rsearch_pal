import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { api } from "./api.js";
import Duck from "./Duck.jsx";
import { say as duckSay, stage } from "./duck.js";
import { Icon } from "./icons.jsx";
import { confetti, play } from "./juice.js";
import { useApp } from "./store.js";

// The Semester Simulator. 12 weeks of research, 5 action points each week. The simulation runs on the server:
// the page sends only the choices. The knowledge at the start, the odds of a reviewer and the report come from the REAL work of the student.
// The simulation gives no XP, because XP is only for real work. It shows what the real work is worth.
const ICON = { read: "book", study: "target", experiment: "flask", write: "write", meet: "meet", network: "people", rest: "moon" };
const tone = (v) => (v >= 50 ? "ok" : v >= 25 ? "warn" : "bad");

function Bar({ label, value, kind }) {
  return (
    <div className="sbar">
      <span>{label}</span>
      <div className="sbar-track" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}>
        <motion.i className={"t-" + (kind || tone(value))} initial={false} animate={{ width: `${value}%` }} transition={{ type: "spring", stiffness: 180, damping: 24 }} />
      </div>
      <b>{value}</b>
    </div>
  );
}

function Weeks({ run }) {
  return (
    <ol className="weeks" aria-label={`Week ${run.week} of ${run.weeks}`}>
      {Array.from({ length: run.weeks }, (_, i) => {
        const w = i + 1;
        const ms = run.milestones.find((m) => m.week === w);
        const state = run.status !== "active" || w < run.week ? "past" : w === run.week ? "now" : "next";
        return (
          <li key={w} className={"wk " + state + (ms ? " ms" : "") + (ms?.done ? (ms.ok ? " ok" : " no") : "")} title={ms ? `Week ${w}: ${ms.label}` : `Week ${w}`}>
            {ms ? <Icon name="flag" size={12} weight="fill" /> : w}
          </li>
        );
      })}
    </ol>
  );
}

function Report({ run, records, onAgain, onBack }) {
  const r = run.report;
  const openBattle = useApp((s) => s.openBattle);
  const best = records.best;
  const record = r.progress >= best && records.runs > 0;
  return (
    <div className="report">
      <motion.div className={"grade g-" + r.grade} initial={{ scale: 0.4, rotate: -12, opacity: 0 }} animate={{ scale: 1, rotate: 0, opacity: 1 }} transition={{ type: "spring", stiffness: 220, damping: 14 }}>
        {r.grade}
      </motion.div>
      <div>
        <span className="eyebrow">{r.burnout ? "Burnout in week " + r.weeks_done : "Semester finished"}</span>
        <h2>Your thesis is {r.progress}% ready</h2>
        <p className="lead">{r.text}</p>
        {record && <span className="badge b-ok">New personal best</span>}
        {!record && records.runs > 1 && <span className="muted small">Your best: {records.best}%. You compare only with yourself.</span>}
      </div>
      <div className="rchapters">
        {Object.entries(run.chapter_names).map(([k, name]) => (
          <Bar key={k} label={name} value={r.chapters[k]} kind="accent" />
        ))}
      </div>
      <div className="rcard">
        <h3>What to do next</h3>
        <p>{r.tip}</p>
        {r.next_steps.length > 0 && (
          <ul className="plain">
            {r.next_steps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        )}
        {r.weak_spots.length > 0 && (
          <div className="row">
            {r.weak_spots.map((w) => (
              <button key={w.id} className="btn small" onClick={() => openBattle(w.id)}>
                <Icon name="sword" size={14} /> Fight: {w.title.length > 34 ? w.title.slice(0, 33) + "…" : w.title}
              </button>
            ))}
          </div>
        )}
        <p className="muted small">
          Your real work gave you {r.real.knowledge - 10} knowledge at the start ({r.real.mastered} mastered, {r.real.explained} explained, {r.real.read} read, {r.real.links} links found).
        </p>
      </div>
      <div className="row">
        <button className="btn" onClick={onAgain}>
          <Icon name="play" size={15} weight="fill" /> Play a new semester
        </button>
        <button className="btn ghost" onClick={onBack}>
          Back
        </button>
      </div>
    </div>
  );
}

export default function Semester({ notify, onBack }) {
  const [d, setD] = useState(null); // { run, records }
  const [line, setLine] = useState("");
  const [busy, setBusy] = useState(false);
  const [study, setStudy] = useState(false);
  const game = useApp((s) => s.game);

  useEffect(() => {
    api.sim().then(setD).catch((e) => notify(e.message));
  }, [notify]);

  const apply = async (call, sound = "tap") => {
    setBusy(true);
    try {
      const r = await call();
      const run = r.run || r; // starting a semester answers with the run only
      const next = { run, records: r.records || d.records };
      setD(next);
      setLine(r.say || "");
      setStudy(false);
      if (run.status !== "active" && run.report) {
        play(run.report.burnout ? "lose" : "win");
        if (!run.report.burnout && "SA".includes(run.report.grade)) confetti("big");
      } else if (run.event && !d?.run?.event) play("event");
      else play(sound);
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!d) return <p className="muted">Loading…</p>;
  const { run, records } = d;

  if (!run) {
    const stats = game?.stats;
    return (
      <div className="semstart">
        <Duck size={120} mood="happy" outfit={game?.outfit} stage={stage(game?.level?.index)} />
        <div>
          <span className="eyebrow">Semester Simulator</span>
          <h2>Plan 12 weeks of research</h2>
          <p className="lead">
            Each week you have 5 action points. Read, run tests, write, meet your supervisor, or rest. Events arrive, and each one asks you to take a risk. Plan well, and your thesis grows. Work without rest, and you burn out.
          </p>
          <ul className="plain">
            <li>
              <strong>It uses your real work.</strong> Papers that you mastered give you knowledge at the start. A reviewer asks about <em>your</em> papers, and you know the odds.
            </li>
            <li>
              <strong>It shows what to do next.</strong> The report names the real papers that you did not know, and it sends you to fight their boss.
            </li>
            <li>
              <strong>It is only a game.</strong> It gives no XP. XP is only for real work.
            </li>
          </ul>
          {stats && (
            <p className="muted small">
              Now: {stats.papers} papers in your collection, {stats.mastered} mastered.
            </p>
          )}
          <div className="row">
            <button className="btn" disabled={busy} onClick={() => apply(() => api.simStart(), "event")}>
              <Icon name="play" size={15} weight="fill" /> Start a semester
            </button>
            {records.runs > 0 && (
              <span className="muted small">
                {records.runs} played. Best: {records.best}% (grade {records.best_grade}).
              </span>
            )}
          </div>
          <p className="duckline">
            <Duck size={36} /> <span>{duckSay("semester", records.runs)}</span>
          </p>
        </div>
      </div>
    );
  }

  if (run.status !== "active") return <Report run={run} records={records} onAgain={() => apply(() => api.simStart(), "event")} onBack={onBack} />;

  const act = (id, arg = "") => apply(() => api.simAct(run.id, id, arg));
  const tired = run.energy < 30;
  return (
    <div className="sem">
      <div className="semhead">
        <Weeks run={run} />
        <div className="semweek">
          <strong>Week {run.week}</strong> of {run.weeks}
          <span className="muted"> · {run.milestones.find((m) => m.week >= run.week)?.label} (week {run.milestones.find((m) => m.week >= run.week)?.week})</span>
        </div>
      </div>

      <div className="semgrid">
        <section className="sempanel" aria-label="Your state">
          <div className="apdots" role="img" aria-label={`${run.ap} of ${run.ap_max} action points left`}>
            {Array.from({ length: run.ap_max }, (_, i) => (
              <motion.i key={i} className={i < run.ap ? "on" : ""} animate={{ scale: i < run.ap ? 1 : 0.8 }} />
            ))}
            <span>{run.ap} action points</span>
          </div>
          <Bar label="Energy" value={run.energy} />
          <Bar label="Morale" value={run.morale} />
          <Bar label="Trust" value={run.trust} kind="accent" />
          <div className="knowledge">
            <Icon name="idea" size={15} /> Knowledge <strong>{run.knowledge}</strong>
          </div>
          <hr />
          <h3 className="smallh">Thesis · {run.progress}%</h3>
          {Object.entries(run.chapter_names).map(([k, name]) => (
            <Bar key={k} label={name} value={run.chapters[k]} kind="accent" />
          ))}
        </section>

        <section className="semmain" aria-label="This week">
          <p className="duckline">
            <Duck size={44} mood={tired ? "sleepy" : "idle"} outfit={game?.outfit} stage={stage(game?.level?.index)} />
            <span>{tired ? duckSay("tired", run.week) : duckSay("semester", run.week)}</span>
          </p>

          {run.coming && !run.event && (
            <div className="coming" role="status">
              <Icon name="meet" size={16} /> Your supervisor says: <strong>{run.coming.title}</strong> this week.
              {run.coming.paper?.id ? ` It is about "${run.coming.paper.title}".` : ""}
            </div>
          )}

          <AnimatePresence mode="wait">
            {run.event ? (
              <motion.div key={"ev-" + run.week} className="event" initial={{ opacity: 0, y: 14, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0 }}>
                <span className="eyebrow">Event</span>
                <h3>{run.event.title}</h3>
                <p>{run.event.text}</p>
                <div className="choices">
                  {run.event.choices.map((c) => (
                    <button key={c.id} className={"choice " + c.risk} disabled={busy} onClick={() => apply(() => api.simChoose(run.id, c.id))}>
                      <strong>{c.label}</strong>
                      <span>
                        {c.risk === "risky" ? "Risk · " : ""}
                        {c.hint}
                      </span>
                    </button>
                  ))}
                </div>
              </motion.div>
            ) : (
              <motion.div key="acts" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="actions-grid">
                  {run.actions.map((a) => (
                    <button
                      key={a.id}
                      className={"act" + (a.id === "rest" && tired ? " hint" : "")}
                      disabled={busy || !a.enabled}
                      title={a.why || a.text}
                      aria-label={`${a.label}. ${a.ap} action point${a.ap > 1 ? "s" : ""}. ${a.why || a.text}`}
                      onClick={() => (a.id === "study" ? setStudy(!study) : act(a.id))}
                      aria-expanded={a.id === "study" ? study : undefined}
                    >
                      <Icon name={ICON[a.id]} size={22} />
                      <strong>{a.label}</strong>
                      <span className="cost">
                        {a.ap} AP · {a.energy > 0 ? `+${a.energy}` : a.energy} energy
                      </span>
                      <em>{a.text}</em>
                    </button>
                  ))}
                </div>
                {study && (
                  <div className="studylist" role="group" aria-label="Choose a paper to study">
                    {run.papers.map((p) => (
                      <button key={p.id} className="btn small ghost" disabled={busy || p.prepared} onClick={() => act("study", p.id)}>
                        {p.prepared ? <Icon name="check" size={14} weight="fill" /> : null} {p.title.length > 40 ? p.title.slice(0, 39) + "…" : p.title}
                        <span className={"chip rk r" + p.rank}>{p.rank_name}</span>
                      </button>
                    ))}
                  </div>
                )}
                <div className="semfoot">
                  <button className={"btn" + (run.ap === 0 ? " pulse" : " ghost")} disabled={busy} onClick={() => apply(() => api.simEndWeek(run.id), "event")}>
                    End the week <Icon name="arrow" size={15} />
                  </button>
                  <button className="btn small tint" disabled={busy || !run.boosts.coffee || run.coffee_used} onClick={() => apply(() => api.simBoost(run.id, "coffee"), "spark")} title="Coffee: +25 energy. One for each week.">
                    <Icon name="coffee" size={14} weight="fill" /> Coffee ({run.boosts.coffee || 0})
                  </button>
                  <button className="btn small tint" disabled={busy || !run.boosts.second_chance || run.armed} onClick={() => apply(() => api.simBoost(run.id, "second_chance"), "spark")} title="Second chance: roll again after a failed roll.">
                    <Icon name="bolt" size={14} weight="fill" /> {run.armed ? "Second chance ready" : `Second chance (${run.boosts.second_chance || 0})`}
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="semlog" aria-live="polite">
            {line && <p className="latest">{line}</p>}
            {[...run.log].reverse().map((l, i) => (
              <p key={run.log.length - i} className={"k-" + l.kind}>
                <em>W{l.week}</em> {l.text}
              </p>
            ))}
          </div>
        </section>
      </div>

      <details className="rpapers">
        <summary>Your real papers in this simulation ({run.papers.length})</summary>
        {run.papers.length ? (
          <ul>
            {run.papers.map((p) => (
              <li key={p.id}>
                <span className={"chip rk r" + p.rank}>{p.rank_name}</span> {p.title}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted small">You have no papers yet. Add papers in the library. Reviewers then ask about them.</p>
        )}
        <p className="muted small">Knowledge at the start came from your real work: {run.real.mastered} mastered, {run.real.explained} explained, {run.real.read} read, {run.real.links} links found.</p>
      </details>
    </div>
  );
}
