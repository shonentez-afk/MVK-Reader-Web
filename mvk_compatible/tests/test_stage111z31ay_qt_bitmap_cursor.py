"""Stage111Z31AY: same-bitmap pmXor cursor on Qt at 150% DPR (synthetic)."""
import numpy as np
import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import QPointF

from .test_desktop_qt import qt_app
from .test_stage111z31a_x32dbg_visual_reference import (
    create_reference_fixture,
)
from mvk_compatible.core.tqgrapher_bitmap_xor_cursor import (
    source_bitmap_xor_cursor,
)


@pytest.mark.parametrize('mode', [0, 3])
def test_source_raster_cursor_is_one_bitmap_not_qt_overlay(
        qt_app, tmp_path, mode):
    from mvk_compatible.desktop.main_window import MainWindow

    win = MainWindow()
    win.show()
    manifest, _, _, _ = create_reference_fixture(
        tmp_path / f'original_mode_{mode}', mode=mode, n=1024, fs=65536)
    win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()
    before = np.asarray(
        win._full_spectrum['amplitude'], dtype='<f4').view('<u4').copy()

    for checkbox in (win.spec_source_grid_checkbox,
                     win.spec_source_raster_checkbox,
                     win.spec_source_series_checkbox):
        checkbox.click()
        qt_app.processEvents()
    model = win._spec_source_grid_model
    assert model['combined_preview_active']
    canvas = model['combined_canvas']
    base = win._spec_source_raster_data.copy()
    rect = win.spec_plot.getViewBox().sceneBoundingRect()
    mouse_x = (canvas['pixel_left'] + 30.25) / canvas['canvas_width'] * rect.width()
    win._spec_at_scene_pos(
        QPointF(rect.left() + mouse_x, rect.center().y()), force=True)
    pre_cursor = win._spec_last_cursor
    pre_status = win.statusBar().currentMessage()
    pre_signature = win._spec_source_grid_model['bitmap_viewport_signature']
    qt_app.processEvents()

    selected = win._spec_last_cursor
    assert selected is not None, (
        f'immediate={pre_cursor is not None}; status_before={pre_status}; '
        f'status_after={win.statusBar().currentMessage()}; '
        f'viewport_changed={pre_signature != win._spec_source_grid_model.get("bitmap_viewport_signature")}; '
        f'mouse_pixel={win._spec_mouse_pixel}')
    pixel_xy = (
        selected['source_bitmap_cursor_pixel_x'],
        selected['source_bitmap_cursor_pixel_y'])
    assert win._spec_source_cursor_raster_data is not None
    expected = source_bitmap_xor_cursor(
        base, canvas=canvas, cursor_pixel=pixel_xy)
    np.testing.assert_array_equal(
        win._spec_source_cursor_raster_data, expected)
    # The exact source logical pixels are now the ImageItem data;
    # no second physical-DPR-dependent Qt RasterOp crosshair.
    np.testing.assert_array_equal(
        win._spec_source_raster_item.image,
        np.ascontiguousarray(expected[::-1]))
    assert win.spec_xor_crosshair.cursor is None
    assert not win.spec_line.isVisible()
    assert not win.spec_hline.isVisible()
    np.testing.assert_array_equal(win._spec_source_raster_data, base)

    # The cursor leaves source PixelRect: original background bitmap restored
    # with no leftover XOR or stale line from last mouse position.
    win._spec_at_scene_pos(
        QPointF(rect.left() + 2., rect.center().y()), force=True)
    qt_app.processEvents()
    assert win._spec_last_cursor is None
    assert win._spec_source_cursor_raster_data is None
    np.testing.assert_array_equal(
        win._spec_source_raster_item.image,
        np.ascontiguousarray(base[::-1]))
    np.testing.assert_array_equal(
        np.asarray(
            win._full_spectrum['amplitude'], dtype='<f4').view('<u4'), before)
    win.close()
    qt_app.processEvents()


def test_zoom_after_bitmap_cursor_invalidates_native_mouse_and_bitmap(
        qt_app, tmp_path):
    from mvk_compatible.desktop.main_window import MainWindow

    win = MainWindow()
    win.show()
    manifest, _, _, _ = create_reference_fixture(
        tmp_path / 'source', mode=0, n=1024, fs=65536)
    win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()
    for c in (win.spec_source_grid_checkbox,
              win.spec_source_raster_checkbox,
              win.spec_source_series_checkbox):
        c.click()
        qt_app.processEvents()
    canvas = win._spec_source_grid_model['combined_canvas']
    vb = win.spec_plot.getViewBox()
    rect = vb.sceneBoundingRect()
    target_x = rect.left() + (
        (canvas['pixel_left'] + 20) / canvas['canvas_width']) * rect.width()
    win._spec_at_scene_pos(
        QPointF(target_x, rect.center().y()), force=True)
    assert win._spec_source_cursor_raster_data is not None
    old_image = win._spec_source_raster_item
    vb.setXRange(1100., 6100., padding=0.)
    qt_app.processEvents()
    assert win._spec_source_raster_item is not old_image
    assert old_image.scene() is None
    assert win._spec_source_cursor_raster_data is None
    assert win._spec_last_cursor is None
    assert win._spec_mouse_pixel is None
    assert win.spec_xor_crosshair.cursor is None
    win.close()
    qt_app.processEvents()
