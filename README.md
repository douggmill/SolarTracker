# SolarTracker

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

SolarTracker computes the sun's azimuth and elevation at a configured observer site using NASA JPL's DE421 planetary ephemeris through [Skyfield](https://rhodesmill.org/skyfield/). It is the software foundation for a dual-axis solar tracker; the current release is a desktop console that reports sun position, sunrise, and sunset.

- [Overview](#overview)
- [Hardware and goal](#hardware-and-goal)
- [Install](#install)
- [Usage](#usage)
- [Testing](#testing)
- [Project layout](#project-layout)
- [Roadmap](#roadmap)
- [License](#license)

## Overview

The console reads an observer site (latitude, longitude, and elevation), loads DE421, and prints the sun's topocentric azimuth (eastward from true north) and elevation, including atmospheric refraction by default. Sunrise and sunset for the same civil date are included in the report.

Site coordinates that belong to a real installation live only in a gitignored `site_local.py`. The repository ships `site.example.py` with a public placeholder so the project can be cloned and run without exposing a private location.

## Hardware and goal

The long-term goal is a dual-axis tracker that points a payload at the sun. Position solutions in this repository are accurate enough for that job: Skyfield plus DE421 is compared in the test suite against the public NREL Solar Position Algorithm (SPA) reference case for the laboratory site in Golden, Colorado (Reda & Andreas, NREL/TP-560-34302).

On-controller firmware (planned around an ESP32) is deferred. This repository is the Python model, console, and tests that a later firmware port can follow.

## Install

Python 3.10 or later is required. From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On first run, Skyfield downloads `de421.bsp` (about 17 MB) and small timescale files into the project root. Those files are gitignored. You can also copy a local `de421.bsp` into the project root yourself. To store data somewhere else, set `SOLARTRACKER_DATA` to that directory.

Configure your site (optional, but recommended for personal use):

```bash
cp site.example.py site_local.py
```

Then edit `site_local.py` with your latitude, longitude, and elevation in meters. Do not commit that file.

## Usage

From the project root, with the virtual environment active:

```bash
python console.py
python console.py --time 2026-11-26T18:00:00-06:00
python console.py --no-refract
python console.py --json
python console.py --timezone America/Chicago
```

`run_console.sh` does the same thing using `.venv` when it is present, and waits for Enter so it can be used from a desktop launcher.

Example text output (placeholder Dallas site):

```text
SolarTracker
Site:      Example (Dallas, Texas) (32.776700° N, 96.797000° W, 140.0 m)
Time:      2026-11-26 18:00:00 CST (2026-11-27T00:00:00.000000Z)
Azimuth:    250.2312°  (eastward from true north)
Elevation:   -8.3230°  (with refraction)
Sunrise:   2026-11-26 07:07:21 CST
Sunset:    2026-11-26 17:21:30 CST
```

Azimuth is 0° at true north, 90° at east, 180° at south, and 270° at west. Elevation is degrees above the geometric horizon and is negative when the sun is down.

## Testing

```bash
source .venv/bin/activate
python -m pytest -q
```

The sun-position tests check Skyfield against the published NREL SPA example for Golden, Colorado, on 2003-10-17 12:30:30 (timezone −7, 19:30:30 UTC): apparent azimuth 194.340241° and apparent elevation 39.888378°, to within 0.05°. Site-loading tests use the committed Dallas placeholder and a temporary Greenwich override; they do not depend on a private `site_local.py`.

## Project layout

```text
SolarTracker/
  console.py                 Command-line entry point
  run_console.sh             Launcher that uses .venv when present
  site.py                    Loads site.example.py, then site_local.py
  site.example.py            Public placeholder coordinates (Dallas, Texas)
  site_local.py              Optional real site; gitignored, not in the repo
  solartracker/
    ephemeris.py             DE421 and timescale loader
    sun.py                   Azimuth, elevation, sunrise, and sunset
  tests/
    test_sun_position.py     NREL SPA (Golden, CO) comparison
    test_site.py             Example site and local overrides
  requirements.txt
  LICENSE
  README.md
```

## Roadmap

- Keep the console and tests current as the position model is refined.
- ESP32 firmware that consumes the same site model and sun-position solution is deferred.
- A later pass may restore a planet-direction display, in the spirit of the earlier desktop experiments that motivated this project.
- Mechanical design, sensors, and motor control come after the firmware work.

## License

MIT. See [LICENSE](LICENSE).
