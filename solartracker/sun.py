"""Sun azimuth and elevation for an observer on Earth."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from skyfield import almanac
from skyfield.api import wgs84

from .ephemeris import load_ephemeris, timescale


@dataclass(frozen=True)
class SunPosition:
    """Topocentric sun position.

    Azimuth is measured eastward from true north, in the range [0, 360).
    Elevation is degrees above the horizon (negative when the sun is down).
    When ``refraction`` is true, the elevation includes atmospheric
    refraction at the given temperature and pressure (Skyfield defaults
    if those are omitted).
    """

    azimuth_deg: float
    elevation_deg: float
    time_utc: datetime
    refraction: bool
    temperature_C: Optional[float] = None
    pressure_mbar: Optional[float] = None


def _as_skyfield_time(ts, when: Optional[datetime]):
    if when is None:
        return ts.now()
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    when = when.astimezone(timezone.utc)
    return ts.from_datetime(when)


def sun_position(
    latitude_deg: float,
    longitude_deg: float,
    elevation_m: float = 0.0,
    when: Optional[datetime] = None,
    *,
    temperature_C: Optional[float] = None,
    pressure_mbar: Optional[float] = None,
    refraction: bool = True,
    eph=None,
    ts=None,
) -> SunPosition:
    """Return the sun's azimuth and elevation at a site and time.

    ``when`` is interpreted as UTC if it is naive. If ``refraction`` is
    true, pass ``temperature_C`` and ``pressure_mbar`` to use a specific
    atmosphere; otherwise Skyfield's standard refraction is applied.
    """
    if eph is None:
        eph = load_ephemeris()
    if ts is None:
        ts = timescale()

    t = _as_skyfield_time(ts, when)
    earth = eph["earth"]
    sun = eph["sun"]
    loc = wgs84.latlon(latitude_deg, longitude_deg, elevation_m=elevation_m)
    apparent = (earth + loc).at(t).observe(sun).apparent()

    if not refraction:
        alt, az, _ = apparent.altaz(temperature_C=0.0, pressure_mbar=0.0)
        applied = False
    elif temperature_C is not None and pressure_mbar is not None:
        alt, az, _ = apparent.altaz(
            temperature_C=temperature_C, pressure_mbar=pressure_mbar
        )
        applied = True
    else:
        alt, az, _ = apparent.altaz()
        applied = True

    utc = t.utc_datetime().replace(tzinfo=timezone.utc)
    return SunPosition(
        azimuth_deg=az.degrees % 360.0,
        elevation_deg=alt.degrees,
        time_utc=utc,
        refraction=applied,
        temperature_C=temperature_C,
        pressure_mbar=pressure_mbar,
    )


def sunrise_sunset(
    latitude_deg: float,
    longitude_deg: float,
    elevation_m: float = 0.0,
    on_date: Optional[datetime] = None,
    *,
    eph=None,
    ts=None,
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Return UTC sunrise and sunset for the civil date of ``on_date``.

    The date is taken in UTC if ``on_date`` is naive, otherwise in that
    datetime's timezone. Either value may be ``None`` at polar day/night.
    """
    if eph is None:
        eph = load_ephemeris()
    if ts is None:
        ts = timescale()

    if on_date is None:
        on_date = datetime.now(timezone.utc)
    elif on_date.tzinfo is None:
        on_date = on_date.replace(tzinfo=timezone.utc)

    start = on_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    loc = wgs84.latlon(latitude_deg, longitude_deg, elevation_m=elevation_m)
    t0 = ts.from_datetime(start.astimezone(timezone.utc))
    t1 = ts.from_datetime(end.astimezone(timezone.utc))
    times, events = almanac.find_discrete(t0, t1, almanac.sunrise_sunset(eph, loc))

    rise = set_ = None
    for time, event in zip(times, events):
        stamp = time.utc_datetime().replace(tzinfo=timezone.utc)
        if event:  # 1 = sunrise
            rise = stamp
        else:
            set_ = stamp
    return rise, set_
