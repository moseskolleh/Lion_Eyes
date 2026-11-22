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

**Website:** https://moseskolleh.github.io/Maji/ (the latest Outlook, the zone map,
the flood history and all the analysis). Built and published by GitHub Actions,
and refreshed with each Outlook, morning and evening.

## Status

| Piece | State |
|---|---|
| Flood history (`data/events/freetown_floods.csv`) | 33 sourced events, 2007-2026, from two research rounds; thin before 2014, none found for 2011-2013, 2016, 2018 |
| Rainfall history | CHIRPS v3 daily (satellite + gauges), rainy seasons; 2008-2026 analysed (2000-2007 not scored: no dated floods found there yet) |
| Tide | Harmonic tide fitted to 2023-2026 modelled sea level, predicted back to 2000 (4.7 cm error on a held-out year) |
| Hindcast (do rain/tide rules flag past floods?) | v0, daily: 2008-2026, 28 floods: flood days clearly wetter (AUC 0.82); daily rules catch ~half of floods at ~3 false alarms per season; misses cluster in May/October. See [docs/analysis/hindcast-v0.md](docs/analysis/hindcast-v0.md) |
| Half-hourly satellite rain (NASA IMERG) | Floods follow 1-6 h of heavy rain; satellite misses local cloudbursts; short bursts add no skill over daily totals, and no rain measure separates floods from the very wettest no-flood days. See [docs/analysis/subdaily-v0.md](docs/analysis/subdaily-v0.md) |
| Outlook backtest (2024-2026 ECMWF forecasts) | Replaying the Outlook: HIGH in time before 4 of 9 floods, on ~23 of ~214 rainy-season mornings; ELEVATED on over a third of mornings; today's forecast is useful, tomorrow's misses most heavy days. See [docs/analysis/outlook-backtest-v0.md](docs/analysis/outlook-backtest-v0.md) |
| Hourly model rain (ERA5, ECMWF 9 km) | Code ready; blocked by the free API's daily quota |
| Terrain and flood places | v0 map of streams and past flood places (two groups: stream mouths/shoreline and hillsides); street level next |
| Warning zones | v0: 94 catchment zones (21 in the city), each with low-ground and steep-slope measures and CHIRPS weights. See [docs/analysis/zones-v0.md](docs/analysis/zones-v0.md) |
| Exposure | ~72,600 people (23,300 buildings) on low ground near streams and the shore, ~44,200 on steep slopes; per zone from Overture buildings and Meta HRSL population (`floodwatch exposure`) |
| 3-day Outlook | v0 running on live data (ECMWF ensemble + IMERG + tide), issued twice a day by GitHub Actions: morning (00 UTC run, calendar days) and evening (12 UTC run, noon-to-noon periods covering the night). Levels read HIGH = act, ELEVATED = watch; provisional thresholds, forecasts archived for calibration. See [docs/outlook.md](docs/outlook.md) |
| Website | Static site on GitHub Pages: Outlook, interactive zone map (Leaflet), flood history, analysis pages (`floodwatch site`); styled with the sustaintheworld theme (dark/light, Newsreader / Inter / IBM Plex Mono) |
| Nowcast (hours), resident reporting, warning delivery | Planned for April-May 2027 |

## Quick start

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'              # core: Outlook, website, tests
pip install -e '.[analysis,dev]'     # plus CHIRPS, terrain, zones, figures

floodwatch fetch            # sea level + CHIRPS daily rain into data/raw (cached, slow first time)
floodwatch fetch --hourly   # optional: hourly model rain from Open-Meteo (rate-limited)
floodwatch catalogue data/events/research/*.jsonl   # rebuild the flood history
floodwatch hindcast --from 2008   # score warning rules; writes data/derived/
floodwatch terrain          # streams, flood places, map
floodwatch zones            # warning zones (after terrain)
floodwatch exposure         # buildings and people per zone (after zones)
floodwatch subdaily         # half-hourly NASA IMERG around past floods (needs Earthdata token)
floodwatch backtest         # replay the Outlook on 2024-2026 ECMWF forecasts (~20 GB first time)
floodwatch backtest --evening   # the same for the evening issue (after the morning backtest)
floodwatch outlook          # 3-day outlook (morning or evening issue, by the clock) -> data/outlook/
floodwatch site             # build the website into _site/
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
  terrain.py, exposure.py    streams, height above stream, flood places on the terrain
  zones.py                   warning zones (catchments), zone rainfall
  population.py              buildings (Overture) and people (Meta HRSL) per zone
  subdaily.py                half-hourly rain timing and intensity around floods
  outlook.py                 3-day outlook, morning and evening issues
  backtest.py                the Outlook replayed on past forecasts and scored
  sources/imerg.py           NASA IMERG half-hourly and daily (OPeNDAP)
  sources/ecmwf.py           ECMWF open-data ensemble rain (byte-range GRIB)
  site.py                    static website for GitHub Pages
site_assets/leaflet/         Leaflet 1.9.4 (BSD-2), vendored for the map page
site_assets/fonts/           Newsreader, Inter, IBM Plex Mono (SIL OFL), from the sustaintheworld site
data/outlook/                Outlook bulletins, YYYY-MM-DD(-evening) (committed by the workflow)
data/archive/ecmwf/          forecast archive for calibrating Outlook thresholds
.github/workflows/           twice-daily Outlook + website deploy; tests on pull requests
tests/
```

## Daily Outlook and website: one-time setup

The workflow `.github/workflows/outlook-and-site.yml` runs every day at 09:23 and 20:47 UTC. It:
1. issues the Outlook;
2. commits the bulletin and forecast archive to `main`;
3. rebuilds the website and publishes it.

It needs two settings in the GitHub repository:
1. **Settings > Pages > Build and deployment > Source: GitHub Actions.**
2. **Settings > Secrets and variables > Actions > New repository secret:** `EARTHDATA_TOKEN`, a NASA Earthdata Login token. Without it, the Outlook still runs but cannot see recent rain. Earthdata tokens expire after 60 days; replace the secret then.

You can also run it at any time from the **Actions** tab (*Daily outlook and website > Run workflow*).

## Data sources

| Data | Provider | Access |
|---|---|---|
| Daily rainfall, 0.05 deg, 1981- | CHIRPS v3, Climate Hazards Center, UC Santa Barbara | Public domain |
| Hourly rainfall (ERA5, ECMWF IFS) and modelled sea level | Open-Meteo | Free tier, CC BY 4.0, attribution required |
| Half-hourly and daily satellite rain, 0.1 deg | NASA IMERG V07 (GES DISC) | Free NASA Earthdata account |
| Ensemble rain forecasts, 0.25 deg | ECMWF open data (AWS copy) | Free, CC BY 4.0 |
| Elevation, 30 m | Copernicus DEM GLO-30 (AWS) | Free, attribution |
| Place names, map tiles | OpenStreetMap contributors | ODbL |
| Building footprints | Overture Maps Foundation (AWS) | ODbL / CDLA, attribution |
| Population, 30 m | Meta & CIESIN High Resolution Settlement Layer (AWS) | CC BY 4.0 |
| Flood reports | News, NDMA, IFRC/Red Cross, OCHA (URLs per event) | Cited per row |
