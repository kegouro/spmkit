# First analysis

This path uses an experimental instrument file you are permitted to analyze.
SPM-Kit does not bundle redistributable experimental data with the package.

## 1. Inspect before computing

```bash
spmkit info scan.nid
```

The command reports the channels, scan direction, array shape, physical unit and
field of view. Copy the exact channel name; commands do not guess when the name
is wrong.

## 2. Run the declared pipeline

```bash
spmkit analyze scan.nid --channel Z-Axis --level plane --output results/
```

For `scan.nid`, this creates:

```text
results/
├── scan_roughness.csv
├── scan_roughness.json
├── scan_kpfm.csv       # only when the configured CPD channel exists
└── scan_kpfm.json      # only when the configured CPD channel exists
```

`--level plane` subtracts a least-squares plane before computing Sa, Sq, Sz,
Ssk and Sku. Report that preprocessing choice with the result. Use
`--level none` only when an unlevelled height field is scientifically intended.

## 3. Check one result interactively

```bash
spmkit gui scan.nid
```

Fathom inspects the file, selects the compatible route and opens the relevant
perspective. In the Image perspective, verify channel, unit, field of view and
leveling before exporting a figure.

## 4. Preserve enough context

Keep the original file outside version control when its license or consent does
not permit redistribution. Preserve alongside the results:

- the file checksum and lawful source;
- `spmkit --version` and Python version;
- command or Fathom project/recipe;
- channel name and scan direction;
- field of view and physical units;
- preprocessing and model parameters;
- result files and interpretation limits.

An exported CSV without its channel, units and preprocessing is not a
reproducible analysis.

[:material-arrow-left: Installation](installation.md) ·
[:material-arrow-right: Fathom quick start](fathom-quick-start.md)
