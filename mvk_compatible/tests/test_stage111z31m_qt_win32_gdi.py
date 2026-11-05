"""Windows 150% GDI TextOut candidate integration with original-reference plot.

Only SYNTHETIC Power/Y references, not the user's private original files.
"""
import sys
import numpy as np
import pytest

pytest.importorskip("PySide6")
from .test_desktop_qt import qt_app
from .test_stage111z31a_x32dbg_visual_reference import create_reference_fixture


@pytest.mark.skipif(sys.platform!="win32",reason="Win32 GDI required")
@pytest.mark.parametrize("mode",[0,1,2,3])
def test_win32_reference_uses_native_gdi_not_qt_for_all_four_modes(
        qt_app,tmp_path,mode):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    manifest,_,_,_=create_reference_fixture(
        tmp_path/f"synthetic_mode_{mode}",mode=mode,n=1024,fs=65536)
    win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()
    before=np.asarray(win._full_spectrum["amplitude"],dtype="<f4").view("<u4").copy()
    win.spec_source_grid_checkbox.click()
    win.spec_source_raster_checkbox.click()
    win.spec_source_series_checkbox.click()
    qt_app.processEvents()
    model=win._spec_source_grid_model
    assert model["combined_preview_active"]
    assert model["spectrum_textout_engine"]=="WIN32_GDI_DFM_CANDIDATE"
    d=model["spectrum_textout_native_metrics"]
    assert d["gdi_width_zero"]>0
    assert d["gdi_width_sixdecimals"]>0
    assert d["gdi_height_zero"]>0
    assert d["requested_font_height"]==-13
    assert not d["original_font_in_process_verified"]
    assert not model["original_runtime_tcanvas_font_verified"]
    assert not model["original_runtime_pixel_parity_verified"]
    assert model["source_textout_placements"][
        "font_metrics_provenance"]=="gdi_reconstructed_from_dfm"
    assert len(model["source_textout_placements"]["events"])>=4
    assert win._spec_source_raster_data.dtype==np.uint8
    assert np.all(win._spec_source_raster_data[:,:,3]==255)
    np.testing.assert_array_equal(
        np.asarray(win._full_spectrum["amplitude"],dtype="<f4").view("<u4"),
        before)
    win.spec_source_series_checkbox.click()
    qt_app.processEvents()
    assert win._spec_source_series_item is None
    assert not win._spec_source_grid_model["combined_preview_active"]
    win.spec_reference_restore_button.click()
    qt_app.processEvents()
    assert win._spec_source_raster_item is None
    assert win.spec_plot.getPlotItem().getAxis("bottom").label.isVisible()
    win.close()
    qt_app.processEvents()
