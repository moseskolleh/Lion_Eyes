"""Command line entry point: ``floodwatch <command>``.

Commands
  fetch      download rainfall and sea level into data/raw (cached)
  catalogue  merge research files into data/events/freetown_floods.csv
  hindcast   score warning rules against the flood history
  terrain    trace streams, place past floods on the terrain, draw the map
  zones      split the peninsula into warning zones (run after terrain)
  exposure   count buildings and people per zone and hazard class (after zones)
  subdaily   half-hourly satellite rain around past floods (after hindcast)
  backtest   replay the Outlook on past ECMWF forecasts (2024-2026)
  outlook    today's 3-day flood outlook (live data; writes data/outlook/)
  site       build the static website (GitHub Pages) into _site/
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from floodwatch import config


def _fetch(args: argparse.Namespace) -> None:
    from floodwatch.sources import chirps, openmeteo

    end = date.today() - timedelta(days=2)
    out = config.RAW_DIR / "tables"
    out.mkdir(parents=True, exist_ok=True)

    sea = openmeteo.fetch_sea_level(config.SEA_POINT, 2023, end)
    sea.to_csv(out / "sea_level.csv.gz", index=False)
    print(f"sea level: {sea['sea_level_m'].notna().sum()} hours")

    cells = chirps.fetch(config.FIRST_YEAR, end.year)
    print(f"CHIRPS: {cells['date'].nunique()} days")

    if args.hourly:
        # Open-Meteo's free tier is rate-limited per address; this can take a
        # while or fail until the daily quota resets.
        by_key = {p.key: p for p in config.POINTS}
        era5 = openmeteo.fetch_rain(
            "era5", [by_key["central"], by_key["waterloo"]], config.FIRST_YEAR, end
        )
        era5.to_csv(out / "rain_era5.csv.gz", index=False)
        ifs = openmeteo.fetch_rain("ecmwf_ifs", config.POINTS, config.FIRST_YEAR, end)
        ifs.to_csv(out / "rain_ifs.csv.gz", index=False)
        print(f"hourly: era5 {len(era5)} rows, ifs {len(ifs)} rows")


def _catalogue(args: argparse.Namespace) -> None:
    from floodwatch import events

    df = events.build_catalogue(args.inputs)
    print(f"{len(df)} events written to {events.CATALOGUE_CSV}")


def _hindcast(args: argparse.Namespace) -> None:
    from floodwatch import hindcast

    hindcast.run(args.first_year)


def _terrain(args: argparse.Namespace) -> None:
    from floodwatch import exposure

    exposure.run()


def _zones(args: argparse.Namespace) -> None:
    from floodwatch import zones

    zones.build()


def _subdaily(args: argparse.Namespace) -> None:
    from floodwatch import subdaily

    subdaily.run()


def _outlook(args: argparse.Namespace) -> None:
    from floodwatch import outlook

    outlook.build()


def _site(args: argparse.Namespace) -> None:
    from floodwatch import site

    site.build()


def _exposure(args: argparse.Namespace) -> None:
    from floodwatch import population

    population.run()


def _backtest(args: argparse.Namespace) -> None:
    from floodwatch import backtest

    if args.evening:
        backtest.run_evening()
    else:
        backtest.run()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="floodwatch")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch", help="download rainfall and sea level")
    fetch.add_argument("--hourly", action="store_true", help="also fetch hourly model rain (Open-Meteo)")
    fetch.set_defaults(func=_fetch)
    cat = sub.add_parser("catalogue", help="merge flood research files")
    cat.add_argument("inputs", nargs="+", help="JSONL files from research")
    cat.set_defaults(func=_catalogue)
    hc = sub.add_parser("hindcast", help="score warning rules")
    hc.add_argument("--from", dest="first_year", type=int, default=config.FIRST_YEAR,
                    help="first rainy season to include (default %(default)s)")
    hc.set_defaults(func=_hindcast)
    sub.add_parser("terrain", help="streams, flood places and exposure map").set_defaults(func=_terrain)
    sub.add_parser("zones", help="warning zones (one per catchment) and their maps").set_defaults(func=_zones)
    sub.add_parser("exposure", help="buildings and people per zone (after zones)").set_defaults(func=_exposure)
    sub.add_parser("subdaily", help="half-hourly IMERG rain around past floods (needs Earthdata token)").set_defaults(func=_subdaily)
    bt = sub.add_parser("backtest", help="replay the Outlook on past ECMWF forecasts and score it")
    bt.add_argument("--evening", action="store_true", help="evening issues before each flood (after the morning run)")
    bt.set_defaults(func=_backtest)
    sub.add_parser("outlook", help="today's 3-day flood outlook (ECMWF ensemble + IMERG + tide)").set_defaults(func=_outlook)
    sub.add_parser("site", help="build the static website into _site/").set_defaults(func=_site)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
