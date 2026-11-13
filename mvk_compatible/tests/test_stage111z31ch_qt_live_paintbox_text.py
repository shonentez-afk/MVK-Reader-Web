"""CH actual PageAdc and PageSpectrum source full-PaintBox font plane.

Only synthetic offline ZIP; not a proof of original Windows pixel parity.
"""
from hashlib import sha256
import sys
import numpy as np
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt, QPointF

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31cc_qt_graph_layout_cursor import settle
from ..desktop.source_paintbox_text_overlay import (
    SourcePaintBoxTextOverlay, source_paintbox_font_metrics,
)
from ..core.original_live_paintbox_text import SOURCE


def _assert_native_canvas_text(plot, expected_inverse):
    layer=plot.source_paintbox_text_overlay
    assert isinstance(layer,SourcePaintBoxTextOverlay)
    assert layer.render_source_text_now(),layer.source_textout_last_error
    r=layer.source_textout_receipt
    assert r["source"]==SOURCE
    assert r["axis_event_count"]>=12
    assert "x_tick" in r["axis_event_kinds"]
    assert "y_tick" in r["axis_event_kinds"]
    assert "x_name" in r["axis_event_kinds"]
    assert len(r["axis_glyph_sha256"])==64
    assert r["source_inverted_x"] is expected_inverse
    assert r["source_dfm_font_family"]=="Tahoma"
    assert r["source_dfm_font_height"]==-13
    assert r["source_dfm_design_ppi"]==96
    assert not r["native_original_font_verified"]
    assert not r["original_whole_tcanvas_bitmap_implemented"]
    assert not r["original_gdi_pixel_parity_verified"]
    if sys.platform=="win32":
        assert r["textout_engine"]=="WIN32_GDI_DFM_TEXT_OUT"
        assert r["native_gdi_metrics"]["requested_font_height"]==-13
        assert r["font_metrics_provenance"]=="gdi_reconstructed_from_dfm"
    else:
        assert r["textout_engine"]=="QT_GLYPHS_NOT_GDI"
        assert r["font_metrics_provenance"]=="qt_approximation"
    axes=(plot.getPlotItem().getAxis("bottom"),
          plot.getPlotItem().getAxis("left"))
    assert not axes[0].label.isVisible()
    assert not axes[1].label.isVisible()
    assert layer.testAttribute(Qt.WA_TransparentForMouseEvents)
    assert layer.geometry()==plot.viewport().rect()
    assert layer.isVisible()
    assert plot.source_composite_overlay.source_series_bound
    assert plot.source_composite_overlay.render_source_composite_now()
    # The full source PaintBox glyphs are margins only; they do
    # not replace the original data/FFT or intercept mouse input.
    return r


def test_both_live_pages_use_source_paintbox_gdi_or_explicit_qt_fallback(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    archive=fixture_zip(tmp_path,sample_count=8192)
    archive_sha=sha256(archive.read_bytes()).hexdigest()
    w=MainWindow();w.show();settle(qt_app)
    try:
        w.open_archive(archive)
        w.wave_hscale_menu.actions()[9].trigger()
        settle(qt_app)
        full_fft=np.asarray(w._full_spectrum["amplitude"]).copy()
        for page,plot,invert in ((3,w.wave_plot,True),
                                 (4,w.spec_plot,False)):
            w.original_root_tabs.setCurrentIndex(page)
            settle(qt_app)
            receipt=_assert_native_canvas_text(plot,invert)
            first_sha=receipt["axis_glyph_sha256"]
            xr=plot.getViewBox().viewRange()[0]
            plot.getViewBox().setXRange(
                xr[0]+(xr[1]-xr[0])*.11,
                xr[1]-(xr[1]-xr[0])*.11,padding=0)
            settle(qt_app)
            changed=_assert_native_canvas_text(plot,invert)
            assert changed["source_paintbox_canvas"]["pixel_left"]>=0
            assert changed["source_textout_placements"]["events"]
            # The range or glyph hash may change; an exact 10x10
            # shift can still look identical, so do not assert a
            # different image digest after every zoom.
            if changed["axis_glyph_sha256"]==first_sha:
                assert changed["source_paintbox_canvas"] is not None
        np.testing.assert_array_equal(w._full_spectrum["amplitude"],full_fft)
        assert sha256(archive.read_bytes()).hexdigest()==archive_sha
    finally:
        w.close();settle(qt_app)


def test_native_axis_layer_clears_without_leaking_into_research_or_status(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    w=MainWindow();w.show();settle(qt_app)
    try:
        w.open_archive(fixture_zip(tmp_path,sample_count=8192))
        w.original_root_tabs.setCurrentIndex(4)
        settle(qt_app)
        plot=w.spec_plot
        _assert_native_canvas_text(plot,False)
        plot.clear_source_tqgr_series()
        assert not plot.source_paintbox_text_overlay.isVisible()
        assert plot.source_paintbox_text_overlay.source_textout_receipt is None
        for axisname in ("bottom","left"):
            axis=plot.getPlotItem().getAxis(axisname)
            assert axis.label.isVisible()
        assert not hasattr(w.original_status_plot,
                           "source_paintbox_text_overlay")
        plot.enable_source_grid(False)
        assert not plot.source_paintbox_text_overlay.isVisible()
        plot.enable_source_grid(True)
        assert not plot.source_paintbox_text_overlay.isVisible()
    finally:
        w.close();settle(qt_app)


@pytest.mark.skipif(sys.platform!="win32",reason="native Win32 GDI required")
def test_windows_uses_actual_gdi_font_metrics_for_source_plot_geometry(
        qt_app):
    from ..desktop.source_plot_geometry import SourceGeometryPlot
    p=SourceGeometryPlot(background="#ffffff")
    p.setLabel("bottom","Гц")
    p.setLabel("left","дБ")
    p.show();settle(qt_app)
    try:
        p.sync_source_geometry()
        report=p.source_canvas_model
        native=source_paintbox_font_metrics()
        assert native["font_metrics_provenance"]=="gdi_reconstructed_from_dfm"
        assert native["requested_font_height"]==-13
        assert report["source_font_metrics_backend"]=="gdi_reconstructed_from_dfm"
        assert report["source_dfm_font_height"]==-13
        assert not report["original_canvas_font_metrics_verified"]
    finally:
        p.close();settle(qt_app)
