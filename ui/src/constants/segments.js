import { Capacitor } from "@capacitor/core";

export const resolveApiBase = () => {
  const normalize = (value) => {
    if (!value || typeof value !== "string") {
      return "";
    }
    return value.trim().replace(/\/$/, "");
  };

  const configured = import.meta.env.VITE_API_BASE_URL;
  const normalizedConfigured = normalize(configured);
  if (normalizedConfigured) {
    return normalizedConfigured;
  }

  const platform = Capacitor.getPlatform ? Capacitor.getPlatform() : "web";
  if (platform === "android") {
    return "http://10.0.2.2:8000";
  }
  if (platform === "ios") {
    return "http://127.0.0.1:8000";
  }

  if (typeof window !== "undefined" && window.location?.hostname) {
    return `http://${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
};

export const API_BASE = resolveApiBase();
export const VALID_MODES = new Set(["report", "compare", "deepdive", "rankings", "planner", "profile"]);
export const IOS_MOBILE_MEDIA_QUERY = "(max-width: 900px)";

export const isIosBrowserDevice = () => {
  if (typeof window === "undefined") {
    return false;
  }
  const { navigator } = window;
  const userAgent = navigator.userAgent || "";
  const isiOSUserAgent = /iPad|iPhone|iPod/i.test(userAgent);
  const isIPadDesktopMode = navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
  return isiOSUserAgent || isIPadDesktopMode;
};

export const getInitialMode = () => {
  if (typeof window === "undefined") {
    return "report";
  }
  const stored = window.localStorage.getItem("pyrox.ui.last-mode");
  return VALID_MODES.has(stored) ? stored : "report";
};

export const DEEPDIVE_STAT_OPTIONS = [
  { value: "p05", label: "Top 5%" },
  { value: "podium", label: "Podium" },
  { value: "mean", label: "Mean" },
  { value: "p90", label: "Bottom 10%" },
];

export const RUN_SEGMENTS = [
  { key: "run1", label: "Run 1", color: "#38bdf8", column: "run1_time_min" },
  { key: "run2", label: "Run 2", color: "#22d3ee", column: "run2_time_min" },
  { key: "run3", label: "Run 3", color: "#0ea5e9", column: "run3_time_min" },
  { key: "run4", label: "Run 4", color: "#60a5fa", column: "run4_time_min" },
  { key: "run5", label: "Run 5", color: "#818cf8", column: "run5_time_min" },
  { key: "run6", label: "Run 6", color: "#a5b4fc", column: "run6_time_min" },
  { key: "run7", label: "Run 7", color: "#93c5fd", column: "run7_time_min" },
  { key: "run8", label: "Run 8", color: "#7dd3fc", column: "run8_time_min" },
  { key: "roxzone", label: "Roxzone", color: "#f97316", column: "roxzone_time_min" },
];

export const STATION_SEGMENTS = [
  { key: "skierg", label: "SkiErg", color: "#38bdf8", column: "skiErg_time_min" },
  { key: "sledpush", label: "Sled Push", color: "#22d3ee", column: "sledPush_time_min" },
  { key: "sledpull", label: "Sled Pull", color: "#f97316", column: "sledPull_time_min" },
  {
    key: "burpeebroadjump",
    label: "Burpee Broad Jump",
    color: "#facc15",
    column: "burpeeBroadJump_time_min",
  },
  { key: "rowerg", label: "RowErg", color: "#4ade80", column: "rowErg_time_min" },
  {
    key: "farmerscarry",
    label: "Farmers Carry",
    color: "#2dd4bf",
    column: "farmersCarry_time_min",
  },
  {
    key: "sandbaglunges",
    label: "Sandbag Lunges",
    color: "#fb7185",
    column: "sandbagLunges_time_min",
  },
  {
    key: "wallballs",
    label: "Wall Balls",
    color: "#a3e635",
    column: "wallBalls_time_min",
  },
];

export const DEEPDIVE_METRIC_OPTIONS = [
  { value: "total_time_min", label: "Total time" },
  { value: "work_time_min", label: "Total work" },
  { value: "run_time_min", label: "Total runs" },
  { value: "roxzone_time_min", label: "Roxzone" },
  ...RUN_SEGMENTS.filter((segment) => segment.key !== "roxzone").map((segment) => ({
    value: segment.column,
    label: segment.label,
  })),
  ...STATION_SEGMENTS.map((segment) => ({
    value: segment.column,
    label: segment.label,
  })),
];

export const RUN_PERCENTILE_SEGMENTS = RUN_SEGMENTS.map(({ key, label }) => ({ key, label }));
export const STATION_PERCENTILE_SEGMENTS = STATION_SEGMENTS.map(({ key, label }) => ({
  key,
  label,
}));
