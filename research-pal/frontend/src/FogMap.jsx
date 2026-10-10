import { useEffect, useId, useMemo, useState } from "react";
import { motion } from "motion/react";
import { api } from "./api.js";
import { Explain, layout } from "./Graph.jsx";
import { play } from "./juice.js";
import { useApp } from "./store.js";

// The map of what the student found. The papers are islands. A possible link between two papers lies in the fog.
// The student explores a link: the AI reads the best passages of both papers. With a checked quote, the fog opens and the link shines.
// Without a checked quote, the link stays "unclear" and gives no points.
const W = 800;
const H = 520;
const RANK_NAME = ["Seen", "Read", "Explained", "Mastered"];
const key = (e) => [e.source, e.target].sort().join(":");

export default function FogMap({ notify }) {
  const id = useId().replace(/:/g, "");
  const [m, setM] = useState(null);
  const [sel, setSel] = useState("");
  const [ex, setEx] = useState({});
  const { openPaper, refreshGame } = useApp.getState();

  const load = () => api.gameMap().then(setM).catch((e) => notify(e.message));
  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const pos = useMemo(() => (m ? layout(m.nodes, m.edges) : {}), [m]);
  const title = useMemo(() => Object.fromEntries((m?.nodes || []).map((n) => [n.id, n.title])), [m]);

  const explain = async (e, again = false) => {
    const k = key(e);
    setSel(k);
    setEx((cur) => ({ ...cur, [k]: { loading: true } }));
    try {
      const data = await api.explainLink(e.source, e.target, again);
      setEx((cur) => ({ ...cur, [k]: { data } }));
      play(data.status === "verified" ? "correct" : "wrong");
      await refreshGame(); // the server pays the link, and maybe a lucky find
      await load();
    } catch (err) {
      setEx((cur) => ({ ...cur, [k]: { error: err.message } }));
    }
  };
  const pick = (e) => {
    play("tap");
    setSel(key(e));
    // A link that is found has a saved explanation: showing it costs no AI call.
    if (e.state !== "fog" && !ex[key(e)]?.data) explain(e);
  };

  if (!m) return <p className="muted">Loading…</p>;
  if (m.nodes.length < 2)
    return (
      <div className="gempty">
        <h3>The map needs two papers</h3>
        <p className="muted">Add at least two papers with a ready card. Then the map shows how they may link.</p>
      </div>
    );

  const selected = m.edges.find((e) => key(e) === sel);
  const { found, fog, unclear } = m.stats;

  return (
    <div>
      <p className="lead">
        Each paper is an island. A link between two papers lies in the fog until you explore it. Find links, and the fog goes away.
      </p>
      <div className="mapstats">
        <span>
          <i className="d found" /> Found: <strong>{found}</strong>
        </span>
        <span>
          <i className="d fog" /> In the fog: <strong>{fog}</strong>
        </span>
        {unclear > 0 && (
          <span>
            <i className="d unclear" /> Unclear: <strong>{unclear}</strong>
          </span>
        )}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="fogmap" role="group" aria-label="Map of your papers and their possible links">
        <defs>
          <filter id={id + "soft"} x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="16" />
          </filter>
          <mask id={id + "clear"} maskUnits="userSpaceOnUse" x="0" y="0" width={W} height={H}>
            <rect width={W} height={H} fill="#fff" />
            <g filter={`url(#${id}soft)`} fill="#000" stroke="#000" strokeLinecap="round">
              {m.nodes.map((n) => pos[n.id] && <motion.circle key={n.id} cx={pos[n.id].x} cy={pos[n.id].y} initial={{ r: 0 }} animate={{ r: 56 + n.rank * 20 }} transition={{ duration: 0.9, ease: "easeOut" }} stroke="none" />)}
              {m.edges
                .filter((e) => e.state === "found" && pos[e.source] && pos[e.target])
                .map((e) => (
                  <motion.line key={key(e)} x1={pos[e.source].x} y1={pos[e.source].y} x2={pos[e.target].x} y2={pos[e.target].y} strokeWidth="62" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1.1 }} />
                ))}
            </g>
          </mask>
        </defs>
        <rect className="land" width={W} height={H} rx="16" />
        {m.edges.map((e) => {
          const a = pos[e.source];
          const b = pos[e.target];
          return a && b && <line key={key(e)} className={"fedge " + e.state + (sel === key(e) ? " sel" : "")} x1={a.x} y1={a.y} x2={b.x} y2={b.y} />;
        })}
        {m.nodes.map((n, i) => {
          const p = pos[n.id];
          if (!p) return null;
          const t = n.title.length > 28 ? n.title.slice(0, 27) + "…" : n.title;
          const above = m.nodes.slice(0, i).some((o) => pos[o.id] && Math.abs(pos[o.id].x - p.x) < 200 && Math.abs(pos[o.id].y - p.y) < 36);
          return (
            <g key={n.id} className={"fnode r" + n.rank} transform={`translate(${p.x},${p.y})`} tabIndex={0} role="button" aria-label={`${n.title}. ${RANK_NAME[n.rank]}. Open the card.`} onClick={() => openPaper(n.id)} onKeyDown={(ev) => ev.key === "Enter" && openPaper(n.id)}>
              <circle className="halo" r="19" />
              <circle className="core" r="11" />
              {n.rank === 3 && <path className="crownmark" d="M-8 -17 l3 -7 l5 5 l5 -5 l3 7 z" />}
              <text y={above ? -26 : 33} textAnchor="middle">
                {t}
              </text>
            </g>
          );
        })}
        <rect className="fog" width={W} height={H} rx="16" mask={`url(#${id}clear)`} />
        {m.edges.map((e) => {
          const a = pos[e.source];
          const b = pos[e.target];
          if (!a || !b) return null;
          const x = (a.x + b.x) / 2;
          const y = (a.y + b.y) / 2;
          const label = e.state === "fog" ? "Unexplored link. Explore it." : e.state === "found" ? "Found link. Show it." : "Unclear link. Show it.";
          return (
            <g key={key(e)} className={"fmark " + e.state + (sel === key(e) ? " sel" : "")} transform={`translate(${x},${y})`} tabIndex={0} role="button" aria-label={`${label} ${title[e.source]} and ${title[e.target]}`} onClick={() => pick(e)} onKeyDown={(ev) => ev.key === "Enter" && pick(e)}>
              <circle r="15" />
              <text dy="5" textAnchor="middle">
                {e.state === "fog" ? "?" : e.state === "found" ? "✦" : "!"}
              </text>
            </g>
          );
        })}
      </svg>

      {selected ? (
        <div className="fogpanel">
          <h3>
            {title[selected.source]} <span className="muted">and</span> {title[selected.target]}
          </h3>
          {ex[sel]?.data || ex[sel]?.loading || ex[sel]?.error ? (
            <>
              <Explain state={ex[sel]} onAgain={() => explain(selected, true)} notify={notify} />
              {ex[sel]?.data?.status !== "verified" && ex[sel]?.data && <p className="muted small">No checked quote was found. The map keeps this link unclear, and it gives no points.</p>}
            </>
          ) : (
            <>
              <p>
                This link is in the fog. The papers are <strong>{Math.round(selected.sim * 100)}% similar</strong>
                {selected.shared.length ? ` and share: ${selected.shared.join(", ")}` : ""}. Is it a real link?
              </p>
              <button className="btn" onClick={() => explain(selected)}>
                Explore this link
              </button>
              <span className="muted small"> The AI reads the best passages of both papers. A checked quote gives +10 XP, and maybe a lucky find.</span>
            </>
          )}
        </div>
      ) : (
        <p className="muted small">Click a mark on the map. A "?" is a link in the fog.</p>
      )}
    </div>
  );
}
