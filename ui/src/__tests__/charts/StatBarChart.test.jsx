import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatBarChart } from "../../charts/StatBarChart.jsx";

describe("StatBarChart", () => {
  it("renders empty message when no items", () => {
    render(<StatBarChart title="Test" items={[]} />);
    expect(screen.getByText("No data available.")).toBeInTheDocument();
  });

  it("renders empty message when all values are non-finite", () => {
    render(<StatBarChart title="Test" items={[{ label: "A", value: null }]} />);
    expect(screen.getByText("No data available.")).toBeInTheDocument();
  });

  it("renders bars for valid items", () => {
    const items = [
      { label: "Athlete", value: 5.0, accent: true },
      { label: "Median", value: 6.5 },
      { label: "Best", value: 4.2 },
    ];
    const { container } = render(<StatBarChart title="Comparison" items={items} />);
    expect(screen.getByText("Comparison")).toBeInTheDocument();
    const bars = container.querySelectorAll(".stat-bar-item");
    expect(bars.length).toBe(3);
  });
});
