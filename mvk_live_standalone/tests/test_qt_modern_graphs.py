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
    assert "100" in w.spec.getPlotItem().titleLabel.text
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
