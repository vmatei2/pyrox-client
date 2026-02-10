import React from "react";
import { createRoot } from "react-dom/client";

import App from "./App.jsx";
import "./styles.css";
import "./style_layers/premium_tokens.css";
import "./style_layers/premium_primitives.css";
import "./style_layers/premium_flow.css";
import "./style_layers/bootstrap.css";

createRoot(document.getElementById("root")).render(<App />);

const hideBootSplash = () => {
  document.documentElement.classList.add("app-ready");
  const splash = document.getElementById("boot-splash");
  if (!splash) {
    return;
  }
  if (splash.classList.contains("is-hidden")) {
    return;
  }
  splash.classList.add("is-hidden");
  window.setTimeout(() => {
    splash.remove();
  }, 220);
};

window.addEventListener("pyrox:hide-boot-splash", hideBootSplash, { once: true });
