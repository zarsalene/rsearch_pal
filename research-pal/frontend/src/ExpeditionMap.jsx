import { useEffect, useState } from "react";
import { api } from "./api.js";

const STATE_TEXT = { not_started: "Not started", growing: "Growing", done: "Done" };
// The six regions sit on one winding road. x and y are places in the picture.
const SPOTS = [
  [70, 150],
  [190, 70],
  [320, 140],
  [450, 70],
  [580, 140],
  [680, 60],
];
const R = 30;
const CIRC = 2 * Math.PI * R;

// The PhD road in one picture. Each region is a ring that fills with color. On a small screen, the list below the picture has the same data.
export function MapView({ map, onGo }) {
  const [open, setOpen] = useState(null);
  const sel = map.regions.find((r) => r.code === open);
  const road = SPOTS.map(([x, y], i) => (i ? `S ${(SPOTS[i - 1][0] + x) / 2} ${(SPOTS[i - 1][1] + y) / 2 + (i % 2 ? -40 : 40)}, ${x} ${y}` : `M ${x} ${y}`)).join(" ");
  return (
    <section className="today-block expedition" aria-label="PhD Expedition map">
      <h2>PhD Expedition</h2>
      <p className="small muted">The whole road to your defense. {map.total}% of the road is done. Each region fills when you do real work. Click a region to see a first step.</p>
      <svg className="mapsvg" viewBox="0 0 760 220" role="group" aria-label={`Map of the PhD road: ${map.regions.map((r) => `${r.name} ${r.percent}%`).join(", ")}`}>
        <path d={road} className="road" />
        {map.regions.map((r, i) => {
          const [x, y] = SPOTS[i];
          return (
            <g
              key={r.code}
              className={"region " + r.state + (open === r.code ? " on" : "")}
              transform={`translate(${x} ${y})`}
              role="button"
              tabIndex={0}
              aria-label={`${r.name}, ${r.percent}%, ${STATE_TEXT[r.state]}`}
              onClick={() => setOpen(open === r.code ? null : r.code)}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setOpen(open === r.code ? null : r.code)}
            >
              <circle r={R} className="base" />
              <circle r={R} className="ring" strokeDasharray={CIRC} strokeDashoffset={CIRC * (1 - r.percent / 100)} transform="rotate(-90)" />
              <text className="pct" textAnchor="middle" dy="5">
                {r.percent}%
              </text>
              <text className="rname" textAnchor="middle" y={R + 20}>
                {r.name}
              </text>
            </g>
          );
        })}
      </svg>
      <ol className="regions" aria-label="Regions of the road">
        {map.regions.map((r) => (
          <li key={r.code}>
            <button className={"regionbtn " + r.state + (open === r.code ? " on" : "")} aria-pressed={open === r.code} onClick={() => setOpen(open === r.code ? null : r.code)}>
              <span className="rn">{r.name}</span>
              <span className="bar" aria-hidden="true">
                <span style={{ width: r.percent + "%" }} />
              </span>
              <span className="small muted">
                {r.percent}% · {STATE_TEXT[r.state]}
              </span>
            </button>
          </li>
        ))}
      </ol>
      {sel && (
        <div className="regiondetail" role="region" aria-label={`${sel.name}: what to do`}>
          <h3>
            {sel.name} <span className="small muted">{sel.percent}% · {STATE_TEXT[sel.state]}</span>
          </h3>
          <p className="small muted">{sel.detail}</p>
          <p>
            <strong>First step:</strong> {sel.first_step}
          </p>
          {sel.target && (
            <button className="btn small" onClick={() => onGo(sel.target)}>
              Go there
            </button>
          )}
        </div>
      )}
    </section>
  );
}

export default function ExpeditionMap({ onGo, notify }) {
  const [map, setMap] = useState(null);
  useEffect(() => {
    api.journeyMap().then(setMap).catch((e) => notify(e.message));
  }, [notify]);
  return map ? <MapView map={map} onGo={onGo} /> : null;
}
