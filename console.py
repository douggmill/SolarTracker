#!/usr/bin/env python3
"""SolarTracker console: live sun position, or a one-shot report."""

from __future__ import annotations

import argparse
import json
import select
import sys
import termios
import time
import tty
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from solartracker import (  # noqa: E402
    solar_noon,
    sun_position,
    sun_track_table,
    sunrise_sunset,
    tracker_command,
)
from solartracker.ephemeris import load_ephemeris, timescale  # noqa: E402


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


def _format_clock(when: datetime, zone) -> str:
    return when.astimezone(zone).strftime("%H:%M:%S %Z")


def _resolve_zone(name: str | None):
    if not name:
        return _local_zone()
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Interactive SolarTracker console: live sun azimuth and elevation, "
            "tracker-frame pointing, and night-stow status. Use --once, --time, "
            "or --json for a one-shot report."
        )
    )
    parser.add_argument(
        "--time",
        type=_parse_time,
        default=None,
        help="ISO 8601 instant for a one-shot report. Naive values are treated as UTC.",
    )
    parser.add_argument(
        "--no-refract",
        action="store_true",
        help="Report geometric elevation, without atmospheric refraction.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write a one-shot machine-readable JSON report.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Print a single report and exit instead of opening the live view.",
    )
    parser.add_argument(
        "--live-seconds",
        type=float,
        default=None,
        metavar="N",
        help="Run the live view for N seconds, then exit (for tests and demos).",
    )
    parser.add_argument(
        "--timezone",
        default=None,
        help="IANA timezone for display (default: the host local zone).",
    )
    return parser


def _payload(site, pos, zone, rise, noon, sett) -> dict:
    cmd = tracker_command(pos.azimuth_deg, pos.elevation_deg)
    return {
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
        "tracker_azimuth_deg": round(cmd.azimuth_deg, 4),
        "tracker_elevation_deg": round(cmd.elevation_deg, 4),
        "stow_status": cmd.status,
        "stow_reason": cmd.reason,
        "sunrise_utc": rise.strftime("%Y-%m-%dT%H:%M:%SZ") if rise else None,
        "solar_noon_utc": noon.strftime("%Y-%m-%dT%H:%M:%SZ") if noon else None,
        "sunset_utc": sett.strftime("%Y-%m-%dT%H:%M:%SZ") if sett else None,
        "sunrise_local": _format_local(rise, zone) if rise else None,
        "solar_noon_local": _format_local(noon, zone) if noon else None,
        "sunset_local": _format_local(sett, zone) if sett else None,
    }


def _print_report(site, pos, zone, rise, noon, sett) -> None:
    cmd = tracker_command(pos.azimuth_deg, pos.elevation_deg)
    refract = (
        "(with refraction)" if pos.refraction else "(geometric, no refraction)"
    )
    print("SolarTracker")
    print(f"Site:      {site.description()}")
    print(f"Time:      {_format_local(pos.time_utc, zone)}")
    print(f"Azimuth:   {pos.azimuth_deg:8.4f}°  (eastward from true north)")
    print(f"Elevation: {pos.elevation_deg:8.4f}°  {refract}")
    print(
        f"Tracker:   az {cmd.azimuth_deg:8.4f}°   el {cmd.elevation_deg:8.4f}°"
    )
    print(f"Status:    {cmd.status}  ({cmd.reason})")
    print(f"Sunrise:   {_format_local(rise, zone) if rise else '(none on this date)'}")
    print(f"Noon:      {_format_local(noon, zone) if noon else '(none on this date)'}")
    print(f"Sunset:    {_format_local(sett, zone) if sett else '(none on this date)'}")


def _day_events(site, on_date, *, refraction, eph, ts):
    kwargs = dict(
        latitude_deg=site.latitude_deg,
        longitude_deg=site.longitude_deg,
        elevation_m=site.elevation_m,
        on_date=on_date,
        eph=eph,
        ts=ts,
    )
    rise, sett = sunrise_sunset(**kwargs)
    noon = solar_noon(**kwargs)
    return rise, noon, sett


def _print_events(zone, rise, noon, sett) -> None:
    print("Sunrise / solar noon / sunset")
    print(f"  Sunrise:    {_format_local(rise, zone) if rise else '(none on this date)'}")
    print(f"  Solar noon: {_format_local(noon, zone) if noon else '(none on this date)'}")
    print(f"  Sunset:     {_format_local(sett, zone) if sett else '(none on this date)'}")


def _print_track_table(site, on_date, zone, *, eph, ts) -> None:
    samples = sun_track_table(
        site.latitude_deg,
        site.longitude_deg,
        site.elevation_m,
        on_date,
        eph=eph,
        ts=ts,
    )
    local_date = on_date.astimezone(zone).strftime("%Y-%m-%d")
    print(f"Today's sun track  {local_date}")
    if not samples:
        print("  (no sunrise/sunset on this date)")
        return
    print(
        f"{'Time':<14} {'Azimuth':>10} {'Elev':>10} {'Trk az':>10} {'Trk el':>10}  Status"
    )
    for sample in samples:
        cmd = tracker_command(sample.azimuth_deg, sample.elevation_deg)
        label = f"  {sample.label}" if sample.label else ""
        print(
            f"{_format_clock(sample.time_utc, zone):<14} "
            f"{sample.azimuth_deg:9.4f}° "
            f"{sample.elevation_deg:9.4f}° "
            f"{cmd.azimuth_deg:9.4f}° "
            f"{cmd.elevation_deg:9.4f}°  "
            f"{cmd.status}{label}"
        )


def _render_live(site, pos, zone, rise, noon, sett, *, interactive: bool) -> str:
    cmd = tracker_command(pos.azimuth_deg, pos.elevation_deg)
    refract = (
        "with refraction" if pos.refraction else "geometric, no refraction"
    )
    lines = [
        "SolarTracker — live view",
        f"Site:      {site.description()}",
        f"Time:      {_format_local(pos.time_utc, zone)}",
        "",
        f"Sun azimuth:       {pos.azimuth_deg:8.4f}°  (eastward from true north)",
        f"Sun elevation:     {pos.elevation_deg:8.4f}°  ({refract})",
        "",
        f"Tracker azimuth:   {cmd.azimuth_deg:8.4f}°  (tracker frame, true north)",
        f"Tracker elevation: {cmd.elevation_deg:8.4f}°",
        f"Status:            {cmd.status}  ({cmd.reason})",
        "",
        f"Sunrise:   {_format_local(rise, zone) if rise else '(none on this date)'}",
        f"Noon:      {_format_local(noon, zone) if noon else '(none on this date)'}",
        f"Sunset:    {_format_local(sett, zone) if sett else '(none on this date)'}",
    ]
    if interactive:
        lines.extend(
            [
                "",
                "[T] today's track table   [S] sunrise / noon / sunset   [Q] quit",
            ]
        )
    return "\n".join(lines)


@contextmanager
def _cbreak_stdin():
    if not sys.stdin.isatty():
        yield False
        return
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield True
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _read_key(timeout: float) -> str | None:
    if not sys.stdin.isatty():
        return None
    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if not ready:
        return None
    ch = sys.stdin.read(1)
    if ch == "\x03":
        raise KeyboardInterrupt
    return ch


def _wait_for_continue(interactive: bool) -> str | None:
    if not interactive:
        return None
    print()
    print("Press any key to return to the live view, or Q to quit.")
    sys.stdout.flush()
    while True:
        key = _read_key(None if sys.stdin.isatty() else 0)
        if key is None:
            return None
        if key.lower() == "q":
            return "q"
        if key:
            return None


def _live_loop(site, zone, *, refraction: bool, live_seconds: float | None) -> int:
    eph = load_ephemeris()
    ts = timescale()
    interactive = sys.stdin.isatty() and live_seconds is None
    started = time.monotonic()
    rise = noon = sett = None
    events_for = None
    use_ansi = sys.stdout.isatty()

    def refresh_events(when):
        nonlocal rise, noon, sett, events_for
        local = when.astimezone(zone)
        day = local.date()
        if events_for != day:
            rise, noon, sett = _day_events(
                site, local, refraction=refraction, eph=eph, ts=ts
            )
            events_for = day

    def snapshot():
        pos = sun_position(
            site.latitude_deg,
            site.longitude_deg,
            site.elevation_m,
            refraction=refraction,
            eph=eph,
            ts=ts,
        )
        refresh_events(pos.time_utc)
        return pos

    try:
        with _cbreak_stdin():
            while True:
                pos = snapshot()
                frame = _render_live(
                    site, pos, zone, rise, noon, sett, interactive=interactive
                )
                if use_ansi:
                    sys.stdout.write("\033[2J\033[H")
                print(frame)
                sys.stdout.flush()

                if live_seconds is not None and (time.monotonic() - started) >= live_seconds:
                    return 0

                remaining = 1.0
                if live_seconds is not None:
                    remaining = min(remaining, live_seconds - (time.monotonic() - started))
                    if remaining <= 0:
                        return 0
                deadline = time.monotonic() + remaining
                key = None
                if interactive:
                    while True:
                        wait = deadline - time.monotonic()
                        if wait <= 0:
                            break
                        key = _read_key(wait)
                        if key:
                            break
                else:
                    time.sleep(remaining)

                if not key:
                    continue
                key = key.lower()
                if key == "q":
                    return 0
                if key == "t":
                    if use_ansi:
                        sys.stdout.write("\033[2J\033[H")
                    _print_track_table(
                        site, pos.time_utc.astimezone(zone), zone, eph=eph, ts=ts
                    )
                    if _wait_for_continue(interactive) == "q":
                        return 0
                elif key == "s":
                    if use_ansi:
                        sys.stdout.write("\033[2J\033[H")
                    _print_events(zone, rise, noon, sett)
                    if _wait_for_continue(interactive) == "q":
                        return 0
    except KeyboardInterrupt:
        print()
        return 0
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    site = _load_site_loader().load_site(ROOT)
    zone = _resolve_zone(args.timezone)
    if zone is None:
        print(f"Unknown timezone: {args.timezone}", file=sys.stderr)
        return 2

    one_shot = (
        args.json
        or args.once
        or args.time is not None
        or (args.live_seconds is None and not sys.stdin.isatty())
    )
    eph = load_ephemeris()
    ts = timescale()

    if one_shot and args.live_seconds is None:
        pos = sun_position(
            site.latitude_deg,
            site.longitude_deg,
            site.elevation_m,
            args.time,
            refraction=not args.no_refract,
            eph=eph,
            ts=ts,
        )
        rise, noon, sett = _day_events(
            site,
            pos.time_utc.astimezone(zone),
            refraction=not args.no_refract,
            eph=eph,
            ts=ts,
        )
        if args.json:
            json.dump(_payload(site, pos, zone, rise, noon, sett), sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            _print_report(site, pos, zone, rise, noon, sett)
        return 0

    return _live_loop(
        site,
        zone,
        refraction=not args.no_refract,
        live_seconds=args.live_seconds,
    )


if __name__ == "__main__":
    sys.exit(main())
