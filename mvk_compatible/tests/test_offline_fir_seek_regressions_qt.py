"""Operator checks for archive FIR/history, cross-channel time and drag workers."""
import threading
import time
import numpy as np
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QTimer
from ..desktop import main_window as mw
from ..core.envelope_idr_candidate import EnvelopeProfile
from .test_desktop_qt import qt_app
from .test_mode1_saved_adc_spectrum_export_qt import _adc
from .test_stage111z31en_saved_tach_qt import _write_bin


def test_fir_shows_actual_output_rate_and_recovers_from_early_history(tmp_path,qt_app):
    adc,_=_adc(tmp_path,1,'м/с2',8,fs=65536,n=327680)
    win=mw.MainWindow()
    try:
        banks=np.zeros((10,512),dtype=np.float32)
        banks[:,0]=1
        win.set_envelope_profile(EnvelopeProfile(banks))
        win.open_archive(adc)
        win.original_root_tabs.setCurrentIndex(4)
        win._original_envelope_actions[20].trigger()
        assert win._full_spectrum['output_sample_rate_hz']==32768
        assert 'FIR выходная Fs 32768 Гц' in win.statusBar().currentMessage()
        slider=win.original_shell.view_slider
        slider.setValue(105)
        text=win.spec_mean_primary.text()
        assert 'Недостаточно отсчётов для FIR' in text
        assert '68,813' in text and '262,195' in text
        assert any(a.isEnabled() and a.text() in text for a in win._spec_lines_actions)
        assert not win.spec_copy_button.isEnabled() and not win.spec_save_button.isEnabled()
        slider.setValue(401)
        assert win._full_spectrum is not None and win.spec_save_button.isEnabled()
        assert 'предыстории' not in win.statusBar().currentMessage()
        assert 'Недостаточно' not in win.spec_mean_primary.text()
    finally:
        win.close()


def test_short_tach_clamp_does_not_replace_untouched_adc_time(tmp_path,qt_app):
    adc,_=_adc(tmp_path,1,'м/с2',8,n=262144)
    _write_bin(tmp_path,'TACH1',9,bytes([127])*1500)
    win=mw.MainWindow()
    try:
        win.open_archive(adc)
        win.original_root_tabs.setCurrentIndex(4)
        slider=win.original_shell.view_slider
        slider.setValue(1234)
        win.spec_channel_tabs.setCurrentIndex(8)
        assert slider.value()==18
        win.spec_channel_tabs.setCurrentIndex(0)
        assert slider.value()==1234
        win.spec_channel_tabs.setCurrentIndex(8)
        slider.setValue(9)
        win.spec_channel_tabs.setCurrentIndex(0)
        assert slider.value()==9
    finally:
        win.close()


def _wait(qt_app,predicate,timeout=5):
    until=time.monotonic()+timeout
    while not predicate() and time.monotonic()<until:
        qt_app.processEvents()
        time.sleep(.006)
    assert predicate()


def test_pointer_drag_coalesces_and_computes_fft_outside_gui(tmp_path,qt_app,monkeypatch):
    adc,_=_adc(tmp_path,1,'м/с2',8,n=65536)
    win=mw.MainWindow()
    entered=threading.Event()
    release=threading.Event()
    started=[]
    gui_thread=threading.get_ident()
    original=mw.direct_drag_spectrum
    def controlled(*args,**kwargs):
        started.append((threading.get_ident(), args[1]))
        entered.set()
        release.wait(6)
        return original(*args,**kwargs)
    monkeypatch.setattr(mw,'direct_drag_spectrum',controlled)
    try:
        win.open_archive(adc)
        win.spec_n.setCurrentText('8192')
        win.original_root_tabs.setCurrentIndex(4)
        slider=win.original_shell.view_slider
        slider.setValue(333)
        expected=np.asarray(win._full_spectrum['amplitude'],dtype='<f4')
        slider.setValue(500)
        slider.setSliderDown(True)
        for pos in (102,180,227,333):
            slider.setValue(pos)
        assert not started
        assert not win.spec_save_button.isEnabled()
        with pytest.raises(ValueError):
            win._current_original_spectrum_action()
        slider.setSliderDown(False)
        _wait(qt_app,entered.is_set)
        tick=[]
        QTimer.singleShot(0,lambda:tick.append(True))
        _wait(qt_app,lambda:bool(tick))
        assert started[0][0]!=gui_thread and started[0][1]==333
        assert len(started)==1
        release.set()
        _wait(qt_app,lambda:win._drag_request is None)
        got=np.asarray(win._full_spectrum['amplitude'],dtype='<f4')
        assert got.tobytes()==expected.tobytes()
        assert win.original_shell.view_slider.value()==333
    finally:
        release.set()
        win.close()


def test_drag_result_from_closed_session_is_not_applied(tmp_path,qt_app,monkeypatch):
    adc,_=_adc(tmp_path,1,'м/с2',8,n=65536)
    win=mw.MainWindow()
    entered,release,done=(threading.Event() for _ in range(3))
    original=mw.direct_drag_spectrum
    def controlled(*a,**kw):
        entered.set()
        try:
            release.wait(6)
            return original(*a,**kw)
        finally:
            done.set()
    monkeypatch.setattr(mw,'direct_drag_spectrum',controlled)
    try:
        win.open_archive(adc)
        win.original_root_tabs.setCurrentIndex(4)
        slider=win.original_shell.view_slider
        slider.setSliderDown(True)
        slider.setValue(728)
        slider.setSliderDown(False)
        _wait(qt_app,entered.is_set)
        win._close_session()
        release.set()
        _wait(qt_app,done.is_set)
        assert win._full_spectrum is None and win._drag_request is None
        assert not win.spec_save_button.isEnabled()
    finally:
        release.set()
        win.close()


def test_real_qt_mouse_seek_with_tracking_disabled(tmp_path,qt_app,monkeypatch):
    from PySide6.QtCore import Qt,QPoint
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QStyleOptionSlider,QStyle
    adc,_=_adc(tmp_path,1,'м/с2',8,n=65536)
    win=mw.MainWindow()
    started=[]
    original=mw.direct_drag_spectrum
    def observed(*a,**kw):
        started.append(threading.get_ident())
        return original(*a,**kw)
    monkeypatch.setattr(mw,'direct_drag_spectrum',observed)
    try:
        win.resize(1300,850)
        win.show()
        win.open_archive(adc)
        win.spec_n.setCurrentText('8192')
        win.original_root_tabs.setCurrentIndex(4)
        qt_app.processEvents()
        slider=win.original_shell.view_slider
        assert not slider.hasTracking()
        style=QStyleOptionSlider()
        slider.initStyleOption(style)
        handle=slider.style().subControlRect(QStyle.ComplexControl.CC_Slider,style,QStyle.SubControl.SC_SliderHandle,slider)
        old=slider.value()
        QTest.mousePress(slider,Qt.LeftButton,pos=handle.center())
        point=QPoint(slider.width()//2,handle.center().y())
        QTest.mouseMove(slider,point,delay=20)
        assert slider.value()==old and slider.sliderPosition()<old
        assert win._drag_request is not None and not started
        assert 'Выбор окна' in win.spec_mean_primary.text()
        assert not win.spec_copy_button.isEnabled()
        QTest.mouseRelease(slider,Qt.LeftButton,pos=point)
        _wait(qt_app,lambda:bool(started) and win._drag_request is None)
        assert len(started)==1 and started[0]!=threading.get_ident()
        assert slider.value()<old and win.spec_save_button.isEnabled()
    finally:
        win.close()


def test_early_spectrum_explains_plain_and_fir_without_unavailable_options(tmp_path, qt_app):
    path,_=_adc(tmp_path,1,'м/с2',8,fs=65536,n=327680)
    win=mw.MainWindow()
    try:
        banks=np.zeros((10,512),dtype=np.float32)
        banks[:,0]=1
        win.set_envelope_profile(EnvelopeProfile(banks))
        win.open_archive(path)
        win.original_root_tabs.setCurrentIndex(4)
        slider=win.original_shell.view_slider
        slider.setValue(slider.minimum())
        for code,caption in ((0,'спектра'),(20,'FIR')):
            win._original_envelope_actions[code].trigger()
            text=win.spec_mean_primary.text()
            assert f'Недостаточно отсчётов для {caption}' in text
            assert 'Доступно: 0; нужно:' in text
            assert 'Передвиньте ползунок' in text
            assert 'Выберите разрешение' not in text
            assert win._full_spectrum is None
            assert not win.spec_copy_button.isEnabled() and not win.spec_save_button.isEnabled()
        slider.setValue(slider.maximum())
        assert win._full_spectrum is not None
        assert win.spec_save_button.isEnabled()
        assert 'Недостаточно' not in win.spec_mean_primary.text()
        assert 'Недостаточно' not in win.statusBar().currentMessage()
    finally:
        win.close()


@pytest.mark.parametrize("seek_in_progress",[False,True])
def test_measure_cancel_restores_verified_adc_time_and_spectrum_view(
        tmp_path, qt_app, monkeypatch, seek_in_progress):
    a,_=_adc(tmp_path,1,'м/с2',8,fs=65536,n=655360)
    _adc(tmp_path,3,'м/с2',4,fs=65536,n=655360)
    win=mw.MainWindow()
    entered,release,finished=(threading.Event() for _ in range(3))
    old=mw.direct_drag_spectrum
    def held(*args,**kwargs):
        entered.set()
        try:
            release.wait(5)
            return old(*args,**kwargs)
        finally:
            finished.set()
    if seek_in_progress:
        monkeypatch.setattr(mw,'direct_drag_spectrum',held)
    try:
        win.show()
        banks=np.zeros((10,512),dtype=np.float32)
        banks[:,0]=1
        win.set_envelope_profile(EnvelopeProfile(banks))
        win.open_archive(a)
        win.original_root_tabs.setCurrentIndex(4)
        win.spec_channel_tabs.setCurrentIndex(2)
        slider=win.original_shell.view_slider
        slider.setValue(400)
        win.spec_n.setCurrentText('8192')
        win._original_envelope_actions[20].trigger()
        win._select_original_hscale(3200,position_hz=500)
        assert win.spec_save_button.isEnabled()
        target=430 if seek_in_progress else 400
        if seek_in_progress:
            slider.setSliderDown(True)
            slider.setValue(target)
            slider.setSliderDown(False)
            _wait(qt_app,entered.is_set)
        start=win.original_start_controller
        start.ip_edit.setText('192.0.2.10')
        assert start.open_capture_dialog()
        assert win.session is None and win._drag_future is None
        assert not win.spec_copy_button.isEnabled() and not win.spec_save_button.isEnabled()
        win._native_dialog.cancel_inline.click()
        assert win.session.path==a and win._ch()==3
        assert slider.value()==target and win.spec_n.currentText()=='8192'
        assert win.spec_envelope_code.currentData()==20
        assert win._spec_original_hscale_selected==3200 and win.spec_hscroll.value()==500
        assert win.spec_save_button.isEnabled()
        result=win._full_spectrum
        if seek_in_progress:
            release.set()
            _wait(qt_app,finished.is_set)
            qt_app.processEvents()
            assert win._full_spectrum is result
            assert win._ch()==3 and slider.value()==target
    finally:
        release.set()
        win.close()
