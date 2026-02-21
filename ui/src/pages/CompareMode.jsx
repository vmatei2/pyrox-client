import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Capacitor } from "@capacitor/core";
import { ProgressiveSection } from "../components/UiPrimitives.jsx";
import {
  RUN_SEGMENTS,
  STATION_SEGMENTS,
} from "../constants/segments.js";
import {
  formatMinutes,
  formatDeltaMinutes,
  formatLabel,
  sumTimes,
} from "../utils/formatters.js";
import {
  toNumber,
  buildSplitTimeMap,
  pickSegmentValue,
} from "../utils/parsers.js";
import { buildComparisonFilename } from "../utils/pdf.js";
import { searchAthletes, fetchReport } from "../api/client.js";
import { triggerSelectionHaptic } from "../utils/haptics.js";
import { GroupedBarChart } from "../charts/GroupedBarChart.jsx";

export default function CompareMode({ isIosMobile }) {
  const platform = Capacitor.getPlatform ? Capacitor.getPlatform() : "web";
  const isNativeApp = Capacitor.isNativePlatform
    ? Capacitor.isNativePlatform()
    : platform !== "web";
  const queryClient = useQueryClient();

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

  const selectedBaseRace = useMemo(
    () => baseRaces.find((race) => race.result_id === selectedBaseRaceId),
    [baseRaces, selectedBaseRaceId]
  );
  const selectedCompareRace = useMemo(
    () => compareRaces.find((race) => race.result_id === selectedCompareRaceId),
    [compareRaces, selectedCompareRaceId]
  );

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
      const payload = await queryClient.fetchQuery({
        queryKey: [
          "athletes-search",
          "compare-base",
          baseName.trim(),
          baseFilters.match,
          baseFilters.gender.trim(),
          baseFilters.division.trim(),
          baseFilters.nationality.trim(),
          baseFilters.requireUnique,
        ],
        queryFn: () => searchAthletes(baseName, baseFilters),
      });
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
      const payload = await queryClient.fetchQuery({
        queryKey: ["report", selectedBaseRace.result_id, "", ""],
        queryFn: () => fetchReport(selectedBaseRace.result_id),
      });
      setBaseReport(payload);
      void triggerSelectionHaptic();
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
      const payload = await queryClient.fetchQuery({
        queryKey: [
          "athletes-search",
          "compare-target",
          compareName.trim(),
          compareFilters.match,
          compareFilters.gender.trim(),
          compareFilters.division.trim(),
          compareFilters.nationality.trim(),
          compareFilters.requireUnique,
        ],
        queryFn: () => searchAthletes(compareName, compareFilters),
      });
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
      const payload = await queryClient.fetchQuery({
        queryKey: ["report", selectedCompareRace.result_id, "", ""],
        queryFn: () => fetchReport(selectedCompareRace.result_id),
      });
      setCompareReport(payload);
      void triggerSelectionHaptic();
    } catch (error) {
      setCompareReportError(error.message || "Comparison report failed.");
      setCompareReport(null);
    } finally {
      setCompareReportLoading(false);
    }
  };

  const handleDownloadComparePdf = async () => {
    const compareNode = document.getElementById("compare-root");
    if (!compareNode) {
      return;
    }
    const { default: html2pdf } = await import("html2pdf.js");
    const options = {
      margin: 0.35,
      filename: buildComparisonFilename(baseReport?.race, compareReport?.race),
      image: { type: "jpeg", quality: 0.95 },
      html2canvas: { scale: 2, useCORS: true },
      jsPDF: { unit: "in", format: "letter", orientation: "portrait" },
    };
    html2pdf().set(options).from(compareNode).save();
  };

  return (
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

              <button
                className={baseRaces.length ? "secondary" : "primary"}
                type="submit"
                disabled={baseSearchLoading}
              >
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
                      aria-pressed={race.result_id === selectedBaseRaceId}
                      style={{ animationDelay: `${index * 0.04}s` }}
                      onClick={() => {
                        setSelectedBaseRaceId(race.result_id);
                        setBaseReport(null);
                        setBaseReportError("");
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

              <button
                className={compareRaces.length ? "secondary" : "primary"}
                type="submit"
                disabled={compareSearchLoading}
              >
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
                      aria-pressed={race.result_id === selectedCompareRaceId}
                      style={{ animationDelay: `${index * 0.04}s` }}
                      onClick={() => {
                        setSelectedCompareRaceId(race.result_id);
                        setCompareReport(null);
                        setCompareReportError("");
                        void triggerSelectionHaptic();
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
  );
}
