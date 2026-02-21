import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Capacitor } from "@capacitor/core";
import {
  AnimatedNumber,
  HelpSheet,
  ProgressiveSection,
  ReportCardHeader,
} from "../components/UiPrimitives.jsx";
import {
  RUN_PERCENTILE_SEGMENTS,
  STATION_PERCENTILE_SEGMENTS,
} from "../constants/segments.js";
import {
  formatMinutes,
  formatPercent,
  formatLabel,
  formatTimeWindowLabel,
  getPercentileColorClass,
} from "../utils/formatters.js";
import { toNumber, normalizeSplitKey } from "../utils/parsers.js";
import { buildReportFilename, buildReportHelpContent } from "../utils/pdf.js";
import { fetchFilterOptions, searchAthletes, fetchReport } from "../api/client.js";
import { triggerSelectionHaptic } from "../utils/haptics.js";
import { HistogramChart } from "../charts/HistogramChart.jsx";
import { PercentileLineChart } from "../charts/PercentileLineChart.jsx";
import { WorkRunSplitPieChart } from "../charts/WorkRunSplitPieChart.jsx";
import { RunChangeLineChart } from "../charts/RunChangeLineChart.jsx";

export default function ReportMode({
  isIosMobile,
  pendingRaceJump = null,
  onRaceJumpHandled = () => {},
}) {
  const platform = Capacitor.getPlatform ? Capacitor.getPlatform() : "web";
  const isNativeApp = Capacitor.isNativePlatform
    ? Capacitor.isNativePlatform()
    : platform !== "web";
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [filters, setFilters] = useState({
    match: "best",
    gender: "",
    division: "",
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
  const [activeHelpKey, setActiveHelpKey] = useState(null);

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

  const reportHelpContent = useMemo(
    () => buildReportHelpContent(filters.timeWindow),
    [filters.timeWindow]
  );
  const activeHelpContent = activeHelpKey ? reportHelpContent[activeHelpKey] || null : null;

  const cohortStats = report?.cohort_stats;
  const windowStats = report?.cohort_time_window_stats;
  const distributions = report?.distributions;
  const plotData = report?.plot_data;
  const workVsRunSplit = plotData?.work_vs_run_split;
  const runChangeSeries = plotData?.run_change_series;
  const selectedSplitDistribution = distributions?.selected_split;
  const selectedSplitLabel = selectedSplit ? selectedSplit : "Select station";
  const windowLabel =
    report?.cohort_time_window_min !== null && report?.cohort_time_window_min !== undefined
      ? ` (+/- ${report.cohort_time_window_min} min)`
      : "";
  const filterOptionsQuery = useQuery({
    queryKey: ["filter-options"],
    queryFn: () => fetchFilterOptions(),
  });
  const divisionOptions = Array.isArray(filterOptionsQuery.data?.divisions)
    ? filterOptionsQuery.data.divisions
    : [];
  const genderOptions = Array.isArray(filterOptionsQuery.data?.genders)
    ? filterOptionsQuery.data.genders
    : [];

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

  useEffect(() => {
    if (!activeHelpContent || typeof document === "undefined") {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [activeHelpContent]);

  useEffect(() => {
    if (!pendingRaceJump) {
      return;
    }

    let active = true;
    setView("report");
    setReport(null);
    setSelectedSplit("");
    setSelectedRaceId(pendingRaceJump);
    setReportLoading(true);
    setReportError("");
    setSearchError("");

    const loadPendingRace = async () => {
      try {
        const payload = await queryClient.fetchQuery({
          queryKey: ["report", pendingRaceJump, filters.timeWindow.trim(), ""],
          queryFn: () =>
            fetchReport(pendingRaceJump, {
              timeWindow: filters.timeWindow,
            }),
        });
        if (!active) {
          return;
        }
        setReport(payload);
        if (payload?.race?.result_id) {
          setRaces((prev) => {
            if (prev.some((race) => race.result_id === payload.race.result_id)) {
              return prev;
            }
            return [payload.race, ...prev];
          });
        }
        void triggerSelectionHaptic();
        window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (error) {
        if (!active) {
          return;
        }
        setReportError(error.message || "Report generation failed.");
      } finally {
        if (!active) {
          return;
        }
        setReportLoading(false);
        onRaceJumpHandled();
      }
    };

    void loadPendingRace();
    return () => {
      active = false;
    };
  }, [pendingRaceJump, onRaceJumpHandled, queryClient]);

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
      const payload = await queryClient.fetchQuery({
        queryKey: [
          "athletes-search",
          "report",
          name.trim(),
          filters.match,
          filters.gender.trim(),
          filters.division.trim(),
          filters.requireUnique,
        ],
        queryFn: () => searchAthletes(name, filters),
      });
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
      const splitName = typeof splitOverride === "string" ? splitOverride : selectedSplit;
      const payload = await queryClient.fetchQuery({
        queryKey: [
          "report",
          selectedRace.result_id,
          filters.timeWindow.trim(),
          splitName?.trim() || "",
        ],
        queryFn: () =>
          fetchReport(selectedRace.result_id, {
            timeWindow: filters.timeWindow,
            splitName,
          }),
      });
      setReport(payload);
      setView("report");
      void triggerSelectionHaptic();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      setReportError(error.message || "Report generation failed.");
    } finally {
      setReportLoading(false);
    }
  };

  const handleDownloadPdf = async () => {
    const reportNode = document.getElementById("report-root");
    if (!reportNode) {
      return;
    }
    const { default: html2pdf } = await import("html2pdf.js");
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
    setActiveHelpKey(null);
    setView("search");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const comparisonWindowText = formatTimeWindowLabel(filters.timeWindow);
  const comparisonWindowDescription =
    "Additional comparison cohort: athletes in the same location and season " +
    `finishing within ${comparisonWindowText} of your total time.`;

  return (
    <>
      {view === "search" ? (
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
                    <select
                      value={filters.division}
                      onChange={(event) =>
                        setFilters((prev) => ({ ...prev, division: event.target.value }))
                      }
                      disabled={filterOptionsQuery.isFetching}
                    >
                      <option value="">
                        {filterOptionsQuery.isFetching ? "Loading divisions..." : "Any division"}
                      </option>
                      {divisionOptions.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="field">
                    <span>Gender</span>
                    <select
                      value={filters.gender}
                      onChange={(event) =>
                        setFilters((prev) => ({ ...prev, gender: event.target.value }))
                      }
                      disabled={filterOptionsQuery.isFetching}
                    >
                      <option value="">
                        {filterOptionsQuery.isFetching ? "Loading genders..." : "Any gender"}
                      </option>
                      {genderOptions.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </ProgressiveSection>

              <button
                className={races.length ? "secondary" : "primary"}
                type="submit"
                disabled={searchLoading}
              >
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
                      aria-pressed={race.result_id === selectedRaceId}
                      style={{ animationDelay: `${index * 0.04}s` }}
                      onClick={() => {
                        setSelectedRaceId(race.result_id);
                        setReport(null);
                        setReportError("");
                        setSelectedSplit("");
                        void triggerSelectionHaptic();
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
                  <span>Time Window for Comparison (+/- minutes)</span>
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
                <p className="report-actions-help">{comparisonWindowDescription}</p>
                {reportError ? <p className="error">{reportError}</p> : null}
              </div>
            </div>
          </section>
        </main>
      ) : (
        <main className="report-page">
          <div className="report-toolbar">
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
                <span>
                  Time Window for Comparison (+/- minutes)
                  <span
                    className="info-tooltip"
                    data-tooltip={comparisonWindowDescription}
                    aria-label={comparisonWindowDescription}
                    tabIndex={0}
                  >
                    i
                  </span>
                </span>
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
            <button className="secondary" type="button" onClick={handleBackToSearch}>
              Back to search
            </button>
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
                  <strong>
                    <AnimatedNumber value={report.race?.total_time_min} formatter={formatMinutes} />
                  </strong>
                </div>
              </div>

              {Number.isFinite(report.race?.event_percentile) &&
                report.race.event_percentile >= 0.5 && (
                  <div
                    className={`percentile-callout ${getPercentileColorClass(report.race.event_percentile)}`}
                    aria-label={`You finished ahead of ${(report.race.event_percentile * 100).toFixed(1)}% of athletes in your age group`}
                  >
                    You finished ahead of{" "}
                    <strong>
                      <AnimatedNumber
                        value={report.race.event_percentile * 100}
                        formatter={(v) => `${v.toFixed(1)}%`}
                      />
                    </strong>{" "}
                    of athletes in your age group
                  </div>
                )}

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
                  <ReportCardHeader
                    title="Rankings"
                    helpKey="rankings"
                    onOpenHelp={setActiveHelpKey}
                  />
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
                      <strong className={getPercentileColorClass(report.race?.event_percentile)}>
                        {formatPercent(report.race?.event_percentile)}
                      </strong>
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
                <ReportCardHeader
                  title="Age group distributions"
                  helpKey="age_group_distributions"
                  onOpenHelp={setActiveHelpKey}
                />
                <div className="chart-grid">
                  <HistogramChart
                    title="Age group total time"
                    subtitle="All athletes in the same division, gender, and age group."
                    histogram={distributions?.cohort_total_time}
                    stats={cohortStats}
                  />
                  <HistogramChart
                    title={`Comparison-window total time${windowLabel}`}
                    subtitle="Additional cohort around similar finish times."
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
                    title={`Comparison-window station split${windowLabel}`}
                    subtitle="Station split distribution for the additional comparison cohort."
                    histogram={selectedSplitDistribution?.time_window}
                    stats={selectedSplitDistribution?.stats?.time_window}
                    emptyMessage="Select a station split to see its comparison-window distribution."
                  />
                </div>
              </div>

              <div className="report-card">
                <ReportCardHeader
                  title="Split percentile lines"
                  helpKey="split_percentile_lines"
                  onOpenHelp={setActiveHelpKey}
                />
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
                <h4>Race pacing profile</h4>
                <div className="chart-grid">
                  <WorkRunSplitPieChart
                    title="Work vs run split"
                    subtitle="Share of total effort between work time and runs + Roxzone."
                    split={workVsRunSplit}
                    emptyMessage="Work and run-time fields are missing for this race."
                  />
                  <RunChangeLineChart
                    title="Run pacing vs median (Runs 2-7)"
                    subtitle="Each run shows minutes faster/slower than your median run pace."
                    series={runChangeSeries}
                    emptyMessage="Run split columns are missing for this race."
                  />
                </div>
              </div>

              <div className="report-card">
                <ReportCardHeader
                  title="Splits"
                  helpKey="splits_table"
                  onOpenHelp={setActiveHelpKey}
                />
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
                            <th>Comparison-window percentile</th>
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
                              <td data-label="Comparison-window percentile">
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
                  <ReportCardHeader
                    title="Age group stats"
                    helpKey="age_group_stats"
                    onOpenHelp={setActiveHelpKey}
                  />
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
                  <ReportCardHeader
                    title={`Comparison-window stats${windowLabel}`}
                    helpKey="time_window_stats"
                    onOpenHelp={setActiveHelpKey}
                  />
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
                    <p className="empty">Comparison-window stats unavailable.</p>
                  )}
                </div>
              </div>
            </section>
          )}
        </main>
      )}
      {activeHelpContent ? (
        <HelpSheet content={activeHelpContent} onClose={() => setActiveHelpKey(null)} />
      ) : null}
    </>
  );
}
