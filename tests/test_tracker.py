"""Tracker-frame pointing and night-stow policy."""

from solartracker.tracker import (
    STOW_AZIMUTH_DEG,
    STOW_ELEVATION_DEG,
    tracker_command,
)


def test_tracking_when_sun_is_above_horizon():
    cmd = tracker_command(194.340241, 39.888378)
    assert cmd.status == "TRACKING"
    assert cmd.is_stowed is False
    assert abs(cmd.azimuth_deg - 194.340241) < 1e-9
    assert abs(cmd.elevation_deg - 39.888378) < 1e-9


def test_stow_when_sun_is_below_horizon():
    cmd = tracker_command(270.0, -15.0)
    assert cmd.status == "STOW"
    assert cmd.is_stowed is True
    assert cmd.azimuth_deg == STOW_AZIMUTH_DEG
    assert cmd.elevation_deg == STOW_ELEVATION_DEG
    assert STOW_AZIMUTH_DEG == 180.0
    assert STOW_ELEVATION_DEG == 0.0


def test_horizon_is_still_tracking():
    cmd = tracker_command(90.0, 0.0)
    assert cmd.status == "TRACKING"
    assert cmd.elevation_deg == 0.0
