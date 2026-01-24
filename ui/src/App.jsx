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

export default function App() {
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
  const [searchLoading, setSearchLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [reportError, setReportError] = useState("");

  const selectedRace = useMemo(
    () => races.find((race) => race.result_id === selectedRaceId),
    [races, selectedRaceId]
  );

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
    setSelectedRaceId(null);
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

  const handleGenerateReport = async () => {
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
      const response = await fetch(
        `${API_BASE}/api/reports/${selectedRace.result_id}?${params.toString()}`
      );
      if (!response.ok) {
        throw new Error(await parseError(response));
      }
      const payload = await response.json();
      setReport(payload);
    } catch (error) {
      setReportError(error.message || "Report generation failed.");
    } finally {
      setReportLoading(false);
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

  const cohortStats = report?.cohort_stats;
  const windowStats = report?.cohort_time_window_stats;
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

      <main className="layout">
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

        <section className="panel report-panel">
          <div className="panel-header">
            <h2>Report</h2>
            <p>
              {selectedRace
                ? `Selected: ${selectedRace.event_name || selectedRace.event_id || "Race"}`
                : "Select a race to preview the report."}
            </p>
          </div>

          {!report ? (
            <div className="empty report-empty">
              Generate a report to see the HTML output and PDF export.
            </div>
          ) : (
            <div className="report-wrap">
              <div className="report-buttons">
                <button className="secondary" type="button" onClick={handleDownloadPdf}>
                  Download PDF
                </button>
              </div>

              <section id="report-root" className="report">
                <div className="report-hero">
                  <div>
                    <p className="report-kicker">Race report</p>
                    <h3>{formatLabel(report.race?.name)}</h3>
                    <p className="report-subtitle">
                      {formatLabel(report.race?.event_name || report.race?.event_id)} |{" "}
                      {formatLabel(report.race?.location)} | Season{" "}
                      {formatLabel(report.race?.season)}
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
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
