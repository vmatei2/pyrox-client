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

export async function apiFetch(path, params = {}) {
  const url = new URL(`${API_BASE}${path}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });
  const response = await fetch(url, { signal: AbortSignal.timeout(6500) });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
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
  return apiFetch("/api/athletes/search", params);
}

export function fetchReport(resultId, options = {}) {
  const params = {};
  if (options.timeWindow?.trim()) params.cohort_time_window_min = options.timeWindow.trim();
  if (options.splitName?.trim()) params.split_name = options.splitName.trim();
  return apiFetch(`/api/reports/${resultId}`, params);
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
  return apiFetch(`/api/deepdive/${resultId}`, params);
}

export function fetchDeepdiveFilters(options = {}) {
  const params = {};
  if (options.season?.trim()) params.season = options.season.trim();
  if (options.division?.trim()) params.division = options.division.trim();
  if (options.gender?.trim()) params.gender = options.gender.trim();
  return apiFetch("/api/deepdive/filters", params);
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
  return apiFetch("/api/planner", params);
}
