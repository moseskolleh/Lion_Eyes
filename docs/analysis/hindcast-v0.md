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
| Rain | CHIRPS v3 daily `sat` product, 0.05 deg (~5.5 km), 49 cells over the peninsula, April-November, __PERIOD__ | 5-day station-corrected satellite totals, split across days with NASA IMERG. Good for "how wet was this day", no hour-level timing. |
| Tide | Harmonic tide fitted (UTide) to Open-Meteo modelled sea level 2023-2026 and predicted back to 2000 | Held-out year error 4.7 cm against a +/-68 cm signal. Main constituent M2 = 0.90 m, so spring range ~2.4 m, neap ~1.2 m. |
| Terrain | Copernicus 30 m elevation model | Streams, upstream area, height above nearest stream (HAND). |

## Method

- **Flood window.** Each flood with a known day *E* is matched to rain on *E-1, E, E+1*, because overnight floods are dated by the evening in some reports and by the morning after in others.
- **Rules.** "Warn when rain exceeds the *p*-th percentile of rainy-season days" for *p* = 90, 95, 97.5, 99, on several rain measures. Percentiles are fixed in advance, not tuned to the floods, so the scores are not flattered by fitting.
- **Scores.** *Hits* (floods with the rule firing in the window), *false alarms per season* (runs of firing days touching no known flood), and *AUC*: the probability a flood window is wetter than a random ordinary window (0.5 = no information, 1 = perfect).
- **Lower bound.** Many real floods never made the news, so some "false alarms" are probably unreported floods. True skill is higher than measured.

## Results

__RESULTS__

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
