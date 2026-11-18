"""Screenshot-driven primary vibration spectrum controls. All network off."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def gui():
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    from PySide6.QtWidgets import QApplication
    from mvk_live_standalone.app import LiveWindow
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    w = LiveWindow()
    yield w, app
    w.close()
    w.deleteLater()
    app.processEvents()


def _ax_label(w):
    return w.spec.getPlotItem().getAxis("left").label.toPlainText()


def test_primary_controls_match_user_screenshots_without_advanced_clutter(gui):
    from PySide6 import QtCore
    w, _ = gui
    assert w.spectrum_view.count() == 4
    assert [w.spectrum_view.itemText(i) for i in range(4)] == [
        "Логарифмическая (ВУ, дБ)", "Линейный ВУ",
        "Линейный ВС", "Линейный ВП",
    ]
    assert w.spectrum_view.currentData() == "log_vu"
    assert w.yscale.currentData() == "db"
    assert "дБ" in _ax_label(w)
    assert w.xscale.currentData() == "linear"
    assert w.analysis.currentData() == "fft"
    assert w.filter_choice.currentData() == "none"
    assert w._read_settings()[3] == (0.0, None)
    assert w._read_settings()[-1] is None
    assert w.envelope_band.isHidden()
    assert w.advanced_panel.isHidden()
    assert not w.filter_button.isEnabled()
    assert w._native.state() == QtCore.QProcess.ProcessState.NotRunning
    assert w._capture_root is None
    # Technical paths remain usable without occupying the operator screen.
    assert w.exe_path.parent() is not None
    assert w.exe_sha.parent() is not None


@pytest.mark.parametrize(
    "key,kind,scale,unit",
    [
        ("log_vu","acceleration","db","дБ"),
        ("linear_vu","acceleration","linear","м/с²"),
        ("linear_vs","velocity","linear","мм/с"),
        ("linear_vp","displacement","linear","мкм"),
    ],
)
def test_switching_one_view_immediately_changes_y_physical_units(gui,key,kind,scale,unit):
    w,_=gui
    w.spectrum_view.setCurrentIndex(w.spectrum_view.findData("linear_vp"))
    w.spectrum_view.setCurrentIndex(w.spectrum_view.findData(key))
    assert w.kind.currentData()==kind
    assert w.yscale.currentData()==scale
    assert w.analysis.currentData()=="fft"
    assert w.xscale.currentData()=="linear"
    assert unit in _ax_label(w)
    assert unit in w.y_height_choice.itemText(1)
    assert w.y_height_choice.currentData() is None


def test_filter_selector_controls_real_processing_and_has_no_envelope_default(gui):
    w,_=gui
    w.spectrum_view.setCurrentIndex(w.spectrum_view.findData("linear_vu"))
    assert w._read_settings()[3]==(0.0,None)
    w.filter_choice.setCurrentIndex(w.filter_choice.findData("highpass"))
    assert w.filter_button.isEnabled()
    assert w._read_settings()[3]==(10.0,None)
    w.filter_choice.setCurrentIndex(w.filter_choice.findData("lowpass"))
    assert w._read_settings()[3]==(0.0,1000.0)
    w.filter_choice.setCurrentIndex(w.filter_choice.findData("bandpass"))
    assert w._read_settings()[3]==(10.0,1000.0)
    w.filter_choice.setCurrentIndex(w.filter_choice.findData("notch50"))
    assert w._read_settings()[3]==(0.0,None)
    assert w._read_settings()[-1]==50.0
    assert not w.filter_button.isEnabled()
    w.filter_choice.setCurrentIndex(w.filter_choice.findData("notch60"))
    assert w._read_settings()[-1]==60.0
    w.filter_choice.setCurrentIndex(w.filter_choice.findData("none"))
    assert w._read_settings()[3]==(0.0,None)
    assert w._read_settings()[-1] is None
    assert "Без пользовательского фильтра" in w.operator_info.text()
    assert w.analysis.currentData()=="fft"


def test_frequencies_on_x_are_real_hertz_and_clamped_by_sample_rate(gui):
    from mvk_live_standalone.live_ipc import IPCPreview,IPCChannel,DOMAIN
    w,_=gui
    samples=np.ones(8192,dtype="<f4")
    packet=IPCChannel(1,512,samples,8192,8192,
                      hashlib.sha256(samples.tobytes()).hexdigest())
    w._gui_ring.ingest_preview(IPCPreview(
        "OFFLINE_TEST",DOMAIN,True,datetime.now(timezone.utc),{1:packet}))
    w.x_limit_choice.setCurrentIndex(w.x_limit_choice.findData(25600))
    low,high=w.spec.viewRange()[0]
    assert low==pytest.approx(0,abs=1e-5)
    assert high==pytest.approx(256,abs=1e-4)
    assert "Nyquist" in w.operator_info.text()
    w.x_limit_choice.setCurrentIndex(w.x_limit_choice.findData(50))
    assert w.spec.viewRange()[0][1]==pytest.approx(50,abs=1e-4)
    assert "Nyquist" not in w.operator_info.text()


def test_y_widths_use_selected_units_and_change_graph_range(gui):
    w,_=gui
    for key,unit in (("log_vu","дБ"),("linear_vu","м/с²"),
                     ("linear_vs","мм/с"),("linear_vp","мкм")):
        w.spectrum_view.setCurrentIndex(w.spectrum_view.findData(key))
        assert unit in w.y_height_choice.itemText(1)
        chosen=w.y_height_choice.itemData(2)
        w.y_height_choice.setCurrentIndex(2)
        ylo,yhi=w.spec.viewRange()[1]
        assert yhi-ylo==pytest.approx(chosen,rel=1e-4)
        if key!="log_vu":
            assert ylo==pytest.approx(0.0,abs=1e-5)
        else:
            assert ylo<0 or yhi>0


def test_envelope_filter_only_shown_inside_explicit_advanced_envelope(gui):
    w,_=gui
    assert w.envelope_band.isHidden()
    w.advanced_toggle.setChecked(True)
    assert w.analysis.currentData()=="fft"
    assert w.envelope_band.isHidden()
    w.analysis.setCurrentIndex(w.analysis.findData("envelope"))
    assert not w.envelope_band.isHidden()
    assert not w.envelope_label.isHidden()
    w.analysis.setCurrentIndex(w.analysis.findData("fft"))
    assert w.envelope_band.isHidden()
    w.advanced_toggle.setChecked(False)
    assert w.advanced_panel.isHidden()

def test_octave_spectrum_operator_choose_nominal_center_without_manual_entry(gui):
    w,_=gui
    from mvk_live_standalone.octave_filters import preset_band
    w.filter_choice.setCurrentIndex(w.filter_choice.findData("third_octave"))
    assert w.filter_center.count()==43
    assert not w.filter_button.isEnabled()
    w.filter_center.setCurrentIndex(w.filter_center.findData(1000.))
    import numpy as np
    np.testing.assert_allclose(w._read_settings()[3],
                               preset_band("third_octave",1000.))
    assert "1/3 октавы" in w.operator_info.text()
    w.filter_choice.setCurrentIndex(w.filter_choice.findData("octave"))
    assert "1/1 октавы" in w._filter_description()
    assert not w.filter_button.isEnabled()
    w.filter_choice.setCurrentIndex(w.filter_choice.findData("none"))
    assert w.filter_center.isHidden()

def test_original_mvkview_32_label_menu_keeps_local_filter_provenance(gui):
    w,_=gui
    from mvk_live_standalone.octave_filters import preset_band, ORIGINAL_MVK_MENU
    import numpy as np
    w.filter_choice.setCurrentIndex(w.filter_choice.findData("original_preset"))
    assert w.filter_center.count()==32
    assert w.filter_center.currentData()==("none",None)
    assert w._read_settings()[3]==(0.,None)
    assert [w.filter_center.itemText(i) for i in range(32)]==[
        label for label,_,_ in ORIGINAL_MVK_MENU]
    ix=w.filter_center.findData(("third_octave",25000.))
    assert ix>=0
    w.filter_center.setCurrentIndex(ix)
    np.testing.assert_allclose(w._read_settings()[3],
                               preset_band("third_octave",25000.))
    assert "локальный фильтр" in w._filter_description()
    assert "1/3окт 25 кГц" in w._filter_description()
    w.filter_center.setCurrentIndex(
        w.filter_center.findData(("octave",16000.)))
    assert "1окт 16 кГц" in w._filter_description()
    w.filter_center.setCurrentIndex(
        w.filter_center.findData(("double_octave",13000.)))
    assert "2окт 13 кГц" in w._filter_description()
    assert not w.filter_button.isEnabled()
    w.filter_choice.setCurrentIndex(w.filter_choice.findData("none"))
    assert w.filter_center.isHidden()
