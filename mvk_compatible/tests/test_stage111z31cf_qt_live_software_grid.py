"""Actual TCo2Draw scanline grid and source frame in BOTH real Qt pages."""
from hashlib import sha256
import numpy as np
import pytest
pytest.importorskip("PySide6")

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31cc_qt_graph_layout_cursor import settle
from ..desktop.main_window import MainWindow
from ..desktop.source_live_grid import (
    SourceLiveGridOverlay, SourceLiveFrameOverlay,
)
from ..core.original_live_software_grid import SOURCE


def _assert_software_grid(plot):
    overlay=plot.source_grid_overlay
    assert isinstance(overlay,SourceLiveGridOverlay)
    assert isinstance(plot.source_frame_overlay,SourceLiveFrameOverlay)
    assert overlay.isVisible() and plot.source_frame_overlay.isVisible()
    overlay.sync_source_grid()
    assert overlay.render_source_grid_bitmap_now()
    receipt=overlay.source_software_raster_receipt
    assert receipt is not None
    assert receipt["source"]==SOURCE
    assert receipt["source_actual_software_grid_raster_not_qt_pen"]
    assert not receipt["original_win32_pixel_parity_verified"]
    assert overlay._image is not None
    pixels=overlay.source_software_rgba
    assert pixels is not None and not pixels.flags.writeable
    assert sha256(pixels.tobytes()).hexdigest()==receipt["rgba_sha256"]
    assert pixels.shape[:2]==(receipt["logical_size"][1],
                             receipt["logical_size"][0])
    # Source software line antialiasing blends gray ink with white:
    # subpixel line centers may have NO pixel exactly equal to 192.
    assert np.any(np.all(
        (pixels[:,:,:3]>=[192,192,192]) &
        (pixels[:,:,:3]<[255,255,255]),axis=2))
    return receipt


def test_both_actual_pages_use_software_grid_and_preserve_complete_fft(
        qt_app,tmp_path):
    p=fixture_zip(tmp_path,sample_count=8192)
    sha=sha256(p.read_bytes()).hexdigest()
    w=MainWindow();w.show();settle(qt_app)
    try:
        w.open_archive(p)
        w.wave_hscale_menu.actions()[9].trigger()
        fft=np.asarray(w._full_spectrum["amplitude"]).copy()
        for page,plot in ((3,w.wave_plot),(4,w.spec_plot)):
            w.original_root_tabs.setCurrentIndex(page);settle(qt_app)
            first=_assert_software_grid(plot)
            # Grid must be recalculated at a new viewport, not rescaled
            # from stale pixels; numerical data remain untouched.
            xr=plot.getViewBox().viewRange()[0]
            plot.getViewBox().setXRange(
                xr[0]+(xr[1]-xr[0])*.15,
                xr[1]-(xr[1]-xr[0])*.15,padding=0)
            settle(qt_app)
            second=_assert_software_grid(plot)
            assert second["view_x"]!=first["view_x"]
            assert plot.source_grid_overlay._image_signature[-2:] == second[
                "logical_size"]
            assert plot.source_grid_overlay.source_software_raster_receipt is not None
            # A source 10x10 division grid can be *pixel-identical*
            # after zoom despite new physical X labels. The signature,
            # not differing bitmap bytes, proves stale-range exclusion.
            assert plot.source_grid_overlay._image_signature[:2] == second["view_x"]
            assert plot.source_frame_overlay.scene() is not None
            # Research bitmap explicitly disables BOTH ordinary overlays.
            plot.enable_source_grid(False)
            assert not plot.source_grid_overlay.isVisible()
            assert not plot.source_frame_overlay.isVisible()
            plot.enable_source_grid(True)
            assert plot.source_frame_overlay.isVisible()
        np.testing.assert_array_equal(w._full_spectrum["amplitude"],fft)
        assert sha256(p.read_bytes()).hexdigest()==sha
    finally:w.close();settle(qt_app)


def test_software_raster_persists_across_actual_plotitem_clear(
        qt_app,tmp_path):
    w=MainWindow();w.show();settle(qt_app)
    try:
        w.open_archive(fixture_zip(tmp_path,sample_count=8192))
        w.original_root_tabs.setCurrentIndex(3);settle(qt_app)
        live=w.wave_plot.source_grid_overlay
        _assert_software_grid(w.wave_plot)
        w.refresh_wave();settle(qt_app)
        assert w.wave_plot.source_grid_overlay is live
        _assert_software_grid(w.wave_plot)
        w.original_root_tabs.setCurrentIndex(4);settle(qt_app)
        live=w.spec_plot.source_grid_overlay
        _assert_software_grid(w.spec_plot)
        w.refresh_spec();settle(qt_app)
        assert w.spec_plot.source_grid_overlay is live
        _assert_software_grid(w.spec_plot)
        assert not hasattr(
            w.original_status_plot,"source_software_raster_receipt")
    finally:w.close();settle(qt_app)
