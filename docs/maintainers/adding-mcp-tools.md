# Adding MCP Tools

This guide walks through the process of adding new tools to the Pyrox MCP
server. It uses the `list_races` and `get_race_summary` tools as a worked
example.

## Architecture

Every MCP tool passes through five layers:

```
ReportingQueries method  (reporting_queries.py)
        |
   REST endpoint          (app.py)
        |
   MCP tool function      (mcp_tools.py)
        |
   Tool registration      (mcp_app.py)
        |
   Smoke test set          (scripts/smoke_mcp.py)
```

The MCP tool functions never touch the database directly. They call the REST
API in-process via `TestClient` (no network socket), so they get the same
validation, error mapping, and logging as external HTTP callers.

## Step-by-step

### 1. Add a query method to `ReportingQueries`

All data access lives in `reporting_queries.py`. Add a new method to the
`ReportingQueries` class.

**Example: `list_races`**

```python
def list_races(self, *, season=None, gender=None) -> dict:
    con = self.connection()
    clauses, params = [], []

    if season is not None:
        clauses.append("season = ?")
        params.append(int(season))
    if normalize_optional_text(gender) is not None:
        gc, gp = _gender_filter(gender)
        clauses.extend(gc)
        params.extend(gp)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    df = con.execute(f"""
        SELECT event_name, event_id, location, season, year,
               COUNT(*) AS participant_count
        FROM race_results {where_sql}
        GROUP BY event_name, event_id, location, season, year
        ORDER BY season DESC, year DESC, lower(location)
    """, params).fetchdf()

    return {"filters": {...}, "count": len(df), "races": df_to_records(df)}
```

**Key conventions:**

- Use keyword-only arguments (`*` separator).
- Normalize text inputs with `normalize_optional_text()`.
- Handle gender M/male and F/female equivalence via `_gender_filter()`.
- Return a dict with an echo of the filters applied, a count, and the data.
- Raise `ReportingNotFoundError` (404) or `ReportingQueryError` (400) for
  expected failures; `app.py` maps these to HTTP status codes.
- Reuse existing helpers: `_describe_times()` for summary stats,
  `df_to_records()` for DataFrame-to-JSON conversion, `_build_histogram()`
  for distributions.

### 2. Add a REST endpoint in `app.py`

Wire the query method to a FastAPI route. The endpoint handles HTTP-specific
concerns (parameter validation via `Query`, error mapping via `_query()`).

```python
@app.get("/api/races")
def list_races(
    season: Optional[int] = Query(None, ge=1),
    gender: Optional[str] = Query(None),
) -> dict:
    return _query(queries.list_races, season=season, gender=gender)
```

The `_query()` wrapper catches exceptions from the query layer and converts
them to `HTTPException` responses.

### 3. Add an MCP tool function in `mcp_tools.py`

Each tool is a plain Python function that calls the REST endpoint via `_get()`.

```python
def list_races(season=None, gender=None) -> dict:
    """Available races with participant counts, optionally filtered by season or gender.

    Returns distinct races showing event name, location, season, year, and
    how many athletes participated. Use this to discover which races exist
    before requesting a race summary.
    """
    return _get("/api/races", {"season": season, "gender": gender})
```

**The docstring is the tool description** that LLM callers see. Write it to
guide the model on when and how to use the tool. Mention related tools
(e.g., "use `list_races` first to discover valid season + location pairs").

### 4. Register the tool in `mcp_app.py`

Add a tuple to the `TOOLS` constant:

```python
TOOLS = (
    ...
    (mcp_tools.list_races, "List available races"),
    ...
)
```

The title string appears in MCP client UIs. All tools share the `READ_ONLY_TOOL`
annotation (read-only, non-destructive, idempotent, closed-world).

### 5. Update the smoke test

Add the tool name to `EXPECTED_TOOL_NAMES` in `scripts/smoke_mcp.py`:

```python
EXPECTED_TOOL_NAMES = frozenset({
    ...
    "list_races",
    ...
})
```

### 6. Write tests in `tests/test_mcp_tools.py`

Tests call the tool functions directly (no MCP session needed). Seed a
temporary DuckDB, point `PYROX_DUCKDB_PATH` at it via `monkeypatch`, and
assert on the returned dict.

```python
def test_list_races_returns_distinct_races_with_counts(tmp_path, monkeypatch):
    db_path = tmp_path / "mcp-races.db"
    con = _create_db(db_path)
    _seed_races(con)
    con.close()

    monkeypatch.setenv("PYROX_DUCKDB_PATH", str(db_path))
    result = mcp_tools.list_races()

    assert result["count"] == 3
    london = next(r for r in result["races"] if r["location"] == "london")
    assert london["participant_count"] == 3
```

Always update `test_mcp_server_registers_expected_tools` to include the new
tool names.

## Design principles

1. **Intent-shaped tools, not raw SQL.** Each tool answers a specific question
   an LLM might ask. Never expose a generic `query(sql)` tool.

2. **Errors as dicts, not exceptions.** The `_get()` helper converts non-200
   responses to `{"error": ..., "status_code": ...}` so the LLM can reason
   about failures without the MCP session crashing.

3. **Server-side aggregation.** Distributions, percentiles, and summary stats
   are computed in the query layer, not by the LLM. This keeps answers
   deterministic and avoids dumping large DataFrames into model context.

4. **Reuse helpers.** `_describe_times()` returns
   `{count, min, max, mean, median, p10, p90}` for any numeric column.
   `_gender_filter()` handles M/male F/female equivalence. `df_to_records()`
   converts DataFrames to JSON-safe record lists.

5. **Docstrings are LLM-facing.** The tool's docstring becomes its description
   in the MCP tool listing. Write it for the model: explain what the tool
   does, when to use it, and which tool to call first.

## Verification checklist

- [ ] `pytest tests/test_mcp_tools.py -v` passes (new + existing tests)
- [ ] `pytest tests/ -v` shows no regressions
- [ ] New tool appears in `test_mcp_server_registers_expected_tools`
- [ ] New tool name is in `EXPECTED_TOOL_NAMES` in `smoke_mcp.py`
- [ ] Tool docstring clearly describes purpose and usage flow
