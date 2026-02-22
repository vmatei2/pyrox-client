# UI Test Plan (Deep Dive + Race Planner)

## Goal
Add focused UI tests for `DeepdiveMode` and `PlannerMode` so recent UX and filtering changes are protected by automated checks.

## Current State
- UI test stack exists: `vitest` + `@testing-library/react`.
- Existing page tests already present (for example `ReportMode` and `ProfileMode`).
- No dedicated test files yet for:
  - `ui/src/pages/DeepdiveMode.jsx`
  - `ui/src/pages/PlannerMode.jsx`

## Scope For This Iteration
1. Add page-level tests for render, interactions, and API-driven states.
2. Mock API layer (`ui/src/api/client.js`) and haptics (`ui/src/utils/haptics.js`).
3. Cover high-value user flows only (not pixel/layout assertions).

## Deliverables
1. `ui/src/__tests__/pages/DeepdiveMode.test.jsx`
2. `ui/src/__tests__/pages/PlannerMode.test.jsx`
3. Any minimal test helpers needed in existing test setup (if required).

## Test Cases

### Deep Dive
1. Renders “How to use Deep Dive” step guidance.
2. Loads filter dropdown options from `fetchFilterOptions` (division/gender).
3. Shows validation when search is submitted without athlete name.
4. Runs athlete search and displays race cards from API response.
5. Selecting a race pre-fills deepdive params (`season`, `division`, `gender`, `ageGroup`).
6. Shows validation when running deepdive without required base race or season.
7. Runs deepdive successfully and renders summary/results cards.
8. Shows API error state for failed search/deepdive calls.

### Race Planner
1. Renders “How to use Race Planner” step guidance.
2. Loads filter dropdown options from `fetchFilterOptions` (season/location/year/division/gender).
3. Submits planner query with selected filters.
4. Renders returned planner summary/tags/charts.
5. Shows loading state and API error state.

## Implementation Notes
1. Follow AAA pattern (Arrange, Act, Assert) per test.
2. Keep tests deterministic: no timers/network real calls.
3. Prefer semantic queries (`getByRole`, `findByText`, `within`) over class selectors.
4. Assert payloads passed into mocked API functions to verify integration.

## Run Commands
1. `cd ui && npm run test:run`
2. Optional focused run:
   - `cd ui && npx vitest run src/__tests__/pages/DeepdiveMode.test.jsx`
   - `cd ui && npx vitest run src/__tests__/pages/PlannerMode.test.jsx`

## Definition of Done
1. New tests pass locally.
2. Existing UI test suite remains green.
3. No production code changes required solely to satisfy brittle test assertions.
4. Core user flows above are covered for both screens.
