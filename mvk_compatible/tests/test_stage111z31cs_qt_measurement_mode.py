"""Source Mode2 acceptance on REAL Qt widgets, no physical TCP call."""
from __future__ import annotations

import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from .test_desktop_qt import qt_app
from .test_stage111z31cc_qt_graph_layout_cursor import settle
from .test_stage111z31cr_connected_core import source_test_transport
from ..core.original_runtime_tabs import ORIGINAL_LIVE_VISIBLE
from ..core.original_connected_status import UNKNOWN
from ..desktop.main_window import MainWindow


def test_actual_original_measure_button_enters_five_tabs_before_tcp(
        qt_app,monkeypatch):
    win=MainWindow()
    win.resize(1260,755)
    win.show()
    settle(qt_app)
    try:
        called=[]
        def consent_only():
            called.append((win.original_root_tabs.currentIndex(),
                           win.original_visual_skin.snapshot()["visible_source_tabs"],
                           win.original_measure_controls.status.text(),
                           win._live_active))
        monkeypatch.setattr(win,"open_native_capture",consent_only)
        start=win.original_start_controller
        button=start.buttons["bTaskConnect"]
        assert not win._measurement_mode_selected
        assert win.original_visual_skin.snapshot()[
            "visible_source_tabs"]==["PageStart"]
        assert not win.original_measure_controls.panel.isVisible()
        QTest.mouseClick(button,Qt.LeftButton)
        settle(qt_app)
        assert called==[(2,list(ORIGINAL_LIVE_VISIBLE),
                         "Ожидание подключения к прибору",False)]
        assert win._measurement_mode_selected
        assert win._native_live_status is None
        assert win.session is None
        panel=win.original_measure_controls
        assert panel.panel.isVisible()
        assert panel.status.text()=="Ожидание подключения к прибору"
        assert panel.indicator.text()=="○"
        assert not panel.bad_indicator.isVisible()
        assert not panel.freeze.isEnabled()
        assert not panel.rate.isEnabled()
        assert not panel.buttons["bWriteTable"].isEnabled()
        assert not panel.buttons["bWriteAdc"].isEnabled()
        assert not panel.buttons["bWriteValues"].isEnabled()
        assert win.original_root_tabs.isTabEnabled(3)
        assert win.original_root_tabs.isTabEnabled(4)
        assert win.original_shell.status_table.rowCount()==15
        assert win.original_shell.status_table.item(0,1).text()==UNKNOWN
        assert not win.original_shell.status_page.property(
            "sourceNativeTransportConnected")
        # Exactly the original second Mode2 click hides extra tabs, but
        # NEVER terminates a Go recorder without its stop protocol.
        win.original_visual_skin.reveal_page(0)
        settle(qt_app)
        QTest.mouseClick(button,Qt.LeftButton)
        settle(qt_app)
        assert len(called)==1
        assert not win._measurement_mode_selected
        assert win.original_visual_skin.snapshot()[
            "visible_source_tabs"]==["PageStart"]
        assert not panel.panel.isVisible()
        assert win.measurement_connection_display().phase=="IDLE"
        assert not start.workspace.report()["device_io_performed"]
    finally:
        win.close()
        settle(qt_app)


def test_actual_qt_status_waiting_connected_refused_and_failed_source_mode(
        qt_app):
    win=MainWindow()
    win.show()
    settle(qt_app)
    try:
        assert win.enter_measurement_mode()
        assert win._measurement_mode_selected and not win._live_active
        assert win.original_measure_controls.panel.isVisible()
        # Go captureStarted is simulated, no socket or real process.
        win._begin_live_capture()
        settle(qt_app)
        assert win._live_active
        assert win.original_measure_controls.status.text()==(
            "Ожидание данных прибора")
        win._receive_native_live_status(
            source_test_transport(frames=100))
        settle(qt_app)
        panel=win.original_measure_controls
        assert panel.status.text()=="Подключен к прибору"
        assert panel.indicator.isVisible()
        assert not panel.bad_indicator.isVisible()
        assert win.original_shell.status_page.property(
            "sourceNativeTransportConnected")
        win._receive_native_live_status(
            source_test_transport(phase="REFUSED"))
        settle(qt_app)
        assert panel.status.text()=="Ошибка соединения с прибором"
        assert panel.bad_indicator.isVisible()
        assert not panel.indicator.isVisible()
        win._end_live_capture(False)
        settle(qt_app)
        assert win._measurement_mode_selected
        assert not win._live_active
        assert panel.panel.isVisible()
        assert panel.bad_indicator.isVisible()
        assert win.original_visual_skin.snapshot()[
            "visible_source_tabs"]==list(ORIGINAL_LIVE_VISIBLE)
        assert win.leave_measurement_mode()
        settle(qt_app)
        assert win.original_visual_skin.snapshot()[
            "visible_source_tabs"]==["PageStart"]
        assert not panel.panel.isVisible()
        assert not win.measurement_connection_display().transport_verified
    finally:
        win.close()
        settle(qt_app)
