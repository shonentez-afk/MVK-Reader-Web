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
        'Задачи','Временной сигнал','Спектр']
    assert window.session is None
    assert window.tabs.isEnabled()
    assert window.tabs.isTabEnabled(0)
    assert not window.tabs.isTabEnabled(1)
    assert not window.tabs.isTabEnabled(2)
    assert window.task_subpages.tabText(0)=='Обзор'
    assert window.task_open_button.isEnabled()
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
    # Research labels are in their own dock, so the original 177px width
    # is again available for primary Spectrum controls.
    assert win.spec_tools.width()==177
    from PySide6.QtCore import Qt
    assert win.spec_tools.horizontalScrollBarPolicy()==Qt.ScrollBarAlwaysOff
    assert win.spec_copy_button.text()=='Копировать'
    assert win.spec_hscroll.objectName()=='sbSpecHScroll'
    assert win.spec_vscroll.objectName()=='sbSpecVScroll'
    assert win.spec_hscroll.height()==24
    assert win.spec_vscroll.width()==24
    assert win.spec_mode.objectName()=='bSpecType'
    assert win.spec_n.objectName()=='bSpecLines'
    assert win.spec_hscale_button.objectName()=='bSpecHScale'
    assert win.spec_vscale_button.objectName()=='bSpecVScale'
    assert win.spec_hint.objectName()=='lbSpecHint'
    assert win.spec_cursor_primary.objectName()=='lbSpecHintPrimary'
    assert win.spec_mean_primary.objectName()=='lbSpecMeanPrimary'
    assert not win.spec_envelope_button.isEnabled()  # not faked
    assert win.spec_copy_button.isEnabled()           # explicit research candidate
    assert win.spec_save_button.isEnabled()           # safe user-selected research CSV
    start=win.spec_plot.getViewBox().viewRange()[0]
    win.spec_hscale_button.click()
    qt_app.processEvents()
    mid=win.spec_plot.getViewBox().viewRange()[0]
    assert (mid[1]-mid[0]) < (start[1]-start[0])
    assert win.spec_hscroll.isVisible()
    from mvk_compatible.core.tqgrapher_spectrum_scroll_idr_candidate import SOURCE
    scroll=win._spec_hscroll_source_candidate
    assert scroll['source']==SOURCE
    assert scroll['delphi_page_size']==win.spec_hscroll.pageStep()
    assert scroll['qt_maximum']==win.spec_hscroll.maximum()
    assert scroll['qt_single_step']==win.spec_hscroll.singleStep()
    assert scroll['qt_maximum']==scroll['source_full_size']-scroll['delphi_page_size']
    assert scroll['delphi_max']==scroll['source_full_size']-1
    assert scroll['page_size_from_qt_view_candidate'] is True
    assert scroll['original_plot_coordinate_parity_verified'] is False
    assert scroll['source_menu_preset_verified'] is False
    # Original H scrollbar position is integer Hz (NOT normalized 0..1000).
    assert win.spec_hscroll.maximum()>1000
    win.spec_hscroll.setValue(0)
    qt_app.processEvents()
    near=win.spec_plot.getViewBox().viewRange()[0]
    win.spec_hscroll.setValue(win.spec_hscroll.maximum())
    qt_app.processEvents()
    far=win.spec_plot.getViewBox().viewRange()[0]
    assert far[0]>near[0]
    assert abs(far[0]-win.spec_hscroll.value())<2.0
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


def test_qt_stage111i_compares_local_original_clipboard_without_remote_or_raw_dump(tmp_path,qt_app,monkeypatch):
    from PySide6.QtWidgets import QFileDialog,QMessageBox
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.core.spectrum_summary_export_candidate import spectrum_triplet_text
    from .test_offline_core import fixture_zip
    window=MainWindow()
    window.open_archive(fixture_zip(tmp_path))
    window.show()
    window.tabs.setCurrentIndex(2)
    window.spec_mode.setCurrentIndex(1)
    qt_app.processEvents()
    assert window.spec_original_copy_compare.isEnabled()
    original=spectrum_triplet_text(window._spectrum_summary,decimal_separator=',')
    private=tmp_path/'synthetic-original-copy.txt'
    private.write_text(original,encoding='utf-8')
    monkeypatch.setattr(QFileDialog,'getOpenFileName',
                        lambda *args,**kwargs:(str(private),'Text (*.txt)'))
    messages=[]
    monkeypatch.setattr(QMessageBox,'information',
                        lambda *args:messages.append((args[1],args[2])))
    window.spec_original_copy_compare.click()
    qt_app.processEvents()
    assert len(messages)==1
    title,body=messages[0]
    assert 'оригинальной MVKView' in title
    assert 'ЧИСЛЕННЫЕ ЗНАЧЕНИЯ В ЗАДАННОМ ДОПУСКЕ' in body
    assert 'Текст 3 полей совпал: да' in body
    assert 'Полный численный и визуальный паритет НЕ доказан' in body
    assert original not in body
    assert private.is_file()
    window.close()
    qt_app.processEvents()


def test_qt_stage111j_original_spectrum_visible_series_and_cursor_text(tmp_path,qt_app):
    import numpy as np
    import pytest
    from PySide6.QtCore import Qt,QPointF
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    win.spec_mode.setCurrentIndex(1)
    win.spec_hz.setValue(32768.)
    win.refresh_spec()
    qt_app.processEvents()
    original_dsp=win.session.calculations()
    n=int(win.spec_n.currentText())
    original_size=int((n//2)/1.28)
    assert win._full_spectrum['grapher_series_bins']==original_size
    assert win._spec_display_contract['full_fft_power_bins']==n//2
    assert len(win._full_spectrum['amplitude'])==n//2
    assert len(win.spec_plot.listDataItems())==1
    assert len(win.spec_plot.listDataItems()[0].xData)==original_size
    # Original plotted axis ends at DataSize*XScale, not final data center.
    assert win._spec_visible_max_hz==pytest.approx(original_size*65536/n)
    assert win._spec_display_contract['grapher_axis_end_frequency_hz']==pytest.approx(
        original_size*65536/n)
    assert 'TQGRSeries=' in win.spec_hint.text()
    base=np.asarray(win._full_spectrum['amplitude'])
    peak=int(np.argmax(base))
    assert base[peak]>0
    assert win.spec_input_domain.currentData()=='calibrated_bin'
    win.spec_f_range.setValue(4.)
    win.spec_input_domain.setCurrentIndex(1)
    win.refresh_spec()
    qt_app.processEvents()
    changed=win._full_spectrum
    assert changed['input_domain']=='original_float_storage'
    assert changed['original_storage_read_divided_by_range']
    assert changed['original_source_buffer_provenance_verified'] is False
    assert changed['amplitude'][peak]==pytest.approx(base[peak],rel=1e-4)
    assert win.session.calculations()==original_dsp
    vb=win.spec_plot.getViewBox()
    rect=vb.sceneBoundingRect()
    class LeftClick:
        def button(self):return Qt.LeftButton
        def scenePos(self):return QPointF(rect.left()+rect.width()*.3,
                                         rect.center().y())
    win._spec_click(LeftClick())
    assert 'CursorString IDR-кандидат' in win.spec_hint.text()
    assert 'snap=' in win.spec_hint.text()
    assert 'Гц' in win.spec_hint.text()
    assert 'кандидат' in win.spec_hint.text()
    win.close()
    qt_app.processEvents()


def test_qt_stage111k_canvas_geometry_shows_source_transforms_without_vendor_claim(
        tmp_path,qt_app,monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    window=MainWindow()
    assert not window.spec_canvas_geometry_button.isEnabled()
    window.open_archive(fixture_zip(tmp_path))
    window.show()
    window.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    assert window.spec_canvas_geometry_button.isEnabled()
    notices=[]
    monkeypatch.setattr(QMessageBox,'information',
                        lambda *args:notices.append((args[1],args[2])))
    window.spec_canvas_geometry_button.click()
    qt_app.processEvents()
    assert len(notices)==1
    title,body=notices[0]
    assert 'Canvas' in title
    assert 'итов' not in title  # numeric source transform, not decorative text
    assert 'PixelRect' in body
    assert 'itosM=' in body and 'stoiM=' in body
    assert 'Это НЕ фактический прямоугольник оригинальной MVKView' in body
    preview=window._spec_canvas_geometry_preview
    assert preview['source']=='APP_DERIVED_TQGRAPHER_CANVAS_GEOMETRY_IDR_CANDIDATE'
    assert preview['pixel_right']>preview['pixel_left']
    assert not preview['original_pixel_rectangle_verified']
    assert not preview['original_canvas_font_metrics_verified']
    window.close()
    qt_app.processEvents()


def test_qt_stage111m_raw_horizontal_crosshair_differs_from_rms_label(tmp_path,qt_app):
    """Original 007CA9BA draws raw selected FFT Y, not CursorAveraging=3 label."""
    import numpy as np
    import pytest
    from PySide6.QtCore import QPointF,Qt
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(2)
    win.spec_mode.setCurrentIndex(1)
    win.spec_avg.setCurrentIndex(1)  # CursorAveraging 3
    qt_app.processEvents()
    win.refresh_spec()
    qt_app.processEvents()
    assert win.spec_hline is not None
    assert not win.spec_hline.isVisible()
    rect=win.spec_plot.getViewBox().sceneBoundingRect()
    class MouseClick:
        def button(self):return Qt.LeftButton
        def scenePos(self):
            return QPointF(rect.left()+rect.width()*.36,rect.center().y())
    win._spec_click(MouseClick())
    qt_app.processEvents()
    assert win.spec_hline.isVisible()
    assert win._spec_last_cursor is not None
    picked=win._spec_last_cursor
    value=float(win._full_spectrum['amplitude'][picked['selected_bin']])
    assert win.spec_hline.value()==pytest.approx(value,rel=1e-6,abs=1e-9)
    assert picked['averaging']==3
    assert 'Горизонталь = raw FFT' in win.spec_hint.text()
    assert 'пиксели Delphi НЕ приняты' in win.spec_hint.text()
    assert win.session.calculations()['source']=='MVK_DSP'
    win.close()
    qt_app.processEvents()


def test_qt_stage111m_original_outside_cursor_erases_x_and_y_crosshair(tmp_path,qt_app):
    """007CA811..007CA832: outside original PixelLeft/Right clears the cursor."""
    from PySide6.QtCore import QPointF,Qt
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    w=MainWindow()
    w.open_archive(fixture_zip(tmp_path))
    w.show()
    w.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    rect=w.spec_plot.getViewBox().sceneBoundingRect()
    class Click:
        def __init__(self,pos):self.pos=pos
        def button(self):return Qt.LeftButton
        def scenePos(self):return self.pos
    assert not w.spec_hline.isVisible()
    assert not w.spec_line.isVisible()
    w._spec_click(Click(QPointF(rect.center().x(),rect.center().y())))
    qt_app.processEvents()
    assert w.spec_line.isVisible() and w.spec_hline.isVisible()
    assert w._spec_last_cursor is not None
    w._spec_click(Click(QPointF(rect.right()+10.,rect.center().y())))
    assert not w.spec_line.isVisible()
    assert not w.spec_hline.isVisible()
    assert w._spec_last_cursor is None
    assert 'курсор вне области графика' in w.spec_hint.text()
    w.close()
    qt_app.processEvents()

def test_qt_stage111o_spec_mousemove_updates_original_x_only_and_clears(tmp_path,qt_app):
    """0084C918..933 uses X mouse movement; no button and no Y needed."""
    from PySide6.QtCore import QPointF
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    rect=win.spec_plot.getViewBox().sceneBoundingRect()
    assert rect.width()>20
    assert not win.spec_line.isVisible() and not win.spec_hline.isVisible()
    p=QPointF(rect.left()+rect.width()*.35,rect.center().y())
    win._spec_mouse_move(p)
    assert win.spec_line.isVisible() and win.spec_hline.isVisible()
    first=win._spec_last_cursor
    assert first is not None
    assert 'IDR pixel' in win.spec_hint.text()
    # Same integer mouse X must skip redraw even if Y moves outside plot.
    win._spec_mouse_move(QPointF(p.x(),rect.top()-20.))
    assert win._spec_last_cursor is first
    # Movement X alone must update even with Y outside the plot rectangle.
    win._spec_mouse_move(QPointF(p.x()+5.,rect.top()-20.))
    assert win._spec_last_cursor is not first
    assert win.spec_line.isVisible() and win.spec_hline.isVisible()
    win._spec_mouse_move(QPointF(rect.right()+10.,rect.center().y()))
    assert not win.spec_line.isVisible() and not win.spec_hline.isVisible()
    assert win._spec_last_cursor is None
    assert 'курсор вне области графика' in win.spec_hint.text()
    assert win.session.calculations()['source']=='MVK_DSP'
    win.close()
    qt_app.processEvents()


def test_qt_stage111o_wave_mousemove_uses_cached_full_getsignal(tmp_path,qt_app):
    """0084B4AC: waveform cursor follows X, not click; cached offline only."""
    from PySide6.QtCore import QPointF
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(1)
    qt_app.processEvents()
    rect=win.wave_plot.getViewBox().sceneBoundingRect()
    assert rect.width()>30
    assert not win.wave_line.isVisible()
    assert win._wave_hover_window is None
    initial=QPointF(rect.left()+rect.width()*.4,rect.center().y())
    win._wave_mouse_move(initial)
    assert win.wave_line.isVisible()
    assert win._wave_hover_window is not None
    assert 'MouseMove IDR-кандидат' in win.wave_hint.text()
    cached=win._wave_hover_window
    original_pos=win._wave_mouse_pixel
    old=win.wave_hint.text()
    win._wave_mouse_move(QPointF(initial.x(),rect.top()-17.))
    assert win._wave_hover_window is cached
    assert win._wave_mouse_pixel==original_pos
    assert win.wave_hint.text()==old
    win._wave_mouse_move(QPointF(initial.x()+8.,rect.center().y()))
    assert win._wave_hover_window is cached
    assert 'BIN[' in win.wave_hint.text()
    win._wave_mouse_move(QPointF(rect.left()-10.,rect.center().y()))
    assert not win.wave_line.isVisible()
    assert 'курсор вне временного графика' in win.wave_hint.text()
    win.close()
    qt_app.processEvents()


def test_qt_stage111o_no_unverified_envelope_mouse_cursor(tmp_path,qt_app):
    from PySide6.QtCore import QPointF
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(1)
    qt_app.processEvents()
    rect=win.wave_plot.getViewBox().sceneBoundingRect()
    win.wave_envelope_code.setEnabled(True)
    win.wave_envelope_code.blockSignals(True)
    win.wave_envelope_code.setCurrentIndex(2)
    win.wave_envelope_code.blockSignals(False)
    qt_app.processEvents()
    # No source-accepted envelope hover or fabricated FIR values.
    pos=QPointF(rect.left()+rect.width()*.45,rect.center().y())
    win._wave_mouse_move(pos)
    assert win._wave_hover_window is None
    assert not win.wave_line.isVisible()
    win.close()
    qt_app.processEvents()

def test_qt_stage111q_source_margin_and_scrollbar_registration(tmp_path,qt_app,monkeypatch):
    """Real Delphi 0084C840 margin is size-dependent, Qt viewport is not TPaintBox."""
    from PySide6.QtWidgets import QMessageBox
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.core.tqgrapher_paintbox_registration_idr_candidate import (
        SOURCE,source_paintbox_margin)
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    notices=[]
    monkeypatch.setattr(QMessageBox,'information',
                        lambda *args:notices.append((args[1],args[2])))
    win.spec_canvas_geometry_button.click()
    qt_app.processEvents()
    assert len(notices)==1
    title,body=notices[0]
    g=win._spec_canvas_geometry_preview
    assert g['paintbox_registration_source']==SOURCE
    measured=source_paintbox_margin(g['paintbox_pixel_width'],g['paintbox_pixel_height'])
    assert measured==g['margin_before_tqgrapher_minimum']
    assert g['effective_source_margin']==max(10,measured)
    assert g['spectrum_horizontal_scroll_left']==g['pixel_left']
    assert g['spectrum_horizontal_scroll_width']==g['pixel_right']-g['pixel_left']
    assert g['spectrum_vertical_scroll_top']==g['pixel_top']
    assert g['spectrum_vertical_scroll_height']==g['pixel_bottom']-g['pixel_top']
    assert g['qt_viewport_device_pixel_ratio']>0
    assert g['qt_viewport_logical_dpi_x']>0
    assert g['qt_viewport_logical_dpi_y']>0
    assert isinstance(g['qt_font_family_candidate'],str)
    assert not g['qt_viewbox_and_paintbox_registration_verified']
    assert not g['original_dpi_parity_verified']
    assert not g['original_font_identity_verified']
    assert g['dfm_design_form_font_family']=='Tahoma'
    assert g['dfm_design_form_font_height']==-13
    assert g['dfm_design_pixels_per_inch']==96
    assert g['dfm_design_spectrum_paintbox_size']==(767,716)
    assert g['original_dfm_runtime_canvas_font_verified'] is False
    bridge=g['qt_to_tpaintbox_bridge_candidate']
    assert bridge['qt_scene_x_to_native_x_scale']>0
    assert bridge['qt_scene_y_to_native_y_scale']>0
    assert bridge['device_pixel_ratio_not_applied_to_native_transform'] is True
    assert bridge['original_delphi_pixel_parity_verified'] is False
    assert bridge['native_mouse_integer_rounding_parity_verified'] is False
    assert 'Qt→TPaintBox affine-кандидат' in body
    assert 'DFM design-time:' in body
    assert 'Margin по оригиналу' in body
    assert 'Scrollbars оригинал/TPaintBox' in body
    assert 'DPR=' in body
    assert 'Это НЕ фактический прямоугольник оригинальной MVKView' in body
    win.close()
    qt_app.processEvents()

def test_qt_stage111s_all_original_h_scale_menu_entries_and_position(tmp_path,qt_app):
    """Native popup has exactly 10 recovered Delphi presets; NFFT still research."""
    from PySide6.QtWidgets import QToolButton
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.core.mvk_original_scale_tables_idr_candidate import (
        HORIZONTAL_HZ,original_h_scale_options)
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    assert isinstance(win.spec_hscale_button,QToolButton)
    actions=win.spec_hscale_button.menu().actions()
    assert len(actions)==10
    assert [a.data() for a in actions]==list(HORIZONTAL_HZ)
    assert [a.text() for a in actions]==[r['caption'] for r in original_h_scale_options()]
    assert win._spec_original_hscale_selected is None
    # Stage111Z.18: default now matches original 25600 Hz screen,
    # so the first click selects the next original preset, 12800 Hz.
    assert win.spec_hscale_button.text()=="25600 Гц"
    win.spec_hscale_button.click()
    qt_app.processEvents()
    assert win._spec_original_hscale_selected==12800
    assert sum(a.isChecked() for a in actions)==1
    assert actions[1].isChecked()
    assert win.spec_hscroll.maximum()==25600-12800
    assert win.spec_hscroll.pageStep()==12800
    assert win.spec_hscroll.singleStep()==1280
    win.spec_hscroll.setValue(1200)
    qt_app.processEvents()
    left=win.spec_plot.getViewBox().viewRange()[0][0]
    assert abs(left-1200)<2
    # Original H rescale holds previous Position until clamped by Full-Page.
    actions[3].trigger()  # Tag=3 -> 3200Hz
    qt_app.processEvents()
    assert win._spec_original_hscale_selected==3200
    assert win.spec_hscroll.value()==1200
    assert win.spec_hscroll.maximum()==25600-3200
    assert win.spec_hscroll.pageStep()==3200
    assert actions[3].isChecked() and not actions[2].isChecked()
    assert abs(win.spec_plot.getViewBox().viewRange()[0][0]-1200)<2
    actions[0].trigger()  # Full 25600Hz resets to left edge and hides bar.
    qt_app.processEvents()
    assert win._spec_original_hscale_selected==25600
    assert win.spec_hscroll.maximum()==0
    assert not win.spec_hscroll.isVisible()
    assert actions[0].isChecked()
    win.close()
    qt_app.processEvents()

def test_stage111t_original_vertical_six_menu_and_scroll_position(tmp_path,qt_app):
    """Source VCL Max/Page/Tag and mode transition; Qt Y baseline is candidate."""
    from PySide6.QtWidgets import QToolButton
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.core.mvk_original_scale_tables_idr_candidate import (
        DB_Y_RANGES,PHYSICAL_Y_DIVISORS)
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    assert isinstance(win.spec_vscale_button,QToolButton)
    actions=win.spec_vscale_menu.actions()
    assert len(actions)==6
    assert [a.text() for a in actions]==[f'{n} дБ' for n in DB_Y_RANGES]
    actions[2].trigger()  # source dB tag2: page 75, full 150
    qt_app.processEvents()
    assert win._spec_original_vscale_tag==2
    assert win.spec_vscroll.maximum()==75
    assert win.spec_vscroll.pageStep()==75
    assert win.spec_vscroll.isVisible()
    assert win._spec_vscroll_source_candidate['db_mode'] is True
    assert win._spec_vscroll_source_candidate['source_menu_values_verified'] is True
    assert win._spec_vscroll_source_candidate['original_delphi_y_canvas_parity_verified'] is False
    win.spec_vscroll.setValue(10)
    qt_app.processEvents()
    assert win._spec_vertical_model['delphi_position']==10
    actions[3].trigger()  # source dB 50, oldpos10+oldpage75-newpage50
    qt_app.processEvents()
    assert win._spec_vertical_model['page']==50
    assert win.spec_vscroll.value()==35
    assert win.spec_vscroll.maximum()==100
    win.spec_mode.setCurrentIndex(1)
    qt_app.processEvents()
    assert win._spec_original_vscale_tag==3  # original mode reset
    assert win._spec_vertical_model['full']==100000
    assert win._spec_vertical_model['page']==100
    assert win.spec_vscroll.maximum()==99900
    assert [a.text() for a in win.spec_vscale_menu.actions()]==[
        f'÷ {n}' for n in PHYSICAL_Y_DIVISORS]
    assert win._spec_vscroll_source_candidate['qt_y_baseline_from_local_spectrum'] is True
    assert not win._spec_vscroll_source_candidate['original_delphi_y_canvas_parity_verified']
    win.spec_mode.setCurrentIndex(0)
    qt_app.processEvents()
    assert win._spec_original_vscale_tag==0
    assert win._spec_vertical_model['page']==150
    assert not win.spec_vscroll.isVisible()
    win.close()
    qt_app.processEvents()


def test_stage111t_fft_source_presets_fail_closed_on_short_real_bin(tmp_path,qt_app):
    """Never turn a 4096-sample BIN into a fake original >=8192-point FFT."""
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.core.mvk_original_scale_tables_idr_candidate import (
        FFT_WINDOW_SAMPLES)
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    assert [int(win.spec_n.itemText(i)) for i in range(6)]==list(FFT_WINDOW_SAMPLES)
    assert [int(win.spec_n.itemText(i)) for i in (6,7)]==[1024,4096]
    assert win.spec_n.currentText()=='4096'
    assert win._spec_last_valid_fft_n==4096
    assert 'ИССЛЕДОВАТЕЛЬСКИЙ' in win.spec_n_provenance.text()
    assert all(not win.spec_n.model().item(i).isEnabled() for i in range(6))
    assert all(win.spec_n.model().item(i).isEnabled() for i in (6,7))
    existing=win._full_spectrum
    win.spec_n.setCurrentText('8192')  # even programmatic selection cannot pad
    qt_app.processEvents()
    assert win.spec_n.currentText()=='4096'
    assert win._full_spectrum is existing
    assert len(win._full_spectrum['amplitude'])==2048
    win.close()
    qt_app.processEvents()


def test_stage111t_first_original_fft_8192_with_real_synthetic_history(tmp_path,qt_app):
    """A real 8192-sample synthetic archive enables original menu N=8192."""
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path,sample_count=8192))
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    assert win.spec_n.currentText()=='8192'
    assert win._spec_last_valid_fft_n==8192
    assert win.spec_n.model().item(5).isEnabled()
    assert not win.spec_n.model().item(4).isEnabled()
    assert 'ОРИГИНАЛЬНЫЙ пункт bSpecLines' in win.spec_n_provenance.text()
    assert len(win._full_spectrum['amplitude'])==4096
    assert win._spec_display_contract['grapher_series_bins']==3200
    win.close()
    qt_app.processEvents()

def test_stage111u_graph_default_vscale_original_algorithm_visible_but_not_certified(tmp_path,qt_app):
    """Original FRange/mode/1-2-5 branch in Qt diagnostic, not actual GDI parity."""
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    from mvk_compatible.core.spectrum_graph_default_vscale_idr_candidate import SOURCE
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    assert win.spec_graph_default_label.objectName()=='lbSpecGraphDefaultVScaleCandidate'
    info=win._spec_graph_default_vscale_candidate
    assert info['source']==SOURCE
    assert info['source_mode_multiplier']==1
    assert info['candidate_graph_default_vscale_single']==1.
    assert not info['local_f_range_is_original_channel_frange_verified']
    assert not info['original_delphi_graph_default_vscale_numeric_parity_verified']
    assert 'x87 НЕ ПОДТВЕРЖДЕНЫ' in win.spec_graph_default_label.text()
    assert 'исходное CW=0x1332' in win.spec_graph_default_label.text()
    assert 'runtime не измерен' in win.spec_graph_default_label.text()
    assert info['original_idr_static_initial_pc']=='64_bit'
    assert info['original_idr_static_initial_cw_verified']
    assert info['original_process_cw_at_spectrum_verified'] is False

    win.spec_mode.setCurrentIndex(2)  # source velocity multiplier 10
    qt_app.processEvents()
    assert win._spec_graph_default_vscale_candidate['source_mode_multiplier']==10
    assert win._spec_graph_default_vscale_candidate['candidate_graph_default_vscale_single']==10.
    assert win._spec_original_vscale_tag==3
    scroll=win._spec_vscroll_source_candidate
    assert scroll['source_graph_default_vscale_formula_candidate']['source']==SOURCE
    assert scroll['source_y_scroll_using_manual_frange_candidate']['scr_height_single']==pytest.approx(.01)
    assert not scroll['local_manual_frange_is_original_verified']
    assert not scroll['original_delphi_y_canvas_parity_verified']
    assert scroll['qt_original_graph_default_vscale_estimated']

    win.spec_f_range.setValue(.31)
    win.refresh_spec()
    qt_app.processEvents()
    info=win._spec_graph_default_vscale_candidate
    assert info['candidate_graph_default_vscale_single']==pytest.approx(5.)
    scroll=win._spec_vscroll_source_candidate
    assert scroll['source_y_scroll_using_manual_frange_candidate']['scr_height_single']==pytest.approx(.005)
    assert scroll['qt_y_baseline_from_local_spectrum']
    assert scroll['source_graph_default_vscale_formula_candidate']['original_math_helpers_x87_rounding_verified'] is False
    assert not scroll['original_delphi_y_canvas_parity_verified']
    # log10(1000) is an x87 extended-precision boundary under original
    # on-disk CW 0x1332; Python's float64 candidate can give a different step.
    win.spec_mode.setCurrentIndex(3)
    win.spec_f_range.setValue(10.)
    win.refresh_spec()
    qt_app.processEvents()
    assert win._spec_graph_default_vscale_candidate[
        'original_x87_boundary_requires_runtime_reference'] is True
    assert win._spec_graph_default_vscale_candidate[
        'original_process_cw_at_spectrum_verified'] is False
    assert 'На границе x87' in win.spec_graph_default_label.text()
    assert win._spec_vscroll_source_candidate[
        'original_delphi_y_canvas_parity_verified'] is False
    win.close()
    qt_app.processEvents()


# Stage111Z.16: Qt direct BIN/TSXML and no fabricated DSP (Windows Qt suite)
def test_qt_imports_direct_bin_tsxml_and_displays_no_fabricated_dsp(
    tmp_path, qt_app,
):
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.core.direct_bin_session import DirectBinSession
    from .test_stage111z16_direct_bin_tsxml import _make_pair

    source, sidecar, original = _make_pair(tmp_path, adc=4, n=8192)
    win=MainWindow()
    win.open_archive(source)
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()

    assert isinstance(win.session,DirectBinSession)
    assert win.adc.currentText()=="АЦП 4"
    assert win.adc.currentIndex()==3
    assert win.tick.value()==1 and win.tick.maximum()==1
    assert win.tabs.isEnabled()
    assert win.adc.model().item(3).isEnabled()
    assert all(
        not win.adc.model().item(i).isEnabled()
        for i in range(8) if i!=3
    )
    assert "BIN/TSXML" in win.title.text()
    assert "DSP" in win.calc_source.text()
    assert "недоступны" not in win.calc_source.text() or "отсутствуют" in win.calc_source.text()
    assert "не подтверждена" in win.note.text()
    assert win.metrics.item(0,1).text()=="—"
    assert win.oct_table.item(0,1).text()=="—"
    assert win._full_spectrum is not None
    assert len(win._full_spectrum["amplitude"])==4096
    assert win._full_spectrum["physical_units_verified"] is False
    assert len(win.wave_plot.listDataItems())==1
    assert "BIN/TSXML" in win.statusBar().currentMessage()

    assert win.spec_tools.width()==177
    from PySide6.QtCore import Qt
    assert win.spec_tools.horizontalScrollBarPolicy()==Qt.ScrollBarAlwaysOff
    assert win.spec_copy_button.text()=="Копировать"
    assert win.spec_save_button.text()=="Сохранить CSV"
    # Source button captions must fit within the sidebar available width.
    available=win.spec_tools.viewport().width()
    assert available >= 155
    # Nine original primary controls; research tools live in QDockWidget.
    for widget in (
        win.spec_envelope_button,win.spec_mode,win.spec_lines_button,
        win.spec_cursor_primary,win.spec_mean_primary,
        win.spec_copy_button,win.spec_save_button,win.spec_hscale_button,
        win.spec_vscale_button,
    ):
        assert widget.minimumWidth()==0
        assert widget.width() <= available
    assert not win.spec_inspector.isVisible()
    win.close()
    qt_app.processEvents()


def test_qt_can_switch_direct_session_to_existing_native_zip_without_fake_dsp(
    tmp_path, qt_app,
):
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.core.direct_bin_session import DirectBinSession
    from mvk_compatible.core.offline_export import OfflineSession
    from .test_stage111z16_direct_bin_tsxml import _make_pair
    from .test_offline_core import fixture_zip

    source,sidecar,_=_make_pair(tmp_path,adc=4)
    win=MainWindow()
    win.open_archive(sidecar)
    assert isinstance(win.session,DirectBinSession)
    assert "DSP" in win.calc_source.text()
    assert win.adc.currentIndex()==3

    native=fixture_zip(tmp_path)
    win.open_archive(native)
    assert isinstance(win.session,OfflineSession)
    assert not isinstance(win.session,DirectBinSession)
    assert win.adc.currentIndex()==0
    assert all(win.adc.model().item(i).isEnabled() for i in range(8))
    assert win.tick.maximum()==2 and win.tick.value()==2
    assert win.metrics.item(0,1).text()!="—"
    assert win.oct_table.item(0,1).text()!="—"
    assert "Приборный DSP" in win.calc_source.text()
    assert win._full_spectrum is not None
    win.close()
    qt_app.processEvents()


def test_invalid_or_unpaired_direct_bin_does_not_replace_loaded_zip(
    tmp_path,qt_app,monkeypatch,
):
    from PySide6.QtWidgets import QMessageBox
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip

    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    existing=win.session
    invalid=tmp_path/"unpaired.bin"
    invalid.write_bytes(b"\0"*4096)
    messages=[]
    monkeypatch.setattr(QMessageBox,"critical",
                        lambda *args:messages.append(args[2]))
    win.open_archive(invalid)
    assert win.session is existing
    assert messages and "TSXML" in messages[0]
    assert win.adc.currentIndex()==0
    assert win.metrics.item(0,1).text()!="—"
    win.close()
    qt_app.processEvents()


# Stage111Z.18 — original-style primary panel plus preserved diagnostics.
def test_stage111z18_primary_spec_controls_and_research_dock(tmp_path, qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    layout=win.spec_tools.widget().layout()
    children=[layout.itemAt(i).widget() for i in range(layout.count())
              if layout.itemAt(i).widget() is not None]
    expected=[
        win.spec_envelope_button,win.spec_mode,win.spec_lines_button,
        win.spec_hscale_button,win.spec_vscale_button,
        win.spec_cursor_primary,win.spec_mean_primary,
        win.spec_copy_button,win.spec_save_button,win.spec_advanced_button,
    ]
    assert children == expected
    assert win.spec_mode.itemText(0)=="Логарифмич."
    assert [win.spec_mode.itemText(i) for i in range(1,4)] == [
        "Линейный ВУ","Линейный ВС","Линейный ВП"
    ]
    fs=win.session.samples(win._ch())[1]
    n=int(win.spec_n.currentText())
    assert win.spec_lines_button.text().endswith(" Гц/лин")
    if fs/n==.25:
        assert win.spec_lines_button.text()=="1/4 Гц/лин"
    assert len(win.spec_lines_menu.actions())==win.spec_n.count()
    assert sum(a.isChecked() for a in win.spec_lines_menu.actions())==1
    assert "СКЗ спектра" in win.spec_mean_primary.text()
    assert "Пик спектра" in win.spec_mean_primary.text()
    assert not win.spec_inspector.isVisible()
    assert win.spec_n not in children
    win.spec_advanced_button.click()
    qt_app.processEvents()
    assert win.spec_inspector.isVisible()
    assert win.spec_n.isVisible()
    assert win.spec_original_copy_compare.isVisible()
    assert win.narrow_run.isVisible()
    win.spec_advanced_button.click()
    qt_app.processEvents()
    assert not win.spec_inspector.isVisible()
    assert win.spec_copy_button.isVisible()
    win.close()


def test_stage111z18_small_window_keeps_all_spectrum_actions(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.resize(1024,704)
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    assert win.spec_tools.horizontalScrollBar().maximum()==0
    assert win.spec_tools.verticalScrollBar().maximum()==0
    assert win.spec_copy_button.isVisible()
    assert win.spec_save_button.isVisible()
    win.close()


def test_stage111z18_direct_bin_copy_csv_keep_uncalibrated_warning(
    tmp_path,qt_app,monkeypatch,
):
    from PySide6.QtWidgets import QMessageBox,QFileDialog,QApplication
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_stage111z16_direct_bin_tsxml import _make_pair
    p,sidecar,_=_make_pair(tmp_path,adc=4)
    win=MainWindow()
    win.open_archive(p)
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    assert "Калибровка НЕ подтверждена" in win.spec_mean_primary.text()
    assert "усл. ед." in win.spec_mean_primary.text()
    assert "м/с²" not in win.spec_mean_primary.text()
    clipboard=QApplication.clipboard()
    clipboard.setText("previous clipboard")
    questions=[]
    monkeypatch.setattr(QMessageBox,"question",
        lambda *args,**kwargs:(questions.append(args[2]) or QMessageBox.No))
    win.spec_copy_button.click()
    assert clipboard.text()=="previous clipboard"
    assert questions and "калибровка" in questions[0]
    monkeypatch.setattr(QMessageBox,"question",lambda *a,**kw:QMessageBox.Yes)
    win.spec_copy_button.click()
    assert clipboard.text().startswith("НЕ КАЛИБРОВАНО · условные единицы")
    assert len(clipboard.text().splitlines()[-1].split("\t"))==3
    target=tmp_path/"uncalibrated.csv"
    monkeypatch.setattr(QFileDialog,"getSaveFileName",
                        lambda *a,**kw:(str(target),"CSV (*.csv)"))
    win.spec_save_button.click()
    lines=target.read_text(encoding="utf-8").splitlines()
    assert lines[0]=="sep=|"
    assert "НЕ КАЛИБРОВАНО" in lines[1]
    assert len(lines[-1].split("|"))==3
    win.close()


def test_stage111z19_tasks_start_page_and_offline_routes(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    assert win.tabs.currentIndex()==0
    assert win.task_subpages.currentIndex()==0
    assert win.task_open_button.isEnabled()
    assert not win.task_spectrum_button.isEnabled()
    assert not win.task_signal_button.isEnabled()
    assert "не открыто" in win.task_session_summary.text()
    assert "недоступны" in win.findChild(type(win.task_session_summary),
                                          'taskDeviceOfflineNotice').text()
    win.open_archive(fixture_zip(tmp_path))
    assert win.task_spectrum_button.isEnabled()
    assert win.task_signal_button.isEnabled()
    assert win.task_metrics_button.isEnabled()
    assert "Экспорт Native R6.1" in win.task_session_summary.text()
    win.task_signal_button.click()
    assert win.tabs.currentIndex()==1
    win.tabs.setCurrentIndex(0)
    win.task_spectrum_button.click()
    assert win.tabs.currentIndex()==2
    win.tabs.setCurrentIndex(0)
    win.task_metrics_button.click()
    assert win.task_subpages.currentIndex()==1
    assert win.metrics.item(0,1).text()!="—"
    win.close()


def test_stage111z19_waveform_primary_and_advanced_are_not_mixed(
    tmp_path,qt_app,
):
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(1)
    qt_app.processEvents()
    assert win.wave_filter_button.objectName()=="bAdcEnvelopeType"
    assert win.wave_type_button.objectName()=="bAdcType"
    assert win.wave_hscale_button.objectName()=="bAdcHScale"
    assert win.wave_vscale_button.objectName()=="bAdcVScale"
    assert win.wave_filter_button.text()=="Без фильтра"
    assert win.wave_type_button.text()=="AC · без DC"
    assert win.wave_hscale_button.text()=="1 с"
    assert not win.wave_inspector.isVisible()
    assert "СКЗ сигнала" in win.wave_mean_primary.text()
    assert "GetSignal/IDR" in win.wave_hint.text()
    assert win.wave_cursor_primary.text()=="Курсор: —"
    assert win.wave_plot.listDataItems()
    win.wave_type_menu.actions()[1].trigger()
    qt_app.processEvents()
    assert win.wave_mode.currentIndex()==1
    assert win.wave_type_button.text()=="AC+DC"
    win.wave_hscale_menu.actions()[3].trigger()
    qt_app.processEvents()
    assert win.wave_seconds.value()==.1
    assert win.wave_hscale_button.text()=="0.1 с"
    win.wave_advanced_button.click()
    qt_app.processEvents()
    assert win.wave_inspector.isVisible()
    assert win.wave_start.isVisible()
    assert win.wave_envelope_load.isVisible()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    assert not win.wave_inspector.isVisible()
    assert win.spec_advanced_button.text()=="Исследование ▸"
    win.close()


def test_stage111z19_waveform_direct_bin_primary_never_claims_physical_units(
    tmp_path,qt_app,
):
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_stage111z16_direct_bin_tsxml import _make_pair
    p,_,_=_make_pair(tmp_path,adc=4)
    win=MainWindow()
    win.open_archive(p)
    win.show()
    win.tabs.setCurrentIndex(1)
    qt_app.processEvents()
    assert "усл. ед." in win.wave_mean_primary.text()
    assert "Калибровка НЕ подтверждена" in win.wave_mean_primary.text()
    assert "м/с²" not in win.wave_mean_primary.text()
    assert "АЦП 4"==win.adc.currentText()
    assert win.task_session_summary.text().find("Калибровка")>=0
    win.close()


def test_stage111z20_binary_raster_xor_matches_original_white_and_black(qt_app):
    """The Qt painter MUST use bitwise RasterOp, not Porter-Duff Xor."""
    from PySide6.QtGui import QColor,QImage,QPainter,QPen
    from mvk_compatible.desktop.xor_cursor_overlay import gdi_xor_rgb
    assert gdi_xor_rgb((255,255,255))==(255,127,255)
    assert gdi_xor_rgb((0,0,0))==(0,128,0)
    image=QImage(9,9,QImage.Format_RGB32)
    image.fill(QColor(255,255,255))
    image.setPixelColor(3,5,QColor(0,0,0))
    painter=QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing,False)
    painter.setCompositionMode(QPainter.RasterOp_SourceXorDestination)
    pen=QPen(QColor(0,128,0))
    pen.setWidth(1)
    painter.setPen(pen)
    painter.drawLine(3,1,3,7)
    painter.end()
    assert image.pixelColor(3,2).getRgb()[:3]==(255,127,255)
    assert image.pixelColor(3,5).getRgb()[:3]==(0,128,0)
    assert image.pixelColor(5,5).getRgb()[:3]==(255,255,255)


def test_stage111z20_xor_overlay_tracks_spectrum_cursor_without_fft_change(
    tmp_path,qt_app,
):
    from PySide6.QtCore import QPointF
    from mvk_compatible.desktop.main_window import MainWindow
    from mvk_compatible.desktop.xor_cursor_overlay import QtSpectrumXorCursor
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.open_archive(fixture_zip(tmp_path))
    win.show()
    win.tabs.setCurrentIndex(2)
    qt_app.processEvents()
    assert isinstance(win.spec_xor_crosshair,QtSpectrumXorCursor)
    assert win.spec_xor_crosshair.cursor is None
    fft_before=win._full_spectrum
    vb=win.spec_plot.getViewBox()
    rect=vb.sceneBoundingRect()
    assert rect.width()>10
    scene_cursor=QPointF(rect.left()+rect.width()*.3,rect.center().y())
    win._spec_at_scene_pos(scene_cursor,force=True)
    qt_app.processEvents()
    assert win._full_spectrum is fft_before
    assert win.spec_xor_crosshair.cursor is not None
    crosshair_x,crosshair_y=win.spec_xor_crosshair.cursor
    assert crosshair_x==win._spec_last_cursor["frequency_hz"]
    assert crosshair_y==float(
        win._full_spectrum["amplitude"][win._spec_last_cursor["selected_bin"]])
    win._spec_at_scene_pos(QPointF(rect.left(),rect.center().y()),force=True)
    qt_app.processEvents()
    assert win.spec_xor_crosshair.cursor is None
    assert win._spec_last_cursor is None
    win.close()
