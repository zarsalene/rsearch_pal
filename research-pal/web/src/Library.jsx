import { useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { api } from "./api.js";
import { Icon } from "./icons.jsx";
import { useApp } from "./store.js";

const VERDICT = { read: "Read it", skim: "Skim it", skip: "Skip it" };

function statusText(p) {
  if (p.status === "queued") return "Waiting…";
  if (p.status === "processing") return "Reading the paper…";
  if (p.status === "error") return "Needs attention";
  return VERDICT[p.verdict] || "Ready";
}

export default function Library({ papers, selectedId, config, onSelect, onChanged, notify, onClose }) {
  const side = useRef(null);
  const drag = useRef(null);
  const ranks = useApp((s) => s.game?.ranks); // the rank of each paper in the card collection (see game.py)
  // On a phone you can push the drawer to the left to close it. The drawer follows the finger (no React state, so it stays smooth).
  const onTouchStart = (e) => {
    if (!window.matchMedia("(max-width: 820px)").matches) return;
    const t = e.touches[0];
    drag.current = { x: t.clientX, y: t.clientY, dx: 0, on: false };
  };
  const onTouchMove = (e) => {
    const d = drag.current;
    if (!d) return;
    const t = e.touches[0];
    const dx = t.clientX - d.x;
    const dy = t.clientY - d.y;
    if (!d.on && Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy) * 1.5) d.on = true;
    if (!d.on) return;
    d.dx = Math.min(0, dx);
    side.current.style.transition = "none";
    side.current.style.transform = `translateX(${d.dx}px)`;
  };
  const onTouchEnd = () => {
    const d = drag.current;
    drag.current = null;
    if (!d?.on) return;
    side.current.style.transition = "";
    side.current.style.transform = "";
    if (d.dx < -80) onClose?.();
  };
  const fileRef = useRef(null);
  const [purpose, setPurpose] = useState("");
  const [focus, setFocus] = useState("");
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const [filter, setFilter] = useState("");
  // The upload panel is open when the library is empty. After that, the student opens it with "Add paper".
  const [openSet, setOpenSet] = useState(null);
  const open = openSet ?? papers.length === 0;
  const shown = papers.filter((p) => !filter.trim() || `${p.title || ""} ${p.filename || ""} ${p.focus || ""}`.toLowerCase().includes(filter.trim().toLowerCase()));

  const pick = (list) => setFiles([...list].filter((f) => /\.pdf$/i.test(f.name) || f.type === "application/pdf"));

  const upload = async (e) => {
    e.preventDefault();
    if (!files.length) return;
    setBusy(true);
    let last = null;
    for (const f of files) {
      try {
        const r = await api.upload(f, purpose, focus);
        last = r.id;
      } catch (err) {
        notify(`${f.name}: ${err.message}`);
      }
    }
    setFiles([]);
    setPurpose("");
    setFocus("");
    if (fileRef.current) fileRef.current.value = "";
    setBusy(false);
    setOpenSet(false);
    await onChanged();
    if (last) onSelect(last);
  };

  return (
    <aside className="library" id="library" aria-label="Library" ref={side} onTouchStart={onTouchStart} onTouchMove={onTouchMove} onTouchEnd={onTouchEnd} onTouchCancel={onTouchEnd}>
      <div className="side-head">
        <h2>
          Library <span className="count">{papers.length}</span>
        </h2>
        <button className={"btn small" + (open ? " ghost" : "")} aria-expanded={open} onClick={() => setOpenSet(!open)}>
          <Icon name={open ? "x" : "plus"} size={14} /> {open ? "Close" : "Add paper"}
        </button>
      </div>

      {open && (
      <form onSubmit={upload} className="upload">
        <label
          className={"drop" + (over ? " over" : "") + (files.length ? " has" : "")}
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setOver(false);
            pick(e.dataTransfer.files);
          }}
        >
          <Icon name={files.length ? "check" : "upload"} size={24} />
          <strong>{files.length ? (files.length > 1 ? `${files.length} PDFs ready` : files[0].name) : "Add papers"}</strong>
          <span className="small">{files.length ? "Click to choose other files" : "Drop PDFs here or click to choose"}</span>
          <input ref={fileRef} type="file" accept="application/pdf,.pdf" multiple onChange={(e) => pick(e.target.files)} />
        </label>

        <div className="inwrap focus">
          <label htmlFor="focus">
            <Icon name="target" size={13} /> Focus topic
          </label>
          <input id="focus" type="text" maxLength={200} value={focus} placeholder="Example: the validation agent" onChange={(e) => setFocus(e.target.value)} />
          <p className="hint">The AI reads only this part of the paper. Leave it empty to read the whole paper.</p>
        </div>

        <div className="inwrap">
          <label htmlFor="purpose">Why do you read it?</label>
          <input id="purpose" type="text" value={purpose} placeholder="Example: how do others validate hypotheses?" onChange={(e) => setPurpose(e.target.value)} />
        </div>

        <button className="btn" disabled={busy || !files.length}>
          {busy ? "Uploading…" : files.length > 1 ? `Read ${files.length} papers` : "Read the paper"}
        </button>
        {config && !config.llm_ready && <p className="err small">The AI key is missing on the server. Cards cannot be made.</p>}
      </form>
      )}

      {papers.length > 4 && (
        <label className="filter">
          <Icon name="search" size={14} />
          <input type="text" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter papers…" aria-label="Filter papers" />
        </label>
      )}
      <ul className="plist">
        <AnimatePresence>
        {shown.map((p, i) => (
          <motion.li key={p.id} layout="position" initial={{ opacity: 0, x: -14 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -14 }} transition={{ type: "spring", stiffness: 320, damping: 30, delay: Math.min(i, 8) * 0.03 }}>
            <button className={"pitem" + (p.id === selectedId ? " sel" : "")} onClick={() => onSelect(p.id)}>
              <span className="ptitle">{p.title || p.filename}</span>
              <span className={"pstat s-" + (p.status === "ready" ? p.verdict || "ready" : p.status)}>
                {statusText(p)}
                {ranks?.[p.id] > 0 && (
                  <span className={"rankpip r" + ranks[p.id]} title={["", "Read", "Explained", "Mastered: you defeated the boss"][ranks[p.id]]}>
                    <Icon name={ranks[p.id] === 3 ? "crown" : "star"} size={12} weight="fill" />
                    {ranks[p.id] === 2 && <Icon name="star" size={12} weight="fill" />}
                  </span>
                )}
              </span>
              {p.focus && (
                <span className="pfocus">
                  <Icon name="target" size={12} /> {p.focus}
                </span>
              )}
            </button>
          </motion.li>
        ))}
        </AnimatePresence>
        {!papers.length && <li className="empty-list">No paper yet.</li>}
        {papers.length > 0 && !shown.length && <li className="empty-list">No paper matches “{filter}”.</li>}
      </ul>
    </aside>
  );
}
