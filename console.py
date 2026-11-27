#!/usr/bin/env python3
"""SolarTracker console: print the sun's azimuth and elevation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from solartracker import sun_position, sunrise_sunset  # noqa: E402


def _load_site_loader():
    path = ROOT / "site.py"
    spec = spec_from_file_location("_solartracker_site_loader", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = module_from_spec(spec)
    sys.modules["_solartracker_site_loader"] = module
    spec.loader.exec_module(module)
    return module


def _parse_time(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Time must be ISO 8601, for example 2026-11-26T18:00:00-06:00"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _local_zone():
    try:
        return datetime.now().astimezone().tzinfo or timezone.utc
    except Exception:
        return timezone.utc


def _format_local(when: datetime, zone) -> str:
    local = when.astimezone(zone)
    return local.strftime("%Y-%m-%d %H:%M:%S %Z")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Print the sun's azimuth (eastward from true north) and "
            "elevation at the configured observer site."
        )
    )
    parser.add_argument(
        "--time",
        type=_parse_time,
        default=None,
        help="ISO 8601 instant (default: now). Naive values are treated as UTC.",
    )
    parser.add_argument(
        "--no-refract",
        action="store_true",
        help="Report geometric elevation, without atmospheric refraction.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write machine-readable JSON instead of text.",
    )
    parser.add_argument(
        "--timezone",
        default=None,
        help="IANA timezone for display (default: the host local zone).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    site_mod = _load_site_loader()
    site = site_mod.load_site(ROOT)
    when = args.time
    pos = sun_position(
        site.latitude_deg,
        site.longitude_deg,
        site.elevation_m,
        when,
        refraction=not args.no_refract,
    )

    if args.timezone:
        try:
            zone = ZoneInfo(args.timezone)
        except ZoneInfoNotFoundError:
            print(f"Unknown timezone: {args.timezone}", file=sys.stderr)
            return 2
    else:
        zone = _local_zone()

    rise, sett = sunrise_sunset(
        site.latitude_deg,
        site.longitude_deg,
        site.elevation_m,
        on_date=pos.time_utc.astimezone(zone),
    )

    payload = {
        "site": {
            "name": site.name,
            "latitude_deg": site.latitude_deg,
            "longitude_deg": site.longitude_deg,
            "elevation_m": site.elevation_m,
        },
        "time_utc": pos.time_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "time_local": _format_local(pos.time_utc, zone),
        "azimuth_deg": round(pos.azimuth_deg, 4),
        "elevation_deg": round(pos.elevation_deg, 4),
        "refraction": pos.refraction,
        "sunrise_utc": rise.strftime("%Y-%m-%dT%H:%M:%SZ") if rise else None,
        "sunset_utc": sett.strftime("%Y-%m-%dT%H:%M:%SZ") if sett else None,
        "sunrise_local": _format_local(rise, zone) if rise else None,
        "sunset_local": _format_local(sett, zone) if sett else None,
    }

    if args.json:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    print("SolarTracker")
    print(f"Site:      {site.description()}")
    print(f"Time:      {payload['time_local']} ({payload['time_utc']})")
    print(f"Azimuth:   {pos.azimuth_deg:8.4f}°  (eastward from true north)")
    print(f"Elevation: {pos.elevation_deg:8.4f}°  {'(with refraction)' if pos.refraction else '(geometric, no refraction)'}")
    if rise:
        print(f"Sunrise:   {payload['sunrise_local']}")
    else:
        print("Sunrise:   (none on this date)")
    if sett:
        print(f"Sunset:    {payload['sunset_local']}")
    else:
        print("Sunset:    (none on this date)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
