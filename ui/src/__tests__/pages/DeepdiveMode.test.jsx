import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../../api/client.js", () => ({
  fetchDeepdive: vi.fn(),
  fetchDeepdiveFilters: vi.fn(),
  fetchFilterOptions: vi.fn(),
  searchAthletes: vi.fn(),
}));

vi.mock("../../utils/haptics.js", () => ({
  triggerSelectionHaptic: vi.fn(),
}));

vi.mock("../../charts/HistogramChart.jsx", () => ({
  HistogramChart: ({ title }) => <div data-testid="histogram-chart">{title}</div>,
}));

vi.mock("../../charts/StatBarChart.jsx", () => ({
  StatBarChart: ({ title }) => <div data-testid="statbar-chart">{title}</div>,
}));

import {
  fetchDeepdive,
  fetchDeepdiveFilters,
  fetchFilterOptions,
  searchAthletes,
} from "../../api/client.js";
import { triggerSelectionHaptic } from "../../utils/haptics.js";
import DeepdiveMode from "../../pages/DeepdiveMode.jsx";

function renderDeepdive(props = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <DeepdiveMode {...props} />
    </QueryClientProvider>
  );
}

async function waitForSearchFiltersReady() {
  await waitFor(() => {
    const [divisionSelect] = screen.getAllByRole("combobox", { name: "Division" });
    const [genderSelect] = screen.getAllByRole("combobox", { name: "Gender" });
    expect(divisionSelect).not.toBeDisabled();
    expect(genderSelect).not.toBeDisabled();
  });
}

const BASE_RACE = {
  result_id: "res_1",
  event_name: "London Open",
  event_id: "evt_london",
  season: 8,
  location: "london",
  year: 2025,
  division: "open",
  gender: "female",
  age_group: "30-34",
  total_time_min: 63.2,
};

const DEEPDIVE_PAYLOAD = {
  result_id: "res_1",
  race: BASE_RACE,
  athlete_value: 63.2,
  metric: "total_time_min",
  summary: { count: 10, mean: 62.1, min: 59.5, median: 61.8, max: 70.1 },
  group_summary: {
    p05: { count: 2, mean: 60.1, min: 59.5, median: 60.1, max: 60.7 },
    mean: { count: 10, mean: 62.1, min: 59.5, median: 61.8, max: 70.1 },
    podium: { count: 3, mean: 60.4, min: 59.5, median: 60.7, max: 61.0 },
    p90: { count: 1, mean: 69.8, min: 69.8, median: 69.8, max: 69.8 },
  },
  distribution: { bins: [], count: 10, min: 59.5, max: 70.1, athlete_value: 63.2 },
  group_distribution: {
    p05: { bins: [], count: 2, min: 59.5, max: 60.7, athlete_value: 63.2 },
    mean: { bins: [], count: 10, min: 59.5, max: 70.1, athlete_value: 63.2 },
    podium: { bins: [], count: 3, min: 59.5, max: 61.0, athlete_value: 63.2 },
    p90: { bins: [], count: 1, min: 69.8, max: 69.8, athlete_value: 63.2 },
  },
  filters: {
    season: 8,
    division: "open",
    gender: "female",
    age_group: "30-34",
    location: "london",
  },
  total_rows: 10,
  total_locations: 1,
  locations: [
    {
      location: "london",
      count: 10,
      seasons: 1,
      years: 1,
      p05: 60.7,
      podium: 61.0,
      p90: 69.8,
      mean: 62.1,
      fastest: 59.5,
    },
  ],
};

describe("DeepdiveMode", () => {
  beforeEach(() => {
    window.scrollTo = vi.fn();
    vi.clearAllMocks();

    fetchFilterOptions.mockResolvedValue({
      divisions: ["open", "pro"],
      genders: ["female", "male"],
    });
    fetchDeepdiveFilters.mockResolvedValue({
      locations: ["london", "paris"],
      age_groups: ["30-34", "35-39"],
    });
    searchAthletes.mockResolvedValue({ races: [BASE_RACE] });
    fetchDeepdive.mockResolvedValue(DEEPDIVE_PAYLOAD);
  });

  it("renders step guidance and DB-driven dropdown options", async () => {
    renderDeepdive();

    expect(screen.getByText("How to use Deep Dive")).toBeInTheDocument();
    expect(screen.getByText(/Find your athlete and choose a base race/i)).toBeInTheDocument();

    const divisionSelects = screen.getAllByRole("combobox", { name: "Division" });
    const genderSelects = screen.getAllByRole("combobox", { name: "Gender" });

    await waitFor(() => {
      expect(within(divisionSelects[0]).getByRole("option", { name: "open" })).toBeInTheDocument();
      expect(within(genderSelects[0]).getByRole("option", { name: "female" })).toBeInTheDocument();
    });
  });

  it("shows validation when searching without athlete name", async () => {
    renderDeepdive();

    fireEvent.click(screen.getByRole("button", { name: "Search races" }));

    expect(screen.getByText("Enter an athlete name to search.")).toBeInTheDocument();
    expect(searchAthletes).not.toHaveBeenCalled();
  });

  it("runs athlete search and renders base race results", async () => {
    renderDeepdive();
    await waitForSearchFiltersReady();

    fireEvent.change(screen.getByRole("textbox", { name: "Athlete name" }), {
      target: { value: "Sarah Johnson" },
    });
    const [searchDivision] = screen.getAllByRole("combobox", { name: "Division" });
    const [searchGender] = screen.getAllByRole("combobox", { name: "Gender" });
    fireEvent.change(searchDivision, { target: { value: "open" } });
    fireEvent.change(searchGender, { target: { value: "female" } });

    fireEvent.click(screen.getByRole("button", { name: "Search races" }));

    await waitFor(() => {
      expect(searchAthletes).toHaveBeenCalledWith("Sarah Johnson", {
        match: "best",
        division: "open",
        gender: "female",
        requireUnique: false,
      });
    });
    expect(screen.getByText("London Open")).toBeInTheDocument();
  });

  it("prefills deepdive filters when a base race is selected", async () => {
    renderDeepdive();
    await waitForSearchFiltersReady();

    fireEvent.change(screen.getByRole("textbox", { name: "Athlete name" }), {
      target: { value: "Sarah Johnson" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search races" }));

    const raceButton = await screen.findByRole("button", { name: /London Open/i });
    fireEvent.click(raceButton);

    const seasonInput = screen.getByRole("spinbutton", { name: "Season *" });
    const [, filtersDivision] = screen.getAllByRole("combobox", { name: "Division" });
    const [, filtersGender] = screen.getAllByRole("combobox", { name: "Gender" });
    const ageGroupSelect = screen.getByRole("combobox", { name: "Age group" });

    expect(seasonInput).toHaveValue(8);
    expect(filtersDivision).toHaveValue("open");
    expect(filtersGender).toHaveValue("female");
    await waitFor(() => {
      expect(ageGroupSelect).toHaveValue("30-34");
    });
    expect(triggerSelectionHaptic).toHaveBeenCalled();
  });

  it("shows validation when running deepdive without base race", () => {
    const { container } = renderDeepdive();

    const forms = container.querySelectorAll("form");
    fireEvent.submit(forms[1]);

    expect(screen.getByText("Pick a base race for the deepdive.")).toBeInTheDocument();
    expect(fetchDeepdive).not.toHaveBeenCalled();
  });

  it("shows validation when running deepdive without season", async () => {
    const raceWithoutSeason = { ...BASE_RACE, season: null };
    searchAthletes.mockResolvedValueOnce({ races: [raceWithoutSeason] });

    const { container } = renderDeepdive();
    await waitForSearchFiltersReady();

    fireEvent.change(screen.getByRole("textbox", { name: "Athlete name" }), {
      target: { value: "Sarah Johnson" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search races" }));
    fireEvent.click(await screen.findByRole("button", { name: /London Open/i }));

    const forms = container.querySelectorAll("form");
    fireEvent.submit(forms[1]);

    expect(screen.getByText("Season is required for deepdive analysis.")).toBeInTheDocument();
    expect(fetchDeepdive).not.toHaveBeenCalled();
  });

  it("runs deepdive successfully and renders summary cards", async () => {
    const { container } = renderDeepdive();
    await waitForSearchFiltersReady();

    fireEvent.change(screen.getByRole("textbox", { name: "Athlete name" }), {
      target: { value: "Sarah Johnson" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search races" }));
    fireEvent.click(await screen.findByRole("button", { name: /London Open/i }));
    await waitFor(() => {
      expect(screen.getByRole("spinbutton", { name: "Season *" })).toHaveValue(8);
    });

    const forms = container.querySelectorAll("form");
    fireEvent.submit(forms[1]);

    await waitFor(() => {
      expect(fetchDeepdive).toHaveBeenCalledTimes(1);
    });
    const [resultId, payload] = fetchDeepdive.mock.calls[0];
    expect(resultId).toBe("res_1");
    expect(payload).toEqual(
      expect.objectContaining({
        season: "8",
        division: "open",
        gender: "female",
        ageGroup: "30-34",
      })
    );
    expect(await screen.findByText("Deepdive summary")).toBeInTheDocument();
    expect(screen.getByText("Metric distribution")).toBeInTheDocument();
    expect(screen.getByText("Metric comparison")).toBeInTheDocument();
    expect(screen.getByText("Location targets (Top 5%)")).toBeInTheDocument();
    expect(window.scrollTo).toHaveBeenCalled();
  });

  it("shows API error message when athlete search fails", async () => {
    searchAthletes.mockRejectedValueOnce(new Error("Search failed badly"));
    renderDeepdive();
    await waitForSearchFiltersReady();

    fireEvent.change(screen.getByRole("textbox", { name: "Athlete name" }), {
      target: { value: "Sarah Johnson" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search races" }));
    expect(await screen.findByText("Search failed badly")).toBeInTheDocument();
  });

  it("shows API error message when deepdive request fails", async () => {
    searchAthletes.mockResolvedValueOnce({ races: [BASE_RACE] });
    fetchDeepdive.mockRejectedValueOnce(new Error("Deepdive failed badly"));
    const { container } = renderDeepdive();
    await waitForSearchFiltersReady();

    fireEvent.change(screen.getByRole("textbox", { name: "Athlete name" }), {
      target: { value: "Sarah Johnson" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search races" }));
    fireEvent.click(await screen.findByRole("button", { name: /London Open/i }));
    await waitFor(() => {
      expect(screen.getByRole("spinbutton", { name: "Season *" })).toHaveValue(8);
    });

    const forms = container.querySelectorAll("form");
    fireEvent.submit(forms[1]);

    expect(await screen.findByText("Deepdive failed badly")).toBeInTheDocument();
  });
});
