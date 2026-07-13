import tomllib
from importlib.metadata import version
from pathlib import Path

import yaml

import spmkit

RAIZ = Path(__file__).parents[1]


def test_version_coincide_en_todas_las_fuentes() -> None:
    proyecto = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    cita = yaml.safe_load((RAIZ / "CITATION.cff").read_text(encoding="utf-8"))
    version_proyecto = proyecto["project"]["version"]

    assert version_proyecto == cita["version"]
    assert version("spmkit") == version_proyecto
    assert spmkit.__version__ == version_proyecto


def test_rango_de_python_soportado_es_exacto() -> None:
    proyecto = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))

    assert proyecto["project"]["requires-python"] == ">=3.11,<3.13"
