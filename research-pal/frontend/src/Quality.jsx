import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";

const ANSWER = { yes: "Yes", no: "No", unclear: "Unclear" };

// A checklist for critical reading. The AI answers with a quote. An answer without a checked quote is "Unclear". You can change each answer.
export default function Quality({ paperId, notify }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => api.getCritique(paperId).then(setData).catch((e) => notify(e.message)), [paperId, notify]);
  useEffect(() => {
    load();
  }, [load]);
  const run = async () => {
    setBusy(true);
    try {
      setData(await api.runCritique(paperId));
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };
  const edit = async (answers, confirm = false) => {
    try {
      setData(await api.editCritique(paperId, answers, confirm));
    } catch (e) {
      notify(e.message);
    }
  };
  if (!data) return <p className="muted">Loading…</p>;
  return (
    <section className="quality" aria-label="Quality check">
      <h2>Quality check</h2>
      <p className="small muted">
        A checklist for critical reading. The answers are an <strong>AI opinion</strong>. The AI saw only a part of the paper. You decide: change any answer, add a note, then confirm.
      </p>
      <button className="btn" onClick={run} disabled={busy}>
        {busy ? "Checking…" : data.items.length ? "Check again" : "Run the quality check"}
      </button>
      {data.items.length > 0 && (
        <>
          <ol className="qitems">
            {data.items.map((it) => (
              <li key={it.key} className={"qitem " + it.answer}>
                <p>
                  <strong>{it.question}</strong>
                </p>
                <label className="small">
                  Answer{" "}
                  <select value={it.answer} onChange={(e) => edit({ [it.key]: { answer: e.target.value } })} aria-label={`Answer: ${it.question}`}>
                    {Object.entries(ANSWER).map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                </label>{" "}
                <span className="small muted">{it.edited ? "Changed by you." : "AI opinion."}</span>
                {it.comment && <p className="small">{it.comment}</p>}
                {it.verified ? (
                  <blockquote className="qquote">
                    “{it.quote}” <span className="small muted">page {it.page}</span>
                  </blockquote>
                ) : (
                  <p className="small muted">No checked quote. So the answer stays “Unclear” until you decide.</p>
                )}
                <label className="small">
                  Your note{" "}
                  <input
                    defaultValue={it.note || ""}
                    aria-label={`Your note: ${it.question}`}
                    onBlur={(e) => e.target.value !== (it.note || "") && edit({ [it.key]: { note: e.target.value } })}
                  />
                </label>
              </li>
            ))}
          </ol>
          {data.confirmed ? (
            <p className="small ok" role="status">
              You confirmed this check.
            </p>
          ) : (
            <button className="btn ghost" onClick={() => edit({}, true)}>
              Confirm this check
            </button>
          )}
        </>
      )}
    </section>
  );
}
