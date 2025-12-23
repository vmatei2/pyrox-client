# Reproducible research

This guide documents the workflow for the notebook
`example_notebooks/impact_of_race_locations.ipynb`. The goal is to make results
repeatable, auditable, and easy to refresh.

## What the notebook does

- Pulls Season 7 Open Singles data.
- Cleans and filters timing fields.
- Compares event distributions for total/work time by gender.
- Fits a regression with event-level interaction effects.
- Produces plots to visualize event differences.

## Dependencies

The notebook relies on:

- `pyrox-client`
- `pandas`, `numpy`
- `matplotlib`, `seaborn`
- `statsmodels`

If you are using uv (recommended):

```commandline
uv pip install -e .
```

If you do not already have Jupyter installed:

```commandline
uv pip install jupyter
```

## Run the notebook

From the repo root:

```commandline
uv run jupyter notebook example_notebooks/impact_of_race_locations.ipynb
```

Alternative:

```commandline
uv run jupyter lab
```

Then open the notebook and run cells top to bottom.

## Data determinism

The notebook pulls from the live CDN. To keep results stable across runs:

- Avoid `force_refresh=True` unless you intend to refresh the dataset.
- Keep cached data between runs. Default cache location is `~/.cache/pyrox`.

If you need a clean refresh, clear the cache before running:

```commandline
python - <<'PY'
import pyrox
client = pyrox.PyroxClient()
client.clear_cache()
PY
```

## Inputs and outputs

Inputs:
- Season 7 race data (`get_season(season=7, division="open")`).
- Event list in `events_to_analyse`.

Outputs:
- Plots in the `event_dists/` directory (created automatically).
- Regression summary in the notebook output.

## Repro tips

- Keep a copy of the `events_to_analyse` list in the notebook output so the exact
  event set is recorded.
- If you publish results, consider exporting the dataset to a dated parquet file
  to preserve the snapshot used for modeling.
