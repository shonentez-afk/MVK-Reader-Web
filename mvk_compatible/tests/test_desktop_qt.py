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
    window.adc.setCurrentIndex(6)
    app.processEvents()
    assert 'ALERT' in window.calc_status.text()
    window.close()
    app.processEvents()
