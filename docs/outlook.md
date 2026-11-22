# Daily 3-day Outlook (v0)

`floodwatch outlook` produces the **Outlook** level of the warning system: a
daily call for the next three days. It is built only from data that is free and
available remotely every day:

| Input | Source | Delay |
|---|---|---|
| Rain forecast, days 1-3 | ECMWF ensemble (50 members, 0.25°), open data on AWS | Runs at 00 and 12 UTC, published within hours |
| Rain in the last 3 days | NASA IMERG near-real-time daily (Late run, Early as fallback) | ~14 h (Late), ~4 h (Early) |
| High tides | Harmonic tide model (`floodwatch.tides`) | Predicted, no delay |
| Who is exposed | Warning zones (`data/derived/zones.csv`) | Static |

## Levels

| Level | When |
|---|---|
| **HIGH** | A very wet day (>= 50 mm peninsula average) is likely (>= 30% of members), *or* a wet day (>= 30 mm) is likely on ground that already had >= 100 mm in the previous 3 days |
| **ELEVATED** | A wet day is likely, *or* the ground is already saturated |
| **LOW** | Neither |

The bulletin names the low ground at stream mouths and the shore, and the steep
hillside zones, with plain-language actions and the day's spring high tides.

## Why these rules

- **Accumulated rain matters as much as the day's rain.** In the hindcast, "that day + previous 3 days" was among the best daily measures. The two deadliest mudslides (2010, 2017) followed long wet spells, not single bursts.
- **May, June, October and November use lower thresholds.** Several floods at the edges of the season happened with modest rain. The evidence is weak: four events.
- **The Outlook gives days of notice, not hours.** The half-hourly analysis shows that heavy rain falls 1-6 hours before floods. Observed satellite rain arrives too late to warn, which is why the hour-scale Warning level needs storm tracking, lightning and residents' reports.

## Provisional thresholds and calibration

The millimetre thresholds come from the CHIRPS hindcast. The forecast model has
its own rain climate: smoother, and it usually under-states peaks. So the
thresholds are a starting point, not calibrated values.

Every forecast run used is saved in `data/archive/ecmwf/`: about 20 KB per run,
with all members at the four peninsula grid points. After one rainy season of
daily runs, the thresholds should be reset as percentiles of the model's own
forecasts. The levels should then be scored against what happened, using the
flood history and residents' reports.

## Running it

```bash
floodwatch outlook        # writes data/outlook/YYYY-MM-DD.md and .json
```

It needs a NASA Earthdata token for the observed rain. In the cloud environment
the network proxy adds it; elsewhere set `EARTHDATA_TOKEN`. To build the
calibration archive, it should run once a day, ideally from a scheduled job that
commits the new files.
