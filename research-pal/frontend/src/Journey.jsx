import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import { animationsOn, levelPercent, setAnimations, tzMinutes } from "./game.js";
import ExpeditionMap from "./ExpeditionMap.jsx";
import { QuestLog } from "./Quests.jsx";
import { Icon } from "./icons.jsx";
import AvatarCard from "./Avatar3D.jsx";

const REWARD_HELP = "Conditions: level:3 (a level, by number), xp:500, streak:7 or cards:20.";
const COMPARE = [
  ["xp", "Points"],
  ["cards", "Cards with checked quotes"],
  ["focus_minutes", "Focus minutes"],
];

export function LevelCard({ game }) {
  const { level, xp } = game;
  const next = level.next;
  return (
    <section className="today-block levelcard" aria-label="Level">
      <h2>Level</h2>
      <p className="levelname">
        <strong>{level.name}</strong> <span className="small muted">level {level.index + 1} of {level.names.length}</span>
      </p>
      <p className="small muted">{xp} points</p>
      <ol className="levelsteps" aria-label="All levels">
        {level.names.map((n, i) => (
          <li key={n} className={i <= level.index ? "reached" : ""} aria-current={i === level.index ? "step" : undefined}>
            {n}
          </li>
        ))}
      </ol>
      {next ? (
        <>
          <div className="pbar" role="progressbar" aria-label={`Points to ${next.name}`} aria-valuenow={xp} aria-valuemin={level.floor} aria-valuemax={next.xp_total}>
            <span style={{ width: levelPercent(xp, level.floor, next.xp_total) + "%" }} />
          </div>
          <p className="small">
            To become a <strong>{next.name}</strong>: {next.xp_needed > 0 ? `${next.xp_needed} more points` : "enough points"}
            {next.conditions.length > 0 && ", and:"}
          </p>
          <ul className="conds">
            {next.conditions.map((c) => (
              <li key={c.text} className={c.available && c.have >= c.need ? "ok" : ""}>
                {c.available ? `${Math.min(c.have, c.need)} of ${c.need} ${c.text}` : `${c.need} ${c.text}: this part of the app is not built yet`}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="small">You are at the last level. Thank you for the work.</p>
      )}
    </section>
  );
}

export function StreakCard({ streak, onWeekend }) {
  return (
    <section className="today-block" aria-label="Streak">
      <h2>Streak</h2>
      <p className="bignum">
        {streak.current} <span className="small muted">{streak.current === 1 ? "day" : "days"}</span>
      </p>
      <p>{streak.message}</p>
      <p className="small muted">
        Best: {streak.best}. Rest tokens left this week: {streak.tokens_left} of 2. A rest day uses a token and keeps your streak.
      </p>
      {onWeekend && (
        <label className="small check">
          <input type="checkbox" checked={streak.weekend_off} onChange={(e) => onWeekend(e.target.checked)} /> The weekend is off (Saturday and Sunday need no work)
        </label>
      )}
    </section>
  );
}

function Compare({ records }) {
  return (
    <section className="today-block" aria-label="Records">
      <h2>Your own records</h2>
      <p className="small muted">You compare with your own past only. There is no ranking.</p>
      <table className="records">
        <thead>
          <tr>
            <th />
            <th>This week</th>
            <th>Last week</th>
            <th>This month</th>
            <th>Last month</th>
          </tr>
        </thead>
        <tbody>
          {COMPARE.map(([k, label]) => (
            <tr key={k}>
              <th scope="row">{label}</th>
              <td>{records[k].this_week}</td>
              <td>{records[k].last_week}</td>
              <td>{records[k].this_month}</td>
              <td>{records[k].last_month}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function Rewards({ rewards, onChanged, notify }) {
  const [text, setText] = useState("");
  const [condition, setCondition] = useState("");
  const run = async (fn) => {
    try {
      await fn();
      await onChanged();
    } catch (e) {
      notify(e.message);
    }
  };
  return (
    <section className="today-block" aria-label="Own rewards">
      <h2>Your own rewards</h2>
      <p className="small muted">Write a reward for yourself. The app tells you when you earned it. {REWARD_HELP}</p>
      <ul className="rewards">
        {rewards.map((r) => (
          <li key={r.id} className={r.earned_at ? "earned" : ""}>
            <span>
              <strong>{r.text}</strong> <span className="small muted">({r.condition})</span>
            </span>
            {r.earned_at && !r.claimed && (
              <button className="btn small" onClick={() => run(() => api.claimReward(r.id))}>
                You earned it. Claim it
              </button>
            )}
            {r.claimed && <span className="badge b-ok">Claimed</span>}
            <button className="iconbtn" aria-label={`Delete the reward: ${r.text}`} onClick={() => run(() => api.deleteReward(r.id))}>
              <Icon name="x" size={14} />
            </button>
          </li>
        ))}
        {rewards.length === 0 && <li className="small muted">No reward yet. Example: “A dinner out” at level:3.</li>}
      </ul>
      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault();
          run(async () => {
            await api.addReward({ text, condition });
            setText("");
            setCondition("");
          });
        }}
      >
        <input type="text" maxLength={120} value={text} onChange={(e) => setText(e.target.value)} placeholder="My reward" aria-label="My reward" />
        <input type="text" className="cond" value={condition} onChange={(e) => setCondition(e.target.value)} placeholder="level:3" aria-label="Condition of the reward" />
        <button className="btn small" disabled={!text.trim() || !condition.trim()}>
          Add
        </button>
      </form>
    </section>
  );
}

// Level, streak, badges, records and your own rewards. The points come from work that the server checked.
export default function Journey({ notify, mapOn = false, gameOn = true, questsOn = false, avatarOn = false, onGo = () => {} }) {
  const [game, setGame] = useState(null);
  const [anim, setAnim] = useState(animationsOn);
  const load = useCallback(async () => {
    if (!gameOn) return;
    try {
      setGame(await api.game(new Date().toLocaleDateString("en-CA"), tzMinutes()));
    } catch (e) {
      notify(e.message);
    }
  }, [notify, gameOn]);
  useEffect(() => {
    load();
  }, [load]);

  if (!gameOn) {
    return (
      <section className="journey">
        <h1>Journey</h1>
        {mapOn && <ExpeditionMap onGo={onGo} notify={notify} />}
      </section>
    );
  }
  if (!game) return <p className="muted">Loading…</p>;
  const weekend = async (on) => {
    try {
      await api.gameSettings({ weekend_off: on });
      await load();
    } catch (e) {
      notify(e.message);
    }
  };
  return (
    <section className="journey">
      <h1>Journey</h1>
      <p className="lead">Points come only from real work that the app can check: a card with checked quotes, a Feynman check that you passed, a correct quiz answer, a link with quotes, a focus session and your win of the day.</p>
      {mapOn && <ExpeditionMap onGo={onGo} notify={notify} />}
      {questsOn && <QuestLog notify={notify} />}
      <div className="today-grid">
        <LevelCard game={game} />
        {avatarOn && <AvatarCard level={game.level.index} />}
        <StreakCard streak={game.streak} onWeekend={weekend} />
      </div>

      <section className="today-block" aria-label="Badges">
        <h2>Badges</h2>
        <ul className="badges">
          {game.badges.map((b) => (
            <li key={b.code} className="badge-item earned" title={b.how}>
              <Icon name="check" size={16} /> <strong>{b.name}</strong>
            </li>
          ))}
          {game.badges_missing.map((b) => (
            <li key={b.code} className="badge-item" title={b.how}>
              <span className="muted">{b.name}</span>
            </li>
          ))}
        </ul>
        <p className="small muted">There are few badges, on purpose. Each one marks a real moment.</p>
      </section>

      <Compare records={game.records} />
      <Rewards rewards={game.rewards} onChanged={load} notify={notify} />

      <section className="today-block" aria-label="Where your points came from">
        <h2>Where your points came from</h2>
        {game.recent.length === 0 ? (
          <p className="small muted">No point yet. Make a card, explain a paper or write your win. Each real step counts.</p>
        ) : (
          <ul className="recent">
            {game.recent.map((e) => (
              <li key={e.id}>
                <span className="small muted">{e.date}</span> {e.label} <strong>+{e.xp}</strong>
              </li>
            ))}
          </ul>
        )}
      </section>

      <label className="small check">
        <input
          type="checkbox"
          checked={anim}
          onChange={(e) => {
            setAnim(e.target.checked);
            setAnimations(e.target.checked);
          }}
        />{" "}
        Calm animations when you reach a new level or badge
      </label>
    </section>
  );
}
