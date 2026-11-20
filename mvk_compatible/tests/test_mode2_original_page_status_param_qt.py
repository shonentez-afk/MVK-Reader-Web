"""The REAL Qt PageStatus 15 modes read accepted source PARAM registers.

Only local synthetic frames; never a hardware connection. Existing original
mode0/15 system register projection remains independent and unchanged.
"""
from __future__ import annotations

import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from .test_desktop_qt import qt_app
from .test_stage111z26_native_live_status import now
from .test_mode2_original_page_status_param_banks import live_state
from ..core.native_r6_live_status import validate_live_status


def test_qt_mode2_source_live_four_grid_modes_and_stale_stop_gate(qt_app):
    from ..desktop.main_window import MainWindow
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        assert w.enter_measurement_mode()
        w._begin_live_capture()
        source=live_state()
        status=validate_live_status(source,
            expected_run=source["session_id"],now=now())
        w._receive_native_live_status(status)
        qt_app.processEvents()
        assert w.original_shell.status_tabs.count()==15
        assert w.original_shell.status_page.property(
            "sourceNativeTransportConnected")
        for index,expected_grid,expected_rows in (
            (1,"tabAlarmResult",24),
            (2,"tabAllResult",24),(3,"tabAllResult",24),
            (4,"tabAllResult",24),(5,"tabResult",43),
            (6,"tabResult",43),(7,"tabResult",43),
            (8,"tabResult",43),(9,"tabResult",43),
            (10,"tabResult",43),(11,"tabResult",43),
            (12,"tabResult",43),(13,"tabResult",6),
            (14,"tabResult",6)):
            w.original_status_mode.setCurrentIndex(index)
            w.original_shell.refresh_status()
            grid=w.original_shell.status_table
            assert grid.objectName()==expected_grid
            assert grid.rowCount()==expected_rows
            receipt=w.original_shell.status_page.property(
                "sourceLivePageStatusParamEvidence")
            assert receipt is not None and receipt["mode"]==index
        w.original_status_mode.setCurrentIndex(1)
        w.original_shell.refresh_status()
        assert w.original_shell.status_table.item(0,1).text()=="4,5"
        # +0x132: state = low 8 bits, alert = bits 8..15.
        assert w.original_shell.status_table.item(1,1).text()==(
            "Красная зона (квитировано) (Устар. ПО)")
        assert w.original_shell.status_table.item(2,1).text()=="---"
        w.original_status_mode.setCurrentIndex(2)
        w.original_shell.refresh_status()
        assert w.original_shell.status_table.item(0,1).text()=="1,5"
        w.original_status_mode.setCurrentIndex(5)
        w.original_shell.refresh_status()
        assert w.original_shell.status_plot.isVisible()
        assert w._source_mode2_runtime.receipt()["hardware_commands_sent"]==0
        # A physical input error or stopped session must not keep the
        # previous positive 43-band chart on a different run.
        bad=dict(status)
        bad["seconds_since_last_packet"]=5.1
        bad["quality_alert"]=True
        w._receive_native_live_status(bad)
        w.original_shell.refresh_status()
        assert not w.original_shell.status_plot.isVisible()
        assert w.original_shell.status_table.item(0,1).text()=="—"
        w._end_live_capture(False)
        assert w.original_shell.status_page.property(
            "sourceLivePageStatusParamEvidence") is None
    finally:
        if w._live_active:
            w._end_live_capture(False)
        w.close()
        qt_app.processEvents()
