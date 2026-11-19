"""Qt cursor acceptance: physical values, linked plots and no MVK01 socket."""
from __future__ import annotations

import hashlib
import math
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
    win = LiveWindow()
    yield win, app
    win.close()
    win.deleteLater()
    app.processEvents()


def _feed(win):
    from mvk_live_standalone.live_ipc import IPCPreview, IPCChannel, DOMAIN
    fs, n = 8192, 32768
    t = np.arange(n, dtype=np.float64)/fs
    x = np.asarray(np.sqrt(2)*np.sin(2*np.pi*100*t)
                   + .2*np.sin(2*np.pi*200*t), dtype="<f4")
    channel = IPCChannel(1, fs, x, n % (1 << 32), n,
                         hashlib.sha256(x.tobytes()).hexdigest())
    preview = IPCPreview("TEST_CURSOR_ONLY", DOMAIN, True,
                         datetime.now(timezone.utc), {1:channel})
    win._gui_ring.ingest_preview(preview)
    win._preview = preview
    return x, fs


def _spectrum(win, mode="fft"):
    from mvk_live_standalone.vibration import analyze_vibration
    x, fs = _feed(win)
    win.nfft.setCurrentIndex(win.nfft.findData(8192))
    win.yscale.setCurrentIndex(win.yscale.findData("linear"))
    win._spectrum = analyze_vibration(
        x, fs, kind="acceleration", mode=mode, nfft=8192)
    win._render_spectrum()
    win._render_wave()
    return x, fs


def test_cursors_exist_but_no_fake_readings_without_data(gui):
    w, _ = gui
    c = w._professional_cursors
    assert c.mode.count() == 6
    assert c.time_mode.count() == 3
    assert not c.a_spec.isVisible()
    assert not c.a_time.isVisible()
    assert not c.bearing_line.isVisible()
    assert "Нет подтверждённого" in c.spec_readout.text()
    assert w._native.state() == w._native.ProcessState.NotRunning
    assert w._capture_root is None


def test_spectrum_peak_cursor_uses_full_real_fft_and_links_both_plots(gui):
    w, _ = gui
    _spectrum(w)
    c = w._professional_cursors
    c.mode.setCurrentIndex(c.mode.findData("peak"))
    c._set_spectrum_selection(103.0)
    assert c.a_hz == pytest.approx(100., abs=1.)
    assert c.a_spec.value() == pytest.approx(c.a_overview.value())
    assert c.a_spec.isVisible() and c.a_overview.isVisible()
    assert "100" in c.spec_readout.text()
    assert "м/с²" in c.spec_readout.text()
    assert len(w.spec_curve.getData()[0]) > 10
    assert w._native.state() == w._native.ProcessState.NotRunning


def test_dual_frequency_cursors_and_harmonic_and_sideband_markers(gui):
    w, _ = gui
    _spectrum(w)
    c = w._professional_cursors
    c.mode.setCurrentIndex(c.mode.findData("dual"))
    c.a_hz, c.b_hz = 100., 200.
    c.refresh_spectrum()
    assert c.b_spec.isVisible() and c.b_overview.isVisible()
    assert "Разность частот: 100" in c.spec_readout.text()
    c.mode.setCurrentIndex(c.mode.findData("harmonics"))
    assert c._comb_lines
    assert len(c._comb_lines) >= 8
    c.mode.setCurrentIndex(c.mode.findData("sidebands"))
    c.sideband_spacing.setValue(25.)
    assert c._comb_lines
    assert "расчётные" in c.spec_readout.text()
    c.mode.setCurrentIndex(c.mode.findData("single"))
    assert not c.b_spec.isVisible()
    assert c._comb_lines == []


def test_log_frequency_coordinates_remain_linked_and_physical(gui):
    w, _ = gui
    _spectrum(w)
    c = w._professional_cursors
    c._set_spectrum_selection(100.0)
    w.xscale.setCurrentIndex(w.xscale.findData("log"))
    assert c.a_hz == pytest.approx(100., abs=1.)
    assert c.a_spec.value() == pytest.approx(math.log10(100.), abs=1e-5)
    assert c.a_overview.value() == pytest.approx(math.log10(100.), abs=1e-5)
    c.step_spectrum(1)
    assert c.a_hz == pytest.approx(101.)
    assert "Гц" in c.spec_readout.text()
    w.xscale.setCurrentIndex(w.xscale.findData("linear"))
    assert c.a_spec.value() == pytest.approx(c.a_hz)


def test_time_cursor_reads_full_filtered_samples_not_decimated_render(gui):
    w, _ = gui
    _spectrum(w)
    c = w._professional_cursors
    assert c.a_time.isVisible() and c.a_time_overview.isVisible()
    assert len(w._cursor_time_samples) > 0
    c.time_mode.setCurrentIndex(c.time_mode.findData("interval"))
    c.a_seconds, c.b_seconds = -.25, -.05
    c.refresh_time()
    assert c.a_time.value() == pytest.approx(c.a_time_overview.value())
    assert c.b_time.value() == pytest.approx(c.b_time_overview.value())
    assert "Δt" in c.time_readout.text()
    assert "СКЗ" in c.time_readout.text()
    assert "размах" in c.time_readout.text()
    c.time_mode.setCurrentIndex(c.time_mode.findData("single"))
    assert not c.b_time.isVisible()
    assert c.a_time.isVisible()


def test_spectrum_band_uses_psd_density_integration_not_sum_of_fft_lines(gui):
    w, _ = gui
    _spectrum(w, mode="welch")
    c = w._professional_cursors
    c.mode.setCurrentIndex(c.mode.findData("band"))
    c.a_hz, c.b_hz = 75., 125.
    c.refresh_spectrum()
    assert "СКЗ выбранной полосы" in c.spec_readout.text()
    w._spectrum = None
    c.refresh_spectrum()
    assert not c.a_spec.isVisible()
    assert "Нет подтверждённого" in c.spec_readout.text()


def test_envelope_has_independent_measured_cursor_without_fault_claim(gui):
    from mvk_live_standalone.vibration import analyze_vibration
    w, _ = gui
    x, fs = _feed(w)
    w._bearing_spectrum = analyze_vibration(
        x, fs, mode="envelope", kind="acceleration", nfft=8192,
        envelope_band_hz=(500., 1500.))
    assert w._spectrum is None
    w._show_bearing_diagnostics()
    c = w._professional_cursors
    assert c.bearing_line.isVisible()
    assert "Измеренная линия огибающей" in c.bearing_readout.text()
    assert "не заключение о дефекте" in c.bearing_readout.text()
    w._bearing_spectrum = None
    c.refresh_bearing()
    assert not c.bearing_line.isVisible()


def test_adc_change_clears_old_spectrum_and_cursors_before_next_window(gui):
    w, _ = gui
    _spectrum(w)
    c = w._professional_cursors
    assert c.a_spec.isVisible()
    w.adc.setCurrentIndex(w.adc.findData(2))
    assert w._spectrum is None
    assert not c.a_spec.isVisible()
    assert not c.bearing_line.isVisible()
    assert "Нет подтверждённого спектра" in c.spec_readout.text()
    assert w._gui_ring.channel(2) is None
