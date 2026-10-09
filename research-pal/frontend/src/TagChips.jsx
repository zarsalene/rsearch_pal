// The name of a sub-question: its place in the list. The first is SQ1.
export const sqLabel = (subQuestions, id) => {
  const i = subQuestions.findIndex((s) => s.id === id);
  return i < 0 ? "" : `SQ${i + 1}`;
};

// Chips that link a paper (or one card of a paper) to sub-questions. Click a chip to switch it on or off.
// onChange(ids) gets the new list. label names the group for a screen reader.
export default function TagChips({ subQuestions, selected = [], onChange, busy, label = "Sub-questions of this paper" }) {
  if (!subQuestions?.length) return null;
  const toggle = (id) => onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);
  return (
    <div className="tagchips" role="group" aria-label={label}>
      {subQuestions.map((s, i) => (
        <button key={s.id} type="button" className={"tagchip" + (selected.includes(s.id) ? " on" : "")} aria-pressed={selected.includes(s.id)} disabled={busy} title={s.text} onClick={() => toggle(s.id)}>
          SQ{i + 1}
        </button>
      ))}
    </div>
  );
}
