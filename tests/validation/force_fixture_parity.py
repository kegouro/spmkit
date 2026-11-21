"""Regeneration checks for frozen synthetic force fixtures."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np


def assert_fixture_values(actual, frozen, key: str, max_ulp: int = 0) -> None:
    actual = np.asarray(actual)
    frozen = np.asarray(frozen)
    assert actual.shape == frozen.shape, key
    assert actual.dtype == frozen.dtype == np.dtype("<f8"), key

    actual_bits = actual.view("<u8")
    frozen_bits = frozen.view("<u8")
    changed = actual_bits != frozen_bits
    if not max_ulp or not np.any(changed):
        np.testing.assert_array_equal(actual_bits, frozen_bits, err_msg=key)
        return

    # Zero, sign and nonfinite representations are part of the fixture contract.
    a = actual[changed]
    b = frozen[changed]
    assert np.all(np.isfinite(a) & np.isfinite(b) & (a != 0) & (b != 0)), key
    np.testing.assert_array_equal(np.signbit(a), np.signbit(b), err_msg=key)
    try:
        np.testing.assert_array_max_ulp(a, b, maxulp=max_ulp)
    except AssertionError as error:
        raise AssertionError(f"{key}: {error}") from error


def regenerate_fixture(
    generator: Path,
    manifest: Path,
    arrays: Path,
    tmp_path: Path,
    array_ulps: dict[str, int],
) -> bytes:
    """Check same-runtime byte determinism and cross-runtime array parity."""
    out1, out2 = tmp_path / "first", tmp_path / "second"
    for out in (out1, out2):
        out.mkdir()
        subprocess.run([sys.executable, str(generator), str(out)], check=True)
    for path in (manifest, arrays):
        assert (out1 / path.name).read_bytes() == (out2 / path.name).read_bytes(), path.name

    with (
        np.load(out1 / arrays.name, allow_pickle=False) as actual,
        np.load(arrays, allow_pickle=False) as frozen,
    ):
        assert actual.files == frozen.files
        for key in frozen.files:
            assert_fixture_values(actual[key], frozen[key], key, array_ulps.get(key, 0))

    return (out1 / manifest.name).read_bytes()
