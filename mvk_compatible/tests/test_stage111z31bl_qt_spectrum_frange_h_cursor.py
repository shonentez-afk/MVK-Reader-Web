"""Stage111Z31BL: real original PageSpectrum H/FRange/cursor UI together.

Synthetic BIN/TSXML only, never original runtime, user capture or hardware.
The independent Core validated the SAME selected ADC, N/2 FFT and BIN SHA
before the source menu and original lbSpecHint were updated.
"""
import numpy as np
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import QPointF

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z16_direct_bin_tsxml import _make_pair
from .test_stage111z31bj_qt_visible_file_workbench import (
    capture_synthetic_ui_if_requested,
)


def _with_tsxml_gain(sidecar,gain):
    raw=sidecar.read_text(encoding="utf-8")
    sidecar.write_text(raw.replace(
        "</Channel>",f"<InternalChannelGain>{gain}</InternalChannelGain>"
        "</Channel>"),encoding="utf-8")


def test_source_h_preset_and_real_frange_survive_fft_recompute_and_user_pan(
        qt_app,tmp_path):
    from mvk_compatible.desktop.main_window import MainWindow
    p4,xml4,_=_make_pair(tmp_path,n=16384,adc=4)
    _with_tsxml_gain(xml4,"6.25")
    win=MainWindow()
    win.show()
    try:
        win.open_archive(p4)
        qt_app.processEvents()
        assert win._full_spectrum is not None
        evidence=win._source_spectrum_gain
        assert evidence is not None
        assert evidence.frange_single==6.25
        assert evidence.channel==4
        assert evidence.source_bin_sha256==(
            win._current_offline_flow().source_record()["source_bin_sha256"])
        assert "FRange TSXML 6.25" in win.spec_cursor_primary.text()
        assert "не калибровка" in win.spec_cursor_primary.text()
        assert "6.25" in win.spec_vscale_button.toolTip()
        assert "НЕ подтверждена" in win.spec_mean_primary.text()
        assert not evidence.original_runtime_frange_verified
        source=np.asarray(win._full_spectrum["amplitude"],
                          dtype="<f4").view("<u4").copy()

        win._select_original_hscale(6400)
        qt_app.processEvents()
        assert win._spec_original_hscale_selected==6400
        assert win._spec_source_h_view.selected_page_hz==6400
        assert win._spec_source_h_view.native_position_hz==0
        assert win.spec_hscroll.maximum()==25600-6400
        assert win.spec_hscale_button.text()=="6400 Гц"
        xr=win.spec_plot.getViewBox().viewRange()[0]
        assert xr[1]-xr[0]==pytest.approx(6400,abs=.5)

        win.spec_hscroll.setValue(1000)
        qt_app.processEvents()
        xr=win.spec_plot.getViewBox().viewRange()[0]
        assert xr[0]==pytest.approx(1000,abs=.5)
        assert win._spec_source_h_view.native_position_hz==1000
        assert win._spec_source_h_view.channel==4
        assert win._spec_source_h_view.source_bin_sha256==(
            evidence.source_bin_sha256)
        np.testing.assert_array_equal(
            np.asarray(win._full_spectrum["amplitude"],
                       dtype="<f4").view("<u4"),source)
        win.original_root_tabs.setCurrentIndex(4)
        capture_synthetic_ui_if_requested(win,qt_app,"10_bl_frange_h_pan")

        # Recalculating the FFT must preserve the selected SOURCE menu item
        # and scroll position, rather than silently resetting to full width.
        win.refresh_spec()
        qt_app.processEvents()
        xr=win.spec_plot.getViewBox().viewRange()[0]
        assert win._spec_original_hscale_selected==6400
        assert xr[0]==pytest.approx(1000,abs=.5)
        assert xr[1]-xr[0]==pytest.approx(6400,abs=.5)
        assert win._spec_source_h_view.native_position_hz==1000
        assert win._source_spectrum_gain.frange_single==6.25
        np.testing.assert_array_equal(
            np.asarray(win._full_spectrum["amplitude"],
                       dtype="<f4").view("<u4"),source)

        # A cursor in the actual Qt spectrum must select one full Float32
        # source bin from the same channel (not from plotted pixel min/max).
        vb=win.spec_plot.getViewBox()
        y=win.spec_plot.getViewBox().viewRange()[1][0]+1.
        cursor_scene=vb.mapViewToScene(QPointF(1500.,y))
        win._spec_at_scene_pos(cursor_scene,force=True)
        qt_app.processEvents()
        assert win._spec_last_cursor is not None
        chosen=win._spec_last_cursor
        assert chosen["channel"]==4
        assert chosen["chart_decimation_used"] is False
        assert 0<=chosen["selected_bin"]<len(win._full_spectrum["amplitude"])
        capture_synthetic_ui_if_requested(win,qt_app,"11_bl_frange_cursor")

        win.spec_mode.setCurrentIndex(1)
        qt_app.processEvents()
        assert win._spec_original_hscale_selected==6400
        assert win._source_spectrum_gain.frange_single==6.25
        assert win._source_spectrum_gain.spectrum_mode==1
        assert win._spec_source_h_view.channel==4
        assert "СКЗ спектра" in win.spec_mean_primary.text()
        assert "НЕ подтверждена" in win.spec_mean_primary.text()
        assert "FRange TSXML" in win.spec_vscale_button.toolTip()
        win._select_original_vscale(3)
        qt_app.processEvents()
        assert win._spec_vscroll_source_candidate[
            "source_tsxml_f_range_static_candidate_used"]
        assert win._spec_vscroll_source_candidate[
            "original_physical_calibration_verified"] is False
        capture_synthetic_ui_if_requested(win,qt_app,"12_bl_frange_vscale")

        # New local ZIP has no original TSXML FRange; never retain the old
        # FRange or H scroll state from the previously selected BIN/ADC.
        win.open_archive(fixture_zip(tmp_path,sample_count=8192))
        qt_app.processEvents()
        assert win._source_spectrum_gain.frange_single is None
        assert win._spec_original_hscale_selected is None
        assert win._spec_source_h_view is None
        assert "FRange: не установлен" in win.spec_cursor_primary.text()
        assert "6.25" not in win.spec_vscale_button.toolTip()
        win._close_session()
        qt_app.processEvents()
        assert win._source_spectrum_gain is None
        assert win._spec_source_h_view is None
    finally:
        win.close()
        qt_app.processEvents()


def test_source_gain_changes_with_selected_bin_adc_without_cross_talk(
        qt_app,tmp_path):
    from mvk_compatible.desktop.main_window import MainWindow
    p4,x4,_=_make_pair(tmp_path,n=8192,adc=4)
    p6,x6,_=_make_pair(tmp_path,n=8192,adc=6)
    _with_tsxml_gain(x4,"2.5")
    _with_tsxml_gain(x6,"12.5")
    win=MainWindow()
    win.show()
    try:
        win.open_archive(p4)
        qt_app.processEvents()
        assert win._source_spectrum_gain.frange_single==2.5
        hash4=win._source_spectrum_gain.source_bin_sha256
        win.adc.setCurrentIndex(5)
        qt_app.processEvents()
        assert win._full_spectrum["channel"]==6
        assert win._source_spectrum_gain.channel==6
        assert win._source_spectrum_gain.frange_single==12.5
        assert "FRange TSXML 12.5" in win.spec_cursor_primary.text()
        # Synthetic ADC4 and ADC6 contain the SAME raw sine words, thus
        # identical SHA is valid: channel identity must still be distinct.
        assert win._source_spectrum_gain.source_bin_sha256==hash4
        assert win._pagestatus_snapshot is None
        assert win.original_shell.file_values.count()==1
        win.adc.setCurrentIndex(3)
        qt_app.processEvents()
        assert win._source_spectrum_gain.frange_single==2.5
        assert win._source_spectrum_gain.source_bin_sha256==hash4
    finally:
        win.close()
        qt_app.processEvents()
