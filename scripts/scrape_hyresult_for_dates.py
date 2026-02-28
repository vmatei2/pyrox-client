import argparse
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}


def parse_event(url):

    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(" ", strip=True)
    year = int(re.search(r"20\d{2}", text).group())

    month_day = re.search(
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d+",
        text
    ).group()
    

    # the interpreter below expects Sep
    month_day = month_day.replace("Sept", "Sep")
    dt = datetime.strptime(
        f"{month_day} {year}",
        "%b %d %Y"
    )

    return dt

def save_events_dates(event_dates: dict, path: str):
    """
    Save the generated dictionary of events dates to a
    given path
    """
    json_ready = {
        event: dt.isoformat()
        for event, dt in event_dates.items()
    }

    with open(path, "w") as f:
        json.dump(json_ready, f, indent=2)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape HYRESULT event start dates for a given season."
    )
    parser.add_argument(
        "--season",
        type=int,
        default=8,
        help="HYROX season number to scrape (default: 8).",
    )
    args = parser.parse_args()
    if args.season < 1:
        parser.error("--season must be an integer >= 1.")
    return args


def main() -> None:
    args = _parse_args()
    season = args.season
    url = f"https://www.hyresult.com/events?s={season}&tab=all"

    print(f"Scraping HYRESULT season={season} from {url}")

    r = requests.get(url, headers=headers)

    print(r.status_code)
    print(r.text[:500])

    soup = BeautifulSoup(r.text, "html.parser")

    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith(f"/event/s{season}-"):
            links.append("https://www.hyresult.com" + href)

    links = sorted(set(links))

    print(len(links))

    EVENT_DATES = {}
    for url in links:
        r = requests.get(url=url, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")

        title = soup.find("h1").text.strip()

        start_date = parse_event(url)

        EVENT_DATES[title] = start_date
        print(f"{title} - {start_date}")

    output_path = Path.cwd() / f"EVENT_START_DATES_SEASON_{season}.json"
    save_events_dates(EVENT_DATES, str(output_path))
    print(f"Saved {len(EVENT_DATES)} events to {output_path}")


if __name__ == "__main__":
    main()
