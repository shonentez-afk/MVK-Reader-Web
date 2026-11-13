"""CB: working ORIGINAL two-column popEnvelopeType, real click and Core FFT.

Real Qt widget actions at DPI 150, verified synthetic ZIP only, no device,
no private original IDP or original Win32 process. Screenshot provenance
is SYNTHETIC Qt and must never be described as Win32 pixel acceptance.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import numpy as np
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import QPoint,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMenu,QWidgetAction,QRadioButton,QGridLayout,QToolButton

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_envelope_idr_candidate import fake_profile
from ..core.original_envelope_shared_menu import SOURCE_ORIGINAL_FILTER_CAPTIONS


def _popup_from(qt_app,menu,button):
    assert menu is button.menu()
    menu.popup(button.mapToGlobal(QPoint(0,button.height())))
    qt_app.processEvents()
    assert menu.isVisible()
    assert menu.findChild(QRadioButton,'sourceEnvelopeMenuTag00').isVisible()


def _graph_digest(win):
    assert win._full_spectrum is not None
    return sha256(np.asarray(
        win._full_spectrum['amplitude'],dtype='<f4').tobytes()).hexdigest()


def test_exact_31_static_original_captions_20_plus_12_visible_radio_geometry(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        w.open_archive(fixture_zip(tmp_path,sample_count=8192))
        w.original_root_tabs.setCurrentIndex(4)
        qt_app.processEvents()
        menu=w.original_envelope_menu
        assert isinstance(menu,QMenu)
        assert menu is w.wave_filter_button.menu()
        assert menu is w.spec_envelope_button.menu()
        assert w.spec_envelope_button.isEnabled()
        assert w.spec_envelope_button.popupMode()==QToolButton.InstantPopup
        actions=menu.actions()
        assert len(actions)==32
        assert [a.data() for a in actions]==list(range(32))
        assert isinstance(actions[0],QWidgetAction)
        palette=w.original_envelope_palette
        assert palette.objectName()=='sourceEnvelopeTwoColumnPalette'
        assert actions[0].defaultWidget() is palette
        assert isinstance(palette.layout(),QGridLayout)
        radios=w._original_envelope_radios
        assert len(radios)==32
        for tag,radio in enumerate(radios):
            assert isinstance(radio,QRadioButton)
            assert radio.text()==SOURCE_ORIGINAL_FILTER_CAPTIONS[tag]
            assert actions[tag].text()==radio.text()
            assert radio.objectName()==f'sourceEnvelopeMenuTag{tag:02d}'
            row=tag if tag<20 else tag-20
            col=0 if tag<20 else 1
            assert palette.layout().itemAtPosition(row,col).widget() is radio
        assert palette.layout().itemAtPosition(19,0).widget() is radios[19]
        assert palette.layout().itemAtPosition(0,1).widget() is radios[20]
        assert palette.layout().itemAtPosition(11,1).widget() is radios[31]
        assert palette.layout().itemAtPosition(12,1) is None
        assert radios[20].text()=='1окт 16 кГц'
        assert radios[31].text()=='2окт 400 Гц'
        assert not radios[20].isEnabled() # original FIR profile absent
        assert not actions[20].isEnabled()
        assert radios[0].isChecked()
        assert sum(int(r.isChecked()) for r in radios)==1
        _popup_from(qt_app,menu,w.spec_envelope_button)
        assert palette.isVisible()
        assert radios[0].isVisible()
        assert radios[20].isVisible()
        # Source menu renders 20 rows, two actual columns, no scroll
        # through all 32 items at DPI 150.
        assert palette.width()>=290
        assert palette.height()>=20*22
        target=os.getenv('MVK_SYNTHETIC_UI_PREVIEW_DIR')
        if target:
            folder=Path(target)
            folder.mkdir(parents=True,exist_ok=True)
            assert menu.grab().save(str(folder/'synthetic_stage111cb_original_filter_menu_two_columns.png'),'PNG')
        menu.hide()
        qt_app.processEvents()
        assert w.wave_envelope_code.currentData()==0
        assert w.spec_envelope_code.currentData()==0
        assert not w.spec_envelope_button.isChecked()
    finally:
        w.original_envelope_menu.hide()
        w.close()
        qt_app.processEvents()


def test_qt_real_radio_click_updates_both_source_pages_and_full_fft(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    src=fixture_zip(tmp_path,sample_count=120000)
    checksum=sha256(src.read_bytes()).hexdigest()
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        w.open_archive(src)
        w.wave_start.setValue(.75)
        w.wave_hscale_menu.actions()[9].trigger() # 20 ms, FIR sample data
        w.spec_n.setCurrentText('8192')
        w.set_envelope_profile(fake_profile(i=1.,q=.4))
        w.original_root_tabs.setCurrentIndex(4)
        qt_app.processEvents()
        radios=w._original_envelope_radios
        menu=w.original_envelope_menu
        plain=_graph_digest(w)
        assert radios[20].isEnabled()
        _popup_from(qt_app,menu,w.spec_envelope_button)
        QTest.mouseClick(radios[20],Qt.LeftButton)
        qt_app.processEvents()
        assert not menu.isVisible()
        assert w.wave_envelope_code.currentData()==20
        assert w.spec_envelope_code.currentData()==20
        assert w.wave_filter_button.text()=='1окт 16 кГц'
        assert w.spec_envelope_button.text()=='1окт 16 кГц'
        assert w.spec_envelope_button.isChecked()
        assert radios[20].isChecked()
        assert sum(int(r.isChecked()) for r in radios)==1
        assert w._source_envelope_cursor.code==20
        assert w._source_wave_xaxes_model['kind']=='SOURCE_FIR'
        assert w._full_spectrum['source']==(
            'APP_DERIVED_ENVELOPE_SPECTRUM_IDR_CANDIDATE')
        assert _graph_digest(w)!=plain
        assert w._source_original_envelope_receipt[
            'source_filter_caption']=='1окт 16 кГц'
        assert w._source_original_envelope_receipt[
            'source_filter_menu_column']==1
        assert w._source_original_envelope_receipt[
            'source_filter_menu_row']==0
        # Other original PageAdc button opens the SAME shared 20+12 popup.
        w.original_root_tabs.setCurrentIndex(3)
        qt_app.processEvents()
        _popup_from(qt_app,menu,w.wave_filter_button)
        QTest.mouseClick(radios[1],Qt.LeftButton)
        qt_app.processEvents()
        assert w.wave_filter_button.text()=='1/3окт 25 кГц'
        assert w.spec_envelope_button.text()=='1/3окт 25 кГц'
        assert w._source_wave_xaxes_model['envelope_code']==1
        assert w._source_envelope_cursor.code==1
        assert w.spec_envelope_code.currentData()==1
        assert radios[1].isChecked()
        assert len(w._full_spectrum['amplitude'])==(
            w._full_spectrum['n_fft']//2)
        # Code0 removes FIR from BOTH visible graph models, without
        # reusing previous Code1 source Power/Y.
        w.original_root_tabs.setCurrentIndex(4)
        qt_app.processEvents()
        _popup_from(qt_app,menu,w.spec_envelope_button)
        QTest.mouseClick(radios[0],Qt.LeftButton)
        qt_app.processEvents()
        assert not w.spec_envelope_button.isChecked()
        assert w.wave_envelope_code.currentData()==0
        assert w.spec_envelope_code.currentData()==0
        assert w._source_envelope_cursor is None
        assert w._full_spectrum['source']==(
            'APP_DERIVED_FFT_MVKVIEW_CANDIDATE')
        assert w.wave_filter_button.text()=='Без фильтра'
        assert w.spec_envelope_button.text()=='Без фильтра'
        assert radios[0].isChecked()
        assert _graph_digest(w)==plain
        assert sha256(src.read_bytes()).hexdigest()==checksum
    finally:
        w.original_envelope_menu.hide()
        w.close()
        qt_app.processEvents()


def test_disabled_original_filter_visual_radio_matches_core_fs_gate(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    from .test_stage111z16_direct_bin_tsxml import _make_pair
    file,_,_=_make_pair(tmp_path,n=8192,fs=8192,adc=4)
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        w.open_archive(file)
        w.set_envelope_profile(fake_profile(i=1.,q=.4))
        w.original_root_tabs.setCurrentIndex(4)
        qt_app.processEvents()
        a=w._original_envelope_actions
        r=w._original_envelope_radios
        assert w._source_envelope_menu_fs==8192
        assert not a[20].isEnabled() and not r[20].isEnabled()
        assert a[11].isEnabled() and r[11].isEnabled()
        assert r[20].text()=='1окт 16 кГц'
        assert r[11].text()=='1/3окт 2500 Гц'
        assert w.wave_envelope_code.currentData()==0
        assert w.spec_envelope_code.currentData()==0
        assert r[0].isChecked()
    finally:
        w.original_envelope_menu.hide()
        w.close()
        qt_app.processEvents()
