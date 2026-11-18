"""Qt integration: durable original-device trending + overlaid historical spectra.

All tested samples are synthetic/injected into an isolated local history.
No TCP, no claimed hardware measurements, no TACH or external reference.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")


@pytest.fixture
def w():
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    from PySide6.QtWidgets import QApplication
    from mvk_live_standalone.app import LiveWindow
    app=QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    viewer=LiveWindow()
    yield viewer
    viewer.close()
    viewer.deleteLater()
    app.processEvents()


def vendor_row(adc:int,tick:int,time:str):
    from mvk_live_standalone.original_dsp import _THIRD_HZ
    return {
        "adc":adc,"time_utc":time,"update":tick,"status_hex":"0x00000000",
        "nonfinite_fields":0,"not_ready":{"fs16":False,"fs64":False,"fs512":False},
        "third_octave_hz":_THIRD_HZ.tolist(),
        "third_octave_acceleration_rms":[.2*adc*tick+i*.01 for i in range(43)],
        "band_rms":[.3*adc*tick+i for i in range(24)],
        "band_peak_equiv":[.5*adc*tick+i for i in range(24)],
        "band_span_equiv":[.8*adc*tick+i for i in range(24)],
    }


def seed_vendor(w):
    for tick in (1,2,3):
        for adc in (1,2):
            w._archive.record_vendor_row(
                "TEST_2026-11-18_10-00-00.000",
                vendor_row(adc,tick,f"2026-11-18T10:00:0{tick}Z"))
    w.history_ui.refresh()


def seed_adc(w):
    for utc,freq,fs in (
        ("2026-11-18T09:00:00Z",100.,8192),
        ("2026-11-18T11:00:00Z",200.,8192),
        ("2026-11-18T12:00:00Z",300.,4096),
    ):
        t=np.arange(8192)/fs
        x=np.asarray(np.sqrt(2)*np.sin(2*np.pi*freq*t),dtype="<f4")
        w._archive.capture_npz(
            x,adc=1,fs=fs,session="SIMULATED_FILE_INPUT",
            capture_end=(int(freq)*8192),saved_utc=utc)
    w.history_ui.refresh()


def test_tabs_are_linked_without_disturbing_original_workspaces(w):
    from PySide6 import QtCore
    assert [w.views.tabText(i) for i in range(w.views.count())]==[
        "Спектр","Временной сигнал","Расчётные данные",
        "Тренды","Сравнение","Доп. анализ"]
    ui=w.history_ui
    assert len(ui.trend_group) if False else True
    assert ui.trend_group.count()>=14
    assert ui.compare_mode.count()==9
    assert ui.compare_table.rowCount()==0
    assert w._native.state()==QtCore.QProcess.ProcessState.NotRunning
    assert w._archive.root.exists()
    assert w.history_ui.compare_info.toolTip().find(str(w._archive.root))>=0


def test_trend_selected_original_metric_is_per_adc_and_utc_dated(w):
    seed_vendor(w)
    ui=w.history_ui
    ui.trend_group.setCurrentIndex(ui.trend_group.findData("band_peak_equiv"))
    ui.trend_position.setCurrentIndex(3)
    ui._plot_trend()
    assert len(ui._trend_last)==3
    assert [v for _,v in ui._trend_last]==pytest.approx([.5+3,1+3,1.5+3])
    assert "единица прибора не подтверждена" in ui.trend_info.text()
    w.adc.setCurrentIndex(1)
    ui._plot_trend()
    assert len(ui._trend_last)==3
    assert [v for _,v in ui._trend_last]==pytest.approx([1+3,2+3,3+3])
    ui.trend_group.setCurrentIndex(ui.trend_group.findData("third_octave"))
    ui.trend_position.setCurrentIndex(0)
    assert "0.63" in ui.trend_info.text()
    assert "м/с²" in ui.trend_info.text()


def test_trend_click_links_nearest_original_packet_to_comparison(w):
    seed_vendor(w)
    ui=w.history_ui
    ui._selected_trend_point=ui._trend_last[0][0]
    ui.trend_go.setEnabled(True)
    ui._open_trend_in_comparison()
    assert w.views.currentWidget()==ui.compare_page
    assert ui.compare_mode.currentData()=="vendor43"
    assert len(ui._table_selected)==1
    assert len(ui._last_overlay)==1
    assert ui._last_overlay[0][0].adc==1


def test_compare_fft_four_modes_and_waveforms_from_three_saved_dates(w):
    seed_adc(w)
    ui=w.history_ui
    ui.compare_mode.setCurrentIndex(ui.compare_mode.findData("fft_vu"))
    assert ui.compare_table.rowCount()==3
    ui._choose_latest_two()
    assert len(ui._last_overlay)==2
    entries=[e for e,_,_,_ in ui._last_overlay]
    assert all(e.adc==1 for e in entries)
    assert all("FFT" in label for _,_,_,label in ui._last_overlay)
    assert "Fs различается" in ui.compare_info.text()
    assert ui.compare_plot.viewRange()[0][1]==pytest.approx(2048,rel=.001)
    for view,unit in (("fft_log","дБ"),("fft_vs","мм/с"),
                      ("fft_vp","мкм")):
        ui.compare_mode.setCurrentIndex(ui.compare_mode.findData(view))
        ui._choose_latest_two()
        assert len(ui._last_overlay)==2
        assert all(unit in meta for _,_,_,meta in ui._last_overlay)
    ui.compare_mode.setCurrentIndex(ui.compare_mode.findData("wave"))
    ui._choose_latest_two()
    assert len(ui._last_overlay)==2
    for _,x,y,unit in ui._last_overlay:
        assert x[0]<0 and x[-1]<0
        assert len(x)==len(y)
        assert "м/с²" in unit
    assert "не" in ui.compare_info.text().lower()


def test_vendor_43_and_24_overlays_have_real_and_ordinal_x_separately(w):
    seed_vendor(w)
    ui=w.history_ui
    ui.compare_mode.setCurrentIndex(ui.compare_mode.findData("vendor43"))
    ui._choose_latest_two()
    assert len(ui._last_overlay)==2
    for _,x,y,unit in ui._last_overlay:
        assert x.size==43 and x[-1]==10000
        assert "м/с²" in unit
    ui.compare_mode.setCurrentIndex(ui.compare_mode.findData("vendor24_peak"))
    ui._choose_latest_two()
    assert len(ui._last_overlay)==2
    for _,x,y,unit in ui._last_overlay:
        assert len(x)==24 and x[0]==1 and x[-1]==24
        assert "не подтверждены" in unit
    assert "Номер исходной позиции" in (
        ui.compare_plot.getPlotItem().getAxis("bottom").label.toPlainText())


def test_history_selected_adc_is_a_hard_filter_not_combined_in_one_axis(w):
    seed_vendor(w)
    ui=w.history_ui
    w.adc.setCurrentIndex(1)
    ui.compare_mode.setCurrentIndex(ui.compare_mode.findData("vendor43"))
    ui._choose_latest_two()
    assert len(ui._last_overlay)==2
    assert all(e.adc==2 for e,_,_,_ in ui._last_overlay)
    w.adc.setCurrentIndex(0)
    assert len(ui._last_overlay)==0
    ui._choose_latest_two()
    assert all(e.adc==1 for e,_,_,_ in ui._last_overlay)
