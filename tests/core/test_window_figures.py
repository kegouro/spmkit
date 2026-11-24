"""Batch figures from generated NID acquisitions. No experimental files."""

import csv

import numpy as np
import pytest
from PIL import Image

from spmkit.core.adhesion_review import review_maps
from spmkit.core.analysis.force_windows import WindowOptions, select_windows
from spmkit.core.force_window_batch import analyze_window_files
from spmkit.core.viz.window_figures import CurvePanel, export_batch_figures, render_panel
from tests.core.test_adhesion_review import write_adhesion_map
from tests.core.test_force_windows import curve, write_map


def test_full_trace_exact_windows_detail_limits_and_legend():
    x = np.arange(640) * 1e-9
    f = 0.04 * x
    f[175:] += 1.5e-9
    f[450:] -= 1e-9
    c = curve(x, f)
    windows = select_windows(c, WindowOptions("steps"))
    assert [w.boundary for w in windows] == [175, 450]
    fig = render_panel(c, CurvePanel(0, tuple(windows)), "test.nid", "extend", "steps")
    fig.canvas.draw()
    full, *details = fig.axes
    np.testing.assert_allclose(full.lines[0].get_ydata(), f * 1e9)
    assert len(details) == 2
    for ax, w in zip(details, windows, strict=True):
        lo, hi = ax.get_xlim()
        assert lo < w.start < w.end < hi
        assert hi - lo < 60
        assert np.ptp(ax.get_ylim()) < np.ptp(full.get_ylim())
    legend = fig.legends[0].get_window_extent()
    assert all(not legend.overlaps(ax.bbox) for ax in fig.axes)
    assert all(not legend.overlaps(t.get_window_extent()) for t in fig.texts)
    assert fig.bbox.contains(legend.x1, legend.y1)
    fig.clear()


def test_same_names_distinct_maps_and_unchanged_source_guard(tmp_path):
    paths = []
    for d in ("a", "b"):
        folder = tmp_path / d
        folder.mkdir()
        p = folder / "mapa.nid"
        write_map(p, 2, True)
        paths.append(p)
    out = tmp_path / "out"
    out.mkdir()
    b = analyze_window_files(paths, WindowOptions("contact", tip_radius_nm=100, max_depth_nm=12))
    directory = export_batch_figures(b, out)
    with (directory / "indice.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert [(int(r["mapa"]), int(r["curva"])) for r in rows] == [(0, 0), (0, 1), (1, 0), (1, 1)]
    assert all(r["ventanas"] == "1" for r in rows)
    for r in rows:
        with Image.open(directory / r["imagen"]) as im:
            assert im.width == 2880 and round(im.info["dpi"][0]) == 300
    kept = set(out.iterdir())

    def stop(fraction, message):
        if fraction > 0:
            raise RuntimeError("cancel")

    with pytest.raises(RuntimeError, match="cancel"):
        export_batch_figures(b, out, stop)
    assert set(out.iterdir()) == kept
    paths[1].write_bytes(b"changed synthetic data")
    with pytest.raises(ValueError, match="cambió"):
        export_batch_figures(b, out)
    assert set(out.iterdir()) == kept


def test_adhesion_exclusions_and_branch_without_window(tmp_path):
    p = tmp_path / "mapa.nid"
    write_adhesion_map(p, 3, retract=False)
    maps, _ = review_maps([p])
    maps[0].curves[1].included = False
    out = export_batch_figures(maps, tmp_path)
    with (out / "indice.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert [r["curva"] for r in rows] == ["0", "2"]
    assert all(r["ventanas"] == "0" and "retracción" in r["nota"] for r in rows)
    assert (out / "seleccion.csv").exists()
    assert len(list(out.glob("*/*.png"))) == 2

    # The same inclusion decisions also apply when running the automatic selector.
    b = analyze_window_files(
        [p], WindowOptions("steps", "retract"), selection={p: (maps[0].digest, frozenset([0, 2]))}
    )
    out2 = export_batch_figures(b, tmp_path)
    assert len(list(out2.glob("*/*.png"))) == 2
    with (out2 / "indice.csv").open() as f:
        assert [r["curva"] for r in csv.DictReader(f)] == ["0", "2"]
