"""Stage111Z31F: source palette grid behind unchanged original Power/Y.

Synthetic private-reference-shaped data only. The Qt QPen line is NOT a
pixel-perfect native TCo2Draw software anti-aliased bitmap scanline.
"""
import numpy as np
from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31a_x32dbg_visual_reference import create_reference_fixture


def _visible_original(win):
    return np.asarray(
        win.spec_plot.listDataItems()[0].getData()[1],dtype='<f4').view('<u4').copy()


def test_source_grid_overlay_uses_verified_software_ink_and_restores(
        tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    manifest,_,_,_=create_reference_fixture(tmp_path/'tag0',mode=0,n=1024,fs=65536)
    win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()
    assert win._spec_source_grid_lines==[]
    original=_visible_original(win)
    summary=win._spectrum_summary.copy()

    win.spec_source_grid_checkbox.click()
    qt_app.processEvents()
    model=win._spec_source_grid_model
    items=list(win._spec_source_grid_lines)
    assert model['tco2draw_source_style']['source_grid_line_color_hex']=='#c0c0c0'
    assert model['tco2draw_source_style']['source_original_grid_is_gdi_pen'] is False
    assert len(items)==len(model['x_grid_ticks'])+len(model['y_grid_ticks'])==22
    assert all(item.pen.color().name()=='#c0c0c0' for item in items)
    assert all(item.zValue()==-100 for item in items)
    assert 'TCo2Draw' in win.spec_source_grid_info.text()
    np.testing.assert_array_equal(_visible_original(win),original)
    assert win._spectrum_summary==summary

    win.spec_source_grid_checkbox.click()
    qt_app.processEvents()
    assert win._spec_source_grid_lines==[]
    assert win._spec_source_grid_model is None
    assert not win._spec_source_grid_applied
    assert all(item.scene() is None for item in items)
    np.testing.assert_array_equal(_visible_original(win),original)
    win.close()
    qt_app.processEvents()


def test_source_grid_zoom_replaces_lines_without_duplication(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    manifest,_,_,_=create_reference_fixture(tmp_path/'tag0',mode=0)
    win.show_original_spectrum_reference(manifest)
    win.spec_source_grid_checkbox.click()
    qt_app.processEvents()
    first=list(win._spec_source_grid_lines)
    vb=win.spec_plot.getViewBox()
    vb.setXRange(0.,12800.,padding=0.)
    qt_app.processEvents()
    second=list(win._spec_source_grid_lines)
    assert len(second)==22
    assert set(map(id,second)).isdisjoint(map(id,first))
    assert all(item.scene() is None for item in first)
    assert win._spec_source_grid_model['source_v_line_spacing_x_single']==1280
    assert win._spec_source_grid_model['x_grid_ticks']==tuple(range(0,12801,1280))
    win.close()
    qt_app.processEvents()


def test_source_grid_cannot_leak_to_archive(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    assert not win.spec_source_grid_checkbox.isEnabled()
    assert win._spec_source_grid_lines==[]
    manifest,_,_,_=create_reference_fixture(tmp_path/'tag0',mode=0)
    win.show_original_spectrum_reference(manifest)
    win.spec_source_grid_checkbox.click()
    qt_app.processEvents()
    assert win._spec_source_grid_lines
    win.spec_reference_restore_button.click()
    qt_app.processEvents()
    assert win._spectrum_reference is None
    assert win._spec_source_grid_lines==[]
    assert not win._spec_source_grid_applied
    assert not win.spec_source_grid_checkbox.isChecked()
    assert not win.spec_source_grid_checkbox.isEnabled()
    win.close()
    qt_app.processEvents()
