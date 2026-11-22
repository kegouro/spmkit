"""Run with SPM-Kit and spmkit-phantoms available. Output units are nN."""

import csv
import sys

import numpy as np
from spmkit_phantoms.corruptions import AdditiveGaussianNoise
from spmkit_phantoms.surfaces import step_surface

from spmkit.core.analysis.force_steps import measure_force_step
from spmkit.core.models import ForceSegment


def main():
    out = csv.writer(sys.stdout)
    out.writerow(["target_nN", "offset_samples", "window_samples", "rows", "bias_nN", "rmse_nN"])
    k = 0.2
    z = np.arange(80) * 1e-9
    for target in (-2.0, 0.0, 2.0):
        # Interpret the generated row as imposed cantilever deflection for this test.
        phantom = step_surface((256, 80), 80e-9, 256e-9, target * 1e-9 / k)
        observed = AdditiveGaussianNoise(0.1e-9 / k).apply(phantom, np.random.default_rng(20261122))
        traces = 0.4 * z + k * observed.observed_z
        for offset in (-1, 0, 1):
            for window in (4, 8, 16):
                errors = []
                for force in traces:
                    seg = ForceSegment(
                        "extend", "approach", z, force / k, state="force_n", force=force
                    )
                    estimate = measure_force_step(seg, 40 + offset, window)
                    errors.append(estimate.delta_force_n * 1e9 - target)
                out.writerow(
                    [
                        target,
                        offset,
                        window,
                        len(errors),
                        np.mean(errors),
                        np.sqrt(np.mean(np.square(errors))),
                    ]
                )


if __name__ == "__main__":
    main()
