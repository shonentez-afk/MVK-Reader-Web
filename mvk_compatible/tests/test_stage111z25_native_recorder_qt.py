"""Stage111Z.25 Windows Qt tests. Never opens a socket or starts Native EXE."""
import os
from pathlib import Path
import pytest


@pytest.fixture(scope="module")
def qt_app():
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    yield app


def test_integrated_task_opens_native_dialog_without_device(qt_app, monkeypatch):
    from mvk_compatible.desktop.main_window import MainWindow
    import mvk_compatible.desktop.native_capture_dialog as module

    def unavailable():
        raise ValueError("Сборка без приёмника")
    monkeypatch.setattr(module, "native_executable", unavailable)
    window = MainWindow()
    assert window.tabs.count() == 3
    assert window.task_capture_button.objectName() == "taskCaptureNativeR6"
    window.open_native_capture()
    dlg = window._native_dialog
    assert dlg.isVisible()
    assert not dlg.start_button.isEnabled()
    assert not dlg.stop_button.isEnabled()
    assert not dlg.is_busy()
    assert "Приёмник недоступен" in dlg.availability_label.text()
    dlg.close()
    window.close()
    qt_app.processEvents()


def test_native_adapter_parse_does_not_connect(qt_app, monkeypatch):
    from PySide6.QtCore import QProcess
    import mvk_compatible.desktop.native_capture_dialog as module
    monkeypatch.setattr(module, "native_executable", lambda: Path("synthetic-only.exe"))
    dlg = module.NativeCaptureDialog()
    dlg._mode = "interfaces"
    dlg._stdout = (
        "Активные сетевые адаптеры с IPv4:\n"
        "  1) Ethernet 3 | IPv4 10.13.42.22/24 | индекс 20 | MAC xx:yy\n"
        "  2) Wi-Fi | IPv4 192.168.0.14/24 | индекс 11 | MAC zz\n"
    )
    dlg._process_finished(0, QProcess.NormalExit)
    assert dlg.adapters.count() == 2
    assert dlg.adapters.itemData(0) == "10.13.42.22"
    assert not dlg.start_button.isEnabled()  # operator consent required
    dlg.device_ip.setText("10.13.42.84")
    dlg.confirm.setChecked(True)
    assert dlg.start_button.isEnabled()
    dlg.confirm.setChecked(False)
    assert not dlg.start_button.isEnabled()
    dlg.close()
    qt_app.processEvents()


def test_declined_operator_consent_never_starts_capture(tmp_path, qt_app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    import mvk_compatible.desktop.native_capture_dialog as module
    monkeypatch.setattr(module, "native_executable", lambda: Path("synthetic-only.exe"))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.No)
    dlg = module.NativeCaptureDialog()
    dlg.adapters.addItem("Ethernet", "10.13.42.22")
    dlg.device_ip.setText("10.13.42.84")
    dlg.output_path.setText(str(tmp_path))
    dlg.confirm.setChecked(True)
    dlg.start_capture()
    assert not dlg.is_busy()
    assert not list(tmp_path.glob("mvk_r6_session_*"))
    dlg.close()
    qt_app.processEvents()
