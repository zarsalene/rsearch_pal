import { useEffect, useState } from "react";
import { api } from "./api.js";
import { Icon } from "./icons.jsx";

// One row for each paper, one column for each part of the card. Every cell shows the checked answer and the pages of its quotes.
// The table is built from the cards. It uses no AI, so it adds no new claim.
const COLUMNS = [
  ["problem", "Problem"],
  ["method", "Method"],
  ["result", "Result"],
  ["limitation", "Limitation"],
];
const NOTE = {
  check: "Check the numbers",
  unverified: "Hidden: no proof",
  not_found: "Not found in the excerpts",
  not_stated: "Not stated",
  edited: "Edited by you",
};

function Cell({ paper, f, notify }) {
  const [open, setOpen] = useState(false);
  if (!f) return <td className="cmp-empty">No data</td>;
  const text = f.answer || "";
  const pages = [...new Set((f.evidence || []).filter((e) => e.verified).map((e) => e.page))];
  const long = text.length > 150;
  return (
    <td>
      {text ? <p className={"cmp-text" + (open ? " open" : "")}>{text}</p> : <p className="cmp-text muted">{NOTE[f.status] || "No answer"}</p>}
      {long && (
        <button className="link small" onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? "Show less" : "Show more"}
        </button>
      )}
      <div className="cmp-meta">
        {text && NOTE[f.status] && <span className={"cmp-flag f-" + f.status}>{NOTE[f.status]}</span>}
        {pages.map((p) =>
          paper.has_pdf ? (
            <button key={p} className="chip" title="Open the PDF at this page" onClick={() => api.openPdf(paper.id, p).catch((e) => notify(e.message))}>
              p. {p}
            </button>
          ) : (
            <span key={p} className="chip">
              p. {p}
            </span>
          )
        )}
      </div>
    </td>
  );
}

function csv(rows) {
  const esc = (s) => `"${String(s ?? "").replace(/"/g, '""')}"`;
  const head = ["Paper", "Verdict", ...COLUMNS.map(([, l]) => l), ...COLUMNS.map(([, l]) => l + " pages")];
  const lines = [head, ...rows.map((r) => [r.title, r.verdict, ...COLUMNS.map(([k]) => r.fields[k]?.answer || ""), ...COLUMNS.map(([k]) => [...new Set((r.fields[k]?.evidence || []).filter((e) => e.verified).map((e) => e.page))].join(" "))])];
  return lines.map((l) => l.map(esc).join(",")).join("\n");
}

export default function Compare({ onOpenCard, notify }) {
  const [rows, setRows] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const list = (await api.papers()).filter((p) => p.status === "ready").slice(0, 30);
        const full = await Promise.all(list.map((p) => api.paper(p.id).catch(() => null)));
        if (!alive) return;
        setRows(
          full
            .filter((d) => d && d.card)
            .map((d) => ({ paper: d.paper, title: d.card.title || d.paper.title, verdict: d.card.verdict || "", focus: d.card.focus || "", fields: d.card.fields || {} }))
        );
      } catch (e) {
        notify(e.message);
        if (alive) setRows([]);
      }
    })();
    return () => {
      alive = false;
    };
  }, [notify]);

  if (!rows) return <p className="muted">Loading…</p>;
  if (!rows.length) return <p className="muted">No card is ready yet. Add a paper, and its card appears in this table.</p>;

  const download = () => {
    const url = URL.createObjectURL(new Blob(["﻿" + csv(rows)], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "research-pal-compare-" + new Date().toISOString().slice(0, 10) + ".csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div className="cmp-head">
        <p className="muted small">One row for each paper. Each answer was checked against the PDF. Click a page to open the PDF there.</p>
        <button className="btn small ghost" onClick={download}>
          <Icon name="download" size={14} /> Download CSV
        </button>
      </div>
      <div className="cmp-scroll" tabIndex={0} role="region" aria-label="Comparison table of the papers">
        <table className="cmp">
          <thead>
            <tr>
              <th scope="col">Paper</th>
              {COLUMNS.map(([k, label]) => (
                <th key={k} scope="col">
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.paper.id}>
                <th scope="row">
                  <button className="link cmp-title" onClick={() => onOpenCard(r.paper.id)}>
                    {r.title}
                  </button>
                  {r.verdict && <span className={"cmp-verdict v-" + r.verdict}>{{ read: "Read it", skim: "Skim it", skip: "Skip it" }[r.verdict]}</span>}
                  {r.focus && <span className="cmp-focus">Focus: {r.focus}</span>}
                </th>
                {COLUMNS.map(([k]) => (
                  <Cell key={k} paper={r.paper} f={r.fields[k]} notify={notify} />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
