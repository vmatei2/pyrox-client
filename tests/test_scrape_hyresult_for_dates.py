from __future__ import annotations

import json
from datetime import datetime

from scripts.scrape_hyresult_for_dates import load_existing_event_dates


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
