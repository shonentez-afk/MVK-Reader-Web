"""Source Mode2 default active original Task2, explicit real-operator grant.

Only synthetic Qt preflight state. No socket, physical instrument,
native process, private Pascal/IDP/SQLite or firmware actions.
"""
from pathlib import Path

from .test_stage111z25_native_recorder_qt import qt_app


def test_original_measure_preselects_source_setrate_but_cannot_connect(
        qt_app,monkeypatch):
    from PySide6.QtWidgets import QWidget
    import mvk_compatible.desktop.native_capture_dialog as module
    monkeypatch.setattr(module,"native_executable",
                        lambda:Path("synthetic-no-device.exe"))
    parent=QWidget()
    parent._measurement_mode_selected=True
    dlg=module.NativeCaptureDialog(parent)
    try:
        assert dlg._original_mode2_auto_setrate is True
        assert dlg.source_rate_tx.isChecked()
        assert not dlg.confirm.isChecked()  # separate real physical approval
        assert not dlg.start_button.isEnabled()
        assert not dlg.source_rate_tx_active()
        assert "SetRate" in dlg.source_rate_tx.text()
    finally:
        dlg.close()
        parent.close()
        qt_app.processEvents()


def test_native_standalone_keeps_passive_opt_in_without_source_mode(
        qt_app,monkeypatch):
    import mvk_compatible.desktop.native_capture_dialog as module
    monkeypatch.setattr(module,"native_executable",
                        lambda:Path("synthetic-no-device.exe"))
    dlg=module.NativeCaptureDialog()
    try:
        assert dlg._original_mode2_auto_setrate is False
        assert dlg.source_rate_tx.isChecked() is False
        assert not dlg.confirm.isChecked()
        assert not dlg.start_button.isEnabled()
        assert not dlg.source_rate_tx_active()
    finally:
        dlg.close()
        qt_app.processEvents()


def test_active_capture_cannot_misrepresent_its_source_tx_permission(
        qt_app,monkeypatch):
    import mvk_compatible.desktop.native_capture_dialog as module
    monkeypatch.setattr(module,"native_executable",
                        lambda:Path("synthetic-no-device.exe"))
    dlg=module.NativeCaptureDialog()
    try:
        dlg.source_rate_tx.setChecked(True)
        dlg._mode="capture"
        dlg._sync_buttons()
        assert dlg.source_rate_tx.isChecked()
        assert not dlg.source_rate_tx.isEnabled()
        assert not dlg.source_auto_reconnect.isEnabled()
        dlg._mode=None
        dlg._sync_buttons()
        assert dlg.source_rate_tx.isEnabled()
        assert dlg.source_auto_reconnect.isEnabled()
        assert not dlg.confirm.isChecked()
    finally:
        dlg.close()
        qt_app.processEvents()
