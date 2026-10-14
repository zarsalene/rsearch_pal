import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { api } from "./api.js";
import { Icon } from "./icons.jsx";
import { useApp } from "./store.js";

// Each paper is a card to collect. The rank comes from real work that the server checks:
// Seen -> Read (3 claims with a checked quote) -> Explained (your own work: a word, a note, an edit) -> Mastered (you defeated the boss).
const RANKS = ["Seen", "Read", "Explained", "Mastered"];

function Pips({ n, max = 4 }) {
  return (
    <span className="pips" role="img" aria-label={`${n} of ${max} claims checked`}>
      {Array.from({ length: max }, (_, i) => (
        <i key={i} className={i < n ? "on" : ""} />
      ))}
    </span>
  );
}

export default function Collection({ notify }) {
  const [items, setItems] = useState(null);
  const xp = useApp((s) => s.game?.xp);
  const { openPaper, openBattle } = useApp.getState();

  useEffect(() => {
    api.collection().then(setItems).catch((e) => notify(e.message));
  }, [xp, notify]);

  if (!items) return <p className="muted">Loading…</p>;
  if (!items.length)
    return (
      <div className="gempty">
        <Icon name="cards" size={40} />
        <h3>No cards yet</h3>
        <p className="muted">Add a paper in the library. When its card is ready, it joins your collection.</p>
      </div>
    );
  const mastered = items.filter((c) => c.rank === 3).length;
  return (
    <div>
      <div className="setbar">
        <strong>
          {mastered} of {items.length} mastered
        </strong>
        <div className="setmeter" role="progressbar" aria-valuemin={0} aria-valuemax={items.length} aria-valuenow={mastered} aria-label="Mastered cards">
          <span style={{ width: `${(mastered / items.length) * 100}%` }} />
        </div>
      </div>
      <div className="gcards">
        {items.map((c, i) => (
          <motion.article
            key={c.id}
            className={"gcard r" + c.rank}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            whileHover={{ y: -5, rotate: -0.5 }}
            transition={{ type: "spring", stiffness: 300, damping: 24, delay: Math.min(i, 10) * 0.04 }}
          >
            <header>
              <span className="rank">
                {c.rank === 3 ? <Icon name="crown" size={14} weight="fill" /> : <Icon name="star" size={14} weight={c.rank ? "fill" : "regular"} />} {RANKS[c.rank]}
              </span>
              <Pips n={c.checked} />
            </header>
            <h3>{c.title}</h3>
            {c.keywords.length > 0 && (
              <div className="kw">
                {c.keywords.map((k) => (
                  <span key={k} className="kwchip">
                    {k}
                  </span>
                ))}
              </div>
            )}
            <p className="next">{c.next_step}</p>
            <footer>
              <button className="btn small ghost" onClick={() => openPaper(c.id)}>
                Open
              </button>
              {c.can_fight ? (
                <button className="btn small" onClick={() => openBattle(c.id)}>
                  <Icon name="sword" size={14} /> {c.boss_won ? "Fight again" : "Fight the boss"}
                </button>
              ) : (
                <span className="muted small">Check more claims to fight</span>
              )}
            </footer>
          </motion.article>
        ))}
      </div>
    </div>
  );
}
