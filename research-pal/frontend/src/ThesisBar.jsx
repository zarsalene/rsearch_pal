import { useEffect, useState } from "react";
import { Icon } from "./icons.jsx";

// A thin bar under the top bar of each page: the thesis title and the main question. Click it to edit.
// onSave({ title, question }) answers true when the server saved the change.
export default function ThesisBar({ project, onSave, onOpenHelper }) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (editing) return;
    setTitle(project?.title || "");
    setQuestion(project?.question || "");
  }, [project, editing]);

  if (!project) return null;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    const ok = await onSave({ title, question });
    setBusy(false);
    if (ok) setEditing(false);
  };

  if (editing) {
    return (
      <form className="thesisbar editing" onSubmit={submit} aria-label="Edit your thesis">
        <div className="inwrap">
          <label htmlFor="tb-title">Thesis title</label>
          <input id="tb-title" type="text" maxLength={300} autoFocus value={title} onChange={(e) => setTitle(e.target.value)} placeholder="The title of your thesis" />
        </div>
        <div className="inwrap">
          <label htmlFor="tb-question">Main question</label>
          <input id="tb-question" type="text" maxLength={500} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="The main question of your thesis" />
        </div>
        <div className="row">
          <button className="btn small" disabled={busy}>
            {busy ? "Saving…" : "Save"}
          </button>
          <button type="button" className="btn small ghost" onClick={() => setEditing(false)}>
            Cancel
          </button>
          <button type="button" className="link" onClick={() => { setEditing(false); onOpenHelper(); }}>
            Open the question helper
          </button>
        </div>
      </form>
    );
  }

  return (
    <div className="thesisbar">
      <button className="tb-main" onClick={() => setEditing(true)} aria-label="Edit your thesis title and question" title="Click to edit">
        <Icon name="flag" size={14} />
        <strong className={project.title ? "" : "muted"}>{project.title || "Add your thesis title"}</strong>
        {project.question && <span className="tb-q">{project.question}</span>}
      </button>
    </div>
  );
}
