"""Full Qt navigation regression: four workspaces and isolated time scope.

Headless self-contained verified Float32 samples; NO industrial TCP.
"""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")


@pytest.fixture
def gui():
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    from PySide6.QtWidgets import QApplication
    from mvk_live_standalone.app import LiveWindow
    app=QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    w=LiveWindow()
    yield w,app
    w.close()
    w.deleteLater()
    app.processEvents()


def _feed(w,fs=8192):
    from mvk_live_standalone.live_ipc import IPCPreview,IPCChannel,DOMAIN
    n=32768
    t=np.arange(n,dtype=np.float64)/fs
    x=(np.sqrt(2)*(np.sin(2*np.pi*100*t)+np.sin(2*np.pi*1000*t))).astype("<f4")
    channel=IPCChannel(1,fs,x,n%(1<<32),n,hashlib.sha256(x.tobytes()).hexdigest())
    preview=IPCPreview(
        "TEST_TWO_TONES",DOMAIN,True,datetime.now(timezone.utc),{1:channel})
    w._gui_ring.ingest_preview(preview)
    w._preview=preview
    return x


def test_main_tabs_are_four_tasks_not_mixed_wide_graph_layout(gui):
    w,_=gui
    assert [w.views.tabText(i) for i in range(w.views.count())]==[
        "Спектр","Временной сигнал","Расчётные данные",
        "Тренды","Сравнение","Доп. анализ"]
    assert w.views.widget(0)==w.spectrum_page
    assert w.views.widget(1)==w.wave_page
    assert w.views.widget(2)==w.calculated_page
    assert w.views.widget(3)==w.history_ui.trend_page
    assert w.views.widget(4)==w.history_ui.compare_page
    assert w.views.widget(5)==w.extra_panel
    assert w.wave.parent() is not w.centralWidget()
    assert w.spec.parent() is not w.centralWidget()
    assert w.views.currentWidget()==w.spectrum_page
    assert [w.dsp_pages.tabText(i) for i in range(w.dsp_pages.count())]==[
        "Октавные полосы 1/3 · 1/1",
        "24 позиции · СКЗ / Пик / Размах",
        "Показатели MVK Live",
    ]
    assert [w.extra_pages.tabText(i) for i in range(w.extra_pages.count())]==[
        "Водопад","Кюртограмма","Тренд СКЗ","STFT","CWT Morlet","Кепстр",
        "Подшипники","Редукторы",
    ]
    assert w.dsp_pages.widget(0)!=w.dsp_pages.widget(2)
    assert "APP_DERIVED" in w.derived_layout.itemAt(0).widget().text()
    assert "DSP" in w.dsp_info.text() and "ожидание" in w.dsp_info.text()


def test_time_page_has_own_x_y_and_filter_not_affected_by_spectrum(gui):
    w,_=gui
    assert w.timebase.itemText(0)=="10 мс"
    assert w.timebase.itemText(w.timebase.count()-1)=="30 с"
    assert w.timebase.currentData()==1.0
    assert w.time_y_width.currentData() is None
    assert w.time_y_width.itemText(1).startswith("±")
    assert w.time_filter_choice.currentData()=="none"
    assert not w.time_filter_button.isEnabled()
    assert w.filter_choice.currentData()=="none"
    assert w.analysis.currentData()=="fft"
    w.views.setCurrentWidget(w.wave_page)
    assert w.views.currentWidget()==w.wave_page
    # Distinct filter controls and distinct scopes preserve independent state.
    w.time_filter_choice.setCurrentIndex(w.time_filter_choice.findData("lowpass"))
    assert w.time_filter_button.isEnabled()
    assert w.filter_choice.currentData()=="none"
    assert w._read_settings()[3]==(0.,None)
    w.time_filter_choice.setCurrentIndex(w.time_filter_choice.findData("none"))
    assert not w.time_filter_button.isEnabled()


def test_time_axes_real_milliseconds_signed_y_and_frange_not_doubled(gui):
    w,_=gui
    _feed(w)
    w.views.setCurrentWidget(w.wave_page)
    w.timebase.setCurrentIndex(w.timebase.findData(.02))
    w.time_y_width.setCurrentIndex(w.time_y_width.findData(5.0))
    w._render_wave()
    x,y=w.wave_curve.getData()
    assert len(x)>0 and len(x)==len(y)
    assert x[0]>=-.021 and x[-1]<0
    lo,hi=w.wave.viewRange()[1]
    assert lo==pytest.approx(-5,abs=1e-6)
    assert hi==pytest.approx(5,abs=1e-6)
    assert "м/с²" in w.wave.getPlotItem().getAxis("left").label.toPlainText()
    assert "Fs=8192" in w.wave_info.text()
    assert "один раз" in w.wave_info.text()
    assert "APP_DERIVED" in w.wave_stats.text()
    assert "Пик-пик" in w.wave_stats.text()
    # Change only the local X window, not the FFT sample rate.
    w.timebase.setCurrentIndex(w.timebase.findData(.1))
    assert w.wave.viewRange()[0][0]==pytest.approx(-.1,abs=.001)
    assert w.nfft.currentData()==32768


def test_time_local_filter_is_real_and_does_not_change_spectrum(gui):
    w,_=gui
    _feed(w)
    w.timebase.setCurrentIndex(w.timebase.findData(1.))
    w._render_wave()
    _,before=w.wave_curve.getData()
    before_std=float(np.std(before))
    w.time_filter_choice.setCurrentIndex(w.time_filter_choice.findData("lowpass"))
    w.time_filter_high=200.
    w._render_wave()
    _,after=w.wave_curve.getData()
    assert len(after)==len(before)
    assert np.std(after)<before_std*.85
    assert w.filter_choice.currentData()=="none"
    assert w._read_settings()[3]==(0.,None)
    assert "ФНЧ до 200" in w.wave_info.text()
    assert w.dsp24_curve.getData()[0] is None or len(w.dsp24_curve.getData()[0])==0

def test_time_octave_selection_is_independent_of_spectrum(gui):
    w,_=gui
    _feed(w)
    w.time_filter_choice.setCurrentIndex(w.time_filter_choice.findData("third_octave"))
    assert w.time_filter_center.count()==43
    assert not w.time_filter_button.isEnabled()
    w.time_filter_center.setCurrentIndex(w.time_filter_center.findData(1000.))
    w.timebase.setCurrentIndex(w.timebase.findData(1.))
    w._render_wave()
    assert "1/3 октавы" in w.wave_info.text()
    assert w.filter_choice.currentData()=="none"

def test_extra_pages_independent_waterfall_trend_bearing_and_gears(gui):
    w,_=gui
    assert w.extra_pages.indexOf(w.waterfall_page)>=0
    assert w.extra_pages.indexOf(w.short_trend_page)>=0
    assert w.extra_pages.indexOf(w.diagnostics_page)>=0
    assert w.extra_pages.indexOf(w.gears_page)>=0
    assert w.waterfall_max_frames.currentData()==120
    assert w.trend_max_points.currentData()==240
    w.waterfall_max_frames.setCurrentIndex(
        w.waterfall_max_frames.findData(20))
    assert w.waterfall_max_frames.currentData()==20
    w.trend_max_points.setCurrentIndex(
        w.trend_max_points.findData(30))
    assert w.trend_max_points.currentData()==30
    w.bearing_rpm.setValue(1500)
    assert w.rpm.value()==1500
    assert w.gear_rpm.value()==1500
    w.gear_count.setValue(20)
    assert w.gear_teeth.value()==20
    assert w.gear_table.rowCount()>0
    assert "GMF" in w.gear_table.item(0,0).text()
    w.bearing_balls.setValue(8)
    assert w.balls.value()==8
    w.gear_count.setValue(0)
    assert w.gear_table.rowCount()==0

def test_advanced_adc_selector_clears_only_stale_short_live_views(gui):
    w,_=gui
    assert w.extra_adc.currentData()==1
    w.extra_adc.setCurrentIndex(4)
    assert w.adc.currentData()==5
    assert w.dsp_adc.currentData()==5
    assert "АЦП 5" in w.short_trend_info.text()
    assert all("АЦП 5" in text.text()
               for text in w.extra_method_infos.values())
    assert w._waterfall_rows==[]
    assert w._trend_points==[]
    w.dsp_adc.setCurrentIndex(2)
    assert w.extra_adc.currentData()==3

def test_time_original_mvkview_32_labels_have_independent_selection(gui):
    w,_=gui
    _feed(w)
    w.time_filter_choice.setCurrentIndex(
        w.time_filter_choice.findData("original_preset"))
    assert w.time_filter_center.count()==32
    assert w.time_filter_center.currentData()==("none",None)
    w._render_wave()
    assert "Без фильтра" in w.wave_info.text()
    index=next((i for i in range(w.time_filter_center.count())
             if w.time_filter_center.itemData(i)==("third_octave",1000.)),-1)
    assert index>=0
    w.time_filter_center.setCurrentIndex(index)
    w.timebase.setCurrentIndex(w.timebase.findData(1.))
    w._render_wave()
    assert "1/3окт 1000 Гц" in w.wave_info.text()
    assert "локальный фильтр" in w.wave_info.text()
    assert w.filter_choice.currentData()=="none"
    assert not w.time_filter_button.isEnabled()



def test_full_pysdkit_kurtogram_tab_and_band_handoff(gui):
    w,_=gui
    from mvk_live_standalone.kurtogram import compute_fast_kurtogram
    _feed(w)
    assert w.extra_pages.indexOf(w.kurtogram_page)>0
    assert w.kurtogram_apply.isEnabled() is False
    assert w.kurtogram_levels.currentData()==4
    ch=w._gui_ring.channel(1)
    x=ch.latest(8192)
    view=compute_fast_kurtogram(x,ch.rate_hz,nlevel=4)
    w._kurt_adc=1
    w._kurt_session=w._gui_ring.session_id
    w._kurt_frozen=False
    w._display_kurtogram(view)
    assert w.kurtogram_apply.isEnabled()
    assert "PySDKit Fast Kurtogram" in w.kurtogram_info.text()
    assert w._kurt_selected==(view.best_row,view.best_col)
    assert w.kurtogram_img.image.shape==(48,8)
    w._pick_kurt_cell(0,0)
    assert w._kurt_selected==(0,0)
    w._select_kurt_best()
    lo,hi,_,_,_=view.best_band()
    w._apply_kurt_band()
    assert w.views.currentWidget()==w.extra_panel
    assert w.extra_pages.currentWidget()==w.diagnostics_page
    assert w.analysis.currentData()=="envelope"
    assert w.envelope_band.currentData()==pytest.approx((lo,hi))
    assert w.bearing_resonance.currentData()==pytest.approx((lo,hi))
    w.adc.setCurrentIndex(1)
    assert w._kurt_result is None
    assert not w.kurtogram_apply.isEnabled()
