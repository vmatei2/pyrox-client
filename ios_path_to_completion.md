# iOS Path To Completion

## Objective
Build Pyrox into a world-class iOS data analytics product: visually exceptional, deeply usable on small screens, technically robust, and App Store competitive.

This document is written as an execution guide for a second agent. Each step includes:
- `Why`: why this step is required for top-tier iOS quality.
- `How`: concrete implementation guidance.
- `Done when`: acceptance criteria.

---

## Current State (Baseline Reality)
- App is a React + Vite UI inside Capacitor (`ui/`) with FastAPI backend (`src/pyrox/api/app.py`).
- Mobile support exists but UI is still primarily web-first.
- Data exploration depth is strong, but product polish and iOS-native quality are not yet at top-tier App Store level.
- Build/sync is functioning for iOS simulator.

Top-level implication:
- You can ship incremental improvements quickly in current stack.
- To compete visually and experientially with best-in-class iOS data apps, you need product, design, and performance rigor far beyond a simple responsive web layer.

---

## Phase 1: Product Strategy and Scope Discipline

### 1. Define the iOS Product Wedge
`Why`
- Top apps are focused. "Everything analytics" fails on mobile; a narrow, high-value loop wins.

`How`
- Pick one primary persona for v1 (example: competitive HYROX athlete).
- Pick one primary recurring job (example: "Understand where I lose time and what to train next").
- Pick one hero workflow to optimize end-to-end:
  1. Search athlete.
  2. Select race.
  3. Read actionable insight in under 20 seconds.

`Done when`
- A one-page product brief exists with persona, job-to-be-done, and primary workflow.

### 2. Define Feature Tiers (Now / Next / Later)
`Why`
- Without scope boundaries, UI becomes cluttered and impossible to perfect on iPhone.

`How`
- `Now`: race report + split insights + comparison.
- `Next`: deep dive and planner refinements.
- `Later`: social sharing, coaching plans, premium insights, watch widgets.
- Add strict release gate: no new features until quality metrics are green.

`Done when`
- Backlog labels exist (`now`, `next`, `later`) and only `now` is in active sprint.

---

## Phase 2: Information Architecture for Mobile

### 3. Replace Mode-Toggle Mental Model with iOS Navigation Model
`Why`
- Best iOS apps use persistent, clear navigation (tab bar + hierarchical drill-down).
- Horizontal mode switching is cognitively expensive on phone.

`How`
- Move from one mega-screen with mode tabs to 4-root architecture:
  1. `Report`
  2. `Compare`
  3. `Deep Dive`
  4. `Planner`
- In Capacitor/web stage: create bottom sticky tab bar.
- In native stage: use `UITabBarController`/SwiftUI `TabView`.

`Done when`
- Every root section has independent state and back-stack.
- User can switch sections without losing context unexpectedly.

### 4. Introduce Progressive Disclosure
`Why`
- Dense forms and charts overwhelm users on small screens.

`How`
- Default each screen to a summary card first.
- Move advanced filters into collapsible "Advanced" panels.
- Convert large tables into card-based summaries with "View full table" drill-down.

`Done when`
- First viewport in each screen shows one clear action and one clear output.
- Full functionality remains available, but not in first-load clutter.

---

## Phase 3: Visual System and Brand Quality

### 5. Build a Formal Design Token System
`Why`
- Elite app polish comes from consistency at token level, not isolated CSS edits.

`How`
- Define tokens for:
  - spacing scale (`4, 8, 12, 16, 20, 24, 32`)
  - typography scale (display, title, body, caption)
  - elevation, radius, border strength
  - semantic colors (`bg`, `surface`, `muted`, `accent`, `danger`, `success`)
- Store in one source file and reference everywhere.
- Remove one-off color values where possible.

`Done when`
- All major UI surfaces use token values.
- Visual regression snapshots show consistent spacing and rhythm.

### 6. Establish iOS-First Type and Layout Rhythm
`Why`
- Data apps look premium when readability is excellent at arm's length.

`How`
- Set explicit mobile typography rules:
  - title line lengths <= 2 lines
  - body at ~15-17px equivalent
  - minimum tap target >= 44px
- Use layout grid tuned for iPhone width (single-column first).
- Keep long metadata in secondary text style, not headline area.

`Done when`
- No clipped controls on iPhone SE/13 mini/16.
- Text remains readable at default dynamic type.

### 7. Motion and Interaction Quality Pass
`Why`
- Premium iOS feel depends on motion hierarchy, not only static visuals.

`How`
- Add intentional transitions:
  - screen enter/exit
  - chart update transition
  - filter apply feedback
- Keep durations tight (150-250ms), with reduced-motion support.
- Add subtle haptic feedback (native phase) on key actions.

`Done when`
- Motion is consistent, never distracting, and respects reduced-motion settings.

---

## Phase 4: Data Visualization Excellence

### 8. Define Chart Grammar and Reuse Components
`Why`
- Top data apps have predictable chart behavior and consistent semantics.

`How`
- For each chart type, define:
  - purpose
  - interaction model
  - annotation rules
  - empty/error states
- Standardize axis labeling, units, percentile language, and legends.
- Build shared chart primitives (title, subtitle, stat badge, tooltip, axis, marker).

`Done when`
- All charts follow the same UX rules and terminology.
- No custom one-off chart behavior per screen.

### 9. Mobile-Specific Chart Interaction Model
`Why`
- Hover-dependent behavior does not translate to iOS touch.

`How`
- Replace hover tooltips with tap-to-pin tooltips.
- Support horizontal panning/zoom where density is high.
- Add "insight callout" text under chart for quick interpretation.

`Done when`
- Every chart is fully usable without hover.
- Users can read exact values with one tap.

---

## Phase 5: Architecture and Code Quality

### 10. Break Up `ui/src/App.jsx` into Screen Modules
`Why`
- Current monolith blocks maintainability and slows high-quality iteration.

`How`
- Introduce folder structure:
  - `ui/src/screens/...`
  - `ui/src/components/...`
  - `ui/src/lib/api/...`
  - `ui/src/state/...`
- Move each mode into its own screen component.
- Centralize formatting helpers and data mappers.

`Done when`
- `App.jsx` acts as router/shell only.
- Each screen is independently testable.

### 11. Introduce Deterministic State Management
`Why`
- Complex filters, async requests, and chart updates need predictable state.

`How`
- Use a clear state layer (Context + reducer, Zustand, or Redux Toolkit).
- Define a query key strategy for API requests.
- Add request cancellation and stale response protection everywhere.

`Done when`
- No state leakage between screens.
- No stale data flashes after rapid filter changes.

### 12. API Contract Hardening
`Why`
- Beautiful UI collapses if API responses are inconsistent or fragile.

`How`
- Publish OpenAPI schema for all endpoints used by iOS UI.
- Add typed client models in frontend (TypeScript migration recommended).
- Add backend contract tests for required fields and nullability.

`Done when`
- Typed API client compiles with no `any` in critical paths.
- Contract tests run in CI.

---

## Phase 6: Performance and Reliability

### 13. Establish Performance Budgets
`Why`
- Top iOS apps feel instant; poor startup/frame pacing kills ratings.

`How`
- Define budgets:
  - cold start interactive target
  - max JS/CSS bundle size
  - chart render budget
- Add code splitting by screen.
- Lazy-load heavy chart/report modules.

`Done when`
- Bundle warnings are resolved or justified with documented tradeoffs.
- Measured startup and navigation are within targets on mid-tier iPhones.

### 14. Offline and Resilience Strategy
`Why`
- Analytics users often revisit recent reports; offline continuity improves trust.

`How`
- Cache last successful report payloads by race ID.
- Add explicit offline UI state and retry actions.
- Use skeleton loading states, not spinner-only UX.

`Done when`
- App handles network loss gracefully without hard dead-ends.

### 15. Error UX and Recovery Flows
`Why`
- High-quality apps make failures understandable and recoverable.

`How`
- Standardize error categories:
  - no results
  - validation
  - network
  - backend unavailable
- Provide clear next action in each error block.
- Log structured errors with correlation IDs for backend debugging.

`Done when`
- Every error state shows a recommended recovery path.

---

## Phase 7: Accessibility and Inclusion

### 16. Accessibility-First QA Pass
`Why`
- App Store quality and long-term product strength require inclusive UX.

`How`
- Enforce:
  - color contrast compliance
  - dynamic type support
  - VoiceOver labels and order
  - reduced motion support
  - touch target minimums
- Add accessibility test checklist to PR template.

`Done when`
- Core flows are usable with VoiceOver and increased text size.

---

## Phase 8: Native iOS Quality Decision

### 17. Decide Hybrid vs Native End-State
`Why`
- "Most beautiful iOS data apps" usually rely on native UI frameworks for polish.

`How`
- Keep Capacitor for short-term speed, but set an explicit decision gate:
  - If UX/perf ceilings remain, begin SwiftUI client migration.
- Native migration path:
  1. Keep FastAPI backend unchanged.
  2. Generate typed API models.
  3. Rebuild shell/navigation/charts in SwiftUI + native charting.
  4. Preserve parity with existing feature tiers.

`Done when`
- Written architecture decision record exists with measurable criteria.

---

## Phase 9: Measurement, Iteration, and App Store Execution

### 18. Product Analytics and Experimentation
`Why`
- Top-ranking apps iterate from real usage data, not assumptions.

`How`
- Instrument key events:
  - search started/completed
  - report generated
  - chart interaction
  - session completion
- Define funnel and retention dashboards.
- Run A/B tests for onboarding and report layout variants.

`Done when`
- Weekly dashboard reports conversion and retention.

### 19. App Store Optimization (ASO) and Positioning
`Why`
- Great UI is necessary but not sufficient for category leadership.

`How`
- Build ASO package:
  - keyword strategy
  - subtitle and description tested by market
  - screenshot narrative showing insight value, not just UI
  - preview video with actual use-case outcome
- Localize metadata for top target regions.

`Done when`
- Store page assets are performance-tested and updated from analytics.

### 20. Ratings and Review System
`Why`
- Top charts are driven by rating volume and positive sentiment.

`How`
- Trigger review prompt after successful "aha" moments (not random timing).
- Add in-app feedback channel before public review for negative sentiment.
- Triage feedback weekly into bug/ux/perf categories.

`Done when`
- Review flow is live with measurable conversion and reduced negative churn.

---

## Delivery Plan (Practical Sequencing)

### Sprint 1 (Foundation and Mobile Usability)
- Steps: 1, 2, 3, 4, 5, 10
- Output:
  - clear product wedge
  - new navigation shell
  - modularized UI architecture
  - tokenized design baseline

### Sprint 2 (Data UX and Performance)
- Steps: 6, 8, 9, 11, 13, 15
- Output:
  - high-quality chart interactions on touch
  - predictable state behavior
  - measurable performance improvement

### Sprint 3 (Polish and Go-To-Market)
- Steps: 14, 16, 18, 19, 20
- Output:
  - resilient app behavior
  - accessibility compliance
  - analytics and ASO machine in place

### Strategic Track (Parallel ADR)
- Step: 17
- Output:
  - explicit decision on Capacitor end-state vs SwiftUI migration

---

## Engineering Standards Required for Execution
- No feature merges without:
  - visual QA on iPhone viewport matrix
  - accessibility checklist pass
  - performance budget check
  - unit/integration tests updated
- Enforce typed API boundaries before major UI expansion.
- Keep design debt backlog explicit; never hide polish debt in future work.

---

## First 15 Tickets for the Next Agent
1. Create product brief (`persona`, `job`, `hero workflow`).
2. Implement bottom tab navigation shell and route separation.
3. Split `App.jsx` into per-screen modules.
4. Add centralized design token file and replace hardcoded values.
5. Convert advanced filters to collapsible sections.
6. Replace hover-only chart interactions with tap-first model.
7. Build reusable chart primitives and remove duplicated chart framing.
8. Introduce screen-level loading skeletons.
9. Add structured error state components with retry actions.
10. Add request cancellation and stale response guards globally.
11. Establish performance budget CI check for bundle size.
12. Add accessibility test checklist and VoiceOver labels.
13. Instrument analytics events for primary funnel.
14. Create ASO screenshot storyboard with narrative copy.
15. Write ADR on hybrid vs native iOS future with success criteria.

---

## North Star for Design Quality
If a screen does not answer this in under 5 seconds, it is not good enough:
- What am I looking at?
- What is the key insight?
- What should I do next?

When this is true across all core screens, and the app feels smooth, readable, and trustworthy on any iPhone size, you are close to top-tier category quality.

