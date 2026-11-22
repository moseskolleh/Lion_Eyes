# FloodWatch Freetown *(working name)*

Flash-flood warnings for Freetown, Sierra Leone, built from open data, so it
works before any sensor is installed and by a team that is not on the ground.

> This repository used to hold *Maji*, a water-vendor marketplace. That project
> was dropped in November 2026; its code remains in the git history.

## Why rain-first

Freetown's streams run off steep hills through short channels and reach the
low neighbourhoods within tens of minutes. A river gauge would add only minutes
of warning. The warning signal is the rain itself: *this much rain, over these
hills, at this tide, after this wet week, floods these streets.* That can be
learned and run from satellite, model and tide data, plus reports from
residents. Physical sensors come later and plug in as extra inputs.

Read the full idea in [docs/concept.md](docs/concept.md).

## Status

| Piece | State |
|---|---|
| Flood history (`data/events/freetown_floods.csv`) | v0: 26 sourced events, 2007-2026; thin before 2015 |
| Rainfall history | CHIRPS v3 daily (satellite + gauges), 2000-2026, rainy seasons |
| Tide | Harmonic tide fitted to 2023-2026 modelled sea level, predicted back to 2000 |
| Hindcast (do rain/tide rules flag past floods?) | v0, daily resolution: see [docs/analysis/hindcast-v0.md](docs/analysis/hindcast-v0.md) |
| Hourly model rain (ERA5, ECMWF 9 km) | Code ready; blocked today by the free API's daily quota |
| Exposure map (which streets sit low near streams) | Next |
| Live pipeline, resident reporting, warnings | Planned for April-May 2027 |

## Quick start

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'

floodwatch fetch            # sea level + CHIRPS daily rain into data/raw (cached, slow first time)
floodwatch fetch --hourly   # optional: hourly model rain from Open-Meteo (rate-limited)
floodwatch catalogue data/events/research/*.jsonl   # rebuild the flood history
floodwatch hindcast         # score warning rules; writes data/derived/
pytest
```

## Layout

```
docs/concept.md              product concept, layers, phases, who pays
docs/analysis/               analysis write-ups
data/events/                 the flood history (committed)
data/derived/                features and results (committed, small)
data/raw/                    cached downloads (not committed)
src/floodwatch/
  config.py                  area, sample points, season
  sources/chirps.py          CHIRPS v3 daily rain (byte-range reads of the peninsula)
  sources/openmeteo.py       hourly model rain and sea level
  tides.py                   tidal constituents fit + prediction (UTide)
  events.py                  flood catalogue build/load
  features.py                hourly -> daily rain features
  hindcast.py                scoring: hits, misses, false alarms, AUC
tests/
```

## Data sources

| Data | Provider | Access |
|---|---|---|
| Daily rainfall, 0.05 deg, 1981- | CHIRPS v3, Climate Hazards Center, UC Santa Barbara | Public domain |
| Hourly rainfall (ERA5, ECMWF IFS) and modelled sea level | Open-Meteo | Free tier, CC BY 4.0, attribution required |
| Flood reports | News, NDMA, IFRC/Red Cross, OCHA (URLs per event) | Cited per row |
