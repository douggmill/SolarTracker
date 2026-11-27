"""Compare Skyfield sun positions to the public NREL SPA reference case.

The reference is the well-published example from Reda & Andreas, Solar
Position Algorithm for Solar Radiation Applications, NREL/TP-560-34302
(revised January 2008), as implemented in NREL's spa_tester.c:

    2003-10-17 12:30:30, timezone -7 (19:30:30 UTC)
    latitude  39.742476° N
    longitude 105.1786° W
    elevation 1830.14 m
    pressure  820 mbar, temperature 11 °C, delta_t 67 s

    apparent zenith  50.111622°  =>  elevation 39.888378°
    azimuth          194.340241° (eastward from true north)

This is a public laboratory site in Golden, Colorado, not a private
installation. Tests must keep using a public reference location.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from solartracker import solar_noon, sun_position, sun_track_table, sunrise_sunset
from solartracker.ephemeris import load_ephemeris, timescale

# NREL Solar Radiation Research Laboratory, Golden, Colorado (public).
NREL_LAT = 39.742476
NREL_LON = -105.1786
NREL_ELEV_M = 1830.14
NREL_WHEN = datetime(2003, 10, 17, 19, 30, 30, tzinfo=timezone.utc)
NREL_AZIMUTH = 194.340241
NREL_ELEVATION = 90.0 - 50.111622  # 39.888378
# DE440s vs the SPA analytic series should agree to a small fraction of a degree.
TOLERANCE_DEG = 0.05


def test_nrel_spa_golden_colorado_azimuth_and_elevation():
    pos = sun_position(
        NREL_LAT,
        NREL_LON,
        NREL_ELEV_M,
        NREL_WHEN,
        temperature_C=11.0,
        pressure_mbar=820.0,
        refraction=True,
    )
    assert abs(pos.azimuth_deg - NREL_AZIMUTH) < TOLERANCE_DEG
    assert abs(pos.elevation_deg - NREL_ELEVATION) < TOLERANCE_DEG
    assert pos.refraction is True


def test_azimuth_range_and_north_of_equator_afternoon():
    """A mid-afternoon sun at Golden should be in the western sky."""
    pos = sun_position(
        NREL_LAT,
        NREL_LON,
        NREL_ELEV_M,
        NREL_WHEN,
        temperature_C=11.0,
        pressure_mbar=820.0,
    )
    assert 0.0 <= pos.azimuth_deg < 360.0
    assert 180.0 < pos.azimuth_deg < 270.0
    assert pos.elevation_deg > 0.0


def test_geometric_elevation_is_below_refracted():
    kwargs = dict(
        latitude_deg=NREL_LAT,
        longitude_deg=NREL_LON,
        elevation_m=NREL_ELEV_M,
        when=NREL_WHEN,
    )
    refracted = sun_position(**kwargs, temperature_C=11.0, pressure_mbar=820.0)
    geometric = sun_position(**kwargs, refraction=False)
    # Refraction lifts the apparent sun, so apparent elevation is higher.
    assert refracted.elevation_deg > geometric.elevation_deg
    assert geometric.refraction is False


def test_sunrise_is_before_sunset_at_golden():
    eph = load_ephemeris()
    ts = timescale()
    mst = timezone(timedelta(hours=-7))
    rise, sett = sunrise_sunset(
        NREL_LAT,
        NREL_LON,
        NREL_ELEV_M,
        on_date=datetime(2003, 10, 17, tzinfo=mst),
        eph=eph,
        ts=ts,
    )
    assert rise is not None and sett is not None
    assert rise < sett
    # spa_tester.c lists local (UTC-7) sunrise 06:12:43 and sunset 17:20:19,
    # i.e. 13:12:43 UTC on Oct 17 and 00:20:19 UTC on Oct 18. Allow a few
    # minutes for the apparent-horizon definition.
    assert rise.day == 17 and rise.hour == 13
    assert abs((rise.minute + rise.second / 60.0) - 12.7) < 3.0
    assert sett.day == 18 and sett.hour == 0
    assert abs((sett.minute + sett.second / 60.0) - 20.3) < 3.0


def test_solar_noon_is_between_sunrise_and_sunset_at_golden():
    mst = timezone(timedelta(hours=-7))
    on_date = datetime(2003, 10, 17, tzinfo=mst)
    eph = load_ephemeris()
    ts = timescale()
    kwargs = dict(
        latitude_deg=NREL_LAT,
        longitude_deg=NREL_LON,
        elevation_m=NREL_ELEV_M,
        on_date=on_date,
        eph=eph,
        ts=ts,
    )
    rise, sett = sunrise_sunset(**kwargs)
    noon = solar_noon(**kwargs)
    assert rise is not None and sett is not None and noon is not None
    assert rise < noon < sett
    # Meridian transit should be the high point of the day.
    el_noon = sun_position(NREL_LAT, NREL_LON, NREL_ELEV_M, noon, eph=eph, ts=ts)
    el_rise = sun_position(NREL_LAT, NREL_LON, NREL_ELEV_M, rise, eph=eph, ts=ts)
    assert el_noon.elevation_deg > el_rise.elevation_deg
    # Around midday in October at Golden, the sun is in the southern sky.
    assert 150.0 < el_noon.azimuth_deg < 210.0


def test_sun_track_table_includes_event_rows():
    mst = timezone(timedelta(hours=-7))
    samples = sun_track_table(
        NREL_LAT,
        NREL_LON,
        NREL_ELEV_M,
        datetime(2003, 10, 17, tzinfo=mst),
        step_minutes=30,
        eph=load_ephemeris(),
        ts=timescale(),
    )
    labels = [row.label for row in samples]
    assert labels[0] == "sunrise"
    assert labels[-1] == "sunset"
    assert "solar noon" in labels
    assert len(samples) > 3
    assert all(0.0 <= row.azimuth_deg < 360.0 for row in samples)
