import { useCallback, useEffect, useMemo, useState } from "react";
import { api, cardApi } from "./api.js";
import { Icon } from "./icons.jsx";
import MindMap from "./MindMap.jsx";
import TagChips from "./TagChips.jsx";
import SimpleText from "./SimpleText.jsx";
import Understand from "./Understand.jsx";

const ORDER = [
  ["question", "My question"],
  ["problem", "Problem"],
  ["method", "Method"],
  ["result", "Result"],
  ["limitation", "Limitation"],
  ["use", "Use"],
];
const FIELD_ICON = { question: "help", problem: "flag", method: "layers", result: "chart", limitation: "alert", use: "arrow", focus: "target" };
// [tone, short label, longer help text]
const STATUS = {
  verified: ["ok", "Checked in the paper", "Every quote is in the PDF."],
  check: ["warn", "Check the numbers", "A number in the answer is not in the paper."],
  unverified: ["bad", "Not verified", "No quote was found in the PDF."],
  not_stated: ["muted", "Not stated", "The paper does not state this."],
  not_found: ["warn", "Not found in excerpts", "Not found in the excerpts. The AI saw only part of the paper."],
  suggestion: ["info", "AI suggestion", "The AI wrote this. It is not a claim of the paper."],
  yours: ["info", "Your question", ""],
  edited: ["info", "Edited by you", ""],
};
const VERDICT = { read: "Read it fully", skim: "Skim the method only", skip: "Skip it" };
// The claims that the card proves with quotes. The summary counts them.
const CLAIMS = [
  ["focus", "Focus"],
  ["problem", "Problem"],
  ["method", "Method"],
  ["result", "Result"],
  ["limitation", "Limitation"],
];
const TONE = { verified: "ok", check: "warn", unverified: "bad", not_found: "warn", not_stated: "muted", edited: "info" };

function toMarkdown(paper, card) {
  const f = card.fields;
  const lines = [`# ${card.title || paper.title}`, ""];
  const order = card.focus ? [["focus", `Focus: ${card.focus}`], ...ORDER] : ORDER;
  for (const [k, label] of order) {
    const x = f[k];
    if (!x) continue;
    lines.push(`## ${label}`, x.answer || "(not verified)", "");
    for (const e of x.evidence || []) if (e.verified) lines.push(`> ${e.quote} (p. ${e.page})`, "");
  }
  const parts = card.mindmap?.nodes || [];
  if (parts.length) {
    lines.push("## Mind map");
    for (const n of parts) lines.push(`${n.parent === "root" ? "" : "  "}- **${n.label}**${n.answer ? ": " + n.answer : ""}${n.evidence?.find((e) => e.verified) ? ` (p. ${n.evidence.find((e) => e.verified).page})` : ""}`);
    lines.push("");
  }
  for (const n of card.notes || []) {
    lines.push(`## Note: ${n.question || "From the chat"}`, n.answer, "");
    for (const e of n.evidence || []) lines.push(`> ${e.quote} (${e.title}, p. ${e.page})`, "");
  }
  if (card.keywords?.length) lines.push(`Keywords: ${card.keywords.join(", ")}`);
  return lines.join("\n");
}

function download(name, text) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function jump(name) {
  const el = document.getElementById("f-" + name);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.remove("flash");
  void el.offsetWidth; // restart the animation
  el.classList.add("flash");
}

// The first thing the student sees: what to do with the paper, and how much of the card has proof.
function Summary({ card, paperId, cardId }) {
  const items = CLAIMS.filter(([k]) => card.fields?.[k]).map(([k, label]) => ({ k, label, s: card.fields[k].status }));
  const ok = items.filter((i) => i.s === "verified").length;
  const look = items.filter((i) => ["check", "unverified", "not_found"].includes(i.s)).length;
  if (!card.verdict && !items.length) return null;
  return (
    <section className="summary" aria-label="Summary">
      {card.verdict && (
        <div className={"verdict-panel v-" + card.verdict}>
          <span className="eyebrow">Verdict</span>
          <strong className="vlabel">{VERDICT[card.verdict]}</strong>
          {card.verdict_reason && <SimpleText text={card.verdict_reason} load={() => api.simplifyField(paperId, "verdict_reason", cardId)} cacheKey={`${paperId}|${cardId}|verdict|${card.verdict_reason}`} className="" />}
        </div>
      )}
      {items.length > 0 && (
        <div className="proof">
          <span className="eyebrow">Proof</span>
          <strong className="vlabel">
            {ok} of {items.length} claims checked
          </strong>
          <div className="meter" role="img" aria-label={`${ok} of ${items.length} claims checked in the paper`}>
            {items.map((i) => (
              <span key={i.k} className={"seg t-" + (TONE[i.s] || "muted")} />
            ))}
          </div>
          <div className="legend">
            {items.map((i) => (
              <button key={i.k} className="claim" onClick={() => jump(i.k)} title={(STATUS[i.s] || [])[2]}>
                <span className={"dot t-" + (TONE[i.s] || "muted")} />
                {i.label}
              </button>
            ))}
          </div>
          {look > 0 && <p className="small look">{look === 1 ? "1 claim needs a look." : `${look} claims need a look.`}</p>}
        </div>
      )}
    </section>
  );
}

function Field({ name, label, f, paperId, cardId = "", hasPdf, onSave, notify, bare, onFill, filling }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const [showDraft, setShowDraft] = useState(false);
  const [badge, text0, hint] = STATUS[f.status] || ["muted", f.status, ""];
  const flagged = (f.unverified_numbers || []).length > 0;

  const openPage = (p) => api.openPdf(paperId, p).catch((e) => notify(e.message));

  return (
    <section id={"f-" + name} className={"field s-" + badge + (bare ? " bare" : "")}>
      <div className="rail">
        <h3>
          <Icon name={FIELD_ICON[name] || "doc"} size={14} /> {label}
        </h3>
        <span className={"badge b-" + badge} title={hint}>
          {text0}
        </span>
      </div>

      <div className="fbody">
        <button
          className="link edit-link"
          onClick={() => {
            setText(f.answer || f.draft || "");
            setEditing(!editing);
          }}
        >
          {editing ? "Cancel" : "Edit"}
        </button>

        {editing ? (
          <div className="edit">
            <textarea value={text} rows={4} onChange={(e) => setText(e.target.value)} aria-label={label} />
            <button
              className="btn small"
              onClick={async () => {
                await onSave(name, text);
                setEditing(false);
              }}
            >
              Save
            </button>
          </div>
        ) : f.answer ? (
          // The simple version is for the texts that the AI wrote. A text that you wrote or edited stays as it is.
          ["verified", "check", "suggestion"].includes(f.status) && !f.edited ? (
            <SimpleText text={f.answer} load={() => api.simplifyField(paperId, name, cardId)} cacheKey={`${paperId}|${cardId}|${name}|${f.answer}`} />
          ) : (
            <p className={"answer" + (f.status === "not_stated" || f.status === "not_found" ? " muted" : "")}>{f.answer}</p>
          )
        ) : (
          <p className="answer muted">The AI gave no proof for this claim, so the card hides it. Read the paper yourself, or write the answer.</p>
        )}

        {f.status === "not_found" && onFill && !editing && (
          <button className="btn small tint" disabled={!!filling} onClick={() => onFill([name])}>
            <Icon name="search" size={14} /> {filling === name || filling === "all" ? "Searching the paper…" : "Search the paper again"}
          </button>
        )}

        {flagged && (
          <p className="warn-line">
            Not found in the paper: {f.unverified_numbers.join(", ")}. Compare with the tables before you use this.
          </p>
        )}

        {f.evidence?.length > 0 && (
          <div className="evidence">
            <span className="eyebrow">Evidence</span>
            {f.evidence.map((e, i) => (
              <blockquote key={i} className={e.verified ? "" : "q-bad"}>
                <span>{e.quote}</span>
                {e.verified ? (
                  hasPdf ? (
                    <button className="chip" onClick={() => openPage(e.page)} title="Open the PDF at this page">
                      p. {e.page}
                    </button>
                  ) : (
                    <span className="chip">p. {e.page}</span>
                  )
                ) : (
                  <span className="chip bad">Quote not found in the PDF</span>
                )}
              </blockquote>
            ))}
          </div>
        )}

        {f.draft && (
          <div>
            <button className="link" onClick={() => setShowDraft(!showDraft)}>
              {showDraft ? "Hide the unverified draft" : "Show the unverified draft"}
            </button>
            {showDraft && <p className="answer draft">{f.draft}</p>}
          </div>
        )}
      </div>
    </section>
  );
}

function Skeleton() {
  return (
    <div className="skel-wrap" aria-busy="true" aria-label="Loading the card">
      <div className="skel h" />
      <div className="skel m" />
      <div className="skel box" />
      <div className="skel box" />
    </div>
  );
}

// The student writes one topic. The AI reads and quotes only that part of the paper.
function FocusBar({ current, keywords, busy, onApply }) {
  const [text, setText] = useState(current);
  useEffect(() => setText(current), [current]);
  const next = text.trim();
  const changed = next !== current;

  const submit = (e) => {
    e.preventDefault();
    if (changed && !busy) onApply(next);
  };

  return (
    <div className={"focusbar" + (current ? " has" : "")}>
      <form onSubmit={submit}>
        <span className="ficon">
          <Icon name="target" size={16} />
        </span>
        <input
          type="text"
          maxLength={200}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Focus on one part of this paper…"
          aria-label="Focus topic"
        />
        <button className="btn small" disabled={!changed || busy}>
          {current && !next ? "Clear focus" : current ? "Update focus" : "Focus"}
        </button>
      </form>
      <div className="more">
        <div>
          <p className="hint">
            {current ? "The AI reads this topic only. Each quote must talk about it." : "Example: the validation agent, the dataset, the evaluation. The AI then reads only that part."}
          </p>
          {!current && keywords?.length > 0 && (
            <div className="sugg">
              <span>Try:</span>
              {keywords.slice(0, 5).map((k) => (
                <button key={k} type="button" className="kwchip" onClick={() => setText(k)}>
                  {k}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const isBusy = (s) => s === "queued" || s === "processing";

// One paper can have several cards. Each card has its own focus topic. The first card is the one you made with the upload.
function CardTabs({ list, active, onPick, onAdd, canAdd }) {
  const [open, setOpen] = useState(false);
  const [focus, setFocus] = useState("");
  const [purpose, setPurpose] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!focus.trim() && !purpose.trim()) return;
    setBusy(true);
    const ok = await onAdd({ focus: focus.trim(), purpose: purpose.trim() });
    setBusy(false);
    if (ok) {
      setOpen(false);
      setFocus("");
      setPurpose("");
    }
  };

  return (
    <div className="cardtabs">
      <div className="ctabs" role="tablist" aria-label="Cards of this paper">
        {list.map((c) => (
          <button key={c.id || "first"} role="tab" aria-selected={c.id === active} className={"ctab" + (isBusy(c.status) ? " busy" : "") + (c.status === "error" ? " bad" : "")} onClick={() => onPick(c.id)} title={c.focus || c.purpose || "The whole paper"}>
            {c.focus ? <Icon name="target" size={13} /> : <Icon name="doc" size={13} />}
            <span>{c.focus || (c.id ? c.purpose || "Card" : "Whole paper")}</span>
          </button>
        ))}
        {canAdd && (
          <button className="ctab add" onClick={() => setOpen(!open)} aria-expanded={open}>
            <Icon name={open ? "x" : "plus"} size={13} /> <span>{open ? "Close" : "New card"}</span>
          </button>
        )}
      </div>
      {open && (
        <form className="newcard" onSubmit={submit}>
          <p className="hint">Make another card for this paper. Choose the part you want. No new upload is needed.</p>
          <input type="text" maxLength={200} autoFocus value={focus} onChange={(e) => setFocus(e.target.value)} placeholder="Focus topic. Example: the dataset" aria-label="Focus topic of the new card" />
          <input type="text" maxLength={500} value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="Why do you read it? (optional)" aria-label="Reason for the new card" />
          <button className="btn small" disabled={busy || (!focus.trim() && !purpose.trim())}>
            {busy ? "Making…" : "Make the card"}
          </button>
        </form>
      )}
    </div>
  );
}

// subQuestions: the sub-questions of the thesis (empty when the feature is off). tags: {card id: [sub-question ids]} of this paper.
export default function CardView({ id, subQuestions = [], tags = {}, onChanged, onDeleted, notify, parts = { feynman: true, eli12: true, quiz: true } }) {
  const [view, setView] = useState("card"); // "card" or "understand"
  const understandOn = parts.feynman || parts.eli12 || parts.quiz;
  const [data, setData] = useState(null);
  const [tagBusy, setTagBusy] = useState(false);
  const [purpose, setPurpose] = useState("");
  const [mapBusy, setMapBusy] = useState(false);
  const [fillBusy, setFillBusy] = useState(""); // the field that we search again, or "all"
  const [fillMsg, setFillMsg] = useState("");
  const [cid, setCid] = useState(""); // "" = the first card of the paper
  const src = useMemo(() => cardApi(id, cid), [id, cid]);

  const load = useCallback(async () => {
    try {
      const d = await src.load();
      setData(d);
      return d;
    } catch (e) {
      notify(e.message);
    }
  }, [src, notify]);

  useEffect(() => {
    setData(null);
    load().then((d) => d && setPurpose(d.paper.purpose || ""));
  }, [load]);

  const inProgress = data && isBusy(data.paper.status);
  const busyAny = inProgress || data?.card_list?.some((c) => isBusy(c.status));
  useEffect(() => {
    if (!busyAny) return;
    const t = setInterval(async () => {
      const d = await load();
      if (d && inProgress && !isBusy(d.paper.status)) onChanged();
    }, 3000);
    return () => clearInterval(t);
  }, [busyAny, inProgress, load, onChanged]);

  if (!data) return <Skeleton />;
  const { paper, card } = data;
  const list = data.card_list || [];

  const addCard = async (body) => {
    try {
      const r = await api.addCard(id, body);
      setCid(r.id);
      return true;
    } catch (e) {
      notify(e.message);
      return false;
    }
  };
  const tag = async (ids) => {
    setTagBusy(true);
    try {
      await api.setTags(id, cid, ids);
      await onChanged(); // the list of papers carries the tags
    } catch (e) {
      notify(e.message);
    } finally {
      setTagBusy(false);
    }
  };
  const save = async (name, text) => {
    try {
      await src.patch({ [name]: text });
      await load();
      onChanged();
    } catch (e) {
      notify(e.message);
    }
  };
  // Search the paper again for fields that say "not found". names = [] means every such field.
  const fill = async (names) => {
    setFillBusy(names.length === 1 ? names[0] : "all");
    setFillMsg("");
    try {
      const r = await src.fill(names);
      const label = (k) => (CLAIMS.find(([x]) => x === k) || [k, k])[1];
      setFillMsg(
        (r.filled.length ? `Found and checked: ${r.filled.map(label).join(", ")}. ` : "No new checked quote was found. ") +
          (r.missing.length ? `Still not found: ${r.missing.map(label).join(", ")}.` : "")
      );
      await load();
      onChanged();
    } catch (e) {
      notify(e.message);
    } finally {
      setFillBusy("");
    }
  };
  const makeMap = async () => {
    setMapBusy(true);
    try {
      await src.makeMindmap();
      await load();
    } catch (e) {
      notify(e.message);
    } finally {
      setMapBusy(false);
    }
  };
  const removeMap = async () => {
    if (!confirm("Delete the mind map of this card?")) return;
    try {
      await src.deleteMindmap();
      await load();
    } catch (e) {
      notify(e.message);
    }
  };
  const removeNote = async (noteId) => {
    try {
      await api.deleteNote(id, noteId);
      await load();
    } catch (e) {
      notify(e.message);
    }
  };
  // change = { purpose } or { focus }. A key you leave out keeps its saved value.
  const again = async (change) => {
    try {
      await src.regenerate(change);
      await load();
      onChanged();
    } catch (e) {
      notify(e.message);
    }
  };

  return (
    <article className="card" data-words>
      <CardTabs list={list} active={cid} onPick={(c) => { setFillMsg(""); setCid(c); }} onAdd={addCard} canAdd={paper.status !== "error" || !!cid} />
      <header className="card-head">
        <h1>{card?.title || paper.title}</h1>
        <div className="meta">
          <span>{paper.filename}</span>
          {paper.n_pages > 0 && <span>{paper.n_pages} pages</span>}
          {card?.model && <span>{card.model}</span>}
        </div>
        {card?.keywords?.length > 0 && (
          <div className="kw">
            {card.keywords.map((k) => (
              <span key={k} className="kwchip">
                {k}
              </span>
            ))}
          </div>
        )}
        {subQuestions.length > 0 && (
          <div className="cardtags">
            <span className="eyebrow">Helps these sub-questions</span>
            <TagChips subQuestions={subQuestions} selected={tags[cid] || []} onChange={tag} busy={tagBusy} label="Sub-questions of this card" />
          </div>
        )}
      </header>

      {inProgress && (
        <div className="progress" role="status">
          <span className="dot-anim" />
          {paper.focus
            ? `The AI reads the paper about “${paper.focus}” and checks each quote. This takes 20 to 60 seconds.`
            : "The AI reads the paper and checks each quote. This takes 20 to 60 seconds."}
        </div>
      )}

      {paper.status === "error" && (
        <div className="errbox" role="alert">
          <strong>The card could not be made.</strong>
          <p>{paper.error}</p>
        </div>
      )}

      {card && <Summary card={card} paperId={id} cardId={cid} />}

      {card && understandOn && (
        <div className="viewseg" role="tablist" aria-label="View of the card">
          <button role="tab" aria-selected={view === "card"} onClick={() => setView("card")}>
            <Icon name="doc" size={14} /> Card
          </button>
          <button role="tab" aria-selected={view === "understand"} onClick={() => setView("understand")}>
            <Icon name="sparkle" size={14} /> Understand
          </button>
        </div>
      )}
      {card && understandOn && view === "understand" && <Understand paperId={id} cardId={cid} card={card} parts={parts} notify={notify} />}

      {card && (() => {
        const missing = CLAIMS.filter(([k]) => card.fields?.[k]?.status === "not_found");
        if (!missing.length && !fillMsg) return null;
        return (
          <div className="fillbar" role="status">
            {missing.length > 0 && (
              <>
                <span>
                  {missing.length === 1 ? "1 claim was not found in the excerpts." : `${missing.length} claims were not found in the excerpts.`} The AI saw only a part of the paper.
                </span>
                <button className="btn small tint" disabled={!!fillBusy || inProgress} onClick={() => fill([])}>
                  <Icon name="search" size={14} /> {fillBusy ? "Searching the paper…" : "Search the paper again"}
                </button>
              </>
            )}
            {fillMsg && <span className="small muted fillmsg">{fillMsg}</span>}
          </div>
        );
      })()}

      <FocusBar current={paper.focus || ""} keywords={card?.keywords} busy={inProgress} onApply={(focus) => again({ focus })} />

      {card && (view === "card" || !understandOn) && (
        <>
          {card.focus && card.fields?.focus && (
            <section className="focus-card" aria-label="Focus">
              <div className="focus-eyebrow">
                <Icon name="target" size={14} /> Focus
              </div>
              <h2 className="focus-topic">{card.focus}</h2>
              <Field name="focus" label="Focus" f={card.fields.focus} paperId={id} cardId={cid} hasPdf={paper.has_pdf} onSave={save} notify={notify} bare onFill={fill} filling={fillBusy} />
            </section>
          )}
          <div className="fields">
            {ORDER.map(([k, label]) => {
              const f = card.fields?.[k];
              if (!f) return null;
              return (
                <div key={k}>
                  <Field name={k} label={label} f={f} paperId={id} cardId={cid} hasPdf={paper.has_pdf} onSave={save} notify={notify} onFill={fill} filling={fillBusy} />
                  {k === "limitation" && card.inferred_limitations && (
                    <p className="opinion">
                      <strong>AI opinion, not from the paper:</strong> {card.inferred_limitations}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
          <MindMap title={card.title || paper.title} map={card.mindmap} busy={mapBusy} paperId={id} hasPdf={paper.has_pdf} onMake={makeMap} onDelete={removeMap} notify={notify} />
          {card.notes?.length > 0 && (
            <section className="notes" aria-label="Notes from the chat">
              <h2>Notes from the chat</h2>
              {card.notes.map((n) => (
                <div key={n.id} className="note">
                  <div className="field-head">
                    <h3>{n.question || "From the chat"}</h3>
                    <button className="link" onClick={() => removeNote(n.id)}>
                      Delete
                    </button>
                  </div>
                  <p className="answer">{n.answer}</p>
                  {n.evidence?.length > 0 && (
                    <div className="evidence">
                      {n.evidence.map((e, i) => (
                        <blockquote key={i}>
                          <span>{e.quote}</span>
                          <button className="chip" title="Open the PDF at this page" onClick={() => api.openPdf(e.paper_id, e.page).catch((x) => notify(x.message))}>
                            {e.paper_id !== id ? `${(e.title || "").slice(0, 28)} · ` : ""}p. {e.page}
                          </button>
                        </blockquote>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </section>
          )}
        </>
      )}

      <footer className="actions">
        {paper.has_pdf && (
          <button className="btn ghost" onClick={() => api.openPdf(id).catch((e) => notify(e.message))}>
            <Icon name="external" size={15} /> Open the PDF
          </button>
        )}
        {card && (
          <button className="btn ghost" onClick={() => download((card.title || "card").slice(0, 60).replace(/[^\w]+/g, "_") + ".md", toMarkdown(paper, card))}>
            <Icon name="download" size={15} /> Download as Markdown
          </button>
        )}
        <details className="regen">
          <summary>
            <Icon name="refresh" size={15} /> Read again
          </summary>
          <label htmlFor="rp" className="small muted">
            Why do you read it?
          </label>
          <input id="rp" value={purpose} onChange={(e) => setPurpose(e.target.value)} />
          <button className="btn small" disabled={inProgress} onClick={() => again({ purpose, fresh: true })}>
            Read again
          </button>
        </details>
        <button
          className="btn danger"
          onClick={async () => {
            if (!confirm(cid ? "Delete this card? The paper and its other cards stay." : "Delete this paper and all its cards?")) return;
            try {
              if (cid) {
                await src.remove();
                setCid("");
              } else {
                await api.remove(id);
                onDeleted();
              }
            } catch (e) {
              notify(e.message);
            }
          }}
        >
          <Icon name="trash" size={15} /> {cid ? "Delete this card" : "Delete the paper"}
        </button>
      </footer>
    </article>
  );
}
