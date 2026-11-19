"""Qt regression: device AUX4700 43+24x3, not local FFT or invented Hz."""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")


@pytest.fixture
def window():
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    from PySide6.QtWidgets import QApplication
    from mvk_live_standalone.app import LiveWindow
    app=QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    w=LiveWindow()
    yield w
    w.close()
    w.deleteLater()
    app.processEvents()


def _payload():
    from mvk_live_standalone.original_dsp import _THIRD_HZ
    rec={
        "adc":3,
        "time_utc":"2026-11-18T01:11:12Z",
        "update":6,
        "status_hex":"0x00000000",
        "nonfinite_fields":1,
        "not_ready":{"fs16":False,"fs64":False,"fs512":False},
        "third_octave_hz":_THIRD_HZ.tolist(),
        "third_octave_acceleration_rms":[.01*i for i in range(43)],
        "band_rms":[i*.1 for i in range(24)],
        "band_peak_equiv":[i*.2 for i in range(24)],
        "band_span_equiv":[i*.4 for i in range(24)],
    }
    rec["band_span_equiv"][7]=None
    return {"phase":"RECORDING","aux4700_updates":6,
            "dsp_original_aux4700_channels":[rec]}


def test_qt_shows_all_original_rms_peak_span_per_adc(window):
    w=window
    w._last_status=_payload()
    w.adc.setCurrentIndex(2)  # ADC 3
    w._render_dsp()
    assert w._dsp_last is not None and w._dsp_last.has_extended
    assert w._dsp_last.total_transmitted_cells==115
    assert w.dsp_curve.getData()[0].size==43
    assert w.dsp24_table.rowCount()==24
    assert w.dsp24_table.columnCount()==4
    assert w.dsp24_table.item(5,1).text()=="0.5"
    assert w.dsp24_table.item(5,2).text()=="1"
    assert w.dsp24_table.item(5,3).text()=="2"
    assert w.dsp24_table.item(7,3).text()=="—"  # NaN not zero
    assert "передано: 115" in w.dsp_info.text()
    assert "не подтверждённой" in w.dsp_info.text()
    w.dsp24_mode.setCurrentIndex(1)
    freqs,val=w.dsp24_curve.getData()
    assert freqs.size==24 and freqs[-1]==24
    assert val[5]==pytest.approx(1)
    # X is ordinal, not Hz. We must not pretend original 24 slots have
    # the same physical frequency map as the 43 third-octave centres.
    assert "позиции" in w.dsp24_plot.getPlotItem().getAxis("bottom").label.toPlainText()


def test_qt_original_missing_or_unavailable_never_falls_back_to_fft(window):
    w=window
    w._last_status=_payload()
    w.adc.setCurrentIndex(2)
    w._render_dsp()
    assert w.dsp_curve.getData()[0].size==43
    w.adc.setCurrentIndex(0)  # ADC 1 has NO vendor payload
    w._render_dsp()
    assert w._dsp_last is None
    assert not any(w.dsp24_table.item(0,j) is not None for j in range(4))
    assert "ещё не получены" in w.dsp_info.text()
    w.adc.setCurrentIndex(2)  # ADC 3 is the only channel with a real fake AUX packet
    w._last_status["phase"]="COMPLETED"
    w._render_dsp()
    assert "НЕ Live" in w.dsp_info.text()
    assert w.dsp_curve.getData()[0].size==43
    w._last_status["phase"]="CONNECTING"
    w._render_dsp()
    assert "ожидание" in w.dsp_info.text()

def test_original_43_device_bands_and_local_octave_are_strictly_separate(window):
    w=window
    from mvk_live_standalone.modern_shell import open_advanced_window
    from mvk_live_standalone.original_dsp import _THIRD_HZ
    raw=_payload()
    row=raw["dsp_original_aux4700_channels"][0]
    row["third_octave_acceleration_rms"]=[1.]*43
    # Preserve a real missing device result; it is never synthesized.
    row["third_octave_acceleration_rms"][4]=None
    row["nonfinite_fields"]=2   # 24-slot span + one missing third
    w._last_status=raw
    w.adc.setCurrentIndex(2)
    w._render_dsp()
    assert w.dsp_bands_table.rowCount()==43
    assert w.dsp_band_mode.count()==1
    assert w.dsp_band_mode.findData("octave")==-1
    xx,yy=w.dsp_curve.getData()
    np.testing.assert_allclose(xx,_THIRD_HZ)
    assert np.isnan(yy[4]) and np.all(yy[np.arange(43)!=4]==1.)
    assert w.dsp_bands_table.item(4,1).text()=="—"
    assert w.dsp_curve.opts["connect"]=="finite"
    assert not any("APP_DERIVED" in w.dsp_pages.tabText(i)
                   for i in range(w.dsp_pages.count()))
    # Old 1/1 RSS remains available ONLY as a labelled local window.
    child=open_advanced_window(w,"local_octaves")
    assert child.centralWidget() is w.local_octave_page
    assert "APP_DERIVED" in w.local_octave_note.text()
    assert w.local_octave_table.rowCount()>0
    assert w.local_octave_table.item(1,1).text()=="—"
    assert w.dsp_bands_table.rowCount()==43

def test_calculated_original_band_to_exact_metric_trend_navigation(window):
    w=window
    raw=_payload()
    w._last_status=raw
    w.adc.setCurrentIndex(2)
    w._render_dsp()
    from mvk_live_standalone.original_dsp import _THIRD_HZ
    index=list(_THIRD_HZ).index(1000.)
    w.dsp_bands_table.setCurrentCell(index,0)
    w.dsp_band_trend_button.click()
    ui=w.history_ui
    assert w._modern_windows["archive-trends"].centralWidget()==ui.trend_page
    assert ui.trend_group.currentData()=="third_octave"
    assert ui.trend_position.currentData()==index
    assert w.adc.currentData()==3
    w.views.setCurrentWidget(w.calculated_page)
    assert w.dsp_band_trend_button.isEnabled()
    assert w.dsp_band_mode.findData("octave")==-1
    # A locally aggregated octave cannot be selected as an OEM trend.
    from mvk_live_standalone.modern_shell import open_advanced_window
    local=open_advanced_window(w,"local_octaves")
    assert local.centralWidget() is w.local_octave_page
    assert w.history_ui.trend_group.currentData()=="third_octave"


def test_calculated_24_position_and_local_metric_navigate_to_own_provenance(window):
    w=window
    w._last_status=_payload()
    w.adc.setCurrentIndex(2)
    w._render_dsp()
    w.dsp24_mode.setCurrentIndex(w.dsp24_mode.findData("band_peak_equiv"))
    w.dsp24_table.setCurrentCell(5,2)
    w.dsp24_trend_button.click()
    ui=w.history_ui
    assert ui.trend_group.currentData()=="band_peak_equiv"
    assert ui.trend_position.currentData()==5
    w.views.setCurrentWidget(w.calculated_page)
    from mvk_live_standalone.modern_shell import open_advanced_window
    local=open_advanced_window(w,"local_metrics")
    assert local.centralWidget() is w.derived_page
    assert w.dsp_pages.indexOf(w.derived_page)==-1
    w.local_values_table.setCurrentCell(9,0)
    w.local_trend_button.click()
    assert ui.trend_group.currentData()=="velocity_rms_10_1000"
    assert ui.trend_adc.currentData()==3
    assert w._modern_windows["archive-trends"].centralWidget()==ui.trend_page



def test_calculated_page_has_no_local_values_or_computed_octave_and_preserves_24_slots(window):
    """All main Calculated UI numbers originate from validated device AUX."""
    from PySide6.QtWidgets import QLabel
    w=window
    assert w.dsp_pages.count()==2
    assert w.dsp_band_mode.findData("octave")==-1
    assert w.dsp_pages.indexOf(w.derived_page)==-1
    assert w.dsp_pages.indexOf(w.local_octave_page)==-1
    texts=[label.text() for label in w.calculated_page.findChildren(QLabel)]
    assert all("APP_DERIVED" not in text for text in texts)
    assert "ТОЛЬКО ПРИБОР" in w.dsp_source_hint.text()
    raw=_payload()
    raw["dsp_original_aux4700_channels"][0]["third_octave_acceleration_rms"][2]=None
    raw["dsp_original_aux4700_channels"][0]["nonfinite_fields"]=2
    w._last_status=raw
    w.adc.setCurrentIndex(2)
    w._render_dsp()
    x,y=w.dsp_curve.getData()
    assert len(x)==43 and np.isnan(y[2])
    assert w.dsp_curve.opts["connect"]=="finite"
    w.dsp24_mode.setCurrentIndex(
        w.dsp24_mode.findData("band_span_equiv"))
    x,y=w.dsp24_curve.getData()
    assert len(x)==24 and x[7]==8 and np.isnan(y[7])
    assert w.dsp24_curve.opts["connect"]=="finite"
    assert w.dsp24_table.item(7,3).text()=="—"
    assert "приём (ПК)" in w.dsp_info.text()
    # Switching to an ADC without AUX must clear both vendor and the
    # locally derived 1/1 chart, without inventing zero measurements.
    w.adc.setCurrentIndex(w.adc.findData(1))
    w._render_dsp()
    assert w._dsp_last is None
    assert w.local_octave_table.rowCount()==0
    assert w.local_octave_curve.getData()[0] is None or (
        len(w.local_octave_curve.getData()[0])==0)


def test_advanced_local_metrics_windows_keep_both_original_views_untouched(window):
    from mvk_live_standalone.modern_shell import open_advanced_window
    w=window
    before=[w.dsp_pages.tabText(i) for i in range(w.dsp_pages.count())]
    a=open_advanced_window(w,"local_metrics")
    b=open_advanced_window(w,"local_octaves")
    assert a is not b
    assert a.centralWidget() is w.derived_page
    assert b.centralWidget() is w.local_octave_page
    assert a.statusBar().currentMessage().startswith("APP_DERIVED")
    assert open_advanced_window(w,"local_metrics") is a
    assert [w.dsp_pages.tabText(i) for i in range(w.dsp_pages.count())]==before
    assert w._native.state()==w._native.ProcessState.NotRunning



def test_detached_local_metrics_never_leaks_old_adc_into_new_source(window):
    from PySide6.QtWidgets import QTableWidgetItem
    from mvk_live_standalone.modern_shell import open_advanced_window
    w=window
    local=open_advanced_window(w,"local_metrics")
    assert local.centralWidget() is w.derived_page
    w.local_values_table.setItem(0,0,QTableWidgetItem("ВУ СКЗ"))
    w.local_values_table.setItem(0,1,QTableWidgetItem("123"))
    w.features_label.setText("APP_DERIVED · АЦП 1 · 123")
    w.adc.setCurrentIndex(w.adc.findData(2))
    assert w.local_values_table.item(0,1) is None
    assert "АЦП 2" in w.features_label.text()
    assert "123" not in w.features_label.text()
    assert "АЦП 2" in w.metrics.text()
    assert w.dsp_pages.count()==2
    assert "ТОЛЬКО ПРИБОР" in w.dsp_source_hint.text()
