import { useMemo, useState } from "react";
import html2pdf from "html2pdf.js";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(
  /\/$/,
  ""
);

const MATCH_OPTIONS = [
  { value: "best", label: "Best match" },
  { value: "exact", label: "Exact match" },
  { value: "contains", label: "Contains" },
];

const formatMinutes = (value) => {
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

const parseError = async (response) => {
  try {
    const data = await response.json();
    return data?.detail || response.statusText;
  } catch (error) {
    return response.statusText || "Request failed.";
  }
};

const HistogramChart = ({ title, subtitle, histogram, stats, emptyMessage }) => {
  if (!histogram || !Array.isArray(histogram.bins) || histogram.bins.length === 0) {
    return (
      <div className="chart-card">
        <div className="chart-head">
          <div>
            <h5>{title}</h5>
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
          <h5>{title}</h5>
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
            const label = `${formatMinutes(bin.start)} - ${formatMinutes(bin.end)} | ${
              bin.count
            } (${percent}%)`;
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

export default function App() {
  const [mode, setMode] = useState("report");
  const [name, setName] = useState("");
  const [filters, setFilters] = useState({
    match: "best",
    gender: "",
    division: "",
    nationality: "",
    requireUnique: true,
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

  return (
    <div className="app">
      <header className="hero">
        <div className="hero-tag">Pyrox Race Report Studio</div>
        <h1>Find an athlete, pick a race, and build a clean report fast.</h1>
        <p>
          Search the Hyrox race database, review races, and generate a polished HTML report
          with a PDF export in one flow.
        </p>
      </header>

      <div className="mode-tabs">
        <button
          type="button"
          className={`mode-tab ${mode === "report" ? "is-active" : ""}`}
          onClick={() => handleModeChange("report")}
        >
          Race report
        </button>
        <button
          type="button"
          className={`mode-tab ${mode === "planner" ? "is-active" : ""}`}
          onClick={() => handleModeChange("planner")}
        >
          Pre-race planner
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
                    placeholder="Kate Russell"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                  />
                </label>

                <div className="grid-2">
                  <label className="field">
                    <span>Match style</span>
                    <select
                      value={filters.match}
                      onChange={(event) =>
                        setFilters((prev) => ({ ...prev, match: event.target.value }))
                      }
                    >
                      {MATCH_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>

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
                </div>

                <div className="grid-2">
                  <label className="field">
                    <span>Gender</span>
                    <input
                      type="text"
                      placeholder="M or F"
                      value={filters.gender}
                      onChange={(event) =>
                        setFilters((prev) => ({ ...prev, gender: event.target.value }))
                      }
                    />
                  </label>

                  <label className="field">
                    <span>Nationality</span>
                    <input
                      type="text"
                      placeholder="GB, US, RO"
                      value={filters.nationality}
                      onChange={(event) =>
                        setFilters((prev) => ({ ...prev, nationality: event.target.value }))
                      }
                    />
                  </label>
                </div>

                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={filters.requireUnique}
                    onChange={(event) =>
                      setFilters((prev) => ({ ...prev, requireUnique: event.target.checked }))
                    }
                  />
                  Require a unique athlete match
                </label>

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
                <button className="secondary" type="button" onClick={handleDownloadPdf}>
                  Download PDF
                </button>
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
                        <span>Division</span>
                        <strong>{formatLabel(report.race?.division)}</strong>
                      </div>
                      <div>
                        <span>Gender</span>
                        <strong>{formatLabel(report.race?.gender)}</strong>
                      </div>
                      <div>
                        <span>Age group</span>
                        <strong>{formatLabel(report.race?.age_group)}</strong>
                      </div>
                      <div>
                        <span>Year</span>
                        <strong>{formatLabel(report.race?.year)}</strong>
                      </div>
                    </div>
                  </div>

                  <div className="report-card">
                    <h4>Rankings</h4>
                    <div className="stat-grid">
                      <div>
                        <span>Event rank</span>
                        <strong>
                          {formatLabel(report.race?.event_rank)} /{" "}
                          {formatLabel(report.race?.event_size)}
                        </strong>
                      </div>
                      <div>
                        <span>Event percentile</span>
                        <strong>{formatPercent(report.race?.event_percentile)}</strong>
                      </div>
                      <div>
                        <span>Season rank</span>
                        <strong>
                          {formatLabel(report.race?.season_rank)} /{" "}
                          {formatLabel(report.race?.season_size)}
                        </strong>
                      </div>
                      <div>
                        <span>Overall rank</span>
                        <strong>
                          {formatLabel(report.race?.overall_rank)} /{" "}
                          {formatLabel(report.race?.overall_size)}
                        </strong>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="report-card">
                  <h4>Cohort distributions</h4>
                  <div className="chart-grid">
                    <HistogramChart
                      title="Cohort total time"
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
                      subtitle="Compare your station split against the cohort."
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
                  <h4>Splits</h4>
                  {report.splits?.length ? (
                    <table>
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
                            <td>{formatLabel(split.split_name)}</td>
                            <td>{formatMinutes(split.split_time_min)}</td>
                            <td>
                              {formatLabel(split.split_rank)} / {formatLabel(split.split_size)}
                            </td>
                            <td>{formatPercent(split.split_percentile)}</td>
                            <td>{formatPercent(split.split_percentile_time_window)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <p className="empty">No split data found for this race.</p>
                  )}
                </div>

                <div className="report-grid">
                  <div className="report-card">
                    <h4>Cohort stats</h4>
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
                      <p className="empty">Cohort stats unavailable.</p>
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
                    placeholder="F or M"
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

              <button className="primary" type="submit" disabled={plannerLoading}>
                {plannerLoading ? "Building plan..." : "Run planner"}
              </button>
              {plannerError ? <p className="error">{plannerError}</p> : null}
            </form>

            {plannerData ? (
              <div className="planner-results">
                <div className="report-card">
                  <h4>Planner cohort</h4>
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
