#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    print(f"[FAIL] PyYAML not available: {exc}")
    sys.exit(2)


class _PermissiveLoader(yaml.SafeLoader):
    pass


def _ignore_unknown(loader: Any, _tag_suffix: str, node: Any) -> Any:
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


_PermissiveLoader.add_multi_constructor("", _ignore_unknown)

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"
MANUALS = (DOCS / "user-guide.md", DOCS / "user-guide.tex")
GITHUB_RELEASE = "0.1.4"
PYPI_RELEASE = "0.1.2"
EXPECTED_TOP_NAV = [
    "Home",
    "Getting started",
    "Theory",
    "User manual",
    "API",
    "Ecosystem",
    "Scientific evidence",
    "Reference",
    "Contributing",
    "Citation",
]
ACKNOWLEDGEMENTS = (
    "Tomás Corrales and the SPM Lab at Universidad Técnica Federico Santa María "
    "provided selected experimental datasets and laboratory context during the "
    "development and evaluation of SPM-Kit.",
    "María Saavedra Fredes and Benjamin Schleyer helped locate and share candidate "
    "datasets for the validation campaigns.",
    "Tomás Corrales y el SPM Lab de la Universidad Técnica Federico Santa María "
    "proporcionaron datasets experimentales seleccionados y contexto de laboratorio "
    "durante el desarrollo y la evaluación de SPM-Kit.",
    "María Saavedra Fredes y Benjamin Schleyer ayudaron a localizar y compartir "
    "datasets candidatos para las campañas de validación.",
)


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if condition:
            print(f"[OK]   {message}")
        else:
            self.failures.append(message)
            print(f"[FAIL] {message}")


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_version() -> str:
    with (REPO / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def citation_version() -> str:
    match = re.search(r"^version:\s*(\S+)", text(REPO / "CITATION.cff"), re.MULTILINE)
    if not match:
        raise RuntimeError("CITATION.cff has no version")
    return match.group(1)


def collect_nav_files(node: Any) -> list[str]:
    paths: list[str] = []
    if isinstance(node, str):
        paths.append(node)
    elif isinstance(node, list):
        for item in node:
            paths.extend(collect_nav_files(item))
    elif isinstance(node, dict):
        for item in node.values():
            paths.extend(collect_nav_files(item))
    return paths


def cli_commands() -> list[str]:
    tree = ast.parse(text(REPO / "src/spmkit/cli/app.py"))
    commands: list[str] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "app"
                and decorator.func.attr == "command"
            ):
                continue
            command = node.name.replace("_", "-")
            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                command = str(decorator.args[0].value)
            for keyword in decorator.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                    command = str(keyword.value.value)
            commands.append(command)
    return commands


def perspective_specs() -> list[tuple[str, str]]:
    tree = ast.parse(text(REPO / "src/spmkit/gui/builtin_modules.py"))
    specs: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "PerspectiveSpec"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[1], ast.Constant)
        ):
            continue
        specs.append((str(node.args[0].value), str(node.args[1].value)))
    return specs


def pdf_pages(path: Path) -> int:
    executable = shutil.which("pdfinfo")
    if executable:
        result = subprocess.run([executable, str(path)], capture_output=True, check=True, text=True)
        match = re.search(r"^Pages:\s+(\d+)", result.stdout, re.MULTILINE)
        if match:
            return int(match.group(1))
    try:
        from pypdf import PdfReader

        return len(PdfReader(path).pages)
    except ImportError:
        pass
    raw = path.read_bytes()
    counts = [int(value) for value in re.findall(rb"/Count\s+(\d+)", raw)]
    return max(counts) if counts else len(re.findall(rb"/Type\s*/Page\b", raw))


def main() -> int:
    checks = Checks()
    dev_version = project_version()
    released_version = citation_version()
    print(f"Source version        : {dev_version}")
    print(f"GitHub release        : {released_version}")
    print(f"PyPI distribution     : {PYPI_RELEASE}")
    print("-" * 72)

    config_path = REPO / "mkdocs.yml"
    config = yaml.load(text(config_path), Loader=_PermissiveLoader)
    nav = config.get("nav", [])
    top_nav = [next(iter(item)) for item in nav if isinstance(item, dict) and item]
    checks.require(top_nav == EXPECTED_TOP_NAV, "top-level navigation matches portal IA")
    for relative in collect_nav_files(nav):
        checks.require((DOCS / relative).is_file(), f"nav target exists: {relative}")

    custom_dir = config.get("theme", {}).get("custom_dir")
    override_dir = (REPO / custom_dir).resolve() if custom_dir else None
    checks.require(
        bool(override_dir and override_dir.is_dir()),
        f"theme override directory exists: {custom_dir}",
    )
    checks.require(
        bool(override_dir and (override_dir / "main.html").is_file()),
        "theme override supplies Open Graph metadata",
    )

    checks.require(released_version == GITHUB_RELEASE, "CITATION.cff matches GitHub release")
    required_manual_files = (*MANUALS, DOCS / "user-guide.pdf")
    for path in required_manual_files:
        checks.require(path.is_file() and path.stat().st_size > 0, f"manual artifact: {path.name}")

    version_surfaces = (
        *MANUALS,
        DOCS / "manual/index.md",
        DOCS / "manual/downloads.md",
        DOCS / "getting-started/installation.md",
    )
    for path in version_surfaces:
        body = text(path)
        checks.require(
            all(value in body for value in (dev_version, GITHUB_RELEASE, PYPI_RELEASE)),
            f"three-way package status is explicit: {path.relative_to(REPO)}",
        )

    acknowledgement_surfaces = (*MANUALS, DOCS / "ACKNOWLEDGEMENTS.md")
    for path in acknowledgement_surfaces:
        body = text(path)
        checks.require(
            all(paragraph in body for paragraph in ACKNOWLEDGEMENTS),
            f"canonical bilingual acknowledgement: {path.relative_to(REPO)}",
        )
    ack_body = text(DOCS / "ACKNOWLEDGEMENTS.md")
    checks.require(
        all(term in ack_body for term in ("creator", "author", "lead", "not imply")),
        "acknowledgement page preserves authorship and dataset-suitability boundaries",
    )

    specs = perspective_specs()
    checks.require(len(specs) == 12, "source declares 12 Fathom perspectives")
    for path in MANUALS:
        body = text(path)
        checks.require(
            all(key in body and label in body for key, label in specs),
            f"perspective keys and labels are synchronized: {path.name}",
        )

    commands = cli_commands()
    checks.require(len(commands) == 19, "source declares 19 CLI commands")
    markdown_manual = text(DOCS / "user-guide.md")
    checks.require(
        all(f"`{command}`" in markdown_manual for command in commands),
        "Markdown command index covers every CLI command",
    )
    for path in MANUALS:
        body = text(path)
        checks.require(
            all(f"LEVEL {level}" in body for level in range(6)),
            f"evidence vocabulary LEVEL 0–5 is present: {path.name}",
        )

    published_docs = (
        DOCS / "api.md",
        DOCS / "getting-started/installation.md",
        DOCS / "ecosystem/spmkit.md",
        DOCS / "user-guide.md",
        DOCS / "user-guide.tex",
    )
    bad_field = re.compile(r"\b(?:result|stats)\.(?:sa|sq|sz|mean_cpd)\b")
    for path in published_docs:
        checks.require(
            not bad_field.search(text(path)),
            f"public Python fields match source capitalization: {path.relative_to(REPO)}",
        )

    pdf = DOCS / "user-guide.pdf"
    pages = pdf_pages(pdf)
    checks.require(pages == 19, "committed PDF has 19 pages")
    actual_pdf_hash = sha256(pdf)
    downloads = text(DOCS / "manual/downloads.md")
    published_hash = re.search(r"PDF SHA-256:\*\*\s*\n`([0-9a-f]{64})`", downloads)
    checks.require(
        bool(published_hash and published_hash.group(1) == actual_pdf_hash),
        "download metadata matches committed PDF SHA-256",
    )
    source_match = re.search(
        r"Source commit:\*\*\s*\n\[`([0-9a-f]{40})`\]"
        r"\(https://github\.com/kegouro/spmkit/commit/([0-9a-f]{40})\)",
        downloads,
    )
    source_commit_ok = False
    if source_match and source_match.group(1) == source_match.group(2):
        source_commit = source_match.group(1)
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"],
            cwd=REPO,
            check=False,
        )
        source_commit_ok = ancestor.returncode == 0
        for manual in required_manual_files:
            relative = manual.relative_to(REPO).as_posix()
            committed = subprocess.run(
                ["git", "rev-parse", f"{source_commit}:{relative}"],
                cwd=REPO,
                capture_output=True,
                check=False,
                text=True,
            )
            current = subprocess.run(
                ["git", "hash-object", relative],
                cwd=REPO,
                capture_output=True,
                check=False,
                text=True,
            )
            source_commit_ok = source_commit_ok and (
                committed.returncode == 0
                and current.returncode == 0
                and committed.stdout.strip() == current.stdout.strip()
            )
    checks.require(
        source_commit_ok,
        "source commit is an ancestor containing the published manual artifacts",
    )
    checks.require("115 KiB" in downloads and "19-page" in downloads, "PDF size/page metadata")

    viewer_dir = DOCS / "assets/pdf-viewer"
    viewer = viewer_dir / "viewer.html"
    checks.require(viewer.stat().st_size > 0, "embedded PDF reader is present")
    for relative in ("vendor/pdf.min.mjs", "vendor/pdf.worker.min.mjs"):
        asset = viewer_dir / relative
        checks.require(
            asset.is_file() and asset.stat().st_size > 100_000, f"PDF.js asset: {relative}"
        )
    reader_body = text(DOCS / "manual/reader.md")
    checks.require(
        "assets/pdf-viewer/viewer.html" in reader_body and "user-guide.pdf" in reader_body,
        "reader page references the local viewer and PDF",
    )

    manifest_path = DOCS / "assets/ecosystem/assets-manifest.yml"
    manifest = yaml.safe_load(text(manifest_path))
    parent_assets = manifest.get("parent_identity", [])
    checks.require(
        len(parent_assets) == 2,
        "asset manifest declares canonical Pharos parent marks",
    )
    for entry in parent_assets:
        local = REPO / entry["local_path"]
        checks.require(
            local.is_file() and sha256(local) == entry["sha256"],
            f"parent identity hash: {entry['role']}",
        )
    checks.require(
        any(entry.get("role") == "portal-global-mark-and-favicon" for entry in parent_assets),
        "Pharos owns the portal-global mark and favicon",
    )

    canonical_assets = manifest.get("canonical", [])
    checks.require(len(canonical_assets) == 5, "asset manifest declares five canonical banners")
    for entry in canonical_assets:
        local = REPO / entry["local_path"]
        checks.require(
            local.is_file() and sha256(local) == entry["sha256"],
            f"canonical asset hash: {entry['component']}",
        )
    generated_assets = manifest.get("generated_derivatives", [])
    for entry in generated_assets:
        local = REPO / entry["local_path"]
        checks.require(
            local.is_file() and sha256(local) == entry["sha256"],
            f"generated asset hash: {local.relative_to(DOCS)}",
        )
    fathom_inventory = [
        entry for entry in manifest.get("inventory", []) if entry.get("component") == "fathom"
    ]
    checks.require(
        all("favicon" not in str(entry.get("intended_use", "")) for entry in fathom_inventory),
        "Fathom inventory remains component-only, never the portal favicon",
    )

    required_assets = (
        "assets/theory/afm-instrument.svg",
        "assets/theory/operating-modes.svg",
        "assets/theory/force-distance.svg",
        "assets/theory/contact-geometries.svg",
        "assets/theory/kpfm-energy.svg",
        "assets/theory/roughness-flow.svg",
        "assets/theory/psd-interpretation.svg",
        "assets/theory/resonance-response.svg",
        "assets/theory/software-architecture.svg",
        "assets/brand/pharos.svg",
        "assets/brand/pharos-mono.svg",
        "assets/vendor/fonts/inter-latin-variable.woff2",
        "assets/vendor/fonts/fraunces-latin-variable.woff2",
        "assets/vendor/fonts/ibm-plex-mono-latin-400.woff2",
        "assets/vendor/fonts/ibm-plex-mono-latin-600.woff2",
        "stylesheets/tokens.css",
        "stylesheets/shell.css",
        "stylesheets/components.css",
        "stylesheets/scientific.css",
        "stylesheets/responsive.css",
        "assets/pdf-viewer/viewer.css",
        "assets/vendor/mathjax/tex-mml-chtml.js",
        "assets/vendor/mathjax/LICENSE",
    )
    for relative in required_assets:
        asset = DOCS / relative
        checks.require(asset.is_file() and asset.stat().st_size > 0, f"required asset: {relative}")

    config_scripts = config.get("extra_javascript", [])
    checks.require(
        config_scripts == ["javascripts/mathjax.js", "javascripts/accessibility.js"],
        "MathJax stays demand-loaded and scroll regions receive keyboard access",
    )
    checks.require(
        config.get("extra_css")
        == [
            "stylesheets/tokens.css",
            "stylesheets/shell.css",
            "stylesheets/components.css",
            "stylesheets/scientific.css",
            "stylesheets/responsive.css",
        ],
        "Pharos visual system loads in canonical layer order",
    )
    checks.require(
        config.get("theme", {}).get("logo") == "assets/brand/pharos.svg"
        and config.get("theme", {}).get("favicon") == "assets/brand/pharos.svg",
        "global logo and favicon use the canonical Pharos parent mark",
    )
    banner_pages = (
        DOCS / "ecosystem/index.md",
        DOCS / "ecosystem/spmkit.md",
        DOCS / "ecosystem/fathom.md",
        DOCS / "ecosystem/data-hunter.md",
        DOCS / "ecosystem/phantoms.md",
        DOCS / "ecosystem/validation.md",
    )
    for path in banner_pages:
        body = text(path)
        checks.require(
            "srcset=" in body and ".webp" in body,
            f"responsive banner candidates: {path.relative_to(REPO)}",
        )

    print("-" * 72)
    if checks.failures:
        print(f"DOCUMENTATION SYNC FAILED: {len(checks.failures)} problem(s)")
        for failure in checks.failures:
            print(f"  - {failure}")
        return 1
    print("DOCUMENTATION SYNC OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
