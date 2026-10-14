import { useState } from "react";
import Graph from "./Graph.jsx";
import Compare from "./Compare.jsx";

// Two views of the same papers: the graph of links, and the table that compares the cards.
export default function LinksTab({ onOpenCard, notify }) {
  const [view, setView] = useState("graph");
  return (
    <section>
      <div className="viewseg" role="radiogroup" aria-label="View">
        {[
          ["graph", "Graph"],
          ["table", "Table"],
        ].map(([k, label]) => (
          <button key={k} role="radio" aria-checked={view === k} onClick={() => setView(k)}>
            {label}
          </button>
        ))}
      </div>
      {view === "graph" ? (
        <Graph onOpenCard={onOpenCard} notify={notify} />
      ) : (
        <>
          <h1>Compare</h1>
          <Compare onOpenCard={onOpenCard} notify={notify} />
        </>
      )}
    </section>
  );
}
