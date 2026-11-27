"""Load the observer site for the console.

Default values come from ``site.example.py`` in the project root. If
``site_local.py`` is present in the same directory, its values override
the example. Keep real installation coordinates in ``site_local.py`` only;
that file is gitignored and must not be committed.

This module is loaded by file path under a private name so it does not
shadow Python's standard library ``site`` module.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent
EXAMPLE_PATH = ROOT / "site.example.py"
LOCAL_PATH = ROOT / "site_local.py"


@dataclass(frozen=True)
class Site:
    """An observer location on Earth."""

    name: str
    latitude_deg: float
    longitude_deg: float
    elevation_m: float

    def description(self) -> str:
        ns = "N" if self.latitude_deg >= 0 else "S"
        ew = "E" if self.longitude_deg >= 0 else "W"
        return (
            f"{self.name} ({abs(self.latitude_deg):.6f}° {ns}, "
            f"{abs(self.longitude_deg):.6f}° {ew}, {self.elevation_m:.1f} m)"
        )


def _load_py(path: Path, module_name: str) -> ModuleType:
    spec = spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load site file: {path}")
    module = module_from_spec(spec)
    # Register before exec so dataclasses can resolve string annotations.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_site(root: Path | None = None) -> Site:
    """Return the active site, applying ``site_local.py`` overrides when present."""
    base = ROOT if root is None else Path(root)
    example_path = base / "site.example.py"
    local_path = base / "site_local.py"
    example = _load_py(example_path, "_solartracker_site_example")
    data = {
        "name": example.NAME,
        "latitude_deg": float(example.LATITUDE_DEG),
        "longitude_deg": float(example.LONGITUDE_DEG),
        "elevation_m": float(example.ELEVATION_M),
    }
    if local_path.is_file():
        local = _load_py(local_path, "_solartracker_site_local")
        mapping = {
            "name": "NAME",
            "latitude_deg": "LATITUDE_DEG",
            "longitude_deg": "LONGITUDE_DEG",
            "elevation_m": "ELEVATION_M",
        }
        for field, attr in mapping.items():
            if hasattr(local, attr):
                value = getattr(local, attr)
                data[field] = float(value) if field != "name" else value
    return Site(**data)
