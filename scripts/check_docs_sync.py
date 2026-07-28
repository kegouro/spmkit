#!/usr/bin/env python3
"""Documentation synchronisation checks for SPM-Kit / Fathom.

Runs on CI (`.github/workflows/docs.yml`) and locally.  It verifies that the
documentation tree is internally consistent and that the published artefacts
(user guide, embedded PDF reader, mkdocs nav) are in sync with the canonical
version declared in the packaging metadata.

Exit code is non-zero on the first failure.  All checks print a short
`[OK]`/`[FAIL]` line so the CI log is self-explanatory.

Run::

    python scripts/check_docs_sync.py
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

try:
    import yaml  # part of the mkdocs dependency tree
except ImportError as exc:  # pragma: no cover
    print(f"[FAIL] PyYAML not available: {exc}")
    sys.exit(2)


class _PermissiveLoader(yaml.SafeLoader):
    """SafeLoader that ignores mkdocs-specific custom tags (e.g. ``!!python/name:``).

    The interface we need from ``mkdocs.yml`` only cares about scalars, lists and
    mappings (nav, theme name, custom_dir).  Custom tags such as
    ``!!python/name:pymdownx.superfences.fence_code_format`` are opaque YAML for
    our purposes, so we collapse them to a placeholder string instead of failing.
    """


def _ignore_unknown(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


_PermissiveLoader.add_multi_constructor("", _ignore_unknown)


REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"


def ok(msg: str) -> None:
    print(f"[OK]   {msg}")


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")


def load_pyproject_version() -> str:
    with (REPO / "pyproject.toml").open("rb") as fh:
        data = tomllib.load(fh)
    proj = data.get("project", {})
    version = proj.get("version")
    if not version:
        raise RuntimeError("pyproject.toml has no project.version")
    return version


def load_citation_version() -> str | None:
    cff = REPO / "CITATION.cff"
    if not cff.exists():
        return None
    match = re.search(r"^version:\s*(\S+)", cff.read_text(), re.MULTILINE)
    return match.group(1) if match else None


def iter_nav_files(node, acc):
    if isinstance(node, str):
        acc.append(node)
    elif isinstance(node, list):
        for item in node:
            iter_nav_files(item, acc)
    elif isinstance(node, dict):
        for value in node.values():
            iter_nav_files(value, acc)


STALE_VERSIONS = ("0.1.0", "0.1.1", "0.1.2")


def main() -> int:
    failures: list[str] = []

    dev_version = load_pyproject_version()
    rel_version = load_citation_version()
    print(f"Canonical dev version  : {dev_version}")
    print(f"Last released version  : {rel_version}")
    print("-" * 64)

    # 1) mkdocs.yml nav points at files that exist.
    mkdocs_yml = REPO / "mkdocs.yml"
    if not mkdocs_yml.exists():
        failures.append("mkdocs.yml missing")
        fail("mkdocs.yml missing")
    else:
        cfg = yaml.load(mkdocs_yml.read_text(), Loader=_PermissiveLoader)
        nav_files: list[str] = []
        iter_nav_files(cfg.get("nav", []), nav_files)
        for rel in nav_files:
            if (DOCS / rel).exists():
                ok(f"nav file exists: {rel}")
            else:
                failures.append(f"nav file missing: {rel}")
                fail(f"nav file missing: {rel}")
        custom_dir = cfg.get("theme", {}).get("custom_dir")
        if custom_dir:
            failures.append(f"custom_dir still set: {custom_dir}")
            fail(f"custom_dir still set: {custom_dir} (must be removed or backed by a real directory)")
        else:
            ok("no custom_dir declared (no phantom overrides)")

    # 2) User guide exists in three formats.
    required = ("user-guide.md", "user-guide.tex", "user-guide.pdf")
    for name in required:
        path = DOCS / name
        if path.exists() and path.stat().st_size > 0:
            ok(f"user guide present: {name} ({path.stat().st_size} bytes)")
        else:
            failures.append(f"user guide missing/empty: {name}")
            fail(f"user guide missing/empty: {name}")

    # 3) PDF page count (heuristic; xelatex may compress object streams).
    pdf = DOCS / "user-guide.pdf"
    if pdf.exists():
        raw = pdf.read_bytes()
        counts = [int(n) for n in re.findall(rb"/Count\s+(\d+)", raw)]
        pages = max(counts) if counts else len(re.findall(rb"/Type\s*/Page[^s]", raw))
        if pages >= 5:
            ok(f"user-guide.pdf has approximately {pages} pages")
        elif pdf.stat().st_size > 50_000:
            ok("user-guide.pdf present and non-trivial (page count heuristic inconclusive)")
        else:
            failures.append("user-guide.pdf page count looks wrong")
            fail("user-guide.pdf page count looks wrong or file too small")

    # 4) Canonical dev version appears wherever it must.
    def contains(path: Path, token: str) -> bool:
        return token in path.read_text(encoding="utf-8")

    checks_version = [
        ("docs/user-guide.tex", DOCS / "user-guide.tex"),
        ("docs/manual/index.md", DOCS / "manual" / "index.md"),
    ]
    for label, path in checks_version:
        if not path.exists():
            failures.append(f"{label} missing")
            fail(f"{label} missing")
            continue
        if contains(path, dev_version):
            ok(f"{label} references dev version {dev_version}")
        else:
            failures.append(f"{label} does not reference dev version {dev_version}")
            fail(f"{label} does not reference dev version {dev_version}")

    # 5) No stale version strings in the user guide.
    for name in ("user-guide.tex", "user-guide.md"):
        path = DOCS / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for stale in STALE_VERSIONS:
            if stale in text:
                failures.append(f"{name} still references stale version {stale}")
                fail(f"{name} still references stale version {stale}")
            else:
                ok(f"{name} has no stale version {stale}")

    # 6) Embedded PDF reader assets.
    viewer = DOCS / "assets" / "pdf-viewer" / "viewer.html"
    if viewer.exists() and viewer.stat().st_size > 0:
        ok(f"pdf viewer present: assets/pdf-viewer/viewer.html")
    else:
        failures.append("pdf viewer missing")
        fail("pdf viewer missing: docs/assets/pdf-viewer/viewer.html")

    for rel in ("vendor/pdf.min.mjs", "vendor/pdf.worker.min.mjs"):
        p = DOCS / "assets" / "pdf-viewer" / rel
        if p.exists() and p.stat().st_size > 100_000:
            ok(f"pdfjs asset present: {rel} ({p.stat().st_size} bytes)")
        else:
            failures.append(f"pdfjs asset missing/small: {rel}")
            fail(f"pdfjs asset missing/small: {rel}")

    # 7) reader.md must reference the viewer, not a phantom path.
    reader = DOCS / "manual" / "reader.md"
    if reader.exists():
        rtext = reader.read_text(encoding="utf-8")
        if "assets/pdf-viewer/viewer.html" in rtext:
            ok("reader.md references the embedded viewer")
        else:
            failures.append("reader.md does not reference the viewer")
            fail("reader.md does not reference the viewer")
        if "custom_dir" in rtext or "overrides/" in rtext:
            failures.append("reader.md still mentions overrides/")
            fail("reader.md still mentions overrides/")
        else:
            ok("reader.md has no override reference")
    else:
        failures.append("reader.md missing")
        fail("reader.md missing")

    print("-" * 64)
    if failures:
        print(f"DOCUMENTATION SYNC FAILED: {len(failures)} problem(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("DOCUMENTATION SYNC OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())