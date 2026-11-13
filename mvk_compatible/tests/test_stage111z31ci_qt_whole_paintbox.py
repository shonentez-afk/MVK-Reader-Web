"""CI live Qt PageAdc/PageSpectrum: ONE source PaintBox GDI/Qt bitmap.

Synthetic archive only; native original Delphi process, physical device
and 0-ULP FFT/FRange are not contacted or claimed.
"""
from hashlib import sha256
import sys

import numpy as np
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QPointF

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31cc_qt_graph_layout_cursor import settle
from ..core.original_live_whole_paintbox import SOURCE as WHOLE_SOURCE
from ..core.original_live_plot_composite import SOURCE as CG_SOURCE
from ..desktop.source_paintbox_text_overlay import (
    SourcePaintBoxTextOverlay,
)


def _assert_same_source_paintbox(plot, expected_inverse):
    comp=plot.source_composite_overlay
    labels=plot.source_paintbox_text_overlay
    assert comp.source_series_bound
    plot.sync_source_geometry()
    assert comp.render_source_composite_now(),(
        comp.source_whole_paintbox_last_error,
        comp.source_composite_last_error)
    assert comp.isVisible()
    r=comp.source_composite_receipt
    assert r["source"]==CG_SOURCE  # established UI contract
    assert r["whole_paintbox_source"]==WHOLE_SOURCE
    assert r["source_textout_full_paintbox_implemented"]
    assert r["source_software_grid_and_series_and_frame_one_bitmap"]
    assert r["textout_calls"]==r["textout_event_count"]
    assert r["source_interleaved_tick_textout"]
    assert r["source_gdi_textout_per_matching_grid_tick"]
    assert r["series_stroke_count"]>0
    assert r["frame_stroke_count"]==4
    assert r["source_x_inverted"] is expected_inverse
    assert not r["original_win32_pixel_parity_verified"]
    assert isinstance(labels,SourcePaintBoxTextOverlay)
    assert labels.render_source_text_now(),labels.source_textout_last_error
    t=labels.source_textout_receipt
    assert t["source_one_paintbox_shared_buffer"]
    assert t["whole_paintbox_source"]==WHOLE_SOURCE
    assert t["source_bitmap_sha256"]==r["rgba_sha256"]
    assert t["source_raster_textout_before_series"]
    assert not t["original_gdi_pixel_parity_verified"]
    assert t["source_inverted_x"] is expected_inverse
    assert labels.isVisible()
    assert labels.geometry()==plot.viewport().rect()
    assert "x_tick" in t["axis_event_kinds"]
    assert "y_tick" in t["axis_event_kinds"]
    assert "x_name" in t["axis_event_kinds"]
    assert not plot.getPlotItem().getAxis("bottom").label.isVisible()
    assert not plot.getPlotItem().getAxis("left").label.isVisible()
    if sys.platform=="win32":
        assert t["textout_engine"]=="WIN32_GDI_DFM_TEXT_OUT"
        assert t["font_metrics_provenance"]=="gdi_reconstructed_from_dfm"
    else:
        assert t["textout_engine"]=="QT_GLYPHS_NOT_GDI"
    return r,t


def test_both_live_pages_use_one_full_paintbox_gdi_source(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    src=fixture_zip(tmp_path,sample_count=8192)
    input_sha=sha256(src.read_bytes()).hexdigest()
    win=MainWindow();win.show();settle(qt_app)
    try:
        win.open_archive(src)
        win.wave_hscale_menu.actions()[9].trigger() # source H=20 ms
        settle(qt_app)
        power=np.asarray(win._full_spectrum["amplitude"]).copy()
        for page,plot,inverted in ((3,win.wave_plot,True),
                                  (4,win.spec_plot,False)):
            win.original_root_tabs.setCurrentIndex(page)
            settle(qt_app)
            original,txt=_assert_same_source_paintbox(plot,inverted)
            count=plot.source_composite_overlay.source_composite_render_count
            # Cache valid current paintbox; no duplicate TextOut.
            assert plot.source_composite_overlay.render_source_composite_now()
            assert plot.source_composite_overlay.source_composite_render_count==count
            xr=plot.getViewBox().viewRange()[0]
            plot.getViewBox().setXRange(
                xr[0]+(xr[1]-xr[0])*.12,
                xr[1]-(xr[1]-xr[0])*.12,padding=0)
            settle(qt_app)
            changed,_=_assert_same_source_paintbox(plot,inverted)
            assert changed["source_series_sha256"]==original["source_series_sha256"]
            assert changed["textout_calls"]==changed["textout_event_count"]
            assert changed["source_interleaved_tick_textout"]
            assert plot.source_composite_overlay.source_composite_render_count>count
        np.testing.assert_array_equal(win._full_spectrum["amplitude"],power)
        assert sha256(src.read_bytes()).hexdigest()==input_sha
    finally:
        win.close();settle(qt_app)


def test_whole_paintbox_cursor_and_other_pages_keep_independent_owners(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    win=MainWindow();win.show();settle(qt_app)
    try:
        win.open_archive(fixture_zip(tmp_path,sample_count=8192))
        win.wave_hscale_menu.actions()[9].trigger()
        win.original_root_tabs.setCurrentIndex(4)
        settle(qt_app)
        plot=win.spec_plot
        _assert_same_source_paintbox(plot,False)
        point=plot.getViewBox().sceneBoundingRect()
        win._spec_at_scene_pos(
            QPointF(point.center().x(),point.center().y()),force=True)
        assert win.spec_xor_crosshair.cursor is not None
        assert not hasattr(win.original_status_plot,
                           "source_paintbox_text_overlay")
        assert win.original_root_tabs.count()==7
        plot.enable_source_grid(False)
        assert not plot.source_composite_overlay.isVisible()
        assert not plot.source_paintbox_text_overlay.isVisible()
        plot.enable_source_grid(True)
        settle(qt_app)
        _assert_same_source_paintbox(plot,False)
        # Old CG data curves still represent true full source samples.
        assert len(plot.getPlotItem().listDataItems())>=1
        plot.clear_source_tqgr_series()
        assert not plot.source_composite_overlay.source_series_bound
        assert not plot.source_paintbox_text_overlay.isVisible()
        assert plot.getPlotItem().getAxis("bottom").label.isVisible()
    finally:
        win.close();settle(qt_app)


@pytest.mark.skipif(sys.platform!="win32",reason="native Win32 GDI only")
def test_source_dfm_font_metrics_are_cached_not_reopened_per_zoom(qt_app):
    from ..desktop.source_paintbox_text_overlay import (
        source_paintbox_font_metrics,
        _source_gdi_dfm_metrics_cached,
    )
    _source_gdi_dfm_metrics_cached.cache_clear()
    first=source_paintbox_font_metrics()
    second=source_paintbox_font_metrics()
    assert first==second
    stat=_source_gdi_dfm_metrics_cached.cache_info()
    assert stat.misses==1 and stat.hits>=1
    assert first["font_metrics_provenance"]=="gdi_reconstructed_from_dfm"
    assert not first["source_native_original_font_verified"]
