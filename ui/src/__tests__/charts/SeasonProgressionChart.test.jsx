import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SeasonProgressionChart } from "../../charts/SeasonProgressionChart.jsx";

const THREE_SEASONS = [
  { season: "2023", best_time: 90.5, race_count: 3 },
  { season: "2024", best_time: 87.2, race_count: 5 },
  { season: "2025", best_time: 84.55, race_count: 2 },
];

const DECLINING_SEASONS = [
  { season: "2023", best_time: 84.0, race_count: 3 },
  { season: "2024", best_time: 87.5, race_count: 2 },
];

describe("SeasonProgressionChart", () => {
  it("renders empty state when seasons prop is an empty array", () => {
    render(<SeasonProgressionChart seasons={[]} />);
    expect(screen.getByText("No season data available yet.")).toBeInTheDocument();
  });

  it("renders empty state when seasons prop is omitted", () => {
    render(<SeasonProgressionChart />);
    expect(screen.getByText("No season data available yet.")).toBeInTheDocument();
  });

  it("renders empty state when all entries have non-finite best_time", () => {
    render(
      <SeasonProgressionChart
        seasons={[{ season: "2025", best_time: NaN, race_count: 1 }]}
      />
    );
    expect(screen.getByText("No season data available yet.")).toBeInTheDocument();
  });

  it("renders an SVG element when valid seasons are provided", () => {
    const { container } = render(<SeasonProgressionChart seasons={THREE_SEASONS} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("renders a season label for each season", () => {
    render(<SeasonProgressionChart seasons={THREE_SEASONS} />);
    expect(screen.getByText("2023")).toBeInTheDocument();
    expect(screen.getByText("2024")).toBeInTheDocument();
    expect(screen.getByText("2025")).toBeInTheDocument();
  });

  it("renders one circle (data point) per season", () => {
    const { container } = render(<SeasonProgressionChart seasons={THREE_SEASONS} />);
    const circles = container.querySelectorAll("circle");
    expect(circles).toHaveLength(THREE_SEASONS.length);
  });

  it("shows the Improving indicator when last season is faster than the first", () => {
    render(<SeasonProgressionChart seasons={THREE_SEASONS} />);
    expect(screen.getByText(/Improving/i)).toBeInTheDocument();
  });

  it("does not show the Improving indicator for a single season", () => {
    render(
      <SeasonProgressionChart seasons={[THREE_SEASONS[0]]} />
    );
    expect(screen.queryByText(/Improving/i)).not.toBeInTheDocument();
  });

  it("shows the Stable indicator when latest time is slower than the first", () => {
    render(<SeasonProgressionChart seasons={DECLINING_SEASONS} />);
    expect(screen.getByText(/Stable/i)).toBeInTheDocument();
  });

  it("does not show a trend indicator for a single season", () => {
    render(
      <SeasonProgressionChart seasons={[{ season: "2025", best_time: 84.55, race_count: 1 }]} />
    );
    expect(screen.queryByText(/Stable/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Improving/i)).not.toBeInTheDocument();
  });

  it("renders correctly with a single season (no line, just a point)", () => {
    const { container } = render(
      <SeasonProgressionChart
        seasons={[{ season: "2025", best_time: 84.55, race_count: 1 }]}
      />
    );
    expect(container.querySelector("svg")).toBeInTheDocument();
    expect(screen.getByText("2025")).toBeInTheDocument();
    // No line path when only one season
    const paths = container.querySelectorAll("path[stroke='#0a84ff']");
    expect(paths).toHaveLength(0);
  });

  it("renders a line path when there are two or more seasons", () => {
    const { container } = render(<SeasonProgressionChart seasons={THREE_SEASONS} />);
    const linePath = container.querySelector("path[stroke='#0a84ff']");
    expect(linePath).toBeInTheDocument();
  });

  it("sorts seasons alphabetically regardless of input order", () => {
    const unsorted = [
      { season: "2025", best_time: 84.55, race_count: 2 },
      { season: "2023", best_time: 90.5, race_count: 3 },
      { season: "2024", best_time: 87.2, race_count: 5 },
    ];
    render(<SeasonProgressionChart seasons={unsorted} />);
    // All labels should still be present
    expect(screen.getByText("2023")).toBeInTheDocument();
    expect(screen.getByText("2024")).toBeInTheDocument();
    expect(screen.getByText("2025")).toBeInTheDocument();
  });

  it("shows a tooltip when hovering over a data point", () => {
    const { container } = render(<SeasonProgressionChart seasons={THREE_SEASONS} />);
    const circles = container.querySelectorAll("circle");
    fireEvent.mouseEnter(circles[0]);
    // Tooltip should appear — check for the season label inside the tooltip
    const tooltipLabels = container.querySelectorAll(".season-tooltip-label");
    expect(tooltipLabels.length).toBeGreaterThan(0);
  });

  it("hides tooltip when mouse leaves the SVG", () => {
    const { container } = render(<SeasonProgressionChart seasons={THREE_SEASONS} />);
    const circles = container.querySelectorAll("circle");
    fireEvent.mouseEnter(circles[0]);
    const svg = container.querySelector("svg");
    fireEvent.mouseLeave(svg);
    const tooltipLabels = container.querySelectorAll(".season-tooltip-label");
    expect(tooltipLabels).toHaveLength(0);
  });

  it("filters out entries with non-finite best_time before rendering", () => {
    const mixed = [
      { season: "2023", best_time: 90.5, race_count: 3 },
      { season: "2024", best_time: NaN, race_count: 1 },
      { season: "2025", best_time: 84.55, race_count: 2 },
    ];
    const { container } = render(<SeasonProgressionChart seasons={mixed} />);
    // Should render with 2 valid seasons
    const circles = container.querySelectorAll("circle");
    expect(circles).toHaveLength(2);
  });
});
