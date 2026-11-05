"""Stage111Z31E: opt-in source-derived grid on the SAME Qt Power/Y plot.

Tests use synthetic verified manifests ONLY, not operator original BIN.
No exact Delphi GDI, x87, 007B2090 FormatFloat or font pixel parity claim.
"""
from __future__ import annotations

import numpy as np
import pytest

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31a_x32dbg_visual_reference import create_reference_fixture
from mvk_compatible.core.tqgrapher_grid_idr_candidate import SOURCE
from mvk_compatible.core.original_spectrum_x32dbg_reference import (
    SOURCE as ORIGINAL_REFERENCE_SOURCE,
)


def _spectrum(win):
    return np.asarray(
        win.spec_plot.listDataItems()[0].getData()[1], dtype="<f4").copy()


def test_optin_source_grid_not_available_for_unverified_archive(tmp_path, qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    qt_app.processEvents()
    assert not win.spec_source_grid_checkbox.isEnabled()
    assert not win.spec_source_grid_checkbox.isChecked()
    assert win._spec_source_grid_model is None
    # Even a programmatic attempt must be fail-closed, not alter archive view.
    win.spec_source_grid_checkbox.setChecked(True)
    qt_app.processEvents()
    assert not win.spec_source_grid_checkbox.isChecked()
    assert win._spec_source_grid_model is None
    assert not win._spec_source_grid_applied
    win.close()


@pytest.mark.parametrize("mode", [0, 1, 2, 3])
def test_reference_optin_grid_preserves_full_float32_y_and_original_summary(
        tmp_path,qt_app,mode):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    manifest, _, _, _ = create_reference_fixture(
        tmp_path/f"tag_{mode}",mode=mode,n=1024,fs=65536)
    win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()

    assert win.spec_source_grid_checkbox.isEnabled()
    assert not win.spec_source_grid_checkbox.isChecked()
    assert win._spec_source_grid_model is None
    source=win._full_spectrum['source']
    assert source==ORIGINAL_REFERENCE_SOURCE
    before=_spectrum(win)
    summary=win._spectrum_summary.copy()
    before_xrange=win.spec_plot.getViewBox().viewRange()[0]

    win.spec_source_grid_checkbox.click()
    qt_app.processEvents()
    assert win.spec_source_grid_checkbox.isChecked()
    assert win._spec_source_grid_applied
    grid=win._spec_source_grid_model
    assert grid['source']==SOURCE
    assert grid['source_auto_v_spacing']==10
    assert grid['source_auto_h_spacing']==10
    assert grid['original_delphi_pixel_grid_parity_verified'] is False
    assert grid['source_v_line_spacing_x_single']==2560
    assert grid['x_grid_ticks']==tuple(range(0,25601,2560))
    assert 'Tahoma' in win.spec_plot.getPlotItem().getAxis('bottom').label.font().family()
    assert 'FormatFloat' in win.spec_source_grid_info.text()
    assert 'НЕ подтверждены' in win.spec_source_grid_info.text()
    # No re-FFT/re-integration/recalibration; exactly the same source samples.
    np.testing.assert_array_equal(_spectrum(win).view('<u4'),
                                  before.view('<u4'))
    assert win._spectrum_summary==summary
    assert win._full_spectrum['source']==source
    assert win.spec_plot.getViewBox().viewRange()[0]==pytest.approx(before_xrange)
    assert not win.spec_copy_button.isEnabled()
    assert not win.spec_save_button.isEnabled()
    assert win.spec_canvas_geometry_button.isEnabled()

    win.spec_source_grid_checkbox.click()
    qt_app.processEvents()
    assert not win._spec_source_grid_applied
    assert win._spec_source_grid_model is None
    assert win.spec_plot.getPlotItem().getAxis('bottom')._tickLevels is None
    np.testing.assert_array_equal(_spectrum(win).view('<u4'),
                                  before.view('<u4'))
    win.close()
    qt_app.processEvents()


def test_source_grid_tracks_current_x_range_and_reverts_with_archive(
        tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    qt_app.processEvents()
    archive=win._full_spectrum
    primary_title=win.title.text()
    manifest, _, _, _ = create_reference_fixture(
        tmp_path/"source",mode=0,n=1024,fs=65536)
    win.show_original_spectrum_reference(manifest)
    win.spec_source_grid_checkbox.click()
    qt_app.processEvents()
    assert win._spec_source_grid_model["source_v_line_spacing_x_single"]==2560

    vb=win.spec_plot.getViewBox()
    vb.setXRange(0.,12800.,padding=0.)
    qt_app.processEvents()
    grid=win._spec_source_grid_model
    assert grid is not None
    assert grid["source_v_line_spacing_x_single"]==pytest.approx(1280)
    assert grid["x_grid_ticks"]==tuple(range(0,12801,1280))
    assert not grid["original_delphi_pixel_grid_parity_verified"]

    win.spec_reference_restore_button.click()
    qt_app.processEvents()
    assert win.title.text()==primary_title
    assert win._spectrum_reference is None
    assert win._spec_source_grid_model is None
    assert not win._spec_source_grid_applied
    assert not win.spec_source_grid_checkbox.isChecked()
    assert not win.spec_source_grid_checkbox.isEnabled()
    assert win._full_spectrum["source"]==archive["source"]
    assert win.spec_plot.getPlotItem().getAxis("bottom")._tickLevels is None
    assert win.spec_copy_button.isEnabled()
    win.close()
    qt_app.processEvents()


def test_reference_grid_cleared_when_operator_opens_new_archive(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    manifest,_,_,_=create_reference_fixture(tmp_path/"source",mode=0)
    win.show_original_spectrum_reference(manifest)
    win.spec_source_grid_checkbox.setChecked(True)
    qt_app.processEvents()
    assert win._spec_source_grid_applied
    win.open_archive(fixture_zip(tmp_path))
    qt_app.processEvents()
    assert win._spectrum_reference is None
    assert win._spec_source_grid_model is None
    assert not win.spec_source_grid_checkbox.isChecked()
    assert not win.spec_source_grid_checkbox.isEnabled()
    assert win._full_spectrum.get("original_capture_reference_only") is not True
    win.close()
    qt_app.processEvents()
