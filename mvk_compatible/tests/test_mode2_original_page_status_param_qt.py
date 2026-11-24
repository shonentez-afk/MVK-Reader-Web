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
            (2,"tabAllResult",36),(3,"tabAllResult",36),
            (4,"tabAllResult",36),(5,"tabResult",30),
            (6,"tabResult",30),(7,"tabResult",30),
            (8,"tabResult",30),(9,"tabResult",30),
            (10,"tabResult",30),(11,"tabResult",30),
            (12,"tabResult",30),(13,"tabResult",6),
            (14,"tabResult",6)):
            w.original_status_mode.setCurrentIndex(index)
            w.original_shell.refresh_status()
            grid=w.original_shell.status_table
            assert grid.objectName()==expected_grid
            assert grid.rowCount()==expected_rows
            receipt=w.original_shell.status_page.property(
                "sourceLivePageStatusParamEvidence")
            assert receipt is not None and receipt["mode"]==index
            assert receipt["source_session_id"]==status["session_id"]
            assert receipt["accepted_param_frames"]==3
            assert receipt["source_original_operator_layout"] is True
        w.original_status_mode.setCurrentIndex(1)
        w.original_shell.refresh_status()
        assert w.original_shell.status_table.item(0,1).text()=="4,5"
        # +0x132: state = low 8 bits, alert = bits 8..15.
        assert w.original_shell.status_table.item(1,1).text()==(
            "Красная зона (квитировано) (Устар. ПО)")
        assert w.original_shell.status_table.item(2,1).text()=="---"
        w.original_status_mode.setCurrentIndex(2)
        w.original_shell.refresh_status()
        all_grid=w.original_shell.status_table
        assert all_grid.columnCount()==12
        assert all_grid.item(6,1).text()=="1,5"
        assert all_grid.item(30,9).text()=="50,5"
        assert all_grid.item(30,1).text()==""
        w.original_status_mode.setCurrentIndex(5)
        w.original_shell.refresh_status()
        grid=w.original_shell.status_table
        assert grid.columnCount()==5
        assert [grid.item(6,i).text() for i in (1,2,3)]==["1,5","2,5","3,5"]
        assert grid.item(6,4).text()=="м/с2"
        assert w.original_shell.status_plot.isVisible()
        from ..core.original_status_workbench import source_octave_y_max
        expected_max=source_octave_y_max(w.original_shell._source_status_projection.model.bands_for_plot)
        assert w.original_shell.status_page.property("sourceOctaveYMaximum")==expected_max
        assert w.original_shell.status_plot.viewRange()[1]==pytest.approx([0.0,expected_max])
        assert w.original_shell._source_status_projection.cursor(0)[
            "verified_source_band_value"]==0.25
        # tcStatus has its own ADC selector; changing waveform ADC must
        # not make the currently selected PageStatus ADC show another bank.
        w.adc.setCurrentIndex(1)
        assert w.original_shell.status_table.item(6,1).text()=="1,5"
        assert w.original_status_mode.currentIndex()==5
        assert w._source_mode2_runtime.receipt()["hardware_commands_sent"]==0
        # A physical input error or stopped session must not keep the
        # previous positive 43-band chart on a different run.
        bad=dict(status)
        bad["seconds_since_last_packet"]=5.1
        bad["quality_alert"]=True
        w._receive_native_live_status(bad)
        w.original_shell.refresh_status()
        assert not w.original_shell.status_plot.isVisible()
        assert w.original_shell.status_page.property("sourceOctaveYMaximum") is None
        assert w.original_shell.status_table.item(0,1).text()=="—"
        w._end_live_capture(False)
        assert w.original_shell.status_page.property(
            "sourceLivePageStatusParamEvidence") is None
    finally:
        if w._live_active:
            w._end_live_capture(False)
        w.close()
        qt_app.processEvents()

def test_live_status_freeze_keeps_one_param_snapshot_and_stop_clears_all_modes(qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    from .test_mode2_original_page_status_param_banks import w as raw_float
    class StopOwner:
        _mode="capture"
        def stop_capture(self): return True
        def is_busy(self): return False

    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win._begin_live_capture()
        raw=live_state()
        first=validate_live_status(raw,expected_run=raw["session_id"],now=now())
        win._receive_native_live_status(first)
        win.original_status_mode.setCurrentIndex(5)
        shell=win.original_shell
        assert shell.status_table.item(6,1).text()=="1,5"
        original=shell._source_status_projection
        # Same timer cycle must not clear/rebuild identical grids.
        shell.refresh_status()
        assert shell._source_status_projection is original
        win.original_measure_controls.freeze.click()
        qt_app.processEvents()
        assert win._source_live_view_frozen
        raw2=live_state()
        raw2["source_live_page_status_banks"]["accepted_param_frames"]=4
        raw2["source_live_page_status_banks"]["adc"][0]["rms_24_raw_f32_le"][0]=raw_float(9.5)
        second=validate_live_status(raw2,expected_run=raw2["session_id"],now=now())
        win._receive_native_live_status(second)
        win.original_status_mode.setCurrentIndex(2)
        assert shell.status_table.item(6,1).text()=="1,5"
        receipt=shell.status_page.property("sourceLivePageStatusParamEvidence")
        assert receipt["display_frozen"] and receipt["accepted_param_frames"]==3
        win.original_measure_controls.freeze.click()
        qt_app.processEvents()
        assert not win._source_live_view_frozen
        assert shell.status_table.item(6,1).text()=="9,5"
        assert shell.status_page.property("sourceLivePageStatusParamEvidence")[
            "accepted_param_frames"]==4
        # A fault during a held display must clear actual numeric rows,
        # including on switching to another register mode.
        win.original_measure_controls.freeze.click()
        win._receive_native_live_status({**second,"seconds_since_last_packet":5.1})
        win.original_status_mode.setCurrentIndex(5)
        assert shell.status_table.item(6,1).text()=="—"
        assert not shell.status_plot.isVisible()
        assert shell.status_page.property("sourceLivePageStatusParamEvidence") is None
        win.original_measure_controls.freeze.click()
        win._receive_native_live_status(second)
        assert shell.status_table.item(6,1).text()=="9,5"
        win._native_dialog=StopOwner()
        assert win.request_measurement_stop()
        win.original_status_mode.setCurrentIndex(13)
        assert shell.status_table.item(0,1).text()=="—"
        assert shell.status_page.property("sourceLivePageStatusParamEvidence") is None
        assert not shell.status_page.property("sourceNativeTransportConnected")
        # Delayed healthy PARAM after Stop cannot restore results.
        win._receive_native_live_status(second)
        win.original_status_mode.setCurrentIndex(5)
        assert shell.status_table.item(6,1).text()=="—"
        assert not shell.status_plot.isVisible()
    finally:
        win._native_dialog=None
        if win._live_active:
            win._end_live_capture(False)
        win.close()
        qt_app.processEvents()
