import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";

function Points({ title, hint, points }) {
  return (
    <div className="gapcol">
      <h3>{title}</h3>
      <p className="small muted">{hint}</p>
      {points.length === 0 && <p className="small muted">Nothing found.</p>}
      {points.map((p, i) => (
        <div key={i} className="gappoint">
          <p>{p.point}</p>
          {p.evidence.map((e, j) => (
            <blockquote key={j}>
              “{e.quote}” <span className="small muted">{e.paper_title || e.title}, page {e.page}</span>
            </blockquote>
          ))}
        </div>
      ))}
    </div>
  );
}

const STATUS = { new: "New", confirmed: "You confirmed it", not_gap: "You said: not a gap" };

// Where the papers of a sub-question agree, disagree and what nobody did. The agree and disagree points have checked quotes in two papers. A gap is an AI opinion.
export default function Gaps({ notify, onUsed }) {
  const [subs, setSubs] = useState([]);
  const [sq, setSq] = useState("");
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api
      .subQuestions()
      .then((r) => {
        const list = Array.isArray(r) ? r : r.sub_questions || [];
        setSubs(list);
        if (list[0]) setSq(list[0].id);
      })
      .catch((e) => notify(e.message));
  }, [notify]);
  const load = useCallback(() => (sq ? api.getGaps(sq).then(setData).catch((e) => notify(e.message)) : undefined), [sq, notify]);
  useEffect(() => {
    load();
  }, [load]);
  const run = async () => {
    setBusy(true);
    try {
      setData(await api.runGaps({ sub_question_id: sq }));
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };
  const status = async (id, s) => {
    try {
      await api.setGapStatus(id, s);
      await load();
    } catch (e) {
      notify(e.message);
    }
  };
  const use = async (id) => {
    try {
      await api.useGap(id);
      notify("The gap is now a section in your outline. You write the text.");
      onUsed?.();
    } catch (e) {
      notify(e.message);
    }
  };
  return (
    <section className="gaps" aria-label="Gap finder">
      <p className="lead">
        The AI compares the papers of one sub-question. Each “agree” and “disagree” point has checked quotes from two papers. A “gap” is an <strong>AI opinion</strong>: you decide.
      </p>
      {subs.length === 0 ? (
        <p className="muted">Make sub-questions in the Thesis tab and tag your papers first.</p>
      ) : (
        <div className="row">
          <label htmlFor="gap-sq" className="small muted">
            Sub-question
          </label>
          <select id="gap-sq" value={sq} onChange={(e) => setSq(e.target.value)}>
            {subs.map((s) => (
              <option key={s.id} value={s.id}>
                {s.text}
              </option>
            ))}
          </select>
          <button className="btn" onClick={run} disabled={busy || !sq}>
            {busy ? "Comparing…" : "Find gaps"}
          </button>
        </div>
      )}
      {data && data.run_id && (
        <div className="gapcols">
          <Points title="Agree" hint="Papers say the same." points={data.agree} />
          <Points title="Disagree" hint="Papers say different things." points={data.disagree} />
          <div className="gapcol">
            <h3>Gap</h3>
            <p className="small muted">What nobody did yet. AI opinion.</p>
            {data.gap.length === 0 && <p className="small muted">Nothing found.</p>}
            {data.gap.map((g) => (
              <div key={g.id} className={"gappoint " + g.status}>
                <p>{g.point}</p>
                {g.reason && <p className="small muted">Why: {g.reason}</p>}
                <p className="small">{STATUS[g.status]}</p>
                <div className="row">
                  <button className="btn small ghost" onClick={() => status(g.id, "confirmed")} aria-label={`Confirm the gap: ${g.point.slice(0, 40)}`}>
                    This is a gap
                  </button>
                  <button className="btn small ghost" onClick={() => status(g.id, "not_gap")} aria-label={`Not a gap: ${g.point.slice(0, 40)}`}>
                    Not a gap
                  </button>
                  <button className="btn small" onClick={() => use(g.id)} aria-label={`Use this gap: ${g.point.slice(0, 40)}`}>
                    Use this gap
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      {data && !data.run_id && sq && <p className="muted">No comparison yet. Click “Find gaps”.</p>}
    </section>
  );
}
