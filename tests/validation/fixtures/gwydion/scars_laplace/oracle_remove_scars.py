"""Independent Remove Scars composition reference (Gwydion 2.71).

The compiled campaign proved that Remove Scars is exactly the source
composition of modules/process/scars.c scars_remove() (lines 172-201):
Mark Scars with the shared "scars" settings followed by
gwy_data_field_laplace_solve(field, mask, -1, 1.0) with a temporary mask
that is never user-visible.

This reference composes the two INDEPENDENT oracles in this directory:
  - oracle_mark_scars.oracle_mark_scars (independent detector)
  - oracle_laplace_discrete.oracle_laplace_discrete (mathematical solve)

It does not import any SPMKit production module, the fixture generator, or
any fixture file; it does not call Gwydion.

The composition uses the module defaults (threshold_high=0.666,
threshold_low=0.25, min_len=16, max_width=4, polarity=BOTH) which are the
values the compiled Remove Scars probe ran with.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from oracle_laplace_discrete import oracle_laplace_discrete
from oracle_mark_scars import BOTH, oracle_mark_scars

FloatArray = np.ndarray


@dataclass(frozen=True)
class RemoveScarsReference:
    """Independent composition result plus compiled-evidence comparison."""

    independent_temporary_mask: FloatArray
    mathematical_corrected: FloatArray
    # compiled evidence (supplied by the generator, never read from fixtures)
    compiled_standalone_mask: FloatArray | None
    compiled_temp_mask: FloatArray | None
    compiled_standalone_laplace: FloatArray | None
    compiled_remove_result: FloatArray | None
    mask_identity: bool
    compiled_composition_identity: bool
    temp_mask_unmutated: bool
    mark_guard_triggered: bool
    laplace: object  # LaplaceDiscreteReference
    mark: object     # MarkScarsReference


def oracle_remove_scars(
    field: object,
    *,
    compiled_standalone_mask: object | None = None,
    compiled_temp_mask: object | None = None,
    compiled_standalone_laplace: object | None = None,
    compiled_remove_result: object | None = None,
) -> RemoveScarsReference:
    """Run the independent composition; compare with compiled evidence.

    The compiled arrays are used ONLY for the identity classifications;
    the independent result is never derived from them.
    """
    mark = oracle_mark_scars(
        field,
        threshold_high=0.666,
        threshold_low=0.25,
        min_length=16,
        max_width=4,
        polarity=BOTH,
    )
    laplace = oracle_laplace_discrete(field, mark.final_module_mask)
    mask_identity = False
    comp_identity = False
    temp_unmutated = False
    c_sm = c_tm = c_sl = c_rr = None
    if compiled_temp_mask is not None and compiled_standalone_mask is not None:
        c_tm = np.ascontiguousarray(compiled_temp_mask, dtype=np.float64)
        c_sm = np.ascontiguousarray(compiled_standalone_mask, dtype=np.float64)
        if c_tm.shape == c_sm.shape:
            mask_identity = bool(np.array_equal(
                c_tm.view(np.uint64), c_sm.view(np.uint64)))
    if compiled_remove_result is not None and compiled_standalone_laplace is not None:
        c_rr = np.ascontiguousarray(compiled_remove_result, dtype=np.float64)
        c_sl = np.ascontiguousarray(compiled_standalone_laplace, dtype=np.float64)
        if c_rr.shape == c_sl.shape:
            comp_identity = bool(np.array_equal(
                c_rr.view(np.uint64), c_sl.view(np.uint64)))
    return RemoveScarsReference(
        independent_temporary_mask=mark.final_module_mask,
        mathematical_corrected=laplace.corrected_float64,
        compiled_standalone_mask=c_sm,
        compiled_temp_mask=c_tm,
        compiled_standalone_laplace=c_sl,
        compiled_remove_result=c_rr,
        mask_identity=mask_identity,
        compiled_composition_identity=comp_identity,
        temp_mask_unmutated=temp_unmutated,
        mark_guard_triggered=mark.guard_triggered,
        laplace=laplace,
        mark=mark,
    )
