import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WorkRunSplitPieChart } from "../../charts/WorkRunSplitPieChart.jsx";

describe("WorkRunSplitPieChart", () => {
  it("renders empty message when no split data", () => {
    render(<WorkRunSplitPieChart title="Test" split={null} />);
    expect(screen.getByText("No work/run split data available.")).toBeInTheDocument();
  });

  it("renders pie chart with valid data", () => {
    const split = {
      work_pct: 0.45,
      run_pct: 0.55,
      work_time_min: 20.5,
      run_time_with_roxzone_min: 25.0,
      total_time_min: 45.5,
    };
    render(<WorkRunSplitPieChart title="Work/Run Split" split={split} />);
    expect(screen.getByText("Work/Run Split")).toBeInTheDocument();
    expect(screen.getByText("Work time")).toBeInTheDocument();
    expect(screen.getByText("Runs + Roxzone")).toBeInTheDocument();
  });

  it("renders total time in center", () => {
    const split = {
      work_pct: 0.4,
      run_pct: 0.6,
      work_time_min: 18,
      run_time_with_roxzone_min: 27,
      total_time_min: 45,
    };
    render(<WorkRunSplitPieChart title="Test" split={split} />);
    expect(screen.getByText("Total")).toBeInTheDocument();
    expect(screen.getByText("45:00")).toBeInTheDocument();
  });
});
