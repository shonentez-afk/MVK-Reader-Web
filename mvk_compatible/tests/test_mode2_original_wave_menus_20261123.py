"""PageAdc popup acceptance against four owner screenshots (2026-11-23).

All Qt windows use synthetic BIN/TSXML. This is a screenshot-based UI
regression, NOT a physical-device or Win32/x87 calibration oracle.
"""
import pytest

from ..core.original_adc_view_controls import (
    ADC_HORIZONTAL_MS, ADC_VERTICAL_DIVISORS,
    original_adc_vertical_options, original_adc_vertical_physical_caption,
    local_adc_vertical_peak_fit,source_live_adc_vertical_view,
)
from ..core.original_envelope_shared_menu import SOURCE_ORIGINAL_FILTER_CAPTIONS
from .test_desktop_qt import qt_app


def test_original_wave_popup_tables_and_1000_reference():
    assert ADC_HORIZONTAL_MS == (
        20000,10000,5000,2000,1000,500,200,100,50,20,10,5,2,1)
    assert ADC_VERTICAL_DIVISORS == (
        1,2,5,10,20,50,100,200,500,1000,2000,5000,10000)
    assert len(SOURCE_ORIGINAL_FILTER_CAPTIONS)==32
    assert [r["caption"] for r in original_adc_vertical_options(
        baseline_m_s2=1000.)] == [
        "1000 м/с2", "500 м/с2", "200 м/с2", "100 м/с2",
        "50 м/с2", "20 м/с2", "10 м/с2", "5 м/с2",
        "2 м/с2", "1 м/с2", "0,5 м/с2", "0,2 м/с2",
        "0,1 м/с2",
    ]
    with pytest.raises(ValueError):
        original_adc_vertical_physical_caption(13,1000.)
    with pytest.raises(ValueError):
        original_adc_vertical_physical_caption(0,float("nan"))
    with pytest.raises(ValueError):
        original_adc_vertical_physical_caption(0,0.)
    assert original_adc_vertical_physical_caption(2,200.)=="40 м/с2"
    # A source FRange may lead to an original rounded baseline; a
    # missing FRange never prints nine arbitrary decimals from raw peak.
    assert local_adc_vertical_peak_fit(0)==pytest.approx(1e-12)
    assert local_adc_vertical_peak_fit(.2133)==pytest.approx(.5)
    assert local_adc_vertical_peak_fit(1.1)==pytest.approx(2.)
    assert local_adc_vertical_peak_fit(23.)==pytest.approx(50.)
    with pytest.raises(ValueError):
        local_adc_vertical_peak_fit(float("nan"))
    with pytest.raises(ValueError):
        local_adc_vertical_peak_fit(-1.)


def test_wave_qt_4_original_popup_menus_and_selection(qt_app,tmp_path):
    pytest.importorskip("PySide6")
    from ..desktop.main_window import MainWindow
    from .test_stage111z16_direct_bin_tsxml import _make_pair
    path,sidecar,_ = _make_pair(tmp_path,adc=4,n=8192,fs=65536)
    raw=sidecar.read_text(encoding="utf-8")
    sidecar.write_text(raw.replace(
        "</Channel>",
        "<InternalChannelGain>510.6</InternalChannelGain></Channel>"),
        encoding="utf-8")
    win=MainWindow()
    win.show()
    try:
        win.open_archive(path)
        win.tabs.setCurrentIndex(1)
        qt_app.processEvents()
        assert [a.text() for a in win.wave_type_menu.actions()]==["AC","AC+DC"]
        assert [a.text() for a in win.wave_hscale_menu.actions()]==[
            "20 с","10 с","5 с","2 с","1 с","500 мс","200 мс",
            "100 мс","50 мс","20 мс","10 мс","5 мс","2 мс","1 мс"]
        assert [a.text() for a in win.wave_vscale_menu.actions()]==[
            r["caption"] for r in original_adc_vertical_options(
                baseline_m_s2=1000.)]
        assert len(win.original_envelope_menu.actions())==32
        assert [a.text() for a in win.original_envelope_menu.actions()]==list(
            SOURCE_ORIGINAL_FILTER_CAPTIONS)
        assert win.wave_vscale_button.text()=="1000 м/с2"
        assert [i for i,a in enumerate(win.wave_vscale_menu.actions())
                if a.isChecked()]==[0]
        # Vertical-only action must reframe the FULL source data, not
        # call GetSignal or alter the cached waveform/FFT.
        original_trace=win._source_wave_trace
        original_fft=win._full_spectrum
        win.wave_vscale_menu.actions()[1].trigger()
        assert win._source_wave_trace is original_trace
        assert win._full_spectrum is original_fft
        assert win.wave_vscale_menu.actions()[1].isChecked()
        win.wave_type_menu.actions()[1].trigger()
        win.wave_hscale_menu.actions()[5].trigger()
        win.wave_vscale_menu.actions()[10].trigger()
        qt_app.processEvents()
        assert win.wave_type_button.text()=="AC+DC"
        assert win.wave_hscale_button.text()=="500 мс"
        assert win.wave_vscale_button.text()=="0,5 м/с2"
        assert [i for i,a in enumerate(win.wave_vscale_menu.actions())
                if a.isChecked()]==[10]
        assert "калибровка не подтверждена" in (
            win.wave_vscale_button.toolTip())
        assert win._source_wave_scale_model is not None
        assert win._source_wave_scale_model[
            "axis_baseline_m_s2_nominal"]==pytest.approx(1000.)
    finally:
        win.close()


def test_wave_no_frange_numeric_labels_disclose_local_fallback(qt_app,tmp_path):
    pytest.importorskip("PySide6")
    from ..desktop.main_window import MainWindow
    from .test_stage111z16_direct_bin_tsxml import _make_pair
    path,_,_=_make_pair(tmp_path,adc=1,n=8192,fs=65536)
    win=MainWindow()
    win.show()
    try:
        win.open_archive(path)
        win.tabs.setCurrentIndex(1)
        qt_app.processEvents()
        captions=[a.text() for a in win.wave_vscale_menu.actions()]
        assert len(captions)==13
        assert all("м/с2" in item for item in captions)
        assert not any("диапазона" in item for item in captions)
        assert win.wave_vscale_button.text()==captions[win._wave_vscale_tag]
        assert "калибровка не подтверждена" in (
            win.wave_vscale_button.toolTip())
        assert win._source_wave_scale_model["source_f_range_single"] is None
        peak=win._source_wave_scale_model["window_peak_from_core"]
        basis=win._source_wave_scale_model["axis_baseline_m_s2_nominal"]
        assert basis==local_adc_vertical_peak_fit(peak)
        assert basis>=peak
        assert win.wave_vscale_menu.actions()[0].text()==(
            original_adc_vertical_physical_caption(0,basis))
    finally:
        win.close()


def test_live_y_source_frange1_vs_local_preview_never_transmits():
    """Provenance-bound Y only; no virtual instrument connection."""
    local=source_live_adc_vertical_view(
        full_peak=2.4,tag=2,source_frange1=False)
    assert local["axis_baseline_m_s2_nominal"]==5.
    assert local["local_half_height"]==pytest.approx(1.)
    assert local["source_f_range1_verified"] is False
    assert local["device_io_performed"] is False
    assert local["wave_samples_recomputed_by_view"] is False

    live=source_live_adc_vertical_view(
        full_peak=2.4,tag=2,source_frange1=True)
    assert live["source_f_range1_verified"] is True
    assert live["axis_baseline_m_s2_nominal"]==pytest.approx(1.)
    assert live["local_half_height"]==pytest.approx(.2)
    assert live["physical_sensor_calibration_verified"] is False
    assert live["original_delphi_canvas_parity_verified"] is False
    for invalid in (float("nan"), float("inf"),-1.):
        with pytest.raises(ValueError):
            source_live_adc_vertical_view(
                full_peak=invalid,tag=0,source_frange1=False)
    with pytest.raises(ValueError):
        source_live_adc_vertical_view(
            full_peak=1.,tag=0,source_frange1=1)


def test_qt_live_y_popup_reframes_cached_wave_only(qt_app):
    """No TCP; a pre-validated snapshot is sufficient for Y-only action."""
    pytest.importorskip("PySide6")
    from ..desktop.main_window import MainWindow
    w=MainWindow()
    w.show()
    try:
        w._live_active=True
        w._native_live_status={
            "session_id":"SYNTHETIC-WAVE-Y-ONLY", "phase":"RECORDING",
            "snapshot_stale":False}
        w._live_wave_vertical_basis=dict(
            adc=w._ch(),session_id="SYNTHETIC-WAVE-Y-ONLY",
            full_peak=2.4,source_frange1=False,
            source_sha256="synthetic-no-device-sha")
        same=w._live_wave_vertical_basis
        w.wave_vscale_menu.actions()[2].trigger()  # base 5 / 5 = 1
        qt_app.processEvents()
        assert w._live_wave_vertical_basis is same
        assert w._live_wave_scale_model["device_io_performed"] is False
        assert w._live_wave_scale_model["local_half_height"]==pytest.approx(1.)
        assert w.wave_vscale_button.text()=="1 м/с2"
        assert w.wave_vscale_menu.actions()[2].isChecked()
        vr=w.wave_plot.getViewBox().viewRange()[1]
        assert vr[0]==pytest.approx(-1.,abs=1e-5)
        assert vr[1]==pytest.approx(1.,abs=1e-5)
        # Change current session: stale bound values must not be reused.
        w._native_live_status["session_id"]="OTHER-SYNTHETIC-SESSION"
        w.wave_vscale_menu.actions()[3].trigger()
        assert w._live_wave_scale_model is None
        assert w.wave_vscale_button.text()=="100 м/с2"
        assert "калибровка не подтверждена" in w.wave_vscale_button.toolTip()
    finally:
        w._live_active=False
        w.close()
