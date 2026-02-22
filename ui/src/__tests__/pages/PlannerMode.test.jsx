import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../../api/client.js", () => ({
  fetchFilterOptions: vi.fn(),
  fetchPlanner: vi.fn(),
}));

vi.mock("../../utils/haptics.js", () => ({
  triggerSelectionHaptic: vi.fn(),
}));

vi.mock("../../charts/HistogramChart.jsx", () => ({
  HistogramChart: ({ title }) => <div data-testid="histogram-chart">{title}</div>,
}));

import { fetchFilterOptions, fetchPlanner } from "../../api/client.js";
import { triggerSelectionHaptic } from "../../utils/haptics.js";
import PlannerMode from "../../pages/PlannerMode.jsx";

function renderPlanner(props = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <PlannerMode {...props} />
    </QueryClientProvider>
  );
}

async function waitForPlannerFiltersReady() {
  await waitFor(() => {
    expect(screen.getByRole("combobox", { name: "Season" })).not.toBeDisabled();
    expect(screen.getByRole("combobox", { name: "Location" })).not.toBeDisabled();
    expect(screen.getByRole("combobox", { name: "Year" })).not.toBeDisabled();
    expect(screen.getByRole("combobox", { name: "Division" })).not.toBeDisabled();
    expect(screen.getByRole("combobox", { name: "Gender" })).not.toBeDisabled();
  });
}

const FILTER_OPTIONS = {
  seasons: [9, 8],
  locations: ["london", "paris"],
  years: [2025, 2024],
  divisions: ["open", "pro"],
  genders: ["female", "male"],
};

const PLANNER_PAYLOAD = {
  count: 2,
  filters: {
    season: "8",
    location: "london",
    year: "2024",
    division: "open",
    gender: "female",
    min_total_time: "60",
    max_total_time: "65",
  },
  segments: [
    {
      key: "total_time_min",
      label: "Total time",
      group: "overall",
      histogram: { bins: [], count: 2, min: 60, max: 65 },
      stats: { count: 2, mean: 62.5, min: 60, max: 65 },
    },
    {
      key: "run1_time_min",
      label: "Run 1",
      group: "runs",
      histogram: { bins: [], count: 2, min: 1.2, max: 1.8 },
      stats: { count: 2, mean: 1.5, min: 1.2, max: 1.8 },
    },
    {
      key: "skiErg_time_min",
      label: "SkiErg",
      group: "stations",
      histogram: { bins: [], count: 2, min: 4.1, max: 4.7 },
      stats: { count: 2, mean: 4.4, min: 4.1, max: 4.7 },
    },
  ],
};

describe("PlannerMode", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.scrollTo = vi.fn();
    fetchFilterOptions.mockResolvedValue(FILTER_OPTIONS);
    fetchPlanner.mockResolvedValue(PLANNER_PAYLOAD);
  });

  it("renders guidance steps and DB-driven dropdown options", async () => {
    renderPlanner();
    await waitForPlannerFiltersReady();

    expect(screen.getByText("How to use Race Planner")).toBeInTheDocument();
    expect(screen.getByText(/Choose your planning scope with season, location, and year/i)).toBeInTheDocument();

    const seasonSelect = screen.getByRole("combobox", { name: "Season" });
    const locationSelect = screen.getByRole("combobox", { name: "Location" });
    const yearSelect = screen.getByRole("combobox", { name: "Year" });

    await waitFor(() => {
      expect(seasonSelect).toHaveTextContent("8");
      expect(locationSelect).toHaveTextContent("london");
      expect(yearSelect).toHaveTextContent("2024");
    });
  });

  it("submits planner filters to API and renders result cards", async () => {
    renderPlanner();
    await waitForPlannerFiltersReady();

    fireEvent.change(screen.getByRole("combobox", { name: "Season" }), {
      target: { value: "8" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Location" }), {
      target: { value: "london" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Year" }), {
      target: { value: "2024" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Division" }), {
      target: { value: "open" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Gender" }), {
      target: { value: "female" },
    });

    const minInput = screen.getByPlaceholderText("60");
    const maxInput = screen.getByPlaceholderText("65");
    fireEvent.change(minInput, { target: { value: "60" } });
    fireEvent.change(maxInput, { target: { value: "65" } });

    fireEvent.click(screen.getByRole("button", { name: "Run planner" }));

    await waitFor(() => {
      expect(fetchPlanner).toHaveBeenCalledWith({
        season: "8",
        location: "london",
        year: "2024",
        division: "open",
        gender: "female",
        minTime: "60",
        maxTime: "65",
      });
    });

    expect(await screen.findByText("Planner age group")).toBeInTheDocument();
    expect(screen.getByText("Total time")).toBeInTheDocument();
    expect(screen.getByText("Run 1")).toBeInTheDocument();
    expect(screen.getByText("SkiErg")).toBeInTheDocument();
    expect(screen.getByText("Season 8")).toBeInTheDocument();
    expect(triggerSelectionHaptic).toHaveBeenCalled();
    expect(window.scrollTo).toHaveBeenCalled();
  });

  it("shows loading state while planner request is pending", async () => {
    let resolvePlanner;
    const pendingPlanner = new Promise((resolve) => {
      resolvePlanner = resolve;
    });
    fetchPlanner.mockReturnValueOnce(pendingPlanner);

    renderPlanner();
    await waitForPlannerFiltersReady();
    fireEvent.click(screen.getByRole("button", { name: "Run planner" }));

    expect(screen.getByRole("button", { name: "Building plan..." })).toBeDisabled();
    expect(screen.queryByText("Planner age group")).not.toBeInTheDocument();

    resolvePlanner(PLANNER_PAYLOAD);
    await waitFor(() => {
      expect(screen.getByText("Planner age group")).toBeInTheDocument();
    });
  });

  it("shows API error when planner request fails", async () => {
    fetchPlanner.mockRejectedValueOnce(new Error("Planner failed badly"));
    renderPlanner();
    await waitForPlannerFiltersReady();

    fireEvent.click(screen.getByRole("button", { name: "Run planner" }));

    expect(await screen.findByText("Planner failed badly")).toBeInTheDocument();
  });
});
