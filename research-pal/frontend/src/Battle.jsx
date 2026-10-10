import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { api } from "./api.js";
import { Icon } from "./icons.jsx";
import Duck from "./Duck.jsx";
import { MOOD, say, stage } from "./duck.js";
import { confetti, play } from "./juice.js";
import { useApp } from "./store.js";

// The boss of a paper. A "Paper Golem" made of pages. Each right answer hurts it. A wrong answer costs a heart, and nothing else.
function Boss({ hp, hit, state }) {
  const low = hp <= 34 && state === "fight";
  return (
    <motion.svg
      className={"boss" + (state === "won" ? " down" : "")}
      viewBox="0 0 160 150"
      width="170"
      height="160"
      aria-hidden="true"
      key={state === "won" ? "down" : "up"}
      animate={state === "won" ? { rotate: 78, y: 40, opacity: 0.35, scale: 0.9 } : hit ? { x: [0, -12, 11, -7, 5, 0], rotate: [0, -3, 3, -1, 0] } : { y: [0, -3, 0] }}
      transition={state === "won" ? { duration: 0.9, ease: "easeIn" } : hit ? { duration: 0.45 } : { duration: 2.8, repeat: Infinity, ease: "easeInOut" }}
    >
      <ellipse cx="80" cy="140" rx="46" ry="6" fill="rgba(24,24,27,.14)" />
      {/* three pages stacked: the body of the golem */}
      <rect x="40" y="48" width="80" height="84" rx="6" fill="#E9EBF3" stroke="#AEB3C6" strokeWidth="2" transform="rotate(-5 80 90)" />
      <rect x="40" y="46" width="80" height="84" rx="6" fill="#F2F3F9" stroke="#AEB3C6" strokeWidth="2" transform="rotate(3 80 90)" />
      <rect x="38" y="44" width="84" height="86" rx="6" fill="#FBFBFD" stroke="#9097AE" strokeWidth="2.2" />
      <path d="M48 118 h64 M48 110 h52" stroke="#D5D8E5" strokeWidth="3" strokeLinecap="round" />
      {/* arms */}
      <rect x="18" y="74" width="22" height="9" rx="4.5" fill="#CFD3E4" transform="rotate(-18 28 78)" />
      <rect x="120" y="74" width="22" height="9" rx="4.5" fill="#CFD3E4" transform="rotate(18 132 78)" />
      {/* face */}
      {low ? (
        <g stroke="#2B2B33" strokeWidth="3" strokeLinecap="round">
          <path d="M56 66 l10 10 M66 66 l-10 10" />
          <path d="M94 66 l10 10 M104 66 l-10 10" />
        </g>
      ) : state === "won" ? (
        <g stroke="#2B2B33" strokeWidth="3" strokeLinecap="round" fill="none">
          <path d="M56 72 q5 -5 10 0" />
          <path d="M94 72 q5 -5 10 0" />
        </g>
      ) : (
        <g>
          <circle cx="62" cy="70" r="8" fill="#fff" stroke="#2B2B33" strokeWidth="2" />
          <circle cx="98" cy="70" r="8" fill="#fff" stroke="#2B2B33" strokeWidth="2" />
          <circle cx="64" cy="71" r="3.4" fill="#2B2B33" />
          <circle cx="96" cy="71" r="3.4" fill="#2B2B33" />
          <path d="M52 58 l20 6 M108 58 l-20 6" stroke="#2B2B33" strokeWidth="3.2" strokeLinecap="round" />
        </g>
      )}
      {state === "won" ? <path d="M68 96 q12 10 24 0" stroke="#2B2B33" strokeWidth="3" strokeLinecap="round" fill="none" /> : <path d="M66 98 l5 -6 l5 6 l5 -6 l5 6 l5 -6 l4 6" stroke="#2B2B33" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none" />}
      {low && <path d="M104 42 l14 -5 l3 8 l-14 5 z" fill="#fff" stroke="#E8463A" strokeWidth="2" />}
    </motion.svg>
  );
}

function Hearts({ n, max }) {
  return (
    <div className="hearts" role="img" aria-label={`${n} of ${max} hearts left`}>
      {Array.from({ length: max }, (_, i) => (
        <motion.span key={i} className={i < n ? "on" : "off"} animate={i < n ? { scale: 1 } : { scale: [1.3, 0.85, 1] }} transition={{ duration: 0.4 }}>
          <Icon name={i < n ? "heart" : "heartbreak"} size={22} weight={i < n ? "fill" : "regular"} />
        </motion.span>
      ))}
    </div>
  );
}

const LETTERS = ["A", "B", "C", "D"];

export default function Battle({ paperId, onClose }) {
  const [b, setB] = useState(null);
  const [res, setRes] = useState(null); // the answer that the server gave to the last question
  const [showEnd, setShowEnd] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [hit, setHit] = useState(0);
  const [pop, setPop] = useState(null); // the damage number
  const [line, setLine] = useState("");
  const box = useRef(null);
  const outfit = useApp((s) => s.game?.outfit) || {};
  const level = useApp((s) => s.game?.level?.index) || 0;
  const n = useRef(0);
  const timers = useRef([]);
  const later = (fn, ms) => timers.current.push(setTimeout(fn, ms)); // a sound that waits must not play after the student left
  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const begin = () => {
    setB(null);
    setRes(null);
    setShowEnd(false);
    setErr("");
    api
      .startBattle(paperId)
      .then((s) => {
        setB(s);
        setLine(say("hello", n.current++));
        play("event");
      })
      .catch((e) => setErr(e.message));
  };
  useEffect(begin, [paperId]);
  useEffect(() => box.current?.focus(), []);

  const last = res?.battle.history.at(-1);
  const phase = err ? "error" : !b ? "loading" : showEnd || (b.status !== "active" && !res) ? "end" : res ? "feedback" : "question";

  const pick = async (i) => {
    if (busy || res || !b || b.status !== "active") return;
    setBusy(true);
    try {
      const r = await api.answerBattle(b.id, b.question.n, i);
      setRes(r);
      setB(r.battle);
      const ev = r.correct ? (r.crit ? "crit" : "right") : "wrong";
      setLine(say(ev, n.current++));
      if (r.correct) {
        setHit((h) => h + 1);
        setPop({ id: Date.now(), text: `-${r.damage}`, crit: r.crit });
        play(r.crit ? "crit" : "correct");
      } else play("wrong");
      if (r.battle.status === "won") {
        later(() => {
          play("win");
          confetti("big");
        }, 450);
      } else if (r.battle.status === "lost") later(() => play("lose"), 450);
      // A quest that this answer completed, a welcome back, or a new level.
      useApp.getState().gain({ events: r.extra || [], level_up: r.level_up });
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const next = () => {
    setPop(null);
    if (b.status !== "active") {
      setShowEnd(true);
      setLine(say(b.result.won ? (b.result.flawless ? "flawless" : "win") : "lose", n.current++));
    } else setRes(null);
  };

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
      if (phase === "question" && /^[1-4]$/.test(e.key)) pick(Number(e.key) - 1);
      if (phase === "feedback" && (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        next();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const state = b?.status === "won" ? "won" : "fight";
  const mood = phase === "feedback" ? (res.correct ? MOOD[res.crit ? "crit" : "right"] : MOOD.wrong) : phase === "end" ? (b.result.won ? "cheer" : "oops") : "idle";

  return (
    <div className="battle" role="dialog" aria-modal="true" aria-label={b ? `Boss fight: ${b.title}` : "Boss fight"} ref={box} tabIndex={-1}>
      <motion.div className="battle-card" initial={{ opacity: 0, y: 24, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ type: "spring", stiffness: 300, damping: 28 }}>
        <header className="battle-top">
          <button className="iconbtn" onClick={onClose} aria-label="Leave the fight. You can come back." title="Leave the fight. You can come back.">
            <Icon name="x" size={18} />
          </button>
          <div className="battle-title">
            <span className="eyebrow">Boss fight</span>
            <strong>{b?.title || "…"}</strong>
          </div>
          {b && <Hearts n={b.hearts} max={b.hearts_max} />}
        </header>

        <div className="battle-stage">
          <div className="boss-wrap">
            <Boss hp={b?.hp ?? 100} hit={hit} state={state} key={b?.id} />
            <AnimatePresence>
              {pop && (
                <motion.span key={pop.id} className={"dmg" + (pop.crit ? " crit" : "")} initial={{ opacity: 0, y: 0, scale: 0.6 }} animate={{ opacity: 1, y: -46, scale: pop.crit ? 1.5 : 1.15 }} exit={{ opacity: 0 }} transition={{ duration: 0.6 }}>
                  {pop.text}
                  {pop.crit ? " CRIT" : ""}
                </motion.span>
              )}
            </AnimatePresence>
          </div>
          <div className="hpwrap">
            <div className="hpbar" role="progressbar" aria-label="Boss health" aria-valuemin={0} aria-valuemax={b?.hp_max ?? 100} aria-valuenow={b?.hp ?? 100}>
              <motion.span initial={false} animate={{ width: `${b?.hp ?? 100}%` }} transition={{ type: "spring", stiffness: 160, damping: 22 }} />
            </div>
            <div className="battle-meta">
              <span>{b ? (b.status === "active" ? `Question ${Math.min(b.index + 1, b.total)} of ${b.total}` : "Fight over") : "Waking up…"}</span>
              <AnimatePresence>
                {b?.combo >= 2 && (
                  <motion.span className="combo" initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ opacity: 0 }}>
                    <Icon name="fire" size={14} weight="fill" /> Combo ×{b.combo}
                  </motion.span>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>

        {phase === "loading" && (
          <div className="battle-body" role="status">
            <p className="progress">
              <span className="dot-anim" />
              The boss is waking up. The AI writes questions from your checked quotes. This takes 10 to 30 seconds.
            </p>
          </div>
        )}

        {phase === "error" && (
          <div className="battle-body">
            <div className="errbox" role="alert">
              <strong>The fight cannot start.</strong>
              <p>{err}</p>
            </div>
            <div className="row">
              <button className="btn ghost" onClick={begin}>
                Try again
              </button>
              <button className="btn" onClick={onClose}>
                Close
              </button>
            </div>
          </div>
        )}

        {phase === "question" && (
          <div className="battle-body">
            <span className="chip fieldchip">{b.question.field}</span>
            <h2 className="q">{b.question.text}</h2>
            <div className="opts" role="group" aria-label="Answers">
              {b.question.options.map((o, i) => (
                <button key={i} className="opt" disabled={busy} onClick={() => pick(i)}>
                  <kbd>{LETTERS[i]}</kbd>
                  <span>{o}</span>
                </button>
              ))}
            </div>
            <p className="duckline">
              <Duck size={44} mood="idle" outfit={outfit} stage={stage(level)} /> <span>{line}</span>
            </p>
          </div>
        )}

        {phase === "feedback" && (
          <div className="battle-body">
            <span className="chip fieldchip">{last.field}</span>
            <h2 className="q">{last.text}</h2>
            <div className="opts" role="group" aria-label="Answers">
              {last.options.map((o, i) => (
                <div key={i} className={"opt shown" + (i === last.answer ? " right" : i === last.chosen ? " wrong" : " dim")}>
                  <kbd>{LETTERS[i]}</kbd>
                  <span>{o}</span>
                  {i === last.answer && <Icon name="check" size={18} weight="fill" />}
                </div>
              ))}
            </div>
            <motion.div className={"verdictline " + (res.correct ? "ok" : "no")} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} role="status">
              <strong>{res.correct ? (res.crit ? `Combo hit! −${res.damage} HP` : `Right! −${res.damage} HP`) : "Not this time. You lose a heart."}</strong>
              {res.xp > 0 && <span className="xpchip">+{res.xp} XP</span>}
              {res.extra?.map((e) => (
                <span key={e.action} className="xpchip gold">
                  +{e.xp} {e.label}
                </span>
              ))}
            </motion.div>
            <blockquote className="proof">
              <span>{last.proof.quote}</span>
              <button className="chip" onClick={() => api.openPdf(b.paper_id, last.proof.page).catch(() => {})} title="Open the PDF at this page">
                Proof · p. {last.proof.page}
              </button>
            </blockquote>
            <div className="battle-actions">
              <p className="duckline">
                <Duck size={44} mood={mood} outfit={outfit} stage={stage(level)} /> <span>{line}</span>
              </p>
              <button className="btn" onClick={next} autoFocus>
                {b.status === "active" ? "Next question" : "See the result"} <Icon name="arrow" size={15} />
              </button>
            </div>
          </div>
        )}

        {phase === "end" && (
          <div className="battle-body end">
            <motion.div initial={{ scale: 0.7, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: "spring", stiffness: 260, damping: 18 }}>
              <Duck size={110} mood={b.result.won ? "cheer" : "oops"} outfit={outfit} stage={stage(level)} />
            </motion.div>
            <h2>{b.result.won ? (b.result.flawless ? "Flawless victory!" : "Victory!") : "The boss stands… for now"}</h2>
            <p className="lead">{b.result.text}</p>
            <div className="endstats">
              <div>
                <strong>{b.history.filter((h) => h.correct).length}/{b.total}</strong>
                <span>right answers</span>
              </div>
              <div>
                <strong>{b.best_combo}</strong>
                <span>best combo</span>
              </div>
              <div>
                <strong>+{b.xp}</strong>
                <span>XP</span>
              </div>
            </div>
            <p className="duckline center">
              <span>{line}</span>
            </p>
            <div className="row center">
              <button className="btn" onClick={onClose}>
                Back to the card
              </button>
              <button className="btn ghost" onClick={begin}>
                <Icon name="sword" size={15} /> Fight again
              </button>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}
