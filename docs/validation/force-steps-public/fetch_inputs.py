"""Fetch only the inputs used in the public force-curve comparisons."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


def read_url(url):
    with urlopen(url, timeout=120) as response:
        return response.read()


def save(root, name, data, expected):
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Unexpected file path {name}")
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"Digest mismatch for {name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def pairs(root):
    from remotezip import RemoteZip

    manifest = json.loads(Path(__file__).with_name("pairs.json").read_text())
    with RemoteZip("https://ndownloader.figshare.com/files/19243244") as archive:
        for item in manifest:
            name = item["member"]
            save(root, name, archive.read(name), item["sha256"])


def paam(root):
    record = json.loads(read_url("https://api.figshare.com/v2/articles/11637675/versions/3"))
    urls = {item["name"]: item["download_url"] for item in record["files"]}
    checksums = read_url(urls["sha256.txt"])
    for line in checksums.decode().splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            if name.endswith(".jpk-force"):
                save(root, name, read_url(urls[name]), digest)
    (root / "sha256.txt").write_bytes(checksums)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=["pairs", "paam"])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    {"pairs": pairs, "paam": paam}[args.dataset](args.output)
