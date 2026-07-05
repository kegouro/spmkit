"""Coincidencia difusa (subsecuencia) para la paleta de comandos. Puro, sin Qt."""

from __future__ import annotations


def fuzzy_score(query: str, text: str) -> float | None:
    """Puntúa qué tan bien ``query`` coincide con ``text`` como subsecuencia.

    Devuelve un puntaje (mayor = mejor) o ``None`` si los caracteres de ``query`` no
    aparecen en orden dentro de ``text``. Premia caracteres contiguos y el match de
    prefijo. Sin dependencias.
    """
    query = query.strip().lower()
    if not query:
        return 0.0
    lowered = text.lower()
    score = 0.0
    last = -1
    for ch in query:
        idx = lowered.find(ch, last + 1)
        if idx == -1:
            return None
        gap = idx - last - 1
        score += 1.0 / (1.0 + gap)  # contigüidad premiada
        last = idx
    if lowered.startswith(query):
        score += 2.0
    return score


def rank(query: str, items: list[str]) -> list[tuple[int, float]]:
    """Devuelve ``(índice, puntaje)`` de los ``items`` que coinciden, mejor primero."""
    scored = [(i, s) for i, text in enumerate(items) if (s := fuzzy_score(query, text)) is not None]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored
