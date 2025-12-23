# Data model

Each race is returned as a pandas DataFrame where each row represents a single
entry (athlete or doubles pair, depending on the race).

## Common columns

Expect these columns in most races:

- `name`: athlete name as shown on the official results site.
- `gender`: `male` | `female` | `mixed`.
- `division`: `open` | `pro` (case preserved as stored).
- `total_time`: total race time, minutes (float).
- `work_time`: total station time, minutes.
- `roxzone_time`: transition time, minutes.
- `run_time`: total running time, minutes.

Station and run splits are normalized into readable names:

```commandline
skiErg_time
sledPush_time
sledPull_time
burpeeBroadJump_time
rowErg_time
farmersCarry_time
sandbagLunges_time
wallBalls_time
run1_time
run2_time
run3_time
run4_time
run5_time
run6_time
run7_time
run8_time
```

## Time normalization

All time columns are converted into minutes on load. Use them directly in
statistical workflows without re-parsing.

## Schema drift

The upstream data can evolve between seasons. Always check:

```commandline
print(df.columns)
```

If a column is missing, adapt your pipeline rather than assuming it is always present.
