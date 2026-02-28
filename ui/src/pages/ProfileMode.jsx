import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AnimatedNumber, ModeTabIcon } from "../components/UiPrimitives.jsx";
import { RUN_SEGMENTS, STATION_SEGMENTS } from "../constants/segments.js";
import { formatMinutes, getPercentileColorClass } from "../utils/formatters.js";
import { fetchAthleteProfile, searchAthletes } from "../api/client.js";
import { useAthleteIdentity } from "../hooks/useAthleteIdentity.js";
import { triggerSelectionHaptic } from "../utils/haptics.js";

// ── Helpers ───────────────────────────────────────────────────────

function getInitials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0][0].toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function ordinal(n) {
  if (n === null || n === undefined) return "-";
  const num = Number(n);
  if (!isFinite(num)) return "-";
  const mod10 = num % 10;
  const mod100 = num % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${num}th`;
  if (mod10 === 1) return `${num}st`;
  if (mod10 === 2) return `${num}nd`;
  if (mod10 === 3) return `${num}rd`;
  return `${num}th`;
}

function formatTopPercent(percentile) {
  const val = Number(percentile);
  if (!Number.isFinite(val)) return null;
  const top = Math.round((1 - val) * 100);
  return `Top ${Math.max(1, top)}%`;
}

function getPercFill(percentile) {
  const val = Number(percentile);
  if (!Number.isFinite(val)) return null;
  return Math.min(100, Math.max(0, val * 100));
}

// Segments surfaced in profile time cards.
const PROFILE_TIME_SEGMENTS = [
  { key: "overall", label: "Overall Time", color: "#0a84ff" },
  { key: "runplusroxzone", label: "Run + Roxzone", color: "#f97316" },
  ...STATION_SEGMENTS.map((s) => ({ key: s.key, label: s.label, color: s.color })),
];

const PROGRESSION_METRIC_OPTIONS = [
  { key: "overall", label: "Overall Race Time" },
  { key: "runplusroxzone", label: "Run + Roxzone" },
  { key: "run_time_min", label: "Total Run Time" },
  { key: "work_time_min", label: "Total Work Time" },
  { key: "roxzone_time_min", label: "Roxzone" },
  ...RUN_SEGMENTS.filter((segment) => segment.key !== "roxzone").map((segment) => ({
    key: segment.column,
    label: segment.label,
  })),
  ...STATION_SEGMENTS.map((segment) => ({
    key: segment.column,
    label: segment.label,
  })),
];

function normalizeProfileSearchResults(rows, fallbackName) {
  const safeRows = Array.isArray(rows) ? rows : [];
  const deduped = new Map();

  safeRows.forEach((row) => {
    const athleteNameRaw = row?.athlete_name ?? row?.name ?? fallbackName;
    const athleteName = typeof athleteNameRaw === "string" ? athleteNameRaw.trim() : "";
    if (!athleteName) return;

    const athleteId =
      typeof row?.athlete_id === "string" && row.athlete_id.trim()
        ? row.athlete_id.trim()
        : null;
    const dedupeKey = athleteId || athleteName.toLowerCase();
    const yearValue = Number(row?.year);
    const sortYear = Number.isFinite(yearValue) ? yearValue : -Infinity;
    const candidate = {
      ...row,
      athlete_id: athleteId,
      athlete_name: athleteName,
      nationality: row?.nationality ?? row?.athlete_nationality ?? null,
      _sortYear: sortYear,
    };

    const existing = deduped.get(dedupeKey);
    if (!existing || candidate._sortYear > existing._sortYear) {
      deduped.set(dedupeKey, candidate);
    }
  });

  return Array.from(deduped.values())
    .sort((left, right) => {
      const leftName = (left.athlete_name || "").toLowerCase();
      const rightName = (right.athlete_name || "").toLowerCase();
      return leftName.localeCompare(rightName);
    })
    .map(({ _sortYear, ...candidate }) => candidate);
}

// ── Setup view ────────────────────────────────────────────────────

function SetupView({ onClaim }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSearch(e) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setLoading(true);
    setError("");
    setResults([]);
    try {
      const data = await queryClient.fetchQuery({
        queryKey: ["profile-search", trimmed],
        queryFn: () => searchAthletes(trimmed, { match: "contains", requireUnique: false }),
      });
      const rows = Array.isArray(data) ? data : data?.races;
      setResults(normalizeProfileSearchResults(rows, trimmed));
    } catch (err) {
      setError(err?.message || "Search failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  const searched = name.trim() && !loading && !error;

  return (
    <section className="panel profile-setup-panel" aria-labelledby="setup-title">
      <div className="profile-setup-icon" aria-hidden="true">
        <ModeTabIcon kind="profile" />
      </div>
      <h2 id="setup-title" className="profile-setup-title">
        Set up your profile
      </h2>
      <p className="profile-setup-desc">
        Search for your name in our race database and find your PBs, average
        times, and race history.
      </p>

      <form className="search-form profile-setup-form" onSubmit={handleSearch}>
        <div className="field">
          <span>Your name</span>
          <input
            type="text"
            placeholder="e.g. Sarah Johnson"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="name"
            aria-label="Athlete name"
          />
        </div>
        <button
          type="submit"
          className="primary"
          disabled={loading || !name.trim()}
        >
          {loading ? "Searching…" : "Find me"}
        </button>
      </form>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {results.length > 0 && (
        <div
          className="profile-search-results"
          role="list"
          aria-label="Matching athletes"
        >
          <p className="profile-search-hint">Is one of these you?</p>
          {results.slice(0, 8).map((result) => {
            const athleteName = result.athlete_name || result.name || name.trim();
            const meta = [result.division, result.age_group, result.nationality]
              .filter(Boolean)
              .join(" · ");
            const identityKey = result.athlete_id || `${athleteName}-${result.result_id || "row"}`;
            return (
              <button
                key={identityKey}
                type="button"
                className="profile-search-result-row"
                onClick={() => onClaim(athleteName, result)}
                role="listitem"
                aria-label={`Claim profile for ${athleteName}`}
              >
                <div className="profile-search-result-info">
                  <span className="profile-search-result-name">{athleteName}</span>
                  {meta && (
                    <span className="profile-search-result-meta">{meta}</span>
                  )}
                </div>
                <span className="profile-search-result-action" aria-hidden="true">
                  This is me →
                </span>
              </button>
            );
          })}
        </div>
      )}

      {searched && results.length === 0 && (
        <p className="empty" role="status">
          No results found. Try a different spelling or a shorter name.
        </p>
      )}
    </section>
  );
}

// ── Profile hero card ─────────────────────────────────────────────

function ProfileHero({ athlete, summary, onChangeIdentity }) {
  const displayName = athlete?.name || "Athlete";
  const initials = getInitials(displayName);
  const meta = [athlete?.gender, athlete?.age_group, athlete?.nationality]
    .filter(Boolean)
    .join(" · ");

  return (
    <section className="profile-hero-card" aria-label="Athlete overview">
      <div className="profile-hero-mesh" aria-hidden="true" />
      <div className="profile-hero-content">
        <div className="profile-identity-row">
          <div className="profile-avatar" aria-hidden="true">
            <span className="profile-avatar-initials">{initials}</span>
          </div>
          <div className="profile-identity-info">
            <h2 className="profile-name">{displayName}</h2>
            {meta && <p className="profile-meta">{meta}</p>}
          </div>
          <button
            type="button"
            className="profile-change-btn"
            onClick={onChangeIdentity}
            aria-label="Switch to a different athlete profile"
          >
            Switch Athlete
          </button>
        </div>

        <dl className="profile-stats-strip">
          <div className="profile-stat">
            <dt className="profile-stat-label">Races</dt>
            <dd className="profile-stat-value">
              <AnimatedNumber value={summary?.total_races} />
            </dd>
          </div>
          <div className="profile-stat">
            <dt className="profile-stat-label">Personal Best</dt>
            <dd className="profile-stat-value profile-stat-time">
              <AnimatedNumber value={summary?.best_overall_time} formatter={formatMinutes} />
            </dd>
          </div>
          <div className="profile-stat">
            <dt className="profile-stat-label">Best A.G. Finish</dt>
            <dd className="profile-stat-value">
              {ordinal(summary?.best_age_group_finish)}
            </dd>
          </div>
          {summary?.first_season && (
            <div className="profile-stat">
              <dt className="profile-stat-label">Racing since</dt>
              <dd className="profile-stat-value">{summary.first_season}</dd>
            </div>
          )}
        </dl>
      </div>
    </section>
  );
}

function DivisionFilter({ divisions, selectedDivision, onChange }) {
  const options = Array.isArray(divisions) ? divisions.filter(Boolean) : [];
  if (options.length <= 1) {
    return null;
  }

  return (
    <section className="profile-section" aria-label="Division filter">
      <div className="profile-division-filter">
        <label htmlFor="profile-division-select" className="profile-division-filter-label">
          Division view
        </label>
        <select
          id="profile-division-select"
          className="profile-division-filter-select"
          value={selectedDivision}
          onChange={onChange}
        >
          <option value="">All divisions</option>
          {options.map((division) => (
            <option key={division} value={division}>
              {division}
            </option>
          ))}
        </select>
      </div>
    </section>
  );
}

// ── Time card grids ───────────────────────────────────────────────

function TimeCards({ metrics, emptyMessage, showContext = false, showPercentile = false }) {
  const entries = PROFILE_TIME_SEGMENTS.filter((seg) => metrics?.[seg.key]);

  if (!entries.length) {
    return <p className="empty">{emptyMessage}</p>;
  }

  return (
    <div className="profile-pb-grid">
      {entries.map((seg) => {
        const metric = metrics[seg.key];
        const where = showContext ? [metric.location, metric.year].filter(Boolean).join(" · ") : "";
        const percFill = showPercentile ? getPercFill(metric.percentile) : null;
        const topLabel = percFill !== null ? formatTopPercent(metric.percentile) : null;
        const percClass = percFill !== null ? getPercentileColorClass(metric.percentile) : "";
        return (
          <article
            key={seg.key}
            className="profile-pb-card"
            style={{ "--pb-accent": seg.color }}
            aria-label={`${seg.label}: ${formatMinutes(metric.time)}${topLabel ? `, ${topLabel}` : ""}`}
          >
            <span className="profile-pb-label">{seg.label}</span>
            <span className="profile-pb-time">
              <AnimatedNumber value={metric.time} formatter={formatMinutes} />
            </span>
            {percFill !== null && (
              <div className="profile-pb-perc-row" aria-hidden="true">
                <div className="profile-pb-perc-track">
                  <div className="profile-pb-perc-fill" style={{ width: `${percFill}%` }} />
                </div>
                {topLabel && (
                  <span className={`profile-pb-perc-label ${percClass}`}>{topLabel}</span>
                )}
              </div>
            )}
            {where && <span className="profile-pb-where">{where}</span>}
          </article>
        );
      })}
    </div>
  );
}

function PersonalBests({ personalBests }) {
  return (
    <TimeCards
      metrics={personalBests}
      showContext
      showPercentile
      emptyMessage="No personal best times available for this athlete yet."
    />
  );
}

function AverageTimes({ averageTimes }) {
  return (
    <TimeCards
      metrics={averageTimes}
      showPercentile
      emptyMessage="Average times are unavailable for this athlete."
    />
  );
}

// ── Finish progression chart ──────────────────────────────────────

const PROGRESSION_VIEW_W = 520;
const PROGRESSION_VIEW_H = 190;
const PROGRESSION_PAD = { top: 16, right: 18, bottom: 34, left: 54 };
const PROGRESSION_PLOT_W =
  PROGRESSION_VIEW_W - PROGRESSION_PAD.left - PROGRESSION_PAD.right;
const PROGRESSION_PLOT_H =
  PROGRESSION_VIEW_H - PROGRESSION_PAD.top - PROGRESSION_PAD.bottom;

function toChronologyTimestamp(race, fallbackIndex) {
  if (typeof race?.start_date === "string" && race.start_date.trim()) {
    const parsed = Date.parse(race.start_date);
    if (Number.isFinite(parsed)) return parsed;
  }

  const year = Number(race?.year);
  if (Number.isFinite(year)) {
    return Date.UTC(year, 0, 1) + fallbackIndex;
  }

  return Number.NaN;
}

function toMonthLabel(timestamp, includeYear) {
  if (!Number.isFinite(timestamp)) return "";
  const dt = new Date(timestamp);
  const month = dt.toLocaleString("en-US", { month: "short", timeZone: "UTC" });
  if (!includeYear) return month;
  const shortYear = String(dt.getUTCFullYear()).slice(-2);
  return `${month} '${shortYear}`;
}

function toFiniteNumber(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function getProgressionMetricValue(race, metricKey) {
  if (metricKey === "overall") {
    return toFiniteNumber(race?.total_time) ?? toFiniteNumber(race?.total_time_min);
  }
  if (metricKey === "runplusroxzone") {
    const precomputed = toFiniteNumber(race?.runplusroxzone_time_min);
    if (precomputed !== null) return precomputed;
    const run = toFiniteNumber(race?.run_time_min);
    const roxzone = toFiniteNumber(race?.roxzone_time_min);
    if (run === null || roxzone === null) return null;
    return run + roxzone;
  }
  return toFiniteNumber(race?.[metricKey]);
}

function FinishProgressionChart({ races }) {
  const [hovered, setHovered] = useState(null);
  const [selectedMetricKey, setSelectedMetricKey] = useState("overall");

  const sourceRaces = Array.isArray(races) ? races : [];
  const availableMetricOptions = PROGRESSION_METRIC_OPTIONS.filter((option) =>
    sourceRaces.some((race) => getProgressionMetricValue(race, option.key) !== null)
  );
  const effectiveMetricKey = availableMetricOptions.some(
    (option) => option.key === selectedMetricKey
  )
    ? selectedMetricKey
    : (availableMetricOptions[0]?.key ?? "overall");
  const selectedMetricLabel =
    PROGRESSION_METRIC_OPTIONS.find((option) => option.key === effectiveMetricKey)?.label ||
    "Overall Race Time";

  useEffect(() => {
    if (effectiveMetricKey !== selectedMetricKey) {
      setSelectedMetricKey(effectiveMetricKey);
    }
  }, [effectiveMetricKey, selectedMetricKey]);

  const validRows = sourceRaces
    .map((race, index) => {
      const metricValue = getProgressionMetricValue(race, effectiveMetricKey);
      if (metricValue === null) return null;
      return {
        ...race,
        _originalIndex: index,
        _metricValue: metricValue,
        _chrono: toChronologyTimestamp(race, index),
      };
    })
    .filter(Boolean);

  if (validRows.length === 0) {
    return <p className="empty">No progression data available for this athlete yet.</p>;
  }

  const chronological = [...validRows].sort((left, right) => {
    const leftChrono = Number.isFinite(left._chrono) ? left._chrono : Number.POSITIVE_INFINITY;
    const rightChrono = Number.isFinite(right._chrono) ? right._chrono : Number.POSITIVE_INFINITY;
    if (leftChrono !== rightChrono) return leftChrono - rightChrono;
    const leftYear = Number(left.year);
    const rightYear = Number(right.year);
    if (Number.isFinite(leftYear) && Number.isFinite(rightYear) && leftYear !== rightYear) {
      return leftYear - rightYear;
    }
    return left._originalIndex - right._originalIndex;
  });

  const times = chronological.map((race) => race._metricValue);
  const minTime = Math.min(...times);
  const maxTime = Math.max(...times);
  const range = maxTime - minTime || 1;

  const points = chronological.map((race, index) => {
    const x =
      PROGRESSION_PAD.left +
      (chronological.length === 1
        ? PROGRESSION_PLOT_W / 2
        : (index / (chronological.length - 1)) * PROGRESSION_PLOT_W);
    const y =
      PROGRESSION_PAD.top + ((race._metricValue - minTime) / range) * PROGRESSION_PLOT_H;
    return { ...race, x, y };
  });

  const datedYears = new Set();
  points.forEach((point) => {
    if (!Number.isFinite(point._chrono)) return;
    const dt = new Date(point._chrono);
    datedYears.add(dt.getUTCFullYear());
  });
  const includeYearInMonthLabel = datedYears.size > 1;

  const maxTickLabels = 6;
  const tickIndices = new Set();
  if (points.length <= maxTickLabels) {
    points.forEach((_, index) => tickIndices.add(index));
  } else {
    for (let i = 0; i < maxTickLabels; i += 1) {
      const index = Math.round((i * (points.length - 1)) / (maxTickLabels - 1));
      tickIndices.add(index);
    }
  }

  const linePath = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" ");
  const bottomY = PROGRESSION_PAD.top + PROGRESSION_PLOT_H;
  const areaPath =
    points.length >= 2
      ? `${linePath} L ${points[points.length - 1].x.toFixed(1)} ${bottomY.toFixed(1)} L ${points[0].x.toFixed(1)} ${bottomY.toFixed(1)} Z`
      : null;
  const isImproving =
    chronological.length >= 2 &&
    chronological[chronological.length - 1]._metricValue < chronological[0]._metricValue;

  return (
    <div className="profile-progression-wrap">
      <div className="profile-progression-controls">
        <label htmlFor="profile-progression-metric" className="profile-progression-label">
          Progression metric
        </label>
        <select
          id="profile-progression-metric"
          className="profile-progression-select"
          value={effectiveMetricKey}
          onChange={(event) => setSelectedMetricKey(event.target.value)}
        >
          {availableMetricOptions.map((option) => (
            <option key={option.key} value={option.key}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      <div className="profile-progression-trend">
        {chronological.length >= 2 && (
          <span
            className={isImproving ? "profile-progression-improving" : "profile-progression-stable"}
          >
            {isImproving ? "Improving trend" : "Stable trend"}
          </span>
        )}
      </div>
      <svg
        viewBox={`0 0 ${PROGRESSION_VIEW_W} ${PROGRESSION_VIEW_H}`}
        className="profile-progression-svg"
        role="img"
        aria-label="Finish time progression chart"
        onMouseLeave={() => setHovered(null)}
      >
        <defs>
          <linearGradient id="profile-progress-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0a84ff" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#0a84ff" stopOpacity="0.01" />
          </linearGradient>
        </defs>

        {[0, 0.5, 1].map((fraction) => {
          const y = PROGRESSION_PAD.top + fraction * PROGRESSION_PLOT_H;
          return (
            <line
              key={fraction}
              x1={PROGRESSION_PAD.left}
              y1={y.toFixed(1)}
              x2={PROGRESSION_VIEW_W - PROGRESSION_PAD.right}
              y2={y.toFixed(1)}
              stroke="rgba(156,177,214,0.12)"
              strokeWidth="1"
              strokeDasharray={fraction > 0 && fraction < 1 ? "4 4" : undefined}
            />
          );
        })}

        <text
          x={PROGRESSION_PAD.left - 6}
          y={PROGRESSION_PAD.top + 4}
          textAnchor="end"
          className="profile-progression-axis-label"
        >
          {formatMinutes(minTime)}
        </text>
        <text
          x={PROGRESSION_PAD.left - 6}
          y={bottomY + 4}
          textAnchor="end"
          className="profile-progression-axis-label"
        >
          {formatMinutes(maxTime)}
        </text>

        {points.map((point, index) => {
          if (!tickIndices.has(index)) return null;
          const label = Number.isFinite(point._chrono)
            ? toMonthLabel(point._chrono, includeYearInMonthLabel)
            : Number.isFinite(Number(point.year))
              ? String(point.year)
              : "";
          if (!label) return null;
          return (
            <text
              key={`x-label-${point.result_id || index}`}
              x={point.x.toFixed(1)}
              y={PROGRESSION_VIEW_H - 8}
              textAnchor="middle"
              className="profile-progression-axis-label"
            >
              {label}
            </text>
          );
        })}

        {areaPath && <path d={areaPath} fill="url(#profile-progress-area)" />}
        {points.length >= 2 && (
          <path
            d={linePath}
            fill="none"
            stroke="#0a84ff"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}

        {points.map((point) => {
          const locationLabel =
            typeof point.location === "string" && point.location.trim()
              ? point.location.trim()
              : "Unknown location";
          const label = [locationLabel, point.year].filter(Boolean).join(" · ");
          return (
            <circle
              key={point.result_id || `${point._originalIndex}`}
              cx={point.x.toFixed(1)}
              cy={point.y.toFixed(1)}
              r="4.5"
              fill="#09111f"
              stroke="#0a84ff"
              strokeWidth="2"
              style={{ cursor: "pointer" }}
              onMouseEnter={() => setHovered(point)}
              aria-label={`Race in ${label}: ${selectedMetricLabel} ${formatMinutes(point._metricValue)}`}
            >
              <title>{`Race in ${label}`}</title>
            </circle>
          );
        })}

        {hovered && (() => {
          const tx = Math.min(hovered.x + 12, PROGRESSION_VIEW_W - 152);
          const ty = Math.max(hovered.y - 52, PROGRESSION_PAD.top);
          const locationLabel =
            typeof hovered.location === "string" && hovered.location.trim()
              ? hovered.location.trim()
              : "Unknown location";
          const label = [locationLabel, hovered.year].filter(Boolean).join(" · ");
          return (
            <g role="tooltip" aria-live="polite">
              <rect
                x={tx}
                y={ty}
                width={142}
                height={44}
                rx="8"
                fill="rgba(8,14,25,0.97)"
                stroke="rgba(156,177,214,0.22)"
                strokeWidth="1"
              />
              <text x={tx + 10} y={ty + 16} className="profile-progression-tooltip-label">
                {label}
              </text>
              <text x={tx + 10} y={ty + 32} className="profile-progression-tooltip-value">
                {formatMinutes(hovered._metricValue)}
              </text>
            </g>
          );
        })()}
      </svg>
    </div>
  );
}

// ── Race history list ─────────────────────────────────────────────

function RaceHistory({ races, onOpenRace }) {
  if (!races?.length) {
    return <p className="empty">No race history found for this athlete.</p>;
  }

  return (
    <div className="profile-race-list" role="list">
      {races.map((race, idx) => {
        const label = [race.location, race.year].filter(Boolean).join(" ");
        return (
          <button
            key={race.result_id}
            type="button"
            className="profile-race-row"
            style={{ animationDelay: `${idx * 35}ms` }}
            onClick={() => onOpenRace?.(race.result_id)}
            aria-label={`Open report for ${label}`}
          >
            <div className="profile-race-row-main">
              <span className="profile-race-name">{race.location ?? "—"}</span>
              {race.year && (
                <span className="profile-race-year">{race.year}</span>
              )}
            </div>
            <div className="profile-race-row-right">
              <span className="profile-race-time">
                {formatMinutes(race.total_time)}
              </span>
              {race.age_group_rank != null && (
                <span className="profile-race-rank">
                  {ordinal(race.age_group_rank)} AG
                </span>
              )}
              <span className="profile-race-arrow" aria-hidden="true">
                →
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ── Root component ────────────────────────────────────────────────

export default function ProfileMode({ onOpenRace }) {
  const queryClient = useQueryClient();
  const { identity, setIdentity, clearIdentity } = useAthleteIdentity();

  const [view, setView] = useState(() => (identity ? "loading" : "setup"));
  const [profile, setProfile] = useState(null);
  const [selectedDivision, setSelectedDivision] = useState("");
  const [error, setError] = useState("");

  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Auto-load profile on mount when identity is already stored
  useEffect(() => {
    if (identity) {
      loadProfile(identity);
    }
    // Only run on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadProfile(identityInput, divisionInput = selectedDivision) {
    const identityPayload =
      typeof identityInput === "string" ? { name: identityInput } : identityInput || {};
    const athleteId =
      typeof identityPayload?.athleteId === "string"
        ? identityPayload.athleteId.trim()
        : "";
    const athleteName =
      typeof identityPayload?.name === "string" ? identityPayload.name.trim() : "";
    const division =
      typeof divisionInput === "string" ? divisionInput.trim() : "";
    if (!athleteId && !athleteName) {
      setError("Missing athlete identity. Search and claim your profile again.");
      setView("error");
      return;
    }

    setView("loading");
    setError("");
    try {
      const data = await queryClient.fetchQuery({
        queryKey: [
          "athlete-profile",
          athleteId || `name:${athleteName}`,
          division || "all-divisions",
        ],
        queryFn: () =>
          fetchAthleteProfile({
            athleteId: athleteId || undefined,
            name: athleteName || undefined,
            division: division || undefined,
          }),
      });
      if (!mountedRef.current) return;
      setSelectedDivision(division);
      setProfile(data);
      setView("profile");
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err?.message || "Failed to load profile. Please try again.");
      setView("error");
    }
  }

  function handleClaim(athleteName, match) {
    triggerSelectionHaptic();
    const athleteId =
      typeof match?.athlete_id === "string" ? match.athlete_id.trim() : "";
    const newIdentity = {
      athleteId: athleteId || undefined,
      name: athleteName,
      setAt: new Date().toISOString(),
    };
    setIdentity(newIdentity);
    setSelectedDivision("");
    loadProfile(newIdentity, "");
  }

  function handleChangeIdentity() {
    clearIdentity();
    setProfile(null);
    setSelectedDivision("");
    setError("");
    setView("setup");
  }

  function handleDivisionChange(event) {
    const nextDivision = event.target.value;
    setSelectedDivision(nextDivision);
    if (!identity) return;
    loadProfile(identity, nextDivision);
  }

  // ── Setup ────────────────────────────────────────────────────────
  if (view === "setup") {
    return (
      <main className="layout is-single">
        <div className="profile-page">
          <SetupView onClaim={handleClaim} />
        </div>
      </main>
    );
  }

  // ── Loading ──────────────────────────────────────────────────────
  if (view === "loading") {
    return (
      <main className="layout is-single">
        <div className="profile-page">
          <div
            className="skeleton-panel profile-skeleton"
            aria-label="Loading profile"
            aria-busy="true"
          >
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        </div>
      </main>
    );
  }

  // ── Error ────────────────────────────────────────────────────────
  if (view === "error") {
    return (
      <main className="layout is-single">
        <div className="profile-page">
          <section className="panel">
            <p className="error" role="alert">
              {error}
            </p>
            <div className="profile-error-actions">
              {identity && (
                <button
                  type="button"
                  className="primary"
                  onClick={() => loadProfile(identity)}
                >
                  Retry
                </button>
              )}
              <button
                type="button"
                className="secondary"
                onClick={handleChangeIdentity}
              >
                Change athlete
              </button>
            </div>
          </section>
        </div>
      </main>
    );
  }

  // ── Profile ──────────────────────────────────────────────────────
  const athlete = profile?.athlete ?? {};
  const summary = profile?.summary ?? {};
  const personalBests = profile?.personal_bests ?? {};
  const averageTimes = profile?.average_times ?? {};
  const races = profile?.races ?? [];
  const availableDivisions = Array.isArray(profile?.available_divisions)
    ? profile.available_divisions
    : [];

  return (
    <main className="layout is-single">
      <div className="profile-page">
        <ProfileHero
          athlete={athlete}
          summary={summary}
          onChangeIdentity={handleChangeIdentity}
        />

        <DivisionFilter
          divisions={availableDivisions}
          selectedDivision={selectedDivision}
          onChange={handleDivisionChange}
        />

        <section className="profile-section" aria-labelledby="pb-heading">
          <h3 id="pb-heading" className="profile-section-title">
            Personal Bests
          </h3>
          <p className="profile-section-note">
            Percentiles compare against historical results in your division and gender.
          </p>
          <PersonalBests personalBests={personalBests} />
        </section>

        <section className="profile-section" aria-labelledby="avg-heading">
          <h3 id="avg-heading" className="profile-section-title">
            Your Average Times
          </h3>
          <p className="profile-section-note">
            Percentiles compare against historical results in your division and gender.
          </p>
          <AverageTimes averageTimes={averageTimes} />
        </section>

        <section className="profile-section" aria-labelledby="progression-heading">
          <h3 id="progression-heading" className="profile-section-title">
            Finish Time Progression
          </h3>
          <p className="profile-section-note">
            Your finish times in chronological order, from earliest to latest race.
          </p>
          <FinishProgressionChart races={races} />
        </section>

        <section className="profile-section" aria-labelledby="history-heading">
          <h3 id="history-heading" className="profile-section-title">
            Race History
          </h3>
          <RaceHistory races={races} onOpenRace={onOpenRace} />
        </section>
      </div>
    </main>
  );
}
