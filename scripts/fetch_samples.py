#!/usr/bin/env python3
"""Descarga samples open-source de AFM por formato — el arnés de datos de prueba.

Baja archivos de ejemplo pequeños y de licencia libre a ``reference/samples/``
(gitignored, **nunca se commitea**) para validar los lectores contra datos reales. Los
tests hacen ``skipif`` si el archivo no está, así que el CI sigue verde sin red.

Fuentes (verificadas): datos de test de **afmformats** (MIT, AFM-analysis/afmformats) y
samples de **Gwyddion** (SourceForge). Prefiere el cache local; la red es el último
recurso. Uso:

    python scripts/fetch_samples.py            # baja los que falten
    python scripts/fetch_samples.py --list     # lista el manifiesto
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_AFM = "https://raw.githubusercontent.com/AFM-analysis/afmformats/master/tests/data/"

#: Directorio de cache (gitignored vía reference/).
SAMPLES_DIR = Path(__file__).resolve().parents[1] / "reference" / "samples"


@dataclass(frozen=True)
class Sample:
    key: str  # identificador corto estable (lo usan los tests)
    filename: str  # nombre local del archivo
    url: str
    fmt: str  # formato lógico
    reader: str  # librería que lo lee (afmformats / gwyddion / nativo)


#: Manifiesto de samples. Archivos pequeños (<~500 KB), MIT/OSS.
MANIFEST: tuple[Sample, ...] = (
    Sample(
        "jpk_force",
        "fmt-jpk-fd_spot3-0192.jpk-force",
        _AFM + "fmt-jpk-fd_spot3-0192.jpk-force",
        "jpk-force",
        "afmformats/nativo",
    ),
    Sample(
        "jpk_qi",
        "fmt-jpk-fd_2020.02.07-16.29.05.036.jpk-qi-data",
        _AFM + "fmt-jpk-fd_2020.02.07-16.29.05.036.jpk-qi-data",
        "jpk-qi",
        "afmformats",
    ),
    Sample(
        "igor_ibw",
        "fmt-igor-fd_SiN_FD_plot.ibw",
        _AFM + "fmt-igor-fd_SiN_FD_plot.ibw",
        "ibw",
        "afmformats",
    ),
    Sample(
        "hdf5_fd",
        "fmt-hdf5-fd_version_0.13.3.h5",
        _AFM + "fmt-hdf5-fd_version_0.13.3.h5",
        "hdf5",
        "afmformats",
    ),
    Sample(
        "ntmdt_txt",
        "fmt-ntmdt-txt-fd.txt",
        _AFM + "fmt-ntmdt-txt-fd_2015_01_17_gel4-0,1_mQ_adh_6B_Curve_DFL_Height_51.txt",
        "ntmdt-txt",
        "afmformats",
    ),
    Sample(
        "tab_fd",
        "fmt-tab-fd_version_0.13.3.tab",
        _AFM + "fmt-tab-fd_version_0.13.3.tab",
        "tab",
        "afmformats",
    ),
    Sample(
        "csv_fd",
        "fmt-afm-workshop-fd_single.csv",
        _AFM + "fmt-afm-workshop-fd_single_2021-10-22_14.16.csv",
        "csv",
        "afmformats",
    ),
)

_BY_KEY = {s.key: s for s in MANIFEST}


def sample_path(key: str) -> Path | None:
    """Ruta local de un sample si ya está descargado (para los tests). ``None`` si no."""
    sample = _BY_KEY.get(key)
    if sample is None:
        return None
    path = SAMPLES_DIR / sample.filename
    return path if path.exists() else None


def fetch(sample: Sample, *, force: bool = False, timeout: float = 30.0) -> Path | None:
    """Descarga ``sample`` a ``SAMPLES_DIR`` (salta si ya está). ``None`` si falla la red."""
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    dest = SAMPLES_DIR / sample.filename
    if dest.exists() and not force:
        return dest
    try:
        with urllib.request.urlopen(
            sample.url, timeout=timeout
        ) as resp:  # noqa: S310 - URLs fijas del manifiesto
            dest.write_bytes(resp.read())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"  ✗ {sample.key}: {exc}", file=sys.stderr)
        return None
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description="Descarga samples de AFM open-source.")
    parser.add_argument("--list", action="store_true", help="Lista el manifiesto y sale.")
    parser.add_argument("--force", action="store_true", help="Re-descarga aunque exista.")
    args = parser.parse_args()

    if args.list:
        for s in MANIFEST:
            state = "cache" if (SAMPLES_DIR / s.filename).exists() else "—"
            print(f"{s.key:12s} {s.fmt:10s} [{state}] {s.filename}")
        return 0

    ok = 0
    for s in MANIFEST:
        path = fetch(s, force=args.force)
        if path is not None:
            ok += 1
            print(f"  ✓ {s.key:12s} → {path.relative_to(SAMPLES_DIR.parents[1])}")
    print(f"\n{ok}/{len(MANIFEST)} samples en {SAMPLES_DIR}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
