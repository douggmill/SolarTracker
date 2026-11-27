"""Ephemeris download happens only when de440s.bsp is missing. No network."""

from __future__ import annotations

from pathlib import Path

import pytest

from solartracker import ephemeris


def test_present_file_is_opened_without_downloading(tmp_path: Path):
    path = tmp_path / ephemeris.EPHEMERIS_NAME
    path.write_bytes(b"local-kernel")
    calls: list[tuple[str, Path, float]] = []

    def downloader(url: str, dest: Path, timeout: float) -> None:
        calls.append((url, dest, timeout))

    def opener(candidate: Path):
        assert candidate == path
        return f"opened:{candidate.read_bytes().decode()}"

    kernel = ephemeris.load_ephemeris(
        data_dir=tmp_path, downloader=downloader, opener=opener
    )
    assert kernel == "opened:local-kernel"
    assert calls == []
    assert path.read_bytes() == b"local-kernel"


def test_missing_file_downloads_once_then_opens(tmp_path: Path):
    calls: list[tuple[str, Path, float]] = []

    def downloader(url: str, dest: Path, timeout: float) -> None:
        calls.append((url, dest, timeout))
        dest.write_bytes(b"from-jpl")

    opened: list[Path] = []

    def opener(candidate: Path):
        opened.append(candidate)
        assert candidate.read_bytes() == b"from-jpl"
        return "ok"

    kernel = ephemeris.load_ephemeris(
        data_dir=tmp_path, downloader=downloader, opener=opener, timeout=7.0
    )
    assert kernel == "ok"
    assert calls == [(ephemeris.EPHEMERIS_URL, tmp_path / "de440s.bsp.tmp", 7.0)]
    assert (tmp_path / ephemeris.EPHEMERIS_NAME).read_bytes() == b"from-jpl"
    assert not (tmp_path / "de440s.bsp.tmp").exists()
    # Validate-on-temp, then open the final path.
    assert [p.name for p in opened] == ["de440s.bsp.tmp", "de440s.bsp"]


def test_failed_first_download_does_not_leave_a_temp_or_partial(tmp_path: Path):
    def downloader(url: str, dest: Path, timeout: float) -> None:
        dest.write_bytes(b"partial")
        raise OSError("offline")

    with pytest.raises(OSError, match="offline"):
        ephemeris.load_ephemeris(
            data_dir=tmp_path, downloader=downloader, opener=lambda p: p
        )
    assert not (tmp_path / ephemeris.EPHEMERIS_NAME).exists()
    assert not (tmp_path / "de440s.bsp.tmp").exists()
