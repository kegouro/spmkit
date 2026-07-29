#!/usr/bin/env python3

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import yaml

REPO = Path(__file__).resolve().parents[1]


class _PermissiveLoader(yaml.SafeLoader):
    pass


def _ignore_unknown(loader: Any, _tag_suffix: str, node: Any) -> Any:
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


_PermissiveLoader.add_multi_constructor("", _ignore_unknown)


class References(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.values: list[tuple[str, str]] = []

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if value and name in {"href", "src"}:
                self.values.append((name, value))
            elif value and name == "srcset":
                self.values.extend(("srcset", item.strip().split()[0]) for item in value.split(","))


def resolve_target(site: Path, source: Path, reference: str, site_url: str) -> Path | None:
    parsed = urlparse(reference)
    if parsed.scheme in {"mailto", "tel", "javascript", "data"}:
        return None
    public = urlparse(site_url)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme not in {"http", "https"} or parsed.netloc != public.netloc:
            return None
        relative = unquote(parsed.path)
        public_prefix = public.path.rstrip("/") + "/"
        if not relative.startswith(public_prefix):
            return None
        target = site / relative.removeprefix(public_prefix)
    elif parsed.path.startswith("/"):
        relative = unquote(parsed.path)
        public_prefix = public.path.rstrip("/") + "/"
        if relative.startswith(public_prefix):
            relative = relative.removeprefix(public_prefix)
        target = site / relative.lstrip("/")
    elif parsed.path:
        target = source.parent / unquote(parsed.path)
    else:
        target = source
    if target.is_dir() or (not target.suffix and not target.exists()):
        target /= "index.html"
    return target.resolve()


def main() -> int:
    site = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else (REPO / "site").resolve()
    config = yaml.load(
        (REPO / "mkdocs.yml").read_text(encoding="utf-8"),
        Loader=_PermissiveLoader,
    )
    site_url = str(config["site_url"])
    failures: list[str] = []
    checked = 0
    for source in sorted(site.rglob("*.html")):
        parser = References()
        parser.feed(source.read_text(encoding="utf-8"))
        for attribute, reference in parser.values:
            if "{{" in reference or "{%" in reference:
                continue
            target = resolve_target(site, source, reference, site_url)
            if target is None:
                continue
            checked += 1
            try:
                target.relative_to(site)
            except ValueError:
                failures.append(
                    f"{source.relative_to(site)}: {attribute} escapes site: {reference}"
                )
                continue
            if not target.is_file():
                failures.append(f"{source.relative_to(site)}: missing {attribute}: {reference}")
    if failures:
        print(f"BROKEN INTERNAL LINKS: {len(failures)}")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"INTERNAL LINKS OK: {checked} references across {len(list(site.rglob('*.html')))} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
