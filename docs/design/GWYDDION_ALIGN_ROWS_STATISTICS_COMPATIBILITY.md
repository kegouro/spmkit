# Gwyddion 2.71 Align Rows statistics compatibility boundary

## Scope and evidence status

This private SPMKit kernel covers only four Gwyddion Align Rows row-shift statistics methods:

1. Median (`1`)
2. Median of differences (`2`)
3. Trimmed mean (`5`)
4. Trimmed mean of differences (`6`)

The frozen campaign contains 64 finite `float64` cases, sixteen per method.  It is evidence for this bounded domain, not a public API commitment or a claim of universal, non-finite, other-version, performance, or adapter equivalence.  The production contract is `portable_source_semantics`, represented by the frozen independent V2 oracle.  The private implementation is tested against that profile; no public `align_rows` code is changed or exposed here.

The repository fixture freezes a secondary profile, `installed_gwyddion_2_71_fast_math_profile`.  It was executed by the installed Gwyddion 2.71 module and is retained as external executable evidence, not as the production arithmetic contract.

## Source call graph

The source basis is Gwyddion 2.71 `modules/process/linematch.c` (SHA-256 `79b951a161431ba9822d8d0faba2b512107a5e4822569f78c42201f289e06604`) dispatching Align Rows to `libprocess/correct.c` (SHA-256 `bdac3ea8fcc3555f33644c84d739818c12a8cb9c104cac06ac642c77d2ddaabb`).  The final difference-method line fit uses `gwy_data_line_get_line_coeffs()` in `libprocess/dataline.c` (SHA-256 `359f8fed916eb9216441e3afea4238c7128c587b0877100e0a42f2737e8edbf4`).

The source-driven chain is:

```text
module dispatch → mask routing → oriented rows / adjacent pairs
→ estimator → row correction sequence → mean or slope normalization
→ correction application → optional input-minus-corrected background
```

## Shared input transport

`Exclude = 0`, `Include = 1`, and `Ignore = 2`.  A null mask selects every sample or pair regardless of the stored mode.  Ignore likewise discards a present mask before row orientation.  Direction `0` works on rows directly; direction `1` transposes field and mask into source-equivalent working rows, then restores the result.  The transpose is logical orientation only: the returned field preserves original shape and C-contiguous `float64` storage.

All inputs, masks, and trim fractions are finite in the frozen production domain.  The private kernel rejects invalid geometry, non-real/non-finite fields, mask shape mismatch, invalid enum values, unsupported directions, and trim fractions outside `[0.0, 0.5]`.  It never mutates its input field or mask.

## Absolute methods: Median and Trimmed mean

For an oriented row `z[r,c]` with mask `m[r,c]`:

- Include selects `m[r,c] > 0.0`.
- Exclude selects `m[r,c] < 1.0`.
- Ignore selects every `c`.

Consequently exact `0.5` is selected by both per-row Include and Exclude predicates.  The automatic minimum sample count is `floor(log(width) + 1 + 0.5)`.  Below that count, including zero and one selected samples, the estimate falls back to the global masked upper median.  The source-confirmed global Exclude fallback population uses `m <= 0.0`; this intentional distinction from the per-row Exclude predicate is retained in the portable implementation.

The median is the upper median: rank `floor(n/2)` after ordering.  Trimmed mean computes `trim = floor(fraction*n + 0.5)`, retains `[trim, n-trim)`, and falls back to upper median if trimming would leave no retained sample.  The frozen portable reduction explicitly preserves the confirmed sample sorting and binary64 accumulation order.  Every absolute row shift is then mean-centred over all oriented rows before subtraction.

## Difference methods: Median of differences and Trimmed mean of differences

For adjacent oriented rows, the candidate difference is `z[r+1,c] - z[r,c]`.

- Include requires **both** masks `> 1.0`.
- Exclude requires **both** masks `< 1.0`.
- Ignore selects every adjacent pair.

Exact `0.5` participates in Exclude pairs; exact `1.0` participates in neither joint predicate.  Below the same automatic count, including zero or one pair, an adjacent increment is `+0.0`.  Increments are cumulatively added from row zero.  The complete cumulative sequence is then levelled by the source-derived unweighted index-space least-squares line fit using every oriented row.  The corrected field is the original oriented sample minus the final correction sequence.

## Background and representation

When requested, background is computed as `input - corrected` in the confirmed float64 loop order.  The fixture requires the portable and installed background arrays to be bitwise identical for all eight requests (`504/504` elements), and it records both reconstruction relations separately.  The result record is frozen; corrected field, optional background, and correction sequence are C-contiguous `float64` arrays.

## Dual-profile divergence policy

The frozen V2 portable profile and the installed external profile agree bitwise for `61/64` corrected arrays and `3757/3888` elements.  No mismatch is silently normalized.

| Exception | Frozen classification | Policy |
| --- | --- | --- |
| `median__plateaus_signed_zero__10` | 3 signed-zero-only elements; numerical equality | No output-specific zero-sign patch. |
| `median_of_differences__irregular__11` | 64 finite nonzero elements; max abs `5.329070518200751e-15` | Preserve portable source arithmetic. |
| `trimmed_mean_of_differences__irregular__11` | Same 64-element finite build-profile scope | Preserve portable source arithmetic. |

The installed package was built with GCC 16.1.1, `-ffast-math`, associative floating-point reassociation, LTO, and package optimization flags.  The frozen installed-build diagnosis is `INSTALLED_BUILD_ROOT_CAUSE_CONFIRMED` and `V3_NOT_JUSTIFIED`: disabling associative math in an isolated source build returns the portable result, while disabling LTO or vectorization does not.  Emulating this local compiler transformation in SPMKit would overfit a build profile rather than implement portable source semantics.

## Evidence maturity and non-claims

This design records `SOURCE_CONFIRMED`, frozen external-probe evidence, and a bounded V2-oracle production contract.  Private-kernel test success establishes software evidence only for the listed fixture domain.  It does not claim SPMKit numerical verification, cross-validation, universal Gwyddion parity, non-finite equivalence, public API support, or correctness for any other Align Rows method family.  Adapter/context needs remain deliberately unimplemented; GwyCompat is unchanged in this batch.
