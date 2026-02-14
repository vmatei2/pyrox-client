import { formatMinutes } from "../utils/formatters.js";

export const StatBarChart = ({ title, subtitle, items = [], emptyMessage, infoTooltip }) => {
  const hasValues = items.some((item) => Number.isFinite(item.value));
  if (!items.length || !hasValues) {
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
        <div className="empty">{emptyMessage || "No data available."}</div>
      </div>
    );
  }

  const values = items.map((item) => (Number.isFinite(item.value) ? item.value : 0));
  const maxValue = Math.max(0, ...values);

  return (
    <div className="chart-card stat-bar-chart">
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
      <div className="stat-bars">
        {items.map((item) => {
          const value = Number.isFinite(item.value) ? item.value : 0;
          const height = maxValue > 0 ? (value / maxValue) * 100 : 0;
          return (
            <div key={item.label} className="stat-bar-item">
              <div
                className={`stat-bar${item.accent ? " is-accent" : ""}${
                  Number.isFinite(item.value) ? "" : " is-empty"
                }`}
                style={{ height: `${height}%` }}
              >
                <span>{formatMinutes(item.value)}</span>
              </div>
              <div className="stat-bar-label">{item.label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
