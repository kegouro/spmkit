# Gwyddion Median Background Compatibility

## 0. Status and normative scope

**FREEZE_AUDIT_APPROVED** applies to frozen Gwyddion 2.71 Median Background evidence.
This is a normative design specification for the next mini-batch; no production code is
delivered here. Evidence is limited to the frozen 36-case campaign, represents both rank
filter backends, does not validate an SPMKit implementation, and does not exclude errors
outside the frozen domain.

## 1. Reference identity

**SOURCE_CONFIRMED** reference software is Gwyddion 2.71. The frozen module is
Gwyddion 2.71 source `modules/process/median-bg.c`, SHA-256
`5021fff407531459ed47aff7a47e4f5b2ce2ea7df13d04ca4405f05581258729`.
The manifest records the probe, runner, oracle, campaign, and fixture identities.

## 2. User-visible operation

`median_bg` estimates a local rank-filter background and returns corrected data by
subtracting that background from input. Its radius is a pixel-sample quantity, not a
physical lateral-unit quantity.

## 3. Parameter contract

**SOURCE_CONFIRMED** radius is an integer from 1 through 1024, with default 20. Future
compatibility APIs shall use `radius_px=20` and expose no configurable border, shape, or
rank parameter. Fixture-domain inputs are finite two-dimensional `float64`; mutation is
forbidden.

## 4. Digital elliptical kernel

**SOURCE_CONFIRMED** kernel resolution is `2*radius + 1`. The active region is an
inclusive digital ellipse over pixel centres: `kernel_index + 0.5` with squared ellipse
condition `<= radius_squared`. Offsets subtract `radius` and enumerate row-major.
Cardinalities for radii 1, 2, 3, 4, 20, and 1024 are 9, 21, 37, 69, 1313, and 3297401.

## 5. Border extension

**SOURCE_CONFIRMED** exterior handling is `GWY_EXTERIOR_BORDER_EXTEND`: an exterior
sample maps to the nearest valid edge pixel. No alternate border policy belongs here.

## 6. Rank selection

The rank is `kernel_active_count//2`. The direct reference path applies when active
count is at most 25; the radixtree reference path applies when active count exceeds 25.

## 7. Background and corrected fields

For input `F` and background `B`, corrected data are `C = F - B`. Frozen outputs are
finite, C-contiguous `float64` arrays with shapes equal to the corresponding input.

## 8. Direct and radix-tree reference paths

**EXECUTABLE_EXTERNAL_REFERENCE** covers direct radii 1 and 2, and radixtree radii 3,
4, 20, and 1024. A future implementation shall match observed fields without reproducing
Gwyddion's internal radixtree structure.

## 9. External probe campaign

The campaign contains 36 logical cases and 72 executions: 36 normal and 36 ASan. All
exit codes are zero; timeouts, GLib detections, and ASan detections are zero. Normal and
ASan stdout are byte-identical in all 36 pairs. Coverage includes wide, tall, constants,
signed fields, impulses, monotonic fields, singleton dimensions, oversized radii, edges,
and corners.

## 10. Independent oracle

**INDEPENDENT_ORACLE_CONFIRMED** is a Python and NumPy oracle with no SPMKit or SciPy
import, subprocess, or Gwyddion execution. It uses `numpy.partition` rather than the
internal selection path, calculates from metadata and `input_*` before loading reference
arrays, and selects no acceptance tolerance. All frozen background and corrected arrays
are bitwise equal to their reference counterparts.

## 11. Frozen fixture

The fixture has exactly 108 arrays: `input__<case>`, `background__<case>`, and
`corrected__<case>` for each case. Background and corrected arrays are copied from the
approved external-reference arrays. Canonical array hashes use SHA-256 of `dtype.str`, a
NUL byte, comma-separated shape, a NUL byte, and C-order bytes.

## 12. Future SPMKit API contract

**FUTURE_IMPLEMENTATION_REQUIREMENT** reserves `estimate_gwyddion_median_background`,
`remove_gwyddion_median_background`, and `analyze_gwyddion_median_background`. Planned
parameters are `channel`, `radius_px=20`, and keyword-only parameters where applicable.
`BackgroundResult` shall use `gwyddion_median_background` and metadata `radius_px`,
`kernel_resolution`, `kernel_active_count`, `rank_index`, `rank_backend_reference`,
`border_policy="gwyddion_border_extend"`, and
`kernel_geometry="gwyddion_digital_ellipse"`. These are future requirements, not APIs
already present.

## 13. Acceptance contract

Background and corrected comparisons require bitwise exact `float64` equality. Output
shape must equal input; C-contiguity and finiteness are required for fixture inputs; input
mutation is forbidden. Reconstruction requires `input == background + corrected` with
absolute tolerance `1e-15` and relative tolerance `0`. No acceptance relaxation may be
introduced merely to satisfy tests. Any discrepancy must first adjudicate source, probe,
oracle, fixture, and implementation evidence.

## 14. Evidence classification

| Classification | Meaning |
|---|---|
| **SOURCE_CONFIRMED** | Frozen source establishes parameter, mask, border, rank, and subtraction semantics. |
| **EXECUTABLE_EXTERNAL_REFERENCE** | Normal and ASan Gwyddion 2.71 probe outputs. |
| **INDEPENDENT_ORACLE_CONFIRMED** | Independent NumPy oracle matches external arrays. |
| **FREEZE_AUDIT_APPROVED** | Audit approval within the frozen domain. |
| **FUTURE_IMPLEMENTATION_REQUIREMENT** | Requirement for later work, not delivered code. |
| **NON_CLAIM** | Boundary that must not be inferred from evidence. |
| **TOOLING_LIMITATION** | Non-blocking campaign tooling observation. |

## 15. Explicit non-claims

**NON_CLAIM:** the fixture does not establish behavior for matrices, radii, input
families, or Gwyddion paths outside the frozen campaign. It does not by itself establish
the behavior of a future SPMKit implementation or every Gwyddion feature.

## 16. Known tooling limitations

**TOOLING_LIMITATION:** runner compilation commands use `|| true`, so their stored status
does not preserve the original compiler exit. Its auxiliary parser also recognizes broad
`background_` and `corrected_` prefixes. These do not invalidate the campaign: both
binaries executed, all 72 processes returned, outputs were valid, stderr was empty,
normal and ASan stdout were byte-identical, and arrays and metrics were recalculated
independently.

## 17. Scientific-integrity rule

Tests judge algorithms against valid evidence; algorithms must not be deformed
merely to make tests pass.

Any discrepancy shall be adjudicated before production changes. Acceptance shall not be
relaxed for convenience. Deliberate divergences and reference defects, if evidenced,
shall be preserved explicitly. Existing generic or physical median operations shall
remain separate from this compatibility operation.

## 18. Required implementation workflow

1. Preserve this fixture and manifest unchanged before implementation.
2. Compare candidate background and corrected fields against the fixture bitwise.
3. Check dtype, shape, C-order, finiteness, input immutability, and reconstruction.
4. Adjudicate a mismatch against source, probe, oracle, and fixture evidence before
   modifying production behavior.

## 19. Artifact inventory

The manifest records the frozen module, probe source, runner, campaign summary, oracle
script, summary, source NPZ, provenance, report, log, and permanent NPZ fixture. `/tmp`
paths are ephemeral source artifacts whose identity is frozen by SHA-256.

## 20. Freeze decision

**FREEZE_AUDIT_APPROVED:** artifacts are suitable as external evidence and an independent
oracle within the explicit domain of this campaign.
