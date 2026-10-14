import { useEffect, useState } from "react";
import { api } from "./api.js";
import { Icon } from "./icons.jsx";
import { featureOn, useApp } from "./store.js";

// The student chooses the default AI, one fallback, and the model of each. API keys stay in the server environment.
function AiChoice({ config, onConfig, notify }) {
  const options = config?.ai_options || [];
  const cur = config?.ai_choice;
  const [primary, setPrimary] = useState("");
  const [fallback, setFallback] = useState("");
  const [models, setModels] = useState({});
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState("");

  useEffect(() => {
    if (!cur) return;
    setPrimary(cur.primary);
    setFallback(cur.fallbacks[0] || "");
    setModels(cur.models || {});
  }, [cur]);

  if (!options.length || !cur) return null;
  const opt = (n) => options.find((o) => o.provider === n);
  const modelFor = (n) => models[n] ?? opt(n)?.default_model ?? "";
  const label = (o) => o.provider.charAt(0).toUpperCase() + o.provider.slice(1) + (o.ready ? "" : " (key missing)");

  const apply = async (fn, done) => {
    setBusy(true);
    setSaved("");
    try {
      onConfig(await fn());
      setSaved(done);
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };
  const save = () => {
    const chosen = {};
    for (const n of [primary, fallback].filter(Boolean)) if ((models[n] || "").trim()) chosen[n] = models[n].trim();
    return apply(() => api.setAi({ primary, fallbacks: fallback ? [fallback] : [], models: chosen }), "Saved. It works now.");
  };

  // A plain function, not a component: a component inside a component would lose the focus of the input on each key.
  const row = ({ title, value, onProvider, n, none }) => (
    <div className="aichoice">
      <div className="inwrap">
        <label htmlFor={"ai-" + title}>{title}</label>
        <select id={"ai-" + title} value={value} onChange={(e) => onProvider(e.target.value)}>
          {none && <option value="">None</option>}
          {options
            .filter((o) => title === "Default AI" || o.provider !== primary)
            .map((o) => (
              <option key={o.provider} value={o.provider}>
                {label(o)}
              </option>
            ))}
        </select>
      </div>
      {n && (
        <div className="inwrap">
          <label htmlFor={"m-" + title}>Model</label>
          <input id={"m-" + title} type="text" list={"models-" + n} value={modelFor(n)} onChange={(e) => setModels({ ...models, [n]: e.target.value })} spellCheck={false} />
          <datalist id={"models-" + n}>
            {(opt(n)?.models || []).map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </div>
      )}
    </div>
  );

  return (
    <div className="group">
      <h2>AI models</h2>
      <p className="muted">
        Choose which AI reads your papers. If the default gives an error, the fallback answers. The next request tries the default again. Pick a model from the list, or type any model name that the provider knows.
      </p>
      {row({ title: "Default AI", value: primary, onProvider: (v) => { setPrimary(v); if (v === fallback) setFallback(""); }, n: primary })}
      {row({ title: "Fallback AI", value: fallback, onProvider: setFallback, n: fallback, none: true })}
      <p className="small muted">The API keys stay on the server, in the file .env. They never go through this page. A provider without a key is skipped.</p>
      <div className="row">
        <button className="btn small" disabled={busy || !primary} onClick={save}>
          {busy ? "Saving…" : "Save"}
        </button>
        {cur.custom && (
          <button className="btn small ghost" disabled={busy} onClick={() => apply(api.resetAi, "Back to the settings of the server.")}>
            Use the settings of the server
          </button>
        )}
        {saved && <span className="muted small">{saved}</span>}
      </div>
    </div>
  );
}

// Each feature has a switch. A switch hides the feature and the server refuses its calls. Your data stays.
function FeatureSwitches({ features, onFeatures, notify }) {
  const [busy, setBusy] = useState("");
  if (!features?.length) return null;
  const toggle = async (f) => {
    setBusy(f.name);
    try {
      onFeatures(await api.setFeatures({ [f.name]: !f.enabled }));
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy("");
    }
  };
  return (
    <div className="group">
      <h2>Features</h2>
      <p className="muted">Switch a feature off if it gives a problem. The rest of the app keeps working. Your data stays.</p>
      <ul className="switches">
        {features.map((f) => (
          <li key={f.name}>
            <label className="switchrow">
              <input type="checkbox" role="switch" checked={f.enabled} disabled={busy === f.name} onChange={() => toggle(f)} />
              <span>
                <strong>{f.label}</strong>
                <span className="muted small"> {f.description}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
    </div>
  );
}

// The game feels. Both choices stay in this browser.
function GamePrefs() {
  const prefs = useApp((s) => s.prefs);
  const setPref = useApp((s) => s.setPref);
  return (
    <div className="group">
      <h2>Game feel</h2>
      <p className="muted">Sound and movement of the game. Calm mode has no confetti and no shaking. It starts on when your phone asks to reduce motion.</p>
      <ul className="switches">
        <li>
          <label className="switchrow">
            <input type="checkbox" role="switch" checked={prefs.sound} onChange={() => setPref("sound", !prefs.sound)} />
            <span>
              <strong>Sound effects</strong>
              <span className="muted small"> Soft sounds for right answers, wins and level ups.</span>
            </span>
          </label>
        </li>
        <li>
          <label className="switchrow">
            <input type="checkbox" role="switch" checked={prefs.calm} onChange={() => setPref("calm", !prefs.calm)} />
            <span>
              <strong>Calm mode</strong>
              <span className="muted small"> No confetti, no shaking, a quiet Duck.</span>
            </span>
          </label>
        </li>
      </ul>
    </div>
  );
}

// Each answer of the AI is written in a log. The log has no text of your papers. It says which feature, which paper and which model.
function AiUse({ notify }) {
  const [log, setLog] = useState(null);
  useEffect(() => {
    let alive = true;
    api.aiLog(1).then((d) => alive && setLog(d)).catch((e) => alive && notify(e.message));
    return () => {
      alive = false;
    };
  }, [notify]);
  if (!log) return null;
  const parts = Object.entries(log.by_feature);
  return (
    <div className="group">
      <h2>AI use log</h2>
      <p className="muted">
        The app writes one line for each answer of the AI: the feature, the paper and the model. You can use this record for the AI use statement of your thesis.
        A saved answer is not counted, because the AI did not help again.
      </p>
      <p>
        {log.total === 0 ? "The AI has not helped yet." : `The AI helped ${log.total} ${log.total === 1 ? "time" : "times"}: ${parts.map(([f, n]) => `${f} ${n}`).join(", ")}.`}
      </p>
    </div>
  );
}

export default function Settings({ config, features, onConfig, onFeatures, onImported, onLogout, notify }) {
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

      <AiChoice config={config} onConfig={onConfig} notify={notify} />

      <FeatureSwitches features={features} onFeatures={onFeatures} notify={notify} />
      {features && featureOn(features, "game") && <GamePrefs />}

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

      <AiUse notify={notify} />

      <div className="group">
        <h2>Session</h2>
        <button className="btn ghost" onClick={onLogout}><Icon name="logout" size={15} /> Sign out</button>
      </div>
    </section>
  );
}
