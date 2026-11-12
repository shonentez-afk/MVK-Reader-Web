"""BZ: original PageSpectrum bSpecVScale main-click + 6 menu choices.

The original private mvkform.dfm declares a split button with
OnClick=bAnyDropDownClick, and Unit128:0084EAF4 pops up the menu.
Unit128:0084B901 constructs the physical captions from
GraphDefaultVScale/divisor. Only synthetic Direct BIN/TSXML is used.
"""
from __future__ import annotations
import hashlib
import numpy as np
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt,QPoint,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QToolButton

from .test_desktop_qt import qt_app
from .test_stage111z16_direct_bin_tsxml import _make_pair


def _fft_digest(win):
    assert win._full_spectrum is not None
    return hashlib.sha256(
        np.asarray(win._full_spectrum["amplitude"],dtype="<f4").tobytes()
    ).hexdigest()


def test_original_vscale_main_button_only_pops_menu_and_source_y_labels(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    bin_file,sidecar,_=_make_pair(tmp_path,adc=4,n=8192)
    sidecar.write_text(sidecar.read_text(encoding="utf-8").replace(
        "</Channel>","<InternalChannelGain>6.25</InternalChannelGain></Channel>"),
        encoding="utf-8")
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.open_archive(bin_file)
        win.original_root_tabs.setCurrentIndex(4)
        win.spec_mode.setCurrentIndex(1)
        qt_app.processEvents()
        button=win.spec_vscale_button
        assert button.objectName()=="bSpecVScale"
        assert button.popupMode()==QToolButton.InstantPopup
        assert button.menu() is win.spec_vscale_menu
        actions=button.menu().actions()
        assert len(actions)==6
        assert [a.data() for a in actions]==list(range(6))
        expected=(10.,1.,.1,.01,.001,.0001)
        for i,(item,value) in enumerate(zip(actions,expected)):
            label=item.text()
            assert label.startswith(f"{value:.6g} ")
            assert "усл." in label
            assert f"делитель {10**i}" in item.toolTip()
        assert button.text()=="0.01 усл."
        assert "видимый Y" in button.toolTip()
        assert "кнопка" in button.toolTip().lower()
        original_sha=_fft_digest(win)
        current_tag=win._spec_original_vscale_tag
        pos=win._spec_vertical_model["delphi_position"]
        vertical_before=win.spec_plot.getViewBox().viewRange()[1]
        # A real click on the BUTTON BODY must not silently advance
        # Tag3 -> Tag4. Schedule close to avoid nested popup event loops.
        QTimer.singleShot(30,win.spec_vscale_menu.hide)
        QTest.mouseClick(button,Qt.LeftButton,
                         pos=QPoint(8,button.height()//2))
        qt_app.processEvents()
        assert win._spec_original_vscale_tag==current_tag==3
        assert win._spec_vertical_model["delphi_position"]==pos==99900
        assert win.spec_plot.getViewBox().viewRange()[1]==pytest.approx(
            vertical_before,abs=1e-5)
        assert _fft_digest(win)==original_sha
        assert actions[3].isChecked()
    finally:
        win.spec_vscale_menu.hide()
        win.close()
        qt_app.processEvents()


def test_original_physical_scale_menu_1_10_100_preserves_baseline_and_fft(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    bin_file,sidecar,_=_make_pair(tmp_path,adc=4,n=8192)
    sidecar.write_text(sidecar.read_text(encoding="utf-8").replace(
        "</Channel>","<InternalChannelGain>6.25</InternalChannelGain></Channel>"),
        encoding="utf-8")
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.open_archive(bin_file)
        win.original_root_tabs.setCurrentIndex(4)
        win.spec_mode.setCurrentIndex(1)
        qt_app.processEvents()
        same_sha=_fft_digest(win)
        expected=(10.,1.,.1,.01,.001,.0001)
        for tag,(divisor,height) in enumerate(zip(
            (1,10,100,1000,10000,100000),expected)):
            win.spec_vscale_menu.actions()[tag].trigger()
            qt_app.processEvents()
            assert win._spec_original_vscale_tag==tag
            assert win.spec_vscale_menu.actions()[tag].isChecked()
            assert win.spec_vscale_button.text().startswith(f"{height:.6g} ")
            actual=win.spec_plot.getViewBox().viewRange()[1]
            assert actual[0]==pytest.approx(0.,abs=8e-6)
            assert actual[1]-actual[0]==pytest.approx(height,rel=2e-4)
            assert win.spec_vscroll.value()==100000-100000//divisor
            assert _fft_digest(win)==same_sha
            assert f"Tag{tag}" in win.statusBar().currentMessage()
            assert win._spec_vscroll_source_candidate[
                "source_bound_vertical_view"]["f_range_single"]==6.25
            assert not win._spec_vscroll_source_candidate[
                "qt_y_baseline_from_local_spectrum"]
        # dB is a DIFFERENT original menu: 150,100,75,50,25,10,
        # and it must not retain physical-unit labels.
        win.spec_mode.setCurrentIndex(0)
        qt_app.processEvents()
        assert win.spec_vscale_button.text()=="150 дБ"
        assert [a.text() for a in win.spec_vscale_menu.actions()]==[
            "150 дБ","100 дБ","75 дБ","50 дБ","25 дБ","10 дБ"]
        assert win.spec_vscale_button.popupMode()==QToolButton.InstantPopup
        assert _fft_digest(win)!=same_sha  # mode change recomputes FFT
    finally:
        win.close()
        qt_app.processEvents()


def test_unknown_original_f_range_keeps_explicit_uncalibrated_divisors(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    bin_file,_,_=_make_pair(tmp_path,adc=4,n=8192)
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.open_archive(bin_file)
        win.spec_mode.setCurrentIndex(1)
        qt_app.processEvents()
        assert win._source_spectrum_gain.frange_single is None
        assert [a.text() for a in win.spec_vscale_menu.actions()]==[
            "÷ 1 (лок.)","÷ 10 (лок.)","÷ 100 (лок.)",
            "÷ 1000 (лок.)","÷ 10000 (лок.)","÷ 100000 (лок.)"]
        assert not win._spec_y_source_bound
        assert "локальный" in win.spec_vscale_button.toolTip()
        # Without a proven FRange the source Tag3 initial geometry used
        # to show merely 1/1000 of the spectrum (nearly blank screen).
        # Fit Tag3 locally to 120% of the complete real FFT peak, and
        # keep this SAME baseline when switching 1/10/100 menu values.
        local_max=max(1e-12,abs(win._spec_data_ymin),
                      abs(win._spec_data_ymax))
        span=win.spec_plot.getViewBox().viewRange()[1]
        assert span[0]==pytest.approx(0.,abs=1e-6)
        assert span[1]-span[0]==pytest.approx(1.2*local_max,rel=1e-4)
        auto=win._spec_vscroll_source_candidate
        assert auto["research_local_autofit_original_default_tag"]==3
        assert auto["research_local_full_y_baseline"]==pytest.approx(
            1200*local_max,rel=1e-4)
        same_sha=_fft_digest(win)
        win.spec_vscale_menu.actions()[2].trigger()
        qt_app.processEvents()
        assert win.spec_vscale_button.text()=="÷ 100 (лок.)"
        extended=win.spec_plot.getViewBox().viewRange()[1]
        assert extended[1]-extended[0]==pytest.approx(
            12*local_max,rel=1e-4)
        assert _fft_digest(win)==same_sha
        assert win._spec_vscroll_source_candidate[
            "qt_y_baseline_from_local_spectrum"]
        win.spec_vscale_menu.actions()[3].trigger()
        qt_app.processEvents()
        restored=win.spec_plot.getViewBox().viewRange()[1]
        assert restored==pytest.approx(span,rel=1e-4,abs=1e-6)
        assert _fft_digest(win)==same_sha
    finally:
        win.close()
        qt_app.processEvents()
