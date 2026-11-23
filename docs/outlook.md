# The Lion Eyes Outlook: three days ahead, morning and evening

`floodwatch outlook` produces the **Outlook** level of the warning system: a
call for the next three days, issued twice a day. It is built only from data
that is free and available remotely every day:

| Input | Source | Delay |
|---|---|---|
| Rain forecast, next 3 periods | ECMWF ensemble (50 members, 0.25°), open data on AWS | 00 UTC run published ~07:40 UTC, 12 UTC run ~19:40 UTC |
| Rain before the first period | NASA IMERG near-real-time: daily totals (Late run, Early as fallback), and half-hourly for this morning (Final, Late or Early) | ~14 h (Late), ~4 h (Early) |
| High tides | Harmonic tide model (`floodwatch.tides`) | Predicted, no delay |
| Who is exposed | Warning zones (`data/derived/zones.csv`) | Static |

## Two issues a day

| Issue | Time (Freetown = UTC) | Forecast run | Periods | Wet ground counted before the first period |
|---|---|---|---|---|
| Morning | ~08:15 | 00 UTC | Calendar days: today, tomorrow, the day after | The 3 previous days |
| Evening | ~21:00 | 12 UTC | Noon to noon: tonight (from noon today) to noon tomorrow, then the next two | The 2 previous days plus this morning |

The evening issue exists because most Freetown floods come at night or before
dawn, after the morning issue. Its first period puts a fresh, short-range
forecast on the night ahead, and the backtest shows the forecast is much better
for the next 24 hours than for the day after.

## Levels

| Level | Meaning | When |
|---|---|---|
| **HIGH** | **Act** | A very wet period (>= 50 mm peninsula average) is likely (>= 30% of members), *or* a wet period (>= 30 mm) is likely on ground that already had >= 100 mm in the 3 days before |
| **ELEVATED** | **Watch** | A wet period is likely, *or* the ground is already saturated |
| **LOW** | Normal | Neither |

At HIGH, the bulletin names the low ground at stream mouths and the shore, and
the steep hillside zones, with plain-language actions and the spring high tides.
At ELEVATED it gives a short "watch" message and points to the next issue,
because most days at that level pass without flooding. Each bulletin also says
how often each level has come up (from the backtest).

## Why these rules

- **Accumulated rain matters as much as the day's rain.** In the hindcast, "that day + previous 3 days" separates flood days from ordinary days almost as well as the day's own rain (AUC 0.77 against 0.80), and some deadly floods stand out most on it: the King Jimmy collapse of August 2013 and the flood of 18-19 September 2016. The two deadliest mudslides (2010, 2017) followed long wet spells, not single bursts.
- **May, June, October and November use lower thresholds.** In the hindcast, 9 of the 10 dated floods in these months came with less rain than the 80th percentile of ordinary rainy-season days, against 7 of the 37 floods in July to September. Ten events is still a small sample, and the size of the reduction has not been fitted.
- **The Outlook gives days of notice, not hours.** The half-hourly analysis shows that heavy rain falls 1-6 hours before floods. Observed satellite rain arrives too late to warn, which is why the hour-scale Warning level needs storm tracking, lightning and residents' reports.

## Thresholds and calibration

The millimetre thresholds come from the CHIRPS hindcast. The forecast model has
its own rain climate: smoother, and it usually under-states peaks. So the
thresholds are a starting point, not calibrated values.

Every forecast run used is saved in `data/archive/ecmwf/`: about 20 KB per run,
with all members at the four peninsula grid points. After one rainy season of
daily runs, the thresholds should be reset as percentiles of the model's own
forecasts. The levels should then be scored against what happened, using the
flood history and residents' reports.

## How well it works (backtest)

Replaying the Outlook on ECMWF's 2024-2026 forecasts (`floodwatch backtest`,
[write-up](analysis/outlook-backtest-v0.md)), counting the morning and evening
issues together:

| Level | Rainy-season days with this level in an issue (today or tomorrow) | Floods with this level in time (of 9) |
|---|---|---|
| HIGH | ~17% (~36 days a season) | 5 |
| ELEVATED or HIGH | ~41% (~87 days a season) | 7 |

With the morning issue alone, these were 11% / 4 floods and 37% / 5 floods.
The evening issue added warnings before the night-time floods, for about 9 more
alert days a season.

So **HIGH is the action level and ELEVATED is a watch level.** Today's forecast
is useful, but tomorrow's misses most heavy days. The thresholds stay as they
are until there are more floods to test changes on.

## Getting the Outlook

Each issue is published in four forms, so radio stations, community groups or
an SMS gateway can pick it up without visiting the site:

| Form | Where | For |
|---|---|---|
| Web page | The site's home page, and one page per issue in the archive | Reading |
| Short message | On the home page, at the end of each bulletin, and as `sms` in the JSON | Forwarding by SMS or WhatsApp: at most 160 plain characters |
| Feed | `feed.xml` (Atom): one entry per issue, newest first, with the short message as its summary | Feed readers, or tools that post new entries to WhatsApp, Telegram or email |
| Data | `latest.json`: the newest issue with all numbers, the short message and the bulletin link | Other systems |

Example short message, at HIGH:
`Freetown flood outlook, 02 Aug pm: Tonight HIGH, Tomorrow ELEVATED, Wed LOW. ACT: ready to move people from low ground (New Life Community); watch hillsides.`

## Running it

```bash
floodwatch outlook        # writes data/outlook/YYYY-MM-DD.md and .json
```

It needs a NASA Earthdata token for the observed rain. In the cloud environment
the network proxy adds it; elsewhere set `EARTHDATA_TOKEN`.

It runs every day at 08:13 and 20:47 UTC from GitHub Actions
(`.github/workflows/outlook-and-site.yml`); the issue (morning or evening) is
chosen by the clock. The workflow commits the bulletin and the forecast
archive, and republishes the website. See the README for the one-time
repository settings.
