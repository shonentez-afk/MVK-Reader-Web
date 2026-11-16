"""Real Qt original PageStatus + pnMeasure system error from passive Go RX.

No device connection or source write; test receives synthetic JSON
matching the single Go monitor's exact 14-register Valid model.
"""
from __future__ import annotations

import pytest
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from .test_desktop_qt import qt_app
from .test_stage111z31cz_source_write_stages_core import source_status, RUN
from ..core.original_mode2_status_cells import (
    SOURCE_INDEX_ADDR, SOURCE_STATUS_FIELD,
)


def inbound(*,value=None,param=1,frames=80,raw=50000):
    x=source_status(session=RUN,adc_samples=512,aux=2,
                    frames=frames,raw=raw)
    x.update({
        "source_rx_nonempty_parameter_frames":param,
        "source_rx_ack_observed_no_command_issued":0,
        "source_rx_denied_responses":0,
        SOURCE_STATUS_FIELD:[
            {"index":i,"register_address":address,
             "valid":i==0 and value is not None,
             "value_uint32":value if i==0 else None}
            for i,address in enumerate(SOURCE_INDEX_ADDR)
        ],
    })
    return x


def test_windows_qt_source_statuscells_real_error_blocks_live_pages_and_writer(
        qt_app):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        controls=win.original_measure_controls
        baseline=inbound(value=0)
        win._receive_native_live_status(baseline)
        qt_app.processEvents()
        assert win._source_live_writer.trustworthy
        assert win.measurement_connection_display().indicator=="good"
        cells=win.original_shell.status_page.property(
            "sourceOriginalStatusCells14Receipt")
        assert cells["source_status_cells_valid_count"]==1
        assert cells["source_statuscells0_uint32"]==0
        assert cells["source_status_cells"][0]["value_hex"]=="0x00000000"
        assert "Получено 1/14" in win.original_shell.status_note.text()
        assert not cells["source_stage3_condition_from_observed_register"]
        assert win._source_mode2_runtime.command_model.pending==()
        assert len(win._source_mode2_runtime.command_model.taken)==1

        # A *real* go-valid nonzero 0x1006 DWORD; original source would
        # enter Stage3. This must disarm the existing recording and
        # preview without touching the raw capture or a second TCP client.
        failed=inbound(value=0x80,param=2,frames=83,raw=51000)
        win._receive_native_live_status(failed)
        qt_app.processEvents()
        receipt=win._source_mode2_runtime.receipt()
        assert receipt["mode2_phase"]=="SYSTEM_ERROR"
        assert receipt["original_stage3_system_error_condition_latched"]
        assert receipt["original_status_cells_14"][
            "source_statuscells0_uint32"]==0x80
        assert receipt["original_delphi_stage3_physically_verified"] is False
        assert not win._source_live_writer.trustworthy
        assert win.measurement_connection_display().phase=="SYSTEM_ERROR"
        assert "Системная ошибка прибора" in controls.status.text()
        assert "0x00000080" in controls.status.text()
        assert controls.bad_indicator.isVisible()
        assert not controls.buttons["bWriteAdc"].isEnabled()
        assert "Системная ошибка прибора" in win.original_shell.status_note.text()
        assert "0x00000080" in win.original_shell.status_note.text()
        assert win.original_shell.status_page.property(
            "sourceOriginalStatusCells14Receipt")[
                "source_statuscells0_uint32"]==0x80
        assert receipt["hardware_commands_sent"]==0
        assert all(win.original_shell.status_table.item(i,1).text()=="—"
                   for i in range(15))

        # Raw Go status may later report 0 but original Stage3 does not
        # deassert until a new TMVKThread; prevent stale preview or write.
        cleared=inbound(value=0,param=3,frames=85,raw=52000)
        win._receive_native_live_status(cleared)
        qt_app.processEvents()
        assert win._source_mode2_runtime.status_cells.system_error_latched
        assert not win._source_live_writer.trustworthy
        assert not controls.buttons["bWriteAdc"].isEnabled()
        assert controls.bad_indicator.isVisible()
        assert "ранее подтверждена" in controls.status.text()
        assert "Системная ошибка прибора" in win.original_shell.status_note.text()
        assert win._source_mode2_runtime.receipt()["hardware_commands_sent"]==0
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()


def test_windows_qt_unknown_cell_does_not_mark_stage3_or_fill_page_status(
        qt_app):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        win._receive_native_live_status(inbound(value=None))
        qt_app.processEvents()
        receipt=win._source_mode2_runtime.receipt()
        assert not receipt["original_stage3_system_error_condition_latched"]
        assert receipt["original_status_cells_14"][
            "source_status_cells_valid_count"]==0
        assert "системные StatusCells прибора ещё не получены" in (
            win.original_shell.status_note.text())
        assert win.measurement_connection_display().indicator=="good"
        assert win._source_live_writer.trustworthy
        assert all(win.original_shell.status_table.item(i,1).text()=="—"
                   for i in range(15))
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()
