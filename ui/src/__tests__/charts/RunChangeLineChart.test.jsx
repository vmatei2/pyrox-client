import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RunChangeLineChart } from "../../charts/RunChangeLineChart.jsx";

const makeSeries = () => ({
  points: [
    { run: "R2", delta_from_median_min: -0.2, run_time_min: 3.3 },
    { run: "R3", delta_from_median_min: 0.1, run_time_min: 3.6 },
    { run: "R4", delta_from_median_min: 0.3, run_time_min: 3.8 },
  ],
  median_run_time_min: 3.5,
  min_delta_min: -0.2,
  max_delta_min: 0.3,
});

describe("RunChangeLineChart", () => {
  it("renders empty message when no points", () => {
    render(<RunChangeLineChart title="Test" series={{ points: [] }} />);
    expect(screen.getByText("No run pacing data available.")).toBeInTheDocument();
  });

  it("renders empty when series is null", () => {
    render(<RunChangeLineChart title="Test" series={null} />);
    expect(screen.getByText("No run pacing data available.")).toBeInTheDocument();
  });

  it("renders SVG chart with valid data", () => {
    const { container } = render(
      <RunChangeLineChart title="Pacing" series={makeSeries()} />
    );
    expect(screen.getByText("Pacing")).toBeInTheDocument();
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it("renders footer stats", () => {
    render(<RunChangeLineChart title="Test" series={makeSeries()} />);
    expect(screen.getByText(/Median run/)).toBeInTheDocument();
    expect(screen.getByText(/Fastest vs median/)).toBeInTheDocument();
    expect(screen.getByText(/Slowest vs median/)).toBeInTheDocument();
  });
});
