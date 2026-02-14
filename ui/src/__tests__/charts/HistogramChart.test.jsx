import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { HistogramChart } from "../../charts/HistogramChart.jsx";

const makeHistogram = (overrides = {}) => ({
  bins: [
    { start: 0, end: 5, count: 3 },
    { start: 5, end: 10, count: 7 },
    { start: 10, end: 15, count: 2 },
  ],
  min: 0,
  max: 15,
  count: 12,
  athlete_value: 7.5,
  athlete_percentile: 0.65,
  ...overrides,
});

describe("HistogramChart", () => {
  it("renders empty message when no histogram", () => {
    render(<HistogramChart title="Test" histogram={null} />);
    expect(screen.getByText("No distribution data available.")).toBeInTheDocument();
  });

  it("renders empty message when bins are empty", () => {
    render(<HistogramChart title="Test" histogram={{ bins: [] }} />);
    expect(screen.getByText("No distribution data available.")).toBeInTheDocument();
  });

  it("renders custom empty message", () => {
    render(<HistogramChart title="Test" histogram={null} emptyMessage="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("renders title and subtitle", () => {
    render(
      <HistogramChart title="My Chart" subtitle="Sub text" histogram={makeHistogram()} />
    );
    expect(screen.getByText("My Chart")).toBeInTheDocument();
    expect(screen.getByText("Sub text")).toBeInTheDocument();
  });

  it("renders bins as bars", () => {
    const histogram = makeHistogram();
    const { container } = render(<HistogramChart title="Test" histogram={histogram} />);
    const bars = container.querySelectorAll(".chart-bar");
    expect(bars.length).toBe(3);
  });

  it("renders athlete marker when value present", () => {
    const { container } = render(
      <HistogramChart title="Test" histogram={makeHistogram()} />
    );
    const marker = container.querySelector(".chart-marker");
    expect(marker).toBeInTheDocument();
  });

  it("renders count display", () => {
    render(<HistogramChart title="Test" histogram={makeHistogram()} />);
    expect(screen.getByText("n=12")).toBeInTheDocument();
  });

  it("renders stats footer when stats provided", () => {
    render(
      <HistogramChart
        title="Test"
        histogram={makeHistogram()}
        stats={{ mean: 8, median: 7.5 }}
      />
    );
    expect(screen.getByText(/Avg:/)).toBeInTheDocument();
    expect(screen.getByText(/Median:/)).toBeInTheDocument();
  });
});
