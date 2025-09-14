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
import pyrox

# Create client
client = pyrox.PyroxClient()

# Discover available races
all_races = client.list_races()          
s6_races = client.list_races(season=6)   

# Get multiple races from a season
subset_s6 = client.get_season(season=6, locations=["london", "hamburg"])

# Get single races
london_race = client.get_race(season=6, location="london")
rott_race = client.get_race(season=6, location="rotterdam")
```

All functions return a pandas DataFrame. 


