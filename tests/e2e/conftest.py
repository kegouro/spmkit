from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from spmkit.core.io import save_gwy
from spmkit.core.models import SPMChannel, SPMData


@pytest.fixture
def real_gwy_path(tmp_path: Path) -> Path:
    pytest.importorskip("gwyfile")

    rows, cols = np.indices((5, 7), dtype=np.float64)
    texture = ((cols + 2.0 * rows) % 3.0 - 1.0) * 0.25e-9
    topography_forward = 10e-9 + 2e-9 * cols + 3e-9 * rows + texture
    topography_backward = 20e-9 - 1e-9 * cols + 1.5e-9 * rows - texture
    cpd = 0.1 + 0.01 * rows + 0.005 * cols
    x_range = 7e-6
    y_range = 10e-6

    data = SPMData(
        channels=(
            SPMChannel(
                name="Z-Axis",
                data=topography_forward,
                unit="m",
                x_range=x_range,
                y_range=y_range,
                direction="forward",
                group="Topography forward",
            ),
            SPMChannel(
                name="Z-Axis",
                data=topography_backward,
                unit="m",
                x_range=x_range,
                y_range=y_range,
                direction="backward",
                group="Topography backward",
            ),
            SPMChannel(
                name="CPD",
                data=cpd,
                unit="V",
                x_range=x_range,
                y_range=y_range,
                direction="forward",
                group="Potential forward",
            ),
        ),
        metadata={"format": "synthetic"},
    )
    return save_gwy(data, tmp_path / "image_journey.gwy")
