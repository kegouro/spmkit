"""Lectura de formatos SPM.

``load`` devuelve un ``SPMData`` (imágenes). Las **curvas de fuerza** son un dominio
distinto (``ForceCurve``): se leen con ``load_jpk_force`` (y, más adelante, un
dispatcher ``load_force`` por extensión).
"""

from spmkit.core.io.forceload import load_force, supported_force_extensions
from spmkit.core.io.gwy import load_gwy, save_gwy
from spmkit.core.io.igor_ibw import load_igor_ibw
from spmkit.core.io.jpk import load_jpk_force
from spmkit.core.io.loadany import inspect_any, load_any
from spmkit.core.io.nhf import load_nhf
from spmkit.core.io.nid import load_nid, load_nid_force
from spmkit.core.io.registry import load, supported_extensions

__all__ = [
    "load",
    "load_any",
    "inspect_any",
    "load_nid",
    "load_nid_force",
    "load_nhf",
    "load_gwy",
    "load_igor_ibw",
    "save_gwy",
    "load_jpk_force",
    "load_force",
    "supported_force_extensions",
    "supported_extensions",
]
