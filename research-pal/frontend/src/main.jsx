import React from "react";
import { createRoot } from "react-dom/client";
import { MotionConfig } from "motion/react";
import App from "./App.jsx";
import "./styles.css";
import "./simple-words.css";
import "./understand.css";
import "./today.css";
import "./game.css";
import "./review.css";
import "./quests.css";
import "./write.css";
// The phone rules come last, so they win over the rules of the pages above.
import "./mobile.css";

// reducedMotion="user": if the phone says "reduce motion" in its settings, the movements are off and only the fades stay.
createRoot(document.getElementById("root")).render(
  <MotionConfig reducedMotion="user">
    <App />
  </MotionConfig>,
);
