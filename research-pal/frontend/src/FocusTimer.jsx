import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { beep, cleanMinutes, DEFAULTS, format, nextPhase, remainingMs } from "./timer.js";

const KEY = "rp-timer";
const load = () => {
  try {
    return { ...DEFAULTS, sound: false, ...JSON.parse(localStorage.getItem(KEY) || "{}") };
  } catch {
    return { ...DEFAULTS, sound: false };
  }
};

// A focus timer: work, then rest (25 and 5 minutes by default). The server counts the real minutes of each work session.
// active: the session that is running on the server (after a reload of the page, the timer goes on).
export default function FocusTimer({ date, goals, papers, active, onChanged, notify }) {
  const [opts, setOpts] = useState(load);
  const [phase, setPhase] = useState(active ? "work" : "idle");
  const [startMs, setStartMs] = useState(active ? active.start * 1000 : 0);
  const [planned, setPlanned] = useState(active ? active.planned : opts.work);
  const [now, setNow] = useState(Date.now());
  const [task, setTask] = useState("");
  const [link, setLink] = useState(""); // "goal:ID" or "paper:ID"
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const ended = useRef(false);

  const save = (next) => {
    setOpts(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* private mode */
    }
  };

  // A tick each half second. The time comes from the clock, so a slow tab in the background shows the right time again at once.
  useEffect(() => {
    if (phase === "idle") return;
    const t = setInterval(() => setNow(Date.now()), 500);
    const wake = () => setNow(Date.now());
    document.addEventListener("visibilitychange", wake);
    return () => {
      clearInterval(t);
      document.removeEventListener("visibilitychange", wake);
    };
  }, [phase]);

  const left = phase === "idle" ? 0 : remainingMs(startMs, now, planned);

  useEffect(() => {
    document.title = phase === "idle" ? "Research Pal" : `${format(left)} ${phase === "work" ? "Focus" : "Rest"} · Research Pal`;
    return () => {
      document.title = "Research Pal";
    };
  }, [phase, left]);

  // The end of a phase
  useEffect(() => {
    if (phase === "idle" || left > 0 || ended.current) return;
    ended.current = true;
    (async () => {
      if (opts.sound) beep();
      if (phase === "work") {
        try {
          const s = await api.focusStop();
          setMsg(`Well done. You focused for ${s.minutes} ${s.minutes === 1 ? "minute" : "minutes"}. Now rest.`);
          onChanged();
        } catch (e) {
          notify(e.message);
        }
        setStartMs(Date.now());
        setNow(Date.now());
        setPlanned(opts.rest);
        setPhase("rest");
      } else {
        setMsg("Rest is over. Start again when you are ready.");
        setPhase(nextPhase("rest"));
      }
      ended.current = false;
    })();
  }, [left, phase]); // eslint-disable-line react-hooks/exhaustive-deps

  const start = async () => {
    setBusy(true);
    setMsg("");
    try {
      const [kind, id] = link.split(":");
      const s = await api.focusStart({ task_text: task, paper_id: kind === "paper" ? id : "", goal_id: kind === "goal" ? id : "", planned_minutes: opts.work, date });
      ended.current = false;
      setStartMs(Date.now());
      setNow(Date.now());
      setPlanned(s.planned);
      setPhase("work");
      onChanged();
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };
  const stop = async () => {
    setBusy(true);
    try {
      if (phase === "work") {
        const s = await api.focusStop();
        setMsg(`You focused for ${s.minutes} ${s.minutes === 1 ? "minute" : "minutes"}. Good work.`);
        onChanged();
      }
      setPhase("idle");
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="today-block focus" aria-label="Focus timer">
      <h2>Focus</h2>
      {phase !== "idle" ? (
        <>
          <div className={"timer " + phase} role="timer" aria-live="off">
            <strong>{format(left)}</strong>
            <span>{phase === "work" ? "Focus" : "Rest"}</span>
          </div>
          <button className="btn ghost" disabled={busy} onClick={stop}>
            {phase === "work" ? "Stop" : "Skip the rest"}
          </button>
        </>
      ) : (
        <>
          <div className="row">
            <label className="small muted" htmlFor="focus-task">
              What do you do?
            </label>
            <input id="focus-task" type="text" maxLength={200} value={task} onChange={(e) => setTask(e.target.value)} placeholder="Example: read the method of Smith 2024" />
          </div>
          <div className="row">
            <label className="small muted" htmlFor="focus-link">
              Link it to
            </label>
            <select id="focus-link" value={link} onChange={(e) => setLink(e.target.value)}>
              <option value="">Nothing</option>
              {goals.map((g) => (
                <option key={g.id} value={"goal:" + g.id}>
                  Goal: {g.text}
                </option>
              ))}
              {papers.slice(0, 30).map((p) => (
                <option key={p.id} value={"paper:" + p.id}>
                  Paper: {(p.title || p.filename).slice(0, 60)}
                </option>
              ))}
            </select>
          </div>
          <div className="row">
            <label className="small muted" htmlFor="focus-work">
              Focus
            </label>
            <input id="focus-work" className="num" type="number" min={1} max={180} value={opts.work} onChange={(e) => save({ ...opts, work: cleanMinutes(e.target.value, opts.work) })} aria-label="Focus minutes" />
            <label className="small muted" htmlFor="focus-rest">
              Rest
            </label>
            <input id="focus-rest" className="num" type="number" min={1} max={60} value={opts.rest} onChange={(e) => save({ ...opts, rest: cleanMinutes(e.target.value, opts.rest, 1, 60) })} aria-label="Rest minutes" />
            <span className="small muted">minutes</span>
            <label className="small check">
              <input type="checkbox" checked={opts.sound} onChange={(e) => save({ ...opts, sound: e.target.checked })} /> Sound at the end
            </label>
          </div>
          <button className="btn" disabled={busy} onClick={start}>
            Start {opts.work} minutes
          </button>
        </>
      )}
      {msg && (
        <p className="small muted" role="status">
          {msg}
        </p>
      )}
    </section>
  );
}
