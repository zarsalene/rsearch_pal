import { AnimatePresence, motion } from "motion/react";
import Battle from "./Battle.jsx";
import Confetti from "./Confetti.jsx";
import Duck from "./Duck.jsx";
import { LEVEL_STORY, stage } from "./duck.js";
import { Icon } from "./icons.jsx";
import { useApp } from "./store.js";

// Everything that shows on top of the pages: the confetti, the small reward messages, the level-up card and the boss fight.
function LevelUp({ name }) {
  const close = useApp((s) => s.closeLevelUp);
  const game = useApp((s) => s.game);
  return (
    <motion.div className="levelup" role="dialog" aria-modal="true" aria-label={`Level up: ${name}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <motion.div className="levelup-card" initial={{ scale: 0.7, y: 30, opacity: 0 }} animate={{ scale: 1, y: 0, opacity: 1 }} transition={{ type: "spring", stiffness: 240, damping: 16 }}>
        <Duck size={130} mood="cheer" outfit={game?.outfit} stage={stage(game?.level?.index)} />
        <span className="eyebrow">Level up</span>
        <h2>You are now a {name}!</h2>
        <p>{LEVEL_STORY[name]}</p>
        <button className="btn" onClick={close} autoFocus>
          Keep going
        </button>
      </motion.div>
    </motion.div>
  );
}

export default function GameLayer() {
  const battle = useApp((s) => s.battle);
  const rewards = useApp((s) => s.rewards);
  const levelUp = useApp((s) => s.levelUp);
  const { closeBattle, dismissReward } = useApp.getState();
  return (
    <>
      <Confetti />
      <div className="rewards" aria-live="polite">
        <AnimatePresence>
          {rewards.map((r) => (
            <motion.button
              key={r.id}
              className={"reward t-" + r.tone}
              layout
              initial={{ opacity: 0, x: 40, scale: 0.9 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 40 }}
              transition={{ type: "spring", stiffness: 380, damping: 26 }}
              onClick={() => dismissReward(r.id)}
            >
              <Icon name={r.tone === "eureka" ? "idea" : r.tone === "kind" ? "heart" : "bolt"} size={18} weight="fill" />
              <span>
                <strong>{r.title}</strong>
                <em>{r.text}</em>
              </span>
            </motion.button>
          ))}
        </AnimatePresence>
      </div>
      <AnimatePresence>{levelUp && <LevelUp name={levelUp} />}</AnimatePresence>
      {battle && <Battle paperId={battle} onClose={closeBattle} />}
    </>
  );
}
