import { motion } from "motion/react";
import { api } from "./api.js";
import Duck from "./Duck.jsx";
import { stage } from "./duck.js";
import { Icon } from "./icons.jsx";
import { play } from "./juice.js";
import { useApp } from "./store.js";

// The shop. Sparks come from real work (1 for each XP). Cosmetics are for the Duck. A boost is for the Semester Simulator.
// The server knows each price. A purchase never takes XP, so a level never goes down.
export default function Shop({ notify }) {
  const game = useApp((s) => s.game);
  const refresh = useApp((s) => s.refreshGame);
  if (!game) return <p className="muted">Loading…</p>;
  const outfit = game.outfit || {};
  const cosmetics = game.shop.filter((i) => i.kind === "cosmetic");
  const boosts = game.shop.filter((i) => i.kind === "boost");

  const run = async (fn, sound) => {
    try {
      await fn();
      if (sound) play(sound);
      await refresh();
    } catch (e) {
      notify(e.message);
    }
  };
  const buy = (item) => run(() => api.buy(item.id), "spark");
  const wear = (item) => {
    const next = { ...outfit };
    if (next[item.slot] === item.id) delete next[item.slot];
    else next[item.slot] = item.id;
    return run(() => api.setOutfit(next), "tap");
  };

  return (
    <div className="shop">
      <div className="shop-top">
        <div className="shop-duck">
          <Duck size={150} mood="happy" outfit={outfit} stage={stage(game.level.index)} label="Your Duck" />
        </div>
        <div>
          <span className="eyebrow">Your Sparks</span>
          <div className="sparks-big">
            <Icon name="coin" size={30} weight="fill" /> {game.sparks}
          </div>
          <p className="muted small">Real work gives Sparks: 1 for each XP. Buying never lowers your level.</p>
        </div>
      </div>

      <h2>Wardrobe</h2>
      <div className="shop-grid">
        {cosmetics.map((i) => (
          <motion.div key={i.id} className={"shopitem" + (i.owned ? " owned" : "") + (i.locked ? " locked" : "")} whileHover={{ y: -3 }}>
            <Duck size={70} outfit={{ [i.slot]: i.id }} stage="duck" />
            <strong>{i.label}</strong>
            {i.owned ? (
              <button className={"btn small" + (outfit[i.slot] === i.id ? "" : " ghost")} onClick={() => wear(i)} aria-pressed={outfit[i.slot] === i.id}>
                {outfit[i.slot] === i.id ? "Wearing" : "Wear"}
              </button>
            ) : i.locked ? (
              <span className="chip" title={`Reach the level ${i.level_name}`}>
                <Icon name="lock" size={12} /> Level {i.level_name}
              </span>
            ) : (
              <button className="btn small tint" disabled={!i.can_buy} onClick={() => buy(i)} title={i.can_buy ? "" : `You need ${i.cost - game.sparks} more Sparks`}>
                <Icon name="coin" size={14} weight="fill" /> {i.cost}
              </button>
            )}
          </motion.div>
        ))}
      </div>

      <h2>Boosts for the Semester Simulator</h2>
      <div className="shop-grid">
        {boosts.map((i) => (
          <div key={i.id} className="shopitem boost">
            <span className="boosticon">
              <Icon name={i.id === "coffee" ? "coffee" : "bolt"} size={26} weight="fill" />
            </span>
            <strong>{i.label}</strong>
            <span className="muted small">{i.text}</span>
            <span className="small">You have {i.count}</span>
            <button className="btn small tint" disabled={!i.can_buy} onClick={() => buy(i)}>
              <Icon name="coin" size={14} weight="fill" /> {i.cost}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
