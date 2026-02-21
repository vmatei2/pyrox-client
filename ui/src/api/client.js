import { QueryClient } from "@tanstack/react-query";
import { API_BASE } from "../constants/segments.js";
import { parseError } from "../utils/parsers.js";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const REQUEST_TIMEOUT_MS = {
  default: 15000,
  search: 20000,
  report: 90000,
  deepdive: 90000,
  rankings: 60000,
  planner: 60000,
  profile: 45000,
};

function buildTimeoutError(timeoutMs) {
  const seconds = Math.max(1, Math.round(timeoutMs / 1000));
  return new Error(`Request timed out after ${seconds}s. Please try again.`);
}

export async function apiFetch(path, params = {}, options = {}) {
  const timeoutMs =
    Number.isFinite(options.timeoutMs) && options.timeoutMs > 0
      ? Number(options.timeoutMs)
      : REQUEST_TIMEOUT_MS.default;
  const url = new URL(`${API_BASE}${path}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });

  const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timeoutId = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;

  try {
    const response = await fetch(url, controller ? { signal: controller.signal } : undefined);
    if (!response.ok) {
      throw new Error(await parseError(response));
    }
    return response.json();
  } catch (error) {
    if (error?.name === "AbortError") {
      throw buildTimeoutError(timeoutMs);
    }
    throw error;
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  }
}

export function searchAthletes(name, filters = {}) {
  const params = {
    name: name.trim(),
    match: filters.match || "contains",
    require_unique: String(filters.requireUnique ?? false),
  };
  if (filters.gender?.trim()) params.gender = filters.gender.trim();
  if (filters.division?.trim()) params.division = filters.division.trim();
  if (filters.nationality?.trim()) params.nationality = filters.nationality.trim();
  return apiFetch("/api/athletes/search", params, { timeoutMs: REQUEST_TIMEOUT_MS.search });
}

export function fetchReport(resultId, options = {}) {
  const params = {};
  if (options.timeWindow?.trim()) params.cohort_time_window_min = options.timeWindow.trim();
  if (options.splitName?.trim()) params.split_name = options.splitName.trim();
  return apiFetch(`/api/reports/${resultId}`, params, { timeoutMs: REQUEST_TIMEOUT_MS.report });
}

export function fetchDeepdive(resultId, options = {}) {
  const params = {};
  if (options.season?.trim()) params.season = options.season.trim();
  if (options.metric?.trim()) params.metric = options.metric.trim();
  if (options.division?.trim()) params.division = options.division.trim();
  if (options.gender?.trim()) params.gender = options.gender.trim();
  if (options.ageGroup?.trim()) params.age_group = options.ageGroup.trim();
  if (options.location?.trim()) params.location = options.location.trim();
  if (options.stat?.trim()) params.stat = options.stat.trim();
  return apiFetch(`/api/deepdive/${resultId}`, params, {
    timeoutMs: REQUEST_TIMEOUT_MS.deepdive,
  });
}

export function fetchDeepdiveFilters(options = {}) {
  const params = {};
  if (options.season?.trim()) params.season = options.season.trim();
  if (options.division?.trim()) params.division = options.division.trim();
  if (options.gender?.trim()) params.gender = options.gender.trim();
  return apiFetch("/api/deepdive/filters", params, { timeoutMs: REQUEST_TIMEOUT_MS.search });
}

export function fetchFilterOptions(options = {}) {
  const params = {};
  if (options.season?.toString().trim()) params.season = options.season.toString().trim();
  if (options.division?.trim()) params.division = options.division.trim();
  if (options.gender?.trim()) params.gender = options.gender.trim();
  return apiFetch("/api/filter-options", params, { timeoutMs: REQUEST_TIMEOUT_MS.search });
}

export function fetchPlanner(filters = {}) {
  const params = {};
  if (filters.season?.trim()) params.season = filters.season.trim();
  if (filters.location?.trim()) params.location = filters.location.trim();
  if (filters.year?.trim()) params.year = filters.year.trim();
  if (filters.division?.trim()) params.division = filters.division.trim();
  if (filters.gender?.trim()) params.gender = filters.gender.trim();
  if (filters.minTime?.trim()) params.min_total_time = filters.minTime.trim();
  if (filters.maxTime?.trim()) params.max_total_time = filters.maxTime.trim();
  return apiFetch("/api/planner", params, { timeoutMs: REQUEST_TIMEOUT_MS.planner });
}

export function fetchRankingsFilters(options = {}) {
  const params = {};
  if (options.season?.trim()) params.season = options.season.trim();
  if (options.division?.trim()) params.division = options.division.trim();
  if (options.gender?.trim()) params.gender = options.gender.trim();
  if (options.ageGroup?.trim()) params.age_group = options.ageGroup.trim();
  return apiFetch("/api/rankings/filters", params, { timeoutMs: REQUEST_TIMEOUT_MS.search });
}

export function fetchAthleteProfile(identityOrName) {
  if (typeof identityOrName === "string") {
    const name = identityOrName.trim();
    return apiFetch("/api/athletes/profile", { name }, { timeoutMs: REQUEST_TIMEOUT_MS.profile });
  }

  const division =
    typeof identityOrName?.division === "string" ? identityOrName.division.trim() : "";
  const athleteId =
    typeof identityOrName?.athleteId === "string"
      ? identityOrName.athleteId.trim()
      : "";
  if (athleteId) {
    const params = {};
    if (division) params.division = division;
    return apiFetch(`/api/athletes/${encodeURIComponent(athleteId)}/profile`, params, {
      timeoutMs: REQUEST_TIMEOUT_MS.profile,
    });
  }

  const name =
    typeof identityOrName?.name === "string" ? identityOrName.name.trim() : "";
  if (name) {
    const params = { name };
    if (division) params.division = division;
    return apiFetch("/api/athletes/profile", params, { timeoutMs: REQUEST_TIMEOUT_MS.profile });
  }

  throw new Error("athleteId or name is required.");
}

export function fetchRankings(filters = {}) {
  const params = {};
  if (filters.season?.trim()) params.season = filters.season.trim();
  if (filters.division?.trim()) params.division = filters.division.trim();
  if (filters.gender?.trim()) params.gender = filters.gender.trim();
  if (filters.ageGroup?.trim()) params.age_group = filters.ageGroup.trim();
  if (filters.athleteName?.trim()) params.athlete_name = filters.athleteName.trim();
  if (filters.limit?.trim()) params.limit = filters.limit.trim();
  if (filters.targetTime?.trim()) params.target_time_min = filters.targetTime.trim();
  return apiFetch("/api/rankings", params, { timeoutMs: REQUEST_TIMEOUT_MS.rankings });
}
