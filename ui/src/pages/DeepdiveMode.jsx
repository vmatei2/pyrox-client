import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FlowSteps, ProgressiveSection } from "../components/UiPrimitives.jsx";
import {
  DEEPDIVE_METRIC_OPTIONS,
  DEEPDIVE_STAT_OPTIONS,
} from "../constants/segments.js";
import {
  formatMinutes,
  formatDeltaMinutes,
  formatLabel,
} from "../utils/formatters.js";
import { toNumber } from "../utils/parsers.js";
import {
  fetchDeepdive,
  fetchDeepdiveFilters,
  searchAthletes,
} from "../api/client.js";
import { triggerSelectionHaptic } from "../utils/haptics.js";
import { HistogramChart } from "../charts/HistogramChart.jsx";
import { StatBarChart } from "../charts/StatBarChart.jsx";

const buildOptions = (payload) => {
  const locations = Array.isArray(payload?.locations) ? payload.locations : [];
  const ageGroups = Array.isArray(payload?.age_groups) ? payload.age_groups : [];
  return { locations, ageGroups };
};

export default function DeepdiveMode({ isIosMobile }) {
  const queryClient = useQueryClient();
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
  const [deepdiveParams, setDeepdiveParams] = useState({
    season: "",
    division: "",
    gender: "",
    ageGroup: "",
    location: "",
    metric: "total_time_min",
    stat: "p05",
  });

  const selectedDeepdiveRace = useMemo(
    () => deepdiveRaces.find((race) => race.result_id === selectedDeepdiveRaceId),
    [deepdiveRaces, selectedDeepdiveRaceId]
  );

  const filtersQuery = useQuery({
    queryKey: [
      "deepdive-filters",
      deepdiveParams.season.trim(),
      deepdiveParams.division.trim(),
      deepdiveParams.gender.trim(),
    ],
    queryFn: () =>
      fetchDeepdiveFilters({
        season: deepdiveParams.season,
        division: deepdiveParams.division,
        gender: deepdiveParams.gender,
      }),
    enabled: Boolean(deepdiveParams.season.trim()),
  });
  const deepdiveOptions = useMemo(() => buildOptions(filtersQuery.data), [filtersQuery.data]);
  const deepdiveOptionsLoading = filtersQuery.isFetching;

  useEffect(() => {
    if (!deepdiveParams.season.trim()) {
      return;
    }
    setDeepdiveParams((prev) => ({
      ...prev,
      location:
        prev.location && !deepdiveOptions.locations.includes(prev.location) ? "" : prev.location,
      ageGroup:
        prev.ageGroup && !deepdiveOptions.ageGroups.includes(prev.ageGroup) ? "" : prev.ageGroup,
    }));
  }, [
    deepdiveOptions.ageGroups,
    deepdiveOptions.locations,
    deepdiveParams.season,
  ]);

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
      const payload = await queryClient.fetchQuery({
        queryKey: [
          "athletes-search",
          "deepdive",
          deepdiveName.trim(),
          deepdiveFilters.match,
          deepdiveFilters.gender.trim(),
          deepdiveFilters.division.trim(),
          deepdiveFilters.nationality.trim(),
          deepdiveFilters.requireUnique,
        ],
        queryFn: () => searchAthletes(deepdiveName, deepdiveFilters),
      });
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
      const payload = await queryClient.fetchQuery({
        queryKey: [
          "deepdive",
          selectedDeepdiveRace.result_id,
          deepdiveParams.season.trim(),
          deepdiveParams.metric.trim(),
          deepdiveParams.division.trim(),
          deepdiveParams.gender.trim(),
          deepdiveParams.ageGroup.trim(),
          deepdiveParams.location.trim(),
          deepdiveParams.stat.trim(),
        ],
        queryFn: () => fetchDeepdive(selectedDeepdiveRace.result_id, deepdiveParams),
      });
      setDeepdiveData(payload);
      void triggerSelectionHaptic();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      setDeepdiveError(error.message || "Deepdive analysis failed.");
      setDeepdiveData(null);
    } finally {
      setDeepdiveLoading(false);
    }
  };

  return (
    <main className="deepdive-page">
      <section className="panel">
        <div className="comparison-grid">
          <div className="comparison-column">
            <div className="panel-header">
              <h2>Base race</h2>
              <p>Select the race you want to deepdive.</p>
            </div>
            <FlowSteps steps={["Search athlete", "Select base race", "Configure deepdive"]} />
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

              <button
                className={deepdiveRaces.length ? "secondary" : "primary"}
                type="submit"
                disabled={deepdiveSearchLoading}
              >
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
              {deepdiveSearchLoading && deepdiveRaces.length === 0 ? (
                <div className="skeleton-panel" aria-hidden="true">
                  <div className="skeleton-line" />
                  <div className="skeleton-line" />
                  <div className="skeleton-line" />
                </div>
              ) : deepdiveRaces.length === 0 ? (
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
                      aria-pressed={race.result_id === selectedDeepdiveRaceId}
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
            </div>
          </div>

          <div className="comparison-column">
            <div className="panel-header">
              <h2>Deepdive filters</h2>
              <p>Compare your time against the season-wide field.</p>
            </div>
            <FlowSteps
              steps={["Set season + cohort filters", "Choose metric and stat focus", "Run deepdive"]}
            />
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
          {deepdiveLoading ? (
            <div className="skeleton-panel" aria-hidden="true">
              <div className="skeleton-line" />
              <div className="skeleton-line" />
              <div className="skeleton-line" />
              <div className="skeleton-line" />
            </div>
          ) : deepdiveData ? (
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
                infoTooltip="Histogram uses equal-width bins from the selected cohort group. For Top 5% and Podium, bins include locations for the times in that bin."
                emptyMessage="No distribution data available for these filters."
              />

              <StatBarChart
                title="Metric comparison"
                subtitle={`Athlete vs ${deepdiveStatLabel} group (${deepdiveMetricLabel})`}
                infoTooltip="Compares the athlete’s selected metric against the selected cohort group (Top 5%, Podium, Bottom 10%, or Mean). The bars show mean, median, fastest, and slowest within that group."
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
                              ) : deepdiveParams.stat === "podium" ? (
                                <span
                                  className="info-tooltip"
                                  data-tooltip="Podium time is the 3rd-fastest result in the cohort (or the slowest of available top finishes when fewer than 3 results exist)."
                                  aria-label="Podium time definition"
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
  );
}

