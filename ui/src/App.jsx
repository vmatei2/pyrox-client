import { lazy, Suspense, useEffect, useState } from "react";
import { Capacitor } from "@capacitor/core";
import { ModeTabIcon } from "./components/UiPrimitives.jsx";
import { API_BASE, getInitialMode, VALID_MODES } from "./constants/segments.js";
import { useAppBootstrap } from "./hooks/useAppBootstrap.js";
import { useIosMobile } from "./hooks/useIosMobile.js";

const ReportMode = lazy(() => import("./pages/ReportMode.jsx"));
const CompareMode = lazy(() => import("./pages/CompareMode.jsx"));
const DeepdiveMode = lazy(() => import("./pages/DeepdiveMode.jsx"));
const RankingsMode = lazy(() => import("./pages/RankingsMode.jsx"));
const PlannerMode = lazy(() => import("./pages/PlannerMode.jsx"));

const MODE_ORDER = ["report", "compare", "deepdive", "rankings", "planner"];
const MODE_CONFIG = {
  report: { label: "Race Report", component: ReportMode },
  compare: { label: "Compare", component: CompareMode },
  deepdive: { label: "Deep Dive", component: DeepdiveMode },
  rankings: { label: "Rankings", component: RankingsMode },
  planner: { label: "Race Planner", component: PlannerMode },
};

const ModeLoadingFallback = () => (
  <main className="layout is-single">
    <section className="panel">
      <div className="skeleton-panel" aria-hidden="true">
        <div className="skeleton-line" />
        <div className="skeleton-line" />
        <div className="skeleton-line" />
      </div>
    </section>
  </main>
);

export default function App() {
  const platform = Capacitor.getPlatform ? Capacitor.getPlatform() : "web";
  const isNativeApp = Capacitor.isNativePlatform
    ? Capacitor.isNativePlatform()
    : platform !== "web";
  const isIosMobile = useIosMobile();
  const [mode, setMode] = useState(getInitialMode);
  const [mountedModes, setMountedModes] = useState(() => ({ [getInitialMode()]: true }));
  const {
    isBootstrapping,
    isReady,
    warning: bootstrapWarning,
    retryBootstrap,
  } = useAppBootstrap(API_BASE);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }
    document.body.classList.toggle("ios-mobile", isIosMobile);
    return () => {
      document.body.classList.remove("ios-mobile");
    };
  }, [isIosMobile]);

  useEffect(() => {
    setMountedModes((prev) => (prev[mode] ? prev : { ...prev, [mode]: true }));
  }, [mode]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem("pyrox.ui.last-mode", mode);
    }
  }, [mode]);

  useEffect(() => {
    if (typeof window === "undefined" || isBootstrapping || !isReady) {
      return;
    }
    window.dispatchEvent(new Event("pyrox:hide-boot-splash"));
  }, [isBootstrapping, isReady]);

  const handleModeChange = (nextMode) => {
    if (!VALID_MODES.has(nextMode)) {
      return;
    }
    setMode(nextMode);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className={`app-shell${isReady ? " is-ready" : ""}`}>
      <div className="app-shell-content">
        <div className={`app${isIosMobile ? " ios-mobile-shell" : ""}`}>
          <header className="hero">
            <div className="hero-tag">Pyrox Race Analysis</div>
            <h1>Find an athlete, pick a race, and build a Pyrox race report.</h1>
            <p>
              Search our race database, review your race, and generate a report.
              {!isNativeApp ? " PDF export is available on desktop." : null}
            </p>
          </header>

          {bootstrapWarning ? (
            <div className="bootstrap-warning" role="status" aria-live="polite">
              <span>{bootstrapWarning}</span>
              <button
                type="button"
                className="secondary bootstrap-warning-action"
                onClick={retryBootstrap}
                disabled={isBootstrapping}
              >
                {isBootstrapping ? "Retrying..." : "Retry connection"}
              </button>
            </div>
          ) : null}

          <div className="mode-tabs">
            {MODE_ORDER.map((modeKey) => (
              <button
                key={modeKey}
                type="button"
                className={`mode-tab ${mode === modeKey ? "is-active" : ""}`}
                onClick={() => handleModeChange(modeKey)}
              >
                <span className="mode-tab-icon">
                  <ModeTabIcon kind={modeKey} />
                </span>
                <span className="mode-tab-label">{MODE_CONFIG[modeKey].label}</span>
              </button>
            ))}
          </div>

          {MODE_ORDER.map((modeKey) => {
            if (!mountedModes[modeKey]) {
              return null;
            }
            const ModeComponent = MODE_CONFIG[modeKey].component;
            return (
              <section
                key={modeKey}
                aria-hidden={mode !== modeKey}
                style={{ display: mode === modeKey ? "block" : "none" }}
              >
                <Suspense fallback={<ModeLoadingFallback />}>
                  <ModeComponent isIosMobile={isIosMobile} />
                </Suspense>
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}
