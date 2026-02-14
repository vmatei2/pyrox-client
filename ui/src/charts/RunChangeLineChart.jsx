import { formatMinutes, formatDeltaMinutes } from "../utils/formatters.js";
import { toNumber } from "../utils/parsers.js";

export const RunChangeLineChart = ({ title, subtitle, series, emptyMessage }) => {
  const points = Array.isArray(series?.points) ? series.points : [];
  const validDeltas = points
    .map((point) => toNumber(point?.delta_from_median_min))
    .filter((value) => Number.isFinite(value));

  if (!points.length || !validDeltas.length) {
    return (
      <div className="chart-card">
        <div className="chart-head">
          <div>
            <h5>{title}</h5>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
        </div>
        <div className="empty">{emptyMessage || "No run pacing data available."}</div>
      </div>
    );
  }

  const width = 360;
  const height = 220;
  const padding = { left: 42, right: 16, top: 18, bottom: 42 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const maxAbs = Math.max(0.25, ...validDeltas.map((value) => Math.abs(value)));
  const yMin = -maxAbs;
  const yMax = maxAbs;
  const yRange = yMax - yMin || 1;
  const xForIndex =
    points.length <= 1
      ? () => padding.left + chartWidth / 2
      : (index) => padding.left + (chartWidth * index) / (points.length - 1);
  const yForValue = (value) => {
    const clamped = Math.max(yMin, Math.min(yMax, value));
    return padding.top + ((yMax - clamped) / yRange) * chartHeight;
  };

  let path = "";
  let started = false;
  points.forEach((point, index) => {
    const value = toNumber(point?.delta_from_median_min);
    if (!Number.isFinite(value)) {
      started = false;
      return;
    }
    const x = xForIndex(index);
    const y = yForValue(value);
    if (!started) {
      path += `M ${x} ${y}`;
      started = true;
    } else {
      path += ` L ${x} ${y}`;
    }
  });

  const yTicks = [yMax, yMax / 2, 0, yMin / 2, yMin];
  const medianRunTime = toNumber(series?.median_run_time_min);
  const minDelta = toNumber(series?.min_delta_min);
  const maxDelta = toNumber(series?.max_delta_min);

  return (
    <div className="chart-card run-change-chart">
      <div className="chart-head">
        <div>
          <h5>{title}</h5>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      </div>
      <svg className="run-change-svg" viewBox={`0 0 ${width} ${height}`} role="img">
        <g className="run-change-grid">
          {yTicks.map((tick, index) => (
            <line
              key={`tick-${index}`}
              x1={padding.left}
              x2={width - padding.right}
              y1={yForValue(tick)}
              y2={yForValue(tick)}
            />
          ))}
        </g>
        <g className="run-change-axis">
          <line x1={padding.left} x2={padding.left} y1={padding.top} y2={height - padding.bottom} />
          <line
            x1={padding.left}
            x2={width - padding.right}
            y1={height - padding.bottom}
            y2={height - padding.bottom}
          />
        </g>
        <line
          className="run-change-zero"
          x1={padding.left}
          x2={width - padding.right}
          y1={yForValue(0)}
          y2={yForValue(0)}
        />
        <g className="run-change-labels">
          {yTicks.map((tick, index) => (
            <text key={`label-${index}`} x={padding.left - 7} y={yForValue(tick) + 4} textAnchor="end">
              {formatDeltaMinutes(tick)}
            </text>
          ))}
        </g>
        <path className="run-change-path" d={path} />
        {points.map((point, index) => {
          const value = toNumber(point?.delta_from_median_min);
          const runTime = toNumber(point?.run_time_min);
          if (!Number.isFinite(value)) {
            return null;
          }
          const x = xForIndex(index);
          const y = yForValue(value);
          return (
            <circle key={`${point.run}-${index}`} className="run-change-point" cx={x} cy={y} r="3.8">
              <title>
                {point.run}: {formatDeltaMinutes(value)} vs median
                {runTime !== null ? ` (run ${formatMinutes(runTime)})` : ""}
              </title>
            </circle>
          );
        })}
        <g className="run-change-labels">
          {points.map((point, index) => {
            const x = xForIndex(index);
            return (
              <text key={`run-${point.run}-${index}`} x={x} y={height - 14} textAnchor="middle">
                {point.run}
              </text>
            );
          })}
        </g>
      </svg>
      <div className="chart-foot">
        <span>Median run (R2-R7): {formatMinutes(medianRunTime)}</span>
        <span>Fastest vs median: {formatDeltaMinutes(minDelta)}</span>
        <span>Slowest vs median: {formatDeltaMinutes(maxDelta)}</span>
      </div>
    </div>
  );
};
