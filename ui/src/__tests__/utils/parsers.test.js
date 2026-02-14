import { describe, it, expect } from "vitest";
import {
  toNumber,
  normalizeSplitKey,
  buildSplitTimeMap,
  pickSegmentValue,
  parseError,
} from "../../utils/parsers.js";

describe("toNumber", () => {
  it("returns null for null/undefined/empty", () => {
    expect(toNumber(null)).toBe(null);
    expect(toNumber(undefined)).toBe(null);
    expect(toNumber("")).toBe(null);
    expect(toNumber("   ")).toBe(null);
  });

  it("returns null for non-finite numbers", () => {
    expect(toNumber(NaN)).toBe(null);
    expect(toNumber(Infinity)).toBe(null);
    expect(toNumber(-Infinity)).toBe(null);
  });

  it("returns the number for finite numbers", () => {
    expect(toNumber(42)).toBe(42);
    expect(toNumber(0)).toBe(0);
    expect(toNumber(-5.5)).toBe(-5.5);
  });

  it("parses plain numeric strings", () => {
    expect(toNumber("42")).toBe(42);
    expect(toNumber("  3.14  ")).toBe(3.14);
    expect(toNumber("0")).toBe(0);
  });

  it("returns null for non-numeric strings", () => {
    expect(toNumber("abc")).toBe(null);
    expect(toNumber("12abc")).toBe(null);
  });

  it("parses MM:SS format", () => {
    expect(toNumber("5:30")).toBe(5.5);
    expect(toNumber("10:00")).toBe(10);
    expect(toNumber("0:45")).toBe(0.75);
  });

  it("parses HH:MM:SS format", () => {
    expect(toNumber("1:30:00")).toBe(90);
    expect(toNumber("2:00:00")).toBe(120);
    expect(toNumber("1:23:45")).toBe(60 + 23 + 45 / 60);
  });

  it("returns null for malformed colon strings", () => {
    expect(toNumber(":30")).toBe(null);
    expect(toNumber("5:")).toBe(null);
    expect(toNumber("1:2:3:4")).toBe(null);
    expect(toNumber("a:b")).toBe(null);
  });
});

describe("normalizeSplitKey", () => {
  it("returns empty string for null/undefined", () => {
    expect(normalizeSplitKey(null)).toBe("");
    expect(normalizeSplitKey(undefined)).toBe("");
  });

  it("lowercases and removes non-alphanumeric", () => {
    expect(normalizeSplitKey("Run 1")).toBe("run1");
    expect(normalizeSplitKey("Sled Push")).toBe("sledpush");
    expect(normalizeSplitKey("Burpee Broad Jump")).toBe("burpeebroadjump");
  });

  it("trims whitespace", () => {
    expect(normalizeSplitKey("  SkiErg  ")).toBe("skierg");
  });
});

describe("buildSplitTimeMap", () => {
  it("returns empty map for non-array", () => {
    expect(buildSplitTimeMap(null).size).toBe(0);
    expect(buildSplitTimeMap(undefined).size).toBe(0);
    expect(buildSplitTimeMap("not-array").size).toBe(0);
  });

  it("builds map from splits array", () => {
    const splits = [
      { split_name: "Run 1", split_time_min: 3.5 },
      { split_name: "SkiErg", split_time_min: 2.0 },
    ];
    const map = buildSplitTimeMap(splits);
    expect(map.size).toBe(2);
    expect(map.get("run1")).toEqual({ name: "Run 1", time: 3.5 });
    expect(map.get("skierg")).toEqual({ name: "SkiErg", time: 2.0 });
  });

  it("skips entries with empty split_name", () => {
    const splits = [
      { split_name: "", split_time_min: 1 },
      { split_name: "Run 1", split_time_min: 2 },
    ];
    const map = buildSplitTimeMap(splits);
    expect(map.size).toBe(1);
  });
});

describe("pickSegmentValue", () => {
  it("returns value from splitMap if present", () => {
    const segment = { key: "run1", column: "run1_time_min" };
    const splitMap = new Map([["run1", { time: 3.5 }]]);
    expect(pickSegmentValue(segment, {}, splitMap)).toBe(3.5);
  });

  it("falls back to race column if splitMap missing or null time", () => {
    const segment = { key: "run1", column: "run1_time_min" };
    const race = { run1_time_min: 4.2 };
    expect(pickSegmentValue(segment, race, new Map())).toBe(4.2);
  });

  it("handles null splitMap", () => {
    const segment = { key: "run1", column: "run1_time_min" };
    const race = { run1_time_min: 4.2 };
    expect(pickSegmentValue(segment, race, null)).toBe(4.2);
  });

  it("handles null race", () => {
    const segment = { key: "run1", column: "run1_time_min" };
    expect(pickSegmentValue(segment, null, new Map())).toBe(null);
  });
});

describe("parseError", () => {
  it("extracts detail from JSON response", async () => {
    const response = {
      json: async () => ({ detail: "Not found" }),
      statusText: "Not Found",
    };
    expect(await parseError(response)).toBe("Not found");
  });

  it("falls back to statusText if no detail", async () => {
    const response = {
      json: async () => ({}),
      statusText: "Bad Request",
    };
    expect(await parseError(response)).toBe("Bad Request");
  });

  it("falls back to statusText on JSON parse failure", async () => {
    const response = {
      json: async () => { throw new Error("bad json"); },
      statusText: "Internal Server Error",
    };
    expect(await parseError(response)).toBe("Internal Server Error");
  });

  it("returns default message if no statusText", async () => {
    const response = {
      json: async () => { throw new Error(); },
      statusText: "",
    };
    expect(await parseError(response)).toBe("Request failed.");
  });
});
