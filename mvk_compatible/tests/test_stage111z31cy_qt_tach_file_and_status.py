"""Stage111Z31CY source PageFile + TACH status, same SHA-verified Native ZIP.

Actual Qt widget QA at source DPI96 logical and Windows 144 physical DPI.
The raw TACH Float32 is device-input UNSCALED: never show invented RPM.
"""
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from .test_desktop_qt import qt_app
from .test_stage111z31cy_native_tach_evidence import (
    synthetic_tach_native_zip,
)
from .test_stage111z31cs_qt_measurement_mode import _capture_source_mode2


def test_tach_channels_9_10_show_verified_input_not_original_rpm(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        path=synthetic_tach_native_zip(tmp_path)
        win.open_archive(str(path))
        qt_app.processEvents()
        assert win.session is not None
        shell=win.original_shell
        assert shell.file_channels.count()==10
        assert shell.file_capture_panel.height()==207
        assert shell.file_action_tabs.count()==2
        assert shell.file_spec.count()==43
        assert shell.file_values.count()==73
        for index in (8,9):
            item=shell.file_channels.item(index)
            assert item.flags() & Qt.ItemIsEnabled
            assert item.checkState()==Qt.Checked
            assert "raw Float32" in item.text()
            assert "БЕЗ физической калибровки" in item.text()
            assert "128" in item.text()
        receipt=shell.file_page.property("sourceNativeTachExportEvidence")
        assert receipt["safe_native_tach_channels"]==[9,10]
        assert receipt["physical_rpm_calibration_verified"] is False
        assert not receipt["device_commands_sent"]
        # Two independent tab modes from DFM. No invented TACH waveform.
        win.original_status_mode.setCurrentIndex(13)
        shell.refresh_status()
        qt_app.processEvents()
        tach=shell.status_page.property("sourceNativeTachReceipt")
        assert tach["native_channel"]==9
        assert tach["samples"]==128
        assert tach["rate_hz"]==32768
        assert not tach["physical_rpm_verified"]
        assert "неотмасштабированный Float32" in shell.status_note.text()
        assert "калибровка НЕ подтверждены" in shell.status_note.text()
        win.original_status_mode.setCurrentIndex(14)
        shell.refresh_status()
        qt_app.processEvents()
        assert shell.status_page.property(
            "sourceNativeTachReceipt")["native_channel"]==10
        win.original_visual_skin.reveal_page(5)
        qt_app.processEvents()
        _capture_source_mode2(win,"20_cy_native_tach_sha_100_150")
        shell.file_channels.item(8).setCheckState(Qt.Unchecked)
        assert not shell.file_record_selection.channels[8]
        assert shell.file_record_selection.channels[9]
        assert shell.file_export_button.isEnabled()
        assert "TACH raw" in shell.file_selection_status.text()
    finally:
        win.close()
        qt_app.processEvents()


def test_untrusted_continuity_tach_disabled_but_original_adc_unchanged(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        source=synthetic_tach_native_zip(tmp_path,gap_on_tach1=True)
        win.open_archive(str(source))
        shell=win.original_shell
        assert win.session is not None
        item=shell.file_channels.item(8)
        assert not item.flags() & Qt.ItemIsEnabled
        assert "разрыв/смена частоты" in item.text()
        assert shell.file_channels.item(9).flags() & Qt.ItemIsEnabled
        assert shell.file_record_selection.channels[8] is False
        assert shell.file_record_selection.channels[9] is True
        receipt=shell.file_page.property("sourceNativeTachExportEvidence")
        assert receipt["channels"][0]["sequence_gaps"]==1
        assert not receipt["channels"][0]["safe_for_local_raw_export"]
        # Original 8 ADC and calibrated spectrum remain separate.
        assert shell.file_record_selection.channels[:8]==(True,)*8
        assert win.session.samples(1)[0].size==4096
    finally:
        win.close()
        qt_app.processEvents()
