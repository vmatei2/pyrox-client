#!/usr/bin/env python3
"""
Verify DuckDB schema contracts for Pyrox reporting tables.

Usage:
    python scripts/verify_duckdb_schema.py /path/to/db.duckdb
    DUCKDB_PATH=/path/to/db.duckdb python scripts/verify_duckdb_schema.py
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable
from dotenv import load_dotenv


load_dotenv()

import duckdb


def _normalize_type(raw_type: str) -> str:
    cleaned = raw_type.strip().split()[0]
    return cleaned.split("(")[0].upper()


def _type_matches(actual: str, expected: Iterable[str]) -> bool:
    normalized = _normalize_type(actual)
    return normalized in {value.upper() for value in expected}


def _fetch_table_columns(con: duckdb.DuckDBPyConnection, table: str) -> dict[str, str]:
    rows = con.execute(f"PRAGMA table_info('{table}')").fetchall()
    return {name: col_type for _, name, col_type, *_ in rows}


def _print_header(title: str) -> None:
    print(f"\n== {title} ==")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DuckDB schema contracts.")
    parser.add_argument(
        "database",
        nargs="?",
        help="Path to the DuckDB file (or set DUCKDB_PATH).",
    )
    args = parser.parse_args()

    db_path = args.database or os.getenv("DUCKDB_PATH")
    if not db_path:
        print("ERROR: database path is required (arg or DUCKDB_PATH).")
        return 2

    if not os.path.exists(db_path):
        print(f"ERROR: database path not found: {db_path}")
        return 2

    contracts = {
        "race_results": {
            "required": [
                "result_id",
                "season",
                "location",
                "year",
                "event_id",
                "name",
            ],
            "optional": [
                "age_group",
                "division",
                "event_name",
                "gender",
                "name_raw",
                "nationality",
                "roxzone_time",
                "run1_time",
                "run2_time",
                "run3_time",
                "run4_time",
                "run5_time",
                "run6_time",
                "run7_time",
                "run8_time",
                "run_time",
                "total_time",
                "skiErg_time",
                "sledPush_time",
                "sledPull_time",
                "burpeeBroadJump_time",
                "rowErg_time",
                "farmersCarry_time",
                "sandbagLunges_time",
                "wallBalls_time",
                "work_time",
                "roxzone_time_min",
                "run1_time_min",
                "run2_time_min",
                "run3_time_min",
                "run4_time_min",
                "run5_time_min",
                "run6_time_min",
                "run7_time_min",
                "run8_time_min",
                "run_time_min",
                "total_time_min",
                "skiErg_time_min",
                "sledPush_time_min",
                "sledPull_time_min",
                "burpeeBroadJump_time_min",
                "rowErg_time_min",
                "farmersCarry_time_min",
                "sandbagLunges_time_min",
                "wallBalls_time_min",
                "work_time_min",
            ],
            "types": {
                "result_id": ["VARCHAR"],
                "season": ["INTEGER", "BIGINT"],
                "location": ["VARCHAR"],
                "year": ["INTEGER", "BIGINT"],
                "event_id": ["VARCHAR"],
                "name": ["VARCHAR"],
                "age_group": ["VARCHAR"],
                "division": ["VARCHAR"],
                "event_name": ["VARCHAR"],
                "gender": ["VARCHAR"],
                "name_raw": ["VARCHAR"],
                "nationality": ["VARCHAR"],
                "roxzone_time": ["VARCHAR"],
                "run1_time": ["VARCHAR"],
                "run2_time": ["VARCHAR"],
                "run3_time": ["VARCHAR"],
                "run4_time": ["VARCHAR"],
                "run5_time": ["VARCHAR"],
                "run6_time": ["VARCHAR"],
                "run7_time": ["VARCHAR"],
                "run8_time": ["VARCHAR"],
                "run_time": ["VARCHAR"],
                "total_time": ["VARCHAR"],
                "skiErg_time": ["VARCHAR"],
                "sledPush_time": ["VARCHAR"],
                "sledPull_time": ["VARCHAR"],
                "burpeeBroadJump_time": ["VARCHAR"],
                "rowErg_time": ["VARCHAR"],
                "farmersCarry_time": ["VARCHAR"],
                "sandbagLunges_time": ["VARCHAR"],
                "wallBalls_time": ["VARCHAR"],
                "work_time": ["VARCHAR"],
                "roxzone_time_min": ["DOUBLE", "FLOAT"],
                "run1_time_min": ["DOUBLE", "FLOAT"],
                "run2_time_min": ["DOUBLE", "FLOAT"],
                "run3_time_min": ["DOUBLE", "FLOAT"],
                "run4_time_min": ["DOUBLE", "FLOAT"],
                "run5_time_min": ["DOUBLE", "FLOAT"],
                "run6_time_min": ["DOUBLE", "FLOAT"],
                "run7_time_min": ["DOUBLE", "FLOAT"],
                "run8_time_min": ["DOUBLE", "FLOAT"],
                "run_time_min": ["DOUBLE", "FLOAT"],
                "total_time_min": ["DOUBLE", "FLOAT"],
                "skiErg_time_min": ["DOUBLE", "FLOAT"],
                "sledPush_time_min": ["DOUBLE", "FLOAT"],
                "sledPull_time_min": ["DOUBLE", "FLOAT"],
                "burpeeBroadJump_time_min": ["DOUBLE", "FLOAT"],
                "rowErg_time_min": ["DOUBLE", "FLOAT"],
                "farmersCarry_time_min": ["DOUBLE", "FLOAT"],
                "sandbagLunges_time_min": ["DOUBLE", "FLOAT"],
                "wallBalls_time_min": ["DOUBLE", "FLOAT"],
                "work_time_min": ["DOUBLE", "FLOAT"],
            },
        },
        "athletes": {
            "required": ["athlete_id", "canonical_name"],
            "optional": ["gender", "nationality"],
            "types": {
                "athlete_id": ["VARCHAR"],
                "canonical_name": ["VARCHAR"],
                "gender": ["VARCHAR"],
                "nationality": ["VARCHAR"],
            },
        },
        "athlete_results": {
            "required": ["athlete_id", "result_id", "link_confidence", "link_method"],
            "optional": [],
            "types": {
                "athlete_id": ["VARCHAR"],
                "result_id": ["VARCHAR"],
                "link_confidence": ["DOUBLE", "FLOAT", "DECIMAL", "NUMERIC"],
                "link_method": ["VARCHAR"],
            },
        },
        "athlete_index": {
            "required": [
                "athlete_id",
                "canonical_name",
                "name_lc",
                "race_count",
            ],
            "optional": ["gender", "nationality", "avg_total_time", "avg_run_ratio"],
            "types": {
                "athlete_id": ["VARCHAR"],
                "canonical_name": ["VARCHAR"],
                "name_lc": ["VARCHAR"],
                "gender": ["VARCHAR"],
                "nationality": ["VARCHAR"],
                "race_count": ["INTEGER", "BIGINT"],
                "avg_total_time": ["DOUBLE", "FLOAT"],
                "avg_run_ratio": ["DOUBLE", "FLOAT"],
            },
        },
    }

    con = duckdb.connect(db_path, read_only=True)
    try:
        errors: list[str] = []
        for table, contract in contracts.items():
            _print_header(table)
            try:
                columns = _fetch_table_columns(con, table)
            except duckdb.CatalogException:
                msg = f"Missing table: {table}"
                print(f"ERROR: {msg}")
                errors.append(msg)
                continue

            required = set(contract["required"])
            optional = set(contract["optional"])
            expected = required | optional

            missing = sorted(required - set(columns))
            if missing:
                msg = f"Missing required columns: {', '.join(missing)}"
                print(f"ERROR: {msg}")
                errors.append(f"{table}: {msg}")
            else:
                print("OK: all required columns present")

            extra = sorted(set(columns) - expected)
            if extra:
                print(f"WARN: extra columns present: {', '.join(extra)}")

            for name, expected_types in contract["types"].items():
                if name not in columns:
                    continue
                actual = columns[name]
                if not _type_matches(actual, expected_types):
                    msg = f"{name} has type {actual}, expected {expected_types}"
                    print(f"ERROR: {msg}")
                    errors.append(f"{table}: {msg}")
            if table in columns:
                pass

        if errors:
            _print_header("Summary")
            for err in errors:
                print(f"ERROR: {err}")
            return 1
        print("\nSchema verification passed.")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    main()
