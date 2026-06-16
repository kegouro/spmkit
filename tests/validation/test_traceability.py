"""Suite de verificación y trazabilidad del pipeline .nid.

Cubre:
- Extracción: marcador, número de canales, offsets y longitudes de bloque.
- Formato (unidades físicas): mapeo raw→físico exacto con pytest.approx.
- Presupuesto de bytes: suma de bloques == bytes binarios.
- Orientación: canal imagen (Dim1Name=Y*) se voltea; canal no-imagen no.
- Manipulación: roughness.statistics sobre datos de σ conocida → Sq ≈ σ.
- Representación: round-trip CSV/JSON; HDF5 y GWY si están disponibles.
- Cálculo: todos los checks del traza sintética pasan (trace.ok).
- Datos reales (skip si no están): trace_nid sobre .nid real → trace.ok.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from spmkit.core.analysis import roughness
from spmkit.core.export import to_csv, to_json
from spmkit.core.io.nid import load_nid
from spmkit.core.models import SPMChannel
from spmkit.core.verify import NidTrace, trace_nid

# ---------------------------------------------------------------------------
# Constantes de los canales sintéticos
# ---------------------------------------------------------------------------

# Canal 0: imagen 8×8 (Dim1Name=Y → se voltea)
IMG_POINTS = 8
IMG_LINES = 8
IMG_DIM2_MIN = -1.0
IMG_DIM2_RANGE = 2.0  # → rango físico [-1, 1]

# Canal 1: canal no-imagen 4×4 (Dim1Name=SpecPoint → NO se voltea)
SPEC_POINTS = 4
SPEC_LINES = 4
SPEC_DIM2_MIN = 0.0
SPEC_DIM2_RANGE = 5.0  # → rango físico [0, 5]

_HEADER_TEMPLATE = (
    "[DataSet]\r\n"
    "Version=2\r\n"
    "GroupCount=2\r\n"
    "Gr0-Count=1\r\n"
    "Gr0-Ch0=DataSet-0:0\r\n"
    "Gr1-Count=1\r\n"
    "Gr1-Ch0=DataSet-1:0\r\n"
    "\r\n"
    # Canal imagen
    "[DataSet-0:0]\r\n"
    "Version=2\r\n"
    f"Points={IMG_POINTS}\r\n"
    f"Lines={IMG_LINES}\r\n"
    "Frame=Scan forward\r\n"
    "Dim0Name=X-Axis\r\nDim0Unit=m\r\nDim0Range=5e-06\r\nDim0Min=0\r\n"
    "Dim1Name=Y-Axis\r\nDim1Unit=m\r\nDim1Range=5e-06\r\nDim1Min=0\r\n"
    f"Dim2Name=Z-Axis\r\nDim2Unit=m\r\nDim2Range={IMG_DIM2_RANGE}\r\nDim2Min={IMG_DIM2_MIN}\r\n"
    "SaveMode=Binary\r\nSaveBits=32\r\nSaveSign=Signed\r\nSaveOrder=Intel\r\n"
    "\r\n"
    # Canal espectroscopía (no-imagen)
    "[DataSet-1:0]\r\n"
    "Version=2\r\n"
    f"Points={SPEC_POINTS}\r\n"
    f"Lines={SPEC_LINES}\r\n"
    "Frame=Spectroscopy\r\n"
    "Dim0Name=Z-Axis\r\nDim0Unit=m\r\nDim0Range=1e-06\r\nDim0Min=0\r\n"
    "Dim1Name=SpecPoint\r\nDim1Unit=\r\nDim1Range=4\r\nDim1Min=0\r\n"
    f"Dim2Name=Deflection\r\nDim2Unit=V\r\nDim2Range={SPEC_DIM2_RANGE}\r\nDim2Min={SPEC_DIM2_MIN}\r\n"
    "SaveMode=Binary\r\nSaveBits=32\r\nSaveSign=Signed\r\nSaveOrder=Intel\r\n"
)


def _make_synthetic_nid(tmp_path: Path) -> tuple[Path, bytes, bytes]:
    """Construye un .nid sintético con 2 canales y devuelve (path, raw_img, raw_spec)."""
    # raw=0 → norma = (0 + 2^31) / 2^32 = 0.5 → phys = Dim2Min + 0.5*Dim2Range
    raw_img = np.zeros((IMG_LINES, IMG_POINTS), dtype="<i4")
    raw_img[0, 0] = 2**30  # → norm = (2^30+2^31)/2^32 = 0.75 → phys = -1 + 0.75*2 = 0.5

    raw_spec = np.zeros((SPEC_LINES, SPEC_POINTS), dtype="<i4")
    raw_spec[0, 0] = 2**30  # → phys = 0 + 0.75*5 = 3.75

    blob = _HEADER_TEMPLATE.encode("latin-1") + b"#!" + raw_img.tobytes() + raw_spec.tobytes()
    p = tmp_path / "synthetic2ch.nid"
    p.write_bytes(blob)
    return p, raw_img.tobytes(), raw_spec.tobytes()


@pytest.fixture(scope="module")
def synthetic_nid(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("syn")
    path, _, _ = _make_synthetic_nid(tmp)
    return path


# ===========================================================================
# Extracción
# ===========================================================================


class TestExtraction:
    def test_marker_offset(self, synthetic_nid: Path) -> None:
        blob = synthetic_nid.read_bytes()
        expected = blob.find(b"#!")
        trace = trace_nid(synthetic_nid)
        assert trace.marker_offset == expected

    def test_n_channels(self, synthetic_nid: Path) -> None:
        trace = trace_nid(synthetic_nid)
        assert trace.n_channels == 2

    def test_channel_byte_offsets_and_lengths(self, synthetic_nid: Path) -> None:
        blob = synthetic_nid.read_bytes()
        marker = blob.find(b"#!")
        bin_start = marker + 2

        img_bytes = IMG_POINTS * IMG_LINES * 4
        spec_bytes = SPEC_POINTS * SPEC_LINES * 4

        trace = trace_nid(synthetic_nid)
        ch0 = trace.channels[0]
        ch1 = trace.channels[1]

        assert ch0.byte_offset == bin_start
        assert ch0.byte_length == img_bytes
        assert ch1.byte_offset == bin_start + img_bytes
        assert ch1.byte_length == spec_bytes

    def test_channel_shapes(self, synthetic_nid: Path) -> None:
        trace = trace_nid(synthetic_nid)
        assert trace.channels[0].lines == IMG_LINES
        assert trace.channels[0].points == IMG_POINTS
        assert trace.channels[1].lines == SPEC_LINES
        assert trace.channels[1].points == SPEC_POINTS


# ===========================================================================
# Formato (mapeo raw → físico)
# ===========================================================================


class TestFormat:
    def test_raw_zero_maps_to_midpoint(self, synthetic_nid: Path) -> None:
        """raw=0 → norm=0.5 → phys = Dim2Min + 0.5*Dim2Range."""
        data = load_nid(synthetic_nid)
        ch_img = data["Z-Axis"]
        # La imagen se voltea: raw[0,0] → última fila tras el flip.
        # Las celdas con raw=0 están en todas las posiciones excepto (0,0).
        expected = IMG_DIM2_MIN + 0.5 * IMG_DIM2_RANGE  # = 0.0
        # Verificar una celda que sabemos tiene raw=0 (no es [0,0] ni [-1,0] tras flip)
        assert ch_img.data[0, 1] == pytest.approx(expected, abs=1e-9)

    def test_raw_2pow30_maps_correctly(self, synthetic_nid: Path) -> None:
        """raw=2^30 → norm=0.75 → phys = Dim2Min + 0.75*Dim2Range."""
        data = load_nid(synthetic_nid)
        ch_img = data["Z-Axis"]
        # raw_img[0,0]=2^30; tras flipud la fila 0 pasa a ser la última
        expected = IMG_DIM2_MIN + 0.75 * IMG_DIM2_RANGE  # = 0.5
        assert ch_img.data[-1, 0] == pytest.approx(expected, abs=1e-6)

    def test_spec_channel_raw_zero(self, synthetic_nid: Path) -> None:
        """Canal espectroscopía raw=0 → phys = SPEC_DIM2_MIN + 0.5*SPEC_DIM2_RANGE."""
        data = load_nid(synthetic_nid)
        ch_spec = data["Deflection"]
        expected = SPEC_DIM2_MIN + 0.5 * SPEC_DIM2_RANGE  # = 2.5
        assert ch_spec.data[1, 0] == pytest.approx(expected, abs=1e-6)

    def test_spec_channel_raw_2pow30(self, synthetic_nid: Path) -> None:
        """Canal espectroscopía raw=2^30 → phys = 3.75."""
        data = load_nid(synthetic_nid)
        ch_spec = data["Deflection"]
        expected = SPEC_DIM2_MIN + 0.75 * SPEC_DIM2_RANGE  # = 3.75
        assert ch_spec.data[0, 0] == pytest.approx(expected, abs=1e-6)


# ===========================================================================
# Presupuesto de bytes
# ===========================================================================


class TestByteBudget:
    def test_block_sum_equals_binary_bytes(self, synthetic_nid: Path) -> None:
        trace = trace_nid(synthetic_nid)
        total = sum(ch.byte_length for ch in trace.channels)
        assert total == trace.binary_bytes

    def test_check_budget_passes(self, synthetic_nid: Path) -> None:
        trace = trace_nid(synthetic_nid)
        budget_chk = next(c for c in trace.checks if "suma de bloques" in c.name)
        assert budget_chk.passed


# ===========================================================================
# Orientación
# ===========================================================================


class TestOrientation:
    def test_image_channel_is_flipped(self, synthetic_nid: Path) -> None:
        """El canal imagen debe estar marcado como volteado en la traza."""
        trace = trace_nid(synthetic_nid)
        img_ch = trace.channels[0]
        assert img_ch.flipped is True

    def test_spec_channel_not_flipped(self, synthetic_nid: Path) -> None:
        """El canal espectroscopía NO debe estar volteado."""
        trace = trace_nid(synthetic_nid)
        spec_ch = trace.channels[1]
        assert spec_ch.flipped is False

    def test_load_nid_flips_image(self, synthetic_nid: Path) -> None:
        """load_nid aplica flipud a la imagen: raw[0,0]=2^30 aparece en la última fila."""
        data = load_nid(synthetic_nid)
        ch = data["Z-Axis"]
        # raw[0,0] tenía valor 2^30 → phys = 0.5; tras flipud está en [-1, 0]
        assert ch.data[-1, 0] == pytest.approx(0.5, abs=1e-6)
        # El resto de la última fila (raw=0 → phys=0) permanece en 0.0
        assert ch.data[-1, 1] == pytest.approx(0.0, abs=1e-9)

    def test_load_nid_does_not_flip_spec(self, synthetic_nid: Path) -> None:
        """El canal espectroscopía no se voltea: raw[0,0] sigue en fila 0."""
        data = load_nid(synthetic_nid)
        ch = data["Deflection"]
        # raw_spec[0,0] = 2^30 → phys = 3.75
        assert ch.data[0, 0] == pytest.approx(3.75, abs=1e-6)


# ===========================================================================
# Manipulación: roughness.statistics
# ===========================================================================


class TestManipulation:
    def test_roughness_sq_recovers_sigma(self) -> None:
        """Superficie gaussiana de σ=1.23 e media=0 → Sq ≈ 1.23."""
        rng = np.random.default_rng(2024)
        sigma = 1.23
        data = rng.normal(0.0, sigma, size=(64, 64))
        ch = SPMChannel(name="Z-Axis", data=data, unit="m", x_range=1e-6, y_range=1e-6)
        result = roughness.statistics(ch)
        assert result.Sq == pytest.approx(sigma, rel=0.05)

    def test_roughness_on_synthetic_channel(self, synthetic_nid: Path) -> None:
        """Aplicar roughness sobre canal imagen cargado no lanza error."""
        data = load_nid(synthetic_nid)
        ch = data["Z-Axis"]
        result = roughness.statistics(ch)
        assert result.Sq >= 0
        assert result.n_points == IMG_LINES * IMG_POINTS


# ===========================================================================
# Representación: round-trips CSV/JSON/HDF5/GWY
# ===========================================================================


class TestRepresentation:
    def test_csv_round_trip(self, synthetic_nid: Path, tmp_path: Path) -> None:
        import csv

        data = load_nid(synthetic_nid)
        ch = data["Z-Axis"]
        result = roughness.statistics(ch)
        out = tmp_path / "roughness.csv"
        to_csv(result, out)
        assert out.exists()
        with out.open(encoding="utf-8") as f:
            rows = list(csv.reader(f))
        keys = {row[0] for row in rows[1:]}
        assert "Sq" in keys
        assert "Sa" in keys

    def test_json_round_trip(self, synthetic_nid: Path, tmp_path: Path) -> None:
        data = load_nid(synthetic_nid)
        ch = data["Z-Axis"]
        result = roughness.statistics(ch)
        out = tmp_path / "roughness.json"
        to_json(result, out)
        assert out.exists()
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert "Sq" in loaded
        assert loaded["Sq"] == pytest.approx(result.Sq)

    def test_hdf5_round_trip(self, synthetic_nid: Path, tmp_path: Path) -> None:
        h5py = pytest.importorskip("h5py")
        from spmkit.core.export import to_hdf5

        data = load_nid(synthetic_nid)
        out = tmp_path / "data.h5"
        to_hdf5(data, out)
        assert out.exists()
        with h5py.File(out, "r") as f:
            names = []
            f.visititems(lambda name, _: names.append(name))
            assert len(names) > 0

    def test_gwy_round_trip(self, synthetic_nid: Path, tmp_path: Path) -> None:
        pytest.importorskip("gwyfile")
        from spmkit.core.io import save_gwy

        data = load_nid(synthetic_nid)
        out = tmp_path / "data.gwy"
        save_gwy(data, out)
        assert out.exists()


# ===========================================================================
# Cálculo: todos los checks del trace sintético pasan
# ===========================================================================


class TestCalculation:
    def test_all_checks_pass(self, synthetic_nid: Path) -> None:
        trace = trace_nid(synthetic_nid)
        failed = [c for c in trace.checks if not c.passed]
        assert failed == [], f"Checks fallidos: {[c.name for c in failed]}"

    def test_trace_ok_true(self, synthetic_nid: Path) -> None:
        trace = trace_nid(synthetic_nid)
        assert trace.ok is True

    def test_trace_returns_nidtrace(self, synthetic_nid: Path) -> None:
        trace = trace_nid(synthetic_nid)
        assert isinstance(trace, NidTrace)

    def test_n_sections_nonzero(self, synthetic_nid: Path) -> None:
        trace = trace_nid(synthetic_nid)
        assert trace.n_sections >= 3  # DataSet, DataSet-0:0, DataSet-1:0

    def test_binary_bytes_positive(self, synthetic_nid: Path) -> None:
        trace = trace_nid(synthetic_nid)
        assert trace.binary_bytes > 0

    def test_file_size_matches(self, synthetic_nid: Path) -> None:
        trace = trace_nid(synthetic_nid)
        assert trace.file_size == synthetic_nid.stat().st_size


# ===========================================================================
# Datos reales (skip si no hay archivos en reference/)
# ===========================================================================

_SAMPLES = Path(__file__).parents[2] / "reference" / "sample_files"
_NID_FILES = sorted(_SAMPLES.glob("**/*.nid")) if _SAMPLES.exists() else []


@pytest.mark.skipif(not _NID_FILES, reason="sin archivos .nid reales en reference/")
@pytest.mark.parametrize("path", _NID_FILES, ids=lambda p: p.name)
def test_real_nid_trace_ok(path: Path) -> None:
    """trace_nid sobre archivos reales → trace.ok y datos finitos."""
    trace = trace_nid(path)
    failed = [c.name for c in trace.checks if not c.passed]
    assert trace.ok, f"Checks fallidos en {path.name}: {failed}"
    for ch in trace.channels:
        assert np.isfinite(ch.phys_min)
        assert np.isfinite(ch.phys_max)
