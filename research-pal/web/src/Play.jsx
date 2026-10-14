import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { api } from "./api.js";
import Collection from "./Collection.jsx";
import Duck from "./Duck.jsx";
import FogMap from "./FogMap.jsx";
import Semester from "./Semester.jsx";
import Shop from "./Shop.jsx";
import { say, stage } from "./duck.js";
import { Icon } from "./icons.jsx";
import { useApp } from "./store.js";

const SECTIONS = [
  ["home", "Home"],
  ["cards", "Cards"],
  ["map", "Map"],
  ["semester", "Semester"],
  ["shop", "Shop"],
];

function Home({ notify, go }) {
  const game = useApp((s) => s.game);
  const papers = useApp((s) => s.papers);
  const { openBattle, refreshGame } = useApp.getState();
  const [coll, setColl] = useState(null);

  useEffect(() => {
    api.collection().then(setColl).catch(() => setColl([]));
  }, [game?.xp]);

  if (!game) return <p className="muted">Loading…</p>;
  const { level, next, streak, records, quests } = game;
  const span = level.xp_to ? level.xp_to - level.xp_from : 1;
  const pct = level.xp_to ? Math.min(100, Math.round(((game.xp - level.xp_from) / span) * 100)) : 100;
  const line = !papers.length ? say("empty") : game.xp === 0 ? say("hello") : streak.today_done ? say("streak", streak.days) : say("hello", streak.days);
  const fights = (coll || []).filter((c) => c.can_fight && c.rank < 3).sort((a, b) => b.rank - a.rank).slice(0, 3);

  const weekend = async () => {
    try {
      await api.setGameSettings(!streak.weekend_off);
      await refreshGame();
    } catch (e) {
      notify(e.message);
    }
  };

  return (
    <div className="phome">
      <section className="hero">
        <div className="hero-duck">
          <Duck size={150} mood={streak.today_done ? "happy" : "idle"} outfit={game.outfit} stage={stage(level.index)} label="Your Duck" />
          <p className="bubble">{line}</p>
        </div>
        <div className="hero-level">
          <span className="eyebrow">
            Level {level.index + 1} of {level.count}
          </span>
          <h2>{level.name}</h2>
          <p className="story">{game.story}</p>
          <div className="xpbar" role="progressbar" aria-label="XP to the next level" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
            <motion.span initial={false} animate={{ width: `${pct}%` }} transition={{ type: "spring", stiffness: 120, damping: 20 }} />
          </div>
          <div className="xpline">
            <strong>{game.xp} XP</strong>
            {next ? <span className="muted">Next: {next.name} at {next.xp_need} XP</span> : <span className="muted">The highest level</span>}
          </div>
          {next?.skills.length > 0 && (
            <ul className="skills">
              {next.skills.map((s) => (
                <li key={s.key} className={s.have >= s.need ? "done" : ""}>
                  <Icon name={s.have >= s.need ? "check" : "target"} size={14} weight={s.have >= s.need ? "fill" : "regular"} /> {s.label}: {Math.min(s.have, s.need)}/{s.need}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <div className="stats3">
        <div className="statcard">
          <span className="eyebrow">Streak</span>
          <div className={"big" + (streak.today_done ? " lit" : "")}>
            <Icon name="fire" size={26} weight="fill" /> {streak.days} {streak.days === 1 ? "day" : "days"}
          </div>
          <p className="muted small">
            {streak.today_done ? "Today is done." : "Do one piece of real work today."} {streak.tokens_left} rest {streak.tokens_left === 1 ? "day" : "days"} left this week.
          </p>
          <button className="link" onClick={weekend}>
            {streak.weekend_off ? "Weekends are free. Count them." : "Weekends count. Make them free."}
          </button>
        </div>
        <div className="statcard">
          <span className="eyebrow">Sparks</span>
          <div className="big">
            <Icon name="coin" size={26} weight="fill" /> {game.sparks}
          </div>
          <p className="muted small">Real work gives Sparks. Spend them on the Duck and on simulator boosts.</p>
          <button className="link" onClick={() => go("shop")}>
            Open the shop
          </button>
        </div>
        <div className="statcard">
          <span className="eyebrow">This week</span>
          <div className="big">
            <Icon name="bolt" size={26} weight="fill" /> {records.week_xp} XP
          </div>
          <p className="muted small">Last week: {records.last_week_xp} XP. You compare only with your own past.</p>
        </div>
      </div>

      <h2>Quests of this week</h2>
      <div className="quests">
        {quests.map((q) => (
          <div key={q.code} className={"quest" + (q.done ? " done" : "")}>
            <Icon name={q.done ? "check" : "scroll"} size={20} weight={q.done ? "fill" : "regular"} />
            <div>
              <strong>{q.title}</strong>
              <div className="qbar" role="progressbar" aria-label={q.title} aria-valuemin={0} aria-valuemax={q.need} aria-valuenow={q.have}>
                <motion.span initial={false} animate={{ width: `${(q.have / q.need) * 100}%` }} />
              </div>
            </div>
            <span className="qxp">{q.done ? "Done" : `+${q.xp} XP`}</span>
          </div>
        ))}
      </div>
      <p className="muted small">A missed quest has no penalty. Quests change each week. Only real work completes them.</p>

      <h2>Ready for a fight</h2>
      {fights.length ? (
        <div className="fightlist">
          {fights.map((c) => (
            <button key={c.id} className="fight" onClick={() => openBattle(c.id)}>
              <Icon name="sword" size={20} />
              <span>
                <strong>{c.title}</strong>
                <em>{c.rank_name === "seen" ? "Seen" : c.rank_name === "read" ? "Read" : "Explained"} · {c.next_step}</em>
              </span>
              <Icon name="arrow" size={16} />
            </button>
          ))}
        </div>
      ) : (
        <p className="muted">
          {papers.length ? "You mastered each paper that can fight. Add a new paper, or check more claims on a card." : "Add a paper in the library. Each paper has a boss."}
        </p>
      )}
      <div className="row ctas">
        <button className="btn ghost" onClick={() => go("semester")}>
          <Icon name="scroll" size={15} /> Plan a semester
        </button>
        <button className="btn ghost" onClick={() => go("map")}>
          <Icon name="map" size={15} /> Find links in the fog
        </button>
      </div>
    </div>
  );
}

export default function Play({ notify }) {
  const [section, setSection] = useState(() => {
    try {
      return localStorage.getItem("rp-play") || "home";
    } catch {
      return "home";
    }
  });
  const go = (s) => {
    setSection(s);
    try {
      localStorage.setItem("rp-play", s);
    } catch {}
  };
  // The page looks again at the server when it opens: the server pays the XP that new work has earned.
  useEffect(() => {
    useApp.getState().refreshGame();
  }, []);

  return (
    <section className="play">
      <h1>Play</h1>
      <p className="lead">Your reading is a game. Points come only from real work that the server checks. There is no penalty for a pause.</p>
      <div className="viewseg" role="radiogroup" aria-label="Game section">
        {SECTIONS.map(([k, label]) => (
          <button key={k} role="radio" aria-checked={section === k} onClick={() => go(k)}>
            {label}
          </button>
        ))}
      </div>
      {section === "home" && <Home notify={notify} go={go} />}
      {section === "cards" && <Collection notify={notify} />}
      {section === "map" && <FogMap notify={notify} />}
      {section === "semester" && <Semester notify={notify} onBack={() => go("home")} />}
      {section === "shop" && <Shop notify={notify} />}
    </section>
  );
}
