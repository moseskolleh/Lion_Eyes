# Half-hourly rain around past floods (NASA IMERG)

*November 2026. Reproduce with `floodwatch subdaily` (needs a NASA Earthdata token).*

The daily hindcast showed that flood days are wetter, but could not say *when*
the rain fell or how intense it was. This analysis uses NASA's IMERG V07
satellite rainfall: a rain rate every 30 minutes on a 0.1° (~11 km) grid. It
uses the 9 cells over the peninsula and the Final (gauge-corrected) run.

![Rain timelines](figures/flood_rain_timelines.png)

*Half-hourly rain rate on the wettest cell, over three days around each of the 31 dated floods (2008-2026). The yellow band is the reported flood day.*

## 1. Timing: how long before a flood does the heavy rain fall?

For the 14 floods whose reports give a time of day, I measured the rain on the wettest cell in the 12 hours before that time. Vague phrases were turned into times, with the assumption recorded in `subdaily.REPORTED_TIMES`; for example, "early hours" became 03:00.

| Flood | Reported time | Rain in previous 3 h | 6 h | 12 h | Heavy rain (>= 10 mm/h) began | Hours before report |
|---|---|---|---|---|---|---|
| 11 Sep 2008 | ~midnight | 25 mm | 39 mm | 56 mm | 17:30 | 6.5 |
| 13 Aug 2009 | ~03:00 | 13 mm | 46 mm | 64 mm | 16:00 (day before) | 11.0 |
| 9 Aug 2010 (mudslide) | ~04:00 | 2 mm | 10 mm | 38 mm | not reached | - |
| 14 Aug 2017 (Regent) | 05:45 | 14 mm | 26 mm | 50 mm | not reached | - |
| 26-27 Aug 2017 | ~midnight | 16 mm | 25 mm | 52 mm | not reached | - |
| 2 Aug 2019 | ~07:00 | 14 mm | 16 mm | 20 mm | not reached | - |
| 15 Aug 2019 | ~03:00 | 21 mm | 34 mm | 66 mm | 02:00 | 1.0 |
| 20 Jul 2024 | 12:00 | 7 mm | 24 mm | 50 mm | not reached | - |
| 23 Jul 2025 | ~18:00 | 23 mm | 24 mm | 38 mm | 16:30 | 1.5 |
| 28-29 Jul 2023 (Waterloo market) | ~01:00 | 16 mm | 23 mm | 34 mm | not reached | - |
| 4 Aug 2024 (wall collapse) | ~05:00 | 0 mm | 1 mm | 1 mm | not reached | - |
| 31 Jul 2025 (Kroo Bay) | ~06:00 | 5 mm | 11 mm | 17 mm | not reached | - |
| 23 May 2026 | ~09:00 | 7 mm | 10 mm | 11 mm | not reached | - |
| 3 Aug 2026 | ~04:00 | 79 mm | 143 mm | 149 mm | 23:30 | 4.5 |

What this shows:
- **The median flood had about 44 mm on the wettest cell in the 12 hours before it was reported.**
- **Where a clear burst exists, it starts 1 to 11 hours before the flood is reported,** most often 1-6 hours.
- **The two deadly mudslides (Owen Street 2010, Regent 2017) had no single burst.** They followed long wet spells: Regent came after three days of heavy rain. Accumulated-rain triggers fit them, not intensity triggers. The 4 August 2024 Calaba Town wall collapse (four dead) is the same kind: almost no rain in the 12 hours before, but about 117 mm across the peninsula in the three days before (CHIRPS).
- **Satellite intensity under-reads local cloudbursts badly.** On 20 July 2024 the Tower Hill rain gauge recorded 106 mm between 09:00 and 12:00. IMERG shows under 7 mm on its wettest cell in those hours and places the heavy rain at 06:00-08:00 and 12:00-15:00. A satellite cell is about 11 km wide and its rain is estimated from snapshots, so short local downpours are smeared and shifted. Two of the three floods added in round 2 show the same shift: on 28-29 July 2023 and 31 July 2025 IMERG's heaviest 3 hours end 7 and 5 hours *after* the reported flood. Any satellite threshold must be set on the satellite's own scale (percentiles), never compared directly with gauge millimetres.

## 2. Some daily "misses" were short bursts

Two floods that looked ordinary in daily rain stand out half-hourly:
- **24 Oct 2024:** CHIRPS daily put it at the 47th percentile. IMERG shows **22 mm in one hour and 40 mm in three** on the morning of the flood.
- **23 Jul 2025:** daily percentile 61. IMERG shows **29 mm in one hour and 59 mm in three**, from 18:00, matching the reported evening flood.

The **May floods stay weak even half-hourly**:

| Flood | Most in 1 h | Most in 3 h |
|---|---|---|
| 4 May 2014 | 14 mm | 23 mm |
| 9 May 2023 | 7 mm | 15 mm |
| 23 May 2026 | 14 mm | 16 mm |

Either these early-season events (a boulder fall, a wall collapse, a localised flood) need much less rain because drains and slopes are in their dry-season state, or the rain was too local for any satellite. Either way, May needs its own lower trigger, and ground reports.

## 3. Do short bursts separate floods better than daily totals?

All windows were the same three days long. I compared the 31 flood windows with two groups:
- **27 very wet days with no reported flood:** the wettest rainy-season days in CHIRPS that were at least 4 days from any reported flood. The list was drawn once and frozen (`data/derived/subdaily_controls.csv`); 3 of its original 30 days turned out to be floods, or within 4 days of one, in the second search of the flood history, so they were dropped.
- **29 ordinary days:** random rainy-season days (30 drawn; one turned out to be within 4 days of a flood found later, so it was dropped).

| Rain measure (wettest cell unless noted) | AUC vs ordinary days | AUC vs very wet no-flood days | Median: floods | very wet no-flood | ordinary |
|---|---|---|---|---|---|
| Most rain in 1 hour (IMERG) | 0.75 (0.69-0.82) | 0.43 (0.34-0.52) | 17 mm | 19 mm | 9 mm |
| Most rain in 3 hours | 0.75 (0.68-0.81) | 0.40 (0.31-0.50) | 37 mm | 37 mm | 18 mm |
| Most rain in 6 hours | 0.77 (0.70-0.83) | 0.39 (0.31-0.49) | 53 mm | 61 mm | 23 mm |
| Most rain in 24 hours | 0.78 (0.71-0.84) | 0.38 (0.29-0.48) | 81 mm | 107 mm | 31 mm |
| 24 hours, peninsula average (IMERG) | 0.81 (0.74-0.86) | 0.39 (0.30-0.49) | 62 mm | 79 mm | 20 mm |
| Day's rain, peninsula average (CHIRPS) | 0.85 (0.78-0.91) | 0.17* | 67 mm | 116 mm | 18 mm |

\* The very wet group was *chosen* by CHIRPS rain, so this AUC is low by construction. The IMERG columns were not used to choose it.

What this shows:
1. **Against ordinary days, short bursts add nothing.** All measures separate floods from ordinary days about equally well (AUC 0.75-0.85). Daily totals do as well as or better than 1-3 hour peaks, because satellite bursts are smeared (section 1). The Outlook can work on daily totals.
2. **Among the very wettest days, no rain measure tells floods from non-floods.** The 27 wettest no-flood days were as intense or more intense than the flood days on every measure; the AUC is below 0.5 with intervals mostly below it. Their rain was no more "bursty" either: the 3-hour peak was 47% of the day's total on flood days and 42% on no-flood days. Two explanations, both likely true:
   - **Many of those days probably did flood,** but no report was found. The flood history is news-based and incomplete; The second search of the flood history confirmed this for 3 of the original 30, and 16 Aug 2013, with 232 mm across the peninsula, is still the clearest candidate.
   - **Whether a wet day floods also depends on things rain cannot show:** blocked drains, exactly which hillside got the rain, the tide, and the time of day.

**Consequence for the product.** Rain can say "this is one of the wettest days of the season", and every such day should be treated as a potential flood day. It cannot say which of those days will actually flood. That last step needs information from the ground: residents' reports during the event, and a flood history completed by checking the wettest days.

## What this means for the product

0. **Daily totals are enough for the Outlook.** Sub-daily satellite intensity adds no skill (section 3), so the daily Outlook (`floodwatch outlook`) is the right design for the day-scale levels.
1. **There is little time to warn from observed rain.** The heavy rain usually falls in the 1-6 hours before a flood. IMERG's quickest version arrives about 4 hours late, so it can *confirm* and *learn*, but cannot be the real-time trigger.
2. **The real-time Warning level needs faster signals:**
   - Storm tracking from geostationary satellite imagery (every 10-15 minutes) and lightning from the MTG Lightning Imager. These see storms forming before the rain peaks.
   - Phone-network rain data, once a partner shares it.
   - Residents' reports.
3. **The Watch/Outlook level comes from forecasts and wetness.** Accumulated rain over several days is what preceded the deadly mudslides, and that is visible a day or more ahead.
