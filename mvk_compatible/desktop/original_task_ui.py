"""DFM PageStart task launcher and ADC/spectrum channel tabs, offline-safe.

The original DFM has a runtime-translated ('$') caption, so all Russian
captions here are semantic fallbacks and not verified original text.
"""
from __future__ import annotations
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QTabBar, QWidget, QGridLayout, QPushButton, QStyle
from ..core.original_ui_form_contract import (
    ORIGINAL_CHANNEL_TAB_HEIGHT, ORIGINAL_TASK_BUTTONS,
)
from .original_start_ui import OriginalStartController


def make_original_channel_tabs(window, object_name: str) -> QTabBar:
    tabs = QTabBar(window)
    tabs.setObjectName(object_name)
    tabs.setFixedHeight(ORIGINAL_CHANNEL_TAB_HEIGHT)
    tabs.setExpanding(False)
    # The offline importer currently enumerates eight ADC channels; the
    # original runtime builds its TTabControl names from device configuration.
    for i in range(window.adc.count()):
        tabs.addTab(window.adc.itemText(i))
    tabs.setCurrentIndex(window.adc.currentIndex())

    def from_tabs(index: int) -> None:
        # Never allow a hidden/disabled original ADC tab to point a valid
        # BIN-only channel at another channel's samples.
        if (0 <= index < tabs.count() and tabs.isTabEnabled(index)
                and index != window.adc.currentIndex()):
            window.adc.setCurrentIndex(index)

    def from_model(index: int) -> None:
        # Qt emits connected slots in order. Another earlier slot may have
        # already rejected this old ADC and restored the authoritative
        # source channel. Ignore a stale emitted INDEX instead of moving
        # either DFM tab bar backwards after the Core safety gate.
        if (0 <= index < tabs.count() and
                index == window.adc.currentIndex()
                and tabs.isTabEnabled(index)
                and index != tabs.currentIndex()):
            tabs.setCurrentIndex(index)

    tabs.currentChanged.connect(from_tabs)
    window.adc.currentIndexChanged.connect(from_model)
    return tabs


def install_source_task_buttons(window, navigation: QTabBar) -> QWidget:
    """Install exact original PageStart DFM buttons plus safe local library.

    Replaces the old approximate QGridLayout that compressed source button
    rectangles and lacked edIpAddr/edLibraryPath. It is one Qt client of the
    independent original_start_workbench Core validation/selection model.
    """
    controller=OriginalStartController(window,navigation)
    return controller.host
