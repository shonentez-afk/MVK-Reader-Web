"""Stage111Z31CZ end-to-end source five-button panel, Core and Qt together.

All clicks execute on a Qt window against synthetic read-only Go status.
They are never sent to a physical instrument or vendor TMVKThread.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
pytest.importorskip("PySide6")

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31cs_qt_measurement_mode import _capture_source_mode2
from .test_stage111z31cz_source_write_stages_core import (
    RUN,source_status,
)
from ..core.original_live_write_stages import EXPORT_SUBDIR


def test_source_write_buttons_start_stop_and_same_native_run_exports(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.enter_measurement_mode()
        panel=win.original_measure_controls
        # No instrument/no source status: original buttons do not pretend
        # that a local capture started merely by showing five source tabs.
        assert not panel.buttons["bWriteAdc"].isEnabled()
        assert not panel.buttons["bWriteValues"].isEnabled()
        win._begin_live_capture()
        assert not panel.buttons["bWriteAdc"].isEnabled()
        win._receive_native_live_status(source_status())
        qt_app.processEvents()
        assert panel.buttons["bWriteAdc"].isEnabled()
        assert panel.buttons["bWriteValues"].isEnabled()
        assert panel.rate_menu.actions()[0].isEnabled() is False
        panel.buttons["bWriteAdc"].click()
        panel.buttons["bWriteValues"].click()
        qt_app.processEvents()
        state=panel.panel.property("sourceOriginalWriteStageReceipt")
        assert state["write_data_stage"]==0
        assert state["write_values_stage"]==1
        assert state["write_data_requested"]
        assert state["write_values_requested"]
        assert "Завершить запись сигнала" in panel.buttons["bWriteAdc"].text()
        assert "Завершить запись значений" in panel.buttons["bWriteValues"].text()
        assert "WriteDataStage=0" in win.original_shell._file_selection_status()
        assert win.original_shell.file_channels.count()==10
        assert win.original_shell.file_spec.count()==43
        assert win.original_shell.file_values.count()==36  # original Mode2; Go mark remains 73
        assert win.original_shell.file_capture_panel.height()==207
        win.original_visual_skin.reveal_page(5)
        qt_app.processEvents()
        _capture_source_mode2(win,"21_cz_real_write_stages_armed")
        win._receive_native_live_status(source_status(
            adc_samples=512,aux=1,frames=30,raw=19000))
        qt_app.processEvents()
        assert panel.panel.property(
            "sourceOriginalWriteStageReceipt")["write_data_stage"]==1
        panel.buttons["bWriteAdc"].click()
        panel.buttons["bWriteValues"].click()
        qt_app.processEvents()
        state=panel.panel.property("sourceOriginalWriteStageReceipt")
        assert state["completed_window_count"]==2
        assert state["write_data_stage"]==2
        assert state["write_values_stage"]==2
        assert not state["hardware_commands_sent"]
        _capture_source_mode2(win,"22_cz_real_write_stages_closed")
        # Physical test path is NOT accessible: operator-verified local
        # Native ZIP arrival is stimulated using synthetic fixture.
        run=tmp_path/RUN
        run.mkdir()
        archive=fixture_zip(run)
        win._end_live_capture(True)
        assert win._pending_source_write_ledger is not None
        win._accept_native_capture_archive(str(archive))
        worker=win._source_writer_export_worker
        assert worker is not None
        assert worker.wait(30000)
        qt_app.processEvents()
        result=win._source_writer_last_export
        assert result is not None and not result.get("failed_closed")
        assert result["windows"]==2
        assert result["files_written"]==9
        manifest=json.loads(
            (run/EXPORT_SUBDIR/"SOURCE_WRITE_WINDOWS_AUDIT.json").read_text(
                encoding="utf-8"))
        assert manifest["hardware_command_sent"] is False
        assert manifest["original_tmkvthread_byte_exact_recording"] is False
        assert len(manifest["files"])==9
        assert win.session is not None
    finally:
        worker=getattr(win,"_source_writer_export_worker",None)
        if worker is not None and worker.isRunning():
            worker.wait(30000)
        win.close()
        qt_app.processEvents()


def test_live_invalid_status_disarms_source_writers_without_fake_files(
        qt_app):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        panel=win.original_measure_controls
        win._receive_native_live_status(source_status())
        panel.buttons["bWriteAdc"].click()
        assert win._source_live_writer.data_stage==0
        bad=source_status(
            adc_samples=512,frames=30,raw=19000,packets_bad=True)
        win._receive_native_live_status(bad)
        qt_app.processEvents()
        assert win._source_live_writer.data_stage==2
        assert not panel.buttons["bWriteAdc"].isEnabled()
        assert win._source_live_writer.errors
        assert win._pending_source_write_ledger is None
        win._end_live_capture(False)
        assert win._source_live_writer.finished
        assert not win._source_live_writer.windows
        assert win._pending_source_write_ledger is None
    finally:
        win.close()
        qt_app.processEvents()


def test_live_pagefile_real_writer_locks_and_independent_channel_selector(qt_app):
    from PySide6.QtCore import Qt
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        win._receive_native_live_status(source_status())
        shell=win.original_shell
        panel=win.original_measure_controls
        c,s,v=shell.file_channels,shell.file_spec,shell.file_values
        channel=c.item(0)
        adc=win.adc.currentIndex()
        c.setCurrentRow(1)
        assert win.adc.currentIndex()==adc
        panel.buttons["bWriteAdc"].click()
        assert not channel.flags() & Qt.ItemIsEnabled
        assert s.item(0).flags() & Qt.ItemIsEnabled
        assert not shell.file_record_flags["cbFileWriteXml"].isEnabled()
        s.item(0).setCheckState(Qt.Unchecked)
        assert not shell.live_file_plan.spec[0]
        panel.buttons["bWriteAdc"].click()
        assert channel.flags() & Qt.ItemIsEnabled
        panel.buttons["bWriteValues"].click()
        assert not channel.flags() & Qt.ItemIsEnabled
        assert not s.item(0).flags() & Qt.ItemIsEnabled
        assert not v.item(0).flags() & Qt.ItemIsEnabled
        assert shell.file_record_flags["cbFileWriteXml"].isEnabled()
        channel.setCheckState(Qt.Unchecked)
        assert shell.live_file_plan.channels[0]
        assert channel.checkState()==Qt.Checked
        win._receive_native_live_status(source_status(
            adc_samples=512,aux=1,frames=30,raw=19000))
        assert c.item(0) is channel
        # The row stays selected even while locked; no rebuilding on RX.
        assert c.currentRow()==1
        panel.buttons["bWriteValues"].click()
        assert channel.flags() & Qt.ItemIsEnabled
        assert s.item(0).flags() & Qt.ItemIsEnabled
        assert not shell.live_file_plan.spec[0]
        assert "Полоса 0.63 Гц" in s.item(0).text()
        assert v.item(0).text()=="Индикатор перегрузки"
        # ADC result flags alone cannot start a TACH-only VALUES file.
        for i in range(8):
            c.item(i).setCheckState(Qt.Unchecked)
        c.item(8).setCheckState(Qt.Checked)
        assert panel.buttons["bWriteAdc"].isEnabled()
        assert not panel.buttons["bWriteValues"].isEnabled()
        v.item(30).setCheckState(Qt.Checked)
        assert panel.buttons["bWriteValues"].isEnabled()
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()


def test_receiver_finalization_locks_operator_until_verified_archive(qt_app):
    from PySide6.QtCore import Qt
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        win._receive_native_live_status(source_status())
        panel=win.original_measure_controls
        shell=win.original_shell
        panel.buttons["bWriteAdc"].click()
        panel.buttons["bWriteValues"].click()
        assert panel.buttons["bWriteAdc"].property("sourceWriterElapsedSeconds")>=0
        assert panel.buttons["bWriteValues"].text().count(":")==2
        win._receive_native_live_status(source_status(
            adc_samples=512,aux=1,frames=30,raw=19000))
        # A normally completed receiver is no longer an active command
        # owner, even though captureEnded(True) awaits ZIP verification.
        terminal=source_status(adc_samples=512,aux=1,frames=30,raw=19000)
        terminal["phase"]="VERIFYING"
        win._receive_native_live_status(terminal)
        assert win._live_active and win._live_capture_stopping()
        assert not win._measurement_exit_requested
        assert not panel.buttons["bWriteAdc"].isEnabled()
        assert not panel.buttons["bWriteValues"].isEnabled()
        assert not panel.freeze.isEnabled()
        assert not shell.file_spec.item(0).flags() & Qt.ItemIsEnabled
        assert not shell.file_record_flags["cbFileWriteXml"].isEnabled()
        assert win._source_live_writer.receipt()["source_writer_finalizing"]
        with pytest.raises(ValueError):
            win.source_write_toggle("data")
        # A late status or missing terminal JSON cannot reopen the
        # commands or discard the pending valid BEGIN intervals.
        win._receive_native_live_status(source_status(
            adc_samples=768,aux=2,frames=40,raw=24000))
        win._invalidate_native_live_status("terminal status file not present")
        assert win._source_live_writer.receipt()["write_data_requested"]
        assert win._source_live_writer.receipt()["write_values_requested"]
        assert not panel.buttons["bWriteAdc"].isEnabled()
        win._end_live_capture(True)
        assert win._pending_source_write_ledger is not None
        assert len(win._pending_source_write_ledger.windows)==2
        assert not win._live_active
    finally:
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()
