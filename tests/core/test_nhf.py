from pathlib import Path

import numpy as np
import pytest

from spmkit import load

h5py = pytest.importorskip("h5py")


def test_load_nhf_conserva_canal_y_atributos_bytes(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.nhf"
    esperado = np.array([[1.25, 2.5, 3.75], [4.0, 5.5, 6.75]], dtype=np.float64)
    with h5py.File(path, "w") as archivo:
        grupo = archivo.create_group("Scan forward")
        dataset = grupo.create_dataset("raw_height", data=esperado)
        dataset.attrs["name"] = np.bytes_("Z-Axis")
        dataset.attrs["unit"] = np.bytes_("m")
        dataset.attrs["x_range"] = 3.0e-6
        dataset.attrs["y_range"] = 2.0e-6
        dataset.attrs["direction"] = np.bytes_("backward")
        dataset.attrs["note"] = np.bytes_("sintético".encode())

    resultado = load(path)

    assert len(resultado.channels) == 1
    canal = resultado.channels[0]
    np.testing.assert_array_equal(canal.data, esperado)
    assert canal.name == "Z-Axis"
    assert canal.unit == "m"
    assert canal.x_range == 3.0e-6
    assert canal.y_range == 2.0e-6
    assert canal.direction == "backward"
    assert canal.group == "Scan forward"
    assert canal.metadata["note"] == "sintético"
    assert resultado.source_path == str(path)


def test_load_nhf_ignora_datasets_que_no_son_2d(tmp_path: Path) -> None:
    path = tmp_path / "mixed.nhf"
    with h5py.File(path, "w") as archivo:
        archivo.create_dataset("scalar", data=1.0)
        archivo.create_dataset("profile", data=np.arange(4))
        archivo.create_dataset("volume", data=np.zeros((2, 3, 4)))
        imagen = archivo.create_dataset("image", data=np.ones((2, 3)))
        imagen.attrs["name"] = "Height"

    resultado = load(path)

    assert resultado.names == ["Height"]


def test_load_nhf_sin_datasets_2d_falla_con_mensaje_accionable(tmp_path: Path) -> None:
    path = tmp_path / "empty.nhf"
    with h5py.File(path, "w") as archivo:
        archivo.create_dataset("profile", data=np.arange(4))

    with pytest.raises(ValueError, match=r"(?i)no se encontraron canales 2D.*\.nhf"):
        load(path)


def test_load_nhf_invalido_envuelve_error_de_h5py(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.nhf"
    path.write_bytes(b"esto no es HDF5")

    patron = r"(?i)no se pudo abrir o leer.*\.nhf.*(inválido|corrupto)"
    with pytest.raises(ValueError, match=patron) as error:
        load(path)

    assert isinstance(error.value.__cause__, OSError)
