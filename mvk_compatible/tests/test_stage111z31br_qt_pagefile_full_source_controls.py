"""Stage111Z31BR: real Qt PageFile geometry, checkbox actions and export.

Private original Tmvkform PageFile: 369px splitter, 2 tcFileActions modes,
10 channel checkboxes, 43 Spec, 24+43+6 VALUES, 207px pnFileAdc.
Synthetic Native ZIP/direct BIN only; no external device commands.
"""
from hashlib import sha256
import json
from pathlib import Path

import pytest
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget,QLabel,QLineEdit,QCheckBox,
                               QTabWidget,QListWidget,QFileDialog,QPushButton)

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z16_direct_bin_tsxml import _make_pair
from .test_stage111z31bj_qt_visible_file_workbench import (
    capture_synthetic_ui_if_requested)
from ..core.direct_bin_session import DirectBinSession
from ..core.original_pagefile_recording import (
    CHANNEL_COUNT,SPEC_COUNT,VALUE_COUNT,
    ORIGINAL_SOURCE_DEFAULT_FOLDER_TEMPLATE)


def test_dpi150_original_pagefile_two_modes_selected_source_and_writer_options(
        qt_app,tmp_path,monkeypatch):
    from ..desktop.main_window import MainWindow
    window=MainWindow()
    window.show()
    qt_app.processEvents()
    try:
        win=window
        ui=win.original_shell
        win.original_root_tabs.setCurrentIndex(5)
        qt_app.processEvents()
        assert ui.file_page.objectName()=="PageFile"
        channels=ui.file_page.findChild(QListWidget,"cbFileChannels")
        assert channels.count()==0
        assert ui.file_page.findChild(QTabWidget,"tcFileChannels").count()==1
        tabs=ui.file_page.findChild(QTabWidget,"tcFileActions")
        assert tabs.count()==2
        assert "SPEC" in tabs.tabText(0)
        assert "АЦП" in tabs.tabText(1)
        adc=ui.file_page.findChild(QWidget,"pnFileAdc")
        assert adc.height()==207
        assert not adc.isVisible()
        for key in ("cbFileWriteXml","cbFileFolderPrefix","cbFileMvkName"):
            box=ui.file_page.findChild(QCheckBox,key)
            assert box is not None and box.isChecked()
        assert ui.file_page.findChild(
            QLineEdit,"edFolderPrefix").text()==ORIGINAL_SOURCE_DEFAULT_FOLDER_TEMPLATE
        assert not ui.file_page.findChild(QLineEdit,"edFilePrefix").isVisible()
        assert not ui.file_page.findChild(QLabel,"lbFilePrefix").isVisible()
        assert not ui.file_export_button.isEnabled()

        original=fixture_zip(tmp_path,sample_count=4096)
        zip_sha=sha256(original.read_bytes()).hexdigest()
        win.open_archive(original)
        qt_app.processEvents()
        assert len(ui.file_record_selection.channels)==CHANNEL_COUNT
        assert len(ui.file_record_selection.spec)==SPEC_COUNT
        assert len(ui.file_record_selection.values)==VALUE_COUNT
        assert channels.count()==10
        assert all(channels.item(i).checkState()==Qt.Checked for i in range(8))
        assert all(channels.item(i).checkState()==Qt.Unchecked for i in (8,9))
        assert all(not channels.item(i).flags() & Qt.ItemIsEnabled
                   for i in (8,9))
        assert ui.file_spec.count()==SPEC_COUNT
        assert ui.file_values.count()==VALUE_COUNT
        assert all(not ui.file_values.item(i).flags() & Qt.ItemIsEnabled
                   for i in range(67,73))
        assert ui.file_export_button.isEnabled()
        assert ui.file_metadata.rowCount()>=10

        tabs.setCurrentIndex(1)
        qt_app.processEvents()
        assert adc.isVisible()
        assert ui.file_page.findChild(QLineEdit,"edFolderPrefix").isEnabled()
        assert ui.file_page.findChild(QLineEdit,"edFileMvkName").isEnabled()
        assert ui.file_page.findChild(
            QLineEdit,"edFileMvkName").text()==win.session.serial
        ui.file_record_flags["cbFileFolderPrefix"].setChecked(False)
        assert not ui.file_page.findChild(
            QLineEdit,"edFolderPrefix").isEnabled()
        ui.file_record_flags["cbFileFolderPrefix"].setChecked(True)
        assert ui.file_page.findChild(
            QLineEdit,"edFolderPrefix").isEnabled()
        ui.file_record_flags["cbFileMvkName"].setChecked(False)
        assert not ui.file_page.findChild(
            QLineEdit,"edFileMvkName").isEnabled()
        ui.file_record_flags["cbFileMvkName"].setChecked(True)
        assert ui.file_page.findChild(
            QLineEdit,"edFileMvkName").isEnabled()
        assert "НЕ управляют Native R6.1" in ui.file_page.findChild(
            QLabel,"sourceFileOfflineCaptureNote").text()
        # User picks source selection. This must NOT switch ADC signal
        # merely because a check state changed.
        tabs.setCurrentIndex(0)
        current_adc=win.adc.currentIndex()
        channels.item(1).setCheckState(Qt.Unchecked)
        assert ui.file_record_selection.channels[1] is False
        assert win.adc.currentIndex()==current_adc
        ui.file_spec.item(0).setCheckState(Qt.Unchecked)
        assert ui.file_record_selection.spec[0] is False
        ui.file_values.item(0).setCheckState(Qt.Unchecked)
        assert ui.file_record_selection.values[0] is False
        win.adc.setCurrentIndex(4)
        qt_app.processEvents()
        assert "АЦП5" in ui.file_summary.text()
        assert channels.item(1).checkState()==Qt.Unchecked
        assert ui.file_spec.item(0).checkState()==Qt.Unchecked
        if win.session.updates>1:
            ui.file_tick.setValue(1)
            qt_app.processEvents()
            assert channels.item(1).checkState()==Qt.Unchecked
            assert ui.file_values.item(0).checkState()==Qt.Unchecked
        capture_synthetic_ui_if_requested(
            win,qt_app,"19_br_pagefile_10_channel_43_spec_73_values")
        tabs.setCurrentIndex(1)
        capture_synthetic_ui_if_requested(
            win,qt_app,"20_br_pagefile_original_adc_write_207px")

        out=tmp_path/"offline_pagefile_export"
        out.mkdir()
        ui.file_record_names["edFolderPrefix"].setText("MVKWork")
        ui.file_record_names["edFileMvkName"].setText("UserLocalMVK")
        monkeypatch.setattr(
            QFileDialog,"getExistingDirectory",
            staticmethod(lambda *a,**kw:str(out)))
        ui.file_export_button.click()
        qt_app.processEvents()
        generated=list(out.iterdir())
        assert len(generated)==1 and generated[0].is_dir()
        manifest=json.loads((generated[0]/"PAGEFILE_SELECTION.json").read_text(
            encoding="utf-8"))
        assert manifest["source_pagefile_checklists"]["selected_adcs"]==[
            1,3,4,5,6,7,8]
        assert 0 not in manifest["source_pagefile_checklists"][
            "selected_spec_indices"]
        assert 0 not in manifest["source_pagefile_checklists"][
            "selected_value_indices"]
        assert manifest["source_pagefile_settings"]["cbFileWriteXml"] is True
        assert not manifest["device_io_executed"]
        assert "Экспортировано" in ui.file_source_evidence.text()
        assert sha256(original.read_bytes()).hexdigest()==zip_sha
        assert win.original_root_tabs.isTabEnabled(3)
    finally:
        window.close()
        qt_app.processEvents()


def test_source_pagefile_bin_mode_no_fake_dsp_and_tach_disabled(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    source,sidecar,_=_make_pair(tmp_path,adc=4,n=8192)
    win=MainWindow()
    win.show()
    qt_app.processEvents()
    try:
        win.open_archive(source)
        win.original_root_tabs.setCurrentIndex(5)
        qt_app.processEvents()
        ui=win.original_shell
        assert isinstance(win.session,DirectBinSession)
        assert ui.file_channels.count()==10
        assert ui.file_channels.item(3).checkState()==Qt.Checked
        assert all(not ui.file_channels.item(i).flags() & Qt.ItemIsEnabled
                   for i in range(10) if i!=3)
        assert ui.file_spec.count()==1
        assert ui.file_values.count()==1
        assert not ui.file_record_selection.checked("spec")
        assert not ui.file_record_selection.checked("values")
        assert ui.file_export_button.isEnabled()
        assert "нет аппаратных VALUES/AUX" in ui.file_summary.text()
        capture_synthetic_ui_if_requested(
            win,qt_app,"21_br_direct_bin_no_dsp")
        assert not ui.file_page.findChild(
            QLineEdit,"edFilePrefix").isVisible()
    finally:
        win.close()
        qt_app.processEvents()
