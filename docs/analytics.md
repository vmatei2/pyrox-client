# Analytics

A focused set of workflows to extract signal from race data.

## 1. Segment z-scores

Normalize each station split relative to the field to see strengths and weaknesses.

```commandline
import numpy as np
import pandas as pd

race = client.get_race(season=7, location="london", gender="male")

split_cols = [
    "skiErg_time",
    "sledPush_time",
    "sledPull_time",
    "burpeeBroadJump_time",
    "rowErg_time",
    "farmersCarry_time",
    "sandbagLunges_time",
    "wallBalls_time",
]

field = race[split_cols].astype(float)

means = field.mean()
stds = field.std(ddof=0).replace(0, np.nan)

z = (field - means) / stds
race_z = pd.concat([race[["name"]], z], axis=1)
```

## 2. Rank percentiles by total time

```commandline
race = client.get_race(season=7, location="london")

race = race.sort_values("total_time")

race["percentile"] = race["total_time"].rank(pct=True)
```

## 3. Create pace buckets

```commandline
bins = [0, 55, 60, 65, 70, 999]
labels = ["<55", "55-60", "60-65", "65-70", "70+"]

race["pace_bucket"] = pd.cut(race["total_time"], bins=bins, labels=labels)
summary = race.groupby("pace_bucket")["total_time"].agg(["count", "mean"])
```

## 4. Build a station share profile

Identify which stations dominate a given athlete's time.

```commandline
athlete = client.get_athlete_in_race(
    season=7,
    location="london",
    athlete_name="surname, name",
)

split_cols = [
    "skiErg_time",
    "sledPush_time",
    "sledPull_time",
    "burpeeBroadJump_time",
    "rowErg_time",
    "farmersCarry_time",
    "sandbagLunges_time",
    "wallBalls_time",
]

row = athlete.iloc[0]
share = row[split_cols] / row[split_cols].sum()
```
