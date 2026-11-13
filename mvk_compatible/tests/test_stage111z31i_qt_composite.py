"""Stage111Z31I: unified original-order software bitmap is reversible.

Synthetic manifests only. This is Qt logical preview, NOT Win32 pixel diff.
"""
import numpy as np
from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31a_x32dbg_visual_reference import create_reference_fixture


def _float32_words(win):
    return np.asarray(win._full_spectrum['amplitude'],
                      dtype='<f4').view('<u4').copy()


def _enable_combined(win,qt_app):
    win.spec_source_grid_checkbox.click()
    qt_app.processEvents()
    win.spec_source_raster_checkbox.click()
    qt_app.processEvents()
    assert win._spec_source_raster_item is not None
    assert not win._spec_source_grid_model.get('combined_preview_active',False)
    win.spec_source_series_checkbox.click()
    qt_app.processEvents()
    assert win.spec_source_grid_checkbox.isChecked()
    assert win.spec_source_raster_checkbox.isChecked()
    assert win.spec_source_series_checkbox.isChecked()
    assert win._spec_source_grid_model['combined_preview_active']
    assert win._spec_source_grid_lines==[]
    assert win._spec_source_series_item is not None
    assert not win._spec_source_series_item.isVisible()
    assert not win._spec_source_series_raw_item.isVisible()
    assert win._spec_source_raster_item is not None


def test_tqgr_source_composite_one_bitmap_four_original_modes(
        tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    for mode in range(4):
        win=MainWindow()
        win.show()
        manifest,_,_,_=create_reference_fixture(
            tmp_path/f'tag{mode}',mode=mode,n=1024,fs=65536)
        win.show_original_spectrum_reference(manifest)
        qt_app.processEvents()
        source=_float32_words(win)
        summary=win._spectrum_summary.copy()
        _enable_combined(win,qt_app)
        model=win._spec_source_grid_model
        pixels=win._spec_source_raster_data
        assert pixels.shape[2]==4 and pixels.dtype==np.uint8
        assert np.all(pixels[:,:,3]==255)
        # TCo2Draw coverage blends gray ink with white at fractional
        # pixel positions. Source-sized rectangles need not contain a
        # fully covered (exactly 192) gray pixel at this canvas size.
        rgb=pixels[:,:,:3]
        assert model['tco2draw_source_style']['source_grid_line_color_hex']=='#c0c0c0'
        assert np.any(np.all((rgb>=192)&(rgb<255),axis=2))
        assert np.any(np.all(pixels[:,:,:3]==[0,0,0],axis=2))
        # Original Unit115 counts integer ticks inside current screen
        # with 0.0001 tolerance; a zoomed Y range may have 10, not 11.
        assert model['combined_grid_segments']==(
            len(model['x_grid_ticks'])+len(model['y_grid_ticks']))
        assert model['combined_series_segments']>0
        assert model['combined_frame_segments']==4
        x0,y0,x1,y1=model['combined_paintbox_rect']
        assert 0<x0<x1<pixels.shape[1]-1
        assert 0<y0<y1<pixels.shape[0]-1
        assert model['original_runtime_pixel_parity_verified'] is False
        np.testing.assert_array_equal(_float32_words(win),source)
        assert win._spectrum_summary==summary
        assert not win.spec_copy_button.isEnabled()
        assert not win.spec_save_button.isEnabled()
        win.close()
        qt_app.processEvents()


def test_combined_toggle_to_grid_only_then_series_only_without_leaks(
        tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    manifest,_,_,_=create_reference_fixture(
        tmp_path/'original',mode=0,n=1024,fs=65536)
    win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()
    source=_float32_words(win)
    _enable_combined(win,qt_app)
    combined_item=win._spec_source_raster_item
    win.spec_source_series_checkbox.click()
    qt_app.processEvents()
    assert combined_item.scene() is None
    assert win._spec_source_grid_model['raster_preview_enabled']
    assert not win._spec_source_grid_model['combined_preview_active']
    assert win._spec_source_series_item is None
    assert win._spec_source_series_raw_item.isVisible()
    win.spec_source_series_checkbox.click()
    qt_app.processEvents()
    assert win._spec_source_grid_model['combined_preview_active']
    win.spec_source_raster_checkbox.click()
    qt_app.processEvents()
    assert win._spec_source_raster_item is None
    assert len(win._spec_source_grid_lines)==22
    assert win._spec_source_series_item.isVisible()
    assert not win._spec_source_grid_model['combined_preview_active']
    win.spec_source_grid_checkbox.click()
    qt_app.processEvents()
    assert win._spec_source_grid_lines==[]
    assert win._spec_source_series_item.isVisible()
    np.testing.assert_array_equal(_float32_words(win),source)
    win.spec_reference_restore_button.click()
    qt_app.processEvents()
    assert win._spectrum_reference is None
    assert win._spec_source_series_item is None
    assert win._spec_source_raster_item is None
    assert not win.spec_source_series_checkbox.isEnabled()
    assert not win.spec_source_raster_checkbox.isEnabled()
    assert win.spec_copy_button.isEnabled()
    win.close()
    qt_app.processEvents()


def test_source_composite_zoom_rebuilds_without_duplicate_image(
        tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    manifest,_,_,_=create_reference_fixture(
        tmp_path/'original',mode=0,n=1024,fs=65536)
    win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()
    _enable_combined(win,qt_app)
    first=win._spec_source_raster_item
    source=_float32_words(win)
    win.spec_plot.getViewBox().setXRange(0.,12800.,padding=0)
    qt_app.processEvents()
    second=win._spec_source_raster_item
    assert second is not None and second is not first
    assert first.scene() is None
    assert win._spec_source_grid_model['combined_preview_active']
    assert win._spec_source_grid_model['source_v_line_spacing_x_single']==1280
    assert not win._spec_source_series_item.isVisible()
    np.testing.assert_array_equal(_float32_words(win),source)
    win.close()
    qt_app.processEvents()
