import { useEffect, useState } from "react";
import { api } from "./api.js";

const LABEL = { authors: "Authors", year: "Year", venue: "Venue", doi: "DOI" };

// The metadata of the paper. The server keeps a value from the AI only if the PDF has it. A value that it could not check shows "Check".
export default function MetaBlock({ paper, onChanged, notify }) {
  const [edit, setEdit] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ authors: "", year: "", venue: "", doi: "" });
  const check = paper.meta_check || [];
  useEffect(() => setForm({ authors: (paper.authors || []).join("; "), year: paper.year || "", venue: paper.venue || "", doi: paper.doi || "" }), [paper]);
  const empty = !(paper.authors || []).length && !paper.year && !paper.venue && !paper.doi && !check.length;

  const fill = async () => {
    setBusy(true);
    try {
      await api.extractMeta(paper.id);
      await onChanged();
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };
  const save = async (e) => {
    e.preventDefault();
    try {
      await api.editMeta(paper.id, { authors: form.authors.split(/;|\n/).map((a) => a.trim()).filter(Boolean), year: form.year, venue: form.venue, doi: form.doi });
      setEdit(false);
      await onChanged();
    } catch (err) {
      notify(err.message);
    }
  };
  const show = (k) => {
    const v = k === "authors" ? (paper.authors || []).join("; ") : paper[k];
    return v ? <span>{v}</span> : <span className="badge b-warn">Check</span>;
  };

  return (
    <section className="metablock" aria-label="Metadata of the paper">
      {edit ? (
        <form onSubmit={save} className="metaform">
          <label>
            Authors (separate with “;”)
            <input value={form.authors} onChange={(e) => setForm({ ...form, authors: e.target.value })} />
          </label>
          <label>
            Year
            <input value={form.year} maxLength={4} onChange={(e) => setForm({ ...form, year: e.target.value })} />
          </label>
          <label>
            Venue
            <input value={form.venue} onChange={(e) => setForm({ ...form, venue: e.target.value })} />
          </label>
          <label>
            DOI
            <input value={form.doi} onChange={(e) => setForm({ ...form, doi: e.target.value })} />
          </label>
          <div className="row">
            <button className="btn small">Save</button>
            <button type="button" className="link" onClick={() => setEdit(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <>
          <dl className="metalist">
            {Object.keys(LABEL).map((k) => (
              <div key={k}>
                <dt>{LABEL[k]}</dt>
                <dd>{show(k)}</dd>
              </div>
            ))}
          </dl>
          {empty && <p className="small muted">The metadata is not filled. Click “Fill from the PDF”.</p>}
          {check.length > 0 && <p className="small muted">The server could not find {check.map((c) => LABEL[c]).join(", ")} in the PDF. Check it, or write it yourself.</p>}
          <div className="row">
            <button className="btn small ghost" disabled={busy} onClick={fill}>
              {busy ? "Reading…" : "Fill from the PDF"}
            </button>
            <button className="btn small ghost" onClick={() => setEdit(true)}>
              Edit
            </button>
          </div>
        </>
      )}
    </section>
  );
}
