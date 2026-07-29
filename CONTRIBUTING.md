# Contributing to SPM-Kit

SPM-Kit was independently designed and developed by José Labarca Baeza. It
welcomes community contributions without changing the software’s authorship or
implying institutional ownership.

## Development setup

```bash
git clone https://github.com/kegouro/spmkit.git
cd spmkit
uv pip install -e ".[dev,gui,hdf5,gwy,report,test-gui]"
```

Before a pull request:

```bash
ruff check src tests
black --check src tests
mypy src
pytest
```

## Architecture rule

- `src/spmkit/core/` contains all numerical and file-format behavior.
- `src/spmkit/cli/` and `src/spmkit/gui/` only orchestrate public core APIs.
- New physical or numerical behavior needs the smallest convincing synthetic or
  analytical recovery test.
- Parser, unit, calibration, or orientation changes need traceability evidence.

## Contributing a file-format fixture

Do not upload restricted instrument files to a public issue. State:

- instrument family, software/firmware version when known, and acquisition mode;
- file extension, channel names, direction, array shape, units, and orientation;
- expected reader behavior and any independent reference;
- SHA-256 checksum and approximate file size;
- license and redistribution permission;
- whether personal, laboratory, or sample-identifying metadata was removed;
- whether sample identity may remain private.

If the file cannot be redistributed, submit metadata only and describe a lawful
private validation route. Public availability by itself is not permission to
copy the file into this repository.

## Contributing a validation comparison

Record the SPM-Kit version or commit, reference software/version, exact input,
preprocessing order, units, metrics, tolerances, output, and reference-independence
classification. Preserve failures and inconclusive results. Do not widen a
tolerance after seeing results merely to obtain a pass.

## Pull request checklist

- [ ] The change is focused and preserves the core/CLI/GUI boundary.
- [ ] Relevant tests and documented commands pass.
- [ ] Scientific scope, units, assumptions, and limitations are explicit.
- [ ] No private or restricted data is committed.
- [ ] New claims link to executable or preserved evidence.
- [ ] Authorship and acknowledgements remain distinct.
