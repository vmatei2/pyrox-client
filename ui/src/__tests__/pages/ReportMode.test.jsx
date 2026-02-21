import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../../api/client.js", () => ({
  searchAthletes: vi.fn(),
  fetchReport: vi.fn(),
}));

vi.mock("../../utils/haptics.js", () => ({
  triggerSelectionHaptic: vi.fn(),
}));

vi.mock("../../components/UiPrimitives.jsx", () => ({
  AnimatedNumber: ({ value, formatter }) => {
    if (value === null || value === undefined || !Number.isFinite(value)) return "—";
    return formatter ? formatter(value) : String(value);
  },
  FlowSteps: () => null,
  HelpSheet: () => null,
  ProgressiveSection: ({ children }) => <>{children}</>,
  ReportCardHeader: ({ title }) => <h4>{title}</h4>,
}));

vi.mock("../../charts/HistogramChart.jsx", () => ({
  HistogramChart: () => null,
}));

vi.mock("../../charts/PercentileLineChart.jsx", () => ({
  PercentileLineChart: () => null,
}));

vi.mock("../../charts/WorkRunSplitPieChart.jsx", () => ({
  WorkRunSplitPieChart: () => null,
}));

vi.mock("../../charts/RunChangeLineChart.jsx", () => ({
  RunChangeLineChart: () => null,
}));

import { fetchReport } from "../../api/client.js";
import ReportMode from "../../pages/ReportMode.jsx";

function renderReportMode(props = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ReportMode {...props} />
    </QueryClientProvider>
  );
}

function buildMockReport(overrides = {}) {
  return {
    race: {
      result_id: "result_1",
      name: "Sarah Johnson",
      event_name: "London",
      event_id: "evt_london",
      location: "london",
      season: 8,
      year: 2025,
      total_time_min: 84.55,
      ...overrides,
    },
    splits: [],
    distributions: {},
    plot_data: {},
    cohort_stats: null,
    cohort_time_window_stats: null,
    cohort_time_window_min: 5,
  };
}

describe("ReportMode pending race jump", () => {
  beforeEach(() => {
    window.scrollTo = vi.fn();
  });

  it("loads the report immediately when pendingRaceJump is provided", async () => {
    const onRaceJumpHandled = vi.fn();
    fetchReport.mockResolvedValueOnce(buildMockReport());

    renderReportMode({
      pendingRaceJump: "result_1",
      onRaceJumpHandled,
    });

    await waitFor(() => {
      expect(fetchReport).toHaveBeenCalledWith("result_1", { timeWindow: "5" });
    });
    await waitFor(() => {
      expect(onRaceJumpHandled).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(screen.getByText("Race report")).toBeInTheDocument();
    });
  });
});

describe("Percentile callout banner", () => {
  beforeEach(() => {
    window.scrollTo = vi.fn();
  });

  it("shows the callout when event_percentile is above 50%", async () => {
    fetchReport.mockResolvedValueOnce(
      buildMockReport({ event_percentile: 0.785 })
    );

    renderReportMode({ pendingRaceJump: "result_1", onRaceJumpHandled: vi.fn() });

    await waitFor(() => {
      expect(screen.getByText(/You finished ahead of/)).toBeInTheDocument();
    });
    const callout = screen.getByText(/You finished ahead of/).closest(".percentile-callout");
    expect(within(callout).getByText("78.5%")).toBeInTheDocument();
    expect(screen.getByText(/of athletes in your age group/)).toBeInTheDocument();
  });

  it("does not show the callout when event_percentile is below 50%", async () => {
    fetchReport.mockResolvedValueOnce(
      buildMockReport({ event_percentile: 0.3 })
    );

    renderReportMode({ pendingRaceJump: "result_1", onRaceJumpHandled: vi.fn() });

    await waitFor(() => {
      expect(screen.getByText("Race report")).toBeInTheDocument();
    });
    expect(screen.queryByText(/You finished ahead of/)).not.toBeInTheDocument();
  });

  it("does not show the callout when event_percentile is missing", async () => {
    fetchReport.mockResolvedValueOnce(buildMockReport());

    renderReportMode({ pendingRaceJump: "result_1", onRaceJumpHandled: vi.fn() });

    await waitFor(() => {
      expect(screen.getByText("Race report")).toBeInTheDocument();
    });
    expect(screen.queryByText(/You finished ahead of/)).not.toBeInTheDocument();
  });

  it("shows the callout at exactly 50%", async () => {
    fetchReport.mockResolvedValueOnce(
      buildMockReport({ event_percentile: 0.5 })
    );

    renderReportMode({ pendingRaceJump: "result_1", onRaceJumpHandled: vi.fn() });

    await waitFor(() => {
      expect(screen.getByText(/You finished ahead of/)).toBeInTheDocument();
    });
    const callout = screen.getByText(/You finished ahead of/).closest(".percentile-callout");
    expect(within(callout).getByText("50.0%")).toBeInTheDocument();
  });

  it("applies the correct color class for top 10% percentile", async () => {
    fetchReport.mockResolvedValueOnce(
      buildMockReport({ event_percentile: 0.95 })
    );

    renderReportMode({ pendingRaceJump: "result_1", onRaceJumpHandled: vi.fn() });

    await waitFor(() => {
      expect(screen.getByText(/You finished ahead of/)).toBeInTheDocument();
    });
    const callout = screen.getByText(/You finished ahead of/).closest(".percentile-callout");
    expect(callout).toHaveClass("perc-excellent");
  });

  it("applies the correct color class for top 25% percentile", async () => {
    fetchReport.mockResolvedValueOnce(
      buildMockReport({ event_percentile: 0.8 })
    );

    renderReportMode({ pendingRaceJump: "result_1", onRaceJumpHandled: vi.fn() });

    await waitFor(() => {
      expect(screen.getByText(/You finished ahead of/)).toBeInTheDocument();
    });
    const callout = screen.getByText(/You finished ahead of/).closest(".percentile-callout");
    expect(callout).toHaveClass("perc-good");
  });
});

