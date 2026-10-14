import Duck from "./Duck.jsx";
import { stage } from "./duck.js";
import { Icon } from "./icons.jsx";
import { useApp } from "./store.js";

// A small chip in the top bar: the Duck, the level, the streak and the Sparks. A tap opens the Play page.
export default function GameBar() {
  const game = useApp((s) => s.game);
  const setTab = useApp((s) => s.setTab);
  if (!game) return null;
  const { level, streak, sparks } = game;
  return (
    <button className="gamebar" onClick={() => setTab("play")} aria-label={`Play. Level ${level.name}. Streak ${streak.days} days. ${sparks} Sparks.`} title="Open the game">
      <Duck size={28} outfit={game.outfit} stage={stage(level.index)} mood={streak.today_done ? "happy" : "idle"} />
      <span className="gb-level">{level.name}</span>
      <span className={"gb-chip" + (streak.today_done ? " lit" : "")}>
        <Icon name="fire" size={14} weight="fill" /> {streak.days}
      </span>
      <span className="gb-chip">
        <Icon name="coin" size={14} weight="fill" /> {sparks}
      </span>
    </button>
  );
}
