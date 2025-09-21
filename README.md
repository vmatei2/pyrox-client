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

# Get single race df
london_race = client.get_race(season=6, location="london")
rott_race = client.get_race(season=6, location="rotterdam")

#  Get race statistics (times are in minutes) 
 overall_stats, grouped_stats = client.get_race_stats(season=7, location="london")
 
 
 ##  Example Output of the get_race_stats function
 print(overall)
   season location    fastest    average  number_of_athletes
0       7   london  50.783333  84.827183                2978

print(grouped_stats)
   season location  gender division  number_of_athletes    fastest    average
0       7   london  female  doubles                 517  62.450000  85.671180
1       7   london  female     open                 591  58.783333  93.470446
2       7   london  female      pro                  81  65.700000  90.044239
3       7   london    male  doubles                 444  50.783333  72.543881
4       7   london    male     open                 688  55.700000  86.329409
5       7   london    male      pro                 136  58.066667  81.081127
6       7   london   mixed  doubles                 521  54.966667  82.836052

```

## Methods

- list_races(season: int | None = None) -> pd.DataFrame 
- get_race(season: int, location: str, *, sex: str | None = None, division: str | None = None) -> pd.DataFrame 
- get_season(season: int, locations: list[str] | None = None) -> pd.DataFrame 
- get_race_stats(season: int, location: str) -> tuple[pd.DataFrame, pd.DataFrame] 
  


