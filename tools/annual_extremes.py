#!/usr/bin/env python3
"""Yearly sun-elevation and daylight-azimuth extremes for the configured site.

Uses 1-minute vectorized Skyfield / DE421 samples (about 90 s for one year).
Prints times and angles only — never site coordinates. Matplotlib is optional:
without it, the numeric report still runs and the plot is skipped.

Example:
    python tools/annual_extremes.py --year 2026 --output docs/sun_year_2026.png
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from skyfield.api import wgs84  # noqa: E402

from solartracker.ephemeris import load_ephemeris, timescale  # noqa: E402


def _load_site():
    path = ROOT / "site.py"
    spec = spec_from_file_location("_solartracker_site_loader", path)
    module = module_from_spec(spec)
    sys.modules["_solartracker_site_loader"] = module
    spec.loader.exec_module(module)
    return module.load_site(ROOT)


def _when(times, index: int, zone) -> str:
    dt = times[int(index)].utc_datetime().replace(tzinfo=timezone.utc).astimezone(zone)
    return dt.strftime("%b %d %Y %I:%M %p %Z")


def _report(name: str, alt, az, times, zone) -> dict:
    up = np.where(alt > 0.0)[0]
    if up.size == 0:
        raise SystemExit(f"No daylight samples for the {name} case.")
    daylight_az = az[up]
    result = {
        "max_elevation": (float(alt.max()), _when(times, int(alt.argmax()), zone)),
        "min_daylight_azimuth": (
            float(daylight_az.min()),
            _when(times, int(up[daylight_az.argmin()]), zone),
        ),
        "max_daylight_azimuth": (
            float(daylight_az.max()),
            _when(times, int(up[daylight_az.argmax()]), zone),
        ),
    }
    print(f"{name}:")
    for key, (value, when) in result.items():
        print(f"  {key:22s}  {value:8.3f}°   {when}")
    return result


def _daily_limits(alt, az, n_days: int):
    """Split 1-minute samples into whole days (n_days × 1440)."""
    d_alt = alt.reshape(n_days, 1440)
    d_az = az.reshape(n_days, 1440)
    max_el = d_alt.max(axis=1)
    rise = np.full(n_days, np.nan)
    sett = np.full(n_days, np.nan)
    for day in range(n_days):
        up = np.where(d_alt[day] > 0.0)[0]
        if up.size:
            rise[day] = d_az[day, up[0]]
            sett[day] = d_az[day, up[-1]]
    return max_el, rise, sett


def _plot(days, max_el, rise, sett, year: int, output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].plot(days, max_el, color="#d9822b")
    axes[0].set_title(f"Solar-noon elevation, {year} (with refraction)")
    axes[0].set_ylabel("deg")
    axes[0].grid(alpha=0.3)
    axes[1].plot(days, rise, label="sunrise azimuth")
    axes[1].plot(days, sett, label="sunset azimuth")
    axes[1].set_title(f"Daylight azimuth limits, {year}")
    axes[1].set_ylabel("deg (0=N, 90=E, 180=S)")
    axes[1].legend()
    axes[1].grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=120)
    print(f"Wrote {output}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Yearly sun extremes for the configured site (no coordinates printed)."
    )
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument(
        "--timezone",
        default="America/Chicago",
        help="IANA timezone for reported times (default: America/Chicago).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="PNG path for the two-panel chart (skipped if matplotlib is missing).",
    )
    args = parser.parse_args(argv)

    site = _load_site()
    zone = ZoneInfo(args.timezone)
    # Start at local standard midnight so each reshape row is one civil day
    # in a fixed offset (DST is ignored for day boundaries).
    jan1_local = datetime(args.year, 1, 1, tzinfo=zone)
    start_utc = jan1_local.astimezone(timezone.utc)
    jan1_next = datetime(args.year + 1, 1, 1, tzinfo=zone)
    n_days = (jan1_next.date() - jan1_local.date()).days
    n = n_days * 1440

    print(f"Site: {site.name}  (coordinates not printed)")
    print(f"Sampling {n} 1-minute steps from {jan1_local:%Y-%m-%d} local…")

    eph = load_ephemeris()
    ts = timescale()
    # ts.utc(year, month, day, hour, minute_array) is relative to that civil UTC clock.
    minutes = np.arange(n)
    times = ts.utc(
        start_utc.year,
        start_utc.month,
        start_utc.day,
        start_utc.hour,
        start_utc.minute + minutes,
    )
    observer = eph["earth"] + wgs84.latlon(
        site.latitude_deg, site.longitude_deg, elevation_m=site.elevation_m
    )
    apparent = observer.at(times).observe(eph["sun"]).apparent()
    alt_g, az, _ = apparent.altaz()  # geometric
    alt_r, _, _ = apparent.altaz(temperature_C="standard")
    alt_g = alt_g.degrees
    alt_r = alt_r.degrees
    az = az.degrees

    _report("geometric", alt_g, az, times, zone)
    _report("refraction", alt_r, az, times, zone)

    noon = alt_r.reshape(n_days, 1440).max(axis=1)
    imin = int(noon.argmin())
    low_day = jan1_local + timedelta(days=imin)
    print(
        f"lowest noon elevation (refracted daily max): {noon[imin]:.1f}°  "
        f"on {low_day:%b %d %Y}"
    )

    if args.output is not None:
        try:
            max_el, rise, sett = _daily_limits(alt_r, az, n_days)
            days = [jan1_local + timedelta(days=k) for k in range(n_days)]
            _plot(days, max_el, rise, sett, args.year, args.output)
        except ImportError:
            print("matplotlib is not installed; skipping the plot.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
