import { useEffect } from "react";

const CardHelpButton = ({ onClick }) => (
  <button type="button" className="card-help-button" onClick={onClick}>
    How calculated
  </button>
);

const ReportCardHeader = ({ title, helpKey, onOpenHelp }) => (
  <div className="report-card-head">
    <h4>{title}</h4>
    {helpKey ? <CardHelpButton onClick={() => onOpenHelp(helpKey)} /> : null}
  </div>
);

const HelpSheet = ({ content, onClose }) => {
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="help-sheet-backdrop" onClick={onClose} role="presentation">
      <div
        className="help-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-sheet-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="help-sheet-handle" />
        <div className="help-sheet-header">
          <h4 id="help-sheet-title">{content.title}</h4>
          <button type="button" className="help-sheet-close" onClick={onClose}>
            Close
          </button>
        </div>
        <p className="help-sheet-summary">{content.summary}</p>
        {Array.isArray(content.bullets) && content.bullets.length ? (
          <ul className="help-sheet-list">
            {content.bullets.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : null}
        {content.formula ? (
          <p className="help-sheet-formula">
            <span>Formula:</span> <code>{content.formula}</code>
          </p>
        ) : null}
      </div>
    </div>
  );
};

const ProgressiveSection = ({ enabled, summary, children, defaultOpen = false }) => {
  if (!enabled) {
    return <>{children}</>;
  }
  return (
    <details className="form-advanced" open={defaultOpen}>
      <summary>{summary}</summary>
      <div className="form-advanced-content">{children}</div>
    </details>
  );
};

const FlowSteps = ({ steps = [] }) => {
  if (!steps.length) {
    return null;
  }
  return (
    <ol className="flow-steps" aria-label="Workflow steps">
      {steps.map((step, index) => (
        <li key={step} className="flow-step">
          <span className="flow-step-index">{index + 1}</span>
          <span>{step}</span>
        </li>
      ))}
    </ol>
  );
};

const ModeTabIcon = ({ kind }) => {
  if (kind === "report") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="4" y="4" width="16" height="16" rx="4" />
        <path d="M8 9h8" />
        <path d="M8 13h8" />
        <path d="M8 17h5" />
      </svg>
    );
  }
  if (kind === "compare") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 7h6v12H5z" />
        <path d="M13 5h6v14h-6z" />
      </svg>
    );
  }
  if (kind === "deepdive") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="11" cy="11" r="6" />
        <path d="M15.5 15.5L20 20" />
      </svg>
    );
  }
  if (kind === "rankings") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7 6h10" />
        <path d="M9 6v4l3 2 3-2V6" />
        <path d="M10 14h4" />
        <path d="M9 18h6" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 18h14" />
      <path d="M7 18v-6" />
      <path d="M12 18v-10" />
      <path d="M17 18v-4" />
    </svg>
  );
};

export { FlowSteps, HelpSheet, ModeTabIcon, ProgressiveSection, ReportCardHeader };
