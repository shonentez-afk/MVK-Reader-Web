"""Original DFM top-level tab shell keeps functional legacy spectrum Qt paths."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
from PySide6.QtCore import Qt
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
    # A BIN-only/empty session must NOT synthesize TACH register values.
    assert win.original_shell.status_table.rowCount() == 1
    assert win.original_shell.status_table.item(0, 0).text() == "Источник"


def test_stage111z31av_pagefile_follows_real_archive_and_close(
        source_window, tmp_path):
    from .test_offline_core import fixture_zip
    win = source_window
    assert win.original_shell.file_channels.count() == 0
    win.open_archive(fixture_zip(tmp_path))
    assert win.session is not None
    assert win.original_shell.file_channels.count() == 8
    assert win.original_shell.file_channels.item(0).data(Qt.UserRole) == 1
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
        # Delphi pnConfigButtons contains picture-only 48x48 buttons.
        assert control.width() == 48 and control.height() == 48
        assert control.text() == ""
        assert control.accessibleName()
        assert not control.icon().isNull()
        assert not control.isEnabled()


def test_stage111z31aw_source_control_rectangles_and_mode_menu(source_window):
    from mvk_compatible.core.original_ui_form_contract import (
        ORIGINAL_WAVE_CONTROLS, ORIGINAL_SPECTRUM_CONTROLS)
    win = source_window
    assert win.wave_source_canvas.objectName() == "DFMPageAdcSourceCanvas"
    assert win.spec_source_canvas.objectName() == "DFMPageSpectrumSourceCanvas"
    assert win.spec_type_button.objectName() == "bSpecTypePresenter"
    assert [a.data() for a in win._spec_type_actions] == [0,1,2,3]
    for spec, panel in (
        (ORIGINAL_WAVE_CONTROLS, win.wave_source_canvas),
        (ORIGINAL_SPECTRUM_CONTROLS, win.spec_source_canvas),
    ):
        actual={}
        for widget in panel.findChildren(QPushButton) + panel.findChildren(
                __import__("PySide6.QtWidgets", fromlist=["QToolButton"]).QToolButton) + panel.findChildren(
                __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel):
            source_name=widget.property("originalDfmControlName")
            if source_name:
                actual[source_name]=widget.geometry().getRect()
        # spec_lines and wave_type are split-button presenters, not hidden FFT/mode models.
        assert actual == {
            name: (x,y,w,h) for name,_,x,y,w,h in spec
        }
    win._spec_type_actions[2].trigger()
    assert win.spec_mode.currentIndex() == 2
    assert win.spec_type_button.text() == "Линейный ВС"
    assert win._spec_type_actions[2].isChecked()
    assert win.spec_mode.parentWidget() is not win.spec_source_canvas
    assert win.spec_n.parentWidget() is not win.spec_source_canvas


def test_stage111z31aw_page_status_source_chart_and_config_icons(
        source_window, tmp_path):
    import pyqtgraph as pg
    from .test_offline_core import fixture_zip
    from mvk_compatible.core.original_ui_form_contract import (
        ORIGINAL_CONFIG_TOOLBAR, ORIGINAL_CONFIG_TABS_DESIGN_TIME,
        ORIGINAL_STATUS_CHART, ORIGINAL_STATUS_SPLITTER)
    win=source_window
    page=win.original_root_stack.widget(1)
    tabs=page.findChild(QTabWidget, "tcConfig")
    assert tabs.count() == ORIGINAL_CONFIG_TABS_DESIGN_TIME == 2
    assert page.findChild(QTabWidget, "tcConfig") is tabs
    for name,x,y,w,h,image in ORIGINAL_CONFIG_TOOLBAR:
        button=page.findChild(QPushButton,name)
        assert button.geometry().getRect()==(x,y,w,h)
        assert button.property("originalDfmImageName")==image
        assert not button.isEnabled()
    win.open_archive(fixture_zip(tmp_path))
    win.original_root_tabs.setCurrentIndex(2)
    plot=win.original_shell.status_plot
    assert plot.objectName()=="chResult"
    assert win.original_shell.status_splitter.handleWidth()==ORIGINAL_STATUS_SPLITTER[2]
    assert ORIGINAL_STATUS_CHART[2]==400
    # In system mode there is no verified 43-bar plot.
    win.original_shell.status_tabs.setCurrentIndex(0)
    assert plot.isHidden()
    # Original tcStatus mode 5 is 43 third-octave bars of ADC1.
    win.original_shell.status_tabs.setCurrentIndex(5)
    assert not plot.isHidden()
    assert any(isinstance(item,pg.BarGraphItem)
               for item in plot.getPlotItem().items)
    assert win.original_shell.status_table.rowCount()==43
    win._close_session()
    assert plot.isHidden()
