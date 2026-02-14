import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { GroupedBarChart } from "../../charts/GroupedBarChart.jsx";

const makeSegments = () => [
  { key: "run1", label: "Run 1", color: "#38bdf8", baseValue: 3.5, compareValue: 4.0 },
  { key: "run2", label: "Run 2", color: "#22d3ee", baseValue: 3.2, compareValue: 3.8 },
];

describe("GroupedBarChart", () => {
  it("renders empty message when no segments", () => {
    render(<GroupedBarChart title="Test" segments={[]} />);
    expect(screen.getByText("No data available.")).toBeInTheDocument();
  });

  it("renders title and legend", () => {
    render(
      <GroupedBarChart
        title="Runs"
        subtitle="Comparison"
        segments={makeSegments()}
        baseLabel="Athlete A"
        compareLabel="Athlete B"
      />
    );
    expect(screen.getByText("Runs")).toBeInTheDocument();
    expect(screen.getByText("Athlete A")).toBeInTheDocument();
    expect(screen.getByText("Athlete B")).toBeInTheDocument();
  });

  it("renders bars for each segment", () => {
    const { container } = render(
      <GroupedBarChart title="Test" segments={makeSegments()} baseLabel="A" compareLabel="B" />
    );
    const groups = container.querySelectorAll(".grouped-group");
    expect(groups.length).toBe(2);
  });
});
