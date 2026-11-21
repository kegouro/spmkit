# Ecosystem consolidation — 2026-11-21

## Recovery and history

Initial remote main: `3eba2ca7ea0d7934766f9e94838b838f8b444533`.
Selected engine baseline: `149d0e2ddc7e` (`audit/final-session-integration-20260807`),
an ancestor-preserving local integration with 23 commits beyond remote main.
The original `spmkit/` main was `726045d6ebd7`; its dirty changes were reviewed
separately. Bundles of all local refs, binary patches (working/index), untracked
path inventories and private repo/worktree metadata are retained locally in
`consolidation-recovery-20261121/`, outside the published product. Originals,
including broken historical Mac worktree pointers, remain untouched. Existing
untracked files remain at their original locations; patches do not back them up.
The public [inventory](consolidation-inventory-20261121.json) records commits,
not private dataset paths or file contents.

## Migration matrix

| Component | Source | Destination | Status / validation | Decision |
|---|---|---|---|---|
| Scientific engine and Fathom | `149d0e2` including `414b4d0` | spmkit main | Linux gates recorded below | Preserve integrated GUI and pure core boundary |
| Gwyddion leveling/filter families | `41922e7` through `a6d8084` | core public APIs and capability ledger | Frozen external/oracle campaigns; scoped tests | Recover commits without regenerating evidence |
| Force foundation, mechanics, viscoelasticity, SMFS, acquisition work | `b923409` through `b28030c` | core APIs | Synthetic recovery and external witnesses where recorded | No general physical validation claim |
| JPK ForceScan 2 calibration | `49be186` | core reader | Synthetic calibration fixtures | Preserve calibration and channel semantics |
| Execution manifests | `dd74e39` and dirty original equivalent | core export + analyze CLI | New synthetic CLI/hash/JSON tests | Recover and repair private-fixture tests and swallowed errors |
| Original dependency edits | dirty spmkit | reviewed, selective | SciPy now required by advanced kernels | Keep SciPy required; do not restore obsolete optional-SciPy policy |
| Phantoms | remote `7633112` + `622a888` | independent phantoms | 25 tests passed in merged tree | Preserve export provenance and recover campaign primitives |
| Validation | remote `2b3821b` + `f466986` | independent validation | Integration gates separate | Preserve YAML/report CLI alongside bundle/campaign lifecycle |
| Data hunter | remote `36b943c` | independent hunter | Local functional source already published | No unnecessary push |
| Denoise | non-Git experimental sandbox | retained locally | Not scientifically validated | No production migration |
| Historical pending integration | `2e6b91b` | already in main `3eba2ca` | Prior integration history | Do not duplicate |
| Sanitize / publication / presentation | `11daf88`, `372deee`, `a6e52c9` | ancestry reviewed | Included by chosen baseline | No bulk copying |
| Native IBW v5 image reader | `7c2b385` | core reader + extension registry | Synthetic units/orientation/checksum/fallback tests | Recovered limited little-endian FP32 2D family, no general IBW claim |
| KPFM/roughness/NHF hardening | selected `820df23`, `c76bb8a` | core and focused tests | SI-unit/finite-input guards and synthetic HDF5 | Preserve newer leveling; recover compatible guards |
| IBW evidence-only pilot | `e9706e8` | preserved original branch | Separate archived scientific protocol | No engine code to recover; not merged into runtime |

## Hygiene and provenance

No virtual environments, private datasets, model weights, ZIP backups, database
WAL/SHM or local reference builds are migrated. The 76.5 MB hunter ZIP is a
backup containing instrument data and generated files. The two distinct PyTorch
`.pth` archives have no independently established redistribution/validation
manifest; they were inspected as ZIP containers without unpickling and excluded.
No Git LFS storage is needed for the selected package. Frozen test fixtures and
public documentation assets remain versioned with their source licenses.
The public NSFopen 2.2.4 spectroscopy example is accompanied by the Nanosurf AG
MIT notice and SHA-256 provenance. Production never loads validation fixtures.
Validation's historical ELF helpers/wheels are evidence, not runtime dependencies.

## Verification scope

Executed Linux x86_64 verification:

| Gate | Result |
|---|---|
| Python 3.12.13 full non-GUI suite, consolidated tree | 2244 passed, 80 skipped, 23 warnings; 454.29 s |
| GUI isolated offscreen suite | 174 passed, 8 skipped in 34 files; zero accepted teardown crashes |
| Ruff | passed |
| Black 26.5.1 | passed; recovered Python formatting normalized with identical AST; frozen oracle/generator bytes preserved and excluded from formatter |
| mypy 2.3.0 | passed, 186 source files |
| Wheel and sdist | built; capability resource included; validation fixtures and NSFopen MIT notice in sdist |
| Clean wheel-only environment | installed; CLI help/version and numerical Sa/Sq/Sz smoke passed without Qt imports |
| Documentation | sync, visual contract, strict MkDocs build and 8501 internal references across 73 pages passed |
| Phantoms merged tree | 25 passed |
| Validation merged tree | 260 passed, 11 skipped; Ruff and package builds passed |
| Black-box ecosystem smoke | six cases executed through public CLI; results remain TODO-SCIENTIFIC-DECISION |

The 23 warnings include deliberate all-NaN robustness cases and dependency
warnings; skipped tests include unavailable external helpers and private/reference
inputs. They are not counted as validated capabilities. GUI legacy-window cases
are explicitly skipped under the repository's Linux teardown workaround.
The first baseline run used the original editable environment (2243 passed,
81 skipped); the decisive run above imported the isolated consolidation checkout.

Secondary published heads: Phantoms `09aaee4870772c14be70cbd0e1f31435e177578b`;
Validation `89ab513` (follow-up CI fix after `6f70d0c`). Data Hunter remote
`36b943c` already contains all recoverable local functional changes.

The oldest supported Python remains 3.11. NumPy 2.5.1 requires Python >=3.12;
constraints select NumPy 2.4.6 / SciPy 1.17.1 on Python 3.11 and the frozen
NumPy 2.5.1 / SciPy 1.18.0 combination on 3.12+. CI now exercises Linux and
macOS with both Python versions. A resolved dependency set is not itself proof
that every numerical witness is platform-independent. Software tests,
synthetic numerical recovery and frozen external comparisons are distinct.
External references are not freshly executed merely because fixture tests pass.
Linux x86_64 was available; macOS and Apple Silicon execution remain pending.
This remains `0.1.5.dev0`, not a stable 1.0 release.

See [portable setup](../getting-started/macos.md), [scientific status](../scientific-status.md)
and the [capability ledger](../parity/CAPABILITY_LEDGER.md).

## Final recovery supplement

The final ancestry audit recovered the native IBW v5 reader and compatible
Slice B KPFM/roughness/NHF guards. Reader/plugin/architecture and affected
scientific module tests passed: 41 passed, 2 skipped on Python 3.12;
36 passed on Python 3.11 for IBW/KPFM/roughness/NHF. mypy now covers 187
source files. The SMFS result annotation now honestly permits absent fits for
invalid short windows, matching existing runtime behavior; no algorithm changed.
The full-suite counts above describe the pre-supplement baseline; focused
post-supplement results are recorded separately, without inflating the total.

Validation's first remote CI run exposed a missing optional campaign dependency
in its test environment. Its follow-up workflow installs `[campaign]` and keeps
all tests; none were removed or marked skipped to conceal the failure.
