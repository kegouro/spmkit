"""Lectores built-in (dominio AFM/Fathom) que implementan el contrato :class:`Reader`.

Adaptan los parsers existentes (``load_nid``, ``load_gwy``, …) al contrato de plugins:
declaran extensiones y capacidades, hacen un ``inspect`` barato (solo cabecera cuando el
formato lo permite) y cargan el ``kind`` pedido de forma perezosa.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spmkit.core.plugins.contracts import DatasetInfo, Kind, Reader

_HEADER_PREFIX = 262_144  # 256 KB: los headers de texto son pequeños


class NidReader:
    """NanoSurf ``.nid`` — imagen y/o force-volume, según la cabecera."""

    extensions: tuple[str, ...] = (".nid",)

    def inspect(self, path: str | Path) -> DatasetInfo:
        from spmkit.core.io import nid

        with open(path, "rb") as fh:  # noqa: PTH123 - lectura acotada, no todo el archivo
            prefix = fh.read(_HEADER_PREFIX)
        marker = prefix.find(nid._MARKER)
        if marker == -1:  # cabecera mayor de lo esperado (raro): leer completo
            prefix = Path(path).read_bytes()
            marker = prefix.find(nid._MARKER)
        header = nid._decode_header(prefix[:marker] if marker != -1 else prefix)
        sections = nid._parse_ini(header)
        order = nid._channel_order(sections["DataSet"]) if "DataSet" in sections else []
        channels: list[str] = []
        has_image = has_force = False
        for sec_name in order:
            sec = sections.get(sec_name)
            if sec is None:
                continue
            channels.append(sec.get("Dim2Name", sec_name))
            if sec.get("Dim1Name", "") == "SpecPoint":
                has_force = True
            else:
                has_image = True
        kinds_list: list[Kind] = []
        if has_image:
            kinds_list.append("image")
        if has_force:
            kinds_list.append("force")
        kinds: tuple[Kind, ...] = tuple(kinds_list) or ("image",)
        return DatasetInfo(path=Path(path), format="nid", kinds=kinds, channels=tuple(channels))

    def load(self, path: str | Path, kind: Kind | None = None) -> Any:
        from spmkit.core.io import nid

        if kind == "force":
            return nid.load_nid_force(path)
        if kind == "image":
            return nid.load_nid(path)
        info = self.inspect(path)  # sin kind: si es solo-fuerza, force; si no, imagen
        if info.kinds == ("force",):
            return nid.load_nid_force(path)
        return nid.load_nid(path)


class _ImageReader:
    """Base para formatos de sólo-imagen (``.nhf``, ``.gwy``)."""

    extensions: tuple[str, ...] = ()
    format = ""

    def _loader(self) -> Any:  # pragma: no cover - sobrescrito
        raise NotImplementedError

    def inspect(self, path: str | Path) -> DatasetInfo:
        return DatasetInfo(path=Path(path), format=self.format, kinds=("image",))

    def load(self, path: str | Path, kind: Kind | None = None) -> Any:
        return self._loader()(path)


class NhfReader(_ImageReader):
    extensions: tuple[str, ...] = (".nhf",)
    format = "nhf"

    def _loader(self) -> Any:
        from spmkit.core.io.nhf import load_nhf

        return load_nhf


class GwyReader(_ImageReader):
    extensions: tuple[str, ...] = (".gwy",)
    format = "gwy"

    def _loader(self) -> Any:
        from spmkit.core.io.gwy import load_gwy

        return load_gwy


class BrukerSpmReader(_ImageReader):
    """Bruker/Nanoscope ``.spm`` (imagen) — **EXPERIMENTAL**, escalado sin validar."""

    extensions: tuple[str, ...] = (".spm",)
    format = "bruker-spm"

    def _loader(self) -> Any:
        from spmkit.core.io.bruker_spm import load_bruker_spm

        return load_bruker_spm


class IgorIbwReader(_ImageReader):
    """Limited native Igor Binary Wave v5 image reader.

    A header predicate deliberately lets unsupported ``.ibw`` variants reach the
    optional ``afmformats`` reader when that extra is installed.
    """

    extensions: tuple[str, ...] = (".ibw",)
    format = "igor-ibw-v5-native-limited"

    def matches_path(self, path: str | Path) -> bool:
        from spmkit.core.io.igor_ibw import looks_like_limited_igor_ibw

        return looks_like_limited_igor_ibw(path)

    def inspect(self, path: str | Path) -> Any:
        from spmkit.core.io.igor_ibw import inspect_igor_ibw

        return inspect_igor_ibw(path)

    def _loader(self) -> Any:
        from spmkit.core.io.igor_ibw import load_igor_ibw

        return load_igor_ibw


class JpkForceReader:
    """JPK/Bruker ``.jpk-force`` — curva de fuerza (envuelta en un volumen 1×1)."""

    extensions: tuple[str, ...] = (".jpk-force", ".jpk")

    def inspect(self, path: str | Path) -> DatasetInfo:
        return DatasetInfo(path=Path(path), format="jpk-force", kinds=("force",))

    def load(self, path: str | Path, kind: Kind | None = None) -> Any:
        from spmkit.core.io.forceload import load_force

        return load_force(path)


#: Lectores del dominio AFM que el registry carga por defecto.
BUILTIN_READERS: tuple[Reader, ...] = (
    NidReader(),
    NhfReader(),
    GwyReader(),
    BrukerSpmReader(),
    IgorIbwReader(),
    JpkForceReader(),
)
