"""Modern main-window, axes and filter QA without hardware TCP.

Synthetic test signals are never injected into the production receiver:
only the isolated verified Float32 test ring is exercised here.
"""
from __future__ import annotations
import hashlib
import math
import os
from datetime import datetime, timezone

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def widget():
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    from PySide6.QtWidgets import QApplication
    from mvk_live_standalone.app import LiveWindow
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    window = LiveWindow()
    yield window, app
    window.close()
    window.deleteLater()
    app.processEvents()


def _feed(w, fs=8192, n=32768):
    from mvk_live_standalone.live_ipc import IPCPreview, IPCChannel, DOMAIN
    t = np.arange(n, dtype=np.float64)/fs
    x = np.asarray(np.sqrt(2)*np.sin(2*np.pi*100*t), dtype="<f4")
    ch = IPCChannel(1, fs, x, n % (1 << 32), n,
                    hashlib.sha256(x.tobytes()).hexdigest())
    preview = IPCPreview("TEST_MODERN", DOMAIN, True,
                         datetime.now(timezone.utc), {1: ch})
    w._gui_ring.ingest_preview(preview)
    w._preview = preview
    return x


def test_main_has_one_global_adc_four_tabs_and_eight_working_menus(widget):
    w,_ = widget
    assert w._modern_installed
    assert [w.views.tabText(i) for i in range(w.views.count())] == [
        "Обзор", "Спектр", "Временной сигнал", "Расчётные данные"]
    assert w.views.currentWidget() == w.overview_page
    assert w.adc.count() == 8
    assert w.dsp_adc.isHidden() and w.extra_adc.isHidden()
    assert [a.text() for a in w.menuBar().actions()] == [
            "Файл", "Измерение", "Анализ", "Диагностика",
            "Архив", "Вид", "Настройки", "Справка"]
    assert w._native.state() == w._native.ProcessState.NotRunning
    assert w._capture_root is None


def test_operator_labels_describe_real_quantities_not_x_y(widget):
    """Ordinary measurement controls must name physical quantities, not axes."""
    import re
    from PySide6 import QtWidgets
    w, _ = widget
    inspector_labels = [item.text() for item in
                        w._modern_inspector.findChildren(QtWidgets.QLabel)]
    for required in (
        "Шкала значений", "Частотная шкала", "Показывать частоты до",
        "Масштаб спектра", "Развёртка времени",
        "Масштаб виброускорения", "Фильтр временного сигнала",
    ):
        assert required in inspector_labels
    assert not any(re.search(r"(?<![A-Za-zА-Яа-я])[XY](?![A-Za-zА-Яа-я])", label)
                   for label in inspector_labels)
    assert [w.xscale.itemText(i) for i in range(w.xscale.count())] == [
        "Линейная", "Логарифмическая"]
    assert [w.yscale.itemText(i) for i in range(w.yscale.count())] == [
        "Линейная", "В децибелах (дБ)"]
    assert "время в мс/с" in w.wave_info.text()
    assert "X" not in w.operator_info.text()


def test_spectrum_and_overview_render_the_same_real_source(widget):
    w,_ = widget
    from mvk_live_standalone.vibration import analyze_vibration
    data = _feed(w)
    w.nfft.setCurrentIndex(w.nfft.findData(8192))
    w.kind.setCurrentIndex(w.kind.findData("acceleration"))
    w.yscale.setCurrentIndex(w.yscale.findData("linear"))
    w._spectrum = analyze_vibration(data, 8192,
                  kind="acceleration",mode="fft",nfft=8192)
    w._render_spectrum()
    sx,sy = w.spec_curve.getData()
    ox,oy = w.overview_spec_curve.getData()
    np.testing.assert_allclose(sx,ox)
    np.testing.assert_allclose(sy,oy)
    assert len(ox)>20
    assert w._spectrum.peak[0] == pytest.approx(100, abs=1)
    w._render_wave()
    tx,ty = w.wave_curve.getData()
    ux,uy = w.overview_wave_curve.getData()
    np.testing.assert_allclose(tx,ux)
    np.testing.assert_allclose(ty,uy)


def test_manual_axes_survive_another_verified_fft_frame(widget):
    w,_ = widget
    from mvk_live_standalone.vibration import analyze_vibration
    data = _feed(w)
    w.nfft.setCurrentIndex(w.nfft.findData(8192))
    w.yscale.setCurrentIndex(w.yscale.findData("linear"))
    w._spectrum = analyze_vibration(
        data,8192,mode="fft",nfft=8192)
    w._render_spectrum()
    w._manual_spec_axes=(10.0,200.0,0.0,3.0)
    w._render_spectrum()
    assert w.spec.viewRange()[0] == pytest.approx([10,200],abs=1e-4)
    assert w.overview_spec.viewRange()[0] == pytest.approx([10,200],abs=1e-4)
    w._spectrum = analyze_vibration(
        data*0.5,8192,mode="fft",nfft=8192)
    w._render_spectrum()
    assert w.spec.viewRange()[0] == pytest.approx([10,200],abs=1e-4)
    assert w.spec.viewRange()[1] == pytest.approx([0,3],abs=1e-4)
    w._reset_spectrum_axis()
    assert w._manual_spec_axes is None
    assert w.spec.viewRange()[0][0] == pytest.approx(0,abs=1e-4)


def test_logarithmic_frequency_axis_has_no_zero_and_physical_cursor(widget):
    w,_=widget
    from mvk_live_standalone.vibration import analyze_vibration
    data = _feed(w)
    w.nfft.setCurrentIndex(w.nfft.findData(8192))
    w.yscale.setCurrentIndex(w.yscale.findData("linear"))
    w._spectrum = analyze_vibration(data,8192,mode="fft",nfft=8192)
    w.xscale.setCurrentIndex(w.xscale.findData("log"))
    w._render_spectrum()
    low,high = w.spec.viewRange()[0]
    assert math.isfinite(low) and math.isfinite(high)
    assert low == pytest.approx(0,abs=1e-3)  # log10(8192/8192)=0
    assert high == pytest.approx(3,abs=1e-3)  # log10(1000 Hz)=3
    w.cursor.setValue(math.log10(100))
    w._cursor_text()
    assert "100" in w._professional_cursors.spec_readout.text()
    # This dB mode is a numeric Y ordinate; a second log Y is invalid.
    w.yscale.setCurrentIndex(w.yscale.findData("db"))
    assert "дБ" in w.spec.getPlotItem().getAxis("left").label.toPlainText()


def test_filter_preview_is_two_pass_and_has_no_device_side_effects():
    from mvk_live_standalone.graph_policies import (
        filter_magnitude_response, spectrum_x_limits)
    hz, response=filter_magnitude_response(8192,band_hz=(150,400))
    assert len(hz)==512 and len(response)==512
    assert float(np.interp(250,hz,response))> -7
    assert float(np.interp(25,hz,response))< -30
    z,a=filter_magnitude_response(8192)
    assert np.array_equal(z,hz)
    assert np.all(a==0.0)
    with pytest.raises(ValueError):
        filter_magnitude_response(512,band_hz=(100,300))
    with pytest.raises(ValueError):
        spectrum_x_limits(512,8192,0.0,log_x=True)


def test_detached_method_windows_are_not_extra_main_tabs(widget):
    w,_=widget
    from mvk_live_standalone.modern_shell import open_advanced_window
    stft=open_advanced_window(w,"stft")
    again=open_advanced_window(w,"stft")
    kurt=open_advanced_window(w,"kurtogram")
    assert stft is again
    assert stft is not kurt
    assert stft.centralWidget() is w.extra_method_pages["stft"]
    assert kurt.centralWidget() is w.kurtogram_page
    assert len(w._modern_windows)==2
    assert w.views.count()==4
    assert w._native.state()==w._native.ProcessState.NotRunning


def test_original_four_views_are_presets_not_forced_x_or_psd_modes(widget):
    w,_=widget
    w.analysis.setCurrentIndex(w.analysis.findData("welch"))
    w.xscale.setCurrentIndex(w.xscale.findData("log"))
    w.spectrum_view.setCurrentIndex(w.spectrum_view.findData("linear_vs"))
    assert w.kind.currentData()=="velocity"
    assert w.yscale.currentData()=="linear"
    assert w.xscale.currentData()=="log"
    assert w.analysis.currentData()=="welch"
    assert "мм/с" in w.y_height_choice.itemText(1)
    assert not w.y_height_choice.isEnabled()  # PSD has power density units
    w.analysis.setCurrentIndex(w.analysis.findData("fft"))
    assert w.y_height_choice.isEnabled()


def test_standalone_stft_is_pinned_and_survives_main_adc_switch(widget):
    w,_=widget
    from mvk_live_standalone.modern_shell import open_advanced_window
    _feed(w)
    child=open_advanced_window(w,"stft")
    pin=w._modern_method_pins["stft"]
    assert pin["adc"]==1 and pin["fs"]==8192
    assert not pin["samples"].flags.writeable
    assert len(pin["samples"])==8192
    w.adc.setCurrentIndex(1)  # ADC 2 has no samples
    assert pin["adc"]==1
    w._start_extra_mode("stft")
    assert w._extra_future is not None
    w._extra_future.result(timeout=40)
    w._poll_extra()
    assert w._extra_future is None
    assert w._modern_windows["stft"] is child
    assert "APP_DERIVED" in w.extra_method_infos["stft"].text()
    assert "старый результат отброшен" not in w.extra_method_infos["stft"].text()


def test_inspector_is_compact_vertical_without_horizontally_clipped_fields(widget):
    w,app=widget
    from PySide6 import QtCore,QtWidgets
    w.resize(1600,900)
    w.show()
    app.processEvents()
    scroll=w._modern_inspector_dock.widget()
    assert isinstance(scroll,QtWidgets.QScrollArea)
    assert scroll.horizontalScrollBarPolicy()==QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    # The right inspector uses stacked labels/controls instead of the old
    # two-column QFormLayout that needed a horizontal scrollbar at 1600 px.
    assert len(w._modern_inspector.findChildren(QtWidgets.QFormLayout))==0
    assert len(w._modern_metric_values)==4
    assert all(v.text()=="—" for v in w._modern_metric_values.values())
    spectrum_pane=w._modern_inspector.widget(0)
    toggles=spectrum_pane.findChildren(QtWidgets.QToolButton)
    assert toggles and not toggles[0].isChecked()
    assert w._modern_inspector_dock.width()>=246
    assert scroll.widget().width()<=scroll.viewport().width()+2
    assert w.views.count()==4


def test_overview_curve_is_cleared_after_switch_to_unavailable_adc(widget):
    w,_=widget
    from mvk_live_standalone.vibration import analyze_vibration
    data=_feed(w)
    w.nfft.setCurrentIndex(w.nfft.findData(8192))
    w._spectrum=analyze_vibration(data,8192,nfft=8192)
    w._render_spectrum()
    w._render_wave()
    assert len(w.overview_spec_curve.getData()[0])>0
    assert len(w.overview_wave_curve.getData()[0])>0
    w.adc.setCurrentIndex(1)
    w._render_wave()
    sx,_=w.overview_spec_curve.getData()
    tx,_=w.overview_wave_curve.getData()
    assert sx is None or len(sx)==0
    assert tx is None or len(tx)==0
    assert "нет подтверждённых" in w.overview_wave.getPlotItem().titleLabel.text.lower()


def test_bearing_window_pins_source_and_never_reconfigures_live_fft(widget):
    """Independent bearing operation must not change main FFT settings."""
    w,_=widget
    from mvk_live_standalone.modern_shell import open_advanced_window
    _feed(w)
    w.nfft.setCurrentIndex(w.nfft.findData(8192))
    w.kind.setCurrentIndex(w.kind.findData("velocity"))
    w.analysis.setCurrentIndex(w.analysis.findData("welch"))
    w.bearing_fft.setCurrentIndex(w.bearing_fft.findData(8192))
    before=(w.kind.currentData(),w.analysis.currentData(),
            w.nfft.currentData(),w.envelope_band.currentData())
    child=open_advanced_window(w,"bearing")
    assert child.centralWidget() is w.diagnostics_page
    pin=w._modern_method_pins["bearing"]
    assert pin["adc"]==1 and pin["fs"]==8192
    assert len(pin["samples"])==8192
    assert not pin["samples"].flags.writeable
    w._run_bearing_page()
    view=w._bearing_spectrum
    assert view is not None and view.mode=="envelope"
    assert "АЦП 1" in w.bearing_plot.getPlotItem().titleLabel.text
    assert (w.kind.currentData(),w.analysis.currentData(),
            w.nfft.currentData(),w.envelope_band.currentData())==before
    w.adc.setCurrentIndex(w.adc.findData(2))
    assert w._bearing_spectrum is view
    assert w._modern_method_pins["bearing"] is pin
    assert w._professional_cursors.bearing_line.isVisible()
    np.testing.assert_allclose(w.bearing_curve.getData()[0],view.hz)
    w._clear("LIVE источник закрыт")
    assert w._bearing_spectrum is view  # unrelated session reset
    assert w._native.state()==w._native.ProcessState.NotRunning
    assert open_advanced_window(w,"bearing") is child


def test_bearing_source_must_be_explicit_and_large_fft_needs_new_capture(widget):
    w,_=widget
    from mvk_live_standalone.modern_shell import (
        open_advanced_window, _pin_method_source)
    child=open_advanced_window(w,"bearing")
    assert "bearing" not in w._modern_method_pins
    w._run_bearing_page()
    assert w._bearing_spectrum is None
    assert "Источник не закреплён" in w.bearing_diagnostics.text()
    _feed(w)
    w.bearing_fft.setCurrentIndex(w.bearing_fft.findData(8192))
    assert _pin_method_source(w,"bearing",child)
    w._run_bearing_page()
    assert w._bearing_spectrum is not None
    old_pin=w._modern_method_pins["bearing"]
    w.bearing_fft.setCurrentIndex(w.bearing_fft.findData(16384))
    w._run_bearing_page()
    assert w._bearing_spectrum is None
    assert "больше закреплённой выборки" in w.bearing_diagnostics.text()
    assert w._modern_method_pins["bearing"] is old_pin
    w.adc.setCurrentIndex(w.adc.findData(2))
    assert not _pin_method_source(w,"bearing",child)
    assert w._modern_method_pins["bearing"] is old_pin
