"""Scrape HYRESULT monthly event listings into ingest start-date JSON.

The ingest job expects start-date files beside ``scripts/ingest_duckdb_from_s3.py``
with names like ``scripts/EVENT_START_DATES_SEASON_8.json``. This scraper writes
``EVENT_START_DATES_SEASON_<season>.json`` to the current working directory, so
run it from ``scripts/`` or move the generated file there before ingesting.

Example:
    cd scripts
    uv run python scrape_hyresult_for_dates.py --season 8 --year 2026 \
        --start-month 1 --end-month 7

The output is a mapping from HYRESULT event titles to ISO datetimes. During
ingest, event titles are normalized into ``(season, location, year)`` keys and
matched against S3/DuckDB partition slugs. If the ingest runner later reports
``Missing start_date mappings`` with a different ``location``/``normalized_target``,
update ``DB_LOCATION_ALIASES`` in ``ingest_duckdb_from_s3.py`` to map the
S3/DuckDB slug to the JSON-derived slug.

When the output file already exists, this script loads it first and merges the
newly scraped dates into it. Existing events outside the scraped year/month range
are preserved, which is important because one HYROX season spans multiple
calendar years.
"""

import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

MONTH_ABBR = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Sept": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

# Matches the date label shown on monthly listing cards, e.g.:
#   "Mar 24–29"        → month=Mar, day=24
#   "Apr 11, 2026"     → month=Apr, day=11
#   "Apr 29 – May 4"   → month=Apr, day=29  (cross-month range, take first)
DATE_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep(?:t)?|Oct|Nov|Dec)\s+(\d{1,2})"
)


def parse_start_date(date_text: str, year: int) -> datetime | None:
    """
    Extract the *start* date from a listing card's date label.
    Returns a datetime or None if unparseable.
    """
    m = DATE_RE.search(date_text)
    if not m:
        return None
    month_str, day_str = m.group(1), m.group(2)
    month = MONTH_ABBR[month_str]
    return datetime(year, month, int(day_str))


def parse_relative_start_date(date_text: str, today: datetime | None = None) -> datetime | None:
    """
    Convert relative listing labels such as "14 days ago" into a concrete date.
    """
    today = today or datetime.now()
    text = date_text.lower()

    if "today" in text:
        return today.replace(hour=0, minute=0, second=0, microsecond=0)
    if "yesterday" in text:
        return (today - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if "tomorrow" in text:
        return (today + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    days_ago_match = re.search(r"\b(\d+)\s+days?\s+ago\b", text)
    if days_ago_match:
        return (today - timedelta(days=int(days_ago_match.group(1)))).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    weeks_ago_match = re.search(r"\b(\d+)\s+weeks?\s+ago\b", text)
    if weeks_ago_match:
        return (today - timedelta(weeks=int(weeks_ago_match.group(1)))).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    return None


def parse_event_page_start_date(url: str, default_year: int) -> datetime | None:
    """
    Fallback for cards that only expose relative labels or omit date text entirely.
    """
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(" ", strip=True)

    match = re.search(
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep(?:t)?|Oct|Nov|Dec)\s+(\d{1,2})"
        r"(?:\s*[–-]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep(?:t)?|Oct|Nov|Dec)?\s*\d{1,2})?"
        r"(?:,?\s+(\d{4}))?",
        text,
    )
    if not match:
        return None

    month_str, day_str, year_str = match.group(1), match.group(2), match.group(3)
    year = int(year_str) if year_str else default_year
    return datetime(year, MONTH_ABBR[month_str], int(day_str))


def scrape_month(year: int, month: int, season: int) -> dict[str, datetime]:
    """
    Scrape one monthly events page and return {event_title: start_datetime}.
    Dates are extracted from the listing cards (no per-event page requests needed).
    """
    url = f"https://www.hyresult.com/events/{year}/{month:02d}?s={season}&tab=all"
    print(f"  Fetching {url}")
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    events: dict[str, datetime] = {}

    # Each event card is an <a> whose href starts with /event/s{season}-
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith(f"/event/s{season}-"):
            continue
        event_url = f"https://www.hyresult.com{href}"

        # Title is in an <h2> inside the card
        h2 = a.find("h2")
        if not h2:
            continue
        title = h2.get_text(" ", strip=True)

        # The date label is plain text somewhere in the card; grab all text
        # and look for the first date-like pattern.
        card_text = a.get_text(" ", strip=True)

        # Remove the title itself from the text so we don't accidentally
        # match digits inside the title.
        card_text_clean = card_text.replace(title, "")

        dt = parse_start_date(card_text_clean, year)
        if dt is None:
            dt = parse_relative_start_date(card_text_clean)
        if dt is None:
            # Fallback: the event might list a full date like "Apr 11, 2026"
            # Try matching with explicit year
            m = re.search(
                r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep(?:t)?|Oct|Nov|Dec)"
                r"\s+(\d{1,2}),?\s+(\d{4})",
                card_text_clean,
            )
            if m:
                month_str, day_str, yr_str = m.group(1), m.group(2), m.group(3)
                dt = datetime(int(yr_str), MONTH_ABBR[month_str], int(day_str))
        if dt is None:
            dt = parse_event_page_start_date(event_url, year)

        if dt and title not in events:
            events[title] = dt
            print(f"    {title} → {dt.date()}")
        elif dt is None:
            print(f"    [WARN] Could not parse date for '{title}' — card text: {card_text_clean[:80]!r}")

    return events


def save_events_dates(event_dates: dict[str, datetime], path: str) -> None:
    json_ready = {event: dt.isoformat() for event, dt in event_dates.items()}
    with open(path, "w") as f:
        json.dump(json_ready, f, indent=2)


def sort_events_by_date(event_dates: dict[str, datetime]) -> dict[str, datetime]:
    return dict(sorted(event_dates.items(), key=lambda kv: kv[1]))


def load_existing_event_dates(path: Path) -> dict[str, datetime]:
    if not path.exists():
        return {}

    with path.open(encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected object payload in {path}")

    events: dict[str, datetime] = {}
    for title, raw_date in payload.items():
        if not isinstance(title, str) or not isinstance(raw_date, str):
            raise RuntimeError(f"Invalid event date entry in {path}: {title!r}")
        events[title] = datetime.fromisoformat(raw_date)
    return events


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape HYRESULT event start dates for a given season."
    )
    parser.add_argument("--season", type=int, default=8,
                        help="HYROX season number (default: 8).")
    parser.add_argument("--year", type=int, default=2026,
                        help="Calendar year to scrape (default: 2026).")
    parser.add_argument("--start-month", type=int, default=3,
                        help="First month to scrape, inclusive (default: 3 = March).")
    parser.add_argument("--end-month", type=int, default=7,
                        help="Last month to scrape, inclusive (default: 7 = July).")
    args = parser.parse_args()
    if not (1 <= args.start_month <= args.end_month <= 12):
        parser.error("--start-month and --end-month must satisfy 1 ≤ start ≤ end ≤ 12.")
    return args


def main() -> None:
    args = _parse_args()

    output_path = Path.cwd() / f"EVENT_START_DATES_SEASON_{args.season}.json"
    all_events = load_existing_event_dates(output_path)
    if all_events:
        print(f"Loaded {len(all_events)} existing events from {output_path}")

    for month in range(args.start_month, args.end_month + 1):
        month_name = datetime(args.year, month, 1).strftime("%B")
        print(f"\n── {month_name} {args.year} ──")
        month_events = scrape_month(args.year, month, args.season)
        # Keep the earliest date if an event spans two calendar months
        # and appears in both month pages.
        for title, dt in month_events.items():
            if title not in all_events or dt < all_events[title]:
                all_events[title] = dt

        all_events = sort_events_by_date(all_events)
        save_events_dates(all_events, str(output_path))
        print(f"  Saved {len(all_events)} events so far → {output_path}")

    all_events = sort_events_by_date(all_events)
    save_events_dates(all_events, str(output_path))
    print(f"\nSaved {len(all_events)} events → {output_path}")


if __name__ == "__main__":
    main()
