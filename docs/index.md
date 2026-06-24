<div class="hero">
  <div class="hero-eyebrow">HYROX race analytics</div>
  <h1>pyrox-client</h1>
  <p>
    A Python client for HYROX race results. Pull full races as pandas DataFrames
    with splits already converted to minutes, filter by gender, division, and
    finish time at read time, and cache everything locally so reruns stay cheap.
  </p>
  <div class="hero-actions">
    <a class="hero-button" href="quickstart/">Get started</a>
    <a class="hero-button secondary" href="analytics/">Analytics</a>
  </div>
</div>

<div class="feature-grid">
  <div class="feature-card">
    <h3>Clean race pulls</h3>
    <p>Download race data straight from the CDN and cache it locally for repeatable work.</p>
  </div>
  <div class="feature-card">
    <h3>Clear filters</h3>
    <p>Server-side gender and division filters plus exact time-window slicing in minutes.</p>
  </div>
  <div class="feature-card">
    <h3>Analysis ready</h3>
    <p>Station and run splits are already renamed and normalized for modeling.</p>
  </div>
</div>

## Quickstart

```commandline
import pyrox

client = pyrox.PyroxClient()

races = client.list_races(season=7)
print(races.head())

london = client.get_race(season=7, location="london", gender="male")
print(london["total_time"].describe())
```

<div class="callout">
  Start with Quickstart, then read Filtering and Data Model to learn the columns
  and query options. The Analytics page covers common race-analysis workflows.
</div>
