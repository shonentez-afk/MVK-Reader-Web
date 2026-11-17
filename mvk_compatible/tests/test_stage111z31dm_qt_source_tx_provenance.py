"""No extra engineering screen: native pnMeasure and PageStatus share Core RX."""
from __future__ import annotations
import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
from .test_desktop_qt import qt_app
from .test_stage111z31dm_original_tx_evidence_core import snapshot


def test_real_qt_original_measure_panels_report_candidate_without_sending(qt_app):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        win._receive_native_live_status(snapshot())
        qt_app.processEvents()
        receipt=win._source_mode2_runtime.receipt()["source_mode2_tx_evidence"]
        assert receipt["source_setrate_dispatch_candidate"]
        assert receipt["source_go_bytes_actually_sent"]==0
        assert not receipt["original_delphi_command_physically_observed"]
        for widget in (win.original_measure_controls.panel,
                       win.original_shell.status_page,
                       win.original_shell.file_page):
            assert widget.property("sourceOriginalOutboundEvidence")==receipt
        assert "0 байт" in win.original_measure_controls.status.toolTip()
        assert win._source_mode2_runtime.receipt()["hardware_commands_sent"]==0
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()
