# Changelog

User-visible updates to the Python package, race data and reporting service.
Data updates do not require a Python package upgrade unless stated otherwise.

## 2026-09-13 — Python client data update

- Restored 2025 Yokohama in Season 8: 2,254 results across all six supported non-Elite divisions, including available workout-summary places.
- Added 461 Season 8 results across eight races in the `elite` and `elite_doubles` divisions: Hamburg, Melbourne, Phoenix, EMEA London Olympia, APAC Championship Brisbane, Warsaw, Stockholm and Washington DC.
- Preserved published fractional-second times in Elite results.
- Verified both updates through the public Python client against official results. No package upgrade is required; use `use_cache=False` to bypass previously cached race data.

[Elite publication run](https://github.com/vmatei2/hyrox_analysis/actions/runs/34764051806) · [Yokohama fix](https://github.com/vmatei2/hyrox_analysis/commit/99e50e4)
