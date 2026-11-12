"""DFM-derived seven-page shell around the existing working three-tab Qt core.

The real original Form includes seven TTabSheets and 44px tabs.  The existing
archive/wave/spectrum implementations remain untouched and routable through
an invisible legacy three-tab QTabWidget. Unlike the original instrument,
unsafe device/configuration/calibration buttons remain disabled.

MainWindow still exposes .tabs (the legacy three tabs), preserving its
calculation, callback and automated test interfaces.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QListWidget, QPlainTextEdit, QPushButton,
    QSplitter, QStackedWidget, QTabBar, QTabWidget, QTableWidget,
    QHeaderView, QSpinBox, QSlider, QLineEdit, QFileDialog,
    QTableWidgetItem, QListWidgetItem, QStyle, QVBoxLayout, QWidget,
)

from .original_task_ui import install_source_task_buttons
from .original_config_readonly_ui import OriginalConfigReadOnlyPanel
from .original_windowman_form import OriginalWindowMan
from .original_measure_controls_ui import OriginalMeasureControls
from .original_calibration_ui import build_original_calibration_page, OriginalCalibrationPanel
from ..core.original_offline_view_state import OriginalOfflineView, PAGES, HORIZONTAL_HZ
import pyqtgraph as pg
from ..core.original_pagestatus_source import MODE_NAMES, source_pagestatus_table
from ..core.original_status_workbench import (
    ORIGINAL_STATUS_GRIDS,source_status_projection,export_verified_status_csv,
)
from ..core.original_file_workbench import source_file_workbench
from ..core.original_pagefile_recording import (
    OriginalPageFileSelection,OriginalFileNameOptions,
    export_selected_original_pagefile,ORIGINAL_SOURCE_DEFAULT_FOLDER_TEMPLATE,
    CHANNEL_COUNT,SPEC_COUNT,VALUE_COUNT,ADC_VALUE_COUNT,BAND_VALUE_COUNT,
    TACH_RESULT_COUNT,ORIGINAL_DFM_FILE_ADC_HEIGHT,
)
from ..core.original_pagestatus_source import TACH_FIELDS
from ..core.original_view_time_source import source_view_time, source_linked_caption

from ..core.original_ui_form_contract import (
    ORIGINAL_ROOT_PAGES, ORIGINAL_ROOT_TAB_HEIGHT,
    ORIGINAL_FILE_SPLITTER_LEFT, ORIGINAL_CALIB_SPLITTER_LEFT,
    ORIGINAL_CONFIG_TOOLBAR, ORIGINAL_CONFIG_TABS_DESIGN_TIME,
    ORIGINAL_STATUS_CHART, ORIGINAL_STATUS_SPLITTER,
)


def _text(parent: QWidget, value: str) -> QLabel:
    label = QLabel(value, parent)
    label.setWordWrap(True)
    return label


def _disabled(name: str, caption: str, parent: QWidget) -> QPushButton:
    b = QPushButton(caption, parent)
    b.setObjectName(name)
    b.setEnabled(False)
    b.setToolTip(
        "Исходное имя/положение из Delphi DFM; взаимодействие с прибором "
        "не реализовано и не имитируется.")
    return b


def _readonly_grid(name: str, parent: QWidget) -> QTableWidget:
    grid = QTableWidget(0, 0, parent)
    grid.setObjectName(name)
    grid.setEditTriggers(QTableWidget.NoEditTriggers)
    return grid


def _config_page(parent: QWidget) -> QWidget:
    """Original DFM pnConfig: five IMAGE-ONLY 48x48 buttons, two tab modes.

    User screenshots exposed a Qt regression: forcing translated text inside
    original picture buttons clips labels. Keep the exact DFM geometry and
    show a system-standard icon, with accessible Russian hints. Source
    private ilButtons bitmap data is deliberately not redistributed.
    """
    page = QWidget(parent)
    page.setObjectName("PageConfig")
    lay = QVBoxLayout(page)
    lay.setContentsMargins(4, 4, 4, 4)
    top = QWidget(page)
    top.setObjectName("pnConfig")
    top.setFixedHeight(60)
    top.setStyleSheet("QWidget#pnConfig {background: palette(base);}")
    buttons = QWidget(top)
    buttons.setObjectName("pnConfigButtons")
    buttons.setGeometry(0, 0, 297, 60)
    captions = {
        "bConfigLoad": ("Загрузить конфигурацию", QStyle.SP_DialogOpenButton),
        "bConfigSave": ("Сохранить конфигурацию", QStyle.SP_DialogSaveButton),
        "bConfigReset": ("Сбросить настройки", QStyle.SP_BrowserReload),
        "bConfigDownload": ("Получить конфигурацию из прибора", QStyle.SP_ArrowDown),
        "bConfigUpload": ("Передать конфигурацию в прибор", QStyle.SP_ArrowUp),
    }
    for source_name, left, top_px, width, height, image in ORIGINAL_CONFIG_TOOLBAR:
        description, standard_icon = captions[source_name]
        control = _disabled(source_name, "", buttons)
        control.setText("")  # The original renders bitmap-only in 48x48.
        control.setFixedSize(width, height)
        control.move(left, top_px)
        control.setIcon(control.style().standardIcon(standard_icon))
        control.setIconSize(QSize(24, 24))
        control.setAccessibleName(description)
        control.setToolTip(
            f"{description}. Оригинал: ilButtons/{image}; "
            "безопасный офлайн-режим, команды прибору отключены.")
        control.setProperty("originalDfmLogicalRect",
                            (left, top_px, width, height))
        control.setProperty("originalDfmImageName", image)
    result_label = _text(top, "Config-Result")
    result_label.setObjectName("lbConfigResult")
    result_label.setGeometry(309, 12, 400, 36)
    result_label.hide()  # Original lbConfigResult.Visible=False
    lay.addWidget(top)
    pages = QTabWidget(page)
    pages.setObjectName("tcConfig")
    # Source tcConfig has exactly TWO TabStrings '$'; tabConfigBasic is
    # a sibling TStringGrid, not an invented third tab control mode.
    for name, fallback in (
        ("tabConfigChannels", "Каналы"),
        ("tabConfigAlarms", "Тревоги"),
    ):
        pages.addTab(_readonly_grid(name, pages), fallback)
    assert pages.count() == ORIGINAL_CONFIG_TABS_DESIGN_TIME
    lay.addWidget(pages, 1)
    basic = _readonly_grid("tabConfigBasic", page)
    lay.addWidget(basic, 1)  # original sibling, not a tcConfig tab
    basic.hide()  # Offline no verified original basic-grid dispatch.
    note=_text(page,
        "Настройка: два оригинальных режима tcConfig и отдельный Basic. "
        "Локальная конфигурация: Загрузить → mvkeditform → Сохранить в новый "
        "текстовый файл. Передача/сброс прибора отключены.")
    note.setObjectName("sourceConfigEvidence")
    lay.addWidget(note)
    return page


def _file_page(parent: QWidget, open_offline) -> QWidget:
    """Source DFM PageFile: 369/8/615 split, ten checks, TWO action modes.

    _Unit128:0084845C, original tcFileActions index0 = 43 SPEC /
    24+43+6 VALUES checklists; index1 = pnFileAdc 207px with three
    checked source checkboxes and two conditional text fields.
    Extra offline controls live OUTSIDE the original DFM widgets.
    """
    page=QWidget(parent)
    page.setObjectName("PageFile")
    lay=QVBoxLayout(page)
    lay.setContentsMargins(4,4,4,4)
    shortcuts=QWidget(page)
    shortcuts.setObjectName("sourceFileActionBar")
    route=QHBoxLayout(shortcuts)
    route.setContentsMargins(2,2,2,4)
    for name,title in (
        ("fileGoSignal","Временной сигнал"),
        ("fileGoSpectrum","Спектр"),
        ("fileGoStatus","Расчётные данные")):
        button=QPushButton(title,shortcuts)
        button.setObjectName(name)
        button.setEnabled(False)
        button.setToolTip("Связанный исходный канал из той же проверенной записи")
        route.addWidget(button)
    export=QPushButton("Сохранить выбранное локально…",shortcuts)
    export.setObjectName("pageFileExportSelectedSource")
    export.setEnabled(False)
    export.setToolTip(
        "Исходные чек-листы PageFile: настоящий отбор проверенных BIN/TSXML "
        "и измеренных VALUES/SPEC в НОВУЮ папку. НЕ команда прибору.")
    route.addWidget(export)
    route.addStretch(1)
    route.addWidget(QLabel("VALUES:",shortcuts))
    tick=QSpinBox(shortcuts)
    tick.setObjectName("fileValuesTick")
    tick.setRange(1,1)
    tick.setEnabled(False)
    tick.setToolTip("Выбранный проверенный тик Native R6.1, без выдуманных AUX")
    route.addWidget(tick)
    lay.addWidget(shortcuts)
    summary=QLabel("Измерение не выбрано. Откройте проверенный ZIP/BIN.",page)
    summary.setObjectName("sourceFileSummary")
    summary.setWordWrap(True)
    summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
    lay.addWidget(summary)
    split=QSplitter(Qt.Horizontal,page)
    split.setObjectName("splFile")
    split.setHandleWidth(8)
    left=QTabWidget(split)
    left.setObjectName("tcFileChannels")
    left.tabBar().setFixedHeight(36)
    channel_host=QWidget(left)
    left_lay=QVBoxLayout(channel_host)
    channels=QListWidget(channel_host)
    channels.setObjectName("cbFileChannels")
    channels.setUniformItemSizes(True)
    left_lay.addWidget(channels,1)
    open_button=QPushButton("Открыть локальную запись…",channel_host)
    open_button.setObjectName("openOfflineMeasurement")
    open_button.clicked.connect(open_offline)
    left_lay.addWidget(open_button)
    left.addTab(channel_host,"Каналы · 8 АЦП + 2 TACH")
    assert left.count()==1

    right=QTabWidget(split)
    right.setObjectName("tcFileActions")
    right.tabBar().setFixedHeight(36)
    source_result=QWidget(right)
    results_lay=QVBoxLayout(source_result)
    results_lay.setContentsMargins(4,4,4,4)
    groups=QSplitter(Qt.Horizontal,source_result)
    groups.setObjectName("splFileValues")
    groups.setHandleWidth(8)
    spec_list=QListWidget(groups)
    spec_list.setObjectName("cbFileSpec")
    spec_list.setUniformItemSizes(True)
    values_list=QListWidget(groups)
    values_list.setObjectName("cbFileValues")
    values_list.setUniformItemSizes(True)
    groups.addWidget(spec_list)
    groups.addWidget(values_list)
    groups.setSizes([256,343])
    results_lay.addWidget(groups,1)
    right.addTab(source_result,"Выбор SPEC / VALUES")

    source_adc=QWidget(right)
    adc_lay=QVBoxLayout(source_adc)
    adc_lay.setContentsMargins(4,4,4,4)
    panel=QWidget(source_adc)
    panel.setObjectName("pnFileAdc")
    panel.setFixedHeight(ORIGINAL_DFM_FILE_ADC_HEIGHT)
    def _check(name,label,x,y,w=577):
        b=QCheckBox(label,panel)
        b.setObjectName(name)
        b.setGeometry(x,y,w,17)
        b.setChecked(True)  # DFM Checked=True
        return b
    def _text_field(name,x,y,w=225):
        ed=QLineEdit(panel)
        ed.setObjectName(name)
        ed.setGeometry(x,y,w,24)
        return ed
    write_xml=_check("cbFileWriteXml","Дополнительно TSXML",16,16)
    folder_prefix=_check("cbFileFolderPrefix","Префикс каталога",16,56)
    folder_label=QLabel("Префикс каталога:",panel)
    folder_label.setObjectName("lbFolderPrefix")
    folder_label.setGeometry(16,82,169,21)
    folder_edit=_text_field("edFolderPrefix",176,79)
    folder_edit.setText(ORIGINAL_SOURCE_DEFAULT_FOLDER_TEMPLATE)
    folder_edit.setToolTip(
        'Исходная строка из _Unit128: "RunUp"dd-mm-yyyy hh-nn-ss. '
        'В локальном экспорте подставляется время операции сохранения '
        '(не прибора). Можно ввести безопасный явный префикс.')
    device_name=_check("cbFileMvkName","Указать имя прибора",16,120)
    device_label=QLabel("Имя прибора:",panel)
    device_label.setObjectName("lbFileMvkName")
    device_label.setGeometry(16,146,169,21)
    device_edit=_text_field("edFileMvkName",176,143)
    device_edit.setToolTip("Локальное имя папки, не команда смены имени прибора")
    file_prefix_label=QLabel("Префикс файла:",panel)
    file_prefix_label.setObjectName("lbFilePrefix")
    file_prefix_label.setGeometry(16,176,169,21)
    file_prefix_label.hide()
    file_prefix_edit=_text_field("edFilePrefix",176,173)
    file_prefix_edit.hide()  # DFM Visible=False for BOTH controls
    folder_prefix.toggled.connect(folder_edit.setEnabled)
    device_name.toggled.connect(device_edit.setEnabled)
    adc_lay.addWidget(panel)
    note=QLabel(
        "Параметры исходной панели записи АЦП. Сохраняют выбранные "
        "данные уже существующего файла. bWriteAdc/bWriteValues исходного "
        "TMVKThread пока НЕ управляют Native R6.1.",source_adc)
    note.setWordWrap(True)
    note.setObjectName("sourceFileOfflineCaptureNote")
    adc_lay.addWidget(note)
    adc_lay.addStretch(1)
    right.addTab(source_adc,"Параметры записи АЦП")
    assert right.count()==2
    split.addWidget(left)
    split.addWidget(right)
    split.setSizes([ORIGINAL_FILE_SPLITTER_LEFT,615])
    split.setChildrenCollapsible(False)
    lay.addWidget(split,1)

    # Extra compatible offline view, not a fabricated third tcFileActions tab.
    show_meta=QPushButton("Показать сведения об источнике",page)
    show_meta.setObjectName("pageFileToggleSourceDetails")
    show_meta.setCheckable(True)
    lay.addWidget(show_meta)
    metadata=QTableWidget(0,2,page)
    metadata.setObjectName("fileSourceMetadata")
    metadata.setHorizontalHeaderLabels(("Источник","Проверенное значение"))
    metadata.setEditTriggers(QTableWidget.NoEditTriggers)
    metadata.horizontalHeader().setSectionResizeMode(
        0,QHeaderView.ResizeToContents)
    metadata.horizontalHeader().setStretchLastSection(True)
    metadata.setMaximumHeight(175)
    metadata.setVisible(False)
    show_meta.toggled.connect(metadata.setVisible)
    show_meta.toggled.connect(
        lambda checked:show_meta.setText(
            "Скрыть сведения об источнике" if checked else
            "Показать сведения об источнике"))
    lay.addWidget(metadata)
    selection_status=QLabel(
        "Чек-листы записи: загрузите проверенное измерение",page)
    selection_status.setObjectName("sourcePageFileSelectionState")
    selection_status.setWordWrap(True)
    lay.addWidget(selection_status)
    evidence=QLabel("Источник: измерение не выбрано",page)
    evidence.setObjectName("sourceFileEvidence")
    evidence.setTextInteractionFlags(Qt.TextSelectableByMouse)
    evidence.setWordWrap(True)
    lay.addWidget(evidence)
    return page

def _status_page(parent: QWidget) -> QWidget:
    """Original 15-mode PageStatus with FOUR real TStringGrid identities.

    _Unit128:0084761A/008476B7/0084779C/008479FD/00847D58
    maps modes to tabStatus/tabAlarmResult/tabAllResult/tabResult,
    plus source chResult 43 bars only for ADC modes 5..12.
    Runtime tcStatus 15 modes; DFM design-time tab count 2.
    """
    page=QWidget(parent)
    page.setObjectName("PageStatus")
    layout=QVBoxLayout(page)
    layout.setContentsMargins(4,4,4,4)
    tabs=QTabBar(page)
    tabs.setObjectName("tcStatus")
    tabs.setExpanding(False)
    tabs.setUsesScrollButtons(True)
    tabs.setFixedHeight(36)
    for caption in MODE_NAMES:
        tabs.addTab(caption)
    layout.addWidget(tabs)
    split=QSplitter(Qt.Horizontal,page)
    split.setObjectName("splResult")
    split.setHandleWidth(ORIGINAL_STATUS_SPLITTER[2])
    plot=pg.PlotWidget(split)
    plot.setObjectName("chResult")
    plot.setMinimumWidth(320)
    plot.setBackground("w")
    plot.setMenuEnabled(False)
    plot.setMouseEnabled(x=False,y=False)
    plot.getPlotItem().setLabel("bottom","Полоса, индекс")
    plot.getPlotItem().setLabel("left","СКЗ (только источник)")
    plot.getPlotItem().setXRange(-0.5,42.5,padding=0)
    table_host=QStackedWidget(split)
    table_host.setObjectName("OriginalPageStatusGrids")
    grids={}
    for name in ORIGINAL_STATUS_GRIDS:
        grid=_readonly_grid(name,table_host)
        grid.verticalHeader().setDefaultSectionSize(20)
        grid.setAlternatingRowColors(True)
        grid.horizontalHeader().setStretchLastSection(True)
        table_host.addWidget(grid)
        grids[name]=grid
    split.addWidget(plot)
    split.addWidget(table_host)
    split.setChildrenCollapsible(False)
    split.setSizes([ORIGINAL_STATUS_CHART[2],580])
    layout.addWidget(split,1)

    readout=QLabel("Спектральный курсор: нет исходных полос",page)
    readout.setObjectName("sourceStatusBandReadout")
    readout.setTextInteractionFlags(Qt.TextSelectableByMouse)
    layout.addWidget(readout)
    bottom=QHBoxLayout()
    export=QPushButton("Локально сохранить исходную таблицу CSV…",page)
    export.setObjectName("localPageStatusExportVerifiedCsv")
    export.setEnabled(False)
    export.setToolTip(
        "Дополнительная офлайн-команда для проверенных Native VALUES/AUX. "
        "В оригинальном DFM bStatusSave не существует; никаких команд прибору.")
    bottom.addWidget(export)
    bottom.addStretch(1)
    note=QLabel("",page)
    note.setObjectName("sourceStatusNote")
    note.setWordWrap(True)
    note.setTextInteractionFlags(Qt.TextSelectableByMouse)
    bottom.addWidget(note,2)
    layout.addLayout(bottom)
    page.mode_tabs=tabs
    page.source_grids=grids
    page.source_grid=grids["tabStatus"]  # original mode0 compatibility
    page.source_grid_stack=table_host
    page.source_plot=plot
    page.source_splitter=split
    page.source_note=note
    page.source_cursor=readout
    page.source_export=export
    return page


def _calib_page(parent: QWidget) -> QWidget:
    """Source PageCalib DFM: functional 49-step, 77x11, two-mode worksheet."""
    return build_original_calibration_page(parent)


class OriginalRootShell:
    """Map 7 original DFM page identities onto existing Qt functional pages."""

    def __init__(self, window, layout):
        self.window = window
        self._routing = False
        # Portable controller/client-independent source view contract.
        # This observes safe UI state only; it never controls original or
        # attached instrument, and cannot re-enable blocked device controls.
        self.view_state=OriginalOfflineView.initial()
        window.source_view_state=self.view_state
        self.navigation = QTabBar(window)
        self.navigation.setObjectName("Pages")
        self.navigation.setExpanding(True)
        self.navigation.setDrawBase(False)
        self.navigation.setFixedHeight(ORIGINAL_ROOT_TAB_HEIGHT)
        self.navigation.setDocumentMode(False)
        for page in ORIGINAL_ROOT_PAGES:
            i = self.navigation.addTab(page.fallback_title_ru)
            self.navigation.setTabData(i, page.object_name)
            self.navigation.setTabToolTip(
                i, f"Original Delphi {page.object_name}; icon ImageName={page.image_name}. "
                   "Русский заголовок уточняется по runtime-переводам.")

        self.stack = QStackedWidget(window)
        self.stack.setObjectName("OriginalPageBodies")
        layout.removeWidget(window.tabs)
        self.stack.addWidget(window.tabs)  # index 0, existing work preserved
        self.stack.addWidget(_config_page(window))          # index 1
        self.config_page=self.stack.widget(1)
        self.config_panel=OriginalConfigReadOnlyPanel(self.config_page)
        window.original_config_panel=self.config_panel
        window.original_window_man=OriginalWindowMan(window)
        self.stack.addWidget(_file_page(window, window.choose_archive))  # 2
        self.stack.addWidget(_calib_page(window))           # index 3
        self.calib_page=self.stack.widget(3)
        self.calib_panel=OriginalCalibrationPanel(self.calib_page,window)
        window.original_calib_panel=self.calib_panel
        self.stack.addWidget(_status_page(window))          # index 4
        self.status_page = self.stack.widget(4)
        self.status_tabs = self.status_page.mode_tabs
        self.status_table = self.status_page.source_grid
        self.status_grids = self.status_page.source_grids
        self.status_grid_stack = self.status_page.source_grid_stack
        self.status_cursor = self.status_page.source_cursor
        self.status_export = self.status_page.source_export
        self._source_status_projection = None
        self.status_plot = self.status_page.source_plot
        self.status_splitter = self.status_page.source_splitter
        self.status_note = self.status_page.source_note
        self.file_page = self.stack.widget(2)
        self.file_channels = self.file_page.findChild(QListWidget, "cbFileChannels")
        self.file_spec = self.file_page.findChild(QListWidget, "cbFileSpec")
        self.file_values = self.file_page.findChild(QListWidget, "cbFileValues")
        self.file_source_evidence = self.file_page.findChild(
            QLabel, "sourceFileEvidence")
        self.file_summary = self.file_page.findChild(
            QLabel, "sourceFileSummary")
        self.file_metadata = self.file_page.findChild(
            QTableWidget, "fileSourceMetadata")
        self.file_tick=self.file_page.findChild(QSpinBox,"fileValuesTick")
        self.file_record_selection=None
        self.file_export_button=self.file_page.findChild(
            QPushButton,"pageFileExportSelectedSource")
        self.file_action_tabs=self.file_page.findChild(
            QTabWidget,"tcFileActions")
        self.file_selection_status=self.file_page.findChild(
            QLabel,"sourcePageFileSelectionState")
        self.file_capture_panel=self.file_page.findChild(
            QWidget,"pnFileAdc")
        self.file_record_flags={
            name:self.file_page.findChild(QCheckBox,name)
            for name in ("cbFileWriteXml","cbFileFolderPrefix","cbFileMvkName")}
        self.file_record_names={
            name:self.file_page.findChild(QLineEdit,name)
            for name in ("edFolderPrefix","edFileMvkName","edFilePrefix")}
        self.file_action_buttons = {
            name:self.file_page.findChild(QPushButton,name)
            for name in ("fileGoSignal","fileGoSpectrum","fileGoStatus")}
        if (self.file_summary is None or self.file_metadata is None
                or self.file_tick is None or self.file_export_button is None
                or self.file_action_tabs is None or self.file_capture_panel is None
                or any(b is None for b in self.file_record_flags.values())
                or any(t is None for t in self.file_record_names.values())
                or any(b is None for b in self.file_action_buttons.values())):
            raise ValueError("Source PageFile DFM controls not fully constructed")
        assert self.file_action_tabs.count()==2
        assert self.file_capture_panel.height()==ORIGINAL_DFM_FILE_ADC_HEIGHT
        self.file_export_button.clicked.connect(self._export_selected_file_source)
        for control in (self.file_channels,self.file_spec,self.file_values):
            control.itemChanged.connect(
                lambda item,widget=control:
                    self._file_checked_changed(widget,item))

        for name,index in (("fileGoSignal",3),("fileGoSpectrum",4),
                           ("fileGoStatus",2)):
            self.file_action_buttons[name].clicked.connect(
                lambda _checked=False,target=index:
                    self.navigation.setCurrentIndex(target))
        self._file_flow = None
        self.file_tick.valueChanged.connect(self._file_tick_chosen)
        window.tick.valueChanged.connect(self._sync_file_tick_from_model)
        self.status_tabs.currentChanged.connect(
            window.original_status_mode.setCurrentIndex)
        self.status_plot.scene().sigMouseMoved.connect(
            self._status_chart_moved)
        self.status_export.clicked.connect(self._export_selected_status)
        self.file_channels.currentItemChanged.connect(self._file_channel_chosen)
        window.adc.currentIndexChanged.connect(self._sync_file_selection)
        layout.insertWidget(1, self.navigation)
        layout.insertWidget(2, self.stack, 1)
        # Original Delphi pnMeasure: source 53px bottom panel and five 160x41 buttons.
        # The Qt controller NEVER sends the original TMVKThread device commands.
        self.measure_controls=OriginalMeasureControls(window)
        window.original_measure_controls=self.measure_controls
        layout.insertWidget(3,self.measure_controls.panel)
        # Real original pnView sits beneath all seven pages.  Its slider is
        # bound to the SAME checked ADC/window that GetSignal/GetSpectrum use.
        self.view_panel=QWidget(window)
        self.view_panel.setObjectName("pnView")
        self.view_panel.setFixedHeight(64)  # 48px original + visible provenance
        time_layout=QVBoxLayout(self.view_panel)
        time_layout.setContentsMargins(7,2,7,2)
        time_layout.setSpacing(1)
        time_line=QHBoxLayout()
        time_line.addWidget(QLabel("Время просмотра:",self.view_panel))
        self.view_slider=QSlider(Qt.Horizontal,self.view_panel)
        self.view_slider.setObjectName("tbViewTime")
        self.view_slider.setTracking(False)
        self.view_slider.setRange(0,120)
        self.view_slider.setPageStep(60)
        self.view_slider.setTickInterval(60)
        self.view_slider.setTickPosition(QSlider.TicksAbove)
        self.view_slider.setEnabled(False)
        time_line.addWidget(self.view_slider,1)
        self.view_time_label=QLabel("00:00:00.000",self.view_panel)
        self.view_time_label.setObjectName("lbViewTime")
        self.view_time_label.setMinimumWidth(104)
        self.view_time_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        time_line.addWidget(self.view_time_label)
        time_layout.addLayout(time_line)
        self.view_context=QLabel("Нет подтверждённого сигнала",self.view_panel)
        self.view_context.setObjectName("sourceViewTimeContext")
        self.view_context.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.view_context.setToolTip(
            "Локальный исходный выбор окна BIN; оригинальная Win32 1:1 "
            "координатная/временная приёмка ещё не завершена.")
        time_layout.addWidget(self.view_context)
        layout.insertWidget(3,self.view_panel)
        self._source_view_time=None
        self.view_panel.hide()
        self.view_slider.valueChanged.connect(window._source_time_position_changed)
        window.tabs.tabBar().hide()  # 3 internal tabs no longer 3 top-level pages
        window.original_start_launcher = install_source_task_buttons(window, self.navigation)
        # DFM PageStart is a task launcher, not six research subpages.
        window.task_subpages.tabBar().hide()
        self.sync_file_session(None, ())
        self.refresh_status()
        self.navigation.currentChanged.connect(self._selected)
        window.tabs.currentChanged.connect(self._legacy_changed)
        self._selected(0)

    def clear_source_view_time(self) -> None:
        self._source_view_time=None
        blocked=self.view_slider.blockSignals(True)
        try:
            self.view_slider.setRange(0,120)
            self.view_slider.setValue(0)
            self.view_slider.setEnabled(False)
        finally:
            self.view_slider.blockSignals(blocked)
        self.view_time_label.setText("00:00:00.000")
        self.view_context.setText("Нет проверенного offline сигнала")
        self.view_panel.hide()

    def sync_source_view_time(self,flow,*,requested_start_s=None,position=None):
        """One source-derived tbViewTime and all visible time/readout pages."""
        if flow is None or self.window.session is None or self.window._live_active:
            self.clear_source_view_time()
            return None
        flow.require_session(self.window.session)
        model=source_view_time(
            flow,requested_start_s=requested_start_s,position=position)
        blocked=self.view_slider.blockSignals(True)
        try:
            self.view_slider.setRange(model.minimum,model.maximum)
            self.view_slider.setPageStep(model.page_step)
            self.view_slider.setSingleStep(1)
            self.view_slider.setTickInterval(model.frequency)
            self.view_slider.setValue(model.position)
            self.view_slider.setEnabled(model.maximum>model.minimum)
        finally:
            self.view_slider.blockSignals(blocked)
        self._source_view_time=model
        self.view_time_label.setText(model.label)
        self.view_panel.show()
        # Preserve already verified VALUES provenance during source time
        # changes. Calling with None here overwrote it with "unverified".
        verified=getattr(self.window,"_pagestatus_snapshot",None)
        if (verified is not None and (
                verified.get("source")!="MVK_DSP" or
                verified.get("serial")!=flow.session.serial or
                verified.get("tick")!=flow.tick_index)):
            verified=None
        self.refresh_source_time_context(
            flow,verified_status=verified)
        return model

    def refresh_source_time_context(self,flow,*,verified_status=None) -> None:
        """One ADC + one BIN hash + one VALUES tick in visible caption."""
        model=self._source_view_time
        if flow is None or model is None:
            self.view_context.setText("Нет подтверждённого offline сигнала")
            return
        caption=source_linked_caption(
            flow,model,verified_status=verified_status)
        # Source-backed TSXML gain, if present, is shown in the COMMON
        # view panel without modifying source lbSpecHint (cursor must
        # return to exactly "Курсор: —" when the mouse exits).
        gain=getattr(self.window,"_source_spectrum_gain",None)
        if (gain is not None and gain.channel==flow.channel
                and gain.source_bin_sha256==model.bin_sha256):
            caption+=" · "+gain.label
        self.view_context.setText(caption)
        self.status_note.setToolTip(caption)

    def _remember_view_action(self,action,selection):
        self.view_state=self.view_state.transition(action,selection)
        self.window.source_view_state=self.view_state

    def record_source_spectrum_hscale(self,mode,hz,position):
        """Mirror original menu state into autonomous Core, not DSP data."""
        if hz not in HORIZONTAL_HZ:
            raise ValueError('Unknown original source horizontal menu')
        if self.view_state.spectrum_mode!=mode:
            self._remember_view_action('select_spectrum_mode',mode)
        self._remember_view_action(
            'select_spectrum_hscale',HORIZONTAL_HZ.index(hz))
        self._remember_view_action(
            'scroll_spectrum_horizontal',int(position))

    def record_source_spectrum_vscale(self,mode,tag,position):
        """Mirror verified source menu index+absolute V scroll into Core."""
        if self.view_state.spectrum_mode!=mode:
            self._remember_view_action('select_spectrum_mode',mode)
        if self.view_state.vscale_tag!=tag:
            self._remember_view_action('select_spectrum_vscale',tag)
        self._remember_view_action('scroll_spectrum_vertical',int(position))

    def _selected(self, root_index: int) -> None:
        if self._routing or root_index < 0:
            return
        self._routing = True
        try:
            if root_index in (0, 2, 3, 4):
                self.stack.setCurrentIndex(4 if root_index == 2 else 0)
                old_index = {0: 0, 2: 0, 3: 1, 4: 2}[root_index]
                self.window.tabs.setCurrentIndex(old_index)
                if root_index == 0:
                    self.window.task_subpages.setCurrentIndex(0)
                elif root_index == 2:
                    # Legacy research state remains available, while the
                    # user sees a genuinely separate source PageStatus.
                    self.window.task_subpages.setCurrentIndex(5)
                    self.refresh_status()
            else:
                self.stack.setCurrentIndex({1: 1, 5: 2, 6: 3}[root_index])
                if root_index==6:
                    # The local PageConfig workspace may have been changed
                    # since the last original PageCalib visit.
                    self.calib_panel.refresh_gate()
        finally:
            self._routing = False
        if 0 <= root_index < len(PAGES):
            self._remember_view_action('select_page',PAGES[root_index])

    def _legacy_changed(self, index: int) -> None:
        if self._routing or index not in (0, 1, 2):
            return
        # Compatibility for existing callbacks/tests that change legacy tabs.
        expected = {0: 0, 1: 3, 2: 4}[index]
        self._routing = True
        try:
            self.stack.setCurrentIndex(0)
            self.navigation.setCurrentIndex(expected)
        finally:
            self._routing = False
        self._remember_view_action('select_page',PAGES[expected])

    def refresh_status(self) -> None:
        """Four original source TStringGrid widgets, one selected view mode.

        Current Native ZIP tick and ADC are revalidated through the SAME
        OfflineMeasurementFlow as PageFile/ADC/Spectrum. Direct BIN shows
        UNKNOWN, never an invented system status, alarm, RPM or power.
        """
        index=self.window.original_status_mode.currentIndex()
        if index<0 or index>=len(MODE_NAMES):
            index=0
        self._remember_view_action("select_status_tab",index)
        self.status_tabs.blockSignals(True)
        try:self.status_tabs.setCurrentIndex(index)
        finally:self.status_tabs.blockSignals(False)
        flow=None
        error=None
        if self.window.session is not None and not self.window._live_active:
            try:
                flow=self.window._current_offline_flow()
                flow.require_session(self.window.session)
                result=source_status_projection(index,flow)
            except (ValueError,OSError,KeyError,RuntimeError) as exc:
                error=str(exc)
                result=source_status_projection(index,None)
        else:
            result=source_status_projection(index,None)
        self._source_status_projection=result
        name=result.table_name
        # The original 4 TStringGrid objects have distinct identities and
        # visibility. Keep inactive grids empty to block stale AUX/VALUES.
        for key,grid in self.status_grids.items():
            grid.clearContents()
            if key!=name:grid.setRowCount(0)
        grid=self.status_grids[name]
        self.status_table=grid       # backwards-compatible current grid
        grid.setRowCount(len(result.model.rows))
        grid.setColumnCount(len(result.model.headers))
        grid.setHorizontalHeaderLabels(list(result.model.headers))
        for row,values in enumerate(result.model.rows):
            for col,value in enumerate(values):
                cell=QTableWidgetItem(str(value))
                cell.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)
                grid.setItem(row,col,cell)
        self.status_grid_stack.setCurrentWidget(grid)
        self.status_note.setText(
            ("Источник отклонён: "+error+" · " if error else "")+
            result.model.note)
        self.status_plot.clear()
        verified_chart=result.chart_visible and error is None
        if verified_chart:
            values=list(result.model.bands_for_plot)
            self.status_plot.addItem(pg.BarGraphItem(
                x=list(range(43)),height=values,width=1.0,
                brush="#147b91"))
            self.status_plot.setXRange(-0.5,42.5,padding=0)
            self.status_plot.enableAutoRange(axis="y")
        self.status_plot.setVisible(bool(verified_chart))
        # Source DFM splResult.Width=8 for ALL modes. Hide chResult
        # when its 43 source bars are absent, but never mutate the
        # original Delphi splitter width to zero: Qt already collapses
        # its handle when either adjacent child is hidden.
        self.status_splitter.setHandleWidth(ORIGINAL_STATUS_SPLITTER[2])
        if verified_chart:
            self.status_splitter.setSizes([ORIGINAL_STATUS_CHART[2],580])
        self.status_cursor.setText(
            "Подведите курсор к исходной полосе (43 номинальных частоты)"
            if verified_chart else
            "Нет подтверждённого источника спектра для текущего режима")
        self.status_export.setEnabled(
            bool(error is None and flow is not None
                 and not flow.direct_bin))

    def _status_chart_moved(self,scene_pos) -> None:
        """Source _Unit128:0084AA20 TChartAxis.CalcPosPoint → ROUND → 0..42."""
        source=self._source_status_projection
        if source is None or not source.chart_visible:
            return
        try:
            box=self.status_plot.getPlotItem().vb
            if not box.sceneBoundingRect().contains(scene_pos):
                return
            x=box.mapSceneToView(scene_pos).x()
            index=int(round(x))
            cursor=source.cursor(index)
        except (ValueError,OverflowError,TypeError,AttributeError):
            return
        self.status_cursor.setText(
            f"АЦП{cursor['adc']}: "
            f"{cursor['nominal_hz_float32']:.6g} Гц · "
            f"{cursor['verified_source_band_value']:.8g} м/с² "
            "(по проверенному VALUES, без новых расчётов)")

    def _export_selected_status(self) -> None:
        if (self.window._live_active or self.window.session is None
                or not self.status_export.isEnabled()):
            return
        destination,_=QFileDialog.getSaveFileName(
            self.status_page,
            "Локальный CSV текущей подтверждённой таблицы PageStatus",
            f"MVK-status-mode{self.window.original_status_mode.currentIndex():02d}.csv",
            "CSV (*.csv)")
        if not destination:return
        try:
            flow=self.window._current_offline_flow()
            flow.require_session(self.window.session)
            record=export_verified_status_csv(
                flow,self.window.original_status_mode.currentIndex(),destination)
        except (ValueError,OSError,UnicodeError,KeyError,RuntimeError) as exc:
            self.window.original_window_man.spawn_error(
                "Экспорт PageStatus отклонён: "+str(exc))
            return
        self.status_note.setText(
            f"Создан локальный CSV: {record['saved_rows']} строк, "
            f"{record['saved_columns']} столбцов, "
            f"SHA256 {record['sha256'][:16]}… · "
            "не оригинальная команда прибора. "+self.status_note.text())
        return record

    def _file_channel_chosen(self, item, previous=None) -> None:
        if item is None:
            return
        channel = item.data(Qt.UserRole)
        if isinstance(channel, int) and 1 <= channel <= self.window.adc.count():
            if self.window.adc.currentIndex() != channel - 1:
                self.window.adc.setCurrentIndex(channel - 1)

    def _sync_file_selection(self, index: int) -> None:
        if index < 0:
            return
        if self._file_flow is not None and self.window.session is not None:
            flow=self.window._current_offline_flow()
            self._file_flow=flow
            # A late Qt signal may still carry an old, disabled ADC index.
            # The verified Core selection wins over that stale callback
            # argument for both PageFile and source view-state.
            index=flow.channel-1
            self.update_file_evidence(flow)
        self._remember_view_action('select_channel',index+1)
        for row in range(self.file_channels.count()):
            item = self.file_channels.item(row)
            if item.data(Qt.UserRole) == index + 1:
                self.file_channels.blockSignals(True)
                try:
                    self.file_channels.setCurrentRow(row)
                finally:
                    self.file_channels.blockSignals(False)
                return

    def update_file_evidence(self, flow) -> None:
        """One checked source/ADC/tick, never invented DSP for direct BIN."""
        if flow is None:
            self.file_source_evidence.setText(
                "Источник: измерение не выбрано")
            return
        try:
            flow.require_session(self.window.session)
            info = flow.source_record()
            self.file_source_evidence.setText(
                f"Один источник {info['measurement_kind']} · "
                f"АЦП{info['selected_channel']} / "
                f"{info['sample_count']} реальных Single @ "
                f"{info['sample_rate_hz']:g} Гц · "
                f"SHA256 {info['source_bin_sha256'][:16]}… · "
                + ("AUX/VALUES DSP НЕТ; физическая калибровка НЕ подтверждена"
                   if flow.direct_bin else
                   f"VALUES tick {flow.tick_index+1}/{flow.session.updates}; "
                   "AUX только при проверенном происхождении"))
        except (OSError,ValueError,KeyError) as exc:
            self.file_source_evidence.setText(
                "ИСТОЧНИК ОТКЛОНЁН; данные файла изменены/недоступны: "
                + str(exc))

    def _sync_file_tick_from_model(self, value: int) -> None:
        """The hidden legacy selector and visible File tick have ONE owner."""
        active=(self._file_flow is not None
                and self.window.session is not None
                and not self.window._live_active
                and not self._file_flow.direct_bin)
        previous=self.file_tick.blockSignals(True)
        try:
            maximum=(self._file_flow.session.updates if active else 1)
            self.file_tick.setRange(1,maximum)
            self.file_tick.setValue(int(value) if active else 1)
            self.file_tick.setEnabled(active)
        finally:
            self.file_tick.blockSignals(previous)

    def _file_tick_chosen(self, tick: int) -> None:
        if (self._file_flow is None or self.window.session is None
                or self.window._live_active or self._file_flow.direct_bin):
            return
        self._file_flow.require_session(self.window.session)
        if self.window.tick.value()!=tick:
            self.window.tick.setValue(tick)  # one authoritative Core refresh

    def _file_selection_status(self):
        if self.file_record_selection is None:
            return "Чек-листы записи: загрузите проверенное измерение"
        chosen=self.file_record_selection.report()
        return (
            "Исходный cbFileChannels: 10 флагов (8 АЦП + 2 TACH); "
            "cbFileSpec: 43; cbFileValues: 24+43+6. "
            f"Выбрано ADC {len(chosen['selected_adcs'])}, "
            f"SPEC {len(chosen['selected_spec_indices'])}, "
            f"VALUES {len(chosen['selected_value_indices'])}. "
            "Сохранение локальное, исходный TMVKThread НЕ запускается.")

    def _file_checked_changed(self,widget,item):
        """A real user toggles the ORIGINAL source check-list by its index."""
        if (self.file_record_selection is None or self._file_flow is None
                or self.window.session is None or
                self.window._live_active or item is None):
            return
        group=("channels" if widget is self.file_channels else
               "spec" if widget is self.file_spec else
               "values" if widget is self.file_values else None)
        if group is None:return
        index=item.data(Qt.UserRole+1)
        if type(index) is not int:return
        try:
            flow=self.window._current_offline_flow()
            result=self.file_record_selection.set_checked(
                group,index,item.checkState()==Qt.Checked,flow=flow)
            self.file_record_selection=result
            self.file_export_button.setEnabled(
                bool(result.checked("channels")))
        except (ValueError,OSError,KeyError):
            flags=getattr(self.file_record_selection,group)
            blocked=widget.blockSignals(True)
            try:
                item.setCheckState(
                    Qt.Checked if flags[index] else Qt.Unchecked)
            finally:
                widget.blockSignals(blocked)
        self.file_selection_status.setText(self._file_selection_status())
        if hasattr(self,"measure_controls"):
            self.measure_controls.render()

    @staticmethod
    def _checked_item(text,index,checked,enabled=True):
        item=QListWidgetItem(str(text))
        item.setData(Qt.UserRole+1,index)
        flags=Qt.ItemIsSelectable|Qt.ItemIsUserCheckable
        if enabled:flags|=Qt.ItemIsEnabled
        item.setFlags(flags)
        item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        item.setSizeHint(QSize(190,20))
        return item

    def _file_names_option_state(self):
        return OriginalFileNameOptions(
            write_tsxml=self.file_record_flags["cbFileWriteXml"].isChecked(),
            use_folder_prefix=self.file_record_flags[
                "cbFileFolderPrefix"].isChecked(),
            use_custom_name=self.file_record_flags[
                "cbFileMvkName"].isChecked(),
            folder_prefix=self.file_record_names["edFolderPrefix"].text(),
            custom_name=self.file_record_names["edFileMvkName"].text(),
        )

    def _export_selected_file_source(self):
        """Real offline save. No device commands, no presumed vendor ZIP."""
        if (self.file_record_selection is None or self._file_flow is None
                or self.window.session is None or self.window._live_active):
            return
        folder=QFileDialog.getExistingDirectory(
            self.file_page,"Куда сохранить выбранные RAW/TSXML и показатели?",
            "")
        if not folder:return
        try:
            flow=self.window._current_offline_flow()
            flow.require_session(self.window.session)
            result=export_selected_original_pagefile(
                flow,self.file_record_selection,
                self._file_names_option_state(),folder)
        except (OSError,ValueError,KeyError,UnicodeError) as exc:
            self.window.original_window_man.spawn_error(
                "Локальный экспорт PageFile отклонён: "+str(exc))
            return
        self.file_source_evidence.setText(
            f"Экспортировано {result['files_written']} файла(ов), "
            f"{result['selected_result_rows']} проверенных строк в "
            f"{result['output_folder']}; исходные BIN/TSXML НЕ изменены. "
            "Никаких команд устройству.")
        self.file_selection_status.setText(
            "Локальный экспорт завершён. "+self._file_selection_status())
        return result

    def refresh_file_workbench(self, *, verified_status=None) -> None:
        """Source 43 SPEC, 24+43+6 VALUES with real per-tick provenance.

        Original check-list selections are immutable Core flags and must
        SURVIVE changes of active ADC, tick and visible graph, but must be
        destroyed on file change / fail-closed source rejection.
        """
        table=self.file_metadata
        table.clearContents()
        blocked_spec=self.file_spec.blockSignals(True)
        blocked_values=self.file_values.blockSignals(True)
        try:
            self.file_spec.clear()
            self.file_values.clear()
            if self._file_flow is None or self.window.session is None:
                self._sync_file_tick_from_model(1)
                self.file_summary.setText(
                    "Нет выбранного измерения; откройте ZIP/BIN/TSXML.")
                table.setRowCount(0)
                for button in self.file_action_buttons.values():
                    button.setEnabled(False)
                self.file_export_button.setEnabled(False)
                self.file_selection_status.setText(
                    self._file_selection_status())
                return
            try:
                flow=self.window._current_offline_flow()
                flow.require_session(self.window.session)
                self._file_flow=flow
                self._sync_file_tick_from_model(self.window.tick.value())
                view=source_file_workbench(flow,verified_status=verified_status)
                self.file_summary.setText(
                    f"АЦП{view.selected_channel} · {view.source_basename} · "
                    f"{view.sample_count} Single · {view.sample_rate_hz:g} Гц. "
                    + view.source_note)
                table.setRowCount(len(view.metadata))
                for row,(name,value) in enumerate(view.metadata):
                    for col,txt in enumerate((name,value)):
                        cell=QTableWidgetItem(txt)
                        cell.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)
                        table.setItem(row,col,cell)
                selection=self.file_record_selection
                if selection is not None:
                    selection.validate(flow)
                if view.dsp_verified_for_selection:
                    if (len(view.spectrum_rows)!=SPEC_COUNT
                            or len(view.value_rows)!=ADC_VALUE_COUNT):
                        raise ValueError("Source result counts changed")
                    for i,line in enumerate(view.spectrum_rows):
                        checked=bool(selection and selection.spec[i])
                        self.file_spec.addItem(
                            self._checked_item(line,i,checked))
                    # _Unit128 bWriteValues: first ADC24, then band43,
                    # then source TACH list of 6 (not two synthetic RAW bins).
                    rows=(
                        list(view.value_rows)+
                        [f"SPEC {line}" for line in view.spectrum_rows]+
                        [f"{field[0]} · TACH: запись не восстановлена"
                         for field in TACH_FIELDS]
                    )
                    assert len(rows)==VALUE_COUNT
                    for i,line in enumerate(rows):
                        enabled=i<ADC_VALUE_COUNT+BAND_VALUE_COUNT
                        checked=bool(selection and selection.values[i])
                        self.file_values.addItem(
                            self._checked_item(line,i,checked,enabled))
                else:
                    self.file_spec.addItem(
                        "Приборный SPEC не подтверждён; список не выбирается")
                    self.file_values.addItem(
                        "Нет подтверждённых приборных VALUES/AUX для этого файла")
                for name,button in self.file_action_buttons.items():
                    root_index={"fileGoSignal":3,"fileGoSpectrum":4,
                                "fileGoStatus":2}[name]
                    button.setEnabled(
                        self.navigation.isTabEnabled(root_index))
                self.file_export_button.setEnabled(
                    bool(selection and selection.checked("channels")))
                self.file_selection_status.setText(
                    self._file_selection_status())
            except (ValueError,KeyError,OSError) as exc:
                self._sync_file_tick_from_model(1)
                self.file_tick.setEnabled(False)
                table.setRowCount(0)
                self.file_summary.setText(
                    "Данные текущего файла отклонены: "+str(exc))
                self.file_spec.addItem("Нет подтверждённого текущего спектра")
                self.file_values.addItem(
                    "Нет подтверждённых текущих показателей")
                self.file_export_button.setEnabled(False)
                for button in self.file_action_buttons.values():
                    button.setEnabled(False)
        finally:
            self.file_spec.blockSignals(blocked_spec)
            self.file_values.blockSignals(blocked_values)

    def sync_file_session(self, session, channels, *, flow=None) -> None:
        """Populate ORIGINAL ten check flags, verified ADC only, never TACH fake."""
        self._file_flow=flow
        self.file_record_selection=None
        blocked=self.file_channels.blockSignals(True)
        try:
            self.file_channels.clear()
            if session is None:
                self.update_file_evidence(None)
                self.refresh_file_workbench()
                return
            if flow is None:
                raise ValueError("A checked Core flow is mandatory for PageFile")
            flow.require_session(session)
            if tuple(channels)!=flow.available_channels:
                raise ValueError("PageFile ADC options differ from bound Core")
            self.file_record_selection=OriginalPageFileSelection.for_flow(flow)
            source_by_adc={ch.adc:ch for ch in getattr(session,
                                                       "channel_files",())}
            for i in range(CHANNEL_COUNT):
                adc=i+1
                if i>=8:
                    name=f"TACH{i-7} · исходный канал без проверенного RAW"
                    enabled=False
                elif adc not in channels:
                    name=f"АЦП{adc} · в исходной записи отсутствует"
                    enabled=False
                else:
                    source=source_by_adc.get(adc)
                    name=(f"АЦП{adc}: {source.bin_path.name}"
                          if source is not None else
                          f"АЦП{adc}: {session.serial}")
                    enabled=True
                item=self._checked_item(
                    name,i,self.file_record_selection.channels[i],enabled)
                item.setData(Qt.UserRole,adc)
                self.file_channels.addItem(item)
            self.file_record_names["edFileMvkName"].setText(
                session.serial if session.serial else "")
            self._sync_file_selection(self.window.adc.currentIndex())
            self.update_file_evidence(flow)
            self.refresh_file_workbench()
            if hasattr(self,"measure_controls"):
                self.measure_controls.render()
        finally:
            self.file_channels.blockSignals(blocked)


    def sync_availability(self) -> None:
        self.navigation.setTabEnabled(
            3, self.window.tabs.isTabEnabled(1))
        self.navigation.setTabEnabled(
            4, self.window.tabs.isTabEnabled(2))


def install_original_shell(window, layout) -> OriginalRootShell:
    """Install source-form navigation without replacing the working Qt core."""
    shell = OriginalRootShell(window, layout)
    window.original_root_tabs = shell.navigation
    window.original_root_stack = shell.stack
    window.original_shell = shell
    return shell
