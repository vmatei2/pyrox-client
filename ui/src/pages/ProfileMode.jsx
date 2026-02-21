import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AnimatedNumber, ModeTabIcon } from "../components/UiPrimitives.jsx";
import { STATION_SEGMENTS } from "../constants/segments.js";
import { formatMinutes } from "../utils/formatters.js";
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

// Segments surfaced in profile time cards.
const PROFILE_TIME_SEGMENTS = [
  { key: "overall", label: "Overall Time", color: "#0a84ff" },
  { key: "runplusroxzone", label: "Run + Roxzone", color: "#f97316" },
  ...STATION_SEGMENTS.map((s) => ({ key: s.key, label: s.label, color: s.color })),
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
        Search for your name in our race database. Your personal bests, average
        times, and full race history will be tracked automatically.
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
            aria-label="Change athlete profile"
          >
            Change
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

function TimeCards({ metrics, emptyMessage, showContext = false }) {
  const entries = PROFILE_TIME_SEGMENTS.filter((seg) => metrics?.[seg.key]);

  if (!entries.length) {
    return <p className="empty">{emptyMessage}</p>;
  }

  return (
    <div className="profile-pb-grid">
      {entries.map((seg) => {
        const metric = metrics[seg.key];
        const where = showContext ? [metric.location, metric.year].filter(Boolean).join(" · ") : "";
        return (
          <article
            key={seg.key}
            className="profile-pb-card"
            style={{ "--pb-accent": seg.color }}
            aria-label={`${seg.label}: ${formatMinutes(metric.time)}`}
          >
            <span className="profile-pb-label">{seg.label}</span>
            <span className="profile-pb-time">
              <AnimatedNumber value={metric.time} formatter={formatMinutes} />
            </span>
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
      emptyMessage="No personal best times available for this athlete yet."
    />
  );
}

function AverageTimes({ averageTimes }) {
  return (
    <TimeCards
      metrics={averageTimes}
      emptyMessage="Average times are unavailable for this athlete."
    />
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
          <PersonalBests personalBests={personalBests} />
        </section>

        <section className="profile-section" aria-labelledby="avg-heading">
          <h3 id="avg-heading" className="profile-section-title">
            Average Times
          </h3>
          <AverageTimes averageTimes={averageTimes} />
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
