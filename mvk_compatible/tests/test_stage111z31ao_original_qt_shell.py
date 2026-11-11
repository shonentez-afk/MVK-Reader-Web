"""Original DFM top-level tab shell keeps functional legacy spectrum Qt paths."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
from PySide6.QtWidgets import QApplication, QPushButton, QTabWidget
from mvk_compatible.desktop.main_window import MainWindow


@pytest.fixture
def source_window():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    window = MainWindow()
    yield window
    window.close()


def test_source_root_seven_pages_and_legacy_compatibility(source_window):
    win = source_window
    assert win.original_root_tabs.objectName() == "Pages"
    assert win.original_root_tabs.count() == 7
    assert [win.original_root_tabs.tabData(i) for i in range(7)] == [
        "PageStart", "PageConfig", "PageStatus",
        "PageAdc", "PageSpectrum", "PageFile", "PageCalib"]
    assert win.original_root_tabs.height() == 44
    assert win.tabs.count() == 3  # APIs used by existing Qt calculations remain.
    assert win.tabs.tabBar().isHidden()
    assert win.original_root_tabs.currentIndex() == 0


def test_source_shell_routing_calculated_wave_spectrum(source_window):
    win = source_window
    win._set_active(True)  # Test-only; simulates loaded offline session
    win.original_root_tabs.setCurrentIndex(4)
    assert win.tabs.currentIndex() == 2
    assert win.original_root_stack.currentIndex() == 0
    win.original_root_tabs.setCurrentIndex(3)
    assert win.tabs.currentIndex() == 1
    win.original_root_tabs.setCurrentIndex(2)
    assert win.tabs.currentIndex() == 0
    assert win.task_subpages.currentIndex() == 5
    win.original_root_tabs.setCurrentIndex(0)
    assert win.task_subpages.currentIndex() == 0
    win.tabs.setCurrentIndex(2)
    assert win.original_root_tabs.currentIndex() == 4


def test_source_config_file_calib_are_visible_but_device_commands_disabled(source_window):
    win = source_window
    for index, name, widget_name, command in (
        (1, "PageConfig", "tcConfig", "bConfigUpload"),
        (5, "PageFile", "tcFileActions", None),
        (6, "PageCalib", "tcCalibResult", "bCalibStart"),
    ):
        win.original_root_tabs.setCurrentIndex(index)
        assert win.original_root_tabs.tabData(index) == name
        assert win.original_root_stack.currentIndex() != 0
        page = win.original_root_stack.currentWidget()
        assert page.findChild(QTabWidget, widget_name) is not None
        if command:
            button = page.findChild(QPushButton, command)
            assert button is not None and not button.isEnabled()


def test_original_source_task_launcher_and_channel_tabs(source_window):
    win = source_window
    assert win.original_start_launcher.objectName() == "SourcePageStartLauncher"
    assert win.original_start_launcher.findChild(QPushButton, "bTaskView") is not None
    assert win.original_start_launcher.findChild(QPushButton, "bTaskConnect") is not None
    assert win.original_start_launcher.findChild(QPushButton, "bTaskConfigCh") is not None
    btn_ip = win.original_start_launcher.findChild(QPushButton, "bTaskConfigIP")
    assert btn_ip is not None and not btn_ip.isEnabled()
    assert win.wave_channel_tabs.objectName() == "tcAdc"
    assert win.spec_channel_tabs.objectName() == "tcSpectrum"
    assert win.wave_channel_tabs.height() == 36
    assert win.spec_channel_tabs.height() == 36
    assert win.wave_channel_tabs.count() == win.adc.count()
    win._set_active(True)
    win.wave_channel_tabs.setCurrentIndex(6)
    assert win.adc.currentIndex() == 6
    assert win.spec_channel_tabs.currentIndex() == 6
    win.spec_channel_tabs.setCurrentIndex(2)
    assert win.adc.currentIndex() == 2
    assert win.wave_channel_tabs.currentIndex() == 2
    assert win.compat_toolbar.isHidden()


def test_stage111z31av_source_independent_status_page(source_window):
    win = source_window
    win.original_root_tabs.setCurrentIndex(2)
    assert win.original_root_stack.currentWidget().objectName() == "PageStatus"
    assert win.original_shell.status_tabs.objectName() == "tcStatus"
    assert win.original_shell.status_tabs.count() == 15
    assert win.original_shell.status_table.rowCount() >= 1
    assert "AUX/VALUES" in win.original_shell.status_note.text()
    # MODE_NAMES and calculated data continue to come from existing Stage28B.
    win.original_shell.status_tabs.setCurrentIndex(13)
    assert win.original_status_mode.currentIndex() == 13
    assert win.original_shell.status_table.rowCount() == 6
    assert win.original_shell.status_table.item(0, 0).text() == "ResultTacho"


def test_stage111z31av_pagefile_follows_real_archive_and_close(
        source_window, tmp_path):
    from .test_offline_core import fixture_zip
    win = source_window
    assert win.original_shell.file_channels.count() == 0
    win.open_archive(fixture_zip(tmp_path))
    assert win.session is not None
    assert win.original_shell.file_channels.count() == 8
    assert win.original_shell.file_channels.item(0).data(
        __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.UserRole) == 1
    assert win.original_shell.file_values.count() == 1
    win.original_root_tabs.setCurrentIndex(5)
    assert win.original_root_stack.currentWidget().objectName() == "PageFile"
    # The source channel list is operational, not decorative.
    win.original_shell.file_channels.setCurrentRow(3)
    assert win.adc.currentIndex() == 3
    win._close_session()
    assert win.session is None
    assert win.original_shell.file_channels.count() == 0
    assert win.original_shell.file_spec.count() == 0
    assert win.original_shell.file_values.count() == 0
    assert win.original_shell.status_note.text().startswith(
        "Нет подтверждённого AUX/VALUES")


def test_stage111z31av_original_title_research_and_config_readable(source_window):
    win = source_window
    assert win.windowTitle() == "ТПО МВК"
    assert win.task_subpages.tabBar().isHidden()
    win.research_tabs_action.setChecked(True)
    assert not win.task_subpages.tabBar().isHidden()
    win.research_tabs_action.setChecked(False)
    assert win.task_subpages.tabBar().isHidden()
    page = win.original_root_stack.widget(1)
    for button_name in (
        "bConfigLoad", "bConfigSave", "bConfigReset",
        "bConfigDownload", "bConfigUpload",
    ):
        control = page.findChild(QPushButton, button_name)
        assert control is not None
        assert control.minimumWidth() >= 112
        assert not control.isEnabled()
