import { useState } from "react";
import { api } from "./api.js";
import { Icon } from "./icons.jsx";

const DOT = { verified: "ok", check: "warn", unverified: "bad", not_stated: "muted", not_found: "warn", edited: "info", suggestion: "info" };
const DOT_TEXT = {
  verified: "Checked in the paper",
  check: "Check the numbers",
  unverified: "Not verified",
  not_stated: "Not stated in the paper",
  not_found: "Not found in the excerpts",
  edited: "Edited by you",
  suggestion: "Not a claim of the paper",
};

function Part({ n, paperId, hasPdf, notify, kids, collapsed, onToggle }) {
  const dot = DOT[n.status] || "muted";
  const proof = (n.evidence || []).filter((e) => e.verified);
  return (
    <div className={"mm-card d-" + dot}>
      <div className="mm-label">
        <span className={"mm-dot b-" + dot} title={DOT_TEXT[n.status] || n.status} />
        <h4>{n.label}</h4>
        {kids > 0 && (
          <button className="mm-toggle" onClick={onToggle} aria-expanded={!collapsed} title={collapsed ? "Show the sub-parts" : "Hide the sub-parts"}>
            {collapsed ? `+${kids}` : "−"}
          </button>
        )}
      </div>
      {n.answer ? <p>{n.answer}</p> : <p className="muted small">The card hides this claim, because the AI gave no proof for it. Read the paper yourself.</p>}
      {n.unverified_numbers?.length > 0 && <p className="warn-line">Not found in the paper: {n.unverified_numbers.join(", ")}</p>}
      {proof.length > 0 && (
        <details className="mm-proof">
          <summary>Proof</summary>
          {proof.map((e, i) => (
            <blockquote key={i}>
              <span>{e.quote}</span>
              {hasPdf ? (
                <button className="chip" onClick={() => api.openPdf(paperId, e.page).catch((x) => notify(x.message))} title="Open the PDF at this page">
                  p. {e.page}
                </button>
              ) : (
                <span className="chip">p. {e.page}</span>
              )}
            </blockquote>
          ))}
        </details>
      )}
    </div>
  );
}

// One research paper as a map of small cards. Each card explains one part of the research.
export default function MindMap({ title, map, busy, paperId, hasPdf, onMake, onDelete, notify }) {
  const [closed, setClosed] = useState({});
  const nodes = map?.nodes || [];
  const roots = nodes.filter((n) => n.parent === "root");
  const kidsOf = (id) => nodes.filter((n) => n.parent === id);
  const toggle = (id) => setClosed((c) => ({ ...c, [id]: !c[id] }));

  return (
    <section className="mindmap" aria-label="Mind map">
      <div className="mm-head">
        <h2>Mind map</h2>
        <div className="row">
          <button className="btn small tint" disabled={busy} onClick={onMake}>
            <Icon name={nodes.length ? "refresh" : "sparkle"} size={15} /> {busy ? "Building…" : nodes.length ? "Build it again" : "Build the mind map"}
          </button>
          {nodes.length > 0 && (
            <button className="link" disabled={busy} onClick={onDelete}>
              Delete the map
            </button>
          )}
        </div>
      </div>
      {!nodes.length && !busy && <p className="muted small">The map is built from your cards: problem, method, result and limitation. If the paper has several cards, each card is one branch. It uses no AI, so it is instant and adds no new claim.</p>}
      {nodes.length > 0 && (
        <div className="mm-scroll">
          <div className="mm">
            <div className="mm-root">
              <div className="mm-card mm-center">
                <Icon name="doc" size={16} />
                <h4>{title}</h4>
              </div>
            </div>
            <div className="mm-items">
              {roots.map((r) => {
                const kids = kidsOf(r.id);
                const shut = !!closed[r.id];
                return (
                  <div key={r.id} className="mm-item">
                    <div className="mm-row">
                      <Part n={r} paperId={paperId} hasPdf={hasPdf} notify={notify} kids={kids.length} collapsed={shut} onToggle={() => toggle(r.id)} />
                      {kids.length > 0 && !shut && (
                        <div className="mm-items mm-kids">
                          {kids.map((k) => (
                            <div key={k.id} className="mm-item">
                              <Part n={k} paperId={paperId} hasPdf={hasPdf} notify={notify} kids={0} />
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
      {nodes.length > 0 && <p className="muted small">Built from the cards. It follows them each time you open the card. A dot shows if the server found the quote in the PDF.</p>}
    </section>
  );
}
