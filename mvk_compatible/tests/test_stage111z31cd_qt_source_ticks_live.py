"""Actual Qt PageAdc/PageSpectrum 10-division axes, synthetic file only."""
from hashlib import sha256
import numpy as np
import pytest
pytest.importorskip("PySide6")

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31cc_qt_graph_layout_cursor import settle
from ..core.original_live_axis_ticks import source_live_axis_ticks
from ..desktop.source_plot_geometry import SourceTickAxis


def _assert_axis_source_ticks(plot):
    vb = plot.getViewBox()
    ranges = vb.viewRange()
    for name, (lo, hi) in zip(("bottom", "left"), ranges):
        axis = plot.getPlotItem().getAxis(name)
        assert isinstance(axis, SourceTickAxis)
        expected = source_live_axis_ticks(scr_left=lo, scr_width=hi-lo)
        calculated = axis.tickValues(lo, hi, 500)
        assert len(calculated) == 1
        step, positions = calculated[0]
        assert step == pytest.approx(expected["spacing_single"])
        assert list(positions) == list(expected["values"])
        labels = axis.tickStrings(positions, 1.0, step)
        assert labels == list(expected["texts"])
        assert 2 <= len(positions) <= 12
        assert axis.source_tick_model["source"] == expected["source"]
        assert not axis.source_tick_model["original_win32_runtime_ticks_verified"]


def test_both_live_pages_use_original_source_tick_numbers_after_scale_pan_resize(
        qt_app, tmp_path):
    from ..desktop.main_window import MainWindow

    src = fixture_zip(tmp_path, sample_count=8192)
    original_sha = sha256(src.read_bytes()).hexdigest()
    w = MainWindow()
    w.show()
    settle(qt_app)
    try:
        w.open_archive(src)
        assert w._full_spectrum is not None
        fft = np.asarray(w._full_spectrum["amplitude"]).copy()
        for page_index, plot in ((3, w.wave_plot), (4, w.spec_plot)):
            w.original_root_tabs.setCurrentIndex(page_index)
            settle(qt_app)
            _assert_axis_source_ticks(plot)
            assert plot.source_canvas_model["qt_logical_pixels"]
            x0, x1 = plot.getViewBox().viewRange()[0]
            width = x1 - x0
            # Narrowing a valid source viewport changes the tick division,
            # not the underlying GetSignal / full N/2 Power/Y.
            if width > 1e-5:
                plot.getViewBox().setXRange(
                    x0 + width * .1, x1 - width * .1, padding=0)
                settle(qt_app)
                _assert_axis_source_ticks(plot)
            w.resize(w.width() + 64, w.height() + 32)
            settle(qt_app)
            _assert_axis_source_ticks(plot)
        np.testing.assert_array_equal(w._full_spectrum["amplitude"], fft)
        assert sha256(src.read_bytes()).hexdigest() == original_sha
    finally:
        w.close()
        settle(qt_app)


def test_only_original_live_graphs_receive_source_tick_axis(qt_app):
    from ..desktop.main_window import MainWindow
    w = MainWindow()
    w.show()
    settle(qt_app)
    try:
        for plot in (w.wave_plot, w.spec_plot):
            assert isinstance(plot.getPlotItem().getAxis("bottom"),
                              SourceTickAxis)
            assert isinstance(plot.getPlotItem().getAxis("left"),
                              SourceTickAxis)
        assert not isinstance(
            w.original_status_plot.getPlotItem().getAxis("bottom"),
            SourceTickAxis)
    finally:
        w.close()
        settle(qt_app)
