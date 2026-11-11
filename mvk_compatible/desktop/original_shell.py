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
    QTableWidgetItem, QListWidgetItem, QStyle, QVBoxLayout, QWidget,
)

from .original_task_ui import install_source_task_buttons
from .original_config_readonly_ui import OriginalConfigReadOnlyPanel
from ..core.original_offline_view_state import OriginalOfflineView, PAGES, HORIZONTAL_HZ
import pyqtgraph as pg
from ..core.original_pagestatus_source import MODE_NAMES, source_pagestatus_table

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
        "Настройка: два исходных режима tcConfig. Нет загруженной "
        "проверенной локальной конфигурации; команды прибору отключены.")
    note.setObjectName("sourceConfigEvidence")
    lay.addWidget(note)
    return page


def _file_page(parent: QWidget, open_offline) -> QWidget:
    page = QWidget(parent)
    page.setObjectName("PageFile")
    lay = QVBoxLayout(page)
    lay.setContentsMargins(4, 4, 4, 4)
    split = QSplitter(Qt.Horizontal, page)
    split.setObjectName("splFile")
    left = QTabWidget(split)
    left.setObjectName("tcFileChannels")
    channel_host = QWidget(left)
    left_lay = QVBoxLayout(channel_host)
    channels = QListWidget(channel_host)
    channels.setObjectName("cbFileChannels")
    left_lay.addWidget(channels, 1)
    source_open = QPushButton("Открыть локальную запись…", channel_host)
    source_open.setObjectName("openOfflineMeasurement")
    source_open.clicked.connect(open_offline)
    left_lay.addWidget(source_open)
    left.addTab(channel_host, "Каналы")

    right = QTabWidget(split)
    right.setObjectName("tcFileActions")
    content = QWidget(right)
    contents = QVBoxLayout(content)
    panel = QWidget(content)
    panel.setObjectName("pnFileAdc")
    panel_lay = QVBoxLayout(panel)
    for name, text in (
        ("cbFileWriteXml", "Дополнительно XML"),
        ("cbFileFolderPrefix", "Префикс каталога"),
        ("cbFileMvkName", "Имя прибора"),
    ):
        check = QCheckBox(text, panel)
        check.setObjectName(name)
        check.setEnabled(False)
        panel_lay.addWidget(check)
    panel.setVisible(False)  # DFM pnFileAdc.Visible=False
    contents.addWidget(panel)
    groups = QSplitter(Qt.Horizontal, content)
    spec_list = QListWidget(groups)
    spec_list.setObjectName("cbFileSpec")
    values_list = QListWidget(groups)
    values_list.setObjectName("cbFileValues")
    groups.addWidget(spec_list)
    groups.addWidget(values_list)
    groups.setSizes([256, 343])
    contents.addWidget(groups, 1)
    right.addTab(content, "Данные")
    split.addWidget(left)
    split.addWidget(right)
    split.setChildrenCollapsible(False)
    split.setSizes([ORIGINAL_FILE_SPLITTER_LEFT, 615])
    lay.addWidget(split, 1)
    lay.addWidget(_text(page,
        "Оригинальная структура PageFile — каналы слева, параметры экспорта "
        "справа. Сбор исходных файлов на приборе пока отключён; "
        "кнопка открытия работает только с локальными записями."))
    evidence = _text(page, "Источник: измерение не выбрано")
    evidence.setObjectName("sourceFileEvidence")
    evidence.setTextInteractionFlags(Qt.TextSelectableByMouse)
    lay.addWidget(evidence)
    return page


def _status_page(parent: QWidget) -> QWidget:
    """Independent DFM PageStatus: chResult 400 px, splitter 8 px, table.

    Runtime dispatch retains all fifteen audited tcStatus source modes.
    Chart bars are drawn ONLY when the proven source data supplies all
    43 bands. A BIN+TSXML archive never receives invented AUX/DSP values.
    """
    page = QWidget(parent)
    page.setObjectName("PageStatus")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(4, 4, 4, 4)
    tabs = QTabBar(page)
    tabs.setObjectName("tcStatus")
    tabs.setExpanding(False)
    tabs.setUsesScrollButtons(True)
    for caption in MODE_NAMES:
        tabs.addTab(caption)
    tabs.setFixedHeight(36)
    layout.addWidget(tabs)
    split = QSplitter(Qt.Horizontal, page)
    split.setObjectName("splResult")
    split.setHandleWidth(ORIGINAL_STATUS_SPLITTER[2])
    plot = pg.PlotWidget(split)
    plot.setObjectName("chResult")
    plot.setMinimumWidth(320)  # Original splResult.MinSize=320
    plot.setBackground("w")
    plot.setMenuEnabled(False)
    plot.getPlotItem().setLabel("bottom", "Полоса, индекс")
    plot.getPlotItem().setLabel("left", "СКЗ")
    table = _readonly_grid("tabStatus", split)
    split.addWidget(plot)
    split.addWidget(table)
    split.setChildrenCollapsible(False)
    split.setSizes([ORIGINAL_STATUS_CHART[2], 580])
    layout.addWidget(split, 1)
    note = _text(page, "")
    note.setObjectName("sourceStatusNote")
    layout.addWidget(note)
    page.mode_tabs = tabs
    page.source_grid = table
    page.source_plot = plot
    page.source_splitter = split
    page.source_note = note
    return page


def _calib_page(parent: QWidget) -> QWidget:
    page = QWidget(parent)
    page.setObjectName("PageCalib")
    lay = QVBoxLayout(page)
    lay.setContentsMargins(4, 4, 4, 4)
    split = QSplitter(Qt.Horizontal, page)
    split.setObjectName("splCalib")
    left = QTabWidget(split)
    left.setObjectName("tcCalibParam")
    steps = QWidget(left)
    steps_lay = QVBoxLayout(steps)
    top_actions = QHBoxLayout()
    top_actions.addWidget(_disabled("bCalibStart", "Пуск", steps))
    top_actions.addWidget(_text(steps, "Порт генератора: —"))
    steps_lay.addLayout(top_actions)
    list_view = QListWidget(steps)
    list_view.setObjectName("cbCalibSteps")
    steps_lay.addWidget(list_view, 1)
    unit_row = QHBoxLayout()
    for key in ("A", "V", "D", "DR", "T"):
        unit_row.addWidget(_disabled("bCalib" + key, key, steps))
    steps_lay.addLayout(unit_row)
    left.addTab(steps, "Параметры")

    right = QTabWidget(split)
    right.setObjectName("tcCalibResult")
    result = QWidget(right)
    result_lay = QVBoxLayout(result)
    result_buttons = QHBoxLayout()
    for name, title in (
        ("bCalibSave", "Сохранить"),
        ("bCalibClear", "Очистить"),
        ("bCalibGenerate", "Создать"),
    ):
        result_buttons.addWidget(_disabled(name, title, result))
    result_lay.addLayout(result_buttons)
    log = QPlainTextEdit(result)
    log.setObjectName("logCalibResult")
    log.setReadOnly(True)
    log.setPlaceholderText("Калибровочные измерения не проводились.")
    result_lay.addWidget(log, 1)
    right.addTab(result, "Результаты")
    split.addWidget(left)
    split.addWidget(right)
    split.setChildrenCollapsible(False)
    split.setSizes([ORIGINAL_CALIB_SPLITTER_LEFT, 615])
    lay.addWidget(split, 1)
    lay.addWidget(_text(page,
        "Калибровочный экран структурно восстановлен по оригинальному "
        "DFM. Генератор и запись в прибор отключены до восстановления "
        "и отдельного подтверждения протокола."))
    return page


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
        self.stack.addWidget(_file_page(window, window.choose_archive))  # 2
        self.stack.addWidget(_calib_page(window))           # index 3
        self.stack.addWidget(_status_page(window))          # index 4
        self.status_page = self.stack.widget(4)
        self.status_tabs = self.status_page.mode_tabs
        self.status_table = self.status_page.source_grid
        self.status_plot = self.status_page.source_plot
        self.status_splitter = self.status_page.source_splitter
        self.status_note = self.status_page.source_note
        self.file_page = self.stack.widget(2)
        self.file_channels = self.file_page.findChild(QListWidget, "cbFileChannels")
        self.file_spec = self.file_page.findChild(QListWidget, "cbFileSpec")
        self.file_values = self.file_page.findChild(QListWidget, "cbFileValues")
        self.file_source_evidence = self.file_page.findChild(
            QLabel, "sourceFileEvidence")
        self._file_flow = None
        self.status_tabs.currentChanged.connect(
            window.original_status_mode.setCurrentIndex)
        self.file_channels.currentItemChanged.connect(self._file_channel_chosen)
        window.adc.currentIndexChanged.connect(self._sync_file_selection)
        layout.insertWidget(1, self.navigation)
        layout.insertWidget(2, self.stack, 1)
        window.tabs.tabBar().hide()  # 3 internal tabs no longer 3 top-level pages
        window.original_start_launcher = install_source_task_buttons(window, self.navigation)
        # DFM PageStart is a task launcher, not six research subpages.
        window.task_subpages.tabBar().hide()
        self.sync_file_session(None, ())
        self.refresh_status()
        self.navigation.currentChanged.connect(self._selected)
        window.tabs.currentChanged.connect(self._legacy_changed)
        self._selected(0)

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
        """Render an original-source StatusTable without inventing device DSP."""
        index = self.window.original_status_mode.currentIndex()
        if index >= 0:
            self._remember_view_action('select_status_tab',index)
        self.status_tabs.blockSignals(True)
        try:
            self.status_tabs.setCurrentIndex(index)
        finally:
            self.status_tabs.blockSignals(False)
        model = source_pagestatus_table(
            index, getattr(self.window, "_pagestatus_snapshot", None))
        table = self.status_table
        table.clearContents()
        table.setRowCount(len(model.rows))
        table.setColumnCount(len(model.headers))
        table.setHorizontalHeaderLabels(list(model.headers))
        for row, values in enumerate(model.rows):
            for col, value in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(str(value)))
        self.status_note.setText(model.note)
        self.status_plot.clear()
        # Delphi chResult TBarSeries is source-backed only for original
        # 43-band modes. Never display synthetic bars for BIN/TSXML.
        if model.bands_for_plot is not None:
            values = list(model.bands_for_plot)
            self.status_plot.addItem(pg.BarGraphItem(
                x=list(range(43)), height=values,
                width=1.0, brush="#147b91"))
            self.status_plot.setXRange(-0.5, 42.5, padding=0)
            self.status_plot.enableAutoRange(axis="y")
            self.status_plot.setVisible(True)
        else:
            self.status_plot.setVisible(False)

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

    def sync_file_session(self, session, channels, *, flow=None) -> None:
        """Populate original PageFile strictly from the shared Core source."""
        self._file_flow = flow
        self.file_channels.clear()
        self.file_spec.clear()
        self.file_values.clear()
        if session is None:
            self.update_file_evidence(None)
            return
        if flow is not None:
            flow.require_session(session)
            if tuple(channels) != flow.available_channels:
                raise ValueError("File page channels differ from source Core")
        sources = {ch.adc: ch for ch in getattr(session, "channel_files", ())}
        for adc in channels:
            entry = sources.get(adc)
            if entry is not None:
                label = (
                    f"АЦП{adc}: {entry.bin_path.name} "
                    f"({entry.sample_rate_hz} Гц)")
            else:
                label = f"АЦП{adc}: {session.serial}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, int(adc))
            self.file_channels.addItem(item)
        if sources:
            self.file_spec.addItem(
                "Спектр рассчитывается локально; приборный SPEC не предоставлен")
            self.file_values.addItem(
                "BIN/TSXML: исходные AUX/VALUES отсутствуют")
        else:
            self.file_spec.addItem(
                "Просмотр спектра — на странице «Спектр»")
            self.file_values.addItem(
                f"Native R6.1 VALUES: {session.updates} проверенных тиков; "
                "пиковые AUX — только при наличии связанной проверки")
        self._sync_file_selection(self.window.adc.currentIndex())
        self.update_file_evidence(flow)

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
