import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { Icon } from "./icons.jsx";
import FocusTimer from "./FocusTimer.jsx";
import { QuestBlock } from "./Quests.jsx";
import { tzMinutes } from "./game.js";

// The date of the student, as YYYY-MM-DD. The server can be in another time zone.
export const localDate = () => new Date().toLocaleDateString("en-CA");

const KINDS = [
  ["free", "Free"],
  ["papers", "Papers"],
  ["words", "Words"],
  ["focus", "Focus"],
];

function Goals({ data, date, onChanged, notify }) {
  const [text, setText] = useState("");
  const [kind, setKind] = useState("free");
  const [busy, setBusy] = useState(false);
  const run = async (fn) => {
    setBusy(true);
    try {
      await fn();
      await onChanged();
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };
  const add = (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    run(async () => {
      await api.addGoal({ text, kind, date });
      setText("");
    });
  };
  return (
    <section className="today-block" aria-label="Goals of today">
      <h2>
        Goals of today{" "}
        {data.goals_total > 0 && (
          <span className="small muted" aria-label={`${data.goals_done} of ${data.goals_total} done`}>
            {data.goals_done}/{data.goals_total}
          </span>
        )}
      </h2>
      {data.goals.length === 0 && <p className="small muted">Three small goals are enough. Example: read 1 paper, write 200 words, 1 focus session.</p>}
      <ul className="goals">
        {data.goals.map((g) => (
          <li key={g.id} className={g.done ? "done" : ""}>
            <label>
              <input type="checkbox" checked={g.done} disabled={busy} onChange={() => run(() => api.updateGoal(g.id, { done: !g.done }))} />
              <span>{g.text}</span>
            </label>
            <button className="iconbtn" onClick={() => run(() => api.deleteGoal(g.id))} aria-label={`Delete the goal: ${g.text}`} title="Delete">
              <Icon name="x" size={14} />
            </button>
          </li>
        ))}
      </ul>
      <form className="row" onSubmit={add}>
        <input type="text" maxLength={200} value={text} onChange={(e) => setText(e.target.value)} placeholder="Add a goal" aria-label="New goal" />
        <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Kind of goal">
          {KINDS.map(([k, label]) => (
            <option key={k} value={k}>
              {label}
            </option>
          ))}
        </select>
        <button className="btn small" disabled={busy || !text.trim()}>
          Add
        </button>
      </form>
    </section>
  );
}

function Wins({ data, date, onChanged, notify, inputRef }) {
  const [text, setText] = useState("");
  const [past, setPast] = useState(null);
  const save = async (e) => {
    e.preventDefault();
    try {
      await api.addWin({ text, date });
      setText("");
      await onChanged();
    } catch (err) {
      notify(err.message);
    }
  };
  const showPast = async () => {
    try {
      setPast(past ? null : await api.wins(5, date));
    } catch (e) {
      notify(e.message);
    }
  };
  return (
    <section className="today-block" aria-label="Win of the day">
      <h2>Win of the day</h2>
      {data.win_today && (
        <p className="win-today">
          <Icon name="check" size={15} /> {data.win_today.text}
        </p>
      )}
      <form className="row" onSubmit={save}>
        <input ref={inputRef} type="text" maxLength={300} value={text} onChange={(e) => setText(e.target.value)} placeholder="One small win of today. One line is enough." aria-label="Your win of the day" />
        <button className="btn small" disabled={!text.trim()}>
          Save
        </button>
      </form>
      <button className="link" onClick={showPast}>
        {past ? "Hide my past wins" : "Show my past wins"}
      </button>
      {past && (
        <ul className="pastwins">
          {past.length === 0 && <li className="muted">No past win yet. Your wins will be here.</li>}
          {past.map((w) => (
            <li key={w.id}>
              <span className="small muted">{w.date}</span> {w.text}
            </li>
          ))}
        </ul>
      )}
      {!past && data.past_win && (
        <p className="small muted pastwin">
          A win from {data.past_win.date}: {data.past_win.text}
        </p>
      )}
    </section>
  );
}

// The home page. One main action is clear. The other blocks are calm and small.
export default function Today({ papers, onAction, gameOn = false, reviewOn = false, questsOn = false, onOpenReview, notify }) {
  const [date] = useState(localDate);
  const [data, setData] = useState(null);
  const [game, setGame] = useState(null);
  const [garden, setGarden] = useState(null);
  const winRef = useRef(null);

  const load = useCallback(async () => {
    try {
      setData(await api.today(date));
      if (gameOn) setGame(await api.game(date, tzMinutes()).catch(() => null));
      if (reviewOn) setGarden(await api.reviewGarden(date, tzMinutes()).catch(() => null));
    } catch (e) {
      notify(e.message);
    }
  }, [date, notify, gameOn, reviewOn]);
  useEffect(() => {
    load();
  }, [load, papers.length]);

  if (!data) return <p className="muted">Loading…</p>;
  const act = () => {
    if (data.next.kind === "win") winRef.current?.focus();
    else onAction(data.next);
  };
  const pretty = new Date(date + "T12:00:00").toLocaleDateString([], { weekday: "long", day: "numeric", month: "long" });
  return (
    <section className="today">
      <header className="today-head">
        <p className="small muted">{pretty}</p>
        {data.project.title || data.project.question ? (
          <>
            {data.project.title && <h1>{data.project.title}</h1>}
            {data.project.question && <p className="today-question">{data.project.question}</p>}
          </>
        ) : (
          <>
            <h1>Today</h1>
            <p className="muted">
              You have not written your thesis title and question yet.{" "}
              <button className="link" onClick={() => onAction({ kind: "find_paper" })}>
                Write them now
              </button>
            </p>
          </>
        )}
      </header>

      <section className="today-block next" aria-label="Next best action">
        <h2>Next best action</h2>
        <p className="next-text">{data.next.text}</p>
        {data.next.button && (
          <button className="btn big" onClick={act}>
            {data.next.button}
          </button>
        )}
      </section>

      {questsOn && <QuestBlock notify={notify} />}

      <div className="today-grid">
        <Goals data={data} date={date} onChanged={load} notify={notify} />
        <FocusTimer date={date} goals={data.goals} papers={papers} active={data.active_session} onChanged={load} notify={notify} />
        <Wins data={data} date={date} onChanged={load} notify={notify} inputRef={winRef} />
        <section className="today-block" aria-label="Focus time today">
          <h2>Focus time today</h2>
          <p className="bignum">
            {data.focus_minutes} <span className="small muted">minutes</span>
          </p>
        </section>
      </div>

      <div className="today-soon" role="group" aria-label="Coming soon">
        {game ? (
          <>
            <div className="soon live" aria-label="Streak">
              <strong>Streak</strong>
              <span>
                {game.streak.current} {game.streak.current === 1 ? "day" : "days"}
              </span>
              <span className="small muted">{game.streak.message}</span>
            </div>
            <div className="soon live" aria-label="Level">
              <strong>Level</strong>
              <span>
                {game.level.name} · {game.xp} points
              </span>
              <span className="small muted">{game.level.next ? `Next: ${game.level.next.name}` : "Last level"}</span>
            </div>
          </>
        ) : (
          ["Streak", "Level"].map((n) => (
            <div key={n} className="soon">
              <strong>{n}</strong>
              <span className="small muted">Coming soon</span>
            </div>
          ))
        )}
        {!questsOn && (
          <div className="soon">
            <strong>Quest</strong>
            <span className="small muted">Coming soon</span>
          </div>
        )}
        {garden ? (
          <div className="soon live" aria-label="Review">
            <strong>Review</strong>
            <span>
              {garden.due_total} {garden.due_total === 1 ? "item" : "items"} due
            </span>
            <button className="link" onClick={onOpenReview}>
              {garden.due_total > 0 ? "Water your plants" : "Open the garden"}
            </button>
          </div>
        ) : (
          <div className="soon">
            <strong>Review</strong>
            <span className="small muted">Coming soon</span>
          </div>
        )}
      </div>
    </section>
  );
}
