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
