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
    checks.require(
        "--fathom-" not in css
        and ".portal-" not in css
        and ".fathom-card" not in css,
        "legacy global theme selectors removed",
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
        ".spm-evidence-ladder",
        ".spm-component",
        ".spm-science-figure",
    )
    for selector in required_selectors:
        checks.require(selector in css, f"shared selector: {selector}")

    global_css_bytes = sum(path.stat().st_size for path in layers)
    reader_css_bytes = (DOCS / "assets/pdf-viewer/viewer.css").stat().st_size
    checks.require(global_css_bytes <= 27_000, "global CSS budget <= 27 KiB")
    checks.require(reader_css_bytes <= 5_500, "PDF reader CSS budget <= 5.5 KiB")

    token_contract = {
        "dark ink / canvas": ("#efe7d8", "#0a0908", 4.5),
        "dark muted / canvas": ("#c8bba8", "#0a0908", 4.5),
        "dark link / canvas": ("#ffd690", "#0a0908", 4.5),
        "dark primary label / amber": ("#20150a", "#f5a72c", 4.5),
        "dark success / canvas": ("#86efac", "#0a0908", 4.5),
        "dark danger / canvas": ("#fca5a5", "#0a0908", 4.5),
        "light ink / canvas": ("#201a15", "#f4f0e7", 4.5),
        "light muted / canvas": ("#5f5143", "#f4f0e7", 4.5),
        "light link / canvas": ("#8a4b00", "#f4f0e7", 4.5),
        "light primary label / action": ("#fffdf8", "#8a4b00", 4.5),
        "light signal / canvas": ("#0f766e", "#f4f0e7", 4.5),
        "light success / canvas": ("#166534", "#f4f0e7", 4.5),
        "light danger / canvas": ("#991b1b", "#f4f0e7", 4.5),
    }
    for label, (foreground, background, minimum) in token_contract.items():
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
        checks.require(value in css.lower(), f"canonical Pharos token: {value}")

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
