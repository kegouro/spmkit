from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.models import SPMChannel, SPMData


def _channel(name: str, direction: str, group: str) -> SPMChannel:
    return SPMChannel(
        name=name,
        data=np.zeros((2, 2)),
        unit="m",
        x_range=1e-6,
        y_range=1e-6,
        direction=direction,
        group=group,
    )


@pytest.fixture
def duplicate_channels() -> SPMData:
    return SPMData(
        channels=(
            _channel("Z-Axis", "forward", "Scan 1"),
            _channel("Z-Axis", "backward", "Scan 1"),
            _channel("Z-Axis", "forward", "Scan 2"),
            _channel("CPD", "forward", "Scan 1"),
        )
    )


def test_select_devuelve_la_identidad_exacta(duplicate_channels: SPMData) -> None:
    selected = duplicate_channels.select("Z-Axis", direction="forward", group="Scan 2")

    assert selected is duplicate_channels.channels[2]


def test_select_filtra_solo_los_campos_suministrados(duplicate_channels: SPMData) -> None:
    selected = duplicate_channels.select("Z-Axis", direction="backward")

    assert selected is duplicate_channels.channels[1]


def test_select_rechaza_nombre_ambiguo_con_identidades(duplicate_channels: SPMData) -> None:
    with pytest.raises(ValueError, match="ambigua") as exc_info:
        duplicate_channels.select("Z-Axis")

    message = str(exc_info.value)
    assert "forward" in message
    assert "backward" in message
    assert "Scan 1" in message
    assert "Scan 2" in message


def test_select_rechaza_direccion_ambigua_sin_grupo(duplicate_channels: SPMData) -> None:
    with pytest.raises(ValueError, match="ambigua") as exc_info:
        duplicate_channels.select("Z-Axis", direction="forward")

    message = str(exc_info.value)
    assert "Scan 1" in message
    assert "Scan 2" in message


def test_select_ausente_describe_seleccion_y_opciones(duplicate_channels: SPMData) -> None:
    with pytest.raises(KeyError) as exc_info:
        duplicate_channels.select("Z-Axis", direction="backward", group="Scan 2")

    message = str(exc_info.value)
    assert "Z-Axis" in message
    assert "backward" in message
    assert "Scan 2" in message
    assert "Disponibles" in message
    assert "forward" in message
    assert "Scan 1" in message


def test_get_y_getitem_conservan_el_fallback_compatible(duplicate_channels: SPMData) -> None:
    assert duplicate_channels.get("Z-Axis") is duplicate_channels.channels[0]
    assert duplicate_channels.get("Z-Axis", direction="missing") is duplicate_channels.channels[0]
    assert duplicate_channels["Z-Axis"] is duplicate_channels.channels[0]
