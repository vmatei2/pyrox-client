---
updated: 2026-07-19
sources:
  - INVESTIGATE_REPORTING_SLOWNESS.md
  - ios_path_to_completion.md
---

# Active work

Living page. Update it when you pick up or close out anything here.

## Race report slowness: fix landed, verification outstanding

On 2026-07-18 the production `/api/reports/{result_id}` endpoint hung past 120
seconds with HTTP/2 framing errors (brief: `INVESTIGATE_REPORTING_SLOWNESS.md`
at the repo root). Commit `a9cd559` the same day introduced
`race_report_loader.py`, which bounds memory by computing stats inside DuckDB.

Still open as of 2026-07-19: nobody has re-timed the reproduction id
`5da3237dd0ce736c004623f21fd5383d` against production, so we don't know whether
the framing errors were the slowness or a separate Fly-edge problem. The brief
says to delete itself once done and it still exists. Suspect #1 from the brief
also remains: a new `ReportingClient` and DuckDB connection is built per
request.

## iOS app

`ios_path_to_completion.md` tracks the Capacitor iOS effort; QA state lives in
`ui/test_plan.md` and `ui/UX_ACCEPTANCE_CHECKLIST.md`.

## Housekeeping

Uncommitted deletions sit in git status (`models/hyrox_live_predictor.joblib`,
`quantifying_uncertianty.ipynb`) along with scattered `.DS_Store` files, and
`papers/` plus `docs/research/` are untracked. Decide and commit.
