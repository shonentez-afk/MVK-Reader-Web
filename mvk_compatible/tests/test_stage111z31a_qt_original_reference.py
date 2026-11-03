"""Stage111Z31A: same Qt Spectrum plot renders local original reference only.

Synthetic-only offscreen UI; actual operator x32dbg capture remains private.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31a_x32dbg_visual_reference import create_reference_fixture
from mvk_compatible.core.original_spectrum_x32dbg_reference import SOURCE
from mvk_compatible.core.tqgrapher_display_idr_candidate import (
    spectrum_display_contract,
)


@pytest.mark.parametrize("mode", [0, 1, 2, 3])
def test_qt_same_archive_plot_can_temporarily_show_original_operator_y(
        tmp_path, qt_app, mode):
    from PySide6.QtCore import QPointF, Qt
    from mvk_compatible.desktop.main_window import MainWindow

    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    calculated=win._full_spectrum
    original_widget=win.spec_plot
    old_mode=win.spec_mode.currentIndex()
    old_fft_index=win.spec_n.currentIndex()
    old_copy=win.spec_copy_button.isEnabled()

    manifest,config,p,y=create_reference_fixture(
        tmp_path/f"original_{mode}",mode=mode,fs=65536,n=1024)
    result=win.show_original_spectrum_reference(manifest)
    qt_app.processEvents()

    assert win.spec_plot is original_widget
    assert win._full_spectrum["source"]==SOURCE
    assert win._full_spectrum["mode"]==mode
    assert win._full_spectrum["n_fft"]==1024
    assert win.spec_n.currentData()==1024
    assert win.spec_mode.currentIndex()==mode
    assert win.spec_avg.currentIndex()==(0 if mode==0 else 1)
    assert win._full_spectrum["original_capture_reference_only"]
    assert result["full_display_y_float32_bitwise_equal"]
    assert result["float32_bins"]==512
    assert result["original_qt_pixel_parity_verified"] is False
    assert not win.spec_copy_button.isEnabled()
    assert not win.spec_save_button.isEnabled()
    assert not win.spec_original_copy_compare.isEnabled()
    assert win.spec_reference_restore_button.isEnabled()
    assert not win.spec_mode.isEnabled()
    assert not win.spec_n.isEnabled()
    assert "ОРИГИНАЛ x32dbg" in win.spec_mean_primary.text()
    assert "0 ULP" in win.spec_mean.text()
    assert "оригинал" in win.spec_hint.text().lower() or "x32dbg" in win.spec_hint.text().lower()
    assert win.spec_plot.getPlotItem().getAxis("bottom").labelText=="Гц"

    plot_items=win.spec_plot.listDataItems()
    assert len(plot_items)==1
    xp,yp=plot_items[0].getData()
    contract=spectrum_display_contract(1024,65536)
    count=contract["grapher_series_bins"]
    assert len(xp)==len(yp)==count
    np.testing.assert_array_equal(yp.astype("<f4").view("<u4"),y[:count].view("<u4"))
    assert xp[-1]==(count-1)*64
    assert contract["grapher_axis_end_frequency_hz"]==25600
    assert win._spec_visible_max_hz==25600

    # Cursor must continue to work on actual Float32 series, not a decimated
    # screenshot or a newly calculated FFT.
    rect=win.spec_plot.getViewBox().sceneBoundingRect()
    assert rect.width()>3
    class Click:
        def button(self): return Qt.LeftButton
        def scenePos(self):return QPointF(rect.left()+rect.width()*0.25,
                                           rect.center().y())
    win._spec_click(Click())
    assert win._spec_last_cursor is not None
    assert win._spec_last_cursor["full_bin_count"]==512
    assert win._spec_last_cursor["grapher_series_bins"]==count
    assert win._spec_last_cursor["fft_source"]==SOURCE

    win.spec_reference_restore_button.click()
    qt_app.processEvents()
    assert win._full_spectrum is not None
    assert win._full_spectrum["source"]==calculated["source"]
    assert not win.spec_reference_restore_button.isEnabled()
    assert win.spec_mode.isEnabled()
    assert win.spec_n.isEnabled()
    assert win.spec_mode.currentIndex()==old_mode
    assert win.spec_n.currentIndex()==old_fft_index
    assert win.spec_copy_button.isEnabled()==old_copy
    assert not win._full_spectrum.get("original_capture_reference_only",False)
    win.close()
    qt_app.processEvents()


def test_qt_invalid_original_reference_is_atomic_and_does_not_disable_copy(
        tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    previous=win._full_spectrum
    assert win.spec_copy_button.isEnabled()
    manifest,config,p,y=create_reference_fixture(tmp_path/"tampered")
    config["display_y_sha256"]="0"*64
    manifest.write_text(json.dumps(config),encoding="utf-8")
    with pytest.raises(ValueError,match="SHA256 mismatch"):
        win.show_original_spectrum_reference(manifest)
    assert win._full_spectrum is previous
    assert win._spectrum_reference is None
    assert not win.spec_reference_restore_button.isEnabled()
    assert win.spec_copy_button.isEnabled()
    win.close()
    qt_app.processEvents()


def test_qt_reference_rejected_during_live_without_opening_external_data(
        tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    manifest,config,p,y=create_reference_fixture(tmp_path/"operator")
    win._live_active=True
    with pytest.raises(ValueError,match="офлайн-архиве"):
        win.show_original_spectrum_reference(manifest)
    win._live_active=False
    assert win._spectrum_reference is None
    win.close()
    qt_app.processEvents()
