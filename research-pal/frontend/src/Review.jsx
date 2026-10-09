import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import { tzMinutes } from "./game.js";
import { Icon } from "./icons.jsx";

const localDate = () => new Date().toLocaleDateString("en-CA");
const STATE_TEXT = { fresh: "Fresh", ok: "Needs water", dry: "A little dry" };
const RATINGS = [
  ["again", "Again", "I forgot it"],
  ["hard", "Hard", "I needed effort"],
  ["good", "Good", "I knew it"],
  ["easy", "Easy", "It was simple"],
];

// One plant for each paper. The color shows if something is due. A plant never dies.
export function Garden({ plants, onPick }) {
  if (!plants.length) return <p className="muted">Your garden is empty. Add a paper. Each paper grows a plant.</p>;
  return (
    <ul className="garden" aria-label="Knowledge Garden">
      {plants.map((p) => (
        <li key={p.paper_id}>
          <button className={"plant " + p.state} onClick={() => onPick(p)} aria-label={`${p.title}: ${STATE_TEXT[p.state]}, ${p.due} due, ${p.items} items`}>
            <span className="leaf" aria-hidden="true">
              <Icon name="sparkle" size={22} />
            </span>
            <span className="ptitle">{p.title}</span>
            <span className="small muted">
              {STATE_TEXT[p.state]}
              {p.due > 0 ? ` · ${p.due} due` : ""}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

// One item at a time. The question first. The student thinks. Then "Show answer". Then 4 buttons.
export function ReviewSession({ items, paperId, onDone, notify }) {
  const [i, setI] = useState(0);
  const [shown, setShown] = useState(false);
  const [busy, setBusy] = useState(false);
  const [xp, setXp] = useState(0);
  const item = items[i];
  const date = localDate();

  const rate = async (rating) => {
    setBusy(true);
    try {
      const r = await api.rateReview(item.id, rating, date);
      setXp((x) => x + r.xp_gained);
      setShown(false);
      setI(i + 1);
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!item) {
    return (
      <div className="quizdone" role="status">
        <h3>Done</h3>
        <p>
          You reviewed {items.length} {items.length === 1 ? "item" : "items"}.{xp > 0 ? ` +${xp} points.` : ""} Your plants are fresh. See you on the next day.
        </p>
        <button className="btn" onClick={onDone}>
          Back to the garden
        </button>
      </div>
    );
  }
  return (
    <div className="quizcard review-item">
      <p className="small muted">
        Item {i + 1} of {items.length} · {item.kind_label}
        {item.title ? ` · ${item.title}` : ""}
      </p>
      <h3 className="quizq">{item.question}</h3>
      {!shown ? (
        <>
          <p className="muted">Think first. Say the answer in your mind.</p>
          <button className="btn" onClick={() => setShown(true)} autoFocus>
            Show answer
          </button>
        </>
      ) : (
        <>
          <p className="answer">{item.answer}</p>
          <p className="small">
            <span className={"badge " + (item.label === "AI explanation" ? "b-info" : "b-ok")}>{item.label}</span>
          </p>
          {item.quote && (
            <div className="evidence">
              <blockquote>
                <span>{item.quote}</span>
                {item.page > 0 && (
                  <button className="chip" title="Open the PDF at this page" onClick={() => api.openPdf(item.paper_id, item.page).catch((e) => notify(e.message))}>
                    p. {item.page}
                  </button>
                )}
              </blockquote>
            </div>
          )}
          <p className="small muted">How was it?</p>
          <div className="ratings" role="group" aria-label="How well did you remember?">
            {RATINGS.map(([k, label, hint]) => (
              <button key={k} className={"btn rate-" + k} disabled={busy} onClick={() => rate(k)} title={hint}>
                {label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default function Review({ notify, onChanged }) {
  const [garden, setGarden] = useState(null);
  const [session, setSession] = useState(null); // { items, paperId }
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    try {
      setGarden(await api.reviewGarden(localDate(), tzMinutes()));
    } catch (e) {
      notify(e.message);
    }
  }, [notify]);
  useEffect(() => {
    load();
  }, [load]);

  const start = async (paper) => {
    setMsg("");
    try {
      const due = await api.reviewDue(localDate(), tzMinutes(), paper?.paper_id);
      if (!due.items.length) {
        setMsg(paper ? "This plant is fresh. Nothing is due. Come back on another day." : "Nothing is due today. Your garden is fresh.");
        return;
      }
      setSession({ items: due.items, paperId: paper?.paper_id });
    } catch (e) {
      notify(e.message);
    }
  };
  const done = async () => {
    setSession(null);
    await load();
    onChanged?.();
  };

  if (!garden) return <p className="muted">Loading…</p>;
  return (
    <section className="review">
      <h1>Review</h1>
      <p className="lead">Your plants need a little water on the right day. Each review is short. The app picks the day for each item.</p>
      {session ? (
        <ReviewSession items={session.items} paperId={session.paperId} onDone={done} notify={notify} />
      ) : (
        <>
          <div className="row">
            <button className="btn big" disabled={garden.due_total === 0} onClick={() => start(null)}>
              {garden.due_total > 0 ? `Review ${garden.due_total} due ${garden.due_total === 1 ? "item" : "items"}` : "Nothing is due today"}
            </button>
            <span className="small muted">Two points for each review, 20 points a day at most.</span>
          </div>
          {msg && (
            <p className="muted" role="status">
              {msg}
            </p>
          )}
          <h2>Knowledge Garden</h2>
          <Garden plants={garden.plants} onPick={start} />
        </>
      )}
    </section>
  );
}
