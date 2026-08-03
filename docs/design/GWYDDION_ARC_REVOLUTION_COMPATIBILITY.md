# Gwyddion 2.71 Revolve Arc Compatibility Specification

**Specification ID:** `spmkit-gwyddion-arc-revolution-v1`<br>
**Status:** Normative pre-implementation contract<br>
**Reference:** Gwyddion 2.71<br>
**Base branch:** `feat/gwyddion-leveling-parity`<br>
**Base commit:** `c0e4fc1d3ed24d9970b2e4f6781fb2552d9527c8`<br>
**Frozen fixture:** `gwyddion-2.71-arc-revolution-directional`<br>
**Scoped maturity:** `LEVEL 3 — CROSS_VALIDATED`

This claim applies only to the source, probes, fixtures, routes, parameter
cases and tolerances declared here. It is not a universal-equivalence claim.

## 1. Purpose

This specification binds together the mathematics, exact reference control
flow, external probes, numerical fixtures, public API, tests, provenance and
scientific claims for SPMKit's Gwyddion-compatible Revolve Arc operation.

The implementation is judged against the evidence and this specification.
Neither the algorithm, tests nor specification may be silently altered merely
to obtain passing tests.

Every discrepancy must first be classified as an implementation defect, test
defect, oracle defect, reference defect, specification defect,
unsupported-domain case, or floating-point/platform effect.

## 2. Scientific identity and scope

The operation is classified as a:

> **Gwyddion 2.71-compatible, data-adaptive arc-envelope background
> estimator.**

It is not represented as:

- SPMKit's physical arc-revolution estimator;
- a classical morphological opening;
- an exact frequency cutoff;
- probe deconvolution;
- tip estimation;
- specimen-surface reconstruction;
- metrologically certified correction.

SPMKit's existing physical Arc Revolution remains an independent algorithm.
It uses a physical radius in metres, lateral pixel spacing and explicit border
policies. The compatibility operation uses radius in samples and reproduces
the declared Gwyddion 2.71 semantics.

## 3. Evidence hierarchy

Conflicts are resolved in this order:

1. Exact Gwyddion 2.71 source.
2. C probes compiled against Gwyddion 2.71.
3. Frozen JSON/NPZ numerical fixtures.
4. Official Gwyddion user documentation.
5. Mathematical and SPM-domain literature.
6. Bibliographic and general software context.

Literature defines terminology and conceptual boundaries. It does not
override observed behaviour of the frozen executable reference.

### 3.1 Executable evidence

| Artifact | SHA-256 |
|---|---|
| Gwyddion 2.71 `arc-revolve.c` | `afb19a2382b0abb46595fa3dabc126ade50ec31c91ec9c96ea2284f42d0a67ac` |
| Behaviour-probe source | `27e92376d7955f134a6d76091775dc28fe2e1ba8246936b27e2e924d3ba765f4` |
| Behaviour-probe output | `1f8ee0535ac3b0d93e3b330ec4f96b39436e4da1853f5d3ce9ba45e1f2d0eca3` |
| Directional fixture metadata | `5e037b33e04d2c95420c3e71acbf7b4bc46b8723163bfc11363e6ac083005cd2` |
| Directional fixture NPZ | `50b263b8add97950ba1ef882f96d5ee3bc35001908c47a1dbb20b9428bc3bc5e` |

### 3.2 Literature evidence

| Source | Role | SHA-256 |
|---|---|---|
| Gwyddion levelling guide | Declared user semantics | `002b1af784a1f5c441c21bbf55b670c335d5ed53eb0f6e02ab894d4911178ade` |
| Heijmans, 1995 | Mathematical morphology context | `085cede6c5cce62e214d14eb9ef624db5902f8ac512ec9626761afeedafa41eb` |
| Villarrubia, 1997 | SPM geometry and reconstruction boundary | `d50c845edf53bb6713dc8c3d72fdded1db6ba44906bbac0ee9d830eaad0dbae9` |
| Nečas–Klapetek DOI CSL | Bibliographic identity | `5f6ec95fd7eb68ec66aa8eeeaeee4284d1232e8a85cfbccb48e5d11ca20f448e` |

The Nečas–Klapetek full-text PDF is contextual and optional. Its absence does
not weaken executable numerical provenance. Dynamic publisher HTML is
explicitly non-normative.

## 4. Mathematical boundary

Mathematical morphology provides an algebraic and geometric framework for
non-linear image transformations. Villarrubia applies dilation and erosion to
SPM image simulation, surface reconstruction and tip estimation.

These sources explain why geometric envelopes matter in SPM. They do not
prove that Gwyddion Revolve Arc is a classical morphological opening.

The reference operator is data-adaptive because:

- arc amplitude depends on the global RMS;
- local mean-minus-RMS clipping modifies the working profile;
- moving sums contain historical reference-specific control flow.

Idempotence, anti-extensivity, increasingness and other morphology axioms
must not be claimed without separate proof for this exact adaptive operator.

## 5. Public input contract

The public operation accepts a real, finite, non-empty, two-dimensional
channel.

- `radius_px` is a finite real scalar.
- Boolean, complex, NaN and infinite radii are rejected.
- `1.0 <= radius_px <= 1000.0`.
- Default `radius_px` is `20.0`.
- Direction is `horizontal`, `vertical` or `both`.
- `inverted` is strictly boolean.
- Masks and non-finite field values are unsupported.
- Z units are preserved and need not be geometric lengths.
- Physical lateral ranges do not affect the numerical output.

## 6. Global scale

For all N field samples in C-order,

    mu = (1/N) sum_i f_i

and

    sigma = sqrt((1/N) sum_i (f_i - mu)^2).

This is population RMS. The arc scale is

    q = sigma / sqrt(2/3 - pi/16).

Accumulation order is part of numerical compatibility.

## 7. Discrete arc

For radius r and processing-axis resolution n,

    s = floor(min(r, n) + 1/2).

This is Gwyddion positive half-up rounding, not bankers' rounding.

For k from -s through s, with u = abs(k)/r,

    phi_r(k) =
        u^2/2 * (1 + u^2/4 * (1 + u^2/2))  when r/8 > n
        1                                      when u > 1
        1 - sqrt(1 - u^2)                     otherwise

and

    a_r(k) = q * phi_r(k).

Branch order and floating-point operation order are normative.

## 8. Historical moving sums

Local statistics reproduce Gwyddion 2.71 `moving_sums()` control flow.

Ordinary regimes agree with asymmetric truncated windows. When window size
becomes comparable to the profile, the historical `Moving a whale` branch is
normative even where it differs from a conventional window oracle.

The oversized shortcut is retained in the private primitive for source
fidelity, although it is unreachable through normal valid arc geometry.

## 9. Local clipping and horizontal envelope

At each position j, let m_j and s_j be the local mean and population RMS
produced by the historical moving-sum route.

    g_j = max(f_j, m_j - 2.5*s_j).

No undocumented variance clamp is introduced.

The horizontal background is

    H_r(f)_j = min_k (g_(j+k) + a_r(k)),

using only offsets that remain within the profile. Edges use truncated
support. There is no padding mode and no public border parameter.

## 10. Directional composition

For a field F:

    B_horizontal(F) = H_r(F)

    B_vertical(F) = transpose(H_r(transpose(F)))

    B_both(F) =
        transpose(H_r(transpose(H_r(F))))

`both` is horizontal followed by vertical. It is ordered and is not
represented as a commutative isotropic two-dimensional operator.

## 11. Inversion and corrected field

The inverted background is

    B_inverted(F) = -B(-F).

The corrected field is always

    C(F) = F - B(F).

This reconstruction identity applies to all six direction/inversion routes.

## 12. Known reference defects

### 12.1 Horizontal plus inverted corrected result

Gwyddion 2.71 computes and restores the background correctly, then returns
before writing the corrected field.

Classification: `KNOWN_REFERENCE_DEFECT`.

SPMKit policy:

- preserve the externally validated background;
- return `input - background`;
- test reconstruction explicitly;
- disclose the repaired divergence;
- never claim reproduction of the defective corrected output.

### 12.2 One-sample processing axis

The historical moving-sum branch can read before its output buffer.

Classification: `KNOWN_REFERENCE_DEFECT`.

SPMKit policy:

- do not freeze process-memory-dependent output;
- define a one-sample processed axis as identity;
- test the safe definition explicitly.

### 12.3 Dynamic publisher HTML

Immediate downloads produced different generated byte streams.

Classification: `NON_NORMATIVE_DYNAMIC_CAPTURE`.

SPMKit policy:

- use DOI CSL as canonical bibliographic identity;
- treat local full text as optional context;
- retain dynamic HTML only as provenance;
- never make its byte hash an implementation requirement.

## 13. Public API

    estimate_gwyddion_arc_revolution_background(
        channel: SPMChannel,
        radius_px: float = 20.0,
        *,
        direction: GwyddionArcDirection = "horizontal",
        inverted: bool = False,
    ) -> SPMChannel

    remove_gwyddion_arc_revolution_background(
        channel: SPMChannel,
        radius_px: float = 20.0,
        *,
        direction: GwyddionArcDirection = "horizontal",
        inverted: bool = False,
    ) -> SPMChannel

    analyze_gwyddion_arc_revolution_background(
        channel: SPMChannel,
        radius_px: float = 20.0,
        *,
        direction: GwyddionArcDirection = "horizontal",
        inverted: bool = False,
    ) -> BackgroundResult

The existing physical functions remain unchanged.

## 14. Single authoritative numerical route

The adapter exposes one internal route:

    _gwyddion_arc_result(
        data: np.ndarray,
        radius: object,
        *,
        direction: GwyddionArcDirection,
        inverted: bool,
    ) -> tuple[FloatArray, FloatArray]

It computes the background once and derives corrected data from that exact
background.

- Estimate selects background.
- Remove selects corrected.
- Analyze wraps both.
- No public route recomputes the kernel.
- No alternative correction path can drift.

## 15. Channel and structured-result contract

Returned channels preserve:

- name;
- unit;
- x and y ranges;
- acquisition direction;
- group;
- an independent metadata copy.

Kernel arrays are:

- `float64`;
- C-contiguous;
- independent of the input buffer;
- read-only;
- non-mutating.

Structured results use:

    method = "gwyddion_arc_revolution"

and record effective runtime parameters only:

    {
        "radius_px": 20.0,
        "direction": "horizontal",
        "inverted": False,
    }

Reference versions, hashes, defects, tolerances and maturity remain in
validation provenance rather than runtime parameters.

## 16. Verification model

### 16.1 Source-semantic tests

- half-up rounding;
- exact arc branch boundaries;
- population RMS;
- ordinary moving windows;
- `Moving a whale`;
- oversized shortcut;
- constant fields;
- single rows;
- large radii;
- one-sample safe definition;
- validation;
- non-mutation;
- immutability.

### 16.2 External validation

Frozen fixture: `gwyddion-2.71-arc-revolution-directional`.

The campaign validates:

- one asymmetric 5 by 7 field;
- radius 2.5;
- six background routes;
- five valid corrected routes;
- horizontal-inverted background;
- untouched defect sentinel;
- repaired SPMKit reconstruction;
- directional composition;
- artifact and array hashes.

### 16.3 Metamorphic properties

Where mathematically supported, test:

    B(F + c) = B(F) + c
    C(F + c) = C(F)
    B(alpha*F) = alpha*B(F), alpha > 0
    B_inverted(F) = -B(-F)
    B_vertical(F) = transpose(B_horizontal(transpose(F)))
    C(F) + B(F) = F

Classical morphology axioms are not requirements without independent proof
for this adaptive operator.

## 17. Scientific claim

Supported claim:

> SPMKit's declared Gwyddion-compatible Revolve Arc path is
> `LEVEL 3 — CROSS_VALIDATED` against Gwyddion 2.71 for the frozen kernels,
> fixture, six background routes, five valid corrected routes, focal cases
> and declared tolerances.

This does not establish:

- universal equivalence;
- equivalence with other Gwyddion versions;
- physical truth of the estimated background;
- specimen-surface recovery;
- tip deconvolution or reconstruction;
- metrological traceability;
- performance equivalence;
- support for masks or non-finite values.

## 18. Change control

Explicit specification review is required for changes to:

- arithmetic or accumulation order;
- radius semantics;
- edge handling;
- local clipping;
- direction order;
- inversion;
- one-sample policy;
- public defaults or limits;
- runtime metadata;
- fixtures;
- tolerances;
- scientific claims.

Tests may reveal a specification defect. They may not silently redefine the
specification.

Source, probes, implementation, tests and specification must be reconciled
and classified before changing the algorithm.

## 19. References

1. Gwyddion developers, Data Levelling and Background Subtraction, frozen
   official user documentation.
2. H. J. A. M. Heijmans, Mathematical Morphology: A Modern Approach in Image
   Processing Based on Algebra and Geometry, SIAM Review 37(1), 1–36, 1995.
   DOI: 10.1137/1037001.
3. J. S. Villarrubia, Algorithms for Scanned Probe Microscope Image
   Simulation, Surface Reconstruction, and Tip Estimation, Journal of
   Research of NIST 102(4), 425–454, 1997.
   DOI: 10.6028/jres.102.030.
4. D. Nečas and P. Klapetek, Gwyddion: an open-source software for SPM data
   analysis, Central European Journal of Physics 10(1), 181–188, 2012.
   DOI: 10.2478/s11534-011-0096-2.
5. Masaryk University institutional publication record:
   https://www.muni.cz/en/research/publications/966983
6. Gwyddion project publication record:
   https://gwyddion.net/publications/
