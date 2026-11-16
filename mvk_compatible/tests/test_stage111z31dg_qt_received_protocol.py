"""Real Qt pnMeasure/PageStatus/PageFile with passive received MVK replies.

No socket or instrument. Native Go status evidence is synthetic and has
the same three counters as Stage111Z31DG Go monitor sidecar.
"""
from __future__ import annotations

import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from .test_desktop_qt import qt_app
from .test_stage111z31cz_source_write_stages_core import source_status, RUN
from ..core.original_mode2_rx_evidence import FIELDS


def with_receipt(status: dict, *, params=0, acks=0, denied=0) -> dict:
    return status | dict(zip(FIELDS,(params,acks,denied)))


def test_actual_source_live_tabs_show_receipts_and_received_denial_warning(
        qt_app):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        before=win.original_shell.status_page.property(
            "sourceOriginalReceivedProtocolEvidence")
        assert not before["native_protocol_evidence_available"]
        status=with_receipt(source_status(
            session=RUN,adc_samples=512,frames=60,raw=27000),
            params=1)
        win._receive_native_live_status(status)
        qt_app.processEvents()
        source=win.original_shell.status_page.property(
            "sourceOriginalReceivedProtocolEvidence")
        assert source["native_protocol_evidence_available"]
        assert source["original_source_stage_candidate_from_rx"]==1
        assert source["native_receive_register_frames_with_blocks"]==1
        assert not source["original_source_stage_is_actually_running"]
        assert win.original_shell.file_page.property(
            "sourceOriginalReceivedProtocolEvidence")==source
        assert win.original_measure_controls.panel.property(
            "sourceOriginalReceivedProtocolEvidence")==source
        assert win._source_mode2_runtime.command_model.pending[0].data==65536
        assert win.original_measure_controls.status.text()=="Подключен к прибору"

        with_denial=with_receipt(source_status(
            session=RUN,adc_samples=512,frames=62,raw=28000),
            params=1,acks=1,denied=1)
        win._receive_native_live_status(with_denial)
        qt_app.processEvents()
        source=win.original_shell.status_page.property(
            "sourceOriginalReceivedProtocolEvidence")
        assert source["native_received_ack_unattributed"]==1
        assert source["native_received_denied_unattributed"]==1
        assert source["denial_seen"]
        assert source["new_denial_observed_this_snapshot"]
        assert not source["original_setrate_command_ack_verified"]
        assert "отказ операции" in win.original_measure_controls.status.text()
        assert "команд не отправлял" in win.original_measure_controls.status.text()
        assert win.original_measure_controls.bad_indicator.isVisible()
        assert win._source_mode2_runtime.receipt()["hardware_commands_sent"]==0

        # Duplicated valid Go file cannot generate a second denial.
        win._receive_native_live_status(with_denial)
        again=win.original_shell.status_page.property(
            "sourceOriginalReceivedProtocolEvidence")
        assert again["denial_seen"]
        assert not again["new_denial_observed_this_snapshot"]
        assert not win.session
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()


def test_partial_source_rx_sidecar_cannot_turn_on_green_status(qt_app):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        bad=with_receipt(source_status(session=RUN,frames=10,raw=4200),
                         params=1)
        del bad[FIELDS[2]]
        win._receive_native_live_status(bad)
        assert win._native_live_status is None
        assert not win.measurement_connection_display().transport_verified
        assert not win.original_measure_controls.bad_indicator.isHidden()
        assert win._source_mode2_runtime.receipt()["hardware_commands_sent"]==0
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()
