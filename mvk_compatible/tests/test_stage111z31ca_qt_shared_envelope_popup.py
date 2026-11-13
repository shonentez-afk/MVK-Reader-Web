"""CA: REAL source PageAdc/PageSpectrum shared 32-item Qt popup.

All measurements and coefficient banks are synthetic. Exact Win32 canvas,
proprietary FIR banks, user measurements and physical device are NOT tested.
"""
from __future__ import annotations

from hashlib import sha256
import numpy as np
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt,QPoint,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QToolButton,QMessageBox

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_envelope_idr_candidate import fake_profile
from .test_stage111z16_direct_bin_tsxml import _make_pair


def _full_fft_sha(win):
    spectrum=win._full_spectrum
    assert spectrum is not None
    assert len(spectrum['amplitude'])==spectrum['n_fft']//2
    return sha256(np.asarray(
        spectrum['amplitude'],dtype='<f4').tobytes()).hexdigest()


def _click_source_popup_without_selection(qt_app,button,menu):
    assert not menu.isVisible()
    shown=[]
    menu.aboutToShow.connect(lambda:shown.append(True))
    # Some Windows Qt platforms process delayed timers only after a
    # nested popup event loop. Always explicitly close after the click.
    QTimer.singleShot(300,menu.hide)
    QTest.mouseClick(button,Qt.LeftButton,
                     pos=QPoint(9,button.height()//2))
    qt_app.processEvents()
    menu.hide()
    qt_app.processEvents()
    assert shown, 'Original split button never displayed its QMenu'
    assert not menu.isVisible()


def test_both_original_envelope_buttons_share_one_popup_and_no_click_cycle(
        qt_app,tmp_path,monkeypatch):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        # PageAdc and PageSpectrum are disabled before any measurement.
        # Test a real operator click only after an actual verified source
        # enabled the original root pages (not a hidden/disabled control).
        win.open_archive(fixture_zip(tmp_path,sample_count=8192))
        qt_app.processEvents()
        menu=win.original_envelope_menu
        assert win.wave_filter_button.menu() is menu
        assert win.spec_envelope_button.menu() is menu
        assert win.wave_filter_button.objectName()=='bAdcEnvelopeType'
        assert win.spec_envelope_button.objectName()=='bSpecEnvelopeType'
        assert win.wave_filter_button.popupMode()==QToolButton.InstantPopup
        assert win.spec_envelope_button.popupMode()==QToolButton.InstantPopup
        assert menu.objectName()=='popEnvelopeType'
        actions=menu.actions()
        assert len(actions)==32
        assert [a.data() for a in actions]==list(range(32))
        assert actions[0].isChecked()
        assert not actions[20].isEnabled() # no local FIR coefficients
        assert not win.spec_envelope_button.isEnabled()
        win.original_root_tabs.setCurrentIndex(3)
        qt_app.processEvents()
        _click_source_popup_without_selection(qt_app,win.wave_filter_button,menu)
        assert win.wave_envelope_code.currentData()==0
        assert win.spec_envelope_code.currentData()==0
        assert actions[0].isChecked()

        win.set_envelope_profile(fake_profile(i=1.,q=.4))
        assert win.spec_envelope_button.isEnabled()
        assert win.wave_envelope_code.currentData()==0
        assert win.spec_envelope_code.currentData()==0
        assert actions[20].isEnabled() # source Fs currently unknown
        assert actions[0].isChecked()
        win.original_root_tabs.setCurrentIndex(4)
        qt_app.processEvents()
        _click_source_popup_without_selection(qt_app,win.spec_envelope_button,menu)
        assert win.wave_envelope_code.currentData()==0
        assert win.spec_envelope_code.currentData()==0
        assert not win.spec_envelope_button.isChecked()
        assert actions[0].isChecked()
    finally:
        win.close()
        qt_app.processEvents()


def test_original_popup_code20_code1_tag0_updates_both_visible_pages_core(
        qt_app,tmp_path,monkeypatch):
    from ..desktop.main_window import MainWindow
    src=fixture_zip(tmp_path,sample_count=120000)
    zip_digest=sha256(src.read_bytes()).hexdigest()
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.open_archive(src)
        win.wave_start.setValue(.75)
        win.wave_hscale_menu.actions()[9].trigger() # 20 ms
        win.spec_n.setCurrentText('8192')
        win.set_envelope_profile(fake_profile(i=1.,q=.4))
        assert win.spec_envelope_code.currentData()==0
        assert win.wave_envelope_code.currentData()==0
        menu=win.original_envelope_menu
        assert all(menu.actions()[i].isEnabled() for i in (0,1,20,31))
        win.original_root_tabs.setCurrentIndex(3)
        qt_app.processEvents()
        # Explicit source Tag20 selection computes actual FIR for BOTH
        # current source screens without any legacy checkbox click.
        menu.actions()[20].trigger()
        qt_app.processEvents()
        assert win.spec_envelope_button.isChecked()
        assert win.wave_envelope_code.currentData()==20
        assert win.spec_envelope_code.currentData()==20
        assert win.wave_filter_button.text()=='Огибающая 20'
        assert win.spec_envelope_button.text()=='Огибающая 20'
        assert menu.actions()[20].isChecked()
        assert sum(a.isChecked() for a in menu.actions())==1
        assert win._source_wave_xaxes_model['kind']=='SOURCE_FIR'
        assert win._source_envelope_cursor.code==20
        assert win._full_spectrum['source']==(
            'APP_DERIVED_ENVELOPE_SPECTRUM_IDR_CANDIDATE')
        assert win._source_original_envelope_receipt['adc_tag']==20
        assert win._source_original_envelope_receipt['spectrum_tag']==20
        assert win._source_adc_spectrum_joint_receipt is not None
        source_record=win._current_offline_flow().source_record()
        assert win._source_adc_spectrum_joint_receipt['source_bin_sha256']==(
            source_record['source_bin_sha256'])
        code20_fft=_full_fft_sha(win)
        win.original_root_tabs.setCurrentIndex(4)
        qt_app.processEvents()
        # The same menu object opens from Spectrum; active FIR and display
        # must be updated on PageAdc even though that page is hidden.
        menu.actions()[1].trigger()
        qt_app.processEvents()
        assert win.wave_envelope_code.currentData()==1
        assert win.spec_envelope_code.currentData()==1
        assert win.spec_envelope_button.isChecked()
        assert win._source_envelope_cursor.code==1
        assert win._source_wave_xaxes_model['envelope_code']==1
        assert menu.actions()[1].isChecked()
        assert sum(a.isChecked() for a in menu.actions())==1
        assert win._full_spectrum['source']==(
            'APP_DERIVED_ENVELOPE_SPECTRUM_IDR_CANDIDATE')
        assert _full_fft_sha(win)!=code20_fft
        # Selecting original Tag0 removes FIR from BOTH independent Core
        # pipelines and leaves no stale FIR-shaped Y curve or cursor.
        menu.actions()[0].trigger()
        qt_app.processEvents()
        assert win.wave_envelope_code.currentData()==0
        assert win.spec_envelope_code.currentData()==0
        assert not win.spec_envelope_button.isChecked()
        assert win._source_envelope_cursor is None
        assert win._source_wave_xaxes_model.get('kind')!='SOURCE_FIR'
        assert win._full_spectrum['source']==(
            'APP_DERIVED_FFT_MVKVIEW_CANDIDATE')
        assert len(win.spec_plot.listDataItems())==1
        assert menu.actions()[0].isChecked()
        assert sum(a.isChecked() for a in menu.actions())==1
        assert sha256(src.read_bytes()).hexdigest()==zip_digest
        # Existing original 7-page/3-form E2E remains in the same CI suite.
        for page in range(7):
            win.original_root_tabs.setCurrentIndex(page)
            qt_app.processEvents()
            assert win.session is not None
            assert win._current_offline_flow().channel==1
    finally:
        win.close()
        qt_app.processEvents()


def test_source_sample_rate_disables_impossible_envelope_codes_and_rejects_call(
        qt_app,tmp_path,monkeypatch):
    from ..desktop.main_window import MainWindow
    bin_file,_,_=_make_pair(tmp_path,n=8192,fs=8192,adc=4)
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.open_archive(bin_file)
        win.set_envelope_profile(fake_profile(i=1.,q=.4))
        actions=win.original_envelope_menu.actions()
        assert win._source_envelope_menu_fs==8192
        assert actions[11].isEnabled() # source target Fs8192
        assert not actions[20].isEnabled() # source target Fs65536
        assert actions[0].isChecked()
        before=_full_fft_sha(win)
        # Even a direct programmatic call bypassing disabled Qt QAction
        # MUST be rejected by independent autonomous Core contract.
        win._select_original_envelope_popup_tag(20)
        qt_app.processEvents()
        assert 'Fs' in win.statusBar().currentMessage()
        assert win.wave_envelope_code.currentData()==0
        assert win.spec_envelope_code.currentData()==0
        assert not win.spec_envelope_button.isChecked()
        assert win._source_original_envelope_receipt is None
        assert _full_fft_sha(win)==before
    finally:
        win.close()
        qt_app.processEvents()


def test_open_new_lower_rate_source_resets_active_source_fir_on_both_pages(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    first=fixture_zip(tmp_path,sample_count=120000)
    low_bin,_,_=_make_pair(tmp_path,n=8192,fs=8192,adc=4)
    low_sha=sha256(low_bin.read_bytes()).hexdigest()
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.open_archive(first)
        win.wave_start.setValue(.75)
        win.wave_hscale_menu.actions()[9].trigger()
        win.set_envelope_profile(fake_profile(i=1.,q=.4))
        win.spec_n.setCurrentText('8192')
        win.original_envelope_menu.actions()[20].trigger()
        qt_app.processEvents()
        assert win._source_envelope_menu_fs==65536
        assert win.spec_envelope_button.isChecked()
        assert win._source_wave_xaxes_model['kind']=='SOURCE_FIR'
        assert win.wave_envelope_code.currentData()==20
        # A different real selected BIN/ADC has Fs8192. Original
        # _Unit128:0084BB2E automatically selects Tag0 BEFORE either page
        # is recalculated; no stale selected FIR or old source FFT can leak.
        win.open_archive(low_bin)
        qt_app.processEvents()
        assert win._source_envelope_menu_fs==8192
        assert win._current_offline_flow().channel==4
        assert win.wave_envelope_code.currentData()==0
        assert win.spec_envelope_code.currentData()==0
        assert win.original_envelope_menu.actions()[0].isChecked()
        assert not win.original_envelope_menu.actions()[20].isEnabled()
        assert not win.spec_envelope_button.isChecked()
        assert win._source_original_envelope_receipt is None
        # Direct BIN uses its own correct provenance string, never the
        # Native ZIP FFT backend label.
        assert win._full_spectrum['source']==(
            'APP_DERIVED_DIRECT_BIN_FFT_CANDIDATE')
        assert win._source_envelope_cursor is None
        assert sha256(low_bin.read_bytes()).hexdigest()==low_sha
    finally:
        win.close()
        qt_app.processEvents()


def test_all_nine_original_graph_buttons_show_popup_and_h_main_click_is_inert(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    src=fixture_zip(tmp_path,sample_count=120000)
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.open_archive(src)
        win.set_envelope_profile(fake_profile(i=1.,q=.4))
        nine=(
            win.wave_filter_button,win.wave_type_button,
            win.wave_hscale_button,win.wave_vscale_button,
            win.spec_envelope_button,win.spec_type_button,
            win.spec_lines_button,win.spec_hscale_button,
            win.spec_vscale_button,
        )
        assert len(nine)==9
        assert all(isinstance(btn,QToolButton) for btn in nine)
        assert all(btn.popupMode()==QToolButton.InstantPopup for btn in nine)
        assert all(btn.menu() is not None for btn in nine)
        assert win.spec_envelope_button.menu() is win.wave_filter_button.menu()
        win.original_root_tabs.setCurrentIndex(4)
        win.spec_hscale_menu.actions()[0].trigger()
        qt_app.processEvents()
        assert win._spec_original_hscale_selected==25600
        sha_before=_full_fft_sha(win)
        _click_source_popup_without_selection(
            qt_app,win.spec_hscale_button,win.spec_hscale_menu)
        assert win._spec_original_hscale_selected==25600
        assert _full_fft_sha(win)==sha_before
        win.spec_hscale_menu.actions()[3].trigger()
        qt_app.processEvents()
        assert win._spec_original_hscale_selected==3200
        assert _full_fft_sha(win)==sha_before
    finally:
        win.close()
        qt_app.processEvents()
