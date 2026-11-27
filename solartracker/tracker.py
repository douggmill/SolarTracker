"""Tracker-frame pointing and night-stow policy.

This is a software model for a future dual-axis mount. Azimuth is
eastward from true north, and elevation is degrees above the horizon.
When the sun is below the horizon the mount is commanded to a
horizontal south-facing stow.
"""

from __future__ import annotations

from dataclasses import dataclass

MIN_TRACK_ELEVATION_DEG = 0.0
STOW_AZIMUTH_DEG = 180.0
STOW_ELEVATION_DEG = 0.0


@dataclass(frozen=True)
class TrackerCommand:
    """Commanded mount pose for a sun position."""

    azimuth_deg: float
    elevation_deg: float
    status: str  # "TRACKING" or "STOW"
    reason: str

    @property
    def is_stowed(self) -> bool:
        return self.status == "STOW"


def tracker_command(sun_azimuth_deg: float, sun_elevation_deg: float) -> TrackerCommand:
    """Return the mount command for a topocentric sun position."""
    if sun_elevation_deg >= MIN_TRACK_ELEVATION_DEG:
        return TrackerCommand(
            azimuth_deg=sun_azimuth_deg % 360.0,
            elevation_deg=min(sun_elevation_deg, 90.0),
            status="TRACKING",
            reason="sun above horizon",
        )
    return TrackerCommand(
        azimuth_deg=STOW_AZIMUTH_DEG,
        elevation_deg=STOW_ELEVATION_DEG,
        status="STOW",
        reason="sun below horizon",
    )
