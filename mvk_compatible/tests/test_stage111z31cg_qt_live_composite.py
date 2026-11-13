"""CG real Qt: whole source grid+series+frame, original data kept.

No original Win32 screen/physical calibration or instrument is used.
"""
from hashlib import sha256
import numpy as np
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import QPointF

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31cc_qt_graph_layout_cursor import settle
from ..desktop.source_live_composite import SourceLiveCompositeOverlay
from ..core.original_live_plot_composite import SOURCE


def _receipt(plot):
    overlay=plot.source_composite_overlay
    assert isinstance(overlay,SourceLiveCompositeOverlay)
    assert overlay.source_series_bound
    assert overlay.render_source_composite_now(),overlay.source_composite_last_error
    assert overlay.isVisible()
    assert overlay.scene() is not None
    report=overlay.source_composite_receipt
    assert report["source"]==SOURCE
    assert report["source_software_grid_and_series_and_frame_one_bitmap"]
    assert report["series_stroke_count"]>0
    assert report["frame_stroke_count"]==4
    assert report["source_series_samples"]>2
    if "whole_paintbox_source" in report:
        assert report["source_textout_full_paintbox_implemented"]
        assert report["source_gdi_textout_interposed_before_series"]
        assert not report["original_win32_pixel_parity_verified"]
    else:
        # Accepted CG fallback remains available if Font/PixelRect is
        # unmeasured or native GDI rejects the complete PaintBox.
        assert not report["source_textout_full_paintbox_implemented"]
    assert not report["original_win32_gdi_pixel_parity_verified"]
    assert report["rgba_sha256"] and len(report["rgba_sha256"])==64
    assert len(plot.getPlotItem().listDataItems())>=1
    assert overlay.zValue() > plot.source_frame_overlay.zValue()
    return report


def test_verified_real_wave_and_spectrum_source_composites_after_original_hscale(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    src=fixture_zip(tmp_path,sample_count=8192)
    input_sha=sha256(src.read_bytes()).hexdigest()
    win=MainWindow();win.show();settle(qt_app)
    try:
        win.open_archive(src)
        win.wave_hscale_menu.actions()[9].trigger()
        settle(qt_app)
        fft=np.asarray(win._full_spectrum["amplitude"]).copy()
        for tab,plot in ((3,win.wave_plot),(4,win.spec_plot)):
            win.original_root_tabs.setCurrentIndex(tab)
            settle(qt_app)
            model=_receipt(plot)
            if tab==3:
                assert model["source_x_inverted"] is True
                assert win.wave_line is not None
                assert win._source_wave_xaxes_model is not None
            else:
                assert not model["source_x_inverted"]
                assert model["source_series_samples"]==win._spec_display_contract[
                    "grapher_series_bins"]
                assert win._archive_raw_line is not None
            n=plot.source_composite_overlay.source_composite_render_count
            assert plot.source_composite_overlay.render_source_composite_now()
            assert plot.source_composite_overlay.source_composite_render_count==n
            xrange=plot.getViewBox().viewRange()[0]
            plot.getViewBox().setXRange(
                xrange[0]+(xrange[1]-xrange[0])*.12,
                xrange[1]-(xrange[1]-xrange[0])*.12,padding=0)
            settle(qt_app)
            next_model=_receipt(plot)
            assert next_model["view_x"]!=model["view_x"]
            assert plot.source_composite_overlay.source_composite_render_count>n
        np.testing.assert_array_equal(win._full_spectrum["amplitude"],fft)
        assert sha256(src.read_bytes()).hexdigest()==input_sha
    finally:
        win.close();settle(qt_app)


def test_cursor_and_fallback_have_source_provenance_without_double_data(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    win=MainWindow();win.show();settle(qt_app)
    try:
        win.open_archive(fixture_zip(tmp_path,sample_count=8192))
        win.wave_hscale_menu.actions()[9].trigger()
        win.original_root_tabs.setCurrentIndex(4)
        settle(qt_app)
        plot=win.spec_plot
        overlay=plot.source_composite_overlay
        assert overlay.render_source_composite_now()
        rect=plot.getViewBox().sceneBoundingRect()
        pos=QPointF(rect.left()+rect.width()*.5,rect.center().y())
        win._spec_at_scene_pos(pos,force=True)
        assert win.spec_xor_crosshair.cursor is not None
        selected=win._spec_last_cursor["selected_bin"]
        assert selected>=0
        count=len(plot.getPlotItem().listDataItems())
        assert count>=1
        plot.clear_source_tqgr_series()
        assert not overlay.source_series_bound
        assert not overlay.isVisible()
        assert plot.source_grid_overlay.isVisible()
        assert len(plot.getPlotItem().listDataItems())==count
        plot.enable_source_grid(False)
        assert not plot.source_grid_overlay.isVisible()
        assert not plot.source_frame_overlay.isVisible()
        assert not overlay.isVisible()
        plot.enable_source_grid(True)
        assert plot.source_grid_overlay.isVisible()
    finally:
        win.close();settle(qt_app)
