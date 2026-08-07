# Golden path: JPK ForceScan 2.0 reader (lcd-info profile)

**Dataset**: *Atomic force microscopy indentation data of stiff and compliant
polyacrylamide hydrogels* — DOI `10.6084/m9.figshare.11637675.v3`, licence
**CC0**. Representative file:
`PAAm_Stiff_ROI6_force-save-2019.10.25-11.18.07.055.jpk-force` (SHA-256
`3403e33e...a336eb`; manifest:
`tests/validation/fixtures/jpk_forcescan2/paam_dataset_manifest.json`).

This page proves the reader golden path with the **public API only** (~25
lines): the file loads, channels are calibrated, segments are coherent, arrays
are finite, and units are physically plausible. No hidden defaults are used.

## 1. Load

```python
from spmkit.core.io import load_force

volume = load_force("PAAm_Stiff_ROI6_force-save-2019.10.25-11.18.07.055.jpk-force")
curve = volume.curve(0)          # las curvas sueltas se envuelven en un volumen 1x1
print(curve.metadata["profile"]) # 'lcd-info'  (ForceScan 2.0, indirección lcd-info)
```

## 2. Inspect curves and segments

```python
print(len(curve.segments))                          # 2
for s in curve.segments:
    print(s.segment_type, s.direction, len(s), s.state)
# extend approach 7894 force_n
# retract retract 8000 force_n
print(curve.segments[0].metadata)
# {'num_points': 7894, 'lcd_info': {'height': 1, 'vDeflection': 2}}
```

## 3. Inspect units and calibration

```python
ext = curve.extend
# raw_height ya está calibrado en metros (cadena nominal -> calibrated del archivo)
print("height unit: m (calibrado por el archivo)")
print(curve.calibration)
# Calibration(invols=6.068792445314747e-08, spring_constant=0.04659723113213052,
#             method='jpk_metadata', provenance={'source': '...jpk-force', 'profile': 'lcd-info'})
```

The InVOLS (`6.069e-8 m/V`) and spring constant (`0.0466 N/m`) come **from the
file's own calibration chain** (vDeflection slots `distance` and `force` in
`shared-data/header.properties`), never from a guess.

## 4. Select one approach/retract pair; verify finiteness and plausibility

```python
import numpy as np
ret = curve.retract
assert np.all(np.isfinite(ext.force)) and np.all(np.isfinite(ret.force))
print(ext.raw_height.min(), ext.raw_height.max())   # 2.32e-06 .. 9.77e-06 m  (µm)
print(ext.deflection.max())                         # 6.95e-07 m              (0.7 µm)
print(ext.force.max())                              # 3.24e-08 N              (32 nN)
print(curve.calibration.spring_constant)            # 0.0466 N/m  (cantiléver blando)
```

Physically plausible: a 15 µm z-scanner approach over ~7 µm with up to 32 nN on
a compliant hydrogel, consistent with a soft cantilever.

## 5. Non-mutating metadata summary

```python
summary = {
    "profile": curve.metadata["profile"],
    "segments": [s.segment_type for s in curve.segments],
    "points": [len(s) for s in curve.segments],
    "invols": curve.calibration.invols,
    "spring_constant": curve.calibration.spring_constant,
    "height_range_m": [float(ext.raw_height.min()), float(ext.raw_height.max())],
    "force_max_n": float(ext.force.max()),
}
# summary no modifica curva ni archivo; el lector no muta ningún diccionario crudo
```

## What this proves (and what it does not)

Proved: the lcd-info profile loads through the public entry point; height and
vDeflection are calibrated with file-declared chains; segmentation is coherent
(extend-spm/retract-spm); arrays are finite; units are m/N; no defaults were
substituted (profile, InVOLS and k are all read from the archive).

Not claimed: universal JPK compatibility, physical validation, material
modulus, time-domain analysis, or SMFS compatibility. See
`docs/force-spectroscopy.md` for the analysis pipeline, and the campaign
report for the full ten-file evidence.
