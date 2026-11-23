# Outlook backtest: would the forecasts have warned?

*November 2026. Reproduce with `floodwatch backtest`, then `floodwatch backtest --evening`. The first run downloads about 20 GB of forecasts; each run's result is then kept in `data/archive/ecmwf/`.*

The hindcast scored floods against rain that had **already fallen**. The daily
Outlook has to work from a **forecast**. This analysis replays the Outlook on
ECMWF's past ensemble forecasts (the 00 UTC run of each day), using the same
code as the live Outlook (`outlook.day_levels`). It covers May 2024, when ECMWF's
free archive moved to the 0.25° grid the Outlook uses, to early October 2026,
the end of the satellite rain record.

It looks at two kinds of morning:
- **Mornings before the 9 floods** in the history in that period.
- **120 random rainy-season mornings**, to see how often the Outlook raises an alert when nothing is reported. The list is frozen in `data/derived/outlook_backtest_sample.csv`.

One difference from the live Outlook: the wet-ground rule uses CHIRPS satellite
rain rather than IMERG, because CHIRPS covers the whole period.

## 1. Before floods

The morning Outlook is issued at about 08:15 Freetown time (08:12 UTC; it was 09:23 until late November 2026, which changes none of these results). Each cell is the
highest level the Outlook gave for the flood day or the day before it.

| Flood | Reported time | 2 days before | Day before | Same morning | **In time** |
|---|---|---|---|---|---|
| 16 Jul 2024 | not given | LOW | LOW | HIGH | LOW* |
| 20 Jul 2024 | 12:00 | ELEVATED | ELEVATED | HIGH | **HIGH** |
| 27 Jul 2024 (Moyiba landslide) | night | ELEVATED | HIGH | HIGH | **HIGH** |
| 4 Aug 2024 (Calaba Town wall collapse) | ~05:00 | HIGH | HIGH | ELEVATED | **HIGH** |
| 24 Oct 2024 | not given | LOW | LOW | LOW | LOW |
| 23 Jul 2025 | ~18:00 | HIGH | ELEVATED | ELEVATED | **ELEVATED** |
| 31 Jul 2025 (Kroo Bay) | early hours | LOW | LOW | HIGH | LOW |
| 23 May 2026 | morning | LOW | LOW | LOW | LOW |
| 3 Aug 2026 | ~04:00 | HIGH | HIGH | HIGH | **HIGH** |

**In time** is the latest Outlook issued *before* the flood:
- If the flood was reported after the morning issue, it is the same-morning Outlook.
- If it was reported before that issue, it is the day-before Outlook.
- \* If the time is not given, it is also the day-before Outlook. This is the cautious choice; 16 July 2024 would count as HIGH if that flood came after 08:15.

What this shows:
- **5 of 9 floods had ELEVATED or HIGH in time, and 4 of 9 had HIGH.**
- **The same-morning Outlook flagged 7 of 9, but often too late.** Three floods (4 Aug 2024, 31 Jul 2025, 3 Aug 2026) were reported between 04:00 and 06:00, before that morning's Outlook came out. Night and early-morning floods are the rule in Freetown: 18 of the 29 with a reported time happened then.
- **Two floods were missed at every lead: 24 Oct 2024 and 23 May 2026.** Both were short local downpours that the half-hourly analysis already showed are too small for satellites, let alone forecasts.
- **4 Aug 2024 was HIGH partly for the wrong reason.** The forecast promised heavy rain that mostly did not come (7 mm fell). The ground was already soaked, though, with 128 mm in the previous three days, and the wall collapsed.

## 2. On ordinary days

On the 120 random rainy-season mornings, this is the highest level the Outlook gave for today or tomorrow:

| Level for today or tomorrow | Share of mornings | Mornings per season (May-Nov) |
|---|---|---|
| ELEVATED or HIGH | 37% | ~78 |
| HIGH | 11% | ~23 |

For **today only**, the Outlook gave ELEVATED or HIGH on ~59 mornings a season and HIGH on ~14.
- **The forecast drives most alerts.** 36 of the 44 alert mornings came from the forecast and 8 from wet ground alone.
- **HIGH is a real signal.** It was given in time before 4 of 9 floods (44%), but on only about 1 in 9 ordinary mornings: about 4 times more often before a flood than on an ordinary day.
- **ELEVATED is too common to act on.** It was given on more than a third of rainy-season mornings, so in practice it means "a normal wet-season day".

## 3. Forecast rain against satellite rain

The forecast median (peninsula average) is compared here with CHIRPS rain on the same 120 random mornings. A "wet day" is at least 30 mm (lower in May, June, October and November).

| | Today | Tomorrow | Day after |
|---|---|---|---|
| Rank correlation, forecast vs observed | 0.72 | 0.65 | 0.52 |
| Wet days observed | 19 | 19 | 14 |
| ...flagged by the forecast (>= 30% of members) | 12 | 4 | 4 |
| Days flagged that turned out wet | 12 of 24 | 4 of 20 | 4 of 16 |
| On wet days: forecast median vs rain that fell | 27 vs 36 mm | 14 vs 47 mm | 15 vs 44 mm |

What this shows:
- **Today's forecast is useful.** It ranks days well and flags about 2 in 3 wet days. Half of its "wet" calls are right.
- **Beyond today, the forecast loses the heavy days.** Tomorrow's forecast flagged only 4 of 19 wet days. On those days it predicted about a third of the rain that fell. The model spreads storm rain thinly, so its members rarely put 30 mm or more on the peninsula a day or more ahead.

## 4. Compared with knowing the rain in advance

What if we had known in advance exactly how much rain would fall (CHIRPS) today and tomorrow?
- A "wet today or tomorrow" rule would have fired on ~66 mornings a season and before 6 of 9 floods.
- A "very wet" rule would have fired on ~27 mornings and before 2 of 9.

The Outlook's HIGH-for-today does about as well: ~14 mornings a season, flagging 5 of 9 floods that morning. It does this by combining the forecast with wet ground. Knowing the daily rain amounts would not do much better, which matches the hindcast: daily rain flags dangerous days but cannot pick which of them will flood.

## 5. Stricter settings (for discussion, not adopted)

These are recomputed from the same 146 forecast runs. They are **tuned on the same 9 floods**, so the flood columns differ by only 1-3 events and are not evidence on their own. The ordinary-day columns rest on 120 mornings and are firmer.

| Rule | ELEVATED+ (today or tomorrow), per season | HIGH, per season | Floods flagged the day before: ELEVATED+ / HIGH | Same morning: ELEVATED+ / HIGH |
|---|---|---|---|---|
| **Current**: "likely" = 30% of members; wet ground alone gives ELEVATED | ~78 | ~23 | 5 / 3 | 7 / 5 |
| Wet ground alone no longer gives ELEVATED | ~64 | ~23 | 4 / 3 | 6 / 5 |
| "Likely" = 50% of members | ~46 | ~14 | 4 / 2 | 6 / 2 |
| Both changes | ~29 | ~14 | 3 / 2 | 5 / 2 |
| "Likely" = 70%, no wet-ground-alone | ~21 | ~7 | 2 / 1 | 3 / 2 |

Raising "likely" to 50% halves the ELEVATED mornings but loses most HIGH hits, because forecast probabilities for heavy rain are rarely high. The current HIGH rule is worth keeping. The question is what ELEVATED should mean.

## 6. Adding an evening issue

Because so many floods come at night, the Outlook now also goes out in the
evening, at about 21:00. That issue uses ECMWF's 12 UTC run, and its periods
run noon to noon, so the first one covers the night ahead with a fresh
forecast. It was replayed the same way: on the evenings before and of each
flood, and on the same 120 random days (`floodwatch backtest --evening`).

| Flood | Reported time | Morning issue only, in time | With evening issue: latest issue before the flood | Higher of the last two issues |
|---|---|---|---|---|
| 16 Jul 2024 | not given | LOW | HIGH (evening before) | HIGH |
| 20 Jul 2024 | 12:00 | HIGH | HIGH (same morning) | HIGH |
| 27 Jul 2024 | night | HIGH | ELEVATED (evening before) | HIGH |
| 4 Aug 2024 | ~05:00 | HIGH | ELEVATED (evening before) | HIGH |
| 24 Oct 2024 | not given | LOW | LOW | LOW |
| 23 Jul 2025 | ~18:00 | ELEVATED | ELEVATED (same morning) | ELEVATED |
| 31 Jul 2025 (Kroo Bay) | early hours | LOW | **ELEVATED** (evening before) | ELEVATED |
| 23 May 2026 | morning | LOW | LOW | LOW |
| 3 Aug 2026 | ~04:00 | HIGH | HIGH (evening before) | HIGH |

| | Morning issue only | Morning and evening issues |
|---|---|---|
| Floods with ELEVATED or HIGH in time (of 9) | 5 | **7** |
| Floods with HIGH in time, higher of the last two issues (of 9) | 4 | **5** |
| Rainy-season days with ELEVATED or HIGH in an issue | ~78 a season (37%) | ~87 a season (41%) |
| Rainy-season days with HIGH in an issue | ~23 a season (11%) | ~36 a season (17%) |

What this shows:
- **More floods get a warning in time.** The gain is in the night: before the pre-dawn Kroo Bay flood of 31 July 2025, the morning issue the day before said LOW, but the evening issue said ELEVATED. Before 16 July 2024, the evening issue went to HIGH.
- **It costs more alert days.** Counting both issues, HIGH comes up on about 36 days a season instead of 23. HIGH is still about 3 times more frequent before floods (5 of 9) than on ordinary days (17%). That is a little less sharp than the morning issue alone, which was about 4 times.
- **The evening issue sometimes lowers the level.** Before 27 July and 4 August 2024, it gave ELEVATED where that morning's issue gave HIGH. Its fresher forecast saw less rain coming, and on 4 August little did fall: the wall collapsed on ground already soaked by 128 mm. So read the two issues together: **the higher of the day's two levels** caught 5 of 9 floods at HIGH.
- **An idea to test, not adopted:** keep a morning HIGH through the night when the ground is saturated. It would have helped on 4 August 2024, but it was suggested by these same few floods.

## What this means for the product

1. **HIGH is the action level.** In time before 4 of 9 floods, given on ~23 mornings a season.
2. **ELEVATED should be presented as "watch", not "act".** Alternatively it could be made stricter. The bulletin should say how often each level occurs, so readers know HIGH is rare and ELEVATED is common.
3. **Use the forecast mostly for today.** Tomorrow's and the day after's levels rest on wet ground and the occasional strong forecast signal, not on reliable rain amounts.
4. **Keep the evening Outlook (now running).** Most floods come at night or before dawn. The evening issue put 2 more of the 9 floods "in time" (section 6), for about 9 more alert days a season. Read the morning and evening issues together.
5. **Short local downpours need other signals.** These are floods like 24 Oct 2024 and 23 May 2026. Only storm tracking from geostationary satellites (EUMETSAT) or residents' reports will catch them.

## Limitations

- **Only 9 floods.** Every flood count has wide uncertainty. As a continuous score, the day-before forecast probability separates floods from ordinary mornings only weakly (AUC 0.64, 90% interval 0.49-0.78).
- **Wet ground is measured differently.** It uses CHIRPS here, not the IMERG the live Outlook uses.
- **Some "ordinary" mornings may have had unreported floods,** so part of the alert rate may be real events.
- **Flood times are rough.** Two floods have no reported time, and others rest on phrases like "early hours".
- Results for each flood and morning are in `data/derived/outlook_backtest.json` and `outlook_backtest_days.csv`.
