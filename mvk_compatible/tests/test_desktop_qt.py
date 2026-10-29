"""Windows PySide6 offscreen smoke test. No network/device, no sample export."""
import os
import pytest


@pytest.fixture(scope='module')
def qt_app():
    """Single QApplication lifetime across tests; avoid PySide6 Windows teardown race."""
    pytest.importorskip('PySide6')
    pytest.importorskip('pyqtgraph')
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    yield app
    app.processEvents()
    app.quit()
    app.processEvents()


def test_desktop_three_tabs_without_server(qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    app=qt_app
    window=MainWindow()
    assert window.tabs.count()==3
    assert [window.tabs.tabText(i) for i in range(3)]==[
        'Расчётные данные','Временной сигнал','Спектр']
    assert window.session is None
    assert not window.tabs.isEnabled()
    assert window.adc.count()==8
    assert window.spec_mode.count()==4
    assert window.spec_backend.count()==2
    assert window.spec_precise.isChecked()
    assert window.spec_avg.count()==2
    assert window.spec_avg.currentIndex()==0
    assert window.wave_order.count()==2
    assert window.wave_mode.itemText(0).startswith('AC ·')
    window.close()
    app.processEvents()

def test_qt_reads_synthetic_dsp_bin_fft_without_server(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    app=qt_app
    window=MainWindow()
    file=fixture_zip(tmp_path)
    window.open_archive(file)
    assert window.session is not None
    assert window.session.serial=='MVK00000123'
    assert window.tabs.isEnabled()
    assert window.tick.value()==2
    assert window.metrics.item(0,1).text()!='—'
    assert window.oct_table.item(0,1).text()!='—'
    assert '0x00000000' in window.calc_status.text()
    assert len(window.wave_plot.listDataItems())==1
    assert len(window.spec_plot.listDataItems())==1
    assert 'APP_DERIVED_FFT_MVKVIEW_CANDIDATE' in window.spec_hint.text()
    assert 'idr_float32' in window.spec_hint.text()
    window.spec_backend.setCurrentIndex(1)
    window.refresh_spec()
    assert 'numpy' in window.spec_hint.text()
    window.spec_backend.setCurrentIndex(0)
    window.refresh_spec()
    assert 'idr_float32' in window.spec_hint.text()
    assert window._full_spectrum is not None
    assert len(window._full_spectrum['amplitude'])==int(window.spec_n.currentText())//2
    # Original log mode has CursorAveraging=1, others 3.
    window.spec_mode.setCurrentIndex(1)
    app.processEvents()
    assert window.spec_avg.currentIndex()==1
    assert len(window._full_spectrum['amplitude'])==int(window.spec_n.currentText())//2
    window.spec_mode.setCurrentIndex(0)
    assert window.spec_avg.currentIndex()==0
    assert window.wave_mode.currentIndex()==0
    assert 'GetSignal/IDR' in window.wave_hint.text()
    assert 'chronological' in window.wave_hint.text()
    window.wave_order.setCurrentIndex(1)
    window.refresh_wave()
    assert 'getsignal_buffer' in window.wave_hint.text()
    assert 'НЕ время BIN' in window.wave_plot.getPlotItem().getAxis('bottom').labelText
    window.wave_mode.setCurrentIndex(1)
    window.refresh_wave()
    assert 'acdc' in window.wave_hint.text()
    cursor=window.session.exact_sample(1,31/65536,0,.0625,'acdc','getsignal_buffer')
    assert cursor['index']==4096-1-31
    window.wave_order.setCurrentIndex(0)
    window.wave_mode.setCurrentIndex(0)
    window.refresh_wave()
    assert 'chronological' in window.wave_hint.text()
    window.adc.setCurrentIndex(6)
    app.processEvents()
    assert 'ALERT' in window.calc_status.text()
    window.close()
    app.processEvents()

def test_qt_pixel_based_cursor_click_uses_full_bins(tmp_path,qt_app):
    from PySide6.QtCore import QPointF,Qt
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    window=MainWindow()
    window.open_archive(fixture_zip(tmp_path))
    window.show()
    qt_app.processEvents()
    assert window._full_spectrum is not None
    window.spec_mode.setCurrentIndex(1)
    qt_app.processEvents()
    window.spec_avg.setCurrentIndex(0)
    vb=window.spec_plot.getViewBox()
    rect=vb.sceneBoundingRect()
    assert rect.width()>3
    class LeftClick:
        def button(self): return Qt.LeftButton
        def scenePos(self): return QPointF(rect.left()+rect.width()*.25,rect.center().y())
    window._spec_click(LeftClick())
    assert 'IDR pixel' in window.spec_hint.text()
    assert 'FFT[' in window.spec_hint.text()
    assert 'avg=1' in window.spec_hint.text()
    window.spec_avg.setCurrentIndex(1)
    window._spec_click(LeftClick())
    assert 'avg=3' in window.spec_hint.text()
    assert 'без /N' in window.spec_hint.text()
    window.close()
    qt_app.processEvents()


def test_dmf_spectrum_left_panel_and_functional_scrollbars(tmp_path,qt_app):
    """Check DFM-derived structure, not claim exact Delphi pixel parity."""
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    assert win.spec_tools.objectName()=='pnSpecTools'
    assert win.spec_tools.width()==177
    assert win.spec_hscroll.objectName()=='sbSpecHScroll'
    assert win.spec_vscroll.objectName()=='sbSpecVScroll'
    assert win.spec_hscroll.height()==24
    assert win.spec_vscroll.width()==24
    assert win.spec_mode.objectName()=='bSpecType'
    assert win.spec_n.objectName()=='bSpecLines'
    assert win.spec_hscale_button.objectName()=='bSpecHScale'
    assert win.spec_vscale_button.objectName()=='bSpecVScale'
    assert win.spec_hint.objectName()=='lbSpecHint'
    assert not win.spec_envelope_button.isEnabled()  # not faked
    assert win.spec_copy_button.isEnabled()           # explicit research candidate
    assert win.spec_save_button.isEnabled()           # safe user-selected research CSV
    start=win.spec_plot.getViewBox().viewRange()[0]
    win.spec_hscale_button.click()
    qt_app.processEvents()
    mid=win.spec_plot.getViewBox().viewRange()[0]
    assert (mid[1]-mid[0]) < (start[1]-start[0])
    assert win.spec_hscroll.isVisible()
    win.spec_hscroll.setValue(0)
    qt_app.processEvents()
    near=win.spec_plot.getViewBox().viewRange()[0]
    win.spec_hscroll.setValue(1000)
    qt_app.processEvents()
    far=win.spec_plot.getViewBox().viewRange()[0]
    assert far[0]>near[0]
    win.spec_vscale_button.click()
    qt_app.processEvents()
    assert win.spec_vscroll.isVisible()
    win.close()
    qt_app.processEvents()


def test_qt_optional_user_supplied_envelope_preview_is_explicit(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.tests.test_envelope_idr_candidate import fake_profile
    from .test_offline_core import fixture_zip
    window=MainWindow()
    window.open_archive(fixture_zip(tmp_path))
    window.show()
    window.tabs.setCurrentIndex(1)
    qt_app.processEvents()
    assert window.envelope_profile is None
    assert window.wave_envelope_code.count()==32
    assert not window.wave_envelope_code.isEnabled()
    window.wave_start.setValue(.02)
    window.wave_seconds.setValue(.02)
    window.set_envelope_profile(fake_profile())
    assert window.wave_envelope_code.isEnabled()
    window.wave_envelope_code.setCurrentIndex(1)
    qt_app.processEvents()
    assert 'Огибающая IDR (эксперимент)' in window.wave_hint.text()
    assert 'оригинальный формат/время/курсор НЕ приняты' in window.wave_hint.text()
    assert len(window.wave_plot.listDataItems())==1
    assert 'НЕ время оригинальной MVKView' in window.wave_plot.getPlotItem().getAxis('bottom').labelText
    window.wave_envelope_code.setCurrentIndex(0)
    qt_app.processEvents()
    assert 'GetSignal/IDR' in window.wave_hint.text()
    window.close()
    qt_app.processEvents()


def test_qt_stage111f_spectrum_envelope_requires_private_profile(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.tests.test_envelope_idr_candidate import fake_profile
    from .test_offline_core import fixture_zip
    window=MainWindow()
    window.open_archive(fixture_zip(tmp_path))
    window.show()
    window.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    assert window._full_spectrum['source']=='APP_DERIVED_FFT_MVKVIEW_CANDIDATE'
    assert not window.spec_envelope_button.isEnabled()
    assert not window.spec_envelope_button.isChecked()
    assert not window.spec_envelope_code.isEnabled()
    window.set_envelope_profile(fake_profile())
    assert window.spec_envelope_button.isEnabled()
    assert window.spec_envelope_code.isEnabled()
    assert window.spec_envelope_code.currentData()==20
    window.spec_envelope_button.setChecked(True)
    qt_app.processEvents()
    assert window.spec_envelope_button.isChecked()
    assert window.spec_n.currentText()=='1024' # exact source FIR history; no N padding
    assert window._full_spectrum['source']=='APP_DERIVED_ENVELOPE_SPECTRUM_IDR_CANDIDATE'
    assert len(window._full_spectrum['amplitude'])==512
    assert 'повторного DC нет' in window.spec_hint.text()
    assert not window.spec_compare_button.isEnabled()
    assert window.spec_copy_button.isEnabled()
    assert window.spec_save_button.isEnabled()
    window.spec_envelope_button.setChecked(False)
    qt_app.processEvents()
    assert window._full_spectrum['source']=='APP_DERIVED_FFT_MVKVIEW_CANDIDATE'
    assert window.spec_compare_button.isEnabled()
    window.close()
    qt_app.processEvents()


def test_qt_stage111g_three_field_copy_and_local_save_candidate(tmp_path,qt_app,monkeypatch):
    from pathlib import Path
    from PySide6.QtWidgets import QApplication,QFileDialog
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    window=MainWindow()
    window.open_archive(fixture_zip(tmp_path))
    window.show()
    window.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    assert window._full_spectrum is not None
    assert window._spectrum_summary is not None
    assert 'GetSpectrum' in window.spec_mean.text()
    assert 'Пик:' in window.spec_mean.text()
    assert 'паритет' in window.spec_mean.text()
    assert window.spec_copy_button.isEnabled()
    assert window.spec_save_button.isEnabled()
    window.spec_copy_button.click()
    qt_app.processEvents()
    copied=QApplication.clipboard().text()
    assert len(copied.split('\t'))==3
    assert all(copied.split('\t'))
    # Intercept the *user action* file picker; never open a real directory.
    path=tmp_path/'candidate-export.csv'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',
                        lambda *a,**k:(str(path),'CSV (*.csv)'))
    window.spec_save_button.click()
    qt_app.processEvents()
    assert path.exists()
    lines=path.read_text(encoding='utf-8').splitlines()
    assert lines[0]=='sep=|'
    assert len(lines)==3
    assert len(lines[-1].split('|'))==3
    assert 'кандидат' in lines[1]
    window.close()
    qt_app.processEvents()


def test_qt_stage111h_original_narrowband_and_noise_peak_inspector(tmp_path,qt_app):
    """Original 007D0E58 research control must not alter DSP table or Spectra."""
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    assert win.narrow_result is not None and win.narrow_noise is not None
    previous=win._full_spectrum
    dsp=win.session.calculations()
    win.narrow_frequency.setValue(64.)
    win.narrow_run.click()
    qt_app.processEvents()
    assert 'IDR узкополосный' in win.narrow_result.text()
    assert '4 ±1 FFT-бин' in win.narrow_result.text()
    assert 'не приборный DSP' in win.narrow_result.text()
    win.narrow_noise.setChecked(True)
    win.narrow_run.click()
    qt_app.processEvents()
    assert 'Шумовой пик' in win.narrow_result.text()
    assert 'исключены FFT-бин(ы)' in win.narrow_result.text()
    assert win._full_spectrum is previous
    assert win.session.calculations()==dsp
    win.narrow_frequency.setValue(32768.)
    win.narrow_run.click()
    assert 'расчёт отклонён' in win.narrow_result.text()
    win.close()
    qt_app.processEvents()


def test_qt_stage111i_explicit_f_range_labels_and_narrowband_are_research_only(tmp_path,qt_app):
    import numpy as np
    import pytest
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    assert win.spec_f_range.value()==1.
    win.spec_mode.setCurrentIndex(1)
    qt_app.processEvents()
    first=win._full_spectrum
    assert first is not None
    base=np.asarray(first['amplitude'],dtype=float)
    idx=int(np.argmax(base))
    assert base[idx]>0
    dsp=win.session.calculations()
    win.spec_f_range.setValue(2.5)
    win.refresh_spec()
    qt_app.processEvents()
    updated=win._full_spectrum
    assert updated['f_range_used']==2.5
    assert updated['f_range_source']=='OPERATOR_SUPPLIED_UNVERIFIED'
    assert updated['amplitude'][idx]==pytest.approx(base[idx]*2.5,rel=1e-5)
    assert 'FRange=2.5' in win.spec_hint.text()
    assert 'НЕ доказана' in win.spec_hint.text()
    win.narrow_frequency.setValue(64.)
    win.narrow_run.click()
    qt_app.processEvents()
    assert 'FRange=2.5' in win.narrow_result.text()
    assert win.session.calculations()==dsp
    win.close()
    qt_app.processEvents()
