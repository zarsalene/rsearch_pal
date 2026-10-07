import { useEffect, useState } from "react";
import { Icon } from "./icons.jsx";
import { applyMode, getMode, setMode } from "./theme.js";

const MODES = [
  ["light", "Light", "sun"],
  ["system", "Match my device", "monitor"],
  ["dark", "Dark", "moon"],
];

export default function ThemeToggle() {
  const [mode, setLocal] = useState(getMode);

  // In System mode, follow the device when it changes (for example at sunset).
  useEffect(() => {
    if (mode !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const on = () => applyMode("system");
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [mode]);

  const pick = (m) => {
    setLocal(m);
    setMode(m);
  };

  return (
    <div className="themeseg" role="radiogroup" aria-label="Color theme">
      {MODES.map(([m, label, icon]) => (
        <button key={m} type="button" role="radio" aria-checked={mode === m} aria-label={label} title={label} onClick={() => pick(m)}>
          <Icon name={icon} size={15} />
        </button>
      ))}
    </div>
  );
}
