"""Windows PySide6 offscreen smoke test. No network/device, no sample export."""
import os
import pytest


def test_desktop_three_tabs_without_server():
    pytest.importorskip('PySide6')
    pytest.importorskip('pyqtgraph')
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication
    from mvk_compatible.desktop.main_window import MainWindow
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    assert window.tabs.count()==3
    assert [window.tabs.tabText(i) for i in range(3)]==[
        'Расчётные данные','Временной сигнал','Спектр']
    assert window.session is None
    assert not window.tabs.isEnabled()
    assert window.adc.count()==8
    assert window.spec_mode.count()==4
    assert window.spec_backend.count()==2
    assert window.wave_order.count()==2
    assert window.wave_mode.itemText(0).startswith('AC ·')
    window.close()
    app.processEvents()

def test_qt_reads_synthetic_dsp_bin_fft_without_server(tmp_path):
    pytest.importorskip('PySide6')
    pytest.importorskip('pyqtgraph')
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    app=QApplication.instance() or QApplication([])
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
