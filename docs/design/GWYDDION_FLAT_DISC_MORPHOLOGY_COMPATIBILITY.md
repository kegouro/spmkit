# Gwyddion Flat-Disc Morphology Compatibility

## Status and scope

`gwyddion_filter_flat_disc_morphology` records Gwyddion 2.71 Filter-tool
flat-disc Opening and Closing for finite, non-empty, full-field 2D data with
mask policy fixed to ignore.  It is limited to the frozen 12-field campaign
and sizes 2, 3, 4, 5, 30 and 31.

## Reference and parameters

The reference is the audited installed Gwyddion 2.71 executable path through
`gwy_data_field_area_filter_min_max`.  `size_px` is an integer in `2..31`;
the planned public default is 5.  The kernel is a K by K digital ellipse,
where K equals `size_px`.

## Numerical semantics

The exterior policy is nearest valid edge pixel.  Minimum/erosion uses the
unreflected RLE mask and anchor `(K-1)//2`; maximum/dilation uses the rotated,
row-sorted RLE mask and anchor `K//2`.  Opening is dilation after erosion;
Closing is erosion after dilation.

The executable hierarchy is not generic C-language tie semantics.  The
audited Gwyddion 2.71 library (`libgwyprocess2.so.0.51.1`, SHA-256
`5f5b53cb544068638d1a3be8d6703345e49d5626d3fa4791106ce11bc051d3d7`,
Build ID `04187a41d4102c827e2705bb867292ba77ae37f4`) recursively constructs
Each/Even row reductions.  Its compiled MINSD/MAXSD composition sites select
the second operand on equal values, preserving signed zero.  The later RLE
aggregation uses strict comparison and retains the earlier row-major segment.

## Evidence and fixture

The external canonical reference is SHA-256
`907bd347cc8c213d1061b786b6efe5692c87ffd8be62db1f6de2bd9bc78acdbd` and
its provenance is `c3777cdcfdd868a705ef09c63a7548a5b1c0eb0b79d053e02ac2f45e9c97e5af`.
The independent oracle V2 is `bf4129fe4fd871dda3132d5457d45d0833d69e9acd5cf3bb765fc0f3a8d9792e`;
its executable reduction model is `43089668a7fe0c699093be440402c8b1b11b42dfea4eb720785241788306c543`.

The fixture stores 12 inputs, 30 masks for sizes 2..31, 72 Opening outputs,
and 72 Closing outputs.  It records kernels 30/30 and both operations 72/72
bitwise exact, max absolute difference 0, max ULP 0, signed-zero mismatches 0,
and input mutation 0.

The rejected uninitialised-kernel microprobe is invalid evidence: elliptic
fill writes active pixels only.  Approved probes zero-initialize the kernel
before filling it.

## Non-claims

This is not universal equivalence.  It excludes NaN, infinities, ROI, masks,
ASF, tip morphology, other Gwyddion versions/builds, and performance parity.
It records the audited executable path, not a claim that all C compilers lower
the source identically.
