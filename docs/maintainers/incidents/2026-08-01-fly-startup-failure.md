# Fly startup failure: schema mismatch and MCP dependency

**Date:** 2026-08-01  
**Service:** `pyrox-api` on Fly.io  
**Status:** Resolved in Fly release v67

## Summary

The reporting service could not start because the database producer and consumer
were not updated together. `hyrox_analysis` published a schema-version-2 DuckDB
artifact, while `pyrox-client` accepted only schema version 1. The boot-time
artifact check exited before Uvicorn bound port 8080, causing a restart loop.

After that mismatch was fixed, the next startup exposed a second independent
problem: the Docker build resolved the newly released `mcp==2.0.0`, which no
longer provided `mcp.server.fastmcp`. The application failed while importing the
MCP server.

## What happened

1. On 2026-07-25, `hyrox_analysis` commit `950bc1a` changed its reporting
   database from schema version 1 to 2. The change added the nullable
   `race_results.source_result_id` column.
2. On 2026-07-30, a schema-version-2 artifact was published through
   `db/latest.json`.
3. `pyrox-client` still had `SUPPORTED_SCHEMA_VERSION = 1` in
   `pyrox_api_service/fetch_db.py`.
4. On 2026-08-01, a change touching `pyproject.toml` triggered Fly release v65.
   A cold start read the new pointer and raised:

   ```text
   ArtifactFetchError: pointer schema_version 2 is newer than supported 1
   ```

5. Because the Docker command runs `fetch_db && uvicorn`, Uvicorn never
   started. Fly repeatedly restarted the machine, while the deployment workflow
   still reported success.
6. Accepting schema version 2 allowed artifact installation to finish, then
   exposed the unbounded MCP dependency failure:

   ```text
   ModuleNotFoundError: No module named 'mcp.server.fastmcp'
   ```

## Manual repair

Two changes were tested on fix branches, fast-forwarded into `main`, and
deployed:

- Commit `4a3c93b` raised `SUPPORTED_SCHEMA_VERSION` to 2 and added an explicit
  regression test that accepts v2 while the existing newer-version test rejects
  v3.
- Commit `450e820` constrained the runtime dependency to
  `mcp>=1.2.0,<2` and updated `uv.lock`.

The schema change was safe for the existing reporting queries because version 2
only added a nullable column; existing tables, columns, and `result_id` were
unchanged.

## Verification

The repair was verified with:

- download and SHA-256 verification of the exact 1,257,254,912-byte production
  schema-v2 artifact;
- local REST health, filter, and MCP smoke tests against that artifact;
- a clean dependency resolution, which selected MCP 1.29 and imported the
  composed application successfully;
- the full Python suite: `132 passed, 3 skipped`;
- live Fly release v67: `/api/health` returned HTTP 200;
- the live MCP smoke test discovered and invoked the expected ten tools.

## Remaining operational concern

The machine is configured to stop when idle. Every cold start currently hashes
the complete 1.25 GB database before starting Uvicorn. This takes roughly 90
seconds on the Fly volume, during which callers receive 502 responses or MCP
timeouts. The service is healthy after startup, but this cold-start behavior
should be addressed separately.

Atomic artifact replacement also temporarily requires both the old and new
database files. The current 3 GB Fly volume reached approximately 2.3 GB during
the repair, leaving limited room for future artifact growth.

## Deferred automation: link the repositories

The first automation step should be a pre-publication compatibility gate:

```text
hyrox_analysis builds candidate DuckDB
                 |
                 v
run pyrox-client's verifier against the exact candidate
                 |
          +------+------+
          |             |
        pass           fail
          |             |
publish artifact     quarantine candidate
and latest.json      block publication
                     create issue or draft PR
```

### Ownership

- `pyrox-client` should own one command such as:

  ```bash
  python -m pyrox_api_service.verify_database --database pyrox_duckdb
  ```

  The verifier should open the candidate database and exercise the required
  tables, columns, types, and representative production queries. It should emit
  stable JSON diagnostics and return nonzero for incompatibility.

- `hyrox_analysis` should build and verify its candidate normally, then check
  out the production `pyrox-client` revision and run that verifier before it is
  allowed to update `latest.json`.

### Failure behavior

When compatibility fails, the producer workflow should:

1. leave the current production pointer unchanged;
2. retain the immutable candidate or a minimal schema fixture;
3. write the producer commit, consumer commit, artifact digest, schema diff,
   and remediation steps to the GitHub Actions summary;
4. create or update a downstream issue or draft pull request.

Automatically increasing `SUPPORTED_SCHEMA_VERSION` is not sufficient because
it would claim compatibility without testing it.

### Later improvements

- Let `pyrox-client` own a consumer-specific production pointer and promote
  producer candidates only after validation.
- Add a reliable post-deploy REST and MCP health gate so a stopped or crashing
  machine cannot produce a green deployment.
- Continue serving the last compatible artifact in a clearly reported stale or
  degraded state when a future candidate is rejected.
- Store verified pointer metadata beside the cached database so unchanged cold
  starts do not hash the entire artifact.
- Add producer commit and workflow-run provenance to `latest.json`.
- Increase the Fly volume before artifact growth makes atomic replacement
  unsafe.

## Completion criteria for the automation

The follow-up is complete when an intentionally incompatible candidate:

- cannot change the production pointer;
- produces a clear, reproducible downstream work item;
- names the exact producer commit, consumer commit, and artifact digest;
- leaves the currently compatible service available;
- becomes publishable automatically after the downstream compatibility change
  is merged and verified.
