import { useRef, useState } from "react";

export const PercentileLineChart = ({ title, subtitle, series, emptyMessage }) => {
  const containerRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);
  const hasData = series.some(
    (item) => Number.isFinite(item.cohort) || Number.isFinite(item.window)
  );
  if (!series.length || !hasData) {
    return (
      <div className="chart-card">
        <div className="chart-head">
          <div>
            <h5>{title}</h5>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
        </div>
        <div className="empty">{emptyMessage || "No percentile data available."}</div>
      </div>
    );
  }

  const width = 360;
  const height = 220;
  const padding = { left: 38, right: 14, top: 16, bottom: 40 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const count = series.length;
  const xForIndex =
    count <= 1
      ? () => padding.left + chartWidth / 2
      : (index) => padding.left + (chartWidth * index) / (count - 1);
  const clampPercent = (value) => Math.min(100, Math.max(0, value));
  const yForValue = (value) =>
    padding.top + chartHeight - (clampPercent(value) / 100) * chartHeight;

  const buildPath = (field) => {
    let path = "";
    let started = false;
    series.forEach((item, index) => {
      const rawValue = item[field];
      if (!Number.isFinite(rawValue)) {
        started = false;
        return;
      }
      const x = xForIndex(index);
      const y = yForValue(rawValue);
      if (!started) {
        path += `M ${x} ${y}`;
        started = true;
      } else {
        path += ` L ${x} ${y}`;
      }
    });
    return path;
  };

  const splitLabel = (label) => {
    const parts = String(label).split(" ");
    if (parts.length <= 1) {
      return [label];
    }
    if (parts.length === 2) {
      return parts;
    }
    const mid = Math.ceil(parts.length / 2);
    return [parts.slice(0, mid).join(" "), parts.slice(mid).join(" ")];
  };

  const yTicks = [100, 50, 0];
  const formatPercentValue = (value) => {
    if (!Number.isFinite(value)) {
      return "-";
    }
    return `${value.toFixed(1)}%`;
  };
  const showTooltip = (event, text) => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    const rect = container.getBoundingClientRect();
    setTooltip({
      text,
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    });
  };
  const clearTooltip = () => setTooltip(null);

  return (
    <div className="chart-card percentile-chart">
      <div className="chart-head">
        <div>
          <h5>{title}</h5>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      </div>
      <div className="percentile-legend">
        <span className="legend-item">
          <span className="legend-line is-cohort" />
          Age group percentile
        </span>
        <span className="legend-item">
          <span className="legend-line is-window" />
          Time window percentile
        </span>
      </div>
      <div className="percentile-chart-wrap" ref={containerRef} onMouseLeave={clearTooltip}>
        <svg className="percentile-svg" viewBox={`0 0 ${width} ${height}`} role="img">
          <g className="percentile-grid">
            {yTicks.map((tick) => {
              const y = yForValue(tick);
              return (
                <line
                  key={`grid-${tick}`}
                  x1={padding.left}
                  x2={width - padding.right}
                  y1={y}
                  y2={y}
                />
              );
            })}
          </g>
          <g className="percentile-axis">
            <line
              x1={padding.left}
              x2={padding.left}
              y1={padding.top}
              y2={height - padding.bottom}
            />
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={height - padding.bottom}
              y2={height - padding.bottom}
            />
          </g>
          <g className="percentile-axis-labels">
            {yTicks.map((tick) => {
              const y = yForValue(tick);
              return (
                <text key={`label-${tick}`} x={padding.left - 6} y={y + 4} textAnchor="end">
                  {tick}
                </text>
              );
            })}
          </g>
          <path
            className="percentile-line is-cohort"
            d={buildPath("cohort")}
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            className="percentile-line is-window"
            d={buildPath("window")}
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {series.map((item, index) => {
            const x = xForIndex(index);
            const cohortValue = Number.isFinite(item.cohort) ? item.cohort : null;
            const windowValue = Number.isFinite(item.window) ? item.window : null;
            return (
              <g key={`points-${item.label}`}>
                {cohortValue !== null ? (
                  <g>
                    <circle
                      className="percentile-hit"
                      cx={x}
                      cy={yForValue(cohortValue)}
                      r="10"
                      onMouseMove={(event) =>
                        showTooltip(
                          event,
                          `${item.label} age group: ${formatPercentValue(cohortValue)}`
                        )
                      }
                    />
                    <circle
                      className="percentile-point is-cohort"
                      cx={x}
                      cy={yForValue(cohortValue)}
                      r="3.5"
                    />
                  </g>
                ) : null}
                {windowValue !== null ? (
                  <g>
                    <circle
                      className="percentile-hit"
                      cx={x}
                      cy={yForValue(windowValue)}
                      r="10"
                      onMouseMove={(event) =>
                        showTooltip(
                          event,
                          `${item.label} window: ${formatPercentValue(windowValue)}`
                        )
                      }
                    />
                    <circle
                      className="percentile-point is-window"
                      cx={x}
                      cy={yForValue(windowValue)}
                      r="3.5"
                    />
                  </g>
                ) : null}
              </g>
            );
          })}
          <g className="percentile-axis-labels">
            {series.map((item, index) => {
              const x = xForIndex(index);
              const lines = splitLabel(item.label);
              const firstLineY = height - 14 - (lines.length - 1) * 10;
              return (
                <text key={`x-${item.label}`} x={x} y={firstLineY} textAnchor="middle">
                  {lines.map((line, lineIndex) => (
                    <tspan key={`${item.label}-${lineIndex}`} x={x} dy={lineIndex ? 10 : 0}>
                      {line}
                    </tspan>
                  ))}
                </text>
              );
            })}
          </g>
        </svg>
        {tooltip ? (
          <div className="percentile-tooltip" style={{ left: tooltip.x, top: tooltip.y }}>
            {tooltip.text}
          </div>
        ) : null}
      </div>
    </div>
  );
};
