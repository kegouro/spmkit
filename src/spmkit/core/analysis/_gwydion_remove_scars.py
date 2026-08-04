"""Production composition: Gwydion 2.71 Remove Scars.

Replicates the numerical statements of modules/process/scars.c
scars_remove() (lines 172-201): Mark Scars with the shared "scars"
settings followed by gwy_data_field_laplace_solve(field, mask, -1, 1.0)
with a temporary mask that is never user-visible.  The compiled campaign
proved the composition identities bitwise (temporary mask == standalone
Mark Scars mask; corrected == standalone Laplace result).

This module only composes the two production kernels; it does not
duplicate either algorithm and applies no extra hidden correction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from spmkit.core.analysis._gwydion_laplace import _gwydion_laplace_result
from spmkit.core.analysis._gwydion_mark_scars import _gwydion_mark_scars_result

FloatArray = np.ndarray


@dataclass(frozen=True)
class _GwydionRemoveScarsResult:
    """Every observable of the production Remove Scars composition."""

    input_snapshot: FloatArray
    effective_threshold_high: float
    effective_threshold_low: float
    effective_min_length: int
    effective_max_width: int
    polarity_enum: int
    temporary_mask: FloatArray
    mark_trace: object
    laplace_trace: object
    corrected_field: FloatArray
    delta: FloatArray
    input_mutation_evidence: bool
    temporary_mask_mutation_evidence: bool


def _gwydion_remove_scars_result(
    field: object,
    *,
    threshold_high: float = 0.666,
    threshold_low: float = 0.25,
    min_length: int = 16,
    max_width: int = 4,
    polarity: str = "both",
) -> _GwydionRemoveScarsResult:
    """Run the production Remove Scars composition (private; public wrapper
    in core.analysis.scanline)."""
    # scars.c:186-192: Mark Scars with the shared settings
    mark = _gwydion_mark_scars_result(
        field,
        threshold_high=threshold_high,
        threshold_low=threshold_low,
        min_length=min_length,
        max_width=max_width,
        polarity=polarity,
    )
    temporary_mask = mark.final_mask

    # scars.c:193: laplace_solve(field, mask, -1, 1.0); the temporary mask
    # is never mutated by the solve and is discarded afterwards (194)
    laplace = _gwydion_laplace_result(mark.input_snapshot, temporary_mask)

    corrected = laplace.corrected_field
    delta = corrected - mark.input_snapshot
    return _GwydionRemoveScarsResult(
        input_snapshot=mark.input_snapshot,
        effective_threshold_high=mark.effective_threshold_high,
        effective_threshold_low=mark.effective_threshold_low,
        effective_min_length=mark.effective_min_length,
        effective_max_width=mark.effective_max_width,
        polarity_enum=mark.polarity_enum,
        temporary_mask=temporary_mask,
        mark_trace=mark,
        laplace_trace=laplace,
        corrected_field=corrected,
        delta=delta,
        input_mutation_evidence=mark.input_mutation_evidence,
        temporary_mask_mutation_evidence=laplace.mask_mutation_evidence,
    )
