# Derivative-filter math backend verification — 2026-11-21

## Finding

The four Ubuntu 26.04 / Python 3.12 failures are a verification-platform
classification defect, not evidence of a derivative-kernel regression. The
original gate accepted every x86-64/glibc host and invented the string
`hypot@GLIBC_2.35` without resolving its implementation. This symbol version
identifies an ABI, not the library build or use of FMA.

The immutable Gwyddion 2.71 fixtures reproduce glibc's generic hypot kernel.
An independent compiled probe of the official glibc generic and FMA paths
reproduced the remote Sobel discrepancies exactly:

| Case | Flat index | Frozen/generic hexadecimal result | FMA result | ULP |
|---|---:|---|---|---:|
| C19, X08 | 16 | `0x1.a28c64ce40b45p-1` | `0x1.a28c64ce40b44p-1` | 1 |
| C19, X08 | 28 | `0x1.4c5c24e3ce012p+0` | `0x1.4c5c24e3ce013p+0` | 1 |

The cases are distinct recorded executions, with the same component witness.
Across 57 cases and both Sobel/Prewitt families (2748 magnitude values):

| Compiled route | Sobel mismatches / 1374 | Prewitt mismatches / 1374 | Maximum ULP vs frozen |
|---|---:|---:|---:|
| Generic | 0 | 0 | 0 |
| FMA | 4 | 58 | 1 |

Maximum absolute deltas are `2.220446049250313e-16` for Sobel and
`8.881784197001252e-16` for Prewitt. Both routes, local NumPy and local libm
fall within independently computed faithful binary64 brackets for all 2748
values. The FMA source path reproduces the remote outputs; that establishes
an arithmetic explanation, not remote machine-code attestation.

Primary source: [glibc e_hypot.c](https://github.com/bminor/glibc/blob/master/sysdeps/ieee754/dbl-64/e_hypot.c).
Retrieved source SHA-256: `6b221ee15e8251ab8c5825464ef6c77fb614463cc453a7edf36c2febe831d158`.
The source documents expected errors below one ULP for both paths. The
standalone finite-input diagnostic adapter preserves its attribution and LGPL
license; it is evidence tooling, never imported by the product. The full
license is [COPYING.LIB](COPYING.LIB). Source URL can evolve; the checksum
identifies the inspected revision's bytes.

## Correction and unchanged contracts

No scientific fixtures, expected arrays, hashes, generators or frozen oracles
were modified. No executable production algorithm changed.

* Sobel/Prewitt component comparisons remain unconditional and bitwise exact.
* Frozen magnitude and atan2 comparisons remain bitwise exact, eligible only
  on a verified reproduction backend identified by library SHA-256 and resolved
  function offset, architecture and libc version. The new profile is an
  observed reproduction environment, not invented historical build metadata.
* Every platform compares production magnitude bitwise with its own C `hypot`.
* Every platform also checks all 2748 production and frozen magnitudes against
  independent exact rational squared brackets: for candidate `r`, `r²` and
  its adjacent float's square must enclose exact `x²+y²`. There is no `allclose`,
  rounding of outputs, or adjustable floating tolerance. Exact roots accept
  only the exact float. Tests reject deliberately incorrect neighboring values.
* Frozen backend eligibility does not inspect operation outputs. Unknown
  library identities cannot silently become matching backends.
* Portable direction/relational tests run on every host; platform-specific
  frozen bit comparisons are explicitly separated.

This is scoped numerical verification on the preserved finite campaign, not a
universal correctly-rounded hypot guarantee, cross-platform bitwise identity,
or physical experimental validation.

## Reproduce the diagnostic

From the repository root with NumPy available:

```bash
cc -std=c11 -O2 -fPIC -ffp-contract=off -fno-fast-math -U__FP_FAST_FMA \
  -D__hypot=probe_hypot_generic \
  -c docs/validation/derivative-platform-20261121/hypot-standalone.c \
  -o /tmp/spmkit-hypot-generic.o
cc -std=c11 -O2 -fPIC -ffp-contract=off -fno-fast-math -D__FP_FAST_FMA=1 \
  -D__hypot=probe_hypot_fma \
  -c docs/validation/derivative-platform-20261121/hypot-standalone.c \
  -o /tmp/spmkit-hypot-fma.o
cc -shared /tmp/spmkit-hypot-generic.o /tmp/spmkit-hypot-fma.o \
  -o /tmp/spmkit-hypot-probe.so -lm
python docs/validation/derivative-platform-20261121/hypot-probe.py \
  --library /tmp/spmkit-hypot-probe.so --output /tmp/spmkit-hypot-report.json
python -m pytest tests/validation/test_derivative_platform.py -o addopts= -q -s
```

The archived [C probe report](c-probe-report.json) records compiler, platform,
input hash, source/artifact hashes, exact discrepancy coordinates and metrics.
No compiled executable is distributed.

Local Python 3.12 derivative family: 297 passed; Python 3.11 independently
reruns the same family. CI emits runtime backend identity and numerical maxima on
Linux/macOS and Python 3.11/3.12 before the full suite.

## Other macOS findings remain separate

Original macOS/Python 3.12 run `44933179363` had eight failures: two erroneous
x86-64/glibc assertions in derivative tests (corrected here), and six force
fixture regeneration/inventory assertions:

* `test_force_mechanics_validation.py::test_fixture_regeneration_deterministic`
* `test_force_mechanics_validation.py::test_phantom_geometry_constraints`
* `test_force_smfs_validation.py::test_fixture_regeneration_deterministic`
* `test_force_smfs_validation.py::test_fixture_inventory`
* `test_force_viscoelasticity_validation.py::test_fixture_regeneration_deterministic`
* `test_force_viscoelasticity_validation.py::test_phantom_geometry_and_time_contract`

Those independent scientific families are not fixed by weakening their hash
or numerical contracts. Their original evidence is preserved. Final remote
results must be checked separately; a green derivative characterization step
alone does not mean the complete project CI is green.
