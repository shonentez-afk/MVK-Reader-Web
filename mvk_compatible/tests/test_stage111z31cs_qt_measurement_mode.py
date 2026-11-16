"""Source Mode2 acceptance on REAL Qt widgets, no physical TCP call."""
from __future__ import annotations

import json
import os
from pathlib import Path

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


def _capture_source_mode2(win,phase):
    """Normal operator Qt screenshot; synthetic, NO original or device bytes."""
    root=os.environ.get("MVK_SOURCE_OPERATOR_QA_DIR")
    if not root:
        return
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    image=win.grab()
    assert image.save(str(root/(phase+".png")),"PNG")
    status=win.measurement_connection_display()
    payload={
        "source":"STAGE111Z31CS_IDR_MODE2_BEFORE_TCP",
        "phase":phase,
        "source_mode2_selected":status.selected,
        "native_go_started":status.capture_started,
        "validated_transport":status.transport_verified,
        "connection_indicator":status.indicator,
        "connection_phase":status.phase,
        "original_user_screenshot_embedded":False,
        "device_commands_sent":False,
        "native_window_physical_px":[image.width(),image.height()],
        "device_pixel_ratio":win.devicePixelRatioF(),
        "visible_source_tabs":win.original_visual_skin.snapshot()[
            "visible_source_tabs"],
    }
    (root/(phase+".json")).write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8")


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
        _capture_source_mode2(win,"13_cs_measure_pressed_without_tcp")
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
        _capture_source_mode2(win,"14_cs_instrument_connection_refused")
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


def test_original_second_mode2_click_graceful_native_stop_no_device_tcp(
        qt_app):
    win=MainWindow()
    win.show()
    settle(qt_app)
    class FakeGo:
        _mode="capture"
        count=0
        def stop_capture(self):
            self.count+=1
            return True
    fake=FakeGo()
    try:
        win.enter_measurement_mode()
        win._begin_live_capture()
        win._native_dialog=fake
        win.original_visual_skin.reveal_page(0)
        settle(qt_app)
        QTest.mouseClick(
            win.original_start_controller.buttons["bTaskConnect"],
            Qt.LeftButton)
        settle(qt_app)
        assert fake.count==1
        assert win._measurement_exit_requested
        assert win._live_active and win._measurement_mode_selected
        assert win.original_visual_skin.snapshot()[
            "visible_source_tabs"]==list(ORIGINAL_LIVE_VISIBLE)
        # Repeated clicks cannot send another asynchronous stop.
        QTest.mouseClick(
            win.original_start_controller.buttons["bTaskConnect"],
            Qt.LeftButton)
        assert fake.count==1
        win._end_live_capture(False)
        settle(qt_app)
        assert not win._live_active
        assert not win._measurement_mode_selected
        assert not win._measurement_exit_requested
        assert win.original_visual_skin.snapshot()[
            "visible_source_tabs"]==["PageStart"]
        assert not win.original_measure_controls.panel.isVisible()
    finally:
        win._native_dialog=None
        win.close()
        settle(qt_app)


def test_mode2_parked_verified_zip_is_not_live_and_restores_on_failure(
        tmp_path,qt_app):
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.show()
    settle(qt_app)
    try:
        archive=fixture_zip(tmp_path)
        win.open_archive(archive)
        assert win.session is not None
        serial=win.session.serial
        assert win._live_prior_session is None
        assert win.enter_measurement_mode()
        settle(qt_app)
        # The archive is retained for recovery ONLY. It must not appear
        # as new instrument DSP/TACH, even before Native capture starts.
        assert win._live_prior_session is not None
        assert win._live_prior_session.serial==serial
        assert win.session is None
        assert win._offline_flow is None
        assert "нет проверенных регистров нового сеанса" in (
            win.dsp_tach_status.text())
        assert win.original_status_table.item(0,1).text()==UNKNOWN
        assert win.original_measure_controls.status.text()==(
            "Ожидание подключения к прибору")
        assert not win.original_shell.status_page.property(
            "sourceNativeTransportConnected")
        win._begin_live_capture()
        assert win._live_prior_session is not None
        assert win.session is None
        win._end_live_capture(False)
        settle(qt_app)
        # Failure keeps five Mode2 tabs and a RED indicator, but the
        # previous verified archive is reopened by the offline Core.
        assert win._measurement_mode_selected
        assert win.session is not None and win.session.serial==serial
        assert win.original_measure_controls.status.text()==(
            "Ошибка соединения с прибором")
        assert win.original_visual_skin.snapshot()[
            "visible_source_tabs"]==list(ORIGINAL_LIVE_VISIBLE)
        assert win._live_prior_session is None
        assert win.leave_measurement_mode()
        settle(qt_app)
        assert win.original_visual_skin.snapshot()[
            "visible_source_tabs"]==["PageStart","PageAdc","PageSpectrum"]
    finally:
        win.close()
        settle(qt_app)


def test_mode2_second_click_before_tcp_restores_previous_verified_archive(
        tmp_path,qt_app):
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.show()
    settle(qt_app)
    try:
        archive=fixture_zip(tmp_path)
        win.open_archive(archive)
        serial=win.session.serial
        assert win.enter_measurement_mode()
        assert win.session is None
        assert win.leave_measurement_mode()
        settle(qt_app)
        assert win.session is not None and win.session.serial==serial
        assert win._live_prior_session is None
        assert win.measurement_connection_display().phase=="IDLE"
        assert win.original_visual_skin.snapshot()[
            "visible_source_tabs"]==["PageStart","PageAdc","PageSpectrum"]
    finally:
        win.close()
        settle(qt_app)
