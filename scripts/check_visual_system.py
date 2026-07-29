from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
STYLES = DOCS / "stylesheets"


def relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float:
    lighter, darker = sorted(
        (relative_luminance(first), relative_luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def declaration_block(source: str, selector: str) -> str:
    selector_at = source.index(selector)
    block_start = source.index("{", selector_at) + 1
    block_end = source.index("}", block_start)
    return source[block_start:block_end]


def custom_properties(block: str) -> dict[str, str]:
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", block))


def resolved_hex(name: str, properties: dict[str, str]) -> str:
    seen: set[str] = set()
    value = properties[name].strip()
    while match := re.fullmatch(r"var\((--[\w-]+)\)", value):
        name = match.group(1)
        if name in seen:
            raise ValueError(f"cyclic token reference: {name}")
        seen.add(name)
        value = properties[name].strip()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError(f"token {name} does not resolve to a six-digit hex color: {value}")
    return value


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def require(self, condition: bool, label: str) -> None:
        state = "PASS" if condition else "FAIL"
        print(f"[{state}] {label}")
        if not condition:
            self.failures.append(label)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    checks = Checks()
    config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    layers = [STYLES / name for name in (
        "tokens.css",
        "shell.css",
        "components.css",
        "scientific.css",
        "responsive.css",
    )]
    css = "\n".join(path.read_text(encoding="utf-8") for path in layers)
    tokens = layers[0].read_text(encoding="utf-8")
    reader_css = (DOCS / "assets/pdf-viewer/viewer.css").read_text(encoding="utf-8")
    runtime_css = "\n".join(path.read_text(encoding="utf-8") for path in layers[1:])
    runtime_css += "\n" + reader_css

    checks.require(
        "logo: assets/brand/pharos.svg" in config
        and "favicon: assets/brand/pharos.svg" in config,
        "Pharos mark owns global logo and favicon",
    )
    checks.require(
        sha256(DOCS / "assets/brand/pharos.svg")
        == "2cb865a79561c7099cc9d482cbc51634c88f9d6889810b9ab67ebe063f438835",
        "canonical Pharos asset hash",
    )
    current_sources = []
    for path in DOCS.rglob("*"):
        if path.suffix not in {".md", ".html", ".css", ".js"}:
            continue
        if "assets/legacy" in path.as_posix():
            continue
        current_sources.append(path.read_text(encoding="utf-8"))
    current_source = "\n".join(current_sources)
    checks.require(
        "--fathom-" not in current_source
        and ".portal-" not in current_source
        and ".fathom-card" not in current_source,
        "legacy global theme selectors removed",
    )
    checks.require(
        re.search(r"#[0-9a-fA-F]{3,8}\b", runtime_css) is None,
        "runtime colors are centralized in tokens.css",
    )

    required_selectors = (
        ".spm-hero",
        ".spm-button--primary",
        ".spm-button--secondary",
        ".spm-button--quiet",
        ".spm-panel--evidence",
        ".spm-status--pass",
        ".spm-status--fail",
        ".spm-status--blocked",
        ".spm-status--not-run",
        ".spm-workflow-ladder",
        ".spm-evidence-ladder",
        ".spm-evidence-level--unclaimed",
        ".spm-level--3",
        ".spm-level--unclaimed",
        ".spm-component",
        ".spm-science-figure",
    )
    for selector in required_selectors:
        checks.require(selector in css, f"shared selector: {selector}")

    global_css_bytes = sum(path.stat().st_size for path in layers)
    reader_css_bytes = (DOCS / "assets/pdf-viewer/viewer.css").stat().st_size
    checks.require(global_css_bytes <= 36_864, "global CSS budget <= 36 KiB")
    checks.require(reader_css_bytes <= 5_500, "PDF reader CSS budget <= 5.5 KiB")

    fixed = custom_properties(declaration_block(tokens, ":root {"))
    dark = fixed | custom_properties(
        declaration_block(tokens, '[data-md-color-scheme="slate"]')
    )
    light = fixed | custom_properties(
        declaration_block(tokens, '[data-md-color-scheme="default"]')
    )
    token_contract = {
        "dark ink / canvas": (dark, "--spm-ink", "--spm-canvas", 4.5),
        "dark muted / canvas": (dark, "--spm-ink-muted", "--spm-canvas", 4.5),
        "dark link / canvas": (dark, "--spm-link", "--spm-canvas", 4.5),
        "dark primary label / action": (dark, "--spm-action-ink", "--spm-action", 4.5),
        "dark success / canvas": (dark, "--spm-success", "--spm-canvas", 4.5),
        "dark danger / canvas": (dark, "--spm-danger", "--spm-canvas", 4.5),
        "light ink / canvas": (light, "--spm-ink", "--spm-canvas", 4.5),
        "light muted / canvas": (light, "--spm-ink-muted", "--spm-canvas", 4.5),
        "light link / canvas": (light, "--spm-link", "--spm-canvas", 4.5),
        "light primary label / action": (light, "--spm-action-ink", "--spm-action", 4.5),
        "light signal / canvas": (light, "--spm-signal", "--spm-canvas", 4.5),
        "light success / canvas": (light, "--spm-success", "--spm-canvas", 4.5),
        "light danger / canvas": (light, "--spm-danger", "--spm-canvas", 4.5),
    }
    for label, (properties, foreground_token, background_token, minimum) in token_contract.items():
        foreground = resolved_hex(foreground_token, properties)
        background = resolved_hex(background_token, properties)
        ratio = contrast(foreground, background)
        checks.require(ratio >= minimum, f"{label}: {ratio:.2f}:1")

    for value in {
        "#0a0908",
        "#15110d",
        "#1c1712",
        "#2a2118",
        "#493723",
        "#efe7d8",
        "#c8bba8",
        "#9a8a76",
        "#f5a72c",
        "#ff7a3c",
        "#ffd690",
        "#fb923c",
    }:
        checks.require(value in tokens.lower(), f"canonical Pharos token: {value}")

    scientific_status = (DOCS / "scientific-status.md").read_text(encoding="utf-8")
    checks.require(
        all(f"spm-evidence-level--{level}" in scientific_status for level in range(6)),
        "canonical scientific ladder contains evidence levels 0 through 5",
    )
    checks.require(
        scientific_status.count("spm-evidence-level--unclaimed") == 2
        and "spm-evidence-level--4 spm-evidence-level--unclaimed" in scientific_status
        and "spm-evidence-level--5 spm-evidence-level--unclaimed" in scientific_status,
        "unclaimed physical and reproducibility levels remain explicit",
    )
    for relative in (
        "index.md",
        "scientific-status.md",
        "validation/index.md",
        "theory/index.md",
        "ecosystem/index.md",
    ):
        checks.require(
            "spm-level" in (DOCS / relative).read_text(encoding="utf-8"),
            f"compact evidence consumer: {relative}",
        )

    viewer = (DOCS / "assets/pdf-viewer/viewer.html").read_text(encoding="utf-8")
    checks.require(
        'new URL("../../user-guide.pdf", location.href)' in viewer
        and "location.hash" not in viewer
        and "connect-src 'self'" in viewer,
        "PDF reader is restricted to the packaged same-origin guide",
    )
    checks.require(
        "IntersectionObserver" in viewer
        and "renderTask.cancel()" in viewer
        and "if (fitMode)" in viewer,
        "PDF reader lazily renders, cancels stale work, and reapplies fit on resize",
    )

    checks.require(
        (DOCS / "scientific-status.md").is_file()
        and (DOCS / "validation/index.md").is_file()
        and "Scientific status: scientific-status.md" in config
        and "Validation campaigns: validation/index.md" in config,
        "canonical lowercase evidence routes",
    )

    class_pattern = re.compile(r'class="([^"]+)"')
    used_classes: set[str] = set()
    for path in DOCS.rglob("*"):
        if path.suffix not in {".md", ".html"} or "assets/legacy" in path.as_posix():
            continue
        for match in class_pattern.finditer(path.read_text(encoding="utf-8")):
            used_classes.update(
                name for name in match.group(1).split() if name.startswith("spm-")
            )
    all_css = css + (DOCS / "assets/pdf-viewer/viewer.css").read_text(encoding="utf-8")
    for class_name in sorted(used_classes):
        checks.require(f".{class_name}" in all_css, f"styled consumer class: {class_name}")

    fixture = DOCS / "design/visual-system-fixture.md"
    checks.require(fixture.is_file(), "internal visual-system fixture")
    checks.require(
        "design/visual-system-fixture.md" not in config,
        "fixture remains outside public navigation",
    )

    print("-" * 72)
    if checks.failures:
        print(f"VISUAL SYSTEM FAILED: {len(checks.failures)} problem(s)")
        return 1
    print("VISUAL SYSTEM OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
