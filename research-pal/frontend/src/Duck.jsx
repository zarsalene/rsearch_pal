import { useEffect, useState } from "react";
import { api } from "./api.js";

// A small rubber duck. The student explains ideas to it. It shows short, kind messages. No AI: the texts are fixed.
export function DuckIcon({ size = 40 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true" className="duckicon">
      <ellipse cx="24" cy="32" rx="16" ry="11" fill="#F6C945" />
      <circle cx="32" cy="15" r="9" fill="#F6C945" />
      <path d="M40 16h6l-5 4z" fill="#F08A24" />
      <circle cx="34" cy="13" r="1.6" fill="#2A2A2E" />
      <path d="M10 30c4 6 14 7 20 1" fill="none" stroke="#E0AE2B" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

// event: { name, seed }. The server picks the message of the event.
export default function Duck({ event, onHide }) {
  const [text, setText] = useState("");
  useEffect(() => {
    let alive = true;
    api
      .companion(event.name, event.seed)
      .then((r) => alive && setText(r.message))
      .catch(() => alive && setText(""));
    return () => {
      alive = false;
    };
  }, [event.name, event.seed]);
  return (
    <aside className="duck" aria-label="Duck">
      <DuckIcon />
      <p className="duckmsg" role="status">
        {text || "Duck is here."}
      </p>
      <button className="link" onClick={onHide}>
        Hide Duck
      </button>
    </aside>
  );
}
