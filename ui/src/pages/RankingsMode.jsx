import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ProgressiveSection } from "../components/UiPrimitives.jsx";
import { fetchRankings, fetchRankingsFilters } from "../api/client.js";
import { formatLabel, formatMinutes } from "../utils/formatters.js";
import { triggerSelectionHaptic } from "../utils/haptics.js";

const buildOptions = (payload) => {
  const ageGroups = Array.isArray(payload?.age_groups) ? payload.age_groups : [];
  const locations = Array.isArray(payload?.locations) ? payload.locations : [];
  return { ageGroups, locations };
};

export default function RankingsMode({ isIosMobile }) {
  const queryClient = useQueryClient();
  const [rankingFilters, setRankingFilters] = useState({
    season: "",
    division: "",
    gender: "",
    ageGroup: "",
    athleteName: "",
    targetTime: "",
    limit: "200",
  });
  const [rankingData, setRankingData] = useState(null);
  const [rankingLoading, setRankingLoading] = useState(false);
  const [rankingError, setRankingError] = useState("");

  const requiredFiltersReady = Boolean(
    rankingFilters.season.trim() &&
      rankingFilters.division.trim() &&
      rankingFilters.gender.trim()
  );

  const filtersQuery = useQuery({
    queryKey: [
      "rankings-filters",
      rankingFilters.season.trim(),
      rankingFilters.division.trim(),
      rankingFilters.gender.trim(),
      rankingFilters.ageGroup.trim(),
    ],
    queryFn: () =>
      fetchRankingsFilters({
        season: rankingFilters.season,
        division: rankingFilters.division,
        gender: rankingFilters.gender,
        ageGroup: rankingFilters.ageGroup,
      }),
    enabled: requiredFiltersReady,
  });

  const rankingOptions = useMemo(() => buildOptions(filtersQuery.data), [filtersQuery.data]);

  useEffect(() => {
    if (!requiredFiltersReady) {
      return;
    }
    setRankingFilters((prev) => ({
      ...prev,
      ageGroup:
        prev.ageGroup && !rankingOptions.ageGroups.includes(prev.ageGroup) ? "" : prev.ageGroup,
    }));
  }, [requiredFiltersReady, rankingOptions.ageGroups]);

  const rankingRows = useMemo(
    () => (Array.isArray(rankingData?.rows) ? rankingData.rows : []),
    [rankingData]
  );
  const locationRows = useMemo(
    () => (Array.isArray(rankingData?.locations) ? rankingData.locations : []),
    [rankingData]
  );

  const activeFilterTags = useMemo(() => {
    if (!rankingData?.filters) {
      return [];
    }
    const tags = [
      `Season ${rankingData.filters.season}`,
      `Division ${formatLabel(rankingData.filters.division)}`,
      `Gender ${formatLabel(rankingData.filters.gender)}`,
      `Top ${rankingData.limit} rows`,
    ];
    if (rankingData.filters.age_group) {
      tags.push(`Age group ${rankingData.filters.age_group}`);
    }
    if (rankingData.filters.athlete_name) {
      tags.push(`Athlete "${rankingData.filters.athlete_name}"`);
    }
    return tags;
  }, [rankingData]);

  const handleRunRankings = async (event) => {
    event.preventDefault();
    if (!requiredFiltersReady) {
      setRankingError("Season, division, and gender are required for rankings.");
      return;
    }

    setRankingLoading(true);
    setRankingError("");
    try {
      const payload = await queryClient.fetchQuery({
        queryKey: [
          "rankings",
          rankingFilters.season.trim(),
          rankingFilters.division.trim(),
          rankingFilters.gender.trim(),
          rankingFilters.ageGroup.trim(),
          rankingFilters.athleteName.trim(),
          rankingFilters.targetTime.trim(),
          rankingFilters.limit.trim(),
        ],
        queryFn: () => fetchRankings(rankingFilters),
      });
      setRankingData(payload);
      void triggerSelectionHaptic();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      setRankingError(error.message || "Unable to load rankings.");
      setRankingData(null);
    } finally {
      setRankingLoading(false);
    }
  };

  return (
    <main className="rankings-page">
      <section className="panel">
        <form className="search-form" onSubmit={handleRunRankings}>
          <div className="grid-3">
            <label className="field">
              <span>Season *</span>
              <input
                type="number"
                placeholder="8"
                value={rankingFilters.season}
                onChange={(event) =>
                  setRankingFilters((prev) => ({
                    ...prev,
                    season: event.target.value,
                  }))
                }
              />
            </label>

            <label className="field">
              <span>Division *</span>
              <input
                type="text"
                placeholder="open, pro, doubles"
                value={rankingFilters.division}
                onChange={(event) =>
                  setRankingFilters((prev) => ({
                    ...prev,
                    division: event.target.value,
                  }))
                }
              />
            </label>

            <label className="field">
              <span>Gender *</span>
              <input
                type="text"
                placeholder="female, male, mixed"
                value={rankingFilters.gender}
                onChange={(event) =>
                  setRankingFilters((prev) => ({
                    ...prev,
                    gender: event.target.value,
                  }))
                }
              />
            </label>
          </div>

          <ProgressiveSection enabled={isIosMobile} summary="Optional ranking filters">
            <div className="grid-3">
              <label className="field">
                <span>Age group (recommended)</span>
                <select
                  value={rankingFilters.ageGroup}
                  onChange={(event) =>
                    setRankingFilters((prev) => ({
                      ...prev,
                      ageGroup: event.target.value,
                    }))
                  }
                  disabled={!requiredFiltersReady || filtersQuery.isFetching}
                >
                  <option value="">
                    {filtersQuery.isFetching ? "Loading age groups..." : "Any age group"}
                  </option>
                  {rankingOptions.ageGroups.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Athlete name (DB search)</span>
                <input
                  type="text"
                  placeholder="James"
                  value={rankingFilters.athleteName}
                  onChange={(event) =>
                    setRankingFilters((prev) => ({
                      ...prev,
                      athleteName: event.target.value,
                    }))
                  }
                />
              </label>

              <label className="field">
                <span>Find placement for time (min)</span>
                <input
                  type="number"
                  step="0.01"
                  placeholder="63.5"
                  value={rankingFilters.targetTime}
                  onChange={(event) =>
                    setRankingFilters((prev) => ({
                      ...prev,
                      targetTime: event.target.value,
                    }))
                  }
                />
              </label>

              <label className="field">
                <span>Rows to return</span>
                <input
                  type="number"
                  min="1"
                  max="2000"
                  value={rankingFilters.limit}
                  onChange={(event) =>
                    setRankingFilters((prev) => ({
                      ...prev,
                      limit: event.target.value,
                    }))
                  }
                />
              </label>
            </div>
          </ProgressiveSection>

          <button className="primary" type="submit" disabled={rankingLoading}>
            {rankingLoading ? "Loading rankings..." : "Run rankings"}
          </button>
          {rankingError ? <p className="error">{rankingError}</p> : null}
        </form>

        {requiredFiltersReady ? (
          <div className="report-card">
            <h4>Locations currently in scope</h4>
            {rankingOptions.locations.length ? (
              <div className="filter-tags">
                {rankingOptions.locations.map((location) => (
                  <span key={location} className="filter-tag">
                    {formatLabel(location)}
                  </span>
                ))}
              </div>
            ) : (
              <p className="empty">No locations found for this scope yet.</p>
            )}
          </div>
        ) : null}

        {rankingLoading && !rankingData ? (
          <div className="skeleton-panel" aria-hidden="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : null}

        {rankingData ? (
          <div className="planner-results">
            <div className="report-card">
              <h4>Ranking summary</h4>
              <div className="stat-grid">
                <div>
                  <span>Total results</span>
                  <strong>{formatLabel(rankingData.count)}</strong>
                </div>
                <div>
                  <span>Total locations</span>
                  <strong>{formatLabel(rankingData.total_locations)}</strong>
                </div>
                <div>
                  <span>Rows shown</span>
                  <strong>{formatLabel(rankingRows.length)}</strong>
                </div>
              </div>
              <div className="filter-tags">
                {activeFilterTags.map((tag) => (
                  <span key={tag} className="filter-tag">
                    {tag}
                  </span>
                ))}
              </div>
              {rankingData.placement_lookup ? (
                <p className="empty">
                  A {formatMinutes(rankingData.placement_lookup.target_time_min)} finish would place #
                  {formatLabel(rankingData.placement_lookup.placement)} of {" "}
                  {formatLabel(rankingData.placement_lookup.out_of)}.
                  {rankingData.placement_lookup.exact_matches
                    ? ` Exact matches: ${rankingData.placement_lookup.exact_matches}.`
                    : ""}
                </p>
              ) : null}
            </div>

            <div className="report-card rankings-leaderboard">
              <h4>Top athlete leaderboard</h4>
              {rankingRows.length ? (
                <ol className="rankings-list">
                  {rankingRows.map((row, index) => (
                    <li key={`${row.result_id || "rank"}-${index}`} className="rankings-list-item">
                      <span className="rankings-rank">{formatLabel(row.placement)}.</span>
                      <span className="rankings-name">{formatLabel(row.name)}</span>
                      <span className="rankings-meta">
                        Time: {formatMinutes(row.total_time_min)} | {formatLabel(row.location)}
                      </span>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="empty">
                  No leaderboard rows found for this scope. Try broadening the athlete search.
                </p>
              )}
            </div>

            <div className="report-card">
              <h4>Locations considered</h4>
              {locationRows.length ? (
                <>
                  <div className="filter-tags">
                    {locationRows.map((row, index) => (
                      <span key={`${row.location || "loc"}-${index}`} className="filter-tag">
                        {formatLabel(row.location)} ({formatLabel(row.count)})
                      </span>
                    ))}
                  </div>
                  <div className="table-shell">
                    <div className="table-scroll">
                      <table className="responsive-table">
                        <thead>
                          <tr>
                            <th>Location</th>
                            <th>Rows</th>
                            <th>Fastest time</th>
                          </tr>
                        </thead>
                        <tbody>
                          {locationRows.map((row, index) => (
                            <tr key={`${row.location || "loc"}-${index}`}>
                              <td data-label="Location">{formatLabel(row.location)}</td>
                              <td data-label="Rows">{formatLabel(row.count)}</td>
                              <td data-label="Fastest time">{formatMinutes(row.fastest_time_min)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              ) : (
                <p className="empty">No locations were returned for this ranking scope.</p>
              )}
            </div>

            <div className="report-card">
              <h4>Ranking table</h4>
              {rankingRows.length ? (
                <div className="table-shell">
                  <div className="table-scroll">
                    <table className="responsive-table">
                      <thead>
                        <tr>
                          <th>Placement</th>
                          <th>Athlete</th>
                          <th>Total time</th>
                          <th>Location</th>
                          <th>Event</th>
                          <th>Year</th>
                          <th>Division</th>
                          <th>Gender</th>
                          <th>Age group</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rankingRows.map((row, index) => (
                          <tr key={`${row.result_id || "rank"}-${index}`}>
                            <td data-label="Placement">#{formatLabel(row.placement)}</td>
                            <td data-label="Athlete">{formatLabel(row.name)}</td>
                            <td data-label="Total time">{formatMinutes(row.total_time_min)}</td>
                            <td data-label="Location">{formatLabel(row.location)}</td>
                            <td data-label="Event">{formatLabel(row.event_name || row.event_id)}</td>
                            <td data-label="Year">{formatLabel(row.year)}</td>
                            <td data-label="Division">{formatLabel(row.division)}</td>
                            <td data-label="Gender">{formatLabel(row.gender)}</td>
                            <td data-label="Age group">{formatLabel(row.age_group)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <p className="empty">No ranking rows found for these filters.</p>
              )}
            </div>
          </div>
        ) : null}
      </section>
    </main>
  );
}
