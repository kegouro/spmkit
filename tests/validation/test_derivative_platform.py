"""Independent all-platform verification beside the immutable frozen campaign."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from spmkit.core.analysis import gwyddion_gradient_magnitude
from spmkit.core.models import SPMChannel
from tests.validation import derivative_platform as backend

FIXTURES = Path(__file__).parent / "fixtures/gwyddion/derivative_filters"


def test_runtime_and_frozen_magnitudes_are_faithfully_rounded(record_property) -> None:
    arrays = np.load(FIXTURES / "derivative_filters_reference.npz", allow_pickle=False)
    cases = json.loads((FIXTURES / "derivative_filters_reference.json").read_text())["cases"]
    count = 0
    max_frozen_ulp = 0
    max_real_ulp = 0
    for cid, meta in cases.items():
        shape = (int(meta["yres"]), int(meta["xres"]))
        for family in ("sobel", "prewitt"):
            x, y = arrays[f"{family}_x_{cid}"], arrays[f"{family}_y_{cid}"]
            frozen = arrays[f"mag_{family}_{cid}"]
            channels = [SPMChannel("test", a.reshape(shape), "m", 1.0, 1.0) for a in (x, y)]
            production = gwyddion_gradient_magnitude(*channels).data.reshape(-1)
            runtime = backend.runtime_magnitude(x, y).reshape(-1)
            # Preserve Gwyddion's host-C hypot semantics bitwise on every host.
            assert np.array_equal(production.view(np.uint64), runtime.view(np.uint64)), cid
            for i, (a, b, actual, reference) in enumerate(
                zip(x, y, production, frozen, strict=True)
            ):
                nearest = float(backend.exact_hypot(float(a), float(b)))
                assert backend.faithful_hypot(float(a), float(b), float(actual)), (
                    cid,
                    family,
                    i,
                    float(a).hex(),
                    float(b).hex(),
                    float(actual).hex(),
                    nearest.hex(),
                    backend.backend_identity(),
                )
                assert backend.faithful_hypot(float(a), float(b), float(reference)), (
                    "frozen",
                    cid,
                    family,
                    i,
                )
                bits = int(np.float64(actual).view(np.uint64))
                max_frozen_ulp = max(max_frozen_ulp, abs(bits - int(reference.view(np.uint64))))
                max_real_ulp = max(
                    max_real_ulp, abs(bits - int(np.float64(nearest).view(np.uint64)))
                )
                count += 1
    assert len(cases) == 57 and count == 2748
    metrics = {
        "backend": backend.backend_identity(),
        "cases": 57,
        "values": count,
        "runtime_c_bitwise": True,
        "max_frozen_ulp": max_frozen_ulp,
        "max_nearest_real_ulp": max_real_ulp,
    }
    record_property("derivative_platform_metrics", json.dumps(metrics))
    print(json.dumps(metrics, sort_keys=True))


def test_exact_oracle_rejects_nonfaithful_results() -> None:
    assert backend.faithful_hypot(3.0, 4.0, 5.0)
    assert not backend.faithful_hypot(3.0, 4.0, float(np.nextafter(5.0, np.inf)))
    x, y = -0.7888425248937188, -0.2144684604488727
    nearest = float(backend.exact_hypot(x, y))
    wrong = float(np.nextafter(np.nextafter(nearest, np.inf), np.inf))
    assert not backend.faithful_hypot(x, y, wrong)


@pytest.mark.parametrize("field", ["architecture", "libc", "library_sha256", "code_offset"])
def test_unknown_backend_is_never_frozen(monkeypatch, field: str) -> None:
    identity = {
        "architecture": backend._REPRODUCTION["architecture"],
        "libc": backend._REPRODUCTION["libc"],
        "library_sha256": backend._REPRODUCTION["library_sha256"],
        "code_offset": backend._REPRODUCTION["hypot_offset"],
    }
    monkeypatch.setattr(backend, "backend_identity", lambda operation: identity)
    assert backend.frozen_backend_matches()[0]
    identity[field] = "unknown"
    matches, reason = backend.frozen_backend_matches()
    assert not matches and reason


def test_exact_bracket_preserves_tiny_nonzero_component() -> None:
    tiny = float(np.nextafter(0.0, 1.0))
    assert backend.faithful_hypot(1.0, tiny, 1.0)
    assert backend.faithful_hypot(1.0, tiny, float(np.nextafter(1.0, np.inf)))
    assert not backend.faithful_hypot(1.0, tiny, float(np.nextafter(1.0, -np.inf)))
