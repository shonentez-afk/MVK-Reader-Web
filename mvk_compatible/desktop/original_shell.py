"""Stage111Z31AR: Original 7-page root navigation shell (DFM-derived).

Mirrors the Delphi ``TTabSheet`` layout from the original MVKView 1.0.47
DFM:

    PageStart   (Задачи)     — task launcher buttons
    PageConfig  (Настройка)  — parameter view/edit skeleton
    PageStatus  (Состояние)  — tcStatus / TStringGrid independent body
    PageAdc     (Сигнал)     — waveform primary controls
    PageSpectrum (Спектр)    — spectrum primary controls
    PageFile    (Файлы)      — archive / channel list
    PageCalib   (Калибровка) — calibration parameters/results

The Qt implementation uses a ``QTabWidget`` with **seven root tabs**
(177 px left tools, 24 px scrollbars, tab-height 44 per DFM contract).

Research-specific content (Обзор / Расчётные показатели / 43 полосы /
Диагностика / TACH / PageStatus) is hidden behind ``View -> Исследование``
and does **not** appear on the normal PageStart body.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QScrollArea,
)

if TYPE_CHECKING:
    from .main_window import MainWindow  # noqa: F821


# ---------------------------------------------------------------------------
# DFM contract constants
# ---------------------------------------------------------------------------
DFM_TAB_HEIGHT = 44          # Original TTabSheet tab height
DFM_LEFT_TOOLS_WIDTH = 177   # pnAdcTools / pnSpecTools width
DFM_SCROLLBAR_WIDTH = 24     # Original scrollbar line width
DFM_CHANNEL_TAB_HEIGHT = 36  # ADC channel tab height (ADC 1..8)
DFM_CONFIG_BUTTON_MIN_WIDTH = 120      # Not the broken 48px
DFM_CONFIG_BUTTON_MIN_HEIGHT = 44      # Matches task buttons
DFM_DESIGN_FONT_FAMILY = 'Segoe UI'
DFM_DESIGN_FONT_HEIGHT = 10


@dataclass(frozen=True)
class PageContract:
    """DFM-derived layout contract for a single root page."""
    name: str
    shortcut: str  # mnemonic
    has_left_tools: bool = False
    tools_width: int = DFM_LEFT_TOOLS_WIDTH
    has_scrollbar: bool = True
    has_channel_tabs: bool = False
    channel_tab_height: int = DFM_CHANNEL_TAB_HEIGHT


# Original 7-page contract
ORIGINAL_PAGES: list[PageContract] = [
    PageContract('PageStart', 'O', has_left_tools=False),
    PageContract('PageConfig', 'N', has_left_tools=False),
    PageContract('PageStatus', 'C', has_left_tools=False),
    PageContract('PageAdc', 'G', has_left_tools=True, tools_width=DFM_LEFT_TOOLS_WIDTH),
    PageContract('PageSpectrum', 'S', has_left_tools=True, tools_width=DFM_LEFT_TOOLS_WIDTH),
    PageContract('PageFile', 'F', has_left_tools=False),
    PageContract('PageCalib', 'K', has_left_tools=False),
]


class OriginalRootShell(QWidget):
    """Root container providing the 7-page ``QTabWidget`` layout.

    Connects to ``MainWindow`` via signals so that main_window.py can
    attach specific data-sources (OfflineSession, DirectBinSession)
    without duplicating page-navigation logic.
    """

    # Signals emitted on navigation / session changes
    page_changed = Signal(int, str)     # (index, page_name)
    session_opened = Signal(object)     # session object
    session_closed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)

        # Title bar (DFM caption + session info)
        self._title_bar = QHBoxLayout()
        self._title_label = QLabel('ТПО МВК')
        self._title_label.setObjectName('dfmTitle')
        self._title_label.setFont(QFont(DFM_DESIGN_FONT_FAMILY, DFM_DESIGN_FONT_HEIGHT))
        self._title_label.setStyleSheet('font-weight: bold; padding: 2px 8px;')
        self._session_label = QLabel('Сеанс не выбран')
        self._session_label.setObjectName('sessionInfo')
        self._session_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._title_bar.addWidget(self._title_label)
        self._title_bar.addWidget(self._session_label)
        self._title_bar.addStretch()
        self._layout.addLayout(self._title_bar)

        # 7-page QTabWidget
        self.tabs = QTabWidget()
        self.tabs.setObjectName('originalRootTabs')
        self.tabs.setTabPosition(QTabWidget.North)
        self._build_pages()
        self._layout.addWidget(self.tabs, 1)

        # Status bar
        from PySide6.QtWidgets import QStatusBar
        self._status_bar = QStatusBar()
        self._status_bar.setObjectName('dfmStatusBar')
        self._layout.addWidget(self._status_bar)

        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _build_pages(self):
        """Create all 7 root pages from ORIGINAL_PAGES contract."""
        # PageStart - task launcher
        page_start = self._build_page_start()
        self.tabs.addTab(page_start, 'Задачи')

        # PageConfig - parameters view
        page_config = self._build_page_config()
        self.tabs.addTab(page_config, 'Настройка')

        # PageStatus - independent tcStatus body
        page_status = self._build_page_status()
        self.tabs.addTab(page_status, 'Состояние')

        # PageAdc - waveform
        page_adc = self._build_page_adc()
        self.tabs.addTab(page_adc, 'Сигнал')

        # PageSpectrum - spectrum
        page_spectrum = self._build_page_spectrum()
        self.tabs.addTab(page_spectrum, 'Спектр')

        # PageFile - archive / channels
        page_file = self._build_page_file()
        self.tabs.addTab(page_file, 'Файлы')

        # PageCalib - calibration
        page_calib = self._build_page_calib()
        self.tabs.addTab(page_calib, 'Калибровка')

    def _build_page_start(self) -> QWidget:
        """DFM PageStart: task launcher with 5 original buttons."""
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)

        header = QLabel('MVKView Compatible - просмотр измерений')
        header.setObjectName('taskHomeHeading')
        header.setStyleSheet('font-size: 19px; font-weight: 600;')
        lay.addWidget(header)

        # Original DFM buttons: bTaskConnect, bTaskConfigCh, bTaskView,
        # bTaskConfigIP, and hidden bTaskConfigCalib
        self.bTaskConnect = self._task_button('Открыть измерение...', 'Открыть ZIP/BIN/TSXML файл')
        self.bTaskConfigCh = self._task_button('Настройка каналов', 'Настройка каналов (исследование)')
        self.bTaskView = self._task_button('Временной сигнал', 'Перейти к вкладке Сигнал')
        self.bTaskConfigIP = self._task_button('Спектр', 'Перейти к вкладке Спектр')
        # Hidden by DFM
        self.bTaskConfigCalib = self._task_button('Калибровка', 'Перейти к вкладке Калибровка', visible=False)

        for btn in (self.bTaskConnect, self.bTaskConfigCh,
                     self.bTaskView, self.bTaskConfigIP):
            lay.addWidget(btn)

        # Note
        note = QLabel(
            'Команды настройки прибора и калибровка недоступны. '
            'Запись с прибора - через проверенный Native R6.1. '
            'Оригинальные команды МВК не отправляются.')
        note.setObjectName('taskDeviceOfflineNotice')
        note.setWordWrap(True)
        note.setStyleSheet('color:#776235; padding-top:10px;')
        lay.addWidget(note)
        lay.addStretch()
        return widget

    def _build_page_config(self) -> QWidget:
        """DFM PageConfig: parameter table with properly-sized buttons."""
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(12, 12, 12, 12)

        header = QLabel('Настройка - параметры прибора')
        header.setObjectName('pageConfigHeader')
        lay.addWidget(header)

        # Parameter table (read-only offline)
        self.config_table = QTableWidget(0, 3)
        self.config_table.setObjectName('tcConfig')
        self.config_table.setHorizontalHeaderLabels(['Параметр', 'Значение', 'Ед.изм'])
        self.config_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.config_table.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self.config_table, 1)

        # Action buttons - NOT the broken 48px width
        btn_h = DFM_CONFIG_BUTTON_MIN_HEIGHT
        btn_w = DFM_CONFIG_BUTTON_MIN_WIDTH
        btn_layout = QHBoxLayout()

        self.btnConfigLoad = self._styled_button('Загрузить', btn_w, btn_h,
                                                  'Открыть файл параметров')
        self.btnConfigSave = self._styled_button('Сохранить', btn_w, btn_h,
                                                  'Сохранить параметры')
        self.btnConfigGet = self._styled_button('Получить', btn_w, btn_h,
                                                 'Получить с прибора (недоступно)')
        self.btnConfigGet.setEnabled(False)

        for btn in (self.btnConfigLoad, self.btnConfigSave, self.btnConfigGet):
            btn_layout.addWidget(btn)
        btn_layout.addStretch()
        lay.addLayout(btn_layout)
        return widget

    def _build_page_status(self) -> QWidget:
        """DFM PageStatus: independent tcStatus / TStringGrid body.

        This is NOT a subpage of PageStart - it is a **root** tab with
        its own data source and display logic.
        """
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(12, 12, 12, 12)

        header = QHBoxLayout()
        header.addWidget(QLabel('Режим tcStatus (исходный IDR):'))
        self.status_mode = QComboBox()
        from ..core.original_pagestatus_source import MODE_NAMES
        self.status_mode.addItems(list(MODE_NAMES.values()))
        self.status_mode.setObjectName('tcStatusMode')
        header.addWidget(self.status_mode)
        header.addStretch()
        lay.addLayout(header)

        self.status_note = QLabel()
        self.status_note.setObjectName('statusNote')
        self.status_note.setWordWrap(True)
        lay.addWidget(self.status_note)

        self.status_table = QTableWidget(0, 2)
        self.status_table.setObjectName('tcStatus')
        self.status_table.setHorizontalHeaderLabels(['Показатель', 'Значение'])
        self.status_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.status_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.status_table, 2)

        return widget

    def _build_page_adc(self) -> QWidget:
        """DFM PageAdc: waveform with 177 px left tools."""
        widget = QWidget()
        root = QHBoxLayout(widget)
        root.setContentsMargins(4, 6, 4, 4)
        root.setSpacing(4)

        # Left tools panel
        panel = QWidget()
        panel.setObjectName('pnAdcTools')
        panel.setFixedWidth(DFM_LEFT_TOOLS_WIDTH)
        left = QVBoxLayout(panel)
        left.setContentsMargins(6, 7, 6, 7)
        left.setSpacing(5)

        # Envelope button
        self.bAdcEnvelopeType = QPushButton('Без фильтра')
        self.bAdcEnvelopeType.setObjectName('bAdcEnvelopeType')
        self.bAdcEnvelopeType.setFixedHeight(37)
        left.addWidget(self.bAdcEnvelopeType)

        # Type button
        self.bAdcType = QPushButton('AC - без DC')
        self.bAdcType.setObjectName('bAdcType')
        self.bAdcType.setFixedHeight(37)
        left.addWidget(self.bAdcType)

        # HScale button
        self.bAdcHScale = QPushButton('Шкала X')
        self.bAdcHScale.setObjectName('bAdcHScale')
        self.bAdcHScale.setFixedHeight(37)
        left.addWidget(self.bAdcHScale)

        # VScale button
        self.bAdcVScale = QPushButton('Шкала Y - авто')
        self.bAdcVScale.setObjectName('bAdcVScale')
        self.bAdcVScale.setFixedHeight(37)
        left.addWidget(self.bAdcVScale)

        # Cursor label
        self.lbAdcHint = QLabel('Курсор: -')
        self.lbAdcHint.setObjectName('lbAdcHint')
        self.lbAdcHint.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.lbAdcHint.setFixedHeight(55)
        self.lbAdcHint.setTextInteractionFlags(Qt.TextSelectableByMouse)
        left.addWidget(self.lbAdcHint)

        # Mean label
        self.lbMean = QLabel('СКЗ сигнала: -')
        self.lbMean.setObjectName('lbAdcMean')
        self.lbMean.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.lbMean.setFixedHeight(83)
        self.lbMean.setWordWrap(True)
        self.lbMean.setTextInteractionFlags(Qt.TextSelectableByMouse)
        left.addWidget(self.lbMean)

        left.addStretch()
        root.addWidget(panel, 0)

        # Graph placeholder
        scroll = QScrollArea()
        scroll.setObjectName('adcScroll')
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(400)
        self.adc_graph = QLabel('График временного сигнала')
        self.adc_graph.setObjectName('pcAdc')
        self.adc_graph.setStyleSheet('background:#ffffff; border:1px solid #ccc;')
        scroll.setWidget(self.adc_graph)
        root.addWidget(scroll, 1)
        return widget

    def _build_page_spectrum(self) -> QWidget:
        """DFM PageSpectrum: spectrum with 177 px left tools."""
        widget = QWidget()
        root = QHBoxLayout(widget)
        root.setContentsMargins(4, 6, 4, 4)
        root.setSpacing(4)

        # Left tools panel
        panel = QWidget()
        panel.setObjectName('pnSpecTools')
        panel.setFixedWidth(DFM_LEFT_TOOLS_WIDTH)
        left = QVBoxLayout(panel)
        left.setContentsMargins(6, 7, 6, 7)
        left.setSpacing(5)

        self.bSpecEnvelopeType = QPushButton('Без фильтра')
        self.bSpecEnvelopeType.setObjectName('bSpecEnvelopeType')
        self.bSpecEnvelopeType.setEnabled(False)  # disabled without profile
        self.bSpecEnvelopeType.setFixedHeight(37)
        left.addWidget(self.bSpecEnvelopeType)

        self.bSpecMode = QPushButton('Логарифмич.')
        self.bSpecMode.setObjectName('bSpecMode')
        self.bSpecMode.setFixedHeight(37)
        left.addWidget(self.bSpecMode)

        self.bSpecHScale = QPushButton('Шкала X')
        self.bSpecHScale.setObjectName('bSpecHScale')
        self.bSpecHScale.setFixedHeight(37)
        left.addWidget(self.bSpecHScale)

        self.bSpecVScale = QPushButton('Шкала Y')
        self.bSpecVScale.setObjectName('bSpecVScale')
        self.bSpecVScale.setFixedHeight(37)
        left.addWidget(self.bSpecVScale)

        self.lbSpecHint = QLabel('Курсор: -')
        self.lbSpecHint.setObjectName('lbSpecHint')
        self.lbSpecHint.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.lbSpecHint.setFixedHeight(55)
        self.lbSpecHint.setTextInteractionFlags(Qt.TextSelectableByMouse)
        left.addWidget(self.lbSpecHint)

        left.addStretch()
        root.addWidget(panel, 0)

        # Graph placeholder
        scroll = QScrollArea()
        scroll.setObjectName('specScroll')
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(400)
        self.spec_graph = QLabel('График спектра')
        self.spec_graph.setObjectName('pcSpectrum')
        self.spec_graph.setStyleSheet('background:#ffffff; border:1px solid #ccc;')
        scroll.setWidget(self.spec_graph)
        root.addWidget(scroll, 1)
        return widget

    def _build_page_file(self) -> QWidget:
        """DFM PageFile: archive list with 369/8/615 splitter."""
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(4, 4, 4, 4)

        header = QLabel('Файлы - архивы и каналы')
        lay.addWidget(header)

        # Splitter: left spacer / file list / right spacer
        file_layout = QHBoxLayout()
        file_layout.addLayout(QHBoxLayout(), 0)  # left spacer

        # Channel list
        self.file_channels = QTableWidget(0, 4)
        self.file_channels.setObjectName('tblChannels')
        self.file_channels.setHorizontalHeaderLabels([
            'Канал', 'Файл', 'Длина (отсчётов)', 'Fs (Гц)'])
        self.file_channels.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.file_channels.setEditTriggers(QTableWidget.NoEditTriggers)
        file_layout.addWidget(self.file_channels, 1)

        # File archive list
        self.file_archive = QTableWidget(0, 3)
        self.file_archive.setObjectName('tblArchive')
        self.file_archive.setHorizontalHeaderLabels([
            'Файл', 'Размер', 'Дата'])
        self.file_archive.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.file_archive.setEditTriggers(QTableWidget.NoEditTriggers)
        file_layout.addWidget(self.file_archive, 0)

        lay.addLayout(file_layout)

        # Status
        self.file_status = QLabel('Открыть архив для отображения каналов')
        self.file_status.setObjectName('fileStatus')
        self.file_status.setStyleSheet('color:#9e6500; padding:4px;')
        lay.addWidget(self.file_status)
        return widget

    def _build_page_calib(self) -> QWidget:
        """DFM PageCalib: calibration parameters/results skeleton."""
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(12, 12, 12, 12)

        header = QLabel('Калибровка - параметры и результаты')
        lay.addWidget(header)

        # Parameters
        calib_params = QLabel('Параметры калибровки:')
        lay.addWidget(calib_params)
        self.calib_table = QTableWidget(0, 3)
        self.calib_table.setObjectName('tblCalib')
        self.calib_table.setHorizontalHeaderLabels(['Параметр', 'Значение', 'Статус'])
        self.calib_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.calib_table.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self.calib_table, 1)

        # Status
        self.calib_status = QLabel(
            'Калибровка недоступна офлайн. Данные калибровки загружаются '
            'только через Native R6.1 с подтверждением.')
        self.calib_status.setObjectName('calibStatus')
        self.calib_status.setStyleSheet('color:#9e6500; padding:4px;')
        lay.addWidget(self.calib_status)
        return widget

    # --- helpers ---
    def _task_button(self, text: str, tooltip: str, visible: bool = True) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName(f'bTask{text}')
        btn.setMinimumHeight(DFM_CONFIG_BUTTON_MIN_HEIGHT)
        btn.setToolTip(tooltip)
        btn.setVisible(visible)
        return btn

    def _styled_button(self, text: str, min_width: int, min_height: int,
                       tooltip: str = '') -> QPushButton:
        btn = QPushButton(text)
        btn.setMinimumWidth(min_width)
        btn.setMinimumHeight(min_height)
        btn.setToolTip(tooltip)
        return btn

    def _on_tab_changed(self, index: int):
        page_name = ORIGINAL_PAGES[index].name if index < len(ORIGINAL_PAGES) else ''
        self.page_changed.emit(index, page_name)

    def set_session_info(self, serial: str, channels: int, source: str):
        self._session_label.setText(
            f'{serial} - {channels} ADC - {source}')

    def update_pagefile_channels(self, channels: list[dict]):
        """Update PageFile channel table from session data."""
        tbl = self.file_channels
        tbl.setRowCount(len(channels))
        for i, ch in enumerate(channels):
            tbl.setItem(i, 0, QTableWidgetItem(str(ch.get('adc', '-'))))
            tbl.setItem(i, 1, QTableWidgetItem(ch.get('file', '-')))
            tbl.setItem(i, 2, QTableWidgetItem(str(ch.get('length', '-'))))
            tbl.setItem(i, 3, QTableWidgetItem(str(ch.get('fs', '-'))))
        tbl.resizeRowsToContents()
        self.file_status.setText(f'Каналов: {len(channels)}')

    def clear_pagefile(self):
        """Reset PageFile on session close."""
        self.file_channels.setRowCount(0)
        self.file_archive.setRowCount(0)
        self.file_status.setText('Открыть архив для отображения каналов')

    def set_pagestatus_data(self, model):
        """Set PageStatus table from a PageStatusTableModel."""
        tbl = self.status_table
        tbl.clearContents()
        tbl.setColumnCount(len(model.headers))
        tbl.setRowCount(len(model.rows))
        tbl.setHorizontalHeaderLabels(list(model.headers))
        for row, record in enumerate(model.rows):
            for col, value in enumerate(record):
                tbl.setItem(row, col, QTableWidgetItem(str(value)))
        self.status_note.setText(model.note)

    def get_current_page_name(self) -> str:
        idx = self.tabs.currentIndex()
        return ORIGINAL_PAGES[idx].name if idx < len(ORIGINAL_PAGES) else ''
