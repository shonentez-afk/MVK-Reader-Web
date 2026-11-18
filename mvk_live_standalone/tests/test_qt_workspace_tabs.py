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
    w._gui_ring.ingest_preview(IPCPreview(
        "TEST_TWO_TONES",DOMAIN,True,datetime.now(timezone.utc),{1:channel}))
    w._preview=True
    return x


def test_main_tabs_are_four_tasks_not_mixed_wide_graph_layout(gui):
    w,_=gui
    assert [w.views.tabText(i) for i in range(w.views.count())]==[
        "Спектр","Временной сигнал","Расчётные данные","Доп. анализ"]
    assert w.views.widget(0)==w.spectrum_page
    assert w.views.widget(1)==w.wave_page
    assert w.views.widget(2)==w.calculated_page
    assert w.views.widget(3)==w.extra_panel
    assert w.wave.parent() is not w.centralWidget()
    assert w.spec.parent() is not w.centralWidget()
    assert w.views.currentWidget()==w.spectrum_page
    assert [w.dsp_pages.tabText(i) for i in range(w.dsp_pages.count())]==[
        "43 частоты · СКЗ ВУ",
        "24 позиции · СКЗ / Пик / Размах",
        "Расчёты MVK Live",
    ]
    assert [w.extra_pages.tabText(i) for i in range(w.extra_pages.count())]==[
        "Водопад","Тренд СКЗ","STFT / CWT / Кепстр",
        "Подшипники / редукторы",
    ]
    assert w.dsp_pages.widget(0)!=w.dsp_pages.widget(2)
    assert "APP_DERIVED" in w.derived_layout.itemAt(0).widget().text()
    assert "AUX4700" in w.dsp_info.text() or "Данные" in w.dsp_info.text()


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
