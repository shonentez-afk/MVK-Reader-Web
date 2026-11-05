"""Stage111Z31G: Qt raster stays research-only and never mutates Power/Y."""
import numpy as np
from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31a_x32dbg_visual_reference import create_reference_fixture


def _y_bits(win):
    return np.asarray(win.spec_plot.listDataItems()[0].getData()[1],
                      dtype='<f4').view('<u4').copy()


def test_tco2draw_optin_raster_zoom_return_and_unmodified_y(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    manifest,_,_,_=create_reference_fixture(
        tmp_path/"source",mode=0,n=1024,fs=65536)
    win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()
    y0=_y_bits(win)
    summary=win._spectrum_summary.copy()
    assert not win.spec_source_raster_checkbox.isEnabled()

    win.spec_source_grid_checkbox.click()
    qt_app.processEvents()
    assert win.spec_source_raster_checkbox.isEnabled()
    assert len(win._spec_source_grid_lines)==22

    win.spec_source_raster_checkbox.click()
    qt_app.processEvents()
    item=win._spec_source_raster_item
    assert item is not None
    assert win._spec_source_grid_lines==[]
    assert item.image.ndim==3 and item.image.shape[2]==4
    assert item.image.dtype==np.uint8
    assert np.any(item.image[:,:,0]==192)
    assert np.all(item.image[:,:,3]==255)
    assert win._spec_source_grid_model['raster_preview_enabled']
    assert not win._spec_source_grid_model['tco2draw_raster_contract'][
        'original_delphi_pixel_parity_verified']
    np.testing.assert_array_equal(_y_bits(win),y0)
    assert win._spectrum_summary==summary
    assert not win.spec_copy_button.isEnabled()

    win.spec_plot.getViewBox().setXRange(0,12800,padding=0)
    qt_app.processEvents()
    new_item=win._spec_source_raster_item
    assert new_item is not None and new_item is not item
    assert item.scene() is None
    assert win._spec_source_grid_model['source_v_line_spacing_x_single']==1280
    np.testing.assert_array_equal(_y_bits(win),y0)

    win.spec_source_raster_checkbox.click()
    qt_app.processEvents()
    assert win._spec_source_raster_item is None
    assert len(win._spec_source_grid_lines)==22
    win.spec_source_grid_checkbox.click()
    qt_app.processEvents()
    assert not win.spec_source_raster_checkbox.isEnabled()
    assert not win.spec_source_raster_checkbox.isChecked()
    assert win._spec_source_grid_lines==[]
    win.close()
    qt_app.processEvents()


def test_raster_clears_before_return_to_archived_spectrum(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    qt_app.processEvents()
    archive=win._full_spectrum['source']
    assert not win.spec_source_raster_checkbox.isEnabled()
    manifest,_,_,_=create_reference_fixture(
        tmp_path/"source",mode=0,n=1024,fs=65536)
    win.show_original_spectrum_reference(manifest)
    win.spec_source_grid_checkbox.click()
    win.spec_source_raster_checkbox.click()
    qt_app.processEvents()
    raster=win._spec_source_raster_item
    assert raster is not None
    win.spec_reference_restore_button.click()
    qt_app.processEvents()
    assert raster.scene() is None
    assert win._spec_source_raster_item is None
    assert win._spec_source_grid_lines==[]
    assert win._spectrum_reference is None
    assert win._full_spectrum['source']==archive
    assert not win.spec_source_grid_checkbox.isChecked()
    assert not win.spec_source_raster_checkbox.isChecked()
    assert not win.spec_source_raster_checkbox.isEnabled()
    assert win.spec_copy_button.isEnabled()
    win.close()
    qt_app.processEvents()
