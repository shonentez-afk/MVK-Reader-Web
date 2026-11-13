"""Real PageAdc/PageSpectrum source grid + clGreen XOR on synthetic ZIP.

The source PaintBox clipping contract is not a Win32 screenshot proof.
"""
from hashlib import sha256

import numpy as np
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import QPointF

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31cc_qt_graph_layout_cursor import settle
from ..core.original_live_grid_cursor import (
    source_live_grid_frame,source_live_cursor_hit,
    source_live_clip_crosshair,
)
from ..desktop.source_plot_geometry import SourceGeometryPlot
from ..desktop.source_live_grid import SourceLiveGridOverlay
from ..desktop.xor_cursor_overlay import QtSpectrumXorCursor


def _live(plot):
    assert isinstance(plot,SourceGeometryPlot)
    overlay=plot.source_grid_overlay
    assert isinstance(overlay,SourceLiveGridOverlay)
    assert overlay.isVisible()
    assert overlay.scene() is not None
    overlay.sync_source_grid()
    model=overlay.source_grid_model
    assert model is not None
    r=plot.getViewBox().viewRect()
    expected=source_live_grid_frame(
        view_x=(r.left(),r.right()),view_y=(r.top(),r.bottom()))
    assert model==expected
    assert model["source_grid_hex"]=="#c0c0c0"
    return model


def _select_middle_scene(plot):
    r=plot.getViewBox().sceneBoundingRect()
    return QPointF(r.left()+r.width()*.5,r.center().y())


def test_both_live_page_grid_and_cursor_are_shown_without_replacing_full_data(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    src=fixture_zip(tmp_path,sample_count=8192)
    digest=sha256(src.read_bytes()).hexdigest()
    w=MainWindow();w.show();settle(qt_app)
    try:
        w.open_archive(src)
        # The source ADC H=20 ms tag has a complete real sample window
        # inside this bounded synthetic archive. Do not test a mismatched
        # 1-second research default against the full-history GetSignal gate.
        w.wave_hscale_menu.actions()[9].trigger()
        settle(qt_app)
        fft=np.asarray(w._full_spectrum["amplitude"]).copy()
        for page,plot,handler,overlay_attr,line_attr in [
            (3,w.wave_plot,w._wave_at_scene_pos,
             "wave_xor_crosshair","wave_line"),
            (4,w.spec_plot,w._spec_at_scene_pos,
             "spec_xor_crosshair","spec_line"),
        ]:
            w.original_root_tabs.setCurrentIndex(page)
            settle(qt_app)
            model=_live(plot)
            pos=_select_middle_scene(plot)
            hit=source_live_cursor_hit(
                canvas=plot.source_canvas_model,
                scene_left=plot.getViewBox().sceneBoundingRect().left(),
                scene_right=plot.getViewBox().sceneBoundingRect().right(),
                scene_x=pos.x())
            assert hit["inside_original_pixel_rect"]
            handler(pos,force=True)
            xor=getattr(w,overlay_attr)
            assert isinstance(xor,QtSpectrumXorCursor)
            assert xor.cursor is not None, (
                f"page={page}, active_window={w.original_root_tabs.currentIndex()}, "
                f"status={w.statusBar().currentMessage()!r}, "
                f"wave={w.wave_hint.text() if page==3 else 'n/a'}, "
                f"spec={w.spec_hint.text() if page==4 else 'n/a'}")
            assert getattr(w,line_attr).isVisible()
            assert len(model["x_ticks"])>=2
            handler(QPointF(plot.getViewBox().sceneBoundingRect().left(),
                            pos.y()),force=True)
            assert xor.cursor is None
            assert not getattr(w,line_attr).isVisible()
            handler(pos,force=True)
            assert xor.cursor is not None
            xr=plot.getViewBox().viewRange()[0]
            plot.getViewBox().setXRange(
                xr[0]+.1*(xr[1]-xr[0]),
                xr[1]-.1*(xr[1]-xr[0]),padding=0)
            settle(qt_app)
            assert xor.cursor is None
            _live(plot)
        np.testing.assert_array_equal(w._full_spectrum["amplitude"],fft)
        assert sha256(src.read_bytes()).hexdigest()==digest
    finally:
        w.close();settle(qt_app)


def test_source_grid_survives_real_refresh_and_research_visibility_toggle(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    w=MainWindow();w.show();settle(qt_app)
    try:
        w.open_archive(fixture_zip(tmp_path,sample_count=8192))
        for plot,refresh in ((w.wave_plot,w.refresh_wave),
                             (w.spec_plot,w.refresh_spec)):
            overlay=plot.source_grid_overlay
            _live(plot)
            refresh();settle(qt_app)
            assert plot.source_grid_overlay is overlay
            _live(plot)
            plot.enable_source_grid(False)
            assert not overlay.isVisible()
            plot.enable_source_grid(True)
            _live(plot)
        # Status remains a separate graph and never receives source strokes.
        assert not hasattr(w.original_status_plot,"source_grid_overlay")
    finally:w.close();settle(qt_app)


def test_xor_y_clipped_at_viewport_but_original_full_value_unchanged(qt_app):
    from ..desktop.main_window import MainWindow
    w=MainWindow();w.show();settle(qt_app)
    try:
        for plot in (w.wave_plot,w.spec_plot):
            rect=plot.getViewBox().viewRect()
            x=rect.center().x()
            far_y=rect.top()-1000.*abs(rect.height())
            clip=source_live_clip_crosshair(
                left=rect.left(),right=rect.right(),
                top=rect.top(),bottom=rect.bottom(),x=x,y=far_y)
            assert clip is not None
            assert clip["y"]==rect.top()
            assert clip["raw_y_unchanged"]==far_y
            assert clip["y_clipped_for_presentation"]
    finally:w.close();settle(qt_app)
