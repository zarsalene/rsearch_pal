import { useEffect, useMemo, useState } from "react";
import { api } from "./api.js";
import SimpleText from "./SimpleText.jsx";

const RELATION = {
  same_problem: "Same problem",
  same_method: "Same method",
  same_data: "Same data",
  builds_on: "One builds on the other",
  compares_with: "Can be compared",
  complements: "They complement each other",
  other: "Other link",
};
const edgeKey = (e) => [e.source, e.target].sort().join(":");

// The AI explains one link. Each claim has a quote that the server found in the PDF.
function Explain({ state, onAgain, notify }) {
  if (!state || state.loading) {
    return (
      <div className="progress" role="status">
        <span className="dot-anim" />
        The AI reads the best passages of both papers. This takes 10 to 30 seconds.
      </div>
    );
  }
  if (state.error) {
    return (
      <div className="errbox" role="alert">
        <strong>The link could not be explained.</strong>
        <p>{state.error}</p>
        <button className="link" onClick={onAgain}>Try again</button>
      </div>
    );
  }
  const d = state.data;
  return (
    <div className="explain">
      <div className="row">
        <span className="badge b-info">{RELATION[d.relation] || RELATION.other}</span>
        {d.status !== "verified" && <span className="badge b-bad">No quote was found in the PDFs. Do not trust this text.</span>}
      </div>
      <h4>What links them</h4>
      <SimpleText text={d.summary} load={() => api.simplifyText(d.summary)} />
      {d.shared.length > 0 && (
        <>
          <h4>What they share</h4>
          <div className="kw">{d.shared.map((k) => <span key={k} className="kwchip">{k}</span>)}</div>
        </>
      )}
      {d.differences && (
        <>
          <h4>How they differ</h4>
          <SimpleText text={d.differences} load={() => api.simplifyText(d.differences)} />
        </>
      )}
      {d.evidence.length > 0 && (
        <div className="evidence">
          {d.evidence.map((e, i) => (
            <blockquote key={i} className={e.verified ? "" : "q-bad"}>
              <span>{e.quote}</span>
              {e.verified ? (
                <button className="chip" title="Open the PDF at this page" onClick={() => api.openPdf(e.paper_id, e.page).catch((x) => notify(x.message))}>
                  {e.title.slice(0, 28)}{e.title.length > 28 ? "…" : ""} · p. {e.page}
                </button>
              ) : (
                <span className="chip bad">Quote not found in the PDF</span>
              )}
            </blockquote>
          ))}
        </div>
      )}
      <button className="link" onClick={onAgain}>Explain again</button>
    </div>
  );
}

const W = 800,
  H = 520;

function layout(nodes, edges) {
  const n = nodes.length;
  if (!n) return {};
  const pos = nodes.map((_, i) => ({ x: W / 2 + Math.cos((2 * Math.PI * i) / n) * H * 0.34, y: H / 2 + Math.sin((2 * Math.PI * i) / n) * H * 0.34, vx: 0, vy: 0 }));
  const idx = new Map(nodes.map((nd, i) => [nd.id, i]));
  for (let it = 0; it < 260; it++) {
    for (let i = 0; i < n; i++)
      for (let j = i + 1; j < n; j++) {
        const dx = pos[i].x - pos[j].x, dy = pos[i].y - pos[j].y;
        const d2 = Math.max(dx * dx + dy * dy, 25), d = Math.sqrt(d2), f = 3200 / d2;
        pos[i].vx += (dx / d) * f; pos[i].vy += (dy / d) * f;
        pos[j].vx -= (dx / d) * f; pos[j].vy -= (dy / d) * f;
      }
    for (const e of edges) {
      const a = pos[idx.get(e.source)], b = pos[idx.get(e.target)];
      if (!a || !b) continue;
      const dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) || 1, f = (d - 150) * 0.02;
      a.vx += (dx / d) * f; a.vy += (dy / d) * f;
      b.vx -= (dx / d) * f; b.vy -= (dy / d) * f;
    }
    for (const p of pos) {
      p.vx += (W / 2 - p.x) * 0.004; p.vy += (H / 2 - p.y) * 0.004;
      p.x = Math.min(W - 70, Math.max(70, p.x + p.vx * 0.85)); p.y = Math.min(H - 40, Math.max(40, p.y + p.vy * 0.85));
      p.vx *= 0.5; p.vy *= 0.5;
    }
  }
  return Object.fromEntries(nodes.map((nd, i) => [nd.id, pos[i]]));
}

export default function Graph({ onOpenCard, notify }) {
  const [g, setG] = useState(null);
  const [min, setMin] = useState(0.4);
  const [open, setOpen] = useState("");
  const [ex, setEx] = useState({});

  useEffect(() => {
    api.graph().then((d) => { setG(d); setMin(d.threshold); }).catch((e) => notify(e.message));
  }, [notify]);

  const edges = useMemo(() => (g ? g.edges.filter((e) => e.shared.length > 0 || e.sim >= min) : []), [g, min]);
  const pos = useMemo(() => (g ? layout(g.nodes, edges) : {}), [g, edges]);

  const explain = async (e, refresh = false) => {
    const key = edgeKey(e);
    setOpen(key);
    if (ex[key]?.data && !refresh) return;
    setEx((cur) => ({ ...cur, [key]: { loading: true } }));
    try {
      const data = await api.explainLink(e.source, e.target, refresh);
      setEx((cur) => ({ ...cur, [key]: { data } }));
    } catch (err) {
      setEx((cur) => ({ ...cur, [key]: { error: err.message } }));
    }
  };
  const toggleOpen = (e) => (open === edgeKey(e) ? setOpen("") : explain(e));

  if (!g) return <p className="muted">Loading…</p>;
  if (g.nodes.length < 2) return <section><h1>Links</h1><p className="lead">Upload at least two papers. Research Pal then links the papers that talk about the same things.</p></section>;
  const title = Object.fromEntries(g.nodes.map((n) => [n.id, n.title]));

  return (
    <section>
      <h1>Links</h1>
      <p className="lead">Two papers have a link when their cards talk about similar things, or share a keyword that appears in both PDFs. Click a line, or "What links them?", and the AI explains the link with quotes.</p>
      <div className="slider">
        <label htmlFor="min">Show links from {Math.round(min * 100)}% similarity</label>
        <input id="min" type="range" min="0.25" max="0.9" step="0.01" value={min} onChange={(e) => setMin(parseFloat(e.target.value))} />
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="graph" role="img" aria-label="Graph of linked papers">
        {edges.map((e, i) => {
          const a = pos[e.source], b = pos[e.target];
          if (!a || !b) return null;
          return (
            <g key={i} className={"gline" + (open === edgeKey(e) ? " sel" : "")} onClick={() => explain(e)}>
              <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="gedge" style={{ strokeWidth: 1 + e.sim * 4 }} />
              <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="ghit" />
            </g>
          );
        })}
        {g.nodes.map((n) => {
          const p = pos[n.id];
          if (!p) return null;
          const t = n.title.length > 30 ? n.title.slice(0, 29) + "…" : n.title;
          return (
            <g key={n.id} className={"gnode v-" + (n.verdict || "none")} transform={`translate(${p.x},${p.y})`} tabIndex={0} role="button" aria-label={n.title}
              onClick={() => onOpenCard(n.id)} onKeyDown={(e) => e.key === "Enter" && onOpenCard(n.id)}>
              <circle r="10" />
              <text y="26" textAnchor="middle">{t}</text>
            </g>
          );
        })}
      </svg>
      <ul className="linklist">
        {edges.map((e, i) => (
          <li key={i} className={open === edgeKey(e) ? "open" : ""}>
            <div>
              <button className="link" onClick={() => onOpenCard(e.source)}>{title[e.source]}</button>
              <span className="muted"> and </span>
              <button className="link" onClick={() => onOpenCard(e.target)}>{title[e.target]}</button>
            </div>
            <div className="row small muted">
              <span>{Math.round(e.sim * 100)}% similar</span>
              {e.shared.map((k) => <span key={k} className="kwchip">{k}</span>)}
              <button className="link" onClick={() => toggleOpen(e)} aria-expanded={open === edgeKey(e)}>
                {open === edgeKey(e) ? "Hide" : "What links them?"}
              </button>
            </div>
            {open === edgeKey(e) && <Explain state={ex[edgeKey(e)]} onAgain={() => explain(e, true)} notify={notify} />}
          </li>
        ))}
        {!edges.length && <li className="muted">No link at this level. Move the slider to the left.</li>}
      </ul>
    </section>
  );
}
