"""Qt source Mode2 must restart status truth after a NEW actual TCP socket."""
from __future__ import annotations
import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
from .test_desktop_qt import qt_app
from .test_stage111z31di_qt_live_source_status_cells import inbound


def test_actual_qt_new_tcp_socket_resets_stage3_and_old_status_cells(qt_app):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        first=inbound(value=0x80,param=1,frames=80,raw=50000)
        first.update(source_tcp_connection_count=1,
                     source_tcp_multi_socket=False,
                     source_tcp_reconnects_after_raw=0)
        win._receive_native_live_status(first)
        qt_app.processEvents()
        assert win._source_mode2_runtime.receipt()[
            "original_stage3_system_error_condition_latched"]
        second=inbound(value=None,param=2,frames=85,raw=53000)
        second.update(source_tcp_connection_count=2,
                      source_tcp_multi_socket=True,
                      source_tcp_reconnects_after_raw=1,
                      phase="CONNECTING")
        win._receive_native_live_status(second)
        qt_app.processEvents()
        r=win._source_mode2_runtime.receipt()
        assert r["source_tcp_connection_count"]==2
        assert r["source_multi_socket_measurement"]
        assert not r["original_stage3_system_error_condition_latched"]
        assert r["mode2_phase"]=="CONNECTING"
        assert r["original_status_cells_14"]["source_status_cells_valid_count"]==0
    finally:
        if win._live_active:win._end_live_capture(False)
        win.close()
        qt_app.processEvents()


def test_qt_separate_operator_consent_for_reconnect_defaults_off(qt_app):
    from ..desktop.native_capture_dialog import NativeCaptureDialog
    dlg=NativeCaptureDialog()
    try:
        assert not dlg.source_rate_tx.isChecked()
        assert not dlg.source_auto_reconnect.isChecked()
        assert dlg.source_auto_reconnect.isEnabled()
        dlg.source_auto_reconnect.setChecked(True)
        assert dlg.source_auto_reconnect.isChecked()
        assert not dlg.source_rate_tx.isChecked()
        dlg.source_rate_tx.setChecked(True)
        dlg.source_rate_tx.setChecked(False)
        assert dlg.source_auto_reconnect.isChecked()
        assert dlg.source_auto_reconnect.isEnabled()
        dlg.source_auto_reconnect.setChecked(False)
        assert not dlg.source_auto_reconnect.isChecked()
    finally:
        dlg.close()
        dlg.deleteLater()


def test_passive_retry_never_grants_hardware_rate_permission(qt_app):
    from ..desktop.native_capture_dialog import NativeCaptureDialog
    dlg=NativeCaptureDialog()
    try:
        dlg.source_auto_reconnect.setChecked(True)
        assert dlg.source_auto_reconnect.isChecked()
        assert not dlg.source_rate_tx.isChecked()
        assert not dlg.source_rate_tx_active()
        assert "Без отдельного разрешения SetRate" in dlg.source_auto_reconnect.toolTip()
    finally:
        dlg.close()
        dlg.deleteLater()
