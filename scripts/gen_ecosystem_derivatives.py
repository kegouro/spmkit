#!/usr/bin/env python3

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageOps

REPO = Path(__file__).resolve().parents[1]
SOURCES = {
    "core": REPO / "docs/assets/ecosystem/core/banner.png",
    "fathom": REPO / "docs/assets/ecosystem/fathom/banner.jpeg",
    "data-hunter": REPO / "docs/assets/ecosystem/data-hunter/banner.png",
    "phantoms": REPO / "docs/assets/ecosystem/phantoms/banner.png",
    "validation": REPO / "docs/assets/ecosystem/validation/banner.png",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(source: Path, requested_width: int) -> Path:
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        width = min(requested_width, image.width)
        height = round(image.height * width / image.width)
        resized = image.resize((width, height), Image.Resampling.LANCZOS)
        output = source.with_name(f"banner-{width}.webp")
        resized.save(output, "WEBP", quality=86, method=6)
    return output


def main() -> None:
    for component, source in SOURCES.items():
        for requested_width in (640, 1280):
            output = generate(source, requested_width)
            with Image.open(output) as image:
                print(
                    f"{component}\t{output.relative_to(REPO)}\t"
                    f"{image.width}x{image.height}\t{output.stat().st_size}\t{digest(output)}"
                )


if __name__ == "__main__":
    main()
