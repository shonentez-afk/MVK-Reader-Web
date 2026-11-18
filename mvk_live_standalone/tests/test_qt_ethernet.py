"""GUI: one discovered wired Ethernet fills source IPv4; never dials on startup."""
from concurrent.futures import Future
import os

import pytest
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")


@pytest.fixture
def gui():
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    from PySide6 import QtWidgets
    from mvk_live_standalone.app import LiveWindow
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window=LiveWindow()
    yield window,app
    window.close()
    window.deleteLater()
    app.processEvents()


def _complete(window,nic):
    future=Future()
    future.set_result(nic)
    window._ethernet_future=future
    window._collect_ethernet_discovery()


def test_single_ethernet_auto_fills_and_no_connection(gui):
    from PySide6 import QtCore
    from mvk_live_standalone.ethernet import WiredEthernet
    w,app=gui
    assert not w.local_ip.text()
    assert w.device_ip.text()==""
    _complete(w,WiredEthernet("Ethernet",12,"192.168.10.101",24))
    assert w.local_ip.text()=="192.168.10.101"
    assert "Ethernet" in w.ethernet_info.text()
    assert "автоматически" in w.ethernet_info.text()
    assert w._native.state()==QtCore.QProcess.ProcessState.NotRunning
    assert w._capture_root is None
    assert w._ethernet_detected.if_index==12


def test_no_ethernet_error_keeps_manual_entry_without_tcp(gui):
    from mvk_live_standalone.ethernet import WiredEthernet
    w,_=gui
    w.local_ip.setText("192.168.1.101")
    future=Future()
    future.set_exception(ValueError("Нет активного проводного Ethernet с IPv4"))
    w._ethernet_future=future
    w._collect_ethernet_discovery()
    assert w.local_ip.text()=="192.168.1.101"
    assert "вручную" in w.ethernet_info.text()
    assert w._capture_root is None
    assert w._ethernet_detected is None


def test_operator_input_during_discovery_is_never_overwritten(gui):
    from mvk_live_standalone.ethernet import WiredEthernet
    w,_=gui
    w.local_ip.setText("192.168.11.23")
    w.local_ip.textEdited.emit("192.168.11.23")
    assert w._ethernet_manual_override
    _complete(w,WiredEthernet("Ethernet",17,"192.168.10.101",24))
    assert w.local_ip.text()=="192.168.11.23"
    assert "Ручной адрес не изменён" in w.ethernet_info.text()


def test_operator_must_confirm_device_connection_and_correct_ip(gui,monkeypatch):
    from PySide6 import QtCore,QtWidgets
    from mvk_live_standalone.ethernet import WiredEthernet
    w,_=gui
    _complete(w,WiredEthernet("Ethernet",17,"192.168.10.101",24))
    w.device_ip.setText("192.168.10.80")
    monkeypatch.setattr(w,"_verify_native",lambda *args: "not-executed")
    seen=[]
    monkeypatch.setattr(
        QtWidgets.QMessageBox,"question",
        lambda *args,**kwargs: (
            seen.append(args) or QtWidgets.QMessageBox.StandardButton.No))
    w.start_native()
    assert len(seen)==1
    assert "Ethernet" in seen[0][2] and "192.168.10.101" in seen[0][2]
    assert w._native.state()==QtCore.QProcess.ProcessState.NotRunning
    assert w._capture_root is None
    # A manual Wi-Fi source or typo cannot silently replace the already
    # discovered sole physical Ethernet adapter.
    warnings=[]
    monkeypatch.setattr(
        QtWidgets.QMessageBox,"warning",
        lambda *args,**kwargs: warnings.append(args))
    w.local_ip.setText("10.0.0.123")
    w.start_native()
    assert len(warnings)==1 and "не совпадает" in warnings[0][2]
    assert len(seen)==1
    assert w._native.state()==QtCore.QProcess.ProcessState.NotRunning
