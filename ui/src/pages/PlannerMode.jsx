import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ProgressiveSection } from "../components/UiPrimitives.jsx";
import { formatLabel } from "../utils/formatters.js";
import { fetchPlanner } from "../api/client.js";
import { triggerSelectionHaptic } from "../utils/haptics.js";
import { HistogramChart } from "../charts/HistogramChart.jsx";

export default function PlannerMode({ isIosMobile }) {
  const queryClient = useQueryClient();
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

  const handlePlannerSearch = async (event) => {
    event.preventDefault();
    setPlannerLoading(true);
    setPlannerError("");
    try {
      const payload = await queryClient.fetchQuery({
        queryKey: [
          "planner",
          plannerFilters.season.trim(),
          plannerFilters.location.trim(),
          plannerFilters.year.trim(),
          plannerFilters.division.trim(),
          plannerFilters.gender.trim(),
          plannerFilters.minTime.trim(),
          plannerFilters.maxTime.trim(),
        ],
        queryFn: () => fetchPlanner(plannerFilters),
      });
      setPlannerData(payload);
      void triggerSelectionHaptic();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      setPlannerError(error.message || "Planner query failed.");
      setPlannerData(null);
    } finally {
      setPlannerLoading(false);
    }
  };

  return (
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

        {plannerLoading && !plannerData ? (
          <div className="skeleton-panel" aria-hidden="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : null}

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
  );
}

