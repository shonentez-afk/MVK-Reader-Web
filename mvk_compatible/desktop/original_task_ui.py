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
    """Five visible/hidden task launcher controls from PageStart in DFM."""
    home = window.task_subpages.widget(0)
    host = QWidget(home)
    host.setObjectName("SourcePageStartLauncher")
    grid = QGridLayout(host)
    grid.setContentsMargins(4, 0, 4, 0)
    grid.setHorizontalSpacing(40)
    grid.setVerticalSpacing(0)
    labels = {
        "bTaskConnect": "Подключение к прибору",
        "bTaskConfigCh": "Настройка каналов",
        "bTaskView": "Просмотр измерений",
        "bTaskConfigIP": "Настройка IP",
        "bTaskConfigCalib": "Калибровка",
    }
    position = {
        "bTaskConnect": (0, 0), "bTaskConfigCh": (0, 1),
        "bTaskView": (1, 0), "bTaskConfigIP": (1, 1),
        "bTaskConfigCalib": (2, 1),
    }
    for name, left, top, width, height, image in ORIGINAL_TASK_BUTTONS:
        b = QPushButton(labels[name], host)
        b.setObjectName(name)
        b.setFixedHeight(height)
        b.setMinimumWidth(width)
        # The DFM uses 86px VCL command-links with source ilTasks images.
        # Use a clearly marked platform icon until the private bitmaps have
        # been independently extracted/accepted (never invent vendor art).
        icon={
            "bTaskConnect":QStyle.SP_DriveNetIcon,
            "bTaskConfigCh":QStyle.SP_FileDialogDetailedView,
            "bTaskView":QStyle.SP_DialogOpenButton,
            "bTaskConfigIP":QStyle.SP_ComputerIcon,
            "bTaskConfigCalib":QStyle.SP_FileDialogContentsView,
        }[name]
        b.setIcon(b.style().standardIcon(icon))
        b.setIconSize(QSize(32,32))
        b.setProperty("originalDfmLogicalRect",(left,top,width,height))
        b.setProperty("originalDfmImageName",image)
        b.setToolTip(
            f"DFM {name} ({left},{top},{width},{height}); "
            f"ImageName={image}; original Caption='$' is runtime-translated.")
        if name == "bTaskView":
            # Original PageStart task opens the File workspace, not a
            # disconnected research dialog. Loading is available there.
            b.clicked.connect(lambda _checked=False:
                              navigation.setCurrentIndex(5))
        elif name == "bTaskConnect":
            b.clicked.connect(window.open_native_capture)
        elif name == "bTaskConfigCh":
            b.clicked.connect(lambda _checked=False: (
                window.original_config_panel.set_source_mode(6),
                navigation.setCurrentIndex(1)))
        elif name == "bTaskConfigIP":
            # Only open local read-only Mode4; no original callback/device I/O.
            b.setToolTip("Mode4 ConfigIP: просмотр локального файла, без прибора")
            b.clicked.connect(lambda _checked=False: (
                window.original_config_panel.set_source_mode(4),
                navigation.setCurrentIndex(1)))
        else:
            b.setEnabled(False)  # calibration remains gated
        if name == "bTaskConfigCalib":
            b.hide()  # original DFM Visible=False
        grid.addWidget(b, *position[name])
    grid.setColumnStretch(0, 301)
    grid.setColumnStretch(1, 458)
    host.setMinimumHeight(194)
    home.layout().insertWidget(2, host)
    # Old research shortcuts remain available as methods/test attributes,
    # but do not displace the source 5-button PageStart layout.
    for old in (window.task_open_button, window.task_capture_button,
                window.task_signal_button, window.task_spectrum_button,
                window.task_metrics_button):
        old.hide()
    return host
