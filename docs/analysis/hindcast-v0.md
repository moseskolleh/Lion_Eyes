# Hindcast v0: does open data "see" Freetown's past floods?

*November 2026. First pass, daily resolution. Reproduce with `floodwatch fetch && floodwatch hindcast && floodwatch terrain`.*

## Questions

1. Were the days Freetown flooded unusually wet in freely available satellite rainfall?
2. Does the tide matter, especially for shoreline communities?
3. Where do floods happen relative to the terrain?
4. What does the flood history say about *how* warnings must be delivered?

## Data

| What | Source | Notes |
|---|---|---|
| Floods | `data/events/freetown_floods.csv`: 26 events, 2007-2026, 21 with a known day | Built from news, NDMA, IFRC/Red Cross and OCHA via web search. Thin before 2015; none found for 2016 and 2018. Each row cites its sources. |
| Rain | CHIRPS v3 daily `sat` product, 0.05 deg (~5.5 km), 49 cells over the peninsula, April-November, 2013-2026 (14 rainy seasons) | 5-day station-corrected satellite totals, split across days with NASA IMERG. Good for "how wet was this day", no hour-level timing. |
| Tide | Harmonic tide fitted (UTide) to Open-Meteo modelled sea level 2023-2026 and predicted back to 2000 | Held-out year error 4.7 cm against a +/-68 cm signal. Main constituent M2 = 0.90 m, so spring range ~2.4 m, neap ~1.2 m. |
| Terrain | Copernicus 30 m elevation model | Streams, upstream area, height above nearest stream (HAND). |

## Method

- **Flood window.** Each flood with a known day *E* is matched to rain on *E-1, E, E+1*, because overnight floods are dated by the evening in some reports and by the morning after in others.
- **Rules.** "Warn when rain exceeds the *p*-th percentile of rainy-season days" for *p* = 90, 95, 97.5, 99, on several rain measures. Percentiles are fixed in advance, not tuned to the floods, so the scores are not flattered by fitting.
- **Scores.** *Hits* (floods with the rule firing in the window), *false alarms per season* (runs of firing days touching no known flood), and *AUC*: the probability a flood window is wetter than a random ordinary window (0.5 = no information, 1 = perfect).
- **Lower bound.** Many real floods never made the news, so some "false alarms" are probably unreported floods. True skill is higher than measured.

## Results

### 1. Free satellite rainfall does "see" most of Freetown's floods

Over 14 rainy seasons (2013-2026) and the 18 floods with a known day:

- **Flood days are much wetter than ordinary rainy-season days.** On the wettest cell, the median flood window had **94 mm**, against **37 mm** on ordinary days.
- **Rain separates flood days from ordinary days clearly, though not perfectly.** For peninsula-average rain on the day, the AUC is **0.79** (90% interval 0.69-0.88). 0.5 would mean no information.
- **Most big floods stand out.** On the wettest cell, 11 of the 18 flood windows were wetter than 85% of ordinary windows, and 8 were wetter than 95%. The deadliest stand out most: Regent, August 2017, was at the 96th percentile; 28 August 2022 at the 100th; 20 July 2024 at the 100th.

### 2. The misses have a pattern: the edges of the season

The weakest cases are these:
- 4 May 2014: 73rd percentile.
- 9 May 2023: 32nd percentile.
- 23 May 2026: 9th percentile.
- 24 October 2024: 47th percentile.
- 23 July 2025: an evening storm, 60th percentile.
- 26 July 2021: the date itself is uncertain.

Four of the six fall in May or October, the transition months. Two explanations fit, and both matter for the product:
- **The storms are short.** Early- and late-season storms are brief, intense convective downpours. Daily data spreads them across a whole day, and CHIRPS also spreads each 5-day total across days.
- **Less rain is needed to flood.** At the start of the season, drains are still blocked with dry-season rubbish, and slopes and walls have been dry and loose.

So transition months need their own, lower trigger, judged on **hourly** rain.

### 3. Rules from daily rain alone: useful, but noisy

| Rule (fires on...) | Floods caught | False alarms per season |
|---|---|---|
| Peninsula-average rain in the top 2.5% of days (>= 77 mm) | 9 of 18 | 4.4 |
| That day + previous 3 days in the top 5% (>= 162 mm) | 9 of 18 | 3.2 |
| Previous 3 days in the top 2.5% (>= 157 mm) | 6 of 18 | 2.0 |
| Wettest cell in the top 10% (>= 64 mm) | 12 of 18 | 15.4 |

A daily rule catching half the floods with about 3 false alarms per 7-month season is a reasonable **Outlook/Watch** level. It is not good enough for a street-level Warning on its own. That level needs hourly rain and resident confirmation (layer 4).

**Some of these "false alarms" are probably real floods that were never reported.** The wettest day in the whole record with no reported flood is **16 August 2013**: 232 mm across the peninsula and 284 mm on the wettest cell. It is very likely a flood the news search missed. The full list of such dates is below. Searching them is the fastest way to complete the flood history, and every flood found turns a false alarm into a hit.

### 4. Tide: not yet detectable

- **Shoreline floods:** across the 8 floods in shoreline communities, tides were slightly higher than on ordinary days (AUC 0.60, interval 0.49-0.70). That is not distinguishable from chance with this few events.
- **Inland floods:** no tide effect, as expected (AUC 0.44).

Keep tide as an input for shoreline zones and re-test with more events and hourly timing. With daily data, a high tide anywhere in the 3-day window counts, which blurs the effect.

### Full tables

(Generated by `floodwatch hindcast --from 2013`; also in `data/derived/hindcast_tables.md`.)

Source: CHIRPS v3 daily (satellite + gauges, IMERG-timed). Period 2013-04-01 to 2026-10-08, 14 rainy seasons, 18 dated floods.

**How well each rain measure separates flood days from ordinary rainy-season days**

| Rain measure | AUC | 90% interval | Median on flood days | Median on other days |
|---|---|---|---|---|
| Wettest cell, that day | 0.77 | 0.66-0.87 | 94 mm | 37 mm |
| Peninsula average, that day | 0.79 | 0.69-0.88 | 72 mm | 22 mm |
| Peninsula average, previous 3 days | 0.76 | 0.65-0.85 | 106 mm | 46 mm |
| Peninsula average, previous 7 days | 0.71 | 0.59-0.82 | 201 mm | 95 mm |
| Peninsula average, that day + previous 3 days | 0.76 | 0.65-0.86 | 159 mm | 59 mm |

**Each flood: rain as a percentile of ordinary rainy-season days**

| Flood date | Wettest cell | Percentile | Peninsula avg + previous 3 days | Percentile |
|---|---|---|---|---|
| 2014-05-04 | 59 mm | 73 | 40 mm | 33 |
| 2015-09-16 | 80 mm | 86 | 121 mm | 84 |
| 2017-08-14 | 119 mm | 96 | 185 mm | 95 |
| 2017-08-26 | 83 mm | 86 | 168 mm | 94 |
| 2019-08-02 | 114 mm | 95 | 198 mm | 96 |
| 2019-08-15 | 189 mm | 100 | 173 mm | 94 |
| 2020-07-14 | 104 mm | 93 | 170 mm | 94 |
| 2020-08-25 | 144 mm | 98 | 194 mm | 96 |
| 2021-07-26 | 29 mm | 39 | 91 mm | 72 |
| 2022-08-17 | 179 mm | 100 | 244 mm | 98 |
| 2022-08-28 | 207 mm | 100 | 247 mm | 98 |
| 2023-05-09 | 24 mm | 32 | 34 mm | 27 |
| 2024-07-16 | 128 mm | 97 | 150 mm | 91 |
| 2024-07-20 | 181 mm | 100 | 308 mm | 100 |
| 2024-10-24 | 34 mm | 47 | 66 mm | 55 |
| 2025-07-23 | 46 mm | 60 | 60 mm | 51 |
| 2026-05-23 | 8 mm | 9 | 11 mm | 8 |
| 2026-08-03 | 65 mm | 78 | 103 mm | 78 |

**Wettest days with no reported flood (first dates to search for missing floods)**

| Date | Peninsula average | Wettest cell | Previous 3 days |
|---|---|---|---|
| 2013-08-16 | 232 mm | 284 mm | 36 mm |
| 2024-07-30 | 161 mm | 220 mm | 130 mm |
| 2024-08-14 | 150 mm | 171 mm | 100 mm |
| 2017-07-08 | 135 mm | 173 mm | 47 mm |
| 2023-07-29 | 134 mm | 202 mm | 121 mm |
| 2015-05-18 | 134 mm | 160 mm | 12 mm |
| 2013-08-30 | 126 mm | 178 mm | 83 mm |
| 2023-07-14 | 123 mm | 160 mm | 52 mm |
| 2025-08-07 | 122 mm | 146 mm | 75 mm |

The full rule table (every measure at every threshold) is in `data/derived/hindcast_tables.md`.

### What this means for the product

1. **The open-data approach works for the Outlook and Watch levels.** Big floods are visible in free satellite rainfall without any sensor.
2. **Street-level Warnings need hourly rain and people.** Daily rain alone is too noisy. Hourly satellite rain (IMERG) and resident confirmation are the next two building blocks, not optional extras.
3. **Use season-aware triggers.** May and October floods happen at lower rain totals.
4. **Use separate triggers for the two kinds of flood place.** Stream mouths and shoreline need rain intensity plus tide. Hillsides need accumulated rain, for landslides and wall collapses (see the terrain section).
5. **Completing the flood memory is high-value, cheap work.** The unreported-wet-days list points exactly where to look.

## When floods happen: what it means for delivering warnings

- **Season:** 12 of the 26 floods were in August; July and September add 10 more.
- **Time of day:** of the 11 floods with a reported time, **8 hit at night or in the early hours** (e.g. 4 am Owen Street mudslide 2010, 05:45 Regent 2017, overnight 1-2 Aug 2019, overnight 2-3 Aug 2026).
- **Implication:** SMS alone will not wake people. Warnings need **voice calls** (a ringing phone) and **street wardens** with loudspeakers or whistles, as the concept proposes.

## Where floods happen: terrain

![Streams and flood places](figures/streams_and_flood_places.png)

Of 75 place names in the flood history, 21 could be placed as neighbourhoods on OpenStreetMap; the rest are streets, landmarks or descriptions ("low-lying areas"). They fall into two distinct groups:

| Group | Places | Terrain | Mechanism |
|---|---|---|---|
| **Stream mouths and shoreline** | Kroo Bay (7 events), Susan's Bay, Kanikay, Cline Town, Portor, Lumley, Kaningo, Cockerill Bay | Under ~3 m above the nearest stream, on streams draining 1-13 km² | Streams overflow where they meet the sea; tide can block outflow |
| **Hillsides and upper valleys** | Regent, Looking Town, Sugar Loaf, Bathurst, Tengbeh Town, Wilberforce | 90-360 m elevation, steep | Runoff, landslides, wall collapses |

The two groups need different triggers: rain *intensity* plus tide for the first, *accumulated* rain over several days (soil saturation) for the second.

Limits: geocoded points are neighbourhood centres, not the flooded streets, and the elevation model includes roofs and trees and cannot see culverts. Street-level flood points from residents or partners would sharpen this a lot.

## Limitations

1. **Small, news-biased flood list.** 21 dated floods; small floods and quiet years are missing. Every score has wide uncertainty.
2. **Daily rain only.** CHIRPS cannot tell a 3-hour cloudburst from a steady all-day rain, which is exactly what matters for flash floods. It also smooths a 5-day total across days.
3. **Coarse rain grid vs. tiny catchments.** ~5.5 km cells, and the daily timing comes from ~10 km IMERG.
4. **Modelled tide only.** Fitted to a model's sea level, not a tide gauge; surge is ignored.

## Next steps

1. **Hourly rain** for the same floods: NASA IMERG half-hourly (needs a free NASA Earthdata account) and ECMWF 9 km via Open-Meteo once its quota allows. This answers the lead-time question.
2. **Grow the flood list**: local newspaper archives, NDMA releases, IFRC DREF reports, Freetown City Council, and interviews; add dated *non-flood* heavy-rain days.
3. **Street-level exposure**: building footprints plus resident-reported flood points; define warning zones per catchment.
4. **Separate triggers** for the two flood groups above, then re-score.
