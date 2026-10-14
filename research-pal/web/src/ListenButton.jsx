import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";

// The server makes the voice (Piper). The audio of one passage stays in memory, so a second click costs nothing.
const audio = new Map();
const urlFor = async (text) => {
  if (!audio.has(text)) audio.set(text, URL.createObjectURL(await api.speak(text)));
  return audio.get(text);
};

// A long text goes to the voice in short passages that end at a sentence end. The first sound starts fast.
export function splitText(text, limit = 900) {
  const out = [];
  let cur = "";
  for (const s of String(text || "").replace(/\s+/g, " ").trim().split(/(?<=[.!?])\s+/)) {
    if (cur && cur.length + s.length + 1 > limit) (out.push(cur), (cur = ""));
    cur = (cur + " " + s).trim();
  }
  if (cur) out.push(cur);
  return out;
}

// start(gen): gen is an async generator that gives { text, info }. The next passage loads while the first one plays.
function useSpeaker() {
  const [state, setState] = useState("idle"); // idle | loading | playing
  const [info, setInfo] = useState("");
  const [error, setError] = useState("");
  const run = useRef(0);
  const el = useRef(null);

  const stop = () => {
    run.current++;
    el.current?.pause();
    el.current = null;
    setState("idle");
    setInfo("");
  };
  useEffect(() => () => (run.current++, el.current?.pause()), []);

  async function start(gen) {
    const id = ++run.current;
    setError("");
    setState("loading");
    const it = gen();
    const load = async () => {
      const r = await it.next();
      return r.done ? null : { url: await urlFor(r.value.text), info: r.value.info || "" };
    };
    try {
      let cur = await load();
      while (cur && id === run.current) {
        const next = load();
        next.catch(() => {});
        setInfo(cur.info);
        await new Promise((resolve, reject) => {
          const a = new Audio(cur.url);
          el.current = a;
          a.onended = a.onpause = resolve;
          a.play().then(() => id === run.current && setState("playing"), reject);
        });
        cur = id === run.current ? await next : null;
      }
    } catch (e) {
      if (id === run.current) setError(e.message || "Error");
    } finally {
      if (id === run.current) (setState("idle"), setInfo(""));
    }
  }
  return { state, info, error, start, stop };
}

// Reads one text aloud: an AI answer, a summary or a card field.
export default function ListenButton({ text, label = "Listen" }) {
  const sp = useSpeaker();
  if (!text) return null;
  const go = () => (sp.state === "idle" ? sp.start(async function* () { for (const t of splitText(text)) yield { text: t }; }) : sp.stop());
  return (
    <>
      <button className="link" onClick={go} aria-label={sp.state === "idle" ? label + " (read aloud)" : "Stop"}>
        {sp.state === "loading" ? "Loading the voice…" : sp.state === "playing" ? "Stop" : label}
      </button>
      {sp.error && <span className="small muted"> {sp.error}</span>}
    </>
  );
}

// Reads the paper itself, page by page, from the page that you choose.
export function PaperReader({ paperId, nPages }) {
  const sp = useSpeaker();
  const [from, setFrom] = useState(1);
  if (!nPages) return null;
  const go = () =>
    sp.state !== "idle"
      ? sp.stop()
      : sp.start(async function* () {
          for (let n = Math.min(Math.max(1, from), nPages); n <= nPages; n++) {
            const r = await api.readPage(paperId, n);
            for (const t of r.passages) yield { text: t, info: `Page ${n} of ${nPages}` };
          }
        });
  return (
    <div className="simplebar" role="group" aria-label="Read the paper aloud">
      <button className="link" onClick={go}>
        {sp.state === "loading" ? "Loading the voice…" : sp.state === "playing" ? "Stop reading" : "Read the paper aloud"}
      </button>
      {sp.state === "idle" ? (
        <label className="small muted">
          {" "}from page{" "}
          <input type="number" min={1} max={nPages} value={from} onChange={(e) => setFrom(+e.target.value || 1)} style={{ width: "4.5em" }} />
        </label>
      ) : (
        <span className="small muted"> {sp.info}</span>
      )}
      {sp.error && <span className="small muted"> {sp.error}</span>}
    </div>
  );
}
