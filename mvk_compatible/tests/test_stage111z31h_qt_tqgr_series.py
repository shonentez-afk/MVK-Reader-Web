"""Stage111Z31H Qt source TQGRSeries overlay. Synthetic verified fixtures only."""
import numpy as np
import pytest
from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31a_x32dbg_visual_reference import create_reference_fixture


def _all_source_bits(win):
    return np.asarray(win._full_spectrum['amplitude'],
                      dtype='<f4').view('<u4').copy()


@pytest.mark.parametrize('mode',[0,1,2,3])
def test_original_reference_pixel_series_preserves_float32_and_summary(
        tmp_path,qt_app,mode):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    manifest,_,_,_=create_reference_fixture(
        tmp_path/f'tag{mode}',mode=mode,n=1024,fs=65536)
    win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()
    before=_all_source_bits(win)
    summary=win._spectrum_summary.copy()
    raw=win._spec_source_series_raw_item
    assert raw is not None and raw.isVisible()
    assert win.spec_source_series_checkbox.isEnabled()
    assert not win.spec_source_series_checkbox.isChecked()
    assert win._spec_source_series_item is None

    win.spec_source_series_checkbox.click()
    qt_app.processEvents()
    model=win._spec_source_series_model
    assert win.spec_source_series_checkbox.isChecked()
    assert model['source'].startswith('SOURCE_DERIVED_TQGRSERIES')
    assert model['data_size_original']==win._spec_display_contract['grapher_series_bins']
    assert model['segments'].shape[1]==4
    assert 0<len(model['segments'])<=2*round(win.spec_plot.getViewBox().width())
    assert win._spec_source_series_item is not None
    assert not raw.isVisible()
    assert 'не доказаны' in win.spec_source_series_info.text()
    np.testing.assert_array_equal(_all_source_bits(win),before)
    assert win._spectrum_summary==summary
    assert not win.spec_copy_button.isEnabled()
    assert not win.spec_save_button.isEnabled()

    win.spec_source_series_checkbox.click()
    qt_app.processEvents()
    assert win._spec_source_series_item is None
    assert win._spec_source_series_model is None
    assert raw.isVisible()
    np.testing.assert_array_equal(_all_source_bits(win),before)
    win.close()
    qt_app.processEvents()


def test_original_series_zooms_rebuilds_and_stays_out_of_archive(
        tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    qt_app.processEvents()
    archive_source=win._full_spectrum['source']
    assert not win.spec_source_series_checkbox.isEnabled()
    manifest,_,_,_=create_reference_fixture(
        tmp_path/'x32dbg',mode=0,n=1024,fs=65536)
    win.show_original_spectrum_reference(manifest)
    win.spec_source_series_checkbox.click()
    qt_app.processEvents()
    first=win._spec_source_series_item
    assert first is not None
    before=_all_source_bits(win)
    win.spec_plot.getViewBox().setXRange(0,12800,padding=0)
    qt_app.processEvents()
    assert win._spec_source_series_item is not first
    assert first.scene() is None
    assert win._spec_source_series_model['screen_single'][1]==12800
    np.testing.assert_array_equal(_all_source_bits(win),before)

    # Stage31G grid/raster must remain independent from the new source curve.
    win.spec_source_grid_checkbox.click()
    win.spec_source_raster_checkbox.click()
    qt_app.processEvents()
    assert win._spec_source_raster_item is not None
    assert win._spec_source_series_item is not None
    win.spec_reference_restore_button.click()
    qt_app.processEvents()
    assert first.scene() is None
    assert win._spec_source_series_item is None
    assert win._spec_source_series_raw_item is None
    assert win._spec_source_raster_item is None
    assert not win.spec_source_series_checkbox.isChecked()
    assert not win.spec_source_series_checkbox.isEnabled()
    assert win._spectrum_reference is None
    assert win._full_spectrum['source']==archive_source
    assert win.spec_copy_button.isEnabled()
    win.close()
    qt_app.processEvents()


def test_unauthenticated_series_toggle_fail_closed(qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    win.spec_source_series_checkbox.setChecked(True)
    qt_app.processEvents()
    assert not win.spec_source_series_checkbox.isChecked()
    assert not win.spec_source_series_checkbox.isEnabled()
    assert win._spec_source_series_item is None
    win.close()
    qt_app.processEvents()
