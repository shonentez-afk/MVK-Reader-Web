"""Stage111Z31DA Qt source bWriteAdc/bWriteValues -> local Go mark inbox.

No TCP connection or industrial instrument. Exercises real Qt controls,
the actual shared source Core ledger and atomic local GUI event files.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt

from .test_desktop_qt import qt_app
from .test_stage111z31cz_source_write_stages_core import source_status,RUN
from .test_stage111z31cs_qt_measurement_mode import _capture_source_mode2
from ..core.source_frame_mark_protocol import (
    INBOX,submit_native_frame_mark,
)


class _LocalMarkerReceiver:
    """Only local self-contained test double, never a device/client."""
    _mode="capture"

    def __init__(self,root):
        self._capture_root=root
        self._frame_mark_sequence=0

    def send_source_frame_mark(self,kind,begin,plan,session_id):
        number=self._frame_mark_sequence+1
        receipt=submit_native_frame_mark(
            self._capture_root,number,session_id,
            kind+("_begin" if begin else "_end"),plan)
        self._frame_mark_sequence=number
        return receipt

    def is_busy(self):
        return False


def test_original_qt_buttons_queue_true_next_frame_marks_not_status_counters(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    inbox=tmp_path/INBOX
    inbox.mkdir()
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        win._native_dialog=_LocalMarkerReceiver(tmp_path)
        panel=win.original_measure_controls
        assert not panel.buttons["bWriteAdc"].isEnabled()
        win._receive_native_live_status(source_status())
        qt_app.processEvents()
        assert panel.buttons["bWriteAdc"].isEnabled()
        assert panel.buttons["bWriteValues"].isEnabled()
        # Start selected source 10+43+73 in the original pnMeasure.
        panel.buttons["bWriteAdc"].click()
        panel.buttons["bWriteValues"].click()
        assert win._source_live_writer.frame_marks_required
        assert len(win._source_live_writer.frame_mark_actions)==2
        for name,label in (("bWriteAdc","сигнала"),("bWriteValues","значений")):
            button=panel.buttons[name]
            seconds=button.property("sourceWriterElapsedSeconds")
            assert type(seconds) is int and seconds>=0
            assert button.property("sourceWriterElapsedTimeBasis")==(
                "OPERATOR_REQUEST_UTC_NOT_DELPHI_FILE_OPEN")
            hhmmss=f"{seconds//3600%24:02d}:{seconds//60%60:02d}:{seconds%60:02d}"
            assert button.text()=="Завершить запись "+label+"\n"+hhmmss
        src=(json.loads((inbox/"0001.json").read_text()),
             json.loads((inbox/"0002.json").read_text()))
        assert [x["event"] for x in src]==["data_begin","values_begin"]
        assert all(x["session_id"]==RUN for x in src)
        assert all(x["schema"]==
                   "MVK_NATIVE_LOCAL_FRAME_MARK_REQUEST_V1" for x in src)
        assert src[0]["channels"]==[True]*8+[False,False]
        assert len(src[0]["spec"])==43 and len(src[0]["values"])==73
        win._receive_native_live_status(source_status(
            adc_samples=512,frames=30,aux=1,raw=32000))
        qt_app.processEvents()
        panel.buttons["bWriteAdc"].click()
        panel.buttons["bWriteValues"].click()
        assert panel.buttons["bWriteAdc"].text()=="Запись сигнала"
        assert panel.buttons["bWriteValues"].text()=="Запись значений"
        assert panel.buttons["bWriteAdc"].property("sourceWriterElapsedSeconds") is None
        assert panel.buttons["bWriteValues"].property("sourceWriterElapsedSeconds") is None
        assert len(win._source_live_writer.frame_mark_actions)==4
        assert [json.loads((inbox/f"{i:04d}.json").read_text())["event"]
                for i in range(1,5)]==[
            "data_begin","values_begin","data_end","values_end"]
        assert win._source_live_writer.receipt()["completed_window_count"]==2
        assert win._source_live_writer.receipt()["source_native_mark_event_count"]==4
        assert not win._source_live_writer.receipt()["hardware_commands_sent"]
        assert win.original_shell.file_channels.count()==10
        assert win.original_shell.file_spec.count()==43
        assert win.original_shell.file_values.count()==36  # original Mode2; Go mark remains 73
        assert panel.panel.height()==53
        assert win.original_shell.file_capture_panel.height()==207
        win.original_visual_skin.reveal_page(5)
        qt_app.processEvents()
        _capture_source_mode2(win,"24_da_source_frame_marks_100_150")
        win._end_live_capture(False)
        assert win._pending_source_write_ledger is None
        assert win._source_live_writer.finished
    finally:
        win.close()
        qt_app.processEvents()


def test_frame_marker_inbox_failure_stops_source_buttons_fail_closed(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    # Missing native mark inbox: the full RAW is unaffected, but a local
    # WriteData selection may NEVER revert to the 900ms counter.
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        win._native_dialog=_LocalMarkerReceiver(tmp_path)
        win._receive_native_live_status(source_status())
        panel=win.original_measure_controls
        panel.buttons["bWriteAdc"].click()
        receipt=win._source_live_writer.receipt()
        assert receipt["source_native_frame_marks_failed"]
        assert receipt["completed_window_count"]==0
        assert not receipt["write_data_requested"]
        assert not panel.buttons["bWriteAdc"].isEnabled()
        # Fail-closed for the WHOLE Native run: recovered transport alone
        # cannot quietly resurrect broken local operator frame marks.
        win._receive_native_live_status(source_status(
            adc_samples=512,frames=30,raw=45000))
        qt_app.processEvents()
        assert not panel.buttons["bWriteAdc"].isEnabled()
        assert win._source_live_writer.frame_marks_failed
        win._end_live_capture(False)
        assert win._pending_source_write_ledger is None
    finally:
        win.close()
        qt_app.processEvents()
