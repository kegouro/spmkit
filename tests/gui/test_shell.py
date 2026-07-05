"""Tests del shell: matcher difuso y perspectivas. Puro, sin Qt."""

from __future__ import annotations

import pytest

from spmkit.gui.shell import perspectives
from spmkit.gui.shell.fuzzy import fuzzy_score, rank


def test_fuzzy_matches_subsequence() -> None:
    assert fuzzy_score("aj", "Ajustar elasticidad") is not None
    assert fuzzy_score("cont", "punto de contacto") is not None


def test_fuzzy_rejects_non_subsequence() -> None:
    assert fuzzy_score("xyz", "Ajustar") is None  # no hay x/y/z
    assert fuzzy_score("tj", "Ajustar") is None  # orden importa (no hay j después de t)


def test_fuzzy_prefix_scores_higher() -> None:
    prefix = fuzzy_score("aj", "ajuste")
    scattered = fuzzy_score("aj", "trabajar con jota")
    assert prefix is not None and scattered is not None
    assert prefix > scattered


def test_rank_orders_and_filters() -> None:
    items = ["Ajustar", "Calibrar", "Mapa de modulo"]
    ranked = rank("aj", items)
    assert [i for i, _ in ranked] == [0]  # solo "Ajustar" tiene la subsecuencia a-j


def test_perspective_lookup() -> None:
    assert perspectives.perspective("force").label == "Curva de fuerza"
    assert "pipeline" in perspectives.perspective("force").panels
    with pytest.raises(KeyError, match="perspectiva desconocida"):
        perspectives.perspective("nope")


def test_all_panels_unique_and_complete() -> None:
    assert len(perspectives.ALL_PANELS) == len(set(perspectives.ALL_PANELS))
    assert "navigator" in perspectives.ALL_PANELS
    assert "force_canvas" in perspectives.ALL_PANELS
