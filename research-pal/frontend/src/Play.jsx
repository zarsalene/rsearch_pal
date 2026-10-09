import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { animationsOn } from "./game.js";

const TILE = 48;
const ICON = { flower: "🌸", tree: "🌳", bench: "🪑", lamp: "💡", flag: "🚩", tent: "⛺", boat: "⛵", telescope: "🔭", fountain: "⛲" };
const SPOT_ICON = { quotes: "🔎", terms: "🔤", shop: "🛒" };
const SPOT_NAME = { quotes: "Quote Hunt", terms: "Word Match", shop: "Shop" };

// The island. The page only draws and moves the Duck. The server keeps the coins, the items and the answers of the games.
function draw(ctx, state, pos) {
  const { w, h } = state.grid;
  ctx.clearRect(0, 0, w * TILE, h * TILE);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const edge = x === 0 || y === 0 || x === w - 1 || y === h - 1;
      ctx.fillStyle = edge ? "#7cc4e8" : (x + y) % 2 ? "#9bd48a" : "#8fcb7f";
      ctx.fillRect(x * TILE, y * TILE, TILE, TILE);
    }
  }
  ctx.font = "30px serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (const s of state.spots) {
    ctx.fillStyle = "rgba(255,255,255,.55)";
    ctx.fillRect(s.x * TILE + 3, s.y * TILE + 3, TILE - 6, TILE - 6);
    ctx.fillStyle = "#000";
    ctx.fillText(SPOT_ICON[s.code], s.x * TILE + TILE / 2, s.y * TILE + TILE / 2);
  }
  for (const it of state.shop) if (it.owned && it.x >= 0) ctx.fillText(ICON[it.code] || "⭐", it.x * TILE + TILE / 2, it.y * TILE + TILE / 2);
  ctx.font = "34px serif";
  ctx.fillText("🦆", pos.x * TILE + TILE / 2, pos.y * TILE + TILE / 2);
}

function Round({ round, onDone, notify }) {
  const [i, setI] = useState(0);
  const [answers, setAnswers] = useState([]);
  const [result, setResult] = useState(null);
  const q = round.questions[i];
  const pick = async (n) => {
    const next = [...answers, n];
    if (i + 1 < round.questions.length) {
      setAnswers(next);
      setI(i + 1);
      return;
    }
    try {
      setResult(await api.finishRound(round.id, next));
    } catch (e) {
      notify(e.message);
    }
  };
  if (result) {
    return (
      <div className="playpanel" role="region" aria-label="Round result">
        <h3>
          {result.score} of {result.total} right
        </h3>
        <p>
          {result.message} You win <strong>{result.coins} {result.coins === 1 ? "coin" : "coins"}</strong>.
          {result.capped && " The coins for today are full. You can still play for fun."}
        </p>
        <ol className="playsources">
          {result.answers.map((a, n) => (
            <li key={n} className={a.chosen === a.correct ? "ok" : "miss"}>
              <span>{a.chosen === a.correct ? "Right." : "Not this time."}</span> From <em>{a.source.title}</em>, page {a.source.page}: “{a.source.quote}”
            </li>
          ))}
        </ol>
        <button className="btn" onClick={() => onDone(result)}>
          Back to the island
        </button>
      </div>
    );
  }
  return (
    <div className="playpanel" role="region" aria-label={round.name}>
      <h3>
        {round.name} <span className="small muted">question {i + 1} of {round.questions.length}</span>
      </h3>
      <p className="playprompt">{q.prompt}</p>
      <div className="playoptions">
        {q.options.map((o, n) => (
          <button key={n} className="btn ghost" onClick={() => pick(n)}>
            {o}
          </button>
        ))}
      </div>
      <button className="link" onClick={() => onDone(null)}>
        Stop. No coins, no penalty.
      </button>
    </div>
  );
}

function Shop({ state, onBuy }) {
  return (
    <div className="playpanel" role="region" aria-label="Shop">
      <h3>Shop</h3>
      <p className="small muted">You have {state.coins.balance} coins. Your work and the mini-games give coins. Items are only for fun.</p>
      <ul className="shoplist">
        {state.shop.map((it) => (
          <li key={it.code}>
            <span aria-hidden="true">{ICON[it.code]}</span> {it.name} <span className="small muted">{it.cost} coins</span>
            {it.owned ? (
              <span className="small ok"> You have it.</span>
            ) : (
              <button className="btn small" disabled={state.coins.balance < it.cost} onClick={() => onBuy(it.code)} aria-label={`Buy ${it.name} for ${it.cost} coins`}>
                Buy
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function DuckIsland({ notify }) {
  const [state, setState] = useState(null);
  const [pos, setPos] = useState({ x: 6, y: 4 });
  const [panel, setPanel] = useState(null); // "shop" | "decorate" | { round }
  const [choose, setChoose] = useState("");
  const canvas = useRef(null);
  const target = useRef(null);

  const load = useCallback(() => api.play().then(setState).catch((e) => notify(e.message)), [notify]);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    const ctx = canvas.current?.getContext?.("2d"); // jsdom has no canvas: the buttons below still work
    if (ctx && state) draw(ctx, state, pos);
  }, [state, pos]);

  const enter = useCallback(
    async (code) => {
      if (code === "shop") return setPanel("shop");
      try {
        setPanel({ round: await api.newRound(code) });
      } catch (e) {
        notify(e.message);
      }
    },
    [notify],
  );
  const spotAt = (p) => state?.spots.find((s) => s.x === p.x && s.y === p.y);
  const step = useCallback(
    (dx, dy) => {
      if (!state || panel) return;
      const x = Math.max(1, Math.min(state.grid.w - 2, pos.x + dx));
      const y = Math.max(1, Math.min(state.grid.h - 2, pos.y + dy));
      if (x === pos.x && y === pos.y) return;
      setPos({ x, y });
      const s = spotAt({ x, y });
      if (s) enter(s.code);
    },
    [state, panel, pos, enter], // eslint-disable-line react-hooks/exhaustive-deps
  );
  // walk to a tile that the student clicked: one step each 110 ms (a jump when animations are off)
  useEffect(() => {
    const t = setInterval(() => {
      if (!target.current) return;
      const dx = Math.sign(target.current.x - pos.x);
      const dy = dx ? 0 : Math.sign(target.current.y - pos.y);
      if (!dx && !dy) target.current = null;
      else step(dx, dy);
    }, animationsOn() ? 110 : 15);
    return () => clearInterval(t);
  }, [pos, step]);

  const keys = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1], a: [-1, 0], d: [1, 0], w: [0, -1], s: [0, 1] };
  const onKey = (e) => {
    const m = keys[e.key];
    if (m) {
      e.preventDefault();
      target.current = null;
      step(...m);
    }
  };
  const onClick = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    target.current = { x: Math.floor(((e.clientX - r.left) / r.width) * state.grid.w), y: Math.floor(((e.clientY - r.top) / r.height) * state.grid.h) };
  };
  const goTo = (code) => {
    const s = state.spots.find((x) => x.code === code);
    setPos({ x: s.x, y: s.y });
    enter(code);
  };
  const act = async (fn) => {
    try {
      setState(await fn());
    } catch (e) {
      notify(e.message);
    }
  };
  if (!state) return <p className="small muted">Loading the island…</p>;
  const owned = state.shop.filter((i) => i.owned);
  const c = state.coins;
  return (
    <section className="today-block island" aria-label="Duck Island">
      <h2>Duck Island</h2>
      <p className="small muted">
        Walk with the Duck: arrow keys, W A S D, or click. Play mini-games with quotes from your papers and win coins. Play gives no points and no levels. Nothing is lost if you stop.
      </p>
      <p role="status" aria-label="Coins">
        <strong>{c.balance} coins</strong> <span className="small muted">from work {c.work} · from play {c.play} · spent {c.spent} · play coins today {c.play_today} of {c.play_cap}</span>
      </p>
      <div className="islandwrap" tabIndex={0} onKeyDown={onKey} role="application" aria-label="The island. Use the arrow keys to walk. The buttons below do the same.">
        <canvas ref={canvas} width={state.grid.w * TILE} height={state.grid.h * TILE} onClick={onClick} className="islandcanvas" />
      </div>
      <div className="islandbtns" role="group" aria-label="Places of the island">
        {state.games.map((g) => (
          <button key={g.code} className="btn ghost small" onClick={() => goTo(g.code)} title={g.text}>
            {SPOT_ICON[g.code]} Go to {g.name}
          </button>
        ))}
        <button className="btn ghost small" onClick={() => goTo("shop")}>
          {SPOT_ICON.shop} Go to the Shop
        </button>
        <button className="btn ghost small" onClick={() => setPanel("decorate")}>
          Decorate
        </button>
      </div>
      <p className="small muted">
        {state.material.quotes} checked quotes and {state.material.terms} saved words are ready for the games.
      </p>
      {panel?.round && (
        <Round
          round={panel.round}
          notify={notify}
          onDone={() => {
            setPanel(null);
            load();
          }}
        />
      )}
      {panel === "shop" && (
        <>
          <Shop state={state} onBuy={(code) => act(() => api.buyItem(code))} />
          <button className="link" onClick={() => setPanel(null)}>
            Close the shop
          </button>
        </>
      )}
      {panel === "decorate" && (
        <div className="playpanel" role="region" aria-label="Decorate">
          <h3>Decorate</h3>
          {owned.length === 0 ? (
            <p className="small muted">You have no items yet. Buy one in the Shop.</p>
          ) : (
            <>
              <p className="small muted">Walk the Duck to a free tile. Choose an item. Press Place. The Duck is on tile {pos.x + 1}, {pos.y + 1}.</p>
              <label>
                Item{" "}
                <select value={choose || owned[0].code} onChange={(e) => setChoose(e.target.value)}>
                  {owned.map((i) => (
                    <option key={i.code} value={i.code}>
                      {i.name}
                    </option>
                  ))}
                </select>
              </label>{" "}
              <button className="btn small" onClick={() => act(() => api.placeItem(choose || owned[0].code, pos.x, pos.y))}>
                Place at the Duck
              </button>
            </>
          )}
          <button className="link" onClick={() => setPanel(null)}>
            Close
          </button>
        </div>
      )}
    </section>
  );
}
