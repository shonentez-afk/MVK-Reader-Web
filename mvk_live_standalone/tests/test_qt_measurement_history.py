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
        ("2026-11-18T12:00:00Z",300.,2048),
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
    assert ui.compare_plot.viewRange()[0][1]==pytest.approx(1024,rel=.001)
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



def test_each_history_tab_can_select_adc_without_going_back_to_spectrum(w):
    seed_vendor(w)
    ui=w.history_ui
    w.views.setCurrentWidget(ui.trend_page)
    assert ui.trend_adc.currentData()==1
    ui.trend_adc.setCurrentIndex(1)  # ADC2 selected on Trends page
    assert w.adc.currentData()==2
    assert ui.compare_adc.currentData()==2
    assert len(ui._trend_last)==3
    w.views.setCurrentWidget(ui.compare_page)
    ui.compare_adc.setCurrentIndex(0)
    assert w.adc.currentData()==1
    assert ui.trend_adc.currentData()==1
    ui.compare_mode.setCurrentIndex(ui.compare_mode.findData("vendor43"))
    ui._choose_latest_two()
    assert len(ui._last_overlay)==2
    assert all(e.adc==1 for e,_,_,_ in ui._last_overlay)



def test_compare_date_filter_selects_old_archive_and_exact_point(w):
    from PySide6 import QtCore
    ui=w.history_ui
    for utc,tick in (
        ("2024-03-15T12:00:00Z",1),
        ("2026-11-18T12:00:00Z",2),
    ):
        w._archive.record_vendor_row(
            "TEST_ARCHIVED_DATES",vendor_row(1,tick,utc))
    ui.compare_mode.setCurrentIndex(ui.compare_mode.findData("vendor43"))
    ui._reload_compare()
    assert ui.compare_table.rowCount()==2
    ui.compare_date_from.setDate(QtCore.QDate(2024,3,1))
    ui.compare_date_to.setDate(QtCore.QDate(2024,3,31))
    ui.compare_date_filter.setChecked(True)
    assert ui.compare_table.rowCount()==1
    assert "2024" in ui.compare_table.item(0,1).text()
    ui._choose_latest_two()
    assert not ui._last_overlay or len(ui._last_overlay)<=1
    ui.compare_date_filter.setChecked(False)
    assert ui.compare_table.rowCount()==2
    # An exact original date may be selected from a trend even if the
    # compare table currently shows only the last (newer) 500 entries.
    ui._available_entries={
        e.key:e for e in w._archive.entries(1,"vendor",limit=1)}
    ui._populate_compare_table()
    ui.trend_group.setCurrentIndex(ui.trend_group.findData("third_octave"))
    ui._selected_trend_point=datetime.fromisoformat(
        "2024-03-15T12:00:00+00:00")
    ui._open_trend_in_comparison()
    assert len(ui._last_overlay)==1
    assert ui._last_overlay[0][0].time_utc.startswith("2024-03-15")

def test_compare_pins_distant_utc_dates_beyond_page_limit_and_keeps_same_source_modes(w):
    from datetime import timedelta
    from PySide6 import QtCore
    ui=w.history_ui
    w.adc.setCurrentIndex(7)  # ADC8 only, isolated from other test measurements
    w._archive.record_vendor_row(
        "TEST_MULTI_YEAR_COMPARE",vendor_row(8,1,"2024-03-15T12:00:00Z"))
    for tick in range(2,505):
        utc=(datetime(2026,11,18,12,tzinfo=timezone.utc)
             +timedelta(seconds=tick)).isoformat()
        w._archive.record_vendor_row(
            "TEST_MULTI_YEAR_COMPARE",vendor_row(8,tick,utc))
    ui.compare_mode.setCurrentIndex(ui.compare_mode.findData("vendor43"))
    ui.compare_date_from.setDate(QtCore.QDate(2024,3,1))
    ui.compare_date_to.setDate(QtCore.QDate(2024,3,31))
    ui.compare_date_filter.setChecked(True)
    assert len(ui._filtered_entries)==1
    old=ui._filtered_entries[0]
    ui.compare_table.item(0,0).setCheckState(QtCore.Qt.CheckState.Checked)
    assert ui._table_selected=={old.key}

    # Browsing another year must NOT lose the 2024 checkbox, even though the
    # database returns only 500 newer frames and the old frame is not in page.
    ui.compare_date_from.setDate(QtCore.QDate(2026,11,1))
    ui.compare_date_to.setDate(QtCore.QDate(2026,11,30))
    assert len(ui._filtered_entries)==500
    assert ui.compare_table.rowCount()==501
    assert old.key in ui._available_entries and old.key in ui._table_selected
    latest=ui._filtered_entries[0]
    row=next(i for i in range(ui.compare_table.rowCount())
             if ui.compare_table.item(i,0).data(
                 QtCore.Qt.ItemDataRole.UserRole)==latest.key)
    ui.compare_table.item(row,0).setCheckState(QtCore.Qt.CheckState.Checked)
    ui._draw_comparison()
    assert {e.key for e,_,_,_ in ui._last_overlay}=={old.key,latest.key}
    assert "закреплённых" in ui.compare_info.text()

    # Original 43 and 24-position vendor views are compatible sources.
    ui.compare_mode.setCurrentIndex(ui.compare_mode.findData("vendor24_peak"))
    assert {e.key for e,_,_,_ in ui._last_overlay}=={old.key,latest.key}
    assert all(len(x)==24 for _,x,_,_ in ui._last_overlay)
    ui.compare_date_filter.setChecked(False)
    assert {e.key for e,_,_,_ in ui._last_overlay}=={old.key,latest.key}

    # A different ADC or local-vs-device provenance must invalidate selection.
    w.adc.setCurrentIndex(6)
    assert not ui._table_selected and not ui._pinned_entries
    assert not ui._last_overlay
