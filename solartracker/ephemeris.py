"""Load the JPL DE421 ephemeris and a Skyfield timescale.

Data files are stored in the project root (or ``SOLARTRACKER_DATA``, if
set). ``de421.bsp`` is about 17 MB and is gitignored; Skyfield downloads
it on first use if it is not already present.
"""

from __future__ import annotations

import os
from pathlib import Path

from skyfield.api import Loader

_ROOT = Path(__file__).resolve().parents[1]


def data_directory() -> Path:
    override = os.environ.get("SOLARTRACKER_DATA")
    path = Path(override) if override else _ROOT
    path.mkdir(parents=True, exist_ok=True)
    return path


def loader():
    return Loader(str(data_directory()))


def load_ephemeris():
    return loader()("de421.bsp")


def timescale():
    return loader().timescale()
