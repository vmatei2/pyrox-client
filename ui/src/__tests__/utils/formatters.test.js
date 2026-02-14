import { describe, it, expect } from "vitest";
import {
  formatTimeWindowLabel,
  formatMinutes,
  formatDurationMinutes,
  formatDeltaMinutes,
  formatPercent,
  formatLabel,
  sumTimes,
} from "../../utils/formatters.js";

describe("formatTimeWindowLabel", () => {
  it("returns default label for zero or negative", () => {
    expect(formatTimeWindowLabel(0)).toBe("the selected +/- time window");
    expect(formatTimeWindowLabel(-5)).toBe("the selected +/- time window");
  });

  it("returns default label for non-numeric", () => {
    expect(formatTimeWindowLabel(null)).toBe("the selected +/- time window");
    expect(formatTimeWindowLabel("abc")).toBe("the selected +/- time window");
  });

  it("formats positive values", () => {
    expect(formatTimeWindowLabel(5)).toBe("+/- 5 min");
    expect(formatTimeWindowLabel("10")).toBe("+/- 10 min");
  });
});

describe("formatMinutes", () => {
  it("returns dash for null/undefined/empty", () => {
    expect(formatMinutes(null)).toBe("-");
    expect(formatMinutes(undefined)).toBe("-");
    expect(formatMinutes("")).toBe("-");
  });

  it("returns dash for non-finite", () => {
    expect(formatMinutes(NaN)).toBe("-");
    expect(formatMinutes(Infinity)).toBe("-");
    expect(formatMinutes("abc")).toBe("-");
  });

  it("formats zero", () => {
    expect(formatMinutes(0)).toBe("0:00");
  });

  it("formats minutes under an hour", () => {
    expect(formatMinutes(5)).toBe("5:00");
    expect(formatMinutes(5.5)).toBe("5:30");
    expect(formatMinutes(12.25)).toBe("12:15");
  });

  it("formats values over an hour", () => {
    expect(formatMinutes(60)).toBe("1:00:00");
    expect(formatMinutes(90.5)).toBe("1:30:30");
    expect(formatMinutes(125)).toBe("2:05:00");
  });

  it("clamps negative values to zero", () => {
    expect(formatMinutes(-5)).toBe("0:00");
  });

  it("handles string numbers", () => {
    expect(formatMinutes("5.5")).toBe("5:30");
  });
});

describe("formatDurationMinutes", () => {
  it("returns dash for null/undefined/empty", () => {
    expect(formatDurationMinutes(null)).toBe("-");
    expect(formatDurationMinutes(undefined)).toBe("-");
    expect(formatDurationMinutes("")).toBe("-");
  });

  it("uses absolute value (no sign)", () => {
    expect(formatDurationMinutes(-5)).toBe("5:00");
    expect(formatDurationMinutes(5)).toBe("5:00");
  });

  it("formats values over an hour", () => {
    expect(formatDurationMinutes(75)).toBe("1:15:00");
  });
});

describe("formatDeltaMinutes", () => {
  it("returns dash for null/undefined/empty", () => {
    expect(formatDeltaMinutes(null)).toBe("-");
    expect(formatDeltaMinutes(undefined)).toBe("-");
    expect(formatDeltaMinutes("")).toBe("-");
  });

  it("returns no sign for zero", () => {
    expect(formatDeltaMinutes(0)).toBe("0:00");
  });

  it("adds + for positive values", () => {
    expect(formatDeltaMinutes(2.5)).toBe("+2:30");
  });

  it("adds - for negative values", () => {
    expect(formatDeltaMinutes(-3)).toBe("-3:00");
  });
});

describe("formatPercent", () => {
  it("returns dash for non-finite", () => {
    expect(formatPercent(undefined)).toBe("-");
    expect(formatPercent("abc")).toBe("-");
  });

  it("treats null as zero (Number(null) === 0)", () => {
    expect(formatPercent(null)).toBe("0.0%");
  });

  it("formats decimal to percentage", () => {
    expect(formatPercent(0.5)).toBe("50.0%");
    expect(formatPercent(1)).toBe("100.0%");
    expect(formatPercent(0)).toBe("0.0%");
    expect(formatPercent(0.953)).toBe("95.3%");
  });
});

describe("formatLabel", () => {
  it("returns dash for null/undefined/empty", () => {
    expect(formatLabel(null)).toBe("-");
    expect(formatLabel(undefined)).toBe("-");
    expect(formatLabel("")).toBe("-");
  });

  it("returns string representation", () => {
    expect(formatLabel("hello")).toBe("hello");
    expect(formatLabel(42)).toBe("42");
  });
});

describe("sumTimes", () => {
  it("returns null if any value is null", () => {
    expect(sumTimes(1, null, 3)).toBe(null);
    expect(sumTimes("abc")).toBe(null);
  });

  it("sums numeric values", () => {
    expect(sumTimes(1, 2, 3)).toBe(6);
    expect(sumTimes(5.5, 2.5)).toBe(8);
  });

  it("handles single value", () => {
    expect(sumTimes(10)).toBe(10);
  });

  it("handles time string values via toNumber", () => {
    expect(sumTimes("1:00", "2:00")).toBe(3);
  });
});
