---
title: Python API
description: Public SPM-Kit source API for loading image and force data, numerical analysis, export, batch processing, and reader extensions.
---

# Python API

This page describes the public contracts in source version `0.1.5.dev0`. SPM-Kit is
alpha software: pin a version or commit for reproducible work and consult the
[format matrix](FILE_FORMATS.md) before treating a reader as suitable for a particular
instrument variant.

## Install

```bash
python -m pip install spmkit                    # PyPI 0.1.2
python -m pip install "spmkit[gwy,hdf5,grains]" # selected optional features
```

The current source and GitHub-release options are listed in the
[installation guide](getting-started/installation.md).

## Load image data

`spmkit.load()` is the compact built-in image dispatcher. It currently dispatches
`.nid`, `.nhf`, `.gwy`, and SPM-Kit `.npz` bundles by extension.

```python
from spmkit import SPMChannel, SPMData, load

data: SPMData = load("scan.nid")
print(data.names)

height: SPMChannel = data["Z-Axis"]
height_backward = data.get("Z-Axis", direction="backward")

print(height.shape)          # (lines, points)
print(height.unit)           # physical data unit
print(height.x_range)        # metres
print(height.y_range)        # metres
print(height.pixel_size_x)   # metres per pixel
print(height.direction)
```

`SPMData` contains an immutable tuple of channels, file metadata, and `source_path`.
`SPMChannel.with_data(array)` returns a new channel carrying the original axes, unit,
direction, group, and copied metadata. A missing channel raises `KeyError`; SPM-Kit
does not silently guess a near-matching name.

## Inspect and load by capability

Use the capability-based path when a file may contain image or force data:

```python
from spmkit.core.io import inspect_any, load_any

info = inspect_any("measurement.nid")
print(info.format, info.kinds, info.channels)

payload, kind = load_any("measurement.nid", kind="image")
```

`load_any()` returns `(payload, kind)`. The payload is `SPMData` for `"image"` or a
`ForceVolume` for `"force"`. Content detection additionally covers demonstrated JPK
TIFF and numbered Bruker/Nanoscope files. Optional `afmformats` readers appear only
when the `afm` extra is installed. This registry is broader than `spmkit.load()`; see
the [format matrix](FILE_FORMATS.md) for evidence and limitations.

## Level and calculate roughness

Analysis functions do not mutate input channels.

```python
from spmkit.core.analysis import leveling, roughness

levelled = leveling.plane_fit(height)
# Alternatives:
# levelled = leveling.polynomial(height, order=2)
# levelled = leveling.align_rows(height, method="median")

stats = roughness.statistics(levelled)
print(stats.Sa, stats.Sq, stats.Sz, stats.unit, stats.n_points)
print(stats.Sp, stats.Sv, stats.Ssk, stats.Sku)
record = stats.to_dict()
```

Roughness expects a previously levelled spatial image. The result fields use the
ISO-style capitalization shown above. The current implementation excludes non-finite
values and centres the finite height population before calculating the metrics.

## Arc-revolution background

SPM-Kit exposes physical arc-revolution background estimation through the
public Python API:

```python
from spmkit.core.analysis import (
    estimate_arc_revolution_background,
    remove_arc_revolution_background,
)

background = estimate_arc_revolution_background(
    height,
    radius=2e-6,
    direction="both",
    side="below",
    border="nearest",
)

corrected = remove_arc_revolution_background(
    height,
    radius=2e-6,
    direction="both",
    side="below",
    border="nearest",
)
```

`radius` is expressed in metres. Channel heights must use a supported
geometric Z unit. Heights are converted internally to metres and returned in
the original unit while preserving the channel context.

`direction="horizontal"` processes rows, `"vertical"` processes columns, and
`"both"` applies horizontal followed by vertical. `side="above"` is defined
as the inversion dual of `"below"`.

The current contract accepts finite data and the `"nearest"` and `"reflect"`
border policies. Masks, CLI and Fathom exposure are not available. The
estimated background remains separately inspectable and satisfies
`corrected + background == original` within floating-point tolerance.

This implementation is LEVEL 1 — SOFTWARE_VERIFIED through synthetic tests
and an independent test-local one-dimensional oracle. Numerical equivalence
with Gwyddion has not been established.

## Sphere-revolution background

Sphere Revolution uses a true two-dimensional spherical cap in physical XY
coordinates:

```python
from spmkit.core.analysis import (
    estimate_sphere_revolution_background,
    remove_sphere_revolution_background,
)

background = estimate_sphere_revolution_background(
    height,
    radius=2e-6,
    side="below",
    border="nearest",
)

corrected = remove_sphere_revolution_background(
    height,
    radius=2e-6,
    side="below",
    border="nearest",
)
```

`radius` is expressed in metres. Geometric Z values are converted internally
to metres and returned in the channel's original unit.

The spherical footprint is circular in physical coordinates. With anisotropic
pixel spacing it can therefore appear elliptical in array-index coordinates.
This operation is genuinely two-dimensional and is not equivalent to applying
horizontal and vertical arc openings sequentially.

`side="above"` is the exact inversion dual of `"below"`. The supported border
policies are `"nearest"` and `"reflect"`. Finite data are required; masks, CLI
and Fathom exposure are not available.

The background remains separately inspectable and satisfies
`corrected + background == original` within floating-point tolerance.

This implementation is LEVEL 1 — SOFTWARE_VERIFIED through synthetic tests
and independent test-local two-dimensional oracles for both supported border
policies. Numerical equivalence with Gwyddion has not been established.

## KPFM statistics

```python
from spmkit.core.analysis import kpfm

cpd = kpfm.statistics(data["CPD"], tip_work_function=4.8)
print(cpd.mean, cpd.std, cpd.minimum, cpd.maximum, cpd.contrast)
print(cpd.work_function, cpd.work_function_unit)
```

`tip_work_function` is expressed in eV. With CPD in volts, the implementation uses
`sample_work_function = tip_work_function - mean_CPD`. This sign convention and the
channel's calibration must match the instrument workflow; SPM-Kit cannot infer them
from an arbitrary label.

## Spectral and grain analysis

```python
from spmkit.core.analysis import grains, spectral

psd = spectral.radial_psd(levelled)
fractal = spectral.fractal_dimension(levelled, q_min=None, q_max=None)
correlation_length_m = spectral.correlation_length(levelled)

segmentation = grains.detect(
    levelled,
    threshold=None,
    min_size=4,
    relative_height=0.5,
)
print(segmentation.n_grains, segmentation.mean_diameter)
print(segmentation.coverage, segmentation.density)
```

`radial_psd()` returns `q` in `1/m`. Grain detection uses SciPy, a required SPMKit dependency,
uses eight-connected components, and reports density in grains per µm². Automatic
thresholding is an algorithmic default, not a scientifically universal segmentation
rule; record or override it for a campaign.

## Force data

Force curves and force volumes are a separate domain from `SPMData` images.

```python
from spmkit.core.io import load_force

volume = load_force("curve.jpk-force")
curve = volume.curve(0)
print(volume.grid_shape, curve.position)
```

`load_force()` currently covers `.nid`, `.jpk-force`, and `.jpk`. A single curve is
wrapped as a `1 × 1` `ForceVolume`. Raw force segments preserve calibration state;
operations that require calibrated force or tip-sample separation fail explicitly if
those values have not been produced. Model choice, tip geometry, Poisson ratio,
calibration, contact detection, and fit window remain scientific inputs.

The older array-oriented mechanics API is also public in this alpha release:

```python
from spmkit.core.analysis import mechanics

curves = mechanics.extract_curves(data["Deflection"])
fit = mechanics.fit_hertz(
    curves[0],
    tip_radius=10e-9,
    poisson=0.3,
    model="sphere",
    spring_constant=0.3,
    contact_method="rov",
)
print(fit.young_modulus, fit.young_modulus_std, fit.r_squared, fit.rmse)
```

Do not treat a successful fit as evidence that the chosen contact model or calibration
is valid for the sample.

## Export

```python
from spmkit.core.export import to_csv, to_hdf5, to_json
from spmkit.core.io import save_gwy

to_csv(stats, "roughness.csv")
to_json(stats, "roughness.json")
to_hdf5(data, "scan.h5")       # requires h5py
save_gwy(data, "scan.gwy")     # requires gwyfile
```

CSV is a presentation/interchange export and does not preserve the complete source
object. HDF5 and GWY output do not establish universal lossless round-trip equivalence;
retain the original instrument file, checksums, versions, and processing parameters.

## Batch image analysis

```python
from pathlib import Path
from spmkit.core import batch

files = batch.find_files(Path("measurements"))
result = batch.process(files, channel="Z-Axis", cpd_channel="CPD", level="plane")
print(result.n_ok, result.n_failed)
result.to_csv("summary.csv")
```

`find_files()` is non-recursive and follows the compact built-in image registry.
`BatchResult.rows` retains an error string for each failed file rather than hiding it.

## Reader plugins

Reader plugins implement the versioned `Reader` protocol and register through the
`spmkit.plugins.v1` entry-point group.

```python
from pathlib import Path
from spmkit.core.plugins import DatasetInfo, register_reader

class ExampleReader:
    extensions = (".example",)

    def inspect(self, path):
        return DatasetInfo(
            path=Path(path),
            format="example",
            kinds=("image",),
            channels=(),
        )

    def load(self, path, kind=None):
        raise NotImplementedError("return an SPMData instance here")

register_reader(ExampleReader())
```

`inspect()` should be inexpensive; `load()` returns the requested data kind. Production
plugins should publish an entry point rather than relying on process-local registration.
The plugin contract is versioned, but the surrounding package remains alpha.

## Contract summary

| Concern | Public entry point | Result |
|---|---|---|
| compact image loading | `spmkit.load(path)` | `SPMData` |
| capability inspection | `inspect_any(path)` | `DatasetInfo` |
| capability loading | `load_any(path, kind)` | `(payload, kind)` |
| force loading | `load_force(path)` | `ForceVolume` |
| image preprocessing | `analysis.leveling.*`, `analysis.background.*` | new `SPMChannel` |
| numerical results | `analysis.*` | immutable result dataclasses or arrays |
| open exports | `core.export.*`, `save_gwy()` | file path/output artifact |
| extension discovery | `spmkit.plugins.v1` | registered `Reader`/`Domain` |

For end-to-end examples, continue with the [first analysis](getting-started/first-analysis.md),
[manual](user-guide.md), and [artifact contracts](ecosystem/contracts.md).
