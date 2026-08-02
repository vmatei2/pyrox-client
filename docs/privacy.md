# Privacy policy

Effective date: 1 August 2026

Pyrox works without user accounts. This policy covers the documentation site,
web and iOS clients, REST API, and public MCP endpoint.


## What the Pyrox API records

The API accepts athlete names, race filters and report parameters. Application
logs record the HTTP method, route path, response status and elapsed time. They
don't record query strings, so an athlete name sent as a query parameter isn't
written by the Pyrox request logger.

The rate limiter reads the client IP supplied by Fly.io and keeps its counters
in process memory. Pyrox doesn't write those counters to its DuckDB database or
to a separate user database.

Fly.io may retain platform and proxy logs outside the application process. This
repository doesn't set or control that provider retention period.

## How request data is used

Pyrox uses request data to return race reports, enforce the public rate limit,
diagnose failures and investigate abuse. It doesn't sell personal data or use
requests for advertising profiles.

The underlying race results contain public registration and timing data. Pyrox
doesn't claim ownership of those records.

## Your choices

You can use the Python client to read public Parquet files without sending
queries to the hosted API. To report a privacy problem or request a correction,
open a [GitHub issue](https://github.com/vmatei2/pyrox-client/issues). Don't put
private information in a public issue; ask the maintainer for a private contact
route first.
