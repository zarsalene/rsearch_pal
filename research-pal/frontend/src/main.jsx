import React from "react";
import { createRoot } from "react-dom/client";
import { MotionConfig } from "motion/react";
import App from "./App.jsx";
// Fonts come from our own server (no request to Google). font-display is swap.
import "@fontsource-variable/geist";
import "@fontsource-variable/source-serif-4";
import "./styles.css";
import "./simple-words.css";
import "./mobile.css";

// reducedMotion="user": if the phone says "reduce motion" in its settings, the movements are off and only the fades stay.
createRoot(document.getElementById("root")).render(
  <MotionConfig reducedMotion="user">
    <App />
  </MotionConfig>,
);
