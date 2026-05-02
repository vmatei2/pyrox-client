from __future__ import annotations

import json
from datetime import datetime

from scripts.scrape_hyresult_for_dates import (
    dedupe_event_dates,
    load_existing_event_dates,
    merge_event_date,
)


def test_load_existing_event_dates_preserves_prior_partial_scrapes(tmp_path):
    path = tmp_path / "EVENT_START_DATES_SEASON_8.json"
    path.write_text(
        json.dumps(
            {
                "HYROX Acapulco 2025": "2025-09-06T00:00:00",
                "HYROX Paris 2026": "2026-04-27T00:00:00",
            }
        ),
        encoding="utf-8",
    )

    events = load_existing_event_dates(path)

    assert events == {
        "HYROX Acapulco 2025": datetime(2025, 9, 6),
        "HYROX Paris 2026": datetime(2026, 4, 27),
    }


def test_load_existing_event_dates_returns_empty_for_missing_file(tmp_path):
    assert load_existing_event_dates(tmp_path / "missing.json") == {}


def test_dedupe_event_dates_prefers_local_title_and_earliest_start():
    events = dedupe_event_dates(
        {
            "HYROX Cologne 2026 / Köln": datetime(2026, 4, 16),
            "HYROX Cologne 2026": datetime(2026, 4, 19),
            "HYROX Lisbon 2026": datetime(2026, 5, 1),
            "HYROX Lisbon 2026 / Lisboa": datetime(2026, 5, 1),
        }
    )

    assert events == {
        "HYROX Cologne 2026 / Köln": datetime(2026, 4, 16),
        "HYROX Lisbon 2026 / Lisboa": datetime(2026, 5, 1),
    }


def test_merge_event_date_does_not_reintroduce_title_variant_duplicates():
    events = {"HYROX Wuhan 2026 / 武汉市": datetime(2026, 4, 11)}

    merge_event_date(events, "HYROX Wuhan 2026", datetime(2026, 4, 11))

    assert events == {"HYROX Wuhan 2026 / 武汉市": datetime(2026, 4, 11)}
