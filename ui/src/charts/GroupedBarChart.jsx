import { formatMinutes } from "../utils/formatters.js";

export const GroupedBarChart = ({
  title,
  subtitle,
  segments = [],
  baseLabel,
  compareLabel,
  emptyMessage,
}) => {
  const values = segments
    .flatMap((segment) => [segment.baseValue, segment.compareValue])
    .map((value) => (Number.isFinite(value) ? value : 0));
  const maxValue = Math.max(0, ...values);
  if (!segments.length || maxValue === 0) {
    return (
      <div className="chart-card compare-chart">
        <div className="chart-head">
          <div>
            <h5>{title}</h5>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
        </div>
        <div className="empty">{emptyMessage || "No data available."}</div>
      </div>
    );
  }

  const tickCount = 4;
  const maxScale = maxValue;
  const step = maxScale / tickCount;
  const ticks = Array.from({ length: tickCount + 1 }, (_, index) => maxScale - step * index);

  return (
    <div className="chart-card compare-chart">
      <div className="chart-head">
        <div>
          <h5>{title}</h5>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      </div>
      <div className="compare-legend">
        <span className="legend-item">
          <span className="legend-swatch is-base" />
          {baseLabel}
        </span>
        <span className="legend-item">
          <span className="legend-swatch is-compare" />
          {compareLabel}
        </span>
      </div>
      <div className="grouped-chart-wrap">
        <div className="grouped-axis">
          {ticks.map((tick, index) => (
            <div key={`${tick}-${index}`} className="grouped-axis-tick">
              {formatMinutes(tick)}
            </div>
          ))}
        </div>
        <div className="grouped-chart-area">
          <div className="grouped-chart-inner">
            <div className="grouped-grid">
              {ticks.map((tick, index) => {
                const position = (index / tickCount) * 100;
                return (
                  <div
                    key={`${tick}-${index}`}
                    className="grouped-grid-line"
                    style={{ bottom: `${100 - position}%` }}
                  />
                );
              })}
            </div>
            <div className="grouped-chart-bars">
              {segments.map((segment) => {
                const baseValue = Number.isFinite(segment.baseValue) ? segment.baseValue : 0;
                const compareValue = Number.isFinite(segment.compareValue)
                  ? segment.compareValue
                  : 0;
                const baseHeight = maxScale > 0 ? (baseValue / maxScale) * 100 : 0;
                const compareHeight = maxScale > 0 ? (compareValue / maxScale) * 100 : 0;
                return (
                  <div key={segment.key} className="grouped-group">
                    <div className="grouped-bars">
                      <div
                        className="grouped-bar is-base"
                        style={{ height: `${baseHeight}%`, background: segment.color }}
                        title={`${baseLabel} ${segment.label}: ${formatMinutes(baseValue)}`}
                        data-value={formatMinutes(baseValue)}
                        aria-label={`${segment.label} ${baseLabel}: ${formatMinutes(baseValue)}`}
                      />
                      <div
                        className="grouped-bar is-compare"
                        style={{ height: `${compareHeight}%`, background: segment.color }}
                        title={`${compareLabel} ${segment.label}: ${formatMinutes(compareValue)}`}
                        data-value={formatMinutes(compareValue)}
                        aria-label={`${segment.label} ${compareLabel}: ${formatMinutes(compareValue)}`}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="grouped-x-axis" />
            <div className="grouped-label-row">
              {segments.map((segment) => (
                <div key={`${segment.key}-label`} className="grouped-label">
                  {segment.label}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
