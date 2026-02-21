import { useEffect, useState } from "react";
import { formatMinutes, formatPercent } from "../utils/formatters.js";
import { toNumber } from "../utils/parsers.js";

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

export const WorkRunSplitPieChart = ({ title, subtitle, split, emptyMessage }) => {
  const workPct = toNumber(split?.work_pct);
  const runPct = toNumber(split?.run_pct);
  const workMinutes = toNumber(split?.work_time_min);
  const runMinutes = toNumber(split?.run_time_with_roxzone_min);
  const totalMinutes = toNumber(split?.total_time_min);
  const hasData = Number.isFinite(workPct) && Number.isFinite(runPct);

  if (!hasData) {
    return (
      <div className="chart-card">
        <div className="chart-head">
          <div>
            <h5>{title}</h5>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
        </div>
        <div className="empty">{emptyMessage || "No work/run split data available."}</div>
      </div>
    );
  }

  const safeWorkPct = Math.min(1, Math.max(0, workPct));
  const safeRunPct = Math.min(1, Math.max(0, runPct));
  const targetDegrees = safeWorkPct * 360;

  const [animatedDeg, setAnimatedDeg] = useState(0);
  useEffect(() => {
    const prefersReduced =
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) {
      setAnimatedDeg(targetDegrees);
      return;
    }
    let start = null;
    let raf;
    const duration = 600;
    const animate = (ts) => {
      if (!start) start = ts;
      const progress = Math.min((ts - start) / duration, 1);
      setAnimatedDeg(easeOutCubic(progress) * targetDegrees);
      if (progress < 1) raf = requestAnimationFrame(animate);
    };
    raf = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf);
  }, [targetDegrees]);

  const pieStyle = {
    background: `conic-gradient(var(--accent-cool) 0deg ${animatedDeg}deg, var(--accent-strong) ${animatedDeg}deg 360deg)`,
  };

  return (
    <div className="chart-card pie-chart-card">
      <div className="chart-head">
        <div>
          <h5>{title}</h5>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      </div>
      <div className="work-run-pie-wrap">
        <div
          className="work-run-pie"
          style={pieStyle}
          role="img"
          aria-label={`Work ${formatPercent(safeWorkPct)}, Run plus Roxzone ${formatPercent(
            safeRunPct
          )}`}
        >
          <div className="work-run-pie-center">
            <span>Total</span>
            <strong>{formatMinutes(totalMinutes)}</strong>
          </div>
        </div>
        <div className="work-run-legend">
          <div className="work-run-legend-item">
            <span className="work-run-swatch is-work" />
            <div>
              <strong>Work time</strong>
              <p>
                {formatPercent(safeWorkPct)} • {formatMinutes(workMinutes)}
              </p>
            </div>
          </div>
          <div className="work-run-legend-item">
            <span className="work-run-swatch is-run" />
            <div>
              <strong>Runs + Roxzone</strong>
              <p>
                {formatPercent(safeRunPct)} • {formatMinutes(runMinutes)}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
