Python client to retrieve Hyrox race data as pandas DataFrames.

## Install

```commandline
uv pip install pyrox-client
```
or 
```commandline
pip install pyrox-client
```

## Quickstart

```commandline
from pyrox import list_races, get_season, get_race

# 1) Discover races
all_races = list_races()          # all seasons
s6_races = list_races(season=6)     # season 6 only

# 2) Multiple races from a season (concurrent)
subset_s6 = get_season(season=6, locations=["london", "hamburg"])

# 3) Single race (optional filters)
london_race = get_race(season=6, location="london")
hamburg_race = get_race(season=6, location="hamburg", division="open", gender="m")
```

All functions return a pandas DataFrame. 

