"""Source Mode2 PageFile 10+43+73 -> Native live -> accepted ZIP; no I/O."""
from __future__ import annotations
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31cs_qt_measurement_mode import _capture_source_mode2
from .test_stage111z31cr_connected_core import source_test_transport


def _native_status():
    good=source_test_transport(phase="RECORDING",frames=240)
    good["session_id"]="TEST_2026-11-16_10-01-00.000"
    good["seconds_since_last_packet"]=0.1
    good["channels"]=[
        {"channel":i,"type":"ADC" if i<=8 else "TACH",
         "samples":2000*i,"sample_rates_hz":[65536] if i<=8 else [1024],
         "sequence_discontinuities":0,"nonfinite_samples":0}
        for i in range(1,11)]
    return good


def _assert_live_lists(shell):
    assert shell.file_action_tabs.count()==2
    assert shell.file_capture_panel.height()==207
    assert shell.file_channels.count()==10
    assert shell.file_spec.count()==43
    assert shell.file_values.count()==73
    receipt=shell.file_page.property("sourceLiveFilePlanReceipt")
    assert receipt["source_channel_flag_count"]==10
    assert receipt["source_spec_flag_count"]==43
    assert receipt["source_value_flag_count"]==73
    assert not receipt["device_commands_sent"]
    assert not receipt["selection_controls_native_r6_raw_capture"]


def test_mode2_pagefile_checkboxes_survive_live_and_filter_only_verified_export(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        assert win.enter_measurement_mode()
        qt_app.processEvents()
        shell=win.original_shell
        _assert_live_lists(shell)
        assert not win._live_active
        assert win._native_live_status is None
        assert win.original_root_tabs.isTabVisible(5)
        shell.file_channels.item(0).setCheckState(Qt.Unchecked)
        shell.file_channels.item(9).setCheckState(Qt.Checked)
        shell.file_spec.item(8).setCheckState(Qt.Unchecked)
        shell.file_values.item(0).setCheckState(Qt.Unchecked)
        _assert_live_lists(shell)
        assert not shell.live_file_plan.channels[0]
        assert shell.live_file_plan.channels[9]
        assert not shell.live_file_plan.spec[8]
        assert not shell.live_file_plan.values[0]
        win.original_visual_skin.reveal_page(5)
        qt_app.processEvents()
        _capture_source_mode2(win,"18_cx_pagefile_10_before_tcp")
        win._begin_live_capture()
        qt_app.processEvents()
        _assert_live_lists(shell)
        assert not shell.live_file_plan.channels[0]
        win._receive_native_live_status(_native_status())
        qt_app.processEvents()
        assert shell.live_file_plan.session_id==_native_status()["session_id"]
        assert "2000 отсчётов" in shell.file_channels.item(0).text()
        assert "20000 отсчётов" in shell.file_channels.item(9).text()
        assert "TACH RAW не подтверждён" in shell.file_channels.item(9).text()
        assert not shell.file_export_button.isEnabled()
        _capture_source_mode2(win,"19_cx_pagefile_10_native_stream")
        assert shell.status_page.property(
            "sourceOriginalSystemRowsVerified")==0
        win._end_live_capture(True)
        qt_app.processEvents()
        assert shell.live_file_plan is None
        assert win._pending_native_pagefile_plan is not None
        archive=fixture_zip(tmp_path)
        win._accept_native_capture_archive(str(archive))
        qt_app.processEvents()
        assert win.session is not None
        selected=shell.file_record_selection
        assert selected.channels[0] is False
        assert selected.channels[1] is True
        assert selected.channels[8:] == (False,False)
        assert selected.spec[8] is False
        assert selected.values[0] is False
        assert shell.file_channels.item(0).checkState()==Qt.Unchecked
        assert shell.file_spec.item(8).checkState()==Qt.Unchecked
        assert shell.file_values.item(0).checkState()==Qt.Unchecked
        accepted=shell.file_page.property("sourceAppliedLiveFilePlanReceipt")
        assert accepted["verified_source_bin_rechecked"]
        assert accepted["unsupported_original_tach_channels"]==[2]
        assert not accepted["hardware_write_commands_sent"]
        assert win._pending_native_pagefile_plan is None
    finally:
        win.close()
        qt_app.processEvents()


def test_foreign_native_run_rejected_and_old_live_counts_removed(qt_app):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.enter_measurement_mode()
        shell=win.original_shell
        shell.file_channels.item(1).setCheckState(Qt.Unchecked)
        win._begin_live_capture()
        win._receive_native_live_status(_native_status())
        qt_app.processEvents()
        assert "4000 отсчётов" in shell.file_channels.item(1).text()
        alien=_native_status()|{"session_id":"TEST_2026-11-16_11-01-00.000"}
        win._receive_native_live_status(alien)
        qt_app.processEvents()
        assert win._native_live_status is None
        assert "ожидание данных" in shell.file_channels.item(1).text()
        assert not shell.live_file_plan.channels[1]
        assert not shell.file_page.property("sourceLiveFilePlanReceipt")[
            "connected_status_evidence_accepted"]
        win._end_live_capture(False)
        qt_app.processEvents()
        assert win._measurement_mode_selected
        _assert_live_lists(shell)
        assert win.leave_measurement_mode()
        qt_app.processEvents()
        assert shell.live_file_plan is None
        assert shell.file_channels.count()==0
        assert win._pending_native_pagefile_plan is None
    finally:
        win.close()
        qt_app.processEvents()


def test_aborted_mode2_masks_never_leak_to_manually_opened_archive(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.enter_measurement_mode()
        win.original_shell.file_channels.item(0).setCheckState(Qt.Unchecked)
        assert win.leave_measurement_mode()
        archive=fixture_zip(tmp_path)
        win.open_archive(str(archive))
        assert win.session is not None
        assert win.original_shell.file_record_selection.channels[0]
        assert win.original_shell.file_page.property(
            "sourceAppliedLiveFilePlanReceipt") is None
    finally:
        win.close()
        qt_app.processEvents()
