import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import { tzMinutes } from "./game.js";
import { Icon } from "./icons.jsx";

const localDate = () => new Date().toLocaleDateString("en-CA");

// The 3 quests of this week. The student chooses 1 or 2. A quest that is not done has no penalty: it just goes away.
export function QuestCards({ data, onChoose, onDrop, busy }) {
  const full = data.chosen >= data.max_chosen;
  return (
    <ul className="questlist">
      {data.quests.map((q) => (
        <li key={q.code} className={"quest" + (q.done ? " done" : q.chosen ? " chosen" : "")}>
          <div>
            <h3>
              {q.title} <span className="small muted">+{q.xp} points</span>
            </h3>
            <p className="small">{q.text}</p>
            {(q.chosen || q.done) && (
              <div className="pbar" role="progressbar" aria-label={`Progress of ${q.title}`} aria-valuenow={q.have} aria-valuemin={0} aria-valuemax={q.need}>
                <span style={{ width: Math.round((100 * q.have) / q.need) + "%" }} />
              </div>
            )}
            {(q.chosen || q.done) && (
              <p className="small muted">
                {q.done ? "Quest done" : `${q.have} of ${q.need}`}
              </p>
            )}
          </div>
          {q.done ? (
            <span className="badge b-ok">Quest done</span>
          ) : q.chosen ? (
            <button className="link" disabled={busy} onClick={() => onDrop(q.code)}>
              Drop it
            </button>
          ) : (
            <button className="btn small" disabled={busy || full} onClick={() => onChoose(q.code)} title={full ? "Drop a quest first. There is no penalty." : ""}>
              Choose
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

export function QuestBlock({ notify }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const date = localDate();
  const load = useCallback(async () => {
    try {
      setData(await api.quests(date, tzMinutes()));
    } catch (e) {
      notify(e.message);
    }
  }, [date, notify]);
  useEffect(() => {
    load();
  }, [load]);
  const run = async (fn) => {
    setBusy(true);
    try {
      setData(await fn());
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };
  if (!data) return null;
  const needs = data.chosen === 0;
  return (
    <section className="today-block" aria-label="Quests of this week">
      <h2>{needs ? "Choose your quests" : "Quests of this week"}</h2>
      <p className="small muted">
        Choose 1 or 2 of these 3 quests. They fit your stage. A quest that you do not finish has no penalty.
      </p>
      <QuestCards data={data} busy={busy} onChoose={(c) => run(() => api.chooseQuest(c, date))} onDrop={(c) => run(() => api.dropQuest(c, date))} />
    </section>
  );
}

// The quest log and the bosses, for the Journey page.
export function QuestLog({ notify }) {
  const [data, setData] = useState(null);
  const [bosses, setBosses] = useState([]);
  useEffect(() => {
    api.quests(localDate(), tzMinutes()).then(setData).catch((e) => notify(e.message));
    api.bosses().then(setBosses).catch(() => {});
  }, [notify]);
  if (!data) return null;
  return (
    <>
      <section className="today-block" aria-label="Quest log">
        <h2>Quest log</h2>
        {data.log.length === 0 ? (
          <p className="small muted">No quest done yet. Choose a quest on the Today page.</p>
        ) : (
          <ul className="recent">
            {data.log.map((q, i) => (
              <li key={i}>
                <Icon name="check" size={15} /> {q.title} <span className="small muted">{q.week} · +{q.xp}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="today-block" aria-label="Bosses">
        <h2>Bosses</h2>
        {bosses.length === 0 ? (
          <p className="small muted">No boss yet. Open a hard paper and click “Mark as boss”.</p>
        ) : (
          <ul className="recent">
            {bosses.map((b) => (
              <li key={b.paper_id}>
                <Icon name="crown" size={15} /> <strong>{b.title}</strong>{" "}
                {b.defeated ? (
                  <span className="badge b-ok">Defeated</span>
                ) : (
                  <span className="small muted">
                    Quiz {b.quiz_percent}% ({b.quiz_answered} of {b.quiz_needed} answers needed) · Feynman {b.feynman_best}% · both need {b.need_percent}%
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
