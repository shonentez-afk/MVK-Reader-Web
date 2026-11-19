"""Real PageStatus, pnMeasure and source rate menu with approved TX receipt."""
from __future__ import annotations
import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
from .test_desktop_qt import qt_app
from .test_stage111z31dt_original_real_tx_core import approved_source_tx


def test_qt_actual_transmit_receipt_and_original_rate_menu(qt_app,monkeypatch):
    from ..desktop.main_window import MainWindow
    from ..desktop.native_capture_dialog import NativeCaptureDialog
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        win._receive_native_live_status(approved_source_tx())
        qt_app.processEvents()
        receipt=win._source_mode2_runtime.receipt()
        assert receipt["hardware_commands_sent"]==1
        assert receipt["source_initial_device_setrate_sent"]
        panel=win.original_measure_controls
        assert "36 байт" in panel.status.toolTip()
        assert panel.rate_menu.actions()
        assert not any(action.isEnabled() for action in panel.rate_menu.actions())
        # bTaskConnectClick chooses original Task2, which queues
        # SetRate(65536) before the first TCP socket. This visible
        # original MODE2 preflight therefore defaults to active TX.
        # It is NOT consent to run physical commands yet: the Ethernet
        # grant starts unchecked, and the native process is not running.
        dlg=NativeCaptureDialog(win)
        assert dlg.source_rate_tx.isChecked()
        assert not dlg.confirm.isChecked()
        assert not dlg.start_button.isEnabled()
        assert not dlg.source_rate_tx_active()
        try:
            monkeypatch.setattr(dlg,"source_rate_tx_active",lambda:True)
            win._native_dialog=dlg
            called=[]
            monkeypatch.setattr(win,"source_rate_selected",lambda rate:called.append(rate))
            panel.render()
            actions=panel.rate_menu.actions()
            assert len(actions)==5
            assert all(action.isEnabled() for action in actions)
            actions[1].trigger()
            assert called==[32768]
        finally:
            win._native_dialog=None
            dlg.close()
            dlg.deleteLater()
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()
