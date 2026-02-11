# HYROX UI Acceptance Checklist

Use this checklist before merging any UI-facing change.

## 1. Flow And CTA
- [ ] Each screen has one obvious primary action.
- [ ] Secondary actions are visually subordinate to the primary action.
- [ ] Multi-step flows show clear step progression.
- [ ] Users can recover from errors without dead ends.

## 2. Layout And Spacing
- [ ] Layout follows the 8px spacing rhythm.
- [ ] Sections have consistent vertical rhythm.
- [ ] Cards, panels, and charts share consistent padding.
- [ ] All controls align to a common grid on desktop and mobile.

## 3. Typography
- [ ] Heading hierarchy is clear in under 5 seconds.
- [ ] Body and helper text sizes are consistent by role.
- [ ] Muted text remains readable against background surfaces.
- [ ] No ad-hoc font/weight usage outside token scale.

## 4. Controls And States
- [ ] Inputs and buttons use a consistent height (48px minimum).
- [ ] Hover, active, loading, and disabled states are implemented.
- [ ] Selected states are clear and not color-only.
- [ ] Focus ring is visible and keyboard navigation is intact.

## 5. Visual Quality
- [ ] Surfaces and borders are consistent across screens.
- [ ] Shadows and depth are subtle and intentional.
- [ ] Color usage is purposeful (no decorative noise).
- [ ] UI feels minimal, premium, and confidence-building.

## 6. Accessibility
- [ ] Text contrast meets WCAG AA for normal content.
- [ ] Interactive targets are comfortable for touch (>=44px).
- [ ] Labels are explicit; no ambiguous placeholders-only controls.
- [ ] Screen-reader semantics are present for selectable/toggle-like controls.

## 7. Responsive And Platform
- [ ] Layout works on 390px width mobile viewport.
- [ ] Layout works on common desktop viewport (>=1280px).
- [ ] iOS safe-area behavior is validated in shell mode.
- [ ] No horizontal overflow in primary user flows.

## 8. Performance And Delivery
- [ ] Build passes without runtime warnings introduced by this PR.
- [ ] Avoid unnecessary re-renders in new components.
- [ ] Heavy UI code is split or deferred where possible.
- [ ] Visual polish changes do not regress data-loading clarity.

## 9. QA Signoff
- [ ] `npm run build` passes for `ui`.
- [ ] `pytest -q` passes for API/client integration impact.
- [ ] Screens validated: Report, Compare, Deepdive, Planner.
- [ ] Final pass done on both desktop and mobile layouts.
