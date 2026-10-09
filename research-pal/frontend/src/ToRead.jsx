import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";

// Papers that you did not read yet, with a fit score for your question. The score comes from the abstract, not from the AI. The reason shows the words that fit.
export default function ToRead({ onChanged, notify, suggestOn = false }) {
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState("");
  const load = useCallback(() => api.toRead().then(setItems).catch((e) => notify(e.message)), [notify]);
  useEffect(() => {
    load();
  }, [load]);

  const readNow = async (it) => {
    setBusy(it.id);
    try {
      const r = await api.readToRead(it.id);
      notify(r.status === "exists" ? "This paper is in your library already." : "The app is reading the paper.");
      await load();
      onChanged?.();
    } catch (e) {
      notify(e.message); // for example: no free PDF. The student can upload the PDF.
    } finally {
      setBusy("");
    }
  };
  const upload = async (it, file) => {
    if (!file) return;
    setBusy(it.id);
    try {
      await api.uploadToRead(it.id, file);
      await load();
      onChanged?.();
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy("");
    }
  };
  const suggest = async () => {
    setBusy("suggest");
    try {
      const r = await api.refreshSuggestions();
      notify(r.message);
      await load();
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy("");
    }
  };
  const notUseful = async (it) => {
    try {
      await api.setToRead(it.id, "not_useful");
      await load();
    } catch (e) {
      notify(e.message);
    }
  };

  if (!items) return <p className="muted">Loading…</p>;
  return (
    <section className="toread" aria-label="To read">
      <h1>To read</h1>
      <p className="lead">Papers that you did not read yet. The best fit for your question is first. The score comes from the abstract and your question. Read the reason before you trust it.</p>
      {suggestOn && (
        <p>
          <button className="btn small ghost" disabled={busy === "suggest"} onClick={suggest}>
            {busy === "suggest" ? "Looking…" : "Suggest papers now"}
          </button>{" "}
          <span className="small muted">The app also looks once a day. It uses the references and citations of your papers.</span>
        </p>
      )}
      {items.length === 0 ? (
        <p className="muted">The list is empty. Import a BibTeX or RIS file in Settings, or add a paper by DOI in the library with “Add to To read”.</p>
      ) : (
        <ol className="toreadlist">
          {items.map((it) => (
            <li key={it.id} className="toreaditem">
              <div className="trscore" role="img" aria-label={`Fit score ${it.score} of 100`}>
                {it.score}
              </div>
              <div className="trbody">
                <strong>{it.title}</strong> {it.source === "suggested" && <span className="small tag">Suggested</span>}
                <p className="small muted">
                  {[it.authors.slice(0, 3).map((a) => a.split(",")[0]).join(", "), it.year, it.venue].filter(Boolean).join(" · ")}
                </p>
                <p className="small">{it.reason}</p>
                {it.abstract && (
                  <details>
                    <summary className="small">Abstract</summary>
                    <p className="small">{it.abstract}</p>
                  </details>
                )}
                <div className="row">
                  <button className="btn small" disabled={busy === it.id} onClick={() => readNow(it)}>
                    {busy === it.id ? "Working…" : "Read now"}
                  </button>
                  <label className="btn small ghost filebtn">
                    Upload the PDF
                    <input type="file" accept="application/pdf,.pdf" hidden onChange={(e) => upload(it, e.target.files[0])} />
                  </label>
                  <button className="btn small ghost" onClick={() => notUseful(it)}>
                    Not useful
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
