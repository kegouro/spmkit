# File formats

SPM-Kit exposes a small built-in image registry and a broader capability-based
reader registry used by `load_any`. Optional adapters are named explicitly so
that dependency coverage is not mistaken for a native implementation.

| Extension or detection | Vendor/source | Images | Spectroscopy | Read | Write | Implementation | Optional dependency | Status and evidence | Limitations |
|---|---|---:|---:|---:|---:|---|---|---|---|
| `.nid` | NanoSurf classic | Yes | Yes | Yes | No | `core/io/nid.py` | None | Implemented; synthetic tests, byte tracing, and selected comparisons | Variants beyond demonstrated files remain unassessed |
| `.nhf` | NanoSurf HDF5 | Yes | No | Yes | No | `core/io/nhf.py` | `h5py` via `spmkit[hdf5]` | Experimental | Dataset layout varies; no broad public corpus |
| `.gwy` | Gwyddion | Yes | No | Yes | Yes | `core/io/gwy.py` | `gwyfile` via `spmkit[gwy]` | Implemented interoperability | Not a claim of feature parity or universal equivalence with Gwyddion |
| `.spm`; Nanoscope magic in numbered files | Bruker / Digital Instruments | Yes | No | Yes | No | `core/io/bruker_spm.py` | None | Partial; six demonstrated Nanoscope III files | Only demonstrated header/pixel variants; `.00N` family not broadly assessed |
| `.jpk-force`, `.jpk` | JPK | No | Single curve | Yes | No | `core/io/jpk.py` | None | Two profiles: direct scaling (legacy) and ForceScan 2.0 `lcd-info` indirection; synthetic fixtures + 10 real CC0 files (figshare 11637675.v3, campaign green); see `examples/jpk_forcescan2_reader_golden_path.md` | Other JPK metadata layouts (XML-era variants beyond the demonstrated set) unassessed; time not reconstructed |
| TIFF detected by JPK private tags | JPK export | No | Yes | Yes | No | `core/io/jpk_tiff.py` | `tifffile` via `spmkit[jpk]` | Experimental, content detected | Generic TIFF is not treated as JPK data |
| `.jpk-qi-data`, `.jpk-force-map`, `.jpk-qi-series` | JPK | Adapter-dependent | Yes | Yes | No | `core/io/afmformats_reader.py` | `afmformats` via `spmkit[afm]` | Experimental adapter path | Capability follows installed `afmformats` version |
| `.ibw` | Asylum / Igor Binary Wave | Adapter-dependent | Adapter-dependent | Yes | No | `core/io/afmformats_reader.py` | `afmformats` via `spmkit[afm]` | Experimental adapter path | Not a native IBW implementation on the default branch |
| `.h5` | Generic HDF5 through adapter | Adapter-dependent | Adapter-dependent | Yes | No | `core/io/afmformats_reader.py` | `afmformats` via `spmkit[afm]` | Experimental adapter path | `.h5` alone does not identify a vendor or scientific role |
| `.npz` | SPM-Kit Phantoms interchange | Yes | No | Yes | No | `core/io/npz.py` | None | Implemented for declared bundle keys | Not a generic NumPy archive reader |

## Which loader?

```python
from spmkit import load              # compact built-in image registry
from spmkit.core.io import load_any  # images or force data by capability
```

`load_any` first inspects a registered reader and then loads the requested
`image` or `force` kind. It also performs content detection for JPK TIFF and
numbered Nanoscope files.

## Contributing a fixture

Do not attach a restricted instrument file to a public issue. A fixture proposal
should state the format and instrument family, acquisition mode, expected
channels and orientation, physical units, file checksum, redistribution license,
and whether sample identity may remain private. See the
[fixture contribution template](https://github.com/kegouro/spmkit/issues/new?template=file_format_fixture.yml).
