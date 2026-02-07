import { useEffect, useMemo, useRef, useState } from "react";
import { Capacitor } from "@capacitor/core";
import html2pdf from "html2pdf.js";

const resolveApiBase = () => {
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
    // iOS simulator can reach the host machine on loopback.
    return "http://127.0.0.1:8000";
  }

  if (typeof window !== "undefined" && window.location?.hostname) {
    return `http://${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
};

const API_BASE = resolveApiBase();

const DEEPDIVE_STAT_OPTIONS = [
  { value: "p05", label: "Top 5%" },
  { value: "mean", label: "Mean" },
  { value: "p90", label: "Bottom 10%" },
];

const RUN_SEGMENTS = [
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

const STATION_SEGMENTS = [
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

const DEEPDIVE_METRIC_OPTIONS = [
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

const RUN_PERCENTILE_SEGMENTS = RUN_SEGMENTS.map(({ key, label }) => ({ key, label }));
const STATION_PERCENTILE_SEGMENTS = STATION_SEGMENTS.map(({ key, label }) => ({
  key,
  label,
}));

const formatMinutes = (value) => {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const minutesValue = Number(value);
  if (!Number.isFinite(minutesValue)) {
    return "-";
  }
  const totalSeconds = Math.max(0, Math.round(minutesValue * 60));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
};

const formatDurationMinutes = (value) => {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const minutesValue = Number(value);
  if (!Number.isFinite(minutesValue)) {
    return "-";
  }
  const totalSeconds = Math.round(Math.abs(minutesValue) * 60);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
};

const formatDeltaMinutes = (value) => {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const minutesValue = Number(value);
  if (!Number.isFinite(minutesValue)) {
    return "-";
  }
  const formatted = formatDurationMinutes(minutesValue);
  if (formatted === "-") {
    return "-";
  }
  if (minutesValue === 0) {
    return formatted;
  }
  return `${minutesValue > 0 ? "+" : "-"}${formatted}`;
};

const formatPercent = (value) => {
  const percentValue = Number(value);
  if (!Number.isFinite(percentValue)) {
    return "-";
  }
  return `${(percentValue * 100).toFixed(1)}%`;
};

const formatLabel = (value) => {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
};

const toNumber = (value) => {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }
    if (trimmed.includes(":")) {
      const parts = trimmed.split(":").map((part) => part.trim());
      if (parts.some((part) => part === "")) {
        return null;
      }
      const numbers = parts.map((part) => Number(part));
      if (numbers.some((number) => !Number.isFinite(number))) {
        return null;
      }
      if (numbers.length === 2) {
        const [minutes, seconds] = numbers;
        return minutes + seconds / 60;
      }
      if (numbers.length === 3) {
        const [hours, minutes, seconds] = numbers;
        return hours * 60 + minutes + seconds / 60;
      }
      return null;
    }
    const numberValue = Number(trimmed);
    return Number.isFinite(numberValue) ? numberValue : null;
  }
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : null;
};

const sumTimes = (...values) => {
  const numbers = values.map(toNumber);
  if (numbers.some((number) => number === null)) {
    return null;
  }
  return numbers.reduce((total, number) => total + number, 0);
};

const normalizeSplitKey = (value) => {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value).trim().toLowerCase().replace(/[^a-z0-9]+/g, "");
};

const buildSplitTimeMap = (splits) => {
  const map = new Map();
  if (!Array.isArray(splits)) {
    return map;
  }
  splits.forEach((split) => {
    const key = normalizeSplitKey(split.split_name);
    if (!key) {
      return;
    }
    map.set(key, {
      name: split.split_name,
      time: toNumber(split.split_time_min),
    });
  });
  return map;
};

const buildReportFilename = (race) => {
  const parts = [
    race?.name,
    race?.event_name || race?.event_id,
    race?.location,
    race?.season,
    race?.year,
  ]
    .filter(Boolean)
    .join("-");
  const slug = parts.replace(/[^a-z0-9]+/gi, "-").replace(/(^-|-$)/g, "").toLowerCase();
  return `pyrox-report-${slug || "race"}.pdf`;
};

const buildComparisonFilename = (baseRace, compareRace) => {
  const baseParts = [
    baseRace?.name,
    baseRace?.event_name || baseRace?.event_id,
    baseRace?.location,
    baseRace?.season,
    baseRace?.year,
  ]
    .filter(Boolean)
    .join("-");
  const compareParts = [
    compareRace?.name,
    compareRace?.event_name || compareRace?.event_id,
    compareRace?.location,
    compareRace?.season,
    compareRace?.year,
  ]
    .filter(Boolean)
    .join("-");
  const combined = [baseParts, compareParts].filter(Boolean).join("-vs-");
  const slug = combined
    .replace(/[^a-z0-9]+/gi, "-")
    .replace(/(^-|-$)/g, "")
    .toLowerCase();
  return `pyrox-compare-${slug || "races"}.pdf`;
};

const pickSegmentValue = (segment, race, splitMap) => {
  if (splitMap?.has(segment.key)) {
    const splitValue = splitMap.get(segment.key)?.time;
    if (Number.isFinite(splitValue)) {
      return splitValue;
    }
  }
  return toNumber(race?.[segment.column]);
};

const parseError = async (response) => {
  try {
    const data = await response.json();
    return data?.detail || response.statusText;
  } catch (error) {
    return response.statusText || "Request failed.";
  }
};

const HistogramChart = ({ title, subtitle, histogram, stats, emptyMessage, infoTooltip }) => {
  if (!histogram || !Array.isArray(histogram.bins) || histogram.bins.length === 0) {
    return (
      <div className="chart-card">
        <div className="chart-head">
          <div>
            <h5>
              {title}
              {infoTooltip ? (
                <span className="info-tooltip" data-tooltip={infoTooltip} aria-label={title}>
                  i
                </span>
              ) : null}
            </h5>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
        </div>
        <div className="empty">{emptyMessage || "No distribution data available."}</div>
      </div>
    );
  }

  const maxCount = Math.max(...histogram.bins.map((bin) => bin.count), 1);
  const totalCount = histogram.count || 1;
  const range = histogram.max - histogram.min;
  const athleteRaw = histogram.athlete_value;
  const athleteValue =
    athleteRaw === null || athleteRaw === undefined ? null : Number(athleteRaw);
  const hasAthleteValue = Number.isFinite(athleteValue);
  const athletePercentRaw = histogram.athlete_percentile;
  const athletePercentile =
    athletePercentRaw === null || athletePercentRaw === undefined
      ? null
      : Number(athletePercentRaw);
  const markerPercent =
    hasAthleteValue && range > 0
      ? Math.min(100, Math.max(0, ((athleteValue - histogram.min) / range) * 100))
      : null;
  const athletePercentLabel =
    hasAthleteValue && Number.isFinite(athletePercentile)
      ? formatPercent(athletePercentile)
      : null;
  const statItems = [];
  if (stats?.mean !== undefined && stats?.mean !== null) {
    statItems.push({ label: "Avg", value: formatMinutes(stats.mean) });
  }
  if (stats?.median !== undefined && stats?.median !== null) {
    statItems.push({ label: "Median", value: formatMinutes(stats.median) });
  }
  if (stats?.p10 !== undefined && stats?.p10 !== null) {
    statItems.push({ label: "P10", value: formatMinutes(stats.p10) });
  }
  if (stats?.p90 !== undefined && stats?.p90 !== null) {
    statItems.push({ label: "P90", value: formatMinutes(stats.p90) });
  }

  return (
    <div className="chart-card">
      <div className="chart-head">
        <div>
          <h5>
            {title}
            {infoTooltip ? (
              <span className="info-tooltip" data-tooltip={infoTooltip} aria-label={title}>
                i
              </span>
            ) : null}
          </h5>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        <div className="chart-stat">n={formatLabel(histogram.count)}</div>
      </div>
      <div className="chart-body">
        <div
          className="chart-bars"
          style={{
            gridTemplateColumns: `repeat(${histogram.bins.length}, minmax(0, 1fr))`,
          }}
        >
          {histogram.bins.map((bin, index) => {
            const percent = totalCount ? ((bin.count / totalCount) * 100).toFixed(1) : "0.0";
            const locations = Array.isArray(bin.locations) ? bin.locations : [];
            const locationLabel = locations.length
              ? ` | Locations: ${
                  locations.slice(0, 4).join(", ")
                }${locations.length > 4 ? ` +${locations.length - 4} more` : ""}`
              : "";
            const label = `${formatMinutes(bin.start)} - ${formatMinutes(bin.end)} | ${
              bin.count
            } (${percent}%)${locationLabel}`;
            return (
              <div
                key={`${bin.start}-${index}`}
                className="chart-bar"
                style={{ height: `${(bin.count / maxCount) * 100}%` }}
                data-label={label}
                aria-label={label}
              />
            );
          })}
        </div>
        {markerPercent !== null ? (
          <div className="chart-marker" style={{ left: `${markerPercent}%` }}>
            <span>
              Athlete {formatMinutes(athleteValue)}
              {athletePercentLabel ? ` • ${athletePercentLabel}` : ""}
            </span>
          </div>
        ) : null}
      </div>
      <div className="chart-axis">
        <span>{formatMinutes(histogram.min)}</span>
        <span>{formatMinutes(histogram.max)}</span>
      </div>
      {hasAthleteValue || statItems.length ? (
        <div className="chart-foot">
          {hasAthleteValue ? (
            <span>Athlete time: {formatMinutes(athleteValue)}</span>
          ) : null}
          {athletePercentLabel ? <span>{athletePercentLabel} percentile</span> : null}
          {statItems.map((item) => (
            <span key={item.label}>
              {item.label}: {item.value}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
};

const GroupedBarChart = ({
  title,
  subtitle,
  segments = [],
  baseLabel,
  compareLabel,
  emptyMessage,
}) => {
  const values = segments
    .flatMap((segment) => [segment.baseValue, segment.compareValue])
    .map((value) => (Number.isFinite(value) ? value : 0));
  const maxValue = Math.max(0, ...values);
  if (!segments.length || maxValue === 0) {
    return (
      <div className="chart-card compare-chart">
        <div className="chart-head">
          <div>
            <h5>{title}</h5>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
        </div>
        <div className="empty">{emptyMessage || "No data available."}</div>
      </div>
    );
  }

  const tickCount = 4;
  const maxScale = maxValue;
  const step = maxScale / tickCount;
  const ticks = Array.from({ length: tickCount + 1 }, (_, index) => maxScale - step * index);

  return (
    <div className="chart-card compare-chart">
      <div className="chart-head">
        <div>
          <h5>{title}</h5>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      </div>
      <div className="compare-legend">
        <span className="legend-item">
          <span className="legend-swatch is-base" />
          {baseLabel}
        </span>
        <span className="legend-item">
          <span className="legend-swatch is-compare" />
          {compareLabel}
        </span>
      </div>
      <div className="grouped-chart-wrap">
        <div className="grouped-axis">
          {ticks.map((tick, index) => (
            <div key={`${tick}-${index}`} className="grouped-axis-tick">
              {formatMinutes(tick)}
            </div>
          ))}
        </div>
        <div className="grouped-chart-area">
          <div className="grouped-chart-inner">
            <div className="grouped-grid">
              {ticks.map((tick, index) => {
                const position = (index / tickCount) * 100;
                return (
                  <div
                    key={`${tick}-${index}`}
                    className="grouped-grid-line"
                    style={{ bottom: `${100 - position}%` }}
                  />
                );
              })}
            </div>
            <div className="grouped-chart-bars">
              {segments.map((segment) => {
                const baseValue = Number.isFinite(segment.baseValue) ? segment.baseValue : 0;
                const compareValue = Number.isFinite(segment.compareValue)
                  ? segment.compareValue
                  : 0;
                const baseHeight = maxScale > 0 ? (baseValue / maxScale) * 100 : 0;
                const compareHeight = maxScale > 0 ? (compareValue / maxScale) * 100 : 0;
                return (
                  <div key={segment.key} className="grouped-group">
                    <div className="grouped-bars">
                      <div
                        className="grouped-bar is-base"
                        style={{ height: `${baseHeight}%`, background: segment.color }}
                        title={`${baseLabel} ${segment.label}: ${formatMinutes(baseValue)}`}
                        data-value={formatMinutes(baseValue)}
                        aria-label={`${segment.label} ${baseLabel}: ${formatMinutes(baseValue)}`}
                      />
                      <div
                        className="grouped-bar is-compare"
                        style={{ height: `${compareHeight}%`, background: segment.color }}
                        title={`${compareLabel} ${segment.label}: ${formatMinutes(compareValue)}`}
                        data-value={formatMinutes(compareValue)}
                        aria-label={`${segment.label} ${compareLabel}: ${formatMinutes(compareValue)}`}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="grouped-x-axis" />
            <div className="grouped-label-row">
              {segments.map((segment) => (
                <div key={`${segment.key}-label`} className="grouped-label">
                  {segment.label}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const StatBarChart = ({ title, subtitle, items = [], emptyMessage, infoTooltip }) => {
  const hasValues = items.some((item) => Number.isFinite(item.value));
  if (!items.length || !hasValues) {
    return (
      <div className="chart-card">
        <div className="chart-head">
          <div>
            <h5>
              {title}
              {infoTooltip ? (
                <span className="info-tooltip" data-tooltip={infoTooltip} aria-label={title}>
                  i
                </span>
              ) : null}
            </h5>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
        </div>
        <div className="empty">{emptyMessage || "No data available."}</div>
      </div>
    );
  }

  const values = items.map((item) => (Number.isFinite(item.value) ? item.value : 0));
  const maxValue = Math.max(0, ...values);

  return (
    <div className="chart-card stat-bar-chart">
      <div className="chart-head">
        <div>
          <h5>
            {title}
            {infoTooltip ? (
              <span className="info-tooltip" data-tooltip={infoTooltip} aria-label={title}>
                i
              </span>
            ) : null}
          </h5>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      </div>
      <div className="stat-bars">
        {items.map((item) => {
          const value = Number.isFinite(item.value) ? item.value : 0;
          const height = maxValue > 0 ? (value / maxValue) * 100 : 0;
          return (
            <div key={item.label} className="stat-bar-item">
              <div
                className={`stat-bar${item.accent ? " is-accent" : ""}${
                  Number.isFinite(item.value) ? "" : " is-empty"
                }`}
                style={{ height: `${height}%` }}
              >
                <span>{formatMinutes(item.value)}</span>
              </div>
              <div className="stat-bar-label">{item.label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const PercentileLineChart = ({ title, subtitle, series, emptyMessage }) => {
  const containerRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);
  const hasData = series.some(
    (item) => Number.isFinite(item.cohort) || Number.isFinite(item.window)
  );
  if (!series.length || !hasData) {
    return (
      <div className="chart-card">
        <div className="chart-head">
          <div>
            <h5>{title}</h5>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
        </div>
        <div className="empty">{emptyMessage || "No percentile data available."}</div>
      </div>
    );
  }

  const width = 360;
  const height = 220;
  const padding = { left: 38, right: 14, top: 16, bottom: 40 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const count = series.length;
  const xForIndex =
    count <= 1
      ? () => padding.left + chartWidth / 2
      : (index) => padding.left + (chartWidth * index) / (count - 1);
  const clampPercent = (value) => Math.min(100, Math.max(0, value));
  const yForValue = (value) =>
    padding.top + chartHeight - (clampPercent(value) / 100) * chartHeight;

  const buildPath = (field) => {
    let path = "";
    let started = false;
    series.forEach((item, index) => {
      const rawValue = item[field];
      if (!Number.isFinite(rawValue)) {
        started = false;
        return;
      }
      const x = xForIndex(index);
      const y = yForValue(rawValue);
      if (!started) {
        path += `M ${x} ${y}`;
        started = true;
      } else {
        path += ` L ${x} ${y}`;
      }
    });
    return path;
  };

  const splitLabel = (label) => {
    const parts = String(label).split(" ");
    if (parts.length <= 1) {
      return [label];
    }
    if (parts.length === 2) {
      return parts;
    }
    const mid = Math.ceil(parts.length / 2);
    return [parts.slice(0, mid).join(" "), parts.slice(mid).join(" ")];
  };

  const yTicks = [100, 50, 0];
  const formatPercentValue = (value) => {
    if (!Number.isFinite(value)) {
      return "-";
    }
    return `${value.toFixed(1)}%`;
  };
  const showTooltip = (event, text) => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    const rect = container.getBoundingClientRect();
    setTooltip({
      text,
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    });
  };
  const clearTooltip = () => setTooltip(null);

  return (
    <div className="chart-card percentile-chart">
      <div className="chart-head">
        <div>
          <h5>{title}</h5>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      </div>
      <div className="percentile-legend">
        <span className="legend-item">
          <span className="legend-line is-cohort" />
          Age group percentile
        </span>
        <span className="legend-item">
          <span className="legend-line is-window" />
          Time window percentile
        </span>
      </div>
      <div className="percentile-chart-wrap" ref={containerRef} onMouseLeave={clearTooltip}>
        <svg className="percentile-svg" viewBox={`0 0 ${width} ${height}`} role="img">
          <g className="percentile-grid">
            {yTicks.map((tick) => {
              const y = yForValue(tick);
              return (
                <line
                  key={`grid-${tick}`}
                  x1={padding.left}
                  x2={width - padding.right}
                  y1={y}
                  y2={y}
                />
              );
            })}
          </g>
          <g className="percentile-axis">
            <line
              x1={padding.left}
              x2={padding.left}
              y1={padding.top}
              y2={height - padding.bottom}
            />
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={height - padding.bottom}
              y2={height - padding.bottom}
            />
          </g>
          <g className="percentile-axis-labels">
            {yTicks.map((tick) => {
              const y = yForValue(tick);
              return (
                <text key={`label-${tick}`} x={padding.left - 6} y={y + 4} textAnchor="end">
                  {tick}
                </text>
              );
            })}
          </g>
          <path
            className="percentile-line is-cohort"
            d={buildPath("cohort")}
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            className="percentile-line is-window"
            d={buildPath("window")}
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {series.map((item, index) => {
            const x = xForIndex(index);
            const cohortValue = Number.isFinite(item.cohort) ? item.cohort : null;
            const windowValue = Number.isFinite(item.window) ? item.window : null;
            return (
              <g key={`points-${item.label}`}>
                {cohortValue !== null ? (
                  <g>
                    <circle
                      className="percentile-hit"
                      cx={x}
                      cy={yForValue(cohortValue)}
                      r="10"
                      onMouseMove={(event) =>
                        showTooltip(
                          event,
                          `${item.label} age group: ${formatPercentValue(cohortValue)}`
                        )
                      }
                    />
                    <circle
                      className="percentile-point is-cohort"
                      cx={x}
                      cy={yForValue(cohortValue)}
                      r="3.5"
                    />
                  </g>
                ) : null}
                {windowValue !== null ? (
                  <g>
                    <circle
                      className="percentile-hit"
                      cx={x}
                      cy={yForValue(windowValue)}
                      r="10"
                      onMouseMove={(event) =>
                        showTooltip(
                          event,
                          `${item.label} window: ${formatPercentValue(windowValue)}`
                        )
                      }
                    />
                    <circle
                      className="percentile-point is-window"
                      cx={x}
                      cy={yForValue(windowValue)}
                      r="3.5"
                    />
                  </g>
                ) : null}
              </g>
            );
          })}
          <g className="percentile-axis-labels">
            {series.map((item, index) => {
              const x = xForIndex(index);
              const lines = splitLabel(item.label);
              const firstLineY = height - 14 - (lines.length - 1) * 10;
              return (
                <text key={`x-${item.label}`} x={x} y={firstLineY} textAnchor="middle">
                  {lines.map((line, lineIndex) => (
                    <tspan key={`${item.label}-${lineIndex}`} x={x} dy={lineIndex ? 10 : 0}>
                      {line}
                    </tspan>
                  ))}
                </text>
              );
            })}
          </g>
        </svg>
        {tooltip ? (
          <div className="percentile-tooltip" style={{ left: tooltip.x, top: tooltip.y }}>
            {tooltip.text}
          </div>
        ) : null}
      </div>
    </div>
  );
};

const ProgressiveSection = ({ enabled, summary, children, defaultOpen = false }) => {
  if (!enabled) {
    return <>{children}</>;
  }
  return (
    <details className="form-advanced" open={defaultOpen}>
      <summary>{summary}</summary>
      <div className="form-advanced-content">{children}</div>
    </details>
  );
};

const ModeTabIcon = ({ kind }) => {
  if (kind === "report") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="4" y="4" width="16" height="16" rx="4" />
        <path d="M8 9h8" />
        <path d="M8 13h8" />
        <path d="M8 17h5" />
      </svg>
    );
  }
  if (kind === "compare") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 7h6v12H5z" />
        <path d="M13 5h6v14h-6z" />
      </svg>
    );
  }
  if (kind === "deepdive") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="11" cy="11" r="6" />
        <path d="M15.5 15.5L20 20" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 18h14" />
      <path d="M7 18v-6" />
      <path d="M12 18v-10" />
      <path d="M17 18v-4" />
    </svg>
  );
};

export default function App() {
  const platform = Capacitor.getPlatform ? Capacitor.getPlatform() : "web";
  const isNativeApp = Capacitor.isNativePlatform
    ? Capacitor.isNativePlatform()
    : platform !== "web";
  const isIosPlatform = platform === "ios";
  const [isIosMobile, setIsIosMobile] = useState(() => {
    if (!isIosPlatform || typeof window === "undefined") {
      return false;
    }
    return window.matchMedia("(max-width: 900px)").matches;
  });
  const [mode, setMode] = useState("report");
  const [name, setName] = useState("");
  const [filters, setFilters] = useState({
    match: "best",
    gender: "",
    division: "",
    nationality: "",
    requireUnique: false,
    timeWindow: "5",
  });
  const [races, setRaces] = useState([]);
  const [selectedRaceId, setSelectedRaceId] = useState(null);
  const [report, setReport] = useState(null);
  const [selectedSplit, setSelectedSplit] = useState("");
  const [view, setView] = useState("search");
  const [searchLoading, setSearchLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [reportError, setReportError] = useState("");

  const [baseName, setBaseName] = useState("");
  const [baseFilters, setBaseFilters] = useState({
    match: "best",
    gender: "",
    division: "",
    nationality: "",
    requireUnique: false,
  });
  const [baseRaces, setBaseRaces] = useState([]);
  const [selectedBaseRaceId, setSelectedBaseRaceId] = useState(null);
  const [baseReport, setBaseReport] = useState(null);
  const [baseSearchLoading, setBaseSearchLoading] = useState(false);
  const [baseReportLoading, setBaseReportLoading] = useState(false);
  const [baseSearchError, setBaseSearchError] = useState("");
  const [baseReportError, setBaseReportError] = useState("");

  const [compareName, setCompareName] = useState("");
  const [compareFilters, setCompareFilters] = useState({
    match: "best",
    gender: "",
    division: "",
    nationality: "",
    requireUnique: false,
  });
  const [compareRaces, setCompareRaces] = useState([]);
  const [selectedCompareRaceId, setSelectedCompareRaceId] = useState(null);
  const [compareReport, setCompareReport] = useState(null);
  const [compareSearchLoading, setCompareSearchLoading] = useState(false);
  const [compareReportLoading, setCompareReportLoading] = useState(false);
  const [compareSearchError, setCompareSearchError] = useState("");
  const [compareReportError, setCompareReportError] = useState("");

  const [deepdiveName, setDeepdiveName] = useState("");
  const [deepdiveFilters, setDeepdiveFilters] = useState({
    match: "best",
    division: "",
    gender: "",
    nationality: "",
    requireUnique: false,
  });
  const [deepdiveRaces, setDeepdiveRaces] = useState([]);
  const [selectedDeepdiveRaceId, setSelectedDeepdiveRaceId] = useState(null);
  const [deepdiveData, setDeepdiveData] = useState(null);
  const [deepdiveSearchLoading, setDeepdiveSearchLoading] = useState(false);
  const [deepdiveLoading, setDeepdiveLoading] = useState(false);
  const [deepdiveSearchError, setDeepdiveSearchError] = useState("");
  const [deepdiveError, setDeepdiveError] = useState("");
  const [deepdiveOptions, setDeepdiveOptions] = useState({
    locations: [],
    ageGroups: [],
  });
  const [deepdiveOptionsLoading, setDeepdiveOptionsLoading] = useState(false);
  const [deepdiveParams, setDeepdiveParams] = useState({
    season: "",
    division: "",
    gender: "",
    ageGroup: "",
    location: "",
    metric: "total_time_min",
    stat: "p05",
  });

  const [plannerFilters, setPlannerFilters] = useState({
    season: "",
    location: "",
    year: "",
    division: "",
    gender: "",
    minTime: "",
    maxTime: "",
  });
  const [plannerData, setPlannerData] = useState(null);
  const [plannerLoading, setPlannerLoading] = useState(false);
  const [plannerError, setPlannerError] = useState("");

  const selectedRace = useMemo(
    () => races.find((race) => race.result_id === selectedRaceId),
    [races, selectedRaceId]
  );
  const selectedBaseRace = useMemo(
    () => baseRaces.find((race) => race.result_id === selectedBaseRaceId),
    [baseRaces, selectedBaseRaceId]
  );
  const selectedCompareRace = useMemo(
    () => compareRaces.find((race) => race.result_id === selectedCompareRaceId),
    [compareRaces, selectedCompareRaceId]
  );
  const selectedDeepdiveRace = useMemo(
    () => deepdiveRaces.find((race) => race.result_id === selectedDeepdiveRaceId),
    [deepdiveRaces, selectedDeepdiveRaceId]
  );
  const splitOptions = useMemo(() => {
    if (!report?.splits || report.splits.length === 0) {
      return [];
    }
    const names = report.splits
      .map((split) => split.split_name)
      .filter((value) => value !== null && value !== undefined && value !== "");
    return Array.from(new Set(names));
  }, [report]);

  const plannerSegments = plannerData?.segments || [];
  const plannerGroups = useMemo(() => {
    const groups = {
      overall: [],
      runs: [],
      stations: [],
    };
    plannerSegments.forEach((segment) => {
      if (groups[segment.group]) {
        groups[segment.group].push(segment);
      }
    });
    return groups;
  }, [plannerSegments]);

  const plannerTags = useMemo(() => {
    if (!plannerData?.filters) {
      return [];
    }
    const tags = [];
    if (plannerData.filters.season) {
      tags.push(`Season ${plannerData.filters.season}`);
    }
    if (plannerData.filters.location) {
      tags.push(`Location ${plannerData.filters.location}`);
    }
    if (plannerData.filters.year) {
      tags.push(`Year ${plannerData.filters.year}`);
    }
    if (plannerData.filters.division) {
      tags.push(`Division ${plannerData.filters.division}`);
    }
    if (plannerData.filters.gender) {
      tags.push(`Gender ${plannerData.filters.gender}`);
    }
    if (plannerData.filters.min_total_time || plannerData.filters.max_total_time) {
      const minLabel = plannerData.filters.min_total_time ?? "-";
      const maxLabel = plannerData.filters.max_total_time ?? "-";
      tags.push(`Total time ${minLabel}-${maxLabel} min`);
    }
    return tags;
  }, [plannerData]);

  useEffect(() => {
    if (!isIosPlatform || typeof window === "undefined") {
      setIsIosMobile(false);
      return;
    }
    const mediaQuery = window.matchMedia("(max-width: 900px)");
    const updateIsIosMobile = () => {
      setIsIosMobile(mediaQuery.matches);
    };
    updateIsIosMobile();
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", updateIsIosMobile);
      return () => mediaQuery.removeEventListener("change", updateIsIosMobile);
    }
    mediaQuery.addListener(updateIsIosMobile);
    return () => mediaQuery.removeListener(updateIsIosMobile);
  }, [isIosPlatform]);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }
    document.body.classList.toggle("ios-mobile", isIosMobile);
    return () => {
      document.body.classList.remove("ios-mobile");
    };
  }, [isIosMobile]);

  const handleSearch = async (event) => {
    event.preventDefault();
    if (!name.trim()) {
      setSearchError("Enter an athlete name to search.");
      return;
    }
    setSearchLoading(true);
    setSearchError("");
    setReportError("");
    setReport(null);
    setSelectedSplit("");
    setSelectedRaceId(null);
    setView("search");
    try {
      const params = new URLSearchParams({
        name: name.trim(),
        match: filters.match,
        require_unique: String(filters.requireUnique),
      });
      if (filters.gender.trim()) {
        params.set("gender", filters.gender.trim());
      }
      if (filters.division.trim()) {
        params.set("division", filters.division.trim());
      }
      if (filters.nationality.trim()) {
        params.set("nationality", filters.nationality.trim());
      }
      const response = await fetch(`${API_BASE}/api/athletes/search?${params.toString()}`);
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      const payload = await response.json();
      setRaces(payload.races || []);
    } catch (error) {
      setSearchError(error.message || "Search failed.");
      setRaces([]);
    } finally {
      setSearchLoading(false);
    }
  };

  const handleGenerateReport = async (splitOverride) => {
    if (!selectedRace) {
      setReportError("Pick a race before generating a report.");
      return;
    }
    setReportLoading(true);
    setReportError("");
    try {
      const params = new URLSearchParams();
      if (filters.timeWindow.trim()) {
        params.set("cohort_time_window_min", filters.timeWindow.trim());
      }
      const splitName = typeof splitOverride === "string" ? splitOverride : selectedSplit;
      if (splitName && splitName.trim()) {
        params.set("split_name", splitName.trim());
      }
      const response = await fetch(
        `${API_BASE}/api/reports/${selectedRace.result_id}?${params.toString()}`
      );
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      const payload = await response.json();
      setReport(payload);
      setView("report");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      setReportError(error.message || "Report generation failed.");
    } finally {
      setReportLoading(false);
    }
  };

  const handleBaseSearch = async (event) => {
    event.preventDefault();
    if (!baseName.trim()) {
      setBaseSearchError("Enter an athlete name to search.");
      return;
    }
    setBaseSearchLoading(true);
    setBaseSearchError("");
    setBaseReportError("");
    setBaseReport(null);
    setSelectedBaseRaceId(null);
    try {
      const params = new URLSearchParams({
        name: baseName.trim(),
        match: baseFilters.match,
        require_unique: String(baseFilters.requireUnique),
      });
      if (baseFilters.gender.trim()) {
        params.set("gender", baseFilters.gender.trim());
      }
      if (baseFilters.division.trim()) {
        params.set("division", baseFilters.division.trim());
      }
      if (baseFilters.nationality.trim()) {
        params.set("nationality", baseFilters.nationality.trim());
      }
      const response = await fetch(`${API_BASE}/api/athletes/search?${params.toString()}`);
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      const payload = await response.json();
      setBaseRaces(payload.races || []);
    } catch (error) {
      setBaseSearchError(error.message || "Search failed.");
      setBaseRaces([]);
    } finally {
      setBaseSearchLoading(false);
    }
  };

  const handleLoadBaseReport = async () => {
    if (!selectedBaseRace) {
      setBaseReportError("Pick a base race to compare.");
      return;
    }
    setBaseReportLoading(true);
    setBaseReportError("");
    try {
      const response = await fetch(`${API_BASE}/api/reports/${selectedBaseRace.result_id}`);
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      const payload = await response.json();
      setBaseReport(payload);
    } catch (error) {
      setBaseReportError(error.message || "Base report failed.");
      setBaseReport(null);
    } finally {
      setBaseReportLoading(false);
    }
  };

  const handleCompareSearch = async (event) => {
    event.preventDefault();
    if (!compareName.trim()) {
      setCompareSearchError("Enter an athlete name to search.");
      return;
    }
    setCompareSearchLoading(true);
    setCompareSearchError("");
    setCompareReportError("");
    setCompareReport(null);
    setCompareRaces([]);
    setSelectedCompareRaceId(null);
    try {
      const params = new URLSearchParams({
        name: compareName.trim(),
        match: compareFilters.match,
        require_unique: String(compareFilters.requireUnique),
      });
      if (compareFilters.gender.trim()) {
        params.set("gender", compareFilters.gender.trim());
      }
      if (compareFilters.division.trim()) {
        params.set("division", compareFilters.division.trim());
      }
      if (compareFilters.nationality.trim()) {
        params.set("nationality", compareFilters.nationality.trim());
      }
      const response = await fetch(`${API_BASE}/api/athletes/search?${params.toString()}`);
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      const payload = await response.json();
      setCompareRaces(payload.races || []);
    } catch (error) {
      setCompareSearchError(error.message || "Search failed.");
      setCompareRaces([]);
    } finally {
      setCompareSearchLoading(false);
    }
  };

  const handleLoadCompareReport = async () => {
    if (!selectedCompareRace) {
      setCompareReportError("Pick a race to compare against.");
      return;
    }
    if (selectedBaseRaceId && selectedCompareRaceId === selectedBaseRaceId) {
      setCompareReportError("Pick a different race than the base race.");
      return;
    }
    setCompareReportLoading(true);
    setCompareReportError("");
    try {
      const response = await fetch(
        `${API_BASE}/api/reports/${selectedCompareRace.result_id}`
      );
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      const payload = await response.json();
      setCompareReport(payload);
    } catch (error) {
      setCompareReportError(error.message || "Comparison report failed.");
      setCompareReport(null);
    } finally {
      setCompareReportLoading(false);
    }
  };

  const handleDeepdiveSearch = async (event) => {
    event.preventDefault();
    if (!deepdiveName.trim()) {
      setDeepdiveSearchError("Enter an athlete name to search.");
      return;
    }
    setDeepdiveSearchLoading(true);
    setDeepdiveSearchError("");
    setDeepdiveError("");
    setDeepdiveData(null);
    setDeepdiveRaces([]);
    setSelectedDeepdiveRaceId(null);
    try {
      const params = new URLSearchParams({
        name: deepdiveName.trim(),
        match: deepdiveFilters.match,
        require_unique: String(deepdiveFilters.requireUnique),
      });
      if (deepdiveFilters.gender.trim()) {
        params.set("gender", deepdiveFilters.gender.trim());
      }
      if (deepdiveFilters.division.trim()) {
        params.set("division", deepdiveFilters.division.trim());
      }
      if (deepdiveFilters.nationality.trim()) {
        params.set("nationality", deepdiveFilters.nationality.trim());
      }
      const response = await fetch(`${API_BASE}/api/athletes/search?${params.toString()}`);
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      const payload = await response.json();
      setDeepdiveRaces(payload.races || []);
    } catch (error) {
      setDeepdiveSearchError(error.message || "Search failed.");
      setDeepdiveRaces([]);
    } finally {
      setDeepdiveSearchLoading(false);
    }
  };

  const handleRunDeepdive = async () => {
    if (!selectedDeepdiveRace) {
      setDeepdiveError("Pick a base race for the deepdive.");
      return;
    }
    if (!deepdiveParams.season.trim()) {
      setDeepdiveError("Season is required for deepdive analysis.");
      return;
    }
    setDeepdiveLoading(true);
    setDeepdiveError("");
    try {
      const params = new URLSearchParams({
        season: deepdiveParams.season.trim(),
      });
      if (deepdiveParams.metric.trim()) {
        params.set("metric", deepdiveParams.metric.trim());
      }
      if (deepdiveParams.division.trim()) {
        params.set("division", deepdiveParams.division.trim());
      }
      if (deepdiveParams.gender.trim()) {
        params.set("gender", deepdiveParams.gender.trim());
      }
      if (deepdiveParams.ageGroup.trim()) {
        params.set("age_group", deepdiveParams.ageGroup.trim());
      }
      if (deepdiveParams.location.trim()) {
        params.set("location", deepdiveParams.location.trim());
      }
      const response = await fetch(
        `${API_BASE}/api/deepdive/${selectedDeepdiveRace.result_id}?${params.toString()}`
      );
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      const payload = await response.json();
      setDeepdiveData(payload);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      setDeepdiveError(error.message || "Deepdive analysis failed.");
      setDeepdiveData(null);
    } finally {
      setDeepdiveLoading(false);
    }
  };

  const handlePlannerSearch = async (event) => {
    event.preventDefault();
    setPlannerLoading(true);
    setPlannerError("");
    try {
      const params = new URLSearchParams();
      if (plannerFilters.season.trim()) {
        params.set("season", plannerFilters.season.trim());
      }
      if (plannerFilters.location.trim()) {
        params.set("location", plannerFilters.location.trim());
      }
      if (plannerFilters.year.trim()) {
        params.set("year", plannerFilters.year.trim());
      }
      if (plannerFilters.division.trim()) {
        params.set("division", plannerFilters.division.trim());
      }
      if (plannerFilters.gender.trim()) {
        params.set("gender", plannerFilters.gender.trim());
      }
      if (plannerFilters.minTime.trim()) {
        params.set("min_total_time", plannerFilters.minTime.trim());
      }
      if (plannerFilters.maxTime.trim()) {
        params.set("max_total_time", plannerFilters.maxTime.trim());
      }
      const response = await fetch(`${API_BASE}/api/planner?${params.toString()}`);
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      const payload = await response.json();
      setPlannerData(payload);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      setPlannerError(error.message || "Planner query failed.");
      setPlannerData(null);
    } finally {
      setPlannerLoading(false);
    }
  };

  const handleDownloadPdf = () => {
    const reportNode = document.getElementById("report-root");
    if (!reportNode) {
      return;
    }
    const options = {
      margin: 0.35,
      filename: buildReportFilename(report?.race),
      image: { type: "jpeg", quality: 0.95 },
      html2canvas: { scale: 2, useCORS: true },
      jsPDF: { unit: "in", format: "letter", orientation: "portrait" },
    };
    html2pdf().set(options).from(reportNode).save();
  };

  const handleDownloadComparePdf = () => {
    const compareNode = document.getElementById("compare-root");
    if (!compareNode) {
      return;
    }
    const options = {
      margin: 0.35,
      filename: buildComparisonFilename(baseReport?.race, compareReport?.race),
      image: { type: "jpeg", quality: 0.95 },
      html2canvas: { scale: 2, useCORS: true },
      jsPDF: { unit: "in", format: "letter", orientation: "portrait" },
    };
    html2pdf().set(options).from(compareNode).save();
  };

  const handleSplitChange = (event) => {
    const nextSplit = event.target.value;
    setSelectedSplit(nextSplit);
    if (report) {
      handleGenerateReport(nextSplit);
    }
  };

  const handleBackToSearch = () => {
    setView("search");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleModeChange = (nextMode) => {
    setMode(nextMode);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const cohortStats = report?.cohort_stats;
  const windowStats = report?.cohort_time_window_stats;
  const distributions = report?.distributions;
  const selectedSplitDistribution = distributions?.selected_split;
  const selectedSplitLabel = selectedSplit ? selectedSplit : "Select station";
  const windowLabel =
    report?.cohort_time_window_min !== null && report?.cohort_time_window_min !== undefined
      ? ` (+/- ${report.cohort_time_window_min} min)`
      : "";
  const comparisonRows = useMemo(() => {
    if (!baseReport || !compareReport) {
      return [];
    }
    const rows = [];
    const mainRace = baseReport.race || {};
    const compareRace = compareReport.race || {};
    const addRow = (label, primaryValue, compareValue, key) => {
      rows.push({
        key: key || label,
        label,
        primaryValue,
        compareValue,
        delta:
          primaryValue !== null && compareValue !== null
            ? primaryValue - compareValue
            : null,
      });
    };

    addRow(
      "Total time",
      toNumber(mainRace.total_time_min),
      toNumber(compareRace.total_time_min),
      "total_time"
    );
    addRow(
      "Run + Roxzone",
      sumTimes(mainRace.run_time_min, mainRace.roxzone_time_min),
      sumTimes(compareRace.run_time_min, compareRace.roxzone_time_min),
      "run_roxzone"
    );

    const mainSplits = buildSplitTimeMap(baseReport.splits);
    const compareSplits = buildSplitTimeMap(compareReport.splits);
    const splitKeys = new Set([...mainSplits.keys(), ...compareSplits.keys()]);
    const sortedKeys = Array.from(splitKeys).sort((left, right) => {
      const leftName = mainSplits.get(left)?.name || compareSplits.get(left)?.name || left;
      const rightName =
        mainSplits.get(right)?.name || compareSplits.get(right)?.name || right;
      return String(leftName).localeCompare(String(rightName));
    });

    sortedKeys.forEach((key) => {
      const mainSplit = mainSplits.get(key);
      const compareSplit = compareSplits.get(key);
      const label = mainSplit?.name || compareSplit?.name || key;
      addRow(label, mainSplit?.time ?? null, compareSplit?.time ?? null, `split-${key}`);
    });

    return rows;
  }, [baseReport, compareReport]);

  const comparisonCharts = useMemo(() => {
    if (!baseReport || !compareReport) {
      return null;
    }
    const baseRace = baseReport.race || {};
    const compareRace = compareReport.race || {};
    const baseSplits = buildSplitTimeMap(baseReport.splits);
    const compareSplits = buildSplitTimeMap(compareReport.splits);

    const runSegments = RUN_SEGMENTS.map((segment) => ({
      key: segment.key,
      label: segment.label,
      color: segment.color,
      baseValue: pickSegmentValue(segment, baseRace, baseSplits) ?? 0,
      compareValue: pickSegmentValue(segment, compareRace, compareSplits) ?? 0,
    }));

    const stationSegments = STATION_SEGMENTS.map((segment) => ({
      key: segment.key,
      label: segment.label,
      color: segment.color,
      baseValue: pickSegmentValue(segment, baseRace, baseSplits) ?? 0,
      compareValue: pickSegmentValue(segment, compareRace, compareSplits) ?? 0,
    }));

    return {
      runSegments,
      stationSegments,
    };
  }, [baseReport, compareReport]);

  const deepdiveStatLabel = useMemo(() => {
    const match = DEEPDIVE_STAT_OPTIONS.find((option) => option.value === deepdiveParams.stat);
    return match ? match.label : "Top 5%";
  }, [deepdiveParams.stat]);

  const deepdiveMetricLabel = useMemo(() => {
    const metricKey = deepdiveData?.metric || deepdiveParams.metric;
    const match = DEEPDIVE_METRIC_OPTIONS.find((option) => option.value === metricKey);
    return match ? match.label : "Total time";
  }, [deepdiveData, deepdiveParams.metric]);

  const deepdiveGroupSummary = useMemo(() => {
    const groupSummary = deepdiveData?.group_summary || {};
    if (deepdiveParams.stat === "mean") {
      return deepdiveData?.summary || null;
    }
    return groupSummary[deepdiveParams.stat] || null;
  }, [deepdiveData, deepdiveParams.stat]);

  const deepdiveDistribution = useMemo(() => {
    const groupDistribution = deepdiveData?.group_distribution || {};
    return groupDistribution[deepdiveParams.stat] || deepdiveData?.distribution || null;
  }, [deepdiveData, deepdiveParams.stat]);

  const deepdiveRows = useMemo(() => {
    if (!deepdiveData?.locations || !Array.isArray(deepdiveData.locations)) {
      return [];
    }
    const athleteTime = toNumber(
      deepdiveData.athlete_value ?? deepdiveData.athlete_time
    );
    const statKey = deepdiveParams.stat;
    const rows = deepdiveData.locations.map((row) => {
      const statValue = toNumber(row?.[statKey]);
      const delta =
        athleteTime !== null && statValue !== null ? athleteTime - statValue : null;
      const fastestValue = toNumber(row?.fastest);
      const deltaFastest =
        athleteTime !== null && fastestValue !== null
          ? athleteTime - fastestValue
          : null;
      return {
        location: row?.location,
        count: row?.count,
        seasons: row?.seasons,
        years: row?.years,
        statValue,
        delta,
        fastestValue,
        deltaFastest,
      };
    });
    return rows.sort((left, right) => {
      if (left.delta === null && right.delta === null) {
        return 0;
      }
      if (left.delta === null) {
        return 1;
      }
      if (right.delta === null) {
        return -1;
      }
      return left.delta - right.delta;
    });
  }, [deepdiveData, deepdiveParams.stat]);

  useEffect(() => {
    const season = deepdiveParams.season.trim();
    if (!season) {
      setDeepdiveOptions({ locations: [], ageGroups: [] });
      return;
    }
    const controller = new AbortController();
    const loadOptions = async () => {
      setDeepdiveOptionsLoading(true);
      try {
        const params = new URLSearchParams({ season });
        if (deepdiveParams.division.trim()) {
          params.set("division", deepdiveParams.division.trim());
        }
        if (deepdiveParams.gender.trim()) {
          params.set("gender", deepdiveParams.gender.trim());
        }
        const response = await fetch(
          `${API_BASE}/api/deepdive/filters?${params.toString()}`,
          { signal: controller.signal }
        );
        if (!response.ok) {
          throw new Error(await parseError(response));
        }
        const payload = await response.json();
        const locations = Array.isArray(payload.locations) ? payload.locations : [];
        const ageGroups = Array.isArray(payload.age_groups) ? payload.age_groups : [];
        setDeepdiveOptions({ locations, ageGroups });
        setDeepdiveParams((prev) => ({
          ...prev,
          location:
            prev.location && !locations.includes(prev.location) ? "" : prev.location,
          ageGroup:
            prev.ageGroup && !ageGroups.includes(prev.ageGroup) ? "" : prev.ageGroup,
        }));
      } catch (error) {
        if (error.name !== "AbortError") {
          setDeepdiveOptions({ locations: [], ageGroups: [] });
        }
      } finally {
        setDeepdiveOptionsLoading(false);
      }
    };
    loadOptions();
    return () => controller.abort();
  }, [deepdiveParams.season, deepdiveParams.division, deepdiveParams.gender]);

  const percentileSeries = useMemo(() => {
    if (!report?.splits || report.splits.length === 0) {
      return { runs: [], stations: [] };
    }
    const splitMap = new Map();
    report.splits.forEach((split) => {
      const key = normalizeSplitKey(split.split_name);
      if (!key) {
        return;
      }
      splitMap.set(key, {
        cohort: toNumber(split.split_percentile),
        window: toNumber(split.split_percentile_time_window),
      });
    });
    const toPercent = (value) =>
      Number.isFinite(value) ? Math.min(100, Math.max(0, value * 100)) : null;
    const runs = RUN_PERCENTILE_SEGMENTS.map((segment) => {
      const values = splitMap.get(segment.key);
      return {
        label: segment.label,
        cohort: toPercent(values?.cohort),
        window: toPercent(values?.window),
      };
    });
    const stations = STATION_PERCENTILE_SEGMENTS.map((segment) => {
      const values = splitMap.get(segment.key);
      return {
        label: segment.label,
        cohort: toPercent(values?.cohort),
        window: toPercent(values?.window),
      };
    });
    return { runs, stations };
  }, [report]);

  return (
    <div className={`app${isIosMobile ? " ios-mobile-shell" : ""}`}>
      <header className="hero">
        <div className="hero-tag">Pyrox Race Analysis Studio</div>
        <h1>Find an athlete, pick a race, and build a Pyrox race report.</h1>
        <p>
          Search the Hyrox race database, review races, and generate a report.
          {!isNativeApp ? " PDF export is available on desktop." : null}
        </p>
      </header>

      <div className="mode-tabs">
        <button
          type="button"
          className={`mode-tab ${mode === "report" ? "is-active" : ""}`}
          onClick={() => handleModeChange("report")}
        >
          <span className="mode-tab-icon">
            <ModeTabIcon kind="report" />
          </span>
          <span className="mode-tab-label">Race Report</span>
        </button>
        <button
          type="button"
          className={`mode-tab ${mode === "compare" ? "is-active" : ""}`}
          onClick={() => handleModeChange("compare")}
        >
          <span className="mode-tab-icon">
            <ModeTabIcon kind="compare" />
          </span>
          <span className="mode-tab-label">Compare</span>
        </button>
        <button
          type="button"
          className={`mode-tab ${mode === "deepdive" ? "is-active" : ""}`}
          onClick={() => handleModeChange("deepdive")}
        >
          <span className="mode-tab-icon">
            <ModeTabIcon kind="deepdive" />
          </span>
          <span className="mode-tab-label">Deep Dive</span>
        </button>
        <button
          type="button"
          className={`mode-tab ${mode === "planner" ? "is-active" : ""}`}
          onClick={() => handleModeChange("planner")}
        >
          <span className="mode-tab-icon">
            <ModeTabIcon kind="planner" />
          </span>
          <span className="mode-tab-label">Race Planner</span>
        </button>
      </div>

      {mode === "report" ? (
        view === "search" ? (
          <main className="layout is-single">
            <section className="panel">
              <form className="search-form" onSubmit={handleSearch}>
                <label className="field">
                  <span>Athlete name</span>
                  <input
                    type="text"
                    placeholder="Athlete Name"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                  />
                </label>

                <ProgressiveSection enabled={isIosMobile} summary="More search filters">
                  <div className="grid-2">
                    <label className="field">
                      <span>Division</span>
                      <input
                        type="text"
                        placeholder="open, pro, doubles"
                        value={filters.division}
                        onChange={(event) =>
                          setFilters((prev) => ({ ...prev, division: event.target.value }))
                        }
                      />
                    </label>

                    <label className="field">
                      <span>Gender</span>
                      <input
                        type="text"
                        placeholder="male or female or mixed"
                        value={filters.gender}
                        onChange={(event) =>
                          setFilters((prev) => ({ ...prev, gender: event.target.value }))
                        }
                      />
                    </label>
                  </div>

                  <label className="field">
                    <span>Nationality</span>
                    <input
                      type="text"
                      placeholder="GBR"
                      value={filters.nationality}
                      onChange={(event) =>
                        setFilters((prev) => ({ ...prev, nationality: event.target.value }))
                      }
                    />
                  </label>
                </ProgressiveSection>

                <button className="primary" type="submit" disabled={searchLoading}>
                  {searchLoading ? "Searching..." : "Search races"}
                </button>
                {searchError ? <p className="error">{searchError}</p> : null}
              </form>

              <div className="results">
                <div className="results-header">
                  <h2>Races</h2>
                  <span>{races.length ? `${races.length} matches` : "No results yet"}</span>
                </div>
                {races.length === 0 ? (
                  <div className="empty">Search for an athlete to see their races here.</div>
                ) : (
                  <div className="results-grid">
                    {races.map((race, index) => (
                      <button
                        key={race.result_id || `${race.event_id}-${index}`}
                        type="button"
                        className={`race-card ${
                          race.result_id === selectedRaceId ? "is-selected" : ""
                        }`}
                        style={{ animationDelay: `${index * 0.04}s` }}
                        onClick={() => {
                          setSelectedRaceId(race.result_id);
                          setReport(null);
                          setReportError("");
                          setSelectedSplit("");
                        }}
                      >
                        <div className="race-card-header">
                          <span className="race-title">
                            {race.event_name || race.event_id || "Race"}
                          </span>
                          <span className="race-location">{formatLabel(race.location)}</span>
                        </div>
                        <div className="race-meta">
                          <span>Season {formatLabel(race.season)}</span>
                          <span>{formatLabel(race.year)}</span>
                          <span>{formatLabel(race.division)}</span>
                          <span>{formatLabel(race.gender)}</span>
                        </div>
                        <div className="race-time">
                          Total: {formatMinutes(race.total_time_min)}
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                <div className="report-actions">
                  <label className="field">
                    <span>Time window (+/- minutes)</span>
                    <input
                      type="number"
                      min="1"
                      value={filters.timeWindow}
                      onChange={(event) =>
                        setFilters((prev) => ({ ...prev, timeWindow: event.target.value }))
                      }
                    />
                  </label>
                  <button
                    className="primary"
                    type="button"
                    onClick={handleGenerateReport}
                    disabled={reportLoading || !selectedRace}
                  >
                    {reportLoading ? "Building report..." : "Generate report"}
                  </button>
                  {reportError ? <p className="error">{reportError}</p> : null}
                </div>
              </div>
            </section>
          </main>
        ) : (
          <main className="report-page">
            <div className="report-toolbar">
              <button className="secondary" type="button" onClick={handleBackToSearch}>
                Back to search
              </button>
              <div className="toolbar-actions">
                <label className="field">
                  <span>Station split</span>
                  <select value={selectedSplit} onChange={handleSplitChange}>
                    <option value="">Select station</option>
                    {splitOptions.map((split) => (
                      <option key={split} value={split}>
                        {split}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>Time window (+/- minutes)</span>
                  <input
                    type="number"
                    min="1"
                    value={filters.timeWindow}
                    onChange={(event) =>
                      setFilters((prev) => ({ ...prev, timeWindow: event.target.value }))
                    }
                  />
                </label>
                <button
                  className="primary"
                  type="button"
                  onClick={handleGenerateReport}
                  disabled={reportLoading}
                >
                  {reportLoading ? "Updating report..." : "Update report"}
                </button>
                {!isNativeApp ? (
                  <button className="secondary" type="button" onClick={handleDownloadPdf}>
                    Download PDF
                  </button>
                ) : null}
              </div>
            </div>
            {reportError ? <p className="error">{reportError}</p> : null}

            {!report ? (
              <div className="empty">No report loaded yet. Generate one from search.</div>
            ) : (
              <section id="report-root" className="report report-full">
                <div className="report-hero">
                  <div>
                    <p className="report-kicker">Race report</p>
                    <h3>{formatLabel(report.race?.name)}</h3>
                    <p className="report-subtitle">
                      {formatLabel(report.race?.event_name || report.race?.event_id)} |{" "}
                      {formatLabel(report.race?.location)} | Season {formatLabel(report.race?.season)}
                    </p>
                  </div>
                  <div className="report-time">
                    <span>Total time</span>
                    <strong>{formatMinutes(report.race?.total_time_min)}</strong>
                  </div>
                </div>

                <div className="report-grid">
                  <div className="report-card">
                    <h4>Race snapshot</h4>
                    <div className="stat-grid">
                      <div>
                        <span>
                          Division
                          <span
                            className="info-tooltip"
                            data-tooltip="Race category (open, pro, doubles)."
                            aria-label="Race category (open, pro, doubles)."
                            tabIndex={0}
                          >
                            i
                          </span>
                        </span>
                        <strong>{formatLabel(report.race?.division)}</strong>
                      </div>
                      <div>
                        <span>
                          Gender
                          <span
                            className="info-tooltip"
                            data-tooltip="Competition gender category for this result."
                            aria-label="Competition gender category for this result."
                            tabIndex={0}
                          >
                            i
                          </span>
                        </span>
                        <strong>{formatLabel(report.race?.gender)}</strong>
                      </div>
                      <div>
                        <span>
                          Age group
                          <span
                            className="info-tooltip"
                            data-tooltip="Age band used for rankings and percentiles."
                            aria-label="Age band used for rankings and percentiles."
                            tabIndex={0}
                          >
                            i
                          </span>
                        </span>
                        <strong>{formatLabel(report.race?.age_group)}</strong>
                      </div>
                      <div>
                        <span>
                          Year
                          <span
                            className="info-tooltip"
                            data-tooltip="Calendar year the race took place."
                            aria-label="Calendar year the race took place."
                            tabIndex={0}
                          >
                            i
                          </span>
                        </span>
                        <strong>{formatLabel(report.race?.year)}</strong>
                      </div>
                    </div>
                  </div>

                  <div className="report-card">
                    <h4>Rankings</h4>
                    <div className="stat-grid">
                      <div>
                        <span>
                          Event rank
                          <span
                            className="info-tooltip"
                            data-tooltip="Rank within the same location, division, gender, and age group."
                            aria-label="Rank within the same location, division, gender, and age group."
                            tabIndex={0}
                          >
                            i
                          </span>
                        </span>
                        <strong>
                          {formatLabel(report.race?.event_rank)} /{" "}
                          {formatLabel(report.race?.event_size)}
                        </strong>
                      </div>
                      <div>
                        <span>
                          Event percentile
                          <span
                            className="info-tooltip"
                            data-tooltip="Percentile within the same location cohort (age group/division/gender)."
                            aria-label="Percentile within the same location cohort (age group/division/gender)."
                            tabIndex={0}
                          >
                            i
                          </span>
                        </span>
                        <strong>{formatPercent(report.race?.event_percentile)}</strong>
                      </div>
                      <div>
                        <span>
                          Season rank
                          <span
                            className="info-tooltip"
                            data-tooltip="Rank within the same season, division, gender, and age group."
                            aria-label="Rank within the same season, division, gender, and age group."
                            tabIndex={0}
                          >
                            i
                          </span>
                        </span>
                        <strong>
                          {formatLabel(report.race?.season_rank)} /{" "}
                          {formatLabel(report.race?.season_size)}
                        </strong>
                      </div>
                      <div>
                        <span>
                          Overall rank
                          <span
                            className="info-tooltip"
                            data-tooltip="Rank across all seasons for the same division, gender, and age group."
                            aria-label="Rank across all seasons for the same division, gender, and age group."
                            tabIndex={0}
                          >
                            i
                          </span>
                        </span>
                        <strong>
                          {formatLabel(report.race?.overall_rank)} /{" "}
                          {formatLabel(report.race?.overall_size)}
                        </strong>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="report-card">
                  <h4>Age group distributions</h4>
                  <div className="chart-grid">
                    <HistogramChart
                      title="Age group total time"
                      subtitle="All athletes in the same division, gender, and age group."
                      histogram={distributions?.cohort_total_time}
                      stats={cohortStats}
                    />
                    <HistogramChart
                      title={`Time window total time${windowLabel}`}
                      subtitle="Athletes finishing near the selected total time."
                      histogram={distributions?.time_window_total_time}
                      stats={windowStats}
                    />
                    <HistogramChart
                      title={`Station: ${selectedSplitLabel}`}
                      subtitle="Compare your station split against the age group."
                      histogram={selectedSplitDistribution?.cohort}
                      stats={selectedSplitDistribution?.stats?.cohort}
                      emptyMessage="Select a station split to see its distribution."
                    />
                    <HistogramChart
                      title={`Station window${windowLabel}`}
                      subtitle="Station split distribution inside the time window."
                      histogram={selectedSplitDistribution?.time_window}
                      stats={selectedSplitDistribution?.stats?.time_window}
                      emptyMessage="Select a station split to see its time window."
                    />
                  </div>
                </div>

                <div className="report-card">
                  <h4>Split percentile lines</h4>
                  <div className="chart-grid">
                    <PercentileLineChart
                      title="Runs + Roxzone percentiles"
                      subtitle="Percentiles for each run segment and Roxzone."
                      series={percentileSeries.runs}
                      emptyMessage="No run percentile data available."
                    />
                    <PercentileLineChart
                      title="Station percentiles"
                      subtitle="Percentiles for each station split."
                      series={percentileSeries.stations}
                      emptyMessage="No station percentile data available."
                    />
                  </div>
                </div>

                <div className="report-card">
                  <h4>Splits</h4>
                  {report.splits?.length ? (
                    <div className="table-shell">
                      <div className="table-scroll">
                        <table className="responsive-table">
                          <thead>
                            <tr>
                              <th>Split</th>
                              <th>Time</th>
                              <th>Rank</th>
                              <th>Percentile</th>
                              <th>Window percentile</th>
                            </tr>
                          </thead>
                          <tbody>
                            {report.splits.map((split) => (
                              <tr key={`${split.split_name}-${split.split_rank}`}>
                                <td data-label="Split">{formatLabel(split.split_name)}</td>
                                <td data-label="Time">{formatMinutes(split.split_time_min)}</td>
                                <td data-label="Rank">
                                  {formatLabel(split.split_rank)} / {formatLabel(split.split_size)}
                                </td>
                                <td data-label="Percentile">
                                  {formatPercent(split.split_percentile)}
                                </td>
                                <td data-label="Window percentile">
                                  {formatPercent(split.split_percentile_time_window)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : (
                    <p className="empty">No split data found for this race.</p>
                  )}
                </div>

                <div className="report-grid">
                  <div className="report-card">
                    <h4>Age group stats</h4>
                    {cohortStats ? (
                      <div className="stat-grid">
                        <div>
                          <span>Competitors</span>
                          <strong>{formatLabel(cohortStats.count)}</strong>
                        </div>
                        <div>
                          <span>Median time</span>
                          <strong>{formatMinutes(cohortStats.median)}</strong>
                        </div>
                        <div>
                          <span>Best time</span>
                          <strong>{formatMinutes(cohortStats.min)}</strong>
                        </div>
                        <div>
                          <span>90th percentile</span>
                          <strong>{formatMinutes(cohortStats.p90)}</strong>
                        </div>
                      </div>
                    ) : (
                      <p className="empty">Age group stats unavailable.</p>
                    )}
                  </div>

                  <div className="report-card">
                    <h4>Time window stats{windowLabel}</h4>
                    {windowStats ? (
                      <div className="stat-grid">
                        <div>
                          <span>Competitors</span>
                          <strong>{formatLabel(windowStats.count)}</strong>
                        </div>
                        <div>
                          <span>Median time</span>
                          <strong>{formatMinutes(windowStats.median)}</strong>
                        </div>
                        <div>
                          <span>Best time</span>
                          <strong>{formatMinutes(windowStats.min)}</strong>
                        </div>
                        <div>
                          <span>90th percentile</span>
                          <strong>{formatMinutes(windowStats.p90)}</strong>
                        </div>
                      </div>
                    ) : (
                      <p className="empty">Time window stats unavailable.</p>
                    )}
                  </div>
                </div>
              </section>
            )}
          </main>
        )
      ) : mode === "compare" ? (
        <main className="comparison-page">
          <div className="report-toolbar">
            <div className="toolbar-actions">
              {!isNativeApp ? (
                <button
                  className="secondary"
                  type="button"
                  onClick={handleDownloadComparePdf}
                  disabled={!baseReport || !compareReport}
                >
                  Download PDF
                </button>
              ) : null}
            </div>
          </div>

          <section className="panel">
            <div className="comparison-grid">
              <div className="comparison-column">
                <div className="panel-header">
                  <h2>Base race</h2>
                  <p>Select the race you want to compare from.</p>
                </div>
                <form className="search-form" onSubmit={handleBaseSearch}>
                  <label className="field">
                    <span>Athlete name</span>
                    <input
                      type="text"
                      placeholder="Athlete Name"
                      value={baseName}
                      onChange={(event) => setBaseName(event.target.value)}
                    />
                  </label>

                  <ProgressiveSection enabled={isIosMobile} summary="More search filters">
                    <div className="grid-2">
                      <label className="field">
                        <span>Division</span>
                        <input
                          type="text"
                          placeholder="open, pro, doubles"
                          value={baseFilters.division}
                          onChange={(event) =>
                            setBaseFilters((prev) => ({
                              ...prev,
                              division: event.target.value,
                            }))
                          }
                        />
                      </label>

                      <label className="field">
                        <span>Gender</span>
                        <input
                          type="text"
                          placeholder="male or female or mixed"
                          value={baseFilters.gender}
                          onChange={(event) =>
                            setBaseFilters((prev) => ({
                              ...prev,
                              gender: event.target.value,
                            }))
                          }
                        />
                      </label>
                    </div>

                    <label className="field">
                      <span>Nationality</span>
                      <input
                        type="text"
                        placeholder="GBR"
                        value={baseFilters.nationality}
                        onChange={(event) =>
                          setBaseFilters((prev) => ({
                            ...prev,
                            nationality: event.target.value,
                          }))
                        }
                      />
                    </label>
                  </ProgressiveSection>

                  <button className="primary" type="submit" disabled={baseSearchLoading}>
                    {baseSearchLoading ? "Searching..." : "Search races"}
                  </button>
                  {baseSearchError ? <p className="error">{baseSearchError}</p> : null}
                </form>

                <div className="results">
                  <div className="results-header">
                    <h2>Base races</h2>
                    <span>
                      {baseRaces.length ? `${baseRaces.length} matches` : "No results"}
                    </span>
                  </div>
                  {baseRaces.length === 0 ? (
                    <div className="empty">
                      Search for an athlete to find a base race to compare.
                    </div>
                  ) : (
                    <div className="results-grid">
                      {baseRaces.map((race, index) => (
                        <button
                          key={race.result_id || `${race.event_id}-${index}`}
                          type="button"
                          className={`race-card ${
                            race.result_id === selectedBaseRaceId ? "is-selected" : ""
                          }`}
                          style={{ animationDelay: `${index * 0.04}s` }}
                          onClick={() => {
                            setSelectedBaseRaceId(race.result_id);
                            setBaseReport(null);
                            setBaseReportError("");
                          }}
                        >
                          <div className="race-card-header">
                            <span className="race-title">
                              {race.event_name || race.event_id || "Race"}
                            </span>
                            <span className="race-location">{formatLabel(race.location)}</span>
                          </div>
                          <div className="race-meta">
                            <span>Season {formatLabel(race.season)}</span>
                            <span>{formatLabel(race.year)}</span>
                            <span>{formatLabel(race.division)}</span>
                            <span>{formatLabel(race.gender)}</span>
                          </div>
                          <div className="race-time">
                            Total: {formatMinutes(race.total_time_min)}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}

                  <div className="report-actions">
                    <button
                      className="primary"
                      type="button"
                      onClick={handleLoadBaseReport}
                      disabled={baseReportLoading || !selectedBaseRace}
                    >
                      {baseReportLoading ? "Loading base..." : "Confirm base race"}
                    </button>
                    {baseReportError ? <p className="error">{baseReportError}</p> : null}
                  </div>
                </div>
              </div>

              <div className="comparison-column">
                <div className="panel-header">
                  <h2>Compare against</h2>
                  <p>Search and confirm the race you want to compare.</p>
                </div>
                <form className="search-form" onSubmit={handleCompareSearch}>
                  <label className="field">
                    <span>Athlete name</span>
                    <input
                      type="text"
                      placeholder="Alex Hunter"
                      value={compareName}
                      onChange={(event) => setCompareName(event.target.value)}
                    />
                  </label>

                  <ProgressiveSection enabled={isIosMobile} summary="More search filters">
                    <div className="grid-2">
                      <label className="field">
                        <span>Division</span>
                        <input
                          type="text"
                          placeholder="open, pro, doubles"
                          value={compareFilters.division}
                          onChange={(event) =>
                            setCompareFilters((prev) => ({
                              ...prev,
                              division: event.target.value,
                            }))
                          }
                        />
                      </label>

                      <label className="field">
                        <span>Gender</span>
                        <input
                          type="text"
                          placeholder="male or female or mixed"
                          value={compareFilters.gender}
                          onChange={(event) =>
                            setCompareFilters((prev) => ({
                              ...prev,
                              gender: event.target.value,
                            }))
                          }
                        />
                      </label>
                    </div>

                    <label className="field">
                      <span>Nationality</span>
                      <input
                        type="text"
                        placeholder="GBR"
                        value={compareFilters.nationality}
                        onChange={(event) =>
                          setCompareFilters((prev) => ({
                            ...prev,
                            nationality: event.target.value,
                          }))
                        }
                      />
                    </label>
                  </ProgressiveSection>

                  <button className="primary" type="submit" disabled={compareSearchLoading}>
                    {compareSearchLoading ? "Searching..." : "Search races"}
                  </button>
                  {compareSearchError ? <p className="error">{compareSearchError}</p> : null}
                </form>

                <div className="results">
                  <div className="results-header">
                    <h2>Comparison races</h2>
                    <span>
                      {compareRaces.length ? `${compareRaces.length} matches` : "No results"}
                    </span>
                  </div>
                  {compareRaces.length === 0 ? (
                    <div className="empty">
                      Search for an athlete to find a race to compare against.
                    </div>
                  ) : (
                    <div className="results-grid">
                      {compareRaces.map((race, index) => (
                        <button
                          key={race.result_id || `${race.event_id}-${index}`}
                          type="button"
                          className={`race-card ${
                            race.result_id === selectedCompareRaceId ? "is-selected" : ""
                          }`}
                          style={{ animationDelay: `${index * 0.04}s` }}
                          onClick={() => {
                            setSelectedCompareRaceId(race.result_id);
                            setCompareReport(null);
                            setCompareReportError("");
                          }}
                        >
                          <div className="race-card-header">
                            <span className="race-title">
                              {race.event_name || race.event_id || "Race"}
                            </span>
                            <span className="race-location">
                              {formatLabel(race.location)}
                            </span>
                          </div>
                          <div className="race-meta">
                            <span>Season {formatLabel(race.season)}</span>
                            <span>{formatLabel(race.year)}</span>
                            <span>{formatLabel(race.division)}</span>
                            <span>{formatLabel(race.gender)}</span>
                          </div>
                          <div className="race-time">
                            Total: {formatMinutes(race.total_time_min)}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}

                  <div className="report-actions">
                    <button
                      className="primary"
                      type="button"
                      onClick={handleLoadCompareReport}
                      disabled={compareReportLoading || !selectedCompareRace}
                    >
                      {compareReportLoading ? "Comparing..." : "Confirm comparison"}
                    </button>
                    {compareReportError ? <p className="error">{compareReportError}</p> : null}
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section id="compare-root" className="report report-full">
            <div className="compare-hero">
              <div className="compare-hero-card">
                <p className="report-kicker">Base race</p>
                <h3>
                  {baseReport
                    ? formatLabel(baseReport.race?.event_name || baseReport.race?.event_id)
                    : "Select a base race"}
                </h3>
                <p className="report-subtitle">
                  {baseReport
                    ? `${formatLabel(baseReport.race?.name)} | ${formatLabel(
                        baseReport.race?.location
                      )} | Season ${formatLabel(baseReport.race?.season)}`
                    : "No base race loaded yet."}
                </p>
                {baseReport ? (
                  <div className="compare-hero-time">
                    <span>Total time</span>
                    <strong>{formatMinutes(baseReport.race?.total_time_min)}</strong>
                  </div>
                ) : null}
              </div>
              <div className="compare-hero-card">
                <p className="report-kicker">Compare race</p>
                <h3>
                  {compareReport
                    ? formatLabel(compareReport.race?.event_name || compareReport.race?.event_id)
                    : "Select a comparison race"}
                </h3>
                <p className="report-subtitle">
                  {compareReport
                    ? `${formatLabel(compareReport.race?.name)} | ${formatLabel(
                        compareReport.race?.location
                      )} | Season ${formatLabel(compareReport.race?.season)}`
                    : "No comparison race loaded yet."}
                </p>
                {compareReport ? (
                  <div className="compare-hero-time">
                    <span>Total time</span>
                    <strong>{formatMinutes(compareReport.race?.total_time_min)}</strong>
                  </div>
                ) : null}
              </div>
            </div>

            {!baseReport || !compareReport ? (
              <div className="empty">
                Load a base race and a comparison race to see the charts and split deltas.
              </div>
            ) : (
              <>
                <div className="compare-charts">
                  <GroupedBarChart
                    title="Runs + Roxzone"
                    subtitle="Side-by-side run segments plus Roxzone."
                    segments={comparisonCharts?.runSegments ?? []}
                    baseLabel="Base"
                    compareLabel="Compare"
                    emptyMessage="Run/Roxzone data unavailable for one of the races."
                  />
                  <GroupedBarChart
                    title="Stations"
                    subtitle="Side-by-side station splits in order."
                    segments={comparisonCharts?.stationSegments ?? []}
                    baseLabel="Base"
                    compareLabel="Compare"
                    emptyMessage="Station split data unavailable."
                  />
                </div>

                <div className="report-card">
                  <h4>Split comparison</h4>
                  <div className="table-shell">
                    <div className="table-scroll">
                      <table className="responsive-table">
                        <thead>
                          <tr>
                            <th>Split</th>
                            <th>Base time</th>
                            <th>Compare time</th>
                            <th>Delta (base - compare)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {comparisonRows.map((row) => {
                            const deltaClass =
                              row.delta === null
                                ? ""
                                : row.delta > 0
                                  ? "delta-positive"
                                  : row.delta < 0
                                    ? "delta-negative"
                                    : "delta-even";
                            return (
                              <tr key={row.key}>
                                <td data-label="Split">{formatLabel(row.label)}</td>
                                <td data-label="Base time">
                                  {formatMinutes(row.primaryValue)}
                                </td>
                                <td data-label="Compare time">
                                  {formatMinutes(row.compareValue)}
                                </td>
                                <td data-label="Delta" className={deltaClass}>
                                  {formatDeltaMinutes(row.delta)}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </>
            )}
          </section>
        </main>
      ) : mode === "deepdive" ? (
        <main className="deepdive-page">
          <section className="panel">
            <div className="comparison-grid">
              <div className="comparison-column">
                <div className="panel-header">
                  <h2>Base race</h2>
                  <p>Select the race you want to deepdive.</p>
                </div>
                <form className="search-form" onSubmit={handleDeepdiveSearch}>
                  <label className="field">
                    <span>Athlete name</span>
                    <input
                      type="text"
                      placeholder="Athlete Name"
                      value={deepdiveName}
                      onChange={(event) => setDeepdiveName(event.target.value)}
                    />
                  </label>

                  <ProgressiveSection enabled={isIosMobile} summary="More search filters">
                    <div className="grid-2">
                      <label className="field">
                        <span>Division</span>
                        <input
                          type="text"
                          placeholder="open, pro, doubles"
                          value={deepdiveFilters.division}
                          onChange={(event) =>
                            setDeepdiveFilters((prev) => ({
                              ...prev,
                              division: event.target.value,
                            }))
                          }
                        />
                      </label>

                      <label className="field">
                        <span>Gender</span>
                        <input
                          type="text"
                          placeholder="male or female or mixed"
                          value={deepdiveFilters.gender}
                          onChange={(event) =>
                            setDeepdiveFilters((prev) => ({
                              ...prev,
                              gender: event.target.value,
                            }))
                          }
                        />
                      </label>
                    </div>

                    <label className="field">
                      <span>Nationality</span>
                      <input
                        type="text"
                        placeholder="GBR"
                        value={deepdiveFilters.nationality}
                        onChange={(event) =>
                          setDeepdiveFilters((prev) => ({
                            ...prev,
                            nationality: event.target.value,
                          }))
                        }
                      />
                    </label>
                  </ProgressiveSection>

                  <button className="primary" type="submit" disabled={deepdiveSearchLoading}>
                    {deepdiveSearchLoading ? "Searching..." : "Search races"}
                  </button>
                  {deepdiveSearchError ? <p className="error">{deepdiveSearchError}</p> : null}
                </form>

                <div className="results">
                  <div className="results-header">
                    <h2>Base races</h2>
                    <span>
                      {deepdiveRaces.length
                        ? `${deepdiveRaces.length} matches`
                        : "No results"}
                    </span>
                  </div>
                  {deepdiveRaces.length === 0 ? (
                    <div className="empty">
                      Search for an athlete to find a base race to deepdive.
                    </div>
                  ) : (
                    <div className="results-grid">
                      {deepdiveRaces.map((race, index) => (
                        <button
                          key={race.result_id || `${race.event_id}-${index}`}
                          type="button"
                          className={`race-card ${
                            race.result_id === selectedDeepdiveRaceId ? "is-selected" : ""
                          }`}
                          style={{ animationDelay: `${index * 0.04}s` }}
                          onClick={() => {
                            setSelectedDeepdiveRaceId(race.result_id);
                            setDeepdiveData(null);
                            setDeepdiveError("");
                            setDeepdiveParams((prev) => ({
                              ...prev,
                              season:
                                race.season !== null && race.season !== undefined
                                  ? String(race.season)
                                  : prev.season,
                              division: race.division ? String(race.division) : prev.division,
                              gender: race.gender ? String(race.gender) : prev.gender,
                              ageGroup: race.age_group
                                ? String(race.age_group)
                                : prev.ageGroup,
                            }));
                          }}
                        >
                          <div className="race-card-header">
                            <span className="race-title">
                              {race.event_name || race.event_id || "Race"}
                            </span>
                            <span className="race-location">
                              {formatLabel(race.location)}
                            </span>
                          </div>
                          <div className="race-meta">
                            <span>Season {formatLabel(race.season)}</span>
                            <span>{formatLabel(race.year)}</span>
                            <span>{formatLabel(race.division)}</span>
                            <span>{formatLabel(race.gender)}</span>
                          </div>
                          <div className="race-time">
                            Total: {formatMinutes(race.total_time_min)}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="comparison-column">
                <div className="panel-header">
                  <h2>Deepdive filters</h2>
                  <p>Compare your time against the season-wide field.</p>
                </div>
                <form
                  className="search-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    handleRunDeepdive();
                  }}
                >
                  <div className="grid-3">
                    <label className="field">
                      <span>Season *</span>
                      <input
                        type="number"
                        placeholder="8"
                        value={deepdiveParams.season}
                        onChange={(event) =>
                          setDeepdiveParams((prev) => ({
                            ...prev,
                            season: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label className="field">
                      <span>Division</span>
                      <input
                        type="text"
                        placeholder="open, pro, doubles"
                        value={deepdiveParams.division}
                        onChange={(event) =>
                          setDeepdiveParams((prev) => ({
                            ...prev,
                            division: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label className="field">
                      <span>Gender</span>
                      <input
                        type="text"
                        placeholder="male or female or mixed"
                        value={deepdiveParams.gender}
                        onChange={(event) =>
                          setDeepdiveParams((prev) => ({
                            ...prev,
                            gender: event.target.value,
                          }))
                        }
                      />
                    </label>
                  </div>

                  <ProgressiveSection
                    enabled={isIosMobile}
                    summary="Advanced deepdive options"
                  >
                    <div className="grid-3">
                      <label className="field">
                        <span>Age group</span>
                        <select
                          value={deepdiveParams.ageGroup}
                          onChange={(event) =>
                            setDeepdiveParams((prev) => ({
                              ...prev,
                              ageGroup: event.target.value,
                            }))
                          }
                          disabled={!deepdiveParams.season.trim() || deepdiveOptionsLoading}
                        >
                          <option value="">
                            {deepdiveOptionsLoading
                              ? "Loading age groups..."
                              : "Any age group"}
                          </option>
                          {deepdiveOptions.ageGroups.map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="field">
                        <span>Metric</span>
                        <select
                          value={deepdiveParams.metric}
                          onChange={(event) =>
                            setDeepdiveParams((prev) => ({
                              ...prev,
                              metric: event.target.value,
                            }))
                          }
                        >
                          {DEEPDIVE_METRIC_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="field">
                        <span>Stat focus</span>
                        <select
                          value={deepdiveParams.stat}
                          onChange={(event) =>
                            setDeepdiveParams((prev) => ({
                              ...prev,
                              stat: event.target.value,
                            }))
                          }
                        >
                          {DEEPDIVE_STAT_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>

                    <label className="field">
                      <span>Location (optional)</span>
                      <select
                        value={deepdiveParams.location}
                        onChange={(event) =>
                          setDeepdiveParams((prev) => ({
                            ...prev,
                            location: event.target.value,
                          }))
                        }
                        disabled={!deepdiveParams.season.trim() || deepdiveOptionsLoading}
                      >
                        <option value="">
                          {deepdiveOptionsLoading ? "Loading locations..." : "Any location"}
                        </option>
                        {deepdiveOptions.locations.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    </label>
                  </ProgressiveSection>

                  <div className="report-actions">
                    <button
                      className="primary"
                      type="submit"
                      disabled={deepdiveLoading || !selectedDeepdiveRace}
                    >
                      {deepdiveLoading ? "Running deepdive..." : "Run deepdive"}
                    </button>
                    {deepdiveError ? <p className="error">{deepdiveError}</p> : null}
                  </div>
                </form>

              </div>
            </div>

            <div className="deepdive-report">
              {deepdiveData ? (
                <div className="planner-results">
                  <div className="report-card">
                    <h4>Deepdive summary</h4>
                    <div className="stat-grid">
                      <div>
                        <span>Total locations</span>
                        <strong>{formatLabel(deepdiveData.total_locations)}</strong>
                      </div>
                      <div>
                        <span>Total results</span>
                        <strong>{formatLabel(deepdiveData.total_rows)}</strong>
                      </div>
                      <div>
                        <span>Athlete time</span>
                        <strong>
                          {formatMinutes(
                            deepdiveData.athlete_value ?? deepdiveData.athlete_time
                          )}
                        </strong>
                      </div>
                      <div>
                        <span>Metric</span>
                        <strong>{deepdiveMetricLabel}</strong>
                      </div>
                      <div>
                        <span>Stat focus</span>
                        <strong>{deepdiveStatLabel}</strong>
                      </div>
                    </div>
                  </div>

                  <HistogramChart
                    title="Metric distribution"
                    subtitle={`Filtered cohort distribution for ${deepdiveMetricLabel}`}
                    histogram={deepdiveDistribution}
                    stats={deepdiveGroupSummary}
                    infoTooltip="Histogram uses equal-width bins from the selected cohort group. For Top 5%, bins include locations for the times in that bin."
                    emptyMessage="No distribution data available for these filters."
                  />

                  <StatBarChart
                    title="Metric comparison"
                    subtitle={`Athlete vs ${deepdiveStatLabel} group (${deepdiveMetricLabel})`}
                    infoTooltip="Compares the athlete’s selected metric against the selected cohort group (Top 5%, Bottom 10%, or Mean). The bars show mean, median, fastest, and slowest within that group."
                    items={[
                      {
                        label: "Athlete",
                        value: toNumber(
                          deepdiveData.athlete_value ?? deepdiveData.athlete_time
                        ),
                        accent: true,
                      },
                      { label: "Mean", value: toNumber(deepdiveGroupSummary?.mean) },
                      { label: "Median", value: toNumber(deepdiveGroupSummary?.median) },
                      { label: "Fastest", value: toNumber(deepdiveGroupSummary?.min) },
                      { label: "Slowest", value: toNumber(deepdiveGroupSummary?.max) },
                    ]}
                  />

                  <div className="report-card">
                    <h4>Locations included</h4>
                    {deepdiveRows.length ? (
                      <div className="filter-tags">
                        {deepdiveRows.map((row, index) => (
                          <span
                            key={row.location ? row.location : `loc-${index}`}
                            className="filter-tag"
                          >
                            {formatLabel(row.location)}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="empty">No locations available for these filters.</p>
                    )}
                  </div>

                  <div className="report-card">
                    <h4>Location targets ({deepdiveStatLabel})</h4>
                    {deepdiveRows.length ? (
                      <div className="table-shell">
                        <div className="table-scroll">
                          <table className="responsive-table">
                            <thead>
                              <tr>
                                <th>Location</th>
                                <th>N</th>
                                <th>
                                  {deepdiveStatLabel} time
                                  {deepdiveParams.stat === "p05" ? (
                                    <span
                                      className="info-tooltip"
                                      data-tooltip="Top 5% time is the 5th percentile of the cohort (interpolated for small groups)."
                                      aria-label="Top 5% time definition"
                                    >
                                      i
                                    </span>
                                  ) : deepdiveParams.stat === "p90" ? (
                                    <span
                                      className="info-tooltip"
                                      data-tooltip="Bottom 10% time is the 90th percentile of the cohort (interpolated for small groups)."
                                      aria-label="Bottom 10% time definition"
                                    >
                                      i
                                    </span>
                                  ) : deepdiveParams.stat === "mean" ? (
                                    <span
                                      className="info-tooltip"
                                      data-tooltip="Mean time is the average across the cohort for the selected filters."
                                      aria-label="Mean time definition"
                                    >
                                      i
                                    </span>
                                  ) : null}
                                </th>
                                <th>Fastest time</th>
                                <th>Athlete time</th>
                                <th>Delta (athlete - target)</th>
                                <th>Delta (athlete - fastest)</th>
                              </tr>
                            </thead>
                            <tbody>
                              {deepdiveRows.map((row, index) => {
                                const deltaClass =
                                  row.delta === null
                                    ? ""
                                    : row.delta > 0
                                      ? "delta-positive"
                                      : row.delta < 0
                                        ? "delta-negative"
                                        : "delta-even";
                                const fastestDeltaClass =
                                  row.deltaFastest === null
                                    ? ""
                                    : row.deltaFastest > 0
                                      ? "delta-positive"
                                      : row.deltaFastest < 0
                                        ? "delta-negative"
                                        : "delta-even";
                                return (
                                  <tr key={`${row.location || "loc"}-${index}`}>
                                    <td data-label="Location">{formatLabel(row.location)}</td>
                                    <td data-label="N">{formatLabel(row.count)}</td>
                                    <td data-label={`${deepdiveStatLabel} time`}>
                                      {formatMinutes(row.statValue)}
                                    </td>
                                    <td data-label="Fastest time">
                                      {formatMinutes(row.fastestValue)}
                                    </td>
                                    <td data-label="Athlete time">
                                      {formatMinutes(
                                        deepdiveData.athlete_value ?? deepdiveData.athlete_time
                                      )}
                                    </td>
                                    <td data-label="Delta vs target" className={deltaClass}>
                                      {formatDeltaMinutes(row.delta)}
                                    </td>
                                    <td data-label="Delta vs fastest" className={fastestDeltaClass}>
                                      {formatDeltaMinutes(row.deltaFastest)}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    ) : (
                      <p className="empty">Run a deepdive to compare locations.</p>
                    )}
                  </div>
                </div>
              ) : (
                <div className="empty">Run a deepdive to see location comparisons.</div>
              )}
            </div>
          </section>
        </main>
      ) : (
        <main className="planner-page">
          <section className="panel">
            <form className="search-form" onSubmit={handlePlannerSearch}>
              <div className="grid-3">
                <label className="field">
                  <span>Season</span>
                  <input
                    type="number"
                    placeholder="8"
                    value={plannerFilters.season}
                    onChange={(event) =>
                      setPlannerFilters((prev) => ({ ...prev, season: event.target.value }))
                    }
                  />
                </label>
                <label className="field">
                  <span>Location</span>
                  <input
                    type="text"
                    placeholder="london"
                    value={plannerFilters.location}
                    onChange={(event) =>
                      setPlannerFilters((prev) => ({ ...prev, location: event.target.value }))
                    }
                  />
                </label>
                <label className="field">
                  <span>Year</span>
                  <input
                    type="number"
                    placeholder="2024"
                    value={plannerFilters.year}
                    onChange={(event) =>
                      setPlannerFilters((prev) => ({ ...prev, year: event.target.value }))
                    }
                  />
                </label>
              </div>

              <ProgressiveSection enabled={isIosMobile} summary="Advanced planner filters">
                <div className="grid-3">
                  <label className="field">
                    <span>Division</span>
                    <input
                      type="text"
                      placeholder="open"
                      value={plannerFilters.division}
                      onChange={(event) =>
                        setPlannerFilters((prev) => ({ ...prev, division: event.target.value }))
                      }
                    />
                  </label>
                  <label className="field">
                    <span>Gender</span>
                    <input
                      type="text"
                      placeholder="male or female or mixed"
                      value={plannerFilters.gender}
                      onChange={(event) =>
                        setPlannerFilters((prev) => ({ ...prev, gender: event.target.value }))
                      }
                    />
                  </label>
                  <label className="field">
                    <span>Time range (min)</span>
                    <div className="range-inputs">
                      <input
                        type="number"
                        placeholder="60"
                        value={plannerFilters.minTime}
                        onChange={(event) =>
                          setPlannerFilters((prev) => ({ ...prev, minTime: event.target.value }))
                        }
                      />
                      <span>to</span>
                      <input
                        type="number"
                        placeholder="65"
                        value={plannerFilters.maxTime}
                        onChange={(event) =>
                          setPlannerFilters((prev) => ({ ...prev, maxTime: event.target.value }))
                        }
                      />
                    </div>
                  </label>
                </div>
              </ProgressiveSection>

              <button className="primary" type="submit" disabled={plannerLoading}>
                {plannerLoading ? "Building plan..." : "Run planner"}
              </button>
              {plannerError ? <p className="error">{plannerError}</p> : null}
            </form>

            {plannerData ? (
              <div className="planner-results">
                <div className="report-card">
                  <h4>Planner age group</h4>
                  <div className="stat-grid">
                    <div>
                      <span>Matches</span>
                      <strong>{formatLabel(plannerData.count)}</strong>
                    </div>
                    <div>
                      <span>Filters</span>
                      <strong>{plannerTags.length ? plannerTags.length : "All"}</strong>
                    </div>
                  </div>
                  {plannerTags.length ? (
                    <div className="filter-tags">
                      {plannerTags.map((tag) => (
                        <span key={tag} className="filter-tag">
                          {tag}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="empty">No filters applied.</p>
                  )}
                </div>

                <div className="report-card">
                  <h4>Overall distribution</h4>
                  <div className="chart-grid">
                    {plannerGroups.overall.map((segment) => (
                      <HistogramChart
                        key={segment.key}
                        title={segment.label}
                        subtitle="Total finish time distribution."
                        histogram={segment.histogram}
                        stats={segment.stats}
                      />
                    ))}
                    {plannerGroups.overall.length === 0 ? (
                      <div className="empty">No overall distribution available.</div>
                    ) : null}
                  </div>
                </div>

                <div className="report-card">
                  <h4>Run segments</h4>
                  <div className="chart-grid">
                    {plannerGroups.runs.map((segment) => (
                      <HistogramChart
                        key={segment.key}
                        title={segment.label}
                        subtitle="Run segment distribution."
                        histogram={segment.histogram}
                        stats={segment.stats}
                      />
                    ))}
                    {plannerGroups.runs.length === 0 ? (
                      <div className="empty">No run segments available.</div>
                    ) : null}
                  </div>
                </div>

                <div className="report-card">
                  <h4>Stations</h4>
                  <div className="chart-grid">
                    {plannerGroups.stations.map((segment) => (
                      <HistogramChart
                        key={segment.key}
                        title={segment.label}
                        subtitle="Station split distribution."
                        histogram={segment.histogram}
                        stats={segment.stats}
                      />
                    ))}
                    {plannerGroups.stations.length === 0 ? (
                      <div className="empty">No station splits available.</div>
                    ) : null}
                  </div>
                </div>
              </div>
            ) : null}
          </section>
        </main>
      )}
    </div>
  );
}
