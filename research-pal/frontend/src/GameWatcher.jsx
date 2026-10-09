import { useEffect, useState } from "react";
import { api } from "./api.js";
import { newThings, tzMinutes } from "./game.js";

// A calm message when the student reaches a new level or earns a badge. It checks when the page opens, when you change the tab,
// and each 30 seconds. It shows nothing at the first visit. The message goes away alone. Animations can be switched off (Journey page).
export default function GameWatcher({ tick }) {
  const [items, setItems] = useState([]);

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const g = await api.game(new Date().toLocaleDateString("en-CA"), tzMinutes());
        const fresh = newThings(g);
        if (alive && fresh.length) setItems((old) => [...old, ...fresh]);
      } catch {
        /* the game is off or the server is busy: nothing to show */
      }
    };
    check();
    const t = setInterval(check, 30000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [tick]);

  useEffect(() => {
    if (!items.length) return;
    const t = setTimeout(() => setItems([]), 8000);
    return () => clearTimeout(t);
  }, [items]);

  if (!items.length) return null;
  return (
    <div className="celebrate" role="status">
      {items.map((x, i) => (
        <p key={i} className={x.kind}>
          {x.text}
        </p>
      ))}
      <button className="link" onClick={() => setItems([])}>
        Close
      </button>
    </div>
  );
}
