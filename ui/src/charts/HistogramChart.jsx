import { formatMinutes, formatPercent, formatLabel } from "../utils/formatters.js";

export const HistogramChart = ({ title, subtitle, histogram, stats, emptyMessage, infoTooltip }) => {
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
