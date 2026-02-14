import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";

import App from "./App.jsx";
import { queryClient } from "./api/client.js";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/components.css";
import "./styles/charts.css";
import "./styles/layouts.css";
import "./styles/bootstrap.css";

createRoot(document.getElementById("root")).render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>
);

const isNativeCapacitorRuntime = () => {
  const protocol = window.location?.protocol || "";
  const ua = navigator.userAgent || "";
  return protocol === "capacitor:" || protocol === "ionic:" || ua.includes("Capacitor");
};

if (isNativeCapacitorRuntime()) {
  document.documentElement.classList.add("native-capacitor");
  document.documentElement.classList.add("app-ready");
  const splash = document.getElementById("boot-splash");
  if (splash) {
    splash.remove();
  }
}

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
