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
