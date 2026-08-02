# Gwyddion Path Level Compatibility

## Status and scope

`gwyddion_path_level` records the registered Gwyddion `pathlevel` **Path
Level** tool within the frozen, finite, non-empty, full-field campaign.  The
reference is the installed `tools.so` module, SHA-256
`4711c360dd42e3e16257bf0e86d8bd41852b43d1d34540bf097736a603146237`,
Build ID `600b16d9857946609b567704b406abcc74aea698`, whose debug source matches
the frozen `pathlevel.c` SHA-256
`4c0411c73f7ca883d4d03f35b38ef81a02ea3c7688620754992cb58e8825326f`.

The evidence consists of 18 field/selection families, four thicknesses, 72
logical cases, 144 fresh external executions, and an independent Python oracle
with 72/72 bitwise-exact arrays.  This is not a universal-equivalence claim.

## Selection identity and coordinates

Path Level consumes an ordered collection of straight `GwySelectionLine`
objects, not `GwySelectionPath`.  `GwySelectionPath` belongs to unrelated
path/spline tools.  Every line is `(x0, y0, x1, y1)` in physical data-field
coordinates.  The tool maps horizontal coordinates as `x*xres/xreal` and
vertical coordinates as `y*yres/yreal`; field origin offsets do not participate.

Each endpoint is floored.  If the first Y is greater than the second Y, both
endpoints are swapped.  X endpoints and Y bounds are clamped to the field.
The active transition domain is `y0 < row <= y1`; consequently horizontal
lines are excluded.

## Numerical contract

For each ordered line object, the tool creates a start and an end change point.
They are ordered by row, then starts before ends, then object ID.  This makes
line IDs and user-supplied object order scientifically relevant.  Duplicates
and overlap retain multiplicity.

For an active line, the column at each row transition uses the source integer
formula with C signed integer division truncated toward zero.  A thickness
window is inclusive and asymmetric: `(thickness - 1)//2` samples on the lower
column side and `thickness//2` on the upper side, clamped to valid columns.
Its range is 1..128; the future public default is 1.

Row differences are accumulated as explicit scalar `current - previous`
samples in line-object and increasing-column order, then divided once by the
sample count.  The per-row differences are cumulatively summed left to right.
That correction is subtracted from every column of its row.  There is no
interpolation, mask, ROI, path, spline, or profile operation in this contract.

## Publication semantics

Gwyddion mutates and publishes the selected data field in place, with undo and
tool logging.  The future SPMKit kernel returns a new corrected array and does
not mutate its input.  This intentionally follows SPMKit immutable-return
convention; it does not claim GUI, undo, logging, or publication parity.

## Evidence and non-claims

The frozen fixture preserves external input/output records, independently
regenerated inputs/cases, oracle comparison records, physical ranges, ordered
lines, normalized endpoints, and bitwise uint64 hashes.  It covers signed zero,
line-order sensitivity, overlap, clamping, fractional coordinates, and all
four frozen thicknesses.

No claim is made for NaN or infinity, masks or ROI, spline/polyline paths,
profile extraction, volume line-leveling, `align_rows` equivalence, performance
parity, other Gwyddion builds or versions, or universal equivalence.
