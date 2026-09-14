# Changelog

User-visible updates to the Python package, race data and reporting service.
Data updates do not require a Python package upgrade unless stated otherwise.

## 2026-09-14 — Python client data correction

- Corrected Season 6's 2024 Doha All Women's Race: removed unrelated results and restored 181 genuine results across open, doubles, pro doubles and relay. The separate 2024 Doha race remains unchanged.
- Corrected the split times for one doubles team in 2024 Rotterdam to match the official results; its finish time is unchanged.
- Verified fresh downloads with Python client 0.2.7. No upgrade is required; use `use_cache=False` to refresh previously cached race data.

## 2026-09-13 — Python client data update

- Restored 2025 Yokohama in Season 8: 2,254 results across all six supported non-Elite divisions, including available workout-summary places.
- Added 461 Season 8 results across eight races in the `elite` and `elite_doubles` divisions: Hamburg, Melbourne, Phoenix, EMEA London Olympia, APAC Championship Brisbane, Warsaw, Stockholm and Washington DC.
- Preserved published fractional-second times in Elite results.
- Verified both updates through the public Python client against official results. No package upgrade is required; use `use_cache=False` to bypass previously cached race data.
