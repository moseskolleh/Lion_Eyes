# Data

## `events/freetown_floods.csv` — the flood history

One row per flood (storm day) on the Freetown peninsula (Western Area Urban and
Rural), built from public sources by `floodwatch catalogue`. Every row has at
least one source URL. Nothing is inferred: if a source does not give a number,
the cell is empty.

| Column | Meaning |
|---|---|
| `event_id` | `FT-YYYYMMDD` |
| `date` | Reported flood date (UTC = local time in Sierra Leone) |
| `date_confidence` | `exact`, `approx_day` (within a day or two), or `month_only` (date set to the 1st; excluded from scoring) |
| `time_of_day` | As reported, e.g. "overnight", "around 4:00 am" |
| `end_date` | Last day, if the source gives a multi-day event |
| `type` | `flash_flood`, `coastal_flood`, `landslide`, or `mixed` (flood plus landslide / wall collapse) |
| `locations` | Neighbourhoods as reported, separated by ` \| ` |
| `deaths`, `affected`, `houses_damaged` | As reported; where sources disagree, the summary gives the range |
| `rain_note` | Any reported rainfall amount or duration |
| `summary`, `evidence` | One-sentence summary and a short quote from a source |
| `sources` | URLs, separated by ` \| ` |
| `coastal` | True if any location is a low-lying shoreline community (tide can block drainage) |

**Known gaps (v0, November 2026):** built from web-search results only; the
full articles could not be opened in this round. Nothing was found for
2000-2006, 2011-2013, 2016 and 2018, which almost certainly reflects what is
searchable, not an absence of floods. Small floods are under-represented.
Next round: local newspaper archives, NDMA press releases, IFRC DREF reports,
ReliefWeb, and resident interviews.

## `derived/`

| File | Contents |
|---|---|
| `daily_features_chirps.csv` | One row per day: wettest-cell and peninsula-mean CHIRPS rainfall, rain in the previous 3 and 7 days, predicted highest tide and tidal range |
| `hindcast_results.json` | Scores from `floodwatch hindcast` |
| `hindcast_tables.md` | The same scores as Markdown tables, used in the write-up |
| `flood_places.csv` | Each place named in the flood history, geocoded where possible, with elevation, height above nearest stream and nearby stream size (`floodwatch terrain`) |
| `exposure_summary.json` | Flood places vs ordinary low-lying land |
| `zones.csv`, `zones.geojson` | Warning zones (one per catchment draining >= 1 km² to the sea): outlet, area, low ground near streams, steep area, flood places (`floodwatch zones`) |
| `zone_chirps_weights.csv` | Share of each zone in each CHIRPS 0.05° cell, for zone-averaged rain |
| `zone_resolution_check.json` | Zone rain vs peninsula rain on past flood days |

## `raw/` (not committed)

Cached downloads, re-created by `floodwatch fetch` and `floodwatch hindcast`.
