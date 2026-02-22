# Errors

Pyrox exposes a small, predictable hierarchy so your pipelines can fail fast and
recover gracefully.

## `PyroxError`

Base class for client-specific errors. Catch this for broad error handling.

## `RaceNotFound`

Raised when a season/location pair is missing from the manifest or a filter
produces zero rows.

## `AthleteNotFound`

Raised when the athlete name filter returns no matches.

## `FileNotFoundError`

Raised when CDN reads fail unexpectedly. Consider retrying or logging the failing
race metadata.

## Reporting Service Degradation Behavior

For repository-only FastAPI profile endpoints (`/api/athletes/profile` and
`/api/athletes/{athlete_id}/profile`), segment percentile enrichment is
best-effort:

- If cohort data or required columns are missing for a segment, the endpoint
  omits `personal_bests[segment].percentile` and/or
  `average_times[segment].percentile`.
- The profile response still returns `200` when the underlying athlete profile
  exists.
