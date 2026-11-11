"""Stage111Z31AX source bitmap pan/cursor Qt regression, synthetic data only."""
import numpy as np
import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import QPointF
from .test_desktop_qt import qt_app
from .test_stage111z31a_x32dbg_visual_reference import create_reference_fixture
from mvk_compatible.core.tqgrapher_viewport_sync_source import (
    bitmap_cursor_overlay_coordinates)


def test_source_bitmap_small_pan_rebuild_and_inset_cursor(qt_app,tmp_path):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    manifest,_,_,_=create_reference_fixture(
        tmp_path/'source',mode=0,n=1024,fs=65536)
    win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()
    before=np.asarray(
        win._full_spectrum['amplitude'],dtype='<f4').view('<u4').copy()
    for button in (win.spec_source_grid_checkbox,
                   win.spec_source_raster_checkbox,
                   win.spec_source_series_checkbox):
        button.click()
        qt_app.processEvents()
    assert win._spec_source_grid_model['combined_preview_active']
    vb=win.spec_plot.getViewBox()
    vb.setXRange(1100.,6100.,padding=0.)
    qt_app.processEvents()
    old_item=win._spec_source_raster_item
    old_sig=win._spec_source_grid_model['bitmap_viewport_signature']
    old_ticks=tuple(win._spec_source_grid_model['x_grid_ticks'])
    vb.setXRange(1101.,6101.,padding=0.)
    qt_app.processEvents()
    model=win._spec_source_grid_model
    assert model['bitmap_viewport_signature']!=old_sig
    assert tuple(model['x_grid_ticks'])==old_ticks
    assert win._spec_source_raster_item is not old_item
    assert old_item.scene() is None

    canvas=model['combined_canvas']
    rect=vb.sceneBoundingRect()
    mouse_x=(canvas['pixel_left']+24.25)/canvas['canvas_width']*rect.width()
    win._spec_at_scene_pos(
        QPointF(rect.left()+mouse_x,rect.center().y()),force=True)
    cursor=win._spec_last_cursor
    assert cursor is not None
    assert cursor['independent_itos_source_supplied']
    assert canvas['pixel_left']<cursor['pixel']<canvas['pixel_right']
    overlay=bitmap_cursor_overlay_coordinates(
        canvas=canvas,bin_index=cursor['selected_bin'],
        raw_y=float(win._full_spectrum['amplitude'][cursor['selected_bin']]),
        view_x=tuple(vb.viewRange()[0]),view_y=tuple(vb.viewRange()[1]))
    assert win.spec_line.value()==overlay['qt_x']
    assert win.spec_hline.value()==overlay['qt_y']
    win._spec_at_scene_pos(
        QPointF(rect.left()+2.,rect.center().y()),force=True)
    assert win._spec_last_cursor is None
    np.testing.assert_array_equal(
        np.asarray(win._full_spectrum['amplitude'],dtype='<f4').view('<u4'),
        before)
    win.close()
    qt_app.processEvents()
