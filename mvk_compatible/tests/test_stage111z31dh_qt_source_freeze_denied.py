"""Native Windows Qt: real bFreezeUpdate + denied reply, source Core same.

Entirely synthetic; no QProcess, no equipment or network connection.
"""
from __future__ import annotations

import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from .test_desktop_qt import qt_app
from .test_stage111z31cz_source_write_stages_core import source_status, RUN
from ..core.original_mode2_rx_evidence import FIELDS


def with_inbound(base,*,params=1,acks=0,denied=0):
    return base | dict(zip(FIELDS,(params,acks,denied)))


def test_real_bfreezeupdate_click_tracks_offline_source_processing_gate(
        qt_app):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        controls=win.original_measure_controls
        trace=win._source_mode2_runtime
        assert controls.freeze.isEnabled()
        assert not trace.receipt()["source_preview_freeze_requested"]
        assert not trace.receipt()[
            "source_source_processing_freeze_gate_offline"]["freeze_update"]
        assert not trace.receipt()["actual_tmkvthread_freeze_updated"]

        controls.freeze.click()
        qt_app.processEvents()
        assert controls.state.frozen
        assert win._source_live_view_frozen
        first=trace.receipt()
        assert first["source_preview_freeze_requested"]
        assert first["source_source_processing_freeze_gate_offline"][
            "freeze_update"]
        assert first["native_go_raw_capture_continues_during_preview_freeze"]
        assert not first["actual_tmkvthread_freeze_updated"]
        assert win.original_shell.measure_controls.panel.property(
            "sourceOriginalMode2RuntimeReceipt")[
                "source_preview_freeze_requested"]
        assert "Продолжить" in controls.freeze.text()

        controls.freeze.click()
        qt_app.processEvents()
        assert not controls.state.frozen
        assert not win._source_live_view_frozen
        assert not trace.receipt()["source_preview_freeze_requested"]
        assert not trace.receipt()[
            "source_source_processing_freeze_gate_offline"]["freeze_update"]
        assert not trace.receipt()["actual_tmkvthread_freeze_updated"]
        assert trace.receipt()["hardware_commands_sent"]==0
        win._end_live_capture(False)
        assert not controls.freeze.isEnabled()
        assert not win._source_interface_qtimer.isActive()
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()


def test_received_denial_rejects_active_source_recording_not_only_red_icon(
        qt_app):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        healthy=with_inbound(source_status(
            session=RUN,adc_samples=512,aux=1,frames=70,raw=50000))
        win._receive_native_live_status(healthy)
        qt_app.processEvents()
        assert win._source_live_writer.trustworthy
        assert win.measurement_connection_display().indicator=="good"
        # Sensor returns an actual on-wire DENIED packet. The passive Go
        # program has not sent SetRate; it must not attribute this reply.
        denied=with_inbound(source_status(
            session=RUN,adc_samples=512,aux=1,frames=72,raw=51000),
            acks=1,denied=1)
        win._receive_native_live_status(denied)
        qt_app.processEvents()
        assert not win._source_live_writer.trustworthy
        assert win.measurement_connection_display().indicator=="bad"
        assert "отказ операции" in win.original_measure_controls.status.text()
        assert win.original_measure_controls.bad_indicator.isVisible()
        assert not win.original_measure_controls.buttons[
            "bWriteAdc"].isEnabled()
        proof=win.original_shell.status_page.property(
            "sourceOriginalReceivedProtocolEvidence")
        assert proof["denial_seen"]
        assert proof["native_received_ack_unattributed"]==1
        assert not proof["original_setrate_command_ack_verified"]
        assert win._source_mode2_runtime.receipt()["hardware_commands_sent"]==0
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()
