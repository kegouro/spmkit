"""Lectura de formatos SPM."""

from spmkit.core.io.gwy import load_gwy, save_gwy
from spmkit.core.io.nhf import load_nhf
from spmkit.core.io.nid import load_nid
from spmkit.core.io.registry import load, supported_extensions

__all__ = ["load", "load_nid", "load_nhf", "load_gwy", "save_gwy", "supported_extensions"]
