import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import {
  useAthleteIdentity,
  ATHLETE_IDENTITY_KEY,
} from "../../hooks/useAthleteIdentity.js";

describe("useAthleteIdentity", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("returns null identity when nothing is stored", () => {
    const { result } = renderHook(() => useAthleteIdentity());
    expect(result.current.identity).toBeNull();
  });

  it("reads a valid identity from localStorage on mount", () => {
    const stored = { name: "Sarah Johnson", setAt: "2025-01-01T00:00:00Z" };
    localStorage.setItem(ATHLETE_IDENTITY_KEY, JSON.stringify(stored));

    const { result } = renderHook(() => useAthleteIdentity());
    expect(result.current.identity).toEqual(stored);
  });

  it("reads a valid athleteId-only identity from localStorage on mount", () => {
    const stored = { athleteId: "ath_123", setAt: "2025-01-01T00:00:00Z" };
    localStorage.setItem(ATHLETE_IDENTITY_KEY, JSON.stringify(stored));

    const { result } = renderHook(() => useAthleteIdentity());
    expect(result.current.identity).toEqual(stored);
  });

  it("setIdentity updates state and persists to localStorage", () => {
    const { result } = renderHook(() => useAthleteIdentity());
    const identity = { name: "John Doe", setAt: "2025-06-01T00:00:00Z" };

    act(() => {
      result.current.setIdentity(identity);
    });

    expect(result.current.identity).toEqual(identity);
    const stored = JSON.parse(localStorage.getItem(ATHLETE_IDENTITY_KEY));
    expect(stored).toEqual(identity);
  });

  it("clearIdentity sets identity to null and removes item from localStorage", () => {
    const stored = { name: "Sarah Johnson", setAt: "2025-01-01T00:00:00Z" };
    localStorage.setItem(ATHLETE_IDENTITY_KEY, JSON.stringify(stored));

    const { result } = renderHook(() => useAthleteIdentity());
    expect(result.current.identity).toEqual(stored);

    act(() => {
      result.current.clearIdentity();
    });

    expect(result.current.identity).toBeNull();
    expect(localStorage.getItem(ATHLETE_IDENTITY_KEY)).toBeNull();
  });

  it("setIdentity(null) removes item from localStorage", () => {
    const stored = { name: "Sarah Johnson", setAt: "2025-01-01T00:00:00Z" };
    localStorage.setItem(ATHLETE_IDENTITY_KEY, JSON.stringify(stored));

    const { result } = renderHook(() => useAthleteIdentity());

    act(() => {
      result.current.setIdentity(null);
    });

    expect(result.current.identity).toBeNull();
    expect(localStorage.getItem(ATHLETE_IDENTITY_KEY)).toBeNull();
  });

  it("ignores malformed JSON in localStorage", () => {
    localStorage.setItem(ATHLETE_IDENTITY_KEY, "not-valid-json{{{");

    const { result } = renderHook(() => useAthleteIdentity());
    expect(result.current.identity).toBeNull();
  });

  it("ignores stored object without a name field", () => {
    localStorage.setItem(
      ATHLETE_IDENTITY_KEY,
      JSON.stringify({ setAt: "2025-01-01T00:00:00Z" })
    );

    const { result } = renderHook(() => useAthleteIdentity());
    expect(result.current.identity).toBeNull();
  });

  it("ignores stored object with an empty name", () => {
    localStorage.setItem(
      ATHLETE_IDENTITY_KEY,
      JSON.stringify({ name: "   ", setAt: "2025-01-01T00:00:00Z" })
    );

    const { result } = renderHook(() => useAthleteIdentity());
    expect(result.current.identity).toBeNull();
  });

  it("exposes setIdentity and clearIdentity functions", () => {
    const { result } = renderHook(() => useAthleteIdentity());
    expect(typeof result.current.setIdentity).toBe("function");
    expect(typeof result.current.clearIdentity).toBe("function");
  });

  it("overwriting identity updates localStorage correctly", () => {
    const { result } = renderHook(() => useAthleteIdentity());

    act(() => {
      result.current.setIdentity({ name: "Alice", setAt: "2024-01-01T00:00:00Z" });
    });
    act(() => {
      result.current.setIdentity({ name: "Bob", setAt: "2025-01-01T00:00:00Z" });
    });

    expect(result.current.identity.name).toBe("Bob");
    const stored = JSON.parse(localStorage.getItem(ATHLETE_IDENTITY_KEY));
    expect(stored.name).toBe("Bob");
  });
});
