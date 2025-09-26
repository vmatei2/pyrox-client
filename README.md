# pyrox-client

Unofficial Python client for HYROX race results — load public results into pandas DataFrames.

[![PyPI - Version](https://img.shields.io/pypi/v/pyrox-client.svg)](https://pypi.org/project/pyrox-client/)
[![Wheel](https://img.shields.io/pypi/wheel/pyrox-client.svg)](https://pypi.org/project/pyrox-client/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy-lang.org/)
[![Downloads](https://static.pepy.tech/badge/pyrox-client/month)](https://pepy.tech/project/pyrox-client)

> Load HYROX race results into pandas in a few lines. Built for people who love fitness *and* data.

Unofficial Python client for HYROX race results — load public results into pandas DataFrames in a few lines. Built for people who love fitness and data: analyse performance trends, understand HYROX’s unique demands, and open up new research avenues. 

## Install

```commandline
uv pip install pyrox-client
```
or 
```commandline
pip install pyrox-client
```

## Quickstart
Below we have added two quick examples. One of loading race data - with different data requests, and one of retrieving race data / extracting athlete information and plotting values with example outputs to show a small glimpse of the analysis possible if 
retrieving the race data.

```commandline
import pyrox

# Create client
client = pyrox.PyroxClient()

# Discover available races
all_races = client.list_races()          
s6_races = client.list_races(season=6)   

# Get multiple races from a season
subset_s6 = client.get_season(season=6, locations=["london", "hamburg"])

# Get single race df
london_race = client.get_race(season=6, location="london")
rott_race = client.get_race(season=6, location="rotterdam")
london_male = client.get_race(season=6, location="london", gender="male")
#  Returning data for May (London Olympia race)
london_2025_s7 = client.get_race(season=7, location="london", year=2025)
#  Returning data for November (London Excel Race)
london_2024_s7 = client.get_race(season=7, location="london", year=2024)
```

## What's included? 

- Servers publicly available race results from the offical results website
- Historical coverage of Season 2-7 (for now) (season 5 and 6 are most used/tested in analysis; please open issues for any data problems spotted)
- Client-side caching by default (local). Set ```use_cache=False``` when querying ```get_race()``` or ```get_season()``` to opt out.
- Going forward - would like to add server-side computed stats and option for enriching filters (i..e "overall time sub 60 mins / only athletes with wall ball time sub 5 mins"")


## API

```commandline
list_races(season: int | None = None) -> pd.DataFrame
```

Returns a Dataframe of available races:
```commandline
from pyrox import PyroxClient

client = PyroxClient()
print(client.list_races(season=5).head(3))
#    season   location
# 0       5  amsterdam
# 1       5    anaheim
# 2       5  barcelona
```

```commandline
get_race(
    season: int,
    location: str,
    year: int | None = None,
    gender: str | None = None,      # "male" | "female" | "mixed"
    division: str | None = None,    # "open" | "pro" (case-insensitive contains)
    use_cache: bool = True,
) -> pd.DataFrame
```

Returns a single race as a pandas dataframe - with optional filtering
```commandline
get_season(
    season: int,
    locations: list[str] | None = None,
    use_cache: bool = True,
) -> pd.DataFrame
```
Returns a combinded Dataframe for a whole season (or a set of locations passed in)
```commandline
clear_cache(pattern: str = "*") -> None
```
Clears local cache entries (regex pattern search option included)

```commandline
cache_info() -> dict
```
Returns cache statistics: `````{"total_size": int, "total_items": int, "items": list[str]}`````

###  Example - compare an athlete's two races vs field averages

> below code requires ```pandas``` and ```numpy``` and the graphs are generated via ```matplotlib``` and ```seaborn```

```commandline
import pandas as pd
import numpy as np
import pyrox

client = pyrox.PyroxClient()

run_cols = [f"run{i}_time" for i in range(1, 8+1)]
station_cols = [
    "skiErg_time","sledPush_time","sledPull_time","burpeeBroadJump_time",
    "rowErg_time","farmersCarry_time","sandbagLunges_time","wallBalls_time",
]
station_labels = ["SkiErg","Sled Push","Sled Pull","BBJ","Row","Farmers","Lunges","Wall Balls"]

def pick_athlete_row(df: pd.DataFrame, athlete: str) -> pd.Series:
    m = df["name"].astype(str).str.contains(athlete, case=False, na=False)
    sub = df[m]
    if sub.empty:
        raise ValueError(f"Athlete '{athlete}' not found")
    return sub.iloc[0]

rot = client.get_race(season=6, location="rotterdam", gender="male", division="open")
bcn = client.get_race(season=7, location="barcelona", gender="male", division="open")

athlete = "surname, name"
user_rot = pick_athlete_row(rot, athlete)
user_bcn = pick_athlete_row(bcn, athlete)

rot_run_avg = rot[run_cols].mean()
bcn_run_avg = bcn[run_cols].mean()
rot_sta_avg = rot[station_cols].mean()
bcn_sta_avg = bcn[station_cols].mean()

runs_cmp = pd.DataFrame({
    "segment": range(1, 9),
    "Rotterdam (athlete)": [user_rot[c] for c in run_cols],
    "Barcelona (athlete)": [user_bcn[c] for c in run_cols],
}).set_index("segment")

stations_cmp = pd.DataFrame({
    "station": station_labels,
    "Rotterdam (athlete)": [user_rot.get(c, np.nan) for c in station_cols],
    "Barcelona (athlete)": [user_bcn.get(c, np.nan) for c in station_cols],
}).set_index("station")

```


## Output 
![](img.png)

![](img_1.png)

### Disclaimer

Pyrox is an independent project and is not affiliated with, endorsed or sponsored by the official Hyrox business and event organisers.
Hyrox and related marks are trademarks of their respective owners; and they are used here only for descriptive purposes.

Client-side caching is user controlled as explained above (depending on an input parameter passed down).

