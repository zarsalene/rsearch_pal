import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { Icon } from "./icons.jsx";
import SimpleText from "./SimpleText.jsx";

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
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 1.6;
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const isPhone = () => window.matchMedia("(max-width: 820px)").matches; // on a phone the map is one column: no pan, no zoom

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
      {n.answer ? <SimpleText text={n.answer} load={() => api.simplifyText(n.answer)} className="" /> : <p className="muted small">The card hides this claim, because the AI gave no proof for it. Read the paper yourself.</p>}
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

// One research paper as a map of small cards. Drag to move the map. Ctrl and scroll, or the buttons, to zoom.
// The position and the zoom live in a ref and go straight to the DOM, so moving the map never re-renders React.
export default function MindMap({ title, map, busy, paperId, hasPdf, onMake, onDelete, notify }) {
  const [closed, setClosed] = useState({});
  const nodes = map?.nodes || [];
  const roots = nodes.filter((n) => n.parent === "root");
  const kidsOf = (id) => nodes.filter((n) => n.parent === id);
  const toggle = (id) => setClosed((c) => ({ ...c, [id]: !c[id] }));
  const branches = roots.filter((r) => kidsOf(r.id).length > 0);
  const allShut = branches.length > 0 && branches.every((r) => closed[r.id]);
  const toggleAll = () => setClosed(allShut ? {} : Object.fromEntries(branches.map((r) => [r.id, true])));

  const vpRef = useRef(null);
  const canvasRef = useRef(null);
  const view = useRef({ x: 0, y: 0, s: 1 });
  const drag = useRef(null);
  const [zoomPct, setZoomPct] = useState(100); // only for the label of the buttons; it changes on a click, not while you drag

  const apply = useCallback((smooth) => {
    const el = canvasRef.current;
    if (!el) return;
    const { x, y, s } = view.current;
    el.classList.toggle("smooth", !!smooth);
    el.style.transform = `translate(${x}px, ${y}px) scale(${s})`;
  }, []);

  const zoomAt = useCallback(
    (factor, cx, cy, smooth) => {
      const v = view.current;
      const s = clamp(v.s * factor, MIN_ZOOM, MAX_ZOOM);
      const k = s / v.s;
      v.x = cx - (cx - v.x) * k; // the point under (cx, cy) stays where it is
      v.y = cy - (cy - v.y) * k;
      v.s = s;
      apply(smooth);
      setZoomPct(Math.round(s * 100));
    },
    [apply]
  );

  const zoomCenter = (factor) => {
    const r = vpRef.current?.getBoundingClientRect();
    if (r) zoomAt(factor, r.width / 2, r.height / 2, true);
  };

  // Show the whole map: scale it down to the width of the box, at the top left.
  const fit = useCallback(
    (smooth) => {
      const vp = vpRef.current;
      const c = canvasRef.current;
      if (!vp || !c) return;
      const s = isPhone() ? 1 : clamp((vp.clientWidth - 32) / c.scrollWidth, MIN_ZOOM, 1);
      view.current = { x: 0, y: 0, s };
      apply(smooth);
      setZoomPct(Math.round(s * 100));
    },
    [apply]
  );

  const has = nodes.length > 0;
  useEffect(() => {
    if (has) requestAnimationFrame(() => fit(false));
  }, [has, fit]);

  useEffect(() => {
    const vp = vpRef.current;
    if (!vp) return;
    // Ctrl (or Cmd) and scroll zoom the map. A normal scroll still scrolls the page.
    const onWheel = (e) => {
      if (!(e.ctrlKey || e.metaKey) || isPhone()) return;
      e.preventDefault();
      const r = vp.getBoundingClientRect();
      zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top, false);
    };
    vp.addEventListener("wheel", onWheel, { passive: false });
    return () => vp.removeEventListener("wheel", onWheel);
  }, [has, zoomAt]);

  const onPointerDown = (e) => {
    if (isPhone() || e.button !== 0 || e.target.closest("button, summary, a, input, details, blockquote, .mm-tools")) return;
    drag.current = { px: e.clientX, py: e.clientY, x: view.current.x, y: view.current.y };
    e.currentTarget.setPointerCapture(e.pointerId);
    e.currentTarget.classList.add("dragging");
  };
  const onPointerMove = (e) => {
    const d = drag.current;
    if (!d) return;
    view.current.x = d.x + (e.clientX - d.px);
    view.current.y = d.y + (e.clientY - d.py);
    apply(false);
  };
  const onPointerUp = (e) => {
    if (!drag.current) return;
    drag.current = null;
    e.currentTarget.classList.remove("dragging");
  };
  const onKeyDown = (e) => {
    if (e.target !== e.currentTarget || isPhone()) return; // keys work when the map itself has the focus
    const v = view.current;
    const step = 48;
    const move = { ArrowLeft: [step, 0], ArrowRight: [-step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] }[e.key];
    if (move) {
      e.preventDefault();
      v.x += move[0];
      v.y += move[1];
      apply(true);
    } else if (e.key === "+" || e.key === "=") zoomCenter(1.2);
    else if (e.key === "-") zoomCenter(1 / 1.2);
    else if (e.key === "0") fit(true);
  };

  return (
    <section className="mindmap" aria-label="Mind map">
      <div className="mm-head">
        <h2>Mind map</h2>
        <div className="row">
          {branches.length > 0 && (
            <button className="link" onClick={toggleAll}>
              {allShut ? "Open all branches" : "Close all branches"}
            </button>
          )}
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
        <div
          className="mm-viewport"
          ref={vpRef}
          tabIndex={0}
          role="group"
          aria-label="Mind map. Drag to move. Arrow keys move, plus and minus zoom, zero shows all."
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onKeyDown={onKeyDown}
        >
          <div className="mm-tools" role="toolbar" aria-label="Map view">
            <button onClick={() => zoomCenter(1 / 1.2)} disabled={zoomPct <= MIN_ZOOM * 100} aria-label="Zoom out" title="Zoom out">
              <Icon name="zoomout" size={16} />
            </button>
            <span className="mm-zoom" aria-live="polite">
              {zoomPct}%
            </span>
            <button onClick={() => zoomCenter(1.2)} disabled={zoomPct >= MAX_ZOOM * 100} aria-label="Zoom in" title="Zoom in">
              <Icon name="zoomin" size={16} />
            </button>
            <button onClick={() => fit(true)} aria-label="Show the whole map" title="Show the whole map">
              <Icon name="fit" size={16} />
            </button>
          </div>
          <div className="mm-canvas" ref={canvasRef}>
            <div className="mm">
              <div className="mm-root">
                <div className="mm-card mm-center">
                  <Icon name="doc" size={16} />
                  <h4>{title}</h4>
                </div>
              </div>
              <div className="mm-items">
                {roots.map((r, i) => {
                  const kids = kidsOf(r.id);
                  const shut = !!closed[r.id];
                  return (
                    <div key={r.id} className="mm-item" style={{ "--i": i }}>
                      <div className="mm-row">
                        <Part n={r} paperId={paperId} hasPdf={hasPdf} notify={notify} kids={kids.length} collapsed={shut} onToggle={() => toggle(r.id)} />
                        {kids.length > 0 && (
                          <div className={"mm-kidwrap" + (shut ? " shut" : "")} aria-hidden={shut}>
                            <div className="mm-items mm-kids">
                              {kids.map((k, j) => (
                                <div key={k.id} className="mm-item" style={{ "--i": i + j + 1 }}>
                                  <Part n={k} paperId={paperId} hasPdf={hasPdf} notify={notify} kids={0} />
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}
      {nodes.length > 0 && <p className="muted small">Built from the cards. It follows them each time you open the card. A dot shows if the server found the quote in the PDF. Drag the map to move it. Ctrl and scroll zoom it.</p>}
    </section>
  );
}
