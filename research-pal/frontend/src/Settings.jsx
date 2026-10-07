import { useEffect, useState } from "react";
import { api } from "./api.js";
import { Icon } from "./icons.jsx";

export default function Settings({ config, onConfig, onImported, onLogout, notify }) {
  const [q, setQ] = useState("");
  const [msg, setMsg] = useState("");
  useEffect(() => setQ(config?.thesis_question || ""), [config]);

  const save = async () => {
    try {
      await api.saveSettings(q);
      onConfig({ ...config, thesis_question: q });
      setMsg("Saved.");
    } catch (e) {
      notify(e.message);
    }
  };
  const backup = async () => {
    try {
      const data = await api.exportAll();
      const url = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = "research-pal-backup-" + new Date().toISOString().slice(0, 10) + ".json";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      notify(e.message);
    }
  };
  const restore = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    try {
      const r = await api.importAll(JSON.parse(await f.text()));
      setMsg(`${r.added} papers restored. The search index is rebuilding.`);
      onImported();
    } catch (err) {
      notify(err.message || "This file is not a backup.");
    }
    e.target.value = "";
  };

  return (
    <section className="settings">
      <h1>Settings</h1>

      <div className="group">
        <h2>Your research question</h2>
        <p className="muted">The AI uses it to write the Use line: how each paper helps your thesis.</p>
        <textarea rows={3} value={q} onChange={(e) => setQ(e.target.value)} aria-label="Research question" />
        <div className="row">
          <button className="btn small" onClick={save}>Save</button>
          {msg && <span className="muted small">{msg}</span>}
        </div>
      </div>

      <div className="group">
        <h2>Backup</h2>
        <p className="muted">
          On a free server, the files can disappear when the server restarts. Download a backup every week. A backup holds the cards and the page texts (not the PDF files).
        </p>
        <div className="row">
          <button className="btn ghost" onClick={backup}><Icon name="download" size={15} /> Download backup</button>
          <label className="btn ghost filebtn">
            <Icon name="upload" size={15} /> Restore a backup
            <input type="file" accept="application/json,.json" onChange={restore} hidden />
          </label>
        </div>
      </div>

      <div className="group">
        <h2>AI and privacy</h2>
        {config && (
          <ul className="plain">
            {(config.providers?.length ? config.providers : [{ provider: config.provider, model: config.model, ready: config.llm_ready }]).map((p, i) => (
              <li key={p.provider}>
                {i === 0 ? "Default" : "Fallback"}: <strong>{p.provider}</strong>, model: <strong>{p.model}</strong>
                {!p.ready ? " (key missing)" : p.paused ? " (paused for a short time after an error)" : ""}
              </li>
            ))}
            <li>If the default fails, the next one answers. The default is tried again on the next request.</li>
            <li>Search and links run on your server. The embeddings do not leave it.</li>
            <li>When a card is made, selected passages of the paper go to the AI provider. For fully private reading, run the backend on your own computer with Ollama.</li>
          </ul>
        )}
      </div>

      <div className="group">
        <h2>Saved AI answers</h2>
        <p className="muted">
          The server saves each AI answer. The same request gets the saved answer, so it is fast and uses no free limit. “Read again” on a card always asks the AI again.
          {config?.saved_answers != null && ` Saved now: ${config.saved_answers}.`}
        </p>
        <button
          className="btn ghost"
          onClick={async () => {
            try {
              await api.clearCache();
              onConfig({ ...config, saved_answers: 0 });
            } catch (e) {
              notify(e.message);
            }
          }}
        >
          <Icon name="trash" size={15} /> Delete saved answers
        </button>
      </div>

      <div className="group">
        <h2>Session</h2>
        <button className="btn ghost" onClick={onLogout}><Icon name="logout" size={15} /> Sign out</button>
      </div>
    </section>
  );
}
