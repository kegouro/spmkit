# Gwyddion 2.71 Sphere Revolution Compatibility Specification

## 1. Status and scope

This document establishes the normative design specification for SPMKit's compatibility with Gwyddion 2.71's 2D Revolve Sphere background leveling operation.

Current Status: Normative Design Specification (Implementation Pending).

The primary objective is to reproduce the exact, observable numerical semantics of Gwyddion 2.71's ``sphere-revolve`` module within SPMKit.

Scope boundaries:
- Direct external reference scope (direct external reference): The normal route (`inverted=False`).
- Derived external reference scope (derived external reference): Inverted background evaluated via the exact mathematical dual `-B(-F)` using normal reference executions on negated inputs.
- Safe deliberate divergence scope (safe deliberate divergence): Inverted corrected field evaluated as `F - B_inv(F)` to guarantee complete reconstruction identity without inheriting upstream memory corruption bugs.
- Universal equivalence is explicitly excluded. Parity claims apply strictly to the frozen test suite and external validation fixtures.

| Capability | Evidence class | Planned SPMKit behavior |
|---|---|---|
| Normal background | Direct external reference | Reproduce Gwyddion 2.71 numerical outputs |
| Normal corrected | Direct external reference | Reproduce Gwyddion 2.71 numerical outputs |
| Inverted reference wrapper | Frozen reference defect | Excluded due to upstream memory corruption crash |
| Inverted background | Derived external reference | Reproduce dual `-B_normal(-F)` using negated inputs |
| Inverted corrected | Safe deliberate divergence | Evaluate `F - B_inv(F)` to ensure input reconstruction |
| Physical Sphere Revolution | Independent physical model | Preserved completely intact without modification |

## 2. Separation from physical Sphere Revolution

SPMKit currently provides `estimate_sphere_revolution_background`, which models a physical 2D spherical contact tip over real surface topographies using physical SI units (metres), anisotropic lateral pixel dimensions (`dx`, `dy`), morphological opening operations, and physical border modes (`nearest`, `reflect`).

The Gwyddion 2.71 compatibility operation defined herein uses dimensionless pixel-sample radii (`radius_px`), data-adaptive RMS scaling (`q`), and historical C-array index truncation.

> The two operations remain separate because their parameter semantics, geometry, scaling, and evidence contracts are not equivalent.

The existing physical Sphere Revolution implementation (`estimate_sphere_revolution_background`, `remove_sphere_revolution_background`, `analyze_sphere_revolution_background`) and its test suite shall remain completely intact and unmodified.

## 3. Proposed public API

The public API for Gwyddion Sphere Revolution compatibility shall provide three functions in `spmkit.core.analysis.background`:

```python
estimate_gwyddion_sphere_revolution_background(
    channel: SPMChannel,
    radius_px: float = 20.0,
    *,
    inverted: bool = False,
) -> SPMChannel
```

```python
remove_gwyddion_sphere_revolution_background(
    channel: SPMChannel,
    radius_px: float = 20.0,
    *,
    inverted: bool = False,
) -> SPMChannel
```

```python
analyze_gwyddion_sphere_revolution_background(
    channel: SPMChannel,
    radius_px: float = 20.0,
    *,
    inverted: bool = False,
) -> BackgroundResult
```

Method string string:

`gwyddion_sphere_revolution`

Parameters dictionary:

```python
{
    "radius_px": float(radius_px),
    "inverted": bool(inverted),
}
```

Public imports will be exported in `spmkit.core.analysis` and `spmkit` upon completion of Block D of the implementation sequence.

## 4. Input and parameter contract

The input channel and parameters must adhere to the following contract:
- Input channel data must be a two-dimensional, finite, real, non-empty `float64` array.
- All internal numerical calculations must use IEEE-754 `numpy.float64` double precision.
- `radius_px` must be a real, finite scalar in the inclusive range `1.0 <= radius_px <= 1000.0`.
- Boolean values passed as `radius_px` must be rejected with `TypeError`, matching SPMKit's `_validated_gwyddion_radius_px` contract.
- `inverted` must be a boolean. Non-boolean values (e.g. integers or strings) must be rejected with `TypeError`.
- `radius_px` represents a sample count along pixel grid axes and is completely independent of physical lateral metadata (`xreal`, `yreal`, `dx`, `dy`).
- Input channels and arrays must never be mutated in place.
- Private array outputs must be C-contiguous `numpy.float64` arrays with `flags.writeable = False`.
- Public SPMChannel metadata, Z units, and spatial context must be preserved using `channel.with_data(...)`.

## 5. Global normalization

Let $F$ be a 2D data field of dimensions $y_{\mathrm{res}} \times x_{\mathrm{res}}$ containing $N = y_{\mathrm{res}} \cdot x_{\mathrm{res}}$ samples.

Global mean $\bar F$ is calculated using a serial C-order sum over double-precision values:

$$
\bar F = \frac{1}{N} \sum_{p=0}^{N-1} F_p
$$

Global population RMS is calculated in a second serial C-order pass:

$$
\operatorname{RMS}(F) = \sqrt{\frac{1}{N} \sum_{p=0}^{N-1} (F_p - \bar F)^2}
$$

The global scaling parameter $q$ is defined as:

$$
q = \frac{\operatorname{RMS}(F)}{\sqrt{5/6}}
$$

Key requirements:
- The divisor $N$ uses the full population count.
- Calculation requires two explicit serial passes to preserve exact accumulation order.
- A constant input field yields $\operatorname{RMS}(F) = 0.0$ and $q = 0.0$.
- `np.std()` must not be used as the normative definition due to variance in accumulation order.

## 6. Discrete sphere construction

The integer sphere radius $s$ in samples, kernel size $n$, and local filter half-width $k$ are derived via `GWY_ROUND` (`floor(val + 0.5)`):

$$
s = \left\lfloor \min(r, x_{\mathrm{res}}) + 0.5 \right\rfloor
$$

$$
n = 2s + 1
$$

$$
k = \left\lfloor \frac{s}{2} \right\rfloor
$$

For indices $i, j \in [0, s]$, normalized coordinate offsets are defined as:

$$
u = \frac{i}{r}, \qquad v = \frac{j}{r}, \qquad \rho^2 = u^2 + v^2
$$

The dimensionless sphere height $z$ is evaluated via the normal branch when $r / 8 \le x_{\mathrm{res}}$:

$$
z = \begin{cases} 1 - \sqrt{1 - \rho^2}, & \rho^2 \le 1 \\ 2, & \rho^2 > 1 \end{cases}
$$

When $r / 8 > x_{\mathrm{res}}$, the very-flat branch polynomial is evaluated:

$$
z = \frac{\rho^2}{2} \left[ 1 + \frac{\rho^2}{4} \left( 1 + \frac{\rho^2}{2} \right) \right]
$$

The scaled sphere kernel $S$ is obtained by quadrant-symmetric assignment and scaling:

$$
S = -q z
$$

Key requirements:
- Quadrant symmetry assigns identical $z$ to $(s-i, s-j)$, $(s-i, s+j)$, $(s+i, s-j)$, and $(s+i, s+j)$.
- The parameter $x_{\mathrm{res}}$ is the sole dimension passed to Gwyddion's `make_sphere`.
- On non-square rectangular grids ($x_{\mathrm{res}} \ne y_{\mathrm{res}}$), this creates an intentional asymmetry under matrix transposition.
- This historical asymmetry is required for exact Gwyddion 2.71 compatibility and must not be "corrected" by using $\min(x_{\mathrm{res}}, y_{\mathrm{res}})$.

## 7. Local mean and RMS semantics

For filter size $k = s // 2 > 0$, local moving windows use asymmetric negative and positive extensions:

$$
k_- = (k - 1) // 2, \qquad k_+ = k // 2
$$

For each pixel $(r, c)$, the window bounds are truncated at image borders:

$$
r_{\mathrm{start}} = \max(0, r - k_-), \qquad r_{\mathrm{stop}} = \min(y_{\mathrm{res}} - 1, r + k_+)
$$

$$
c_{\mathrm{start}} = \max(0, c - k_-), \qquad c_{\mathrm{stop}} = \min(x_{\mathrm{res}} - 1, c + k_+)
$$

Properties:
- Truncated window support at boundaries without zero-padding.
- Window sums are normalized by the effective pixel count in the window.
- Odd $k$ yields a symmetric centered window; even $k$ places one extra sample to the right and bottom.

Local mean $\mu_{\mathrm{local}}$ is the window arithmetic mean.

Local RMS $\sigma_{\mathrm{local}}$ for $k > 1$ is calculated as:

$$
\sigma_{\mathrm{local}} = \sqrt{\max\left(E[F^2] - E[F]^2, 0\right)}
$$

Special filter size semantics:
- When $k = 0$: $\mu_{\mathrm{local}} = F$ (unfiltered copy) and $\sigma_{\mathrm{local}} = F$ (unfiltered copy).
- When $k = 1$: $\mu_{\mathrm{local}} = F$ (unfiltered copy) and $\sigma_{\mathrm{local}} = 0.0$.
- SPMKit reproduces these exact numerical outputs.
- SPMKit does not emit Gwyddion's `GwyProcess-CRITICAL` GLib diagnostic warnings.

Note: The independent Python oracle uses direct window summation loops, while Gwyddion uses 1D rolling sums. Both yield identical floating-point results within sub-ULP rounding tolerances.

## 8. Outlier-trimmed field

The outlier-trimmed field $T$ is computed element-by-element as:

$$
T = \max\left(F, \mu_{\mathrm{local}} - 2.5 \sigma_{\mathrm{local}}\right)
$$

For $k = 0$, where $\mu_{\mathrm{local}} = F$ and $\sigma_{\mathrm{local}} = F$, this simplifies to:

$$
T = \max(F, -1.5 F)
$$

$T$ represents an intermediate trimmed field and is not the final background.

## 9. Two-dimensional envelope

The background $B_{ij}$ at pixel $(i, j)$ is extracted as the lower envelope of $T$ relative to the scaled sphere kernel $S$:

$$
B_{ij} = \min_{\substack{a \in [-s, s], b \in [-s, s] \\ (i+a, j+b) \text{ valid} \\ S_{s+a, s+b} \ge -q}} \left[ T_{i+a, j+b} - S_{s+a, s+b} \right]
$$

Since $S = -q z$, this is equivalent to:

$$
B_{ij} = \min \left[ T_{i+a, j+b} + q z_{s+a, s+b} \right]
$$

Key requirements:
- Full 2D minimization loop over valid kernel offsets.
- Support points with $S < -q$ are excluded from minimization.
- Truncated boundary support without padding.
- Normal corrected field: $C = F - B$.

## 10. Radius-one historical semantics

Executable probe evidence confirms:
- For $r = 1.0$, $s = 1$, $n = 3$, and $k = 0$.
- Gwyddion 2.71 emits two GLib critical diagnostic warnings (`size > 0` assertion failures) because $k = 0$.
- The Gwyddion execution continues normally, returning exit code 0, finite outputs, and exact reconstruction.
- SPMKit preserves the exact numerical output ($T = \max(F, -1.5F)$ passed through the 2D envelope) while executing cleanly without diagnostics.

## 11. Constant-field q=0 semantics

For constant input fields ($F_{ij} = c$):
- Global RMS is $0.0$, yielding $q = 0.0$.
- The scaled sphere kernel $S$ consists entirely of zeros.
- The condition $S \ge -q$ ($0.0 \ge 0.0$) holds for all kernel positions.
- Background $B_{ij} = c$ and corrected $C_{ij} = 0.0$.
- All outputs are finite and exhibit exact zero error.

## 12. Inverted reference execution defect

### EXECUTABLE_CONFIRMED_REFERENCE_DEFECT

Executable campaign evidence across 15 inverted reference cases confirms:
- In Gwyddion 2.71's `sphere-revolve.c`, when `inverted=TRUE`, line 320 executes `gwy_object_unref(field); field = invfield;`.
- At line 328, `gwy_data_field_subtract_fields(args->field, field)` uses `args->field` which was not reassigned to `invfield`.
- 15 out of 15 inverted normal cases crashed with exit code 139 (SIGSEGV).
- 15 out of 15 inverted ASan cases crashed with exit code 134 (SIGABRT).
- Probe output recorded `execute_started=1` but `execute_returned=0`.
- The crash occurs inside `gwy_data_field_check_compatibility()` due to a read of unallocated memory during final subtraction.
- ASan output did not emit the literal string `heap-use-after-free`, so that specific string is not used as an exact diagnostic tag.
- Gwyddion 2.71 provides no valid reference output for `inverted=TRUE`.
- The reference `inverted=TRUE` C wrapper cannot serve as a valid numerical oracle.

## 13. Safe inverted semantics in SPMKit

To provide mathematically sound inversion without inheriting reference crashes, SPMKit defines safe inverted semantics:

Inverted Background Dual:

$$
B_{\mathrm{inv}}(F) = -B_{\mathrm{normal}}(-F)
$$

Inverted Corrected Field:

$$
C_{\mathrm{inv}}(F) = F - B_{\mathrm{inv}}(F)
$$

Evidence hierarchy:
- Direct external reference: Normal route (`inverted=False`).
- Derived external reference: Inverted background $B_{\mathrm{inv}}(F) = -B_{\mathrm{normal}}(-F)$, verified by running Gwyddion's normal C kernel on 10 explicitly negated inputs (`input_negation_max_abs = 0.0`, $q$ difference $= 0.0$, dual reconstruction max abs error $= 8.88 \times 10^{-16}$).
- Safe deliberate divergence: Inverted corrected field $C_{\mathrm{inv}}(F) = F - B_{\mathrm{inv}}(F)$, ensuring exact reconstruction identity without undefined behavior.

## 14. Independent oracle evidence

An independent Python oracle (`/tmp/spmkit_gwyddion_sphere_oracle.py`) evaluated 20 valid cases (10 original normal, 10 negated normal):
- Implemented in pure Python 3 and NumPy without SciPy or SPMKit imports.
- Evaluated using direct 2D window loops.
- Max $q$ absolute error: `0.0`.
- Max background absolute error: `4.4408920985006262e-16`.
- Max background ULP error: 2 ULP.
- Max corrected absolute error: `8.8817841970012523e-16`.
- Max reconstruction error: `8.8817841970012523e-16`.
- All outputs 100% finite.
- Large raw corrected ULP (`4377498837804122113`) resulted from comparing `-4.44e-16` against positive zero `0.0`.
- Raw ULP near zero is not an acceptance criterion.

## 15. Acceptance criteria

Numerical acceptance criteria for external validation fixtures:

```text
background_max_abs_error = 5e-14
corrected_max_abs_error = 5e-14
reconstruction_max_abs_error = 5e-14
rtol = 0
```

Explanation:
- Provides a safety margin above the observed maximum numerical discrepancy (`8.88e-16`).
- Matches the tolerance scale established for Gwyddion Revolve Arc compatibility.
- Applies absolute comparison (`atol = 5e-14`, `rtol = 0`).
- ULP distance is logged as a diagnostic metric only.
- Applies to frozen external validation fixtures and does not constitute universal equivalence.

## 16. Planned implementation architecture

Implementation will add one private module and modify two existing files:
- New file: `src/spmkit/core/analysis/_gwyddion_sphere_revolution.py`
- Modify: `src/spmkit/core/analysis/background.py`
- Modify: `src/spmkit/core/analysis/__init__.py`

Private API signatures in `_gwyddion_sphere_revolution.py`:

```python
_gwyddion_sphere_background(
    data: FloatArray,
    radius: float,
) -> FloatArray
```

```python
_gwyddion_sphere_result(
    data: FloatArray,
    radius: float,
    *,
    inverted: bool = False,
) -> tuple[FloatArray, FloatArray]
```

```python
_gwyddion_sphere_corrected(
    data: FloatArray,
    radius: float,
    *,
    inverted: bool = False,
) -> FloatArray
```

Architecture rules:
- `_gwyddion_sphere_background` computes authoritative normal background.
- `_gwyddion_sphere_result` centralizes inversion dual and corrected calculation.
- `_gwyddion_sphere_corrected` delegates to `_gwyddion_sphere_result`.
- Public adapters delegate to `_gwyddion_sphere_result`.
- No duplication of algorithm logic.
- No sharing of private helper functions with Arc Revolution in this phase.
- Existing physical Sphere Revolution code remains completely untouched.

## 17. Required tests

Required test matrix:

### Private/core tests (`tests/core/test_gwyddion_sphere_revolution_background.py`)
- `test_default_radius_is_20`
- `test_radius_boundary_1_accepted`
- `test_radius_boundary_1000_accepted`
- `test_invalid_nonfinite_radius_rejected`
- `test_invalid_range_radius_rejected`
- `test_bool_radius_rejected`
- `test_float64_conversion`
- `test_c_contiguous_output`
- `test_readonly_array_output`
- `test_input_array_not_mutated`
- `test_constant_field_zero_corrected`
- `test_radius_one_semantics`
- `test_very_flat_branch_execution`
- `test_rectangular_asymmetry`
- `test_safe_inversion_dual_identity`
- `test_reconstruction_identity`
- `test_private_result_agreement`

### Public adapter tests (`tests/core/test_gwyddion_sphere_revolution_background.py`)
- `test_estimate_delegates_correctly`
- `test_remove_delegates_correctly`
- `test_analyze_returns_background_result`
- `test_method_string_is_gwyddion_sphere_revolution`
- `test_parameters_dict_contents`
- `test_channel_context_preservation`
- `test_physical_sphere_api_unchanged`
- `test_public_private_numerical_agreement`

### External validation tests (`tests/validation/test_sphere_revolution_vs_gwyddion.py`)
- `test_gwyddion_sphere_direct_normal_background_matches_gwyddion_2_71`
- `test_gwyddion_sphere_direct_normal_corrected_matches_gwyddion_2_71`
- `test_gwyddion_sphere_negated_normal_background_matches_gwyddion_2_71`
- `test_gwyddion_sphere_derived_inverted_background_matches_gwyddion_2_71`
- `test_gwyddion_sphere_safe_inverted_corrected_matches_gwyddion_2_71`
- `test_gwyddion_sphere_reconstruction_identity`
- `test_gwyddion_sphere_reference_inverted_failure_evidence_is_documented`
- `test_gwyddion_sphere_public_result_matches_gwyddion_2_71`
- `test_gwyddion_sphere_fixture_hashes_are_stable`

## 18. Fixture and provenance requirements

Fixture location:
`tests/validation/fixtures/gwyddion/sphere_revolution/`

Artifacts:
- `gwyddion_2_71_sphere.npz` (uncompressed NPZ containing input, reference background, reference corrected, and derived arrays).
- `gwyddion_2_71_sphere.json` (JSON metadata with SHA-256 hashes, canonical array hashes, source/probe/runner/oracle hashes, case metadata, acceptance tolerances, and reference execution status).

Requirements:
- Distinguish direct normal cases, negated-normal cases, derived inverted arrays, and failed original inverted executions.
- Do not store dummy or synthetic arrays for crashing reference cases.

## 19. Scientific claim boundaries

Claim status before implementation:
- Design specified and normative contract established.
- External reference and independent oracle characterized.
- SPMKit implementation pending.

Claim status after implementation and validation:
- Normal route: Level 3 CROSS_VALIDATED within external fixture.
- Inverted background: Derived external cross-validation (`-B_normal(-F)`).
- Inverted corrected: Safe deliberate divergence (`F - B_inv(F)`).
- Universal equivalence across arbitrary inputs or platforms is not claimed.
- Physical Sphere Revolution maintains its independent maturity and physical claims.

## 20. Explicit non-goals

The following non-goals are explicitly established:
- Do not replace or modify physical Sphere Revolution.
- Do not modify or patch upstream Gwyddion 2.71 C source code.
- Do not reproduce upstream C memory corruption crashes.
- Do not reproduce GLib warning messages.
- Do not use physical units (metres, nanometres) in Gwyddion compatibility APIs.
- Do not add mask support in this phase.
- Do not add border padding or extension policies.
- Do not add direction parameters (`direction` is for Arc, not Sphere).
- Do not expand radius range beyond `1.0 <= radius_px <= 1000.0`.
- Do not perform premature performance optimization before closing parity.
- Do not parallelize execution loops.
- Do not refactor Arc Revolution implementation.
- Do not claim universal numerical equivalence beyond frozen fixtures.

## 21. Provenance ledger

| Artifact | SHA-256 | Role |
|---|---|---|
| `sphere-revolve.c` | `4218cd4e303634c610e9be5f18656d12715c68df95a9b30930b33232b3d8cbe9` | Gwyddion 2.71 reference C module source |
| `sphere_revolve_behavior_probe.c` | `97248b51df742937ed5dc0a975b8b1ca08b1b6eeb5add95eda4526118337b188` | C probe source (schema_version 2, 35 cases) |
| `run_sphere_probe_campaign.sh` | `d673393126833277bda41c77403f1dbaf5dc965d6d8b63ee73994238bec8f7a7` | Campaign runner script v2 |
| `sphere_oracle.py` | `f1598e5f7cd0e173ec72ea928e270038ac8ab5f4c61d57b31a60373e50d40e4b` | Independent Python oracle script |
| `precision_audit.py` | `58f1acd0d3c3d644c93adcc7c754889e883726976341695e974d4c09a34f72e4` | Floating-point precision audit script |
| `implementation_dossier.md` | `fd9e83b28027a130025528130f96d3e4f4f03bdc792830666861ec335efef3a2` | Implementation dossier report |

## 22. Implementation sequence

Execution order:
1. Block A: Create normative specification `docs/design/GWYDDION_SPHERE_REVOLUTION_COMPATIBILITY.md` (completed in this step).
2. Block B: Implement private numerical kernel `src/spmkit/core/analysis/_gwyddion_sphere_revolution.py`.
3. Block C: Implement private unit tests `tests/core/test_gwyddion_sphere_revolution_background.py`.
4. Block D: Implement public adapters in `src/spmkit/core/analysis/background.py` and `__init__.py`.
5. Block E: Implement public API unit tests in `tests/core/test_gwyddion_sphere_revolution_background.py`.
6. Block F: Create frozen external validation fixtures in `tests/validation/fixtures/gwyddion/sphere_revolution/`.
7. Block G: Implement external validation tests in `tests/validation/test_sphere_revolution_vs_gwyddion.py`.
8. Block H: Update documentation files (`docs/api.md`, `docs/scientific-status.md`, `docs/validation/index.md`).
9. Block I: Run focal regression test suite and static type checking.
10. Block J: Run global regression test suite (`pytest`).
11. Block K: Atomic git commit and push.

Each block must be verified before proceeding to the next block.
