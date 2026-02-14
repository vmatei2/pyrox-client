import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PercentileLineChart } from "../../charts/PercentileLineChart.jsx";

const makeSeries = () => [
  { label: "Run 1", cohort: 75.2, window: 68.5 },
  { label: "Run 2", cohort: 80.1, window: 72.3 },
  { label: "SkiErg", cohort: 60.0, window: 55.0 },
];

describe("PercentileLineChart", () => {
  it("renders empty message when series is empty", () => {
    render(<PercentileLineChart title="Test" series={[]} />);
    expect(screen.getByText("No percentile data available.")).toBeInTheDocument();
  });

  it("renders empty when all values are non-finite", () => {
    const series = [{ label: "R1", cohort: null, window: null }];
    render(<PercentileLineChart title="Test" series={series} />);
    expect(screen.getByText("No percentile data available.")).toBeInTheDocument();
  });

  it("renders SVG chart with valid data", () => {
    const { container } = render(
      <PercentileLineChart title="Percentiles" subtitle="By split" series={makeSeries()} />
    );
    expect(screen.getByText("Percentiles")).toBeInTheDocument();
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it("renders legend", () => {
    render(<PercentileLineChart title="Test" series={makeSeries()} />);
    expect(screen.getByText("Age group percentile")).toBeInTheDocument();
    expect(screen.getByText("Time window percentile")).toBeInTheDocument();
  });
});
