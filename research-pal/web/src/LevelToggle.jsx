import { setLevel, useLevel } from "./level.js";

const LEVELS = [
  ["expert", "Expert", "The texts of the AI as they are"],
  ["simple", "Simple", "Shorter sentences. Each hard term has an explanation."],
];

// The switch in the top bar. It changes how the texts of the AI show: on the cards, in the chat, in the links and in the mind map.
export default function LevelToggle() {
  const level = useLevel();
  return (
    <div className="levelseg" role="radiogroup" aria-label="Reading level">
      {LEVELS.map(([v, label, hint]) => (
        <button key={v} type="button" role="radio" aria-checked={level === v} title={hint} onClick={() => setLevel(v)}>
          {label}
        </button>
      ))}
    </div>
  );
}
