import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
// Fonts come from our own server (no request to Google). font-display is swap.
import "@fontsource-variable/geist";
import "@fontsource-variable/source-serif-4";
import "./styles.css";
import "./simple-words.css";
import "./mobile.css";

createRoot(document.getElementById("root")).render(<App />);
