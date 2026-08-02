# Analytics recipes

These examples start with a filtered `pandas.DataFrame` returned by
`PyroxClient`. Keep gender and division filters explicit; a pooled comparison
can put athletes doing different work into the same benchmark.

## Compare station splits with z-scores

This calculation measures each station against the mean and standard deviation
for one race cohort:

```python
import numpy as np
import pandas as pd

race = client.get_race(
    season=7,
    location="london",
    gender="male",
    division="open",
)

station_cols = [
    "skiErg_time",
    "sledPush_time",
    "sledPull_time",
    "burpeeBroadJump_time",
    "rowErg_time",
    "farmersCarry_time",
    "sandbagLunges_time",
    "wallBalls_time",
]

field = race[station_cols].astype(float)
means = field.mean()
stds = field.std(ddof=0).replace(0, np.nan)
z_scores = (field - means) / stds

race_z = pd.concat([race[["name"]], z_scores], axis=1)
```

For split times, a negative z-score means faster than the cohort mean. Missing
splits remain `NaN`; a station with no variation also produces `NaN` because a
z-score would have no useful denominator.

## Express finish rank as a percentile

Lower finish times are better, so rank in descending order when `1.0` should
mean faster than the whole cohort:

```python
race = race.sort_values("total_time")
race["finish_percentile"] = race["total_time"].rank(
    method="average",
    ascending=False,
    pct=True,
)
```

Tied times receive the average rank. Drop missing `total_time` values before
comparing counts if incomplete results are present.

## Group finish times into bands

```python
bins = [0, 55, 60, 65, 70, float("inf")]
labels = ["under 55", "55–60", "60–65", "65–70", "70+"]

race["finish_band"] = pd.cut(
    race["total_time"],
    bins=bins,
    labels=labels,
    right=False,
)

summary = (
    race.groupby("finish_band", observed=False)["total_time"]
    .agg(["count", "median"])
    .reset_index()
)
```

`right=False` puts an exact 60-minute result in the `60–65` band. Change the
edge rule if your published analysis uses a different convention, and write
that convention beside the chart.

## Find an athlete's largest station shares

This reports how much of an athlete's station time each workout consumed. It
doesn't include running or roxzone time.

```python
athlete = client.get_athlete_in_race(
    season=7,
    location="london",
    athlete_name="surname, name",
).iloc[0]

station_times = athlete[station_cols].astype(float)
station_share = (station_times / station_times.sum()).sort_values(ascending=False)
print(station_share.head())
```

A large share can mean a slow station, but it can also reflect the normal cost
of that workout. Compare the shares with the race cohort before calling one a
personal weakness.
