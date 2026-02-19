import { useState } from "react";
import { formatMinutes } from "../utils/formatters.js";

const VIEW_W = 400;
const VIEW_H = 160;
const PAD = { top: 16, right: 20, bottom: 36, left: 56 };
const PLOT_W = VIEW_W - PAD.left - PAD.right;
const PLOT_H = VIEW_H - PAD.top - PAD.bottom;

function computePoints(sorted, minTime, timeRange) {
  return sorted.map((s, i) => {
    const x =
      PAD.left +
      (sorted.length === 1 ? PLOT_W / 2 : (i / (sorted.length - 1)) * PLOT_W);
    // Invert Y: lower time (better) = higher on chart
    const y = PAD.top + ((s.best_time - minTime) / (timeRange || 1)) * PLOT_H;
    return { ...s, x, y };
  });
}

export function SeasonProgressionChart({ seasons = [] }) {
  const [hovered, setHovered] = useState(null);

  const validSeasons = (seasons || []).filter(
    (s) => s && typeof s.best_time === "number" && isFinite(s.best_time)
  );

  if (validSeasons.length === 0) {
    return <p className="empty">No season data available yet.</p>;
  }

  const sorted = [...validSeasons].sort((a, b) =>
    String(a.season).localeCompare(String(b.season))
  );

  const times = sorted.map((s) => s.best_time);
  const minTime = Math.min(...times);
  const maxTime = Math.max(...times);
  const timeRange = maxTime - minTime;

  const points = computePoints(sorted, minTime, timeRange);

  const linePath = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(" ");

  const areaPath =
    points.length >= 2
      ? `${linePath} L ${points[points.length - 1].x.toFixed(1)} ${(PAD.top + PLOT_H).toFixed(1)} L ${points[0].x.toFixed(1)} ${(PAD.top + PLOT_H).toFixed(1)} Z`
      : null;

  const isImproving =
    sorted.length >= 2 &&
    sorted[sorted.length - 1].best_time < sorted[0].best_time;

  const bottomY = PAD.top + PLOT_H;

  return (
    <div className="season-chart-wrap">
      <div className="season-chart-trend">
        {sorted.length >= 2 && isImproving && (
          <span className="season-trend-improving">↑ Improving</span>
        )}
        {sorted.length >= 2 && !isImproving && (
          <span className="season-trend-flat">— Stable</span>
        )}
      </div>
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        className="season-chart-svg"
        aria-label="Season-over-season progression chart"
        role="img"
        onMouseLeave={() => setHovered(null)}
      >
        <defs>
          <linearGradient id="spc-area-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0a84ff" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#0a84ff" stopOpacity="0.01" />
          </linearGradient>
          <filter id="spc-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Horizontal grid lines */}
        {[0, 0.5, 1].map((frac) => {
          const y = PAD.top + frac * PLOT_H;
          return (
            <line
              key={frac}
              x1={PAD.left}
              y1={y.toFixed(1)}
              x2={VIEW_W - PAD.right}
              y2={y.toFixed(1)}
              stroke="rgba(156,177,214,0.1)"
              strokeWidth="1"
              strokeDasharray={frac > 0 && frac < 1 ? "4 4" : undefined}
            />
          );
        })}

        {/* Y-axis labels */}
        <text
          x={PAD.left - 6}
          y={PAD.top + 4}
          textAnchor="end"
          className="season-axis-label"
        >
          {formatMinutes(minTime)}
        </text>
        {timeRange > 0 && (
          <text
            x={PAD.left - 6}
            y={bottomY + 4}
            textAnchor="end"
            className="season-axis-label"
          >
            {formatMinutes(maxTime)}
          </text>
        )}

        {/* Area fill */}
        {areaPath && <path d={areaPath} fill="url(#spc-area-grad)" />}

        {/* Line */}
        {points.length >= 2 && (
          <path
            d={linePath}
            fill="none"
            stroke="#0a84ff"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            filter="url(#spc-glow)"
          />
        )}

        {/* Data points and x-axis labels */}
        {points.map((p) => (
          <g key={p.season}>
            <text
              x={p.x.toFixed(1)}
              y={VIEW_H - 6}
              textAnchor="middle"
              className="season-axis-label"
            >
              {p.season}
            </text>
            <circle
              cx={p.x.toFixed(1)}
              cy={p.y.toFixed(1)}
              r="5"
              fill="#090f1b"
              stroke="#0a84ff"
              strokeWidth="2.5"
              style={{ cursor: "pointer" }}
              onMouseEnter={() => setHovered(p)}
              aria-label={`${p.season}: ${formatMinutes(p.best_time)}`}
            />
          </g>
        ))}

        {/* Hover tooltip */}
        {hovered && (() => {
          const tx = Math.min(hovered.x + 12, VIEW_W - 114);
          const ty = Math.max(hovered.y - 48, PAD.top);
          return (
            <g role="tooltip" aria-live="polite">
              <rect
                x={tx}
                y={ty}
                width={104}
                height={42}
                rx="7"
                fill="rgba(8,14,25,0.97)"
                stroke="rgba(156,177,214,0.22)"
                strokeWidth="1"
              />
              <text x={tx + 10} y={ty + 15} className="season-tooltip-label">
                {hovered.season}
              </text>
              <text x={tx + 10} y={ty + 31} className="season-tooltip-value">
                {formatMinutes(hovered.best_time)}
              </text>
            </g>
          );
        })()}
      </svg>
    </div>
  );
}
