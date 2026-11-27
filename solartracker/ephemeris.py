"""Load the JPL DE440s ephemeris and a Skyfield timescale.

Data files are stored in the project root (or ``SOLARTRACKER_DATA``, if
set). ``de440s.bsp`` is about 31 MB, covers years 1849–2150, and is
gitignored. It is downloaded from JPL only if the file is missing, and
is never re-downloaded afterward.

# DE440s is a fixed snapshot published by JPL in 2020 that never changes.
# Replace the file only when JPL publishes a newer or patch release (for
# example DE442, released in 2025 as a Uranus-focused update to DE440),
# not on a schedule.
"""

from __future__ import annotations

import os
import urllib.request
from collections.abc import Callable
from pathlib import Path

from skyfield.api import Loader
from skyfield.jpllib import SpiceKernel

_ROOT = Path(__file__).resolve().parents[1]

EPHEMERIS_NAME = "de440s.bsp"
EPHEMERIS_URL = "https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de440s.bsp"
DOWNLOAD_TIMEOUT_S = 120

Downloader = Callable[[str, Path, float], None]
Opener = Callable[[Path], SpiceKernel]


def data_directory() -> Path:
    override = os.environ.get("SOLARTRACKER_DATA")
    path = Path(override) if override else _ROOT
    path.mkdir(parents=True, exist_ok=True)
    return path


def loader():
    return Loader(str(data_directory()))


def _default_download(url: str, dest: Path, timeout: float) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "SolarTracker"})
    with urllib.request.urlopen(request, timeout=timeout) as response, dest.open("wb") as handle:
        while True:
            chunk = response.read(256 * 1024)
            if not chunk:
                break
            handle.write(chunk)


def _default_open(path: Path) -> SpiceKernel:
    return SpiceKernel(str(path))


def load_ephemeris(
    *,
    data_dir: Path | None = None,
    downloader: Downloader | None = None,
    opener: Opener | None = None,
    timeout: float | None = None,
) -> SpiceKernel:
    """Open ``de440s.bsp``, downloading it from JPL only if it is missing."""
    directory = Path(data_dir) if data_dir is not None else data_directory()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / EPHEMERIS_NAME
    fetch = downloader or _default_download
    open_kernel = opener or _default_open
    wait = DOWNLOAD_TIMEOUT_S if timeout is None else timeout

    if not path.is_file():
        tmp = path.with_name(path.name + ".tmp")
        try:
            fetch(EPHEMERIS_URL, tmp, wait)
            open_kernel(tmp)
            os.replace(tmp, path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    return open_kernel(path)


def timescale():
    return loader().timescale()
