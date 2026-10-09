import { useEffect, useState } from "react";
import { useLevel } from "./level.js";

// The simple versions that the page already has. The server also saves them, so a second request costs no AI call.
const cache = new Map();

// A text of the AI. In Expert mode it shows as it is. In Simple mode it shows the simple version, with a link to the original.
// load: a function that asks the server for the simple version. key: what makes the text different (default: the text).
export default function SimpleText({ text, load, cacheKey, className = "answer" }) {
  const level = useLevel();
  const key = cacheKey || text;
  const [state, setState] = useState({ key: "", data: null, error: "" });
  const [original, setOriginal] = useState(false);
  const simple = level === "simple" && !!text;

  useEffect(() => {
    if (!simple) return;
    setOriginal(false);
    const hit = cache.get(key);
    if (hit) {
      setState({ key, data: hit, error: "" });
      return;
    }
    let alive = true;
    setState({ key, data: null, error: "" });
    load()
      .then((data) => {
        cache.set(key, data);
        if (alive) setState({ key, data, error: "" });
      })
      .catch((e) => alive && setState({ key, data: null, error: e.message || "Error" }));
    return () => {
      alive = false;
    };
    // load is a new function in each render. The key says when the text changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [simple, key]);

  if (!simple) return <p className={className}>{text}</p>;
  const mine = state.key === key;
  const data = mine ? state.data : null;

  if (data?.ok) {
    return (
      <>
        <p className={className}>{original ? text : data.text}</p>
        <div className="simplebar">
          <span className="chip" title="The AI wrote this simple version. It can add a short explanation of a hard term. The explanation is not from the paper.">
            {original ? "Original" : data.label || "AI simplification"}
          </span>
          <button className="link" onClick={() => setOriginal(!original)}>
            {original ? "Show the simple version" : "Show the original"}
          </button>
        </div>
      </>
    );
  }
  return (
    <>
      <p className={className}>{text}</p>
      {data && <p className="small muted simplebar">{data.message}</p>}
      {state.error && mine && <p className="small muted simplebar">The simple version is not available. {state.error}</p>}
      {!data && !(mine && state.error) && (
        <p className="small muted simplebar" role="status">
          Making the simple version…
        </p>
      )}
    </>
  );
}
