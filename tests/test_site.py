"""Site loading uses the committed example and an optional local override."""

from __future__ import annotations

import sys
from pathlib import Path

from importlib.util import module_from_spec, spec_from_file_location


def _load_site_module(project_root: Path):
    path = project_root / "site.py"
    spec = spec_from_file_location("_solartracker_site_loader_test", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules["_solartracker_site_loader_test"] = module
    spec.loader.exec_module(module)
    return module


def test_example_site_is_the_public_dallas_placeholder(project_root: Path):
    site_mod = _load_site_module(project_root)
    example = site_mod._load_py(
        project_root / "site.example.py", "_solartracker_example_check"
    )
    assert example.NAME == "Example (Dallas, Texas)"
    assert example.LATITUDE_DEG == 32.7767
    assert example.LONGITUDE_DEG == -96.7970
    assert example.ELEVATION_M == 140.0


def test_load_site_uses_example_when_no_local_file(project_root: Path, tmp_path: Path):
    # Copy only the example into a temp tree so a developer's site_local.py
    # cannot affect the test.
    (tmp_path / "site.example.py").write_text(
        (project_root / "site.example.py").read_text()
    )
    site_mod = _load_site_module(project_root)
    site = site_mod.load_site(tmp_path)
    assert site.name == "Example (Dallas, Texas)"
    assert site.latitude_deg == 32.7767
    assert site.longitude_deg == -96.7970
    assert site.elevation_m == 140.0


def test_load_site_applies_local_overrides(project_root: Path, tmp_path: Path):
    (tmp_path / "site.example.py").write_text(
        (project_root / "site.example.py").read_text()
    )
    # A public override location: Greenwich Observatory, not a private site.
    (tmp_path / "site_local.py").write_text(
        "NAME = 'Greenwich Observatory'\n"
        "LATITUDE_DEG = 51.4769\n"
        "LONGITUDE_DEG = -0.0005\n"
        "ELEVATION_M = 46.0\n"
    )
    site_mod = _load_site_module(project_root)
    site = site_mod.load_site(tmp_path)
    assert site.name == "Greenwich Observatory"
    assert site.latitude_deg == 51.4769
    assert site.longitude_deg == -0.0005
    assert site.elevation_m == 46.0
    # The example file itself must stay unchanged.
    example = site_mod._load_py(
        tmp_path / "site.example.py", "_solartracker_example_unchanged"
    )
    assert example.LATITUDE_DEG == 32.7767
