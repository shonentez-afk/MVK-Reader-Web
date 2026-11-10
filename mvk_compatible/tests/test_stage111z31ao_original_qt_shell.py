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
