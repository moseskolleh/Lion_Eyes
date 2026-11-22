# Product concept: flash-flood warnings for Freetown from open data

*Lion Eyes, "Eyes of the mountains". Concept, November 2026; the Outlook has run twice a day since.*

## The problem

Freetown floods every rainy season (roughly May to November, peaking July to
September). Water comes off the steep peninsula hills through short streams and
drains, and reaches the low neighbourhoods (Kroo Bay, Culvert, Susan's Bay,
Kanikay, Portee/Rokupa, Juba, Kissy and others) within tens of minutes. Floods
and the landslides that come with them have killed people in most recent years,
most severely in August 2017 (Regent / Sugar Loaf, 1,141 dead or missing).

## The key insight: in Freetown, rain *is* the warning signal

The catchments are so small and steep that even river gauges would add only
minutes of warning. Any working flash-flood warning here has to say: *this much
rain, over these hills, at this tide, after this wet week, floods these streets.*
That can be built entirely from data, with no hardware, by someone not in
Freetown. Physical sensors (added later) improve accuracy without changing the
design.

## How it works: five layers

| Layer | What it answers | Source (all remote, no hardware) |
|---|---|---|
| 1. Sky | How much rain is coming / falling, and where? | Global forecast models (days), Meteosat imagery and lightning every 10-15 min (hours), satellite rainfall records (learning) |
| 2. Ground | What does that rain do to which streets? | Free elevation data, OpenStreetMap streams and drains, building footprints, population, **predicted tide**, recent wetness |
| 3. Memory | At what rain/tide/wetness has Freetown flooded before? | A sourced catalogue of past floods (news, NDMA, Red Cross, residents) paired with past rain and tide |
| 4. People | Is it actually flooding right now? | Residents in at-risk zones answer "Is water rising on your street? 1/2/3" when the system sees heavy rain; free inbound reports |
| 5. Reach | Who must hear, how, in time? | Voice calls in Krio, SMS/WhatsApp, street wardens, radio; official warnings alongside the Meteorological Agency and NDMA |

Warning levels:

| Level | Trigger | Rough lead time |
|---|---|---|
| Outlook | Forecast ensembles show a likely very wet day | 1-3 days |
| Watch | Storm systems seen building inland on satellite, lightning | 1-3 hours |
| Warning | Heavy rain over a catchment, at that tide and wetness | 0-60 minutes |
| Confirmed | Residents report rising water | now, for the streets downstream |

## Where it fits

National efforts already exist: the World Bank's Resilient Urban Sierra Leone
Project (hydromet early warning), CREWS-funded flood guidance work with the
Meteorological Agency and the National Water Resources Management Agency, and a
Green Climate Fund multi-hazard impact-based warning project led by the
Environment Protection Agency. This product does not compete with national
forecasting. It supplies what those programmes tend to lack: **street-level
impact, a calibrated flood memory, and a two-way channel with residents** for
verification and last-mile reach.

## Who could pay (hypotheses to test)

1. **Agencies and city government** (NDMA, Meteorological Agency, Freetown City
   Council): impact layer and dashboard as a service, often funded by the
   programmes above.
2. **Humanitarian anticipatory action** (Red Cross, NGOs, UN): verified
   triggers that release funds or actions *before* a flood.
3. **Parametric insurance / microinsurance** (insurers, mobile money operators):
   an objective, auditable flood trigger for households and market traders.
4. **Businesses with people or assets in flood zones** (telecoms, banks,
   logistics, schools): duty-of-care alerts.

The flood memory and the scored hindcast are the core asset for all four: they
are what makes a trigger credible.

## Phases

| When | Phase | Output |
|---|---|---|
| Nov 2026 - Mar 2027 | **0. Memory and hindcast** | Flood catalogue, rain/tide history, scored warning rules, exposure map |
| Apr - May 2027 | **1. Live pipeline** | Daily outlook + nowcast + tide, zone risk levels, partner dashboard |
| Jun - Oct 2027 | **2. Shadow season** | Warnings sent only to partners and compared with what happened; resident reporting channel live |
| 2028 | **3. Public warnings + sensors** | With an official partner; add phone-network rain data and physical gauges where the hindcast shows gaps |

## Principles

- **No money for reports.** Crowd reports are verification, never paid, so
  there is nothing to game (the failure mode of the earlier Maji design).
- **Percentile thresholds, not raw millimetres.** Every source under- or
  over-states rain in its own way; thresholds are set against each source's own
  climate.
- **Honest scores.** Every rule is published with hits, misses and false alarms
  per season, and floods not in the news make the scores a lower bound.
