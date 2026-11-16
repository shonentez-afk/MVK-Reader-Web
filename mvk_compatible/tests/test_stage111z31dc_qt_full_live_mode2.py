"""Stage111Z31DC: real Qt PageStatus/PageAdc/PageSpectrum/PageFile one-run E2E.

Actual QWidget buttons and tab stack, synthetic Native status/preview;
never opens TCP and never tests undocumented device commands.
"""
from __future__ import annotations

import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from .test_desktop_qt import qt_app
from .test_stage111z26b_live_preview import make_preview, now
from ..core.native_r6_live_preview import load_live_preview
from ..core.original_runtime_tabs import ORIGINAL_LIVE_VISIBLE


class _LocalStop:
    _mode = "capture"

    def __init__(self):
        self.calls = 0

    def stop_capture(self):
        self.calls += 1
        return True

    def is_busy(self):
        return False


def test_real_qt_all_four_live_pages_share_one_source_core_and_no_device_write(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        assert win.enter_measurement_mode()
        qt_app.processEvents()
        before=win.original_shell.file_page.property(
            "sourceOriginalMode2RuntimeReceipt")
        assert before["mode2_phase"]=="MODE2_BEFORE_TCP"
        assert win.original_visual_skin.snapshot()["visible_source_tabs"]==list(
            ORIGINAL_LIVE_VISIBLE)
        assert win.original_shell.file_channels.count()==10
        assert win.original_shell.file_spec.count()==43
        assert win.original_shell.file_values.count()==73
        assert not before["native_capture_started"]
        assert not win.original_measure_controls.buttons["bWriteAdc"].isEnabled()
        win._begin_live_capture()
        assert win._source_mode2_runtime.receipt()["mode2_phase"]=="CONNECTING"
        win._invalidate_native_live_status("Нет текущего подтверждённого состояния")
        assert win._source_mode2_runtime.receipt()["mode2_phase"]=="CONNECTING"
        assert win._source_mode2_runtime.receipt()[
            "original_faults"]["event_count"]==0
        root,st,_=make_preview(tmp_path)
        preview=load_live_preview(root,st,now=now())
        assert preview is not None
        win._receive_native_live_status(st)
        qt_app.processEvents()
        panel=win.original_measure_controls
        ready=panel.panel.property("sourceOriginalMode2RuntimeReceipt")
        assert ready["mode2_phase"]=="RECORDING"
        assert ready["native_run_bound"]
        assert ready["original_queue"]["current_internal_rate_code"]==65536
        assert ready["original_queue"]["pending_count"]==1
        assert ready["original_queue"]["device_commands_sent"]==0
        for page in (win.original_shell.status_page,win.original_shell.file_page):
            receipt=page.property("sourceOriginalMode2RuntimeReceipt")
            assert receipt==ready
        assert win.original_shell.status_page.property(
            "sourceNativeTransportConnected")
        win._receive_live_preview(preview)
        assert len(win.wave_plot.listDataItems())==1
        assert len(win.spec_plot.listDataItems())==1
        assert win.session is None

        # A bad ongoing transport immediately clears both LIVE ADC/Spectrum
        # without reopening a stale archive or inventing device DSP fields.
        bad=st|{"seconds_since_last_packet":5.1}
        win._receive_native_live_status(bad)
        qt_app.processEvents()
        assert not win.wave_plot.listDataItems()
        assert not win.spec_plot.listDataItems()
        assert win._source_mode2_runtime.receipt()["mode2_phase"]=="SILENT"
        assert not win.measurement_connection_display().transport_verified
        win._receive_live_preview(preview)
        assert not win.wave_plot.listDataItems()

        # A new validated status may refresh *read-only* transport without
        # re-arming an old hardware or source write command.
        win._receive_native_live_status(st)
        win._receive_live_preview(preview)
        assert len(win.wave_plot.listDataItems())==1
        assert win._source_mode2_runtime.receipt()["mode2_phase"]=="RECORDING"
        owner=_LocalStop()
        win._native_dialog=owner
        assert win.request_measurement_stop()
        assert win._source_mode2_runtime.receipt()["mode2_phase"]=="STOPPING"
        assert not panel.freeze.isEnabled()
        assert not panel.buttons["bWriteAdc"].isEnabled()
        assert not panel.buttons["bWriteValues"].isEnabled()
        assert not win.measurement_connection_display().transport_verified
        win._receive_native_live_status(st)
        win._receive_live_preview(preview)
        assert not win.wave_plot.listDataItems()
        assert not win.spec_plot.listDataItems()
        assert owner.calls==1
        win._end_live_capture(False)
        assert not win._measurement_mode_selected
        assert win.session is None
        done=win._source_mode2_runtime.receipt()
        assert done["mode2_phase"]=="IDLE"
        assert done["last_events"][-2][1]=="NATIVE_COMPLETE"
        assert done["last_events"][-2][2]=="STOPPED_WITHOUT_ARCHIVE"
        assert done["last_events"][-1][1]=="MEASURE_OFF_AFTER_NATIVE"
        assert win.original_visual_skin.snapshot()["visible_source_tabs"]==[
            "PageStart"]
    finally:
        win._native_dialog=None
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()


def test_real_qt_failed_source_status_keeps_exception_provenance_separate(
        qt_app):
    from ..desktop.main_window import MainWindow
    from .test_stage111z31cr_connected_core import source_test_transport
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        win._receive_native_live_status(source_test_transport(frames=100))
        win._invalidate_native_live_status("Live status source rejected")
        out=win.original_shell.status_page.property(
            "sourceOriginalMode2RuntimeReceipt")
        assert out["mode2_phase"]=="STATUS_REJECTED"
        faults=out["original_faults"]["events"]
        assert faults and faults[-1]["kind"]=="STATUS_REJECTED"
        assert faults[-1]["matched_to_delphi_exception"] is False
        assert not win.original_shell.status_page.property(
            "sourceNativeTransportConnected")
        win._end_live_capture(False)
        assert win.original_shell.file_page.property(
            "sourceOriginalMode2RuntimeReceipt")["mode2_phase"]==(
                "STOPPED_WITHOUT_ARCHIVE")
    finally:
        win.close()
        qt_app.processEvents()


def test_mode2_failed_reconnect_uses_fresh_queue_and_parks_valid_archive(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    from .test_offline_core import fixture_zip
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        prior=fixture_zip(tmp_path)
        win.open_archive(prior)
        old=win.session
        assert old is not None
        assert win.enter_measurement_mode()
        win._begin_live_capture()
        first_trace=win._source_mode2_runtime
        win._end_live_capture(False)
        assert win._measurement_mode_selected
        assert first_trace.finished
        assert win.session is not None
        assert win.session.serial==old.serial
        # A second approved attempt while Mode2 remains on screen must
        # never reuse first run's source command queue or 10-channel
        # recording windows. The accepted old ZIP must remain recoverable.
        win._begin_live_capture()
        assert win._source_mode2_runtime is not first_trace
        assert not win._source_mode2_runtime.finished
        assert win._source_mode2_runtime.receipt()["mode2_phase"]=="CONNECTING"
        assert win._source_mode2_runtime.command_model.receipt()[
            "pending_count"]==1
        assert win._live_prior_session is not None
        assert win._live_prior_session.serial==old.serial
        win._end_live_capture(False)
        assert win.session is not None
        assert win.session.serial==old.serial
        assert win.leave_measurement_mode()
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()


def test_original_write_export_completion_status_is_real_string_not_call(qt_app):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    try:
        win._source_write_export_ready({
            "files_written":2, "windows":1,
            "verified_frame_boundaries":True})
        text=win.statusBar().currentMessage()
        assert "2 файлов" in text
        assert "Go подтвердил границы кадров" in text
        win._source_write_export_ready({
            "files_written":1, "windows":1,
            "verified_frame_boundaries":False})
        assert "Границы по периодическому статусу" in (
            win.statusBar().currentMessage())
    finally:
        win.close()
        qt_app.processEvents()
