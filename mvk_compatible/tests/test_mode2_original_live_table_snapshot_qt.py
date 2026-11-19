"""Real original pnMeasure bWriteTable Qt action during LIVE Mode2.

The original 0084E020 is one-shot and distinct from 0084E988
WriteValues. Selected 10-channel flags are shared with PageFile.
"""
from __future__ import annotations

from types import SimpleNamespace
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from .test_desktop_qt import qt_app
from .test_stage111z26_native_live_status import now
from .test_mode2_original_page_status_param_banks import live_state
from ..core.native_r6_live_status import validate_live_status
from ..desktop import original_measure_controls_ui as measure_ui


def test_live_bwrite_table_one_shot_without_writevalues_device_tx(
    qt_app,tmp_path,monkeypatch
):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        assert win.enter_measurement_mode()
        controls=win.original_shell.measure_controls
        assert not controls.buttons["bWriteTable"].isEnabled()
        win._begin_live_capture()
        raw=live_state()
        accepted=validate_live_status(raw,
            expected_run=raw["session_id"],now=now())
        win._receive_native_live_status(accepted)
        controls.render()
        assert controls.buttons["bWriteTable"].isEnabled()
        assert controls.buttons["bWriteTable"].property(
            "sourceOriginalLiveTableSnapshotReady") is True
        dest=tmp_path/"TABLE-2026-11-19--17-10-20.csv"
        monkeypatch.setattr(
            measure_ui,"QFileDialog",
            SimpleNamespace(getSaveFileName=lambda *args:(str(dest),"CSV (*.csv)")))
        writer=win._source_live_writer.receipt()
        before=writer["write_values_requested"]
        controls.buttons["bWriteTable"].click()
        assert dest.is_file()
        assert dest.read_bytes().startswith(b"\xef\xbb\xbfsep=|\r\n")
        receipt=controls.panel.property("sourceOriginalLiveTableSnapshotReceipt")
        assert receipt is not None
        assert receipt["source_table_row_count"]==73
        assert receipt["source_table_selected_channels"]==list(range(1,9))
        assert receipt["instrument_commands_sent"] is False
        assert win._source_live_writer.receipt()["write_values_requested"]==before
        assert win._source_mode2_runtime.receipt()["hardware_commands_sent"]==0
        assert win.original_shell.live_file_plan.session_id==raw["session_id"]
        # End Mode2: no stale snapshot button; existing file unmodified.
        previous=dest.read_bytes()
        win._end_live_capture(False)
        controls.render()
        assert not controls.buttons["bWriteTable"].isEnabled()
        assert dest.read_bytes()==previous
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()


def test_table_does_not_persist_foreign_tcp_run_selected_inside_modal_picker(
    qt_app,tmp_path,monkeypatch
):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        assert win.enter_measurement_mode()
        win._begin_live_capture()
        raw=live_state()
        validated=validate_live_status(raw,
            expected_run=raw["session_id"],now=now())
        win._receive_native_live_status(validated)
        btn=win.original_shell.measure_controls
        btn.render()
        assert btn.buttons["bWriteTable"].isEnabled()
        dest=tmp_path/"TABLE-2026-11-19--17-10-20.csv"
        def simulate_other_run(*_):
            # Source changes while the Qt native FileDialog spins its
            # own event loop. The action must never write stale table.
            win._measurement_exit_requested=True
            return str(dest),"CSV (*.csv)"
        monkeypatch.setattr(measure_ui,"QFileDialog",SimpleNamespace(
            getSaveFileName=simulate_other_run))
        btn.buttons["bWriteTable"].click()
        assert not dest.exists()
        assert btn.panel.property("sourceOriginalLiveTableSnapshotReceipt") is None
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()
