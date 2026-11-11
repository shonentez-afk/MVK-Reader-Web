"""Stage111 native Qt window. Offline viewing plus opt-in bundled R6.1 capture.

The Qt UI never opens a device socket or sends MVK commands, HTTP or server.

Delphi MVKView parity is IN PROGRESS: FFT and AC remain labelled candidates.
"""
from __future__ import annotations
from pathlib import Path
from contextlib import nullcontext
from fractions import Fraction
import math
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QPoint, QPointF, QRectF
from PySide6.QtGui import QAction, QFont, QFontMetrics, QPainterPath
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,
    QPushButton,QLabel,QComboBox,QTabWidget,QTableWidget,QTableWidgetItem,
    QSpinBox,QDoubleSpinBox,QCheckBox,QFileDialog,QMessageBox,QHeaderView,
    QScrollBar,QScrollArea,QFrame,QToolButton,QMenu,QSizePolicy,QDockWidget,
    QGraphicsPathItem)
from ..core import OfflineSession
from ..core.original_native_parity import compare_original_native
from ..core.original_pagestatus_source import MODE_NAMES, source_pagestatus_table
from ..core.native_r6_live_preview import provisional_waveform, provisional_spectrum
from ..core.direct_bin_session import DirectBinSession
from ..core.envelope_idr_candidate import EnvelopeProfile,ENVELOPE_RATES
from ..core.cursor_format_candidate import format_cursor_idr_candidate
from ..core.tqgrapher_display_idr_candidate import (spectrum_display_contract,cursor_string_candidate)
from ..core.tqgrapher_paintbox_registration_idr_candidate import source_paintbox_registration
from ..core.tqgrapher_qt_canvas_bridge_candidate import QtPaintBoxBridge
from ..core.qt_spectrum_viewport_observation import describe_qt_viewport_geometry
from ..core.tqgrapher_grid_idr_candidate import source_tqgrapher_grid_candidate
from ..core.tco2draw_grid_source import (source_tco2draw_grid_contract,
    GRID_LINE_HEX, BACKGROUND_HEX)
from ..core.tco2draw_raster_candidate import (source_raster_rgba,
    source_grid_segments, contract as tco2draw_raster_contract)
from ..core.tqgr_series_source_candidate import (
    source_tqgr_series_columns, SOURCE as TQGR_SERIES_SOURCE)
from ..core.spectrum_archive_plot_projection import spectrum_archive_plot_projection
from ..core.tqgrapher_composite_source_candidate import (
    build_tqgrapher_composite)
from .tqgrapher_textout_qt_candidate import (
    qt_textout_source_positions_rgba, qt_source_font_candidate)
from .win32_gdi_source_candidate import (
    Win32SourceTextCanvas, native_gdi_supported)
from ..core.tqgrapher_spectrum_scroll_idr_candidate import (
    source_spectrum_h_scr,NativeScrollContract,rescale_scroll)
from ..core.mvk_original_scale_tables_idr_candidate import (
    HORIZONTAL_HZ, FFT_WINDOW_SAMPLES, original_h_scale_options,
    original_v_scale_options,original_fft_size_options,validate_source_h_scale)
from ..core.mvk_spectrum_menu_runtime_idr_candidate import (
    RESEARCH_FFT_SIZES,source_default_vertical_tag,source_vertical_page,
    source_vertical_selection,fft_source_archive_gate)
from ..core.tqgrapher_spectrum_scroll_idr_candidate import source_spectrum_v_scr
from ..core.spectrum_graph_default_vscale_idr_candidate import (
    spectrum_graph_default_vscale)
from ..core.tqgrapher_dfm_design_idr_candidate import (
    DFM_DESIGN_FONT_FAMILY, DFM_DESIGN_FONT_HEIGHT,
    DFM_DESIGN_PIXELS_PER_INCH, PAINTBOX_DIMENSIONS)
from ..core.spectrum_summary_export_candidate import (spectrum_triplet_text,append_research_summary_csv)
from ..core.original_spectrum_x32dbg_reference import (
    load_original_spectrum_reference, SOURCE as ORIGINAL_X32DBG_REF_SOURCE)
from ..triplet_reference_compare import read_operator_triplet_file,compare_operator_triplet
from ..core.envelope_spectrum_idr_candidate import required_original_history
from ..core.tqgrapher_cursor_candidate import CursorGeometry, cursor_from_spectrum
from ..core.waveform_hover_idr_candidate import prepare_waveform_hover_window
from .xor_cursor_overlay import QtSpectrumXorCursor
from .original_shell import install_original_shell
from .original_task_ui import make_original_channel_tabs


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.session=None
        self._native_dialog=None  # Stage111Z.25: integrated verified Go recorder controller
        self._live_active=False
        self._live_preview=None  # only provisional, bounded, same-run calibrated bytes
        self._live_prior_session=None
        self._live_control_states=[]
        self._pagestatus_snapshot=None
        self.wave_line=None
        self.spec_line=None
        self.spec_hline=None  # Source 007CA9BA: raw signed peak crosshair, NOT averaged label
        self._spec_last_cursor=None
        self._spec_mouse_pixel=None  # Native UpdateCursor ignores unchanged integer X
        self._wave_mouse_pixel=None
        self._wave_hover_window=None  # Lazy, one offline BIN read per displayed window
        self._full_spectrum=None
        self._spectrum_summary=None
        self._spectrum_reference=None  # Explicit research-only original x32dbg visual overlay
        self._spectrum_reference_saved=None
        self._spec_source_grid_applied=False
        self._spec_source_grid_apply_busy=False
        self._spec_source_grid_model=None
        self._spec_source_grid_axis_label_fonts=None
        self._spec_source_grid_lines=[]  # Owned 10x10 research-only Qt overlay items.
        self._spec_source_raster_item=None  # Private-reference research view only.
        self._spec_source_raster_data=None
        self._spec_source_series_raw_item=None  # Original PlotDataItem; never mutated.
        self._spec_source_series_item=None  # Research stroke overlay only.
        self._spec_source_series_model=None
        self._spec_source_series_signature=None
        self._spec_source_series_busy=False
        # Ordinary archive uses source per-column min/max when compressed.
        self._archive_raw_line=None
        self._archive_source_curve=None
        self._archive_source_projection_signature=None
        self._archive_source_projection_model=None
        self._archive_source_projection_busy=False
        # Source _Unit128:0084B274 shares one original EnvelopeCode (0..31).
        self._wave_envelope_dirty=False
        self._spectrum_envelope_dirty=False
        self.envelope_profile=None  # Optional original local user IDP; never saved or uploaded
        self._spec_loaded_sample_rate_hz=None
        self.setWindowTitle('ТПО МВК')
        self.resize(1360,850)
        self.setMinimumSize(960,580)
        pg.setConfigOptions(antialias=False,useOpenGL=False)
        self._build()
        self._set_active(False)

    @staticmethod
    def _plot(x,y):
        p=pg.PlotWidget(background='#ffffff')
        p.setLabel('bottom',x)
        p.setLabel('left',y)
        p.showGrid(x=True,y=True,alpha=.2)
        p.getPlotItem().setClipToView(True)
        p.getPlotItem().setDownsampling(mode='peak')
        return p

    @staticmethod
    def _float(lo,hi,value,decimals=3):
        p=QDoubleSpinBox()
        p.setRange(lo,hi)
        p.setDecimals(decimals)
        p.setValue(value)
        return p

    @staticmethod
    def _value(value):
        if value is None:return '—'
        if isinstance(value,float):return f'{value:.8g}'
        return str(value)

    @staticmethod
    def _cell(table,row,col,value):
        table.setItem(row,col,QTableWidgetItem(str(value)))

    def _build(self):
        file_menu=self.menuBar().addMenu('Файл')
        action=QAction('Открыть измерение (ZIP / BIN / TSXML)…',self)
        action.setShortcut('Ctrl+O')
        action.triggered.connect(self.choose_archive)
        file_menu.addAction(action)
        file_menu.addAction('Закрыть измерение',self._close_session)
        capture_action=QAction('Запись с прибора · Native R6.1…',self)
        capture_action.triggered.connect(self.open_native_capture)
        file_menu.addAction(capture_action)
        parity_action=QAction('Сверить оригинальный BIN с Native R6.1…',self)
        parity_action.setObjectName('actionOriginalNativeParity')
        parity_action.triggered.connect(self.compare_original_native_local)
        file_menu.addAction(parity_action)
        original_y_action=QAction('Эталон графика MVKView · Power/Y x32dbg…',self)
        original_y_action.setObjectName('actionOriginalX32dbgSpectrumReference')
        original_y_action.setToolTip(
            'Открыть только локальный JSON + два исходных Float32 BIN для сравнения '
            'Qt-графика; не заменяет BIN-архив, FFT и приборный DSP.')
        original_y_action.triggered.connect(self.choose_original_spectrum_reference)
        file_menu.addAction(original_y_action)
        file_menu.addSeparator()
        file_menu.addAction('Выход',self.close)
        wrapper=QWidget()
        self.setCentralWidget(wrapper)
        layout=QVBoxLayout(wrapper)
        bar=QHBoxLayout()
        button=QPushButton('Открыть измерение…')
        button.clicked.connect(self.choose_archive)
        bar.addWidget(button)
        bar.addWidget(QLabel('Канал'))
        self.adc=QComboBox()
        self.adc.addItems([f'АЦП {i}' for i in range(1,9)])
        self.adc.currentIndexChanged.connect(self.refresh_all)
        bar.addWidget(self.adc)
        bar.addWidget(QLabel('Обновление DSP'))
        self.tick=QSpinBox()
        self.tick.setRange(1,1)
        self.tick.valueChanged.connect(self.refresh_calc)
        bar.addWidget(self.tick)
        bar.addStretch()
        self.title=QLabel('Сеанс не выбран')
        self.title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bar.addWidget(self.title)
        # Original DFM has no permanent archive research toolbar above Pages.
        # Keep its controls programmatically available, but hide this auxiliary
        # Qt-only toolbar by default (operator can show it from View menu).
        self.compat_toolbar=QWidget(wrapper)
        self.compat_toolbar.setObjectName('compatibilityAuxToolbar')
        self.compat_toolbar.setLayout(bar)
        layout.addWidget(self.compat_toolbar)
        self.compat_toolbar.hide()

        self.tabs=QTabWidget()
        layout.addWidget(self.tabs,1)
        self._calculated_tab()
        self._signal_tab()
        self._spectrum_tab()
        self.tabs.currentChanged.connect(self._active_tab_changed)
        view_menu=self.menuBar().addMenu('Вид')
        research_menu=view_menu.addMenu('Исследование')
        details=QAction('Дополнительные настройки графиков',self)
        details.setShortcut('Ctrl+D')
        details.triggered.connect(self._toggle_current_research)
        research_menu.addAction(details)
        research_tabs=QAction('Вкладки технического анализа',self)
        research_tabs.setCheckable(True)
        research_tabs.setChecked(False)
        research_tabs.toggled.connect(self.task_subpages.tabBar().setVisible)
        research_menu.addAction(research_tabs)
        self.research_tabs_action=research_tabs
        aux=QAction('Служебная панель Qt',self)
        aux.setCheckable(True)
        aux.setChecked(False)
        aux.toggled.connect(self.compat_toolbar.setVisible)
        view_menu.addAction(aux)
        self.note=QLabel('OFFLINE просмотр · LIVE только через Native R6.1 с подтверждением · команды прибору отсутствуют')
        self.note.setStyleSheet('color: #9e6500; padding: 5px')
        layout.addWidget(self.note)
        # Recreate original IDR/Delphi 7-page root structure without replacing
        # the existing three internal, fully functional archive/DSP tabs.
        self.original_shell=install_original_shell(self,layout)
        self.statusBar().showMessage('Открыть локальное измерение или выбрать «Запись с прибора · Native R6.1»')

    def _calculated_tab(self):
        tab=QWidget()
        # Original MVKView 1.0.47 visible top tab: 'Задачи' (2026-11-01 reference).
        self.tabs.addTab(tab,'Задачи')
        lay=QVBoxLayout(tab)
        self.calc_source=QLabel('Штатные данные МВК (AUX4700 / VALUES)')
        self.calc_status=QLabel('Статус: —')
        row=QHBoxLayout()
        row.addWidget(self.calc_source)
        row.addStretch()
        row.addWidget(self.calc_status)
        lay.addLayout(row)
        inner=QTabWidget()
        inner.setObjectName('taskSubpages')
        self.task_subpages=inner
        lay.addWidget(inner,1)

        # Original PageStart is a TASK LAUNCHER, not a DSP results table.
        # Keep source-backed DSP/third-octave/status subpages as adjacent
        # views, but give the operator a useful offline-first home screen.
        home=QWidget()
        home.setObjectName('pageStartOffline')
        hl=QVBoxLayout(home)
        hl.setContentsMargins(24,24,24,24)
        hl.setSpacing(12)
        header=QLabel('MVKView Compatible · просмотр измерений')
        header.setObjectName('taskHomeHeading')
        header.setStyleSheet('font-size: 19px; font-weight: 600;')
        hl.addWidget(header)
        self.task_session_summary=QLabel(
            'Измерение не открыто. Выберите локальный ZIP, BIN или TSXML.')
        self.task_session_summary.setObjectName('taskSessionSummary')
        self.task_session_summary.setWordWrap(True)
        hl.addWidget(self.task_session_summary)
        self.task_open_button=QPushButton('Открыть измерение…')
        self.task_open_button.setObjectName('taskOpenMeasurement')
        self.task_open_button.setMinimumHeight(44)
        self.task_open_button.clicked.connect(self.choose_archive)
        hl.addWidget(self.task_open_button)
        self.task_capture_button=QPushButton('Запись с прибора · Native R6.1…')
        self.task_capture_button.setObjectName('taskCaptureNativeR6')
        self.task_capture_button.setMinimumHeight(44)
        self.task_capture_button.setToolTip('Открывает безопасное управление уже проверенным Windows приёмником; без сетевого подключения до явного подтверждения')
        self.task_capture_button.clicked.connect(self.open_native_capture)
        hl.addWidget(self.task_capture_button)
        self.task_signal_button=QPushButton('Временной сигнал')
        self.task_signal_button.setObjectName('taskOpenTimeSignal')
        self.task_signal_button.setMinimumHeight(44)
        self.task_signal_button.clicked.connect(
            lambda:self.tabs.setCurrentIndex(1))
        hl.addWidget(self.task_signal_button)
        self.task_spectrum_button=QPushButton('Спектр')
        self.task_spectrum_button.setObjectName('taskOpenSpectrum')
        self.task_spectrum_button.setMinimumHeight(44)
        self.task_spectrum_button.clicked.connect(
            lambda:self.tabs.setCurrentIndex(2))
        hl.addWidget(self.task_spectrum_button)
        self.task_metrics_button=QPushButton('Показатели и диагностика')
        self.task_metrics_button.setObjectName('taskOpenMeasurements')
        self.task_metrics_button.setMinimumHeight(44)
        self.task_metrics_button.clicked.connect(
            lambda:self.task_subpages.setCurrentIndex(1))
        hl.addWidget(self.task_metrics_button)
        device_note=QLabel(
            'Команды настройки прибора и калибровка недоступны. '
            'Запись с прибора — через проверенный Native R6.1 с отдельным допуском; '
            'без подтверждения никаких подключений. Оригинальные команды МВК не отправляются.')
        device_note.setObjectName('taskDeviceOfflineNotice')
        device_note.setWordWrap(True)
        device_note.setStyleSheet('color:#776235; padding-top:10px;')
        hl.addWidget(device_note)
        hl.addStretch()
        inner.addTab(home,'Обзор')

        values=QWidget()
        vl=QVBoxLayout(values)
        self.metrics=QTableWidget(24,4)
        self.metrics.setHorizontalHeaderLabels(['Показатель (диапазон)','СКЗ / DSP','ПИК / AUX','ПИК-ПИК / AUX'])
        self.metrics.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.metrics.setEditTriggers(QTableWidget.NoEditTriggers)
        vl.addWidget(self.metrics)
        inner.addTab(values,'Расчётные показатели')

        third=QWidget()
        tl=QVBoxLayout(third)
        self.oct_plot=self._plot('Третьоктавная полоса (индекс)','СКЗ, м/с²')
        tl.addWidget(self.oct_plot,3)
        self.oct_table=QTableWidget(43,2)
        self.oct_table.setHorizontalHeaderLabels(['Оригинальная полоса','СКЗ, м/с²'])
        self.oct_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.oct_table.setEditTriggers(QTableWidget.NoEditTriggers)
        tl.addWidget(self.oct_table,2)
        inner.addTab(third,'43 третьоктавные полосы')

        statuses=QWidget()
        sl=QVBoxLayout(statuses)
        self.status_fields={}
        for key,label in (
            ('sensor_status','Статус датчика'),('overload_status','Перегрузка'),
            ('buffer_status','Статус буфера'),('sensor_voltage_v','Напряжение датчика'),
            ('crest_factor','Пик-фактор'),('broadband_acceleration_m_s2','Широкополосное ускорение')):
            line=QLabel(label+': —')
            line.setTextInteractionFlags(Qt.TextSelectableByMouse)
            sl.addWidget(line)
            self.status_fields[key]=(label,line)
        self.sensor_bit_details=QLabel('АЦП: разбор исходных статусных битов недоступен')
        self.sensor_bit_details.setObjectName('stage111z28SensorBits')
        self.sensor_bit_details.setWordWrap(True)
        sl.addWidget(self.sensor_bit_details)
        sl.addStretch()
        inner.addTab(statuses,'Диагностика')

        # Source-backed Stage111Z28A: no fabricated RPM or speed units.
        tach_page=QWidget()
        tach_layout=QVBoxLayout(tach_page)
        self.dsp_tach_status=QLabel('DSP/TACH: не открыт подтверждённый измерительный сеанс')
        self.dsp_tach_status.setObjectName('stage111z28DspTachSource')
        self.dsp_tach_status.setWordWrap(True)
        tach_layout.addWidget(self.dsp_tach_status)
        self.dsp_tach_clock=QLabel('Время: неизвестно')
        self.dsp_tach_clock.setObjectName('stage111z28TickClock')
        tach_layout.addWidget(self.dsp_tach_clock)
        self.tach_words=QTableWidget(2,6)
        self.tach_words.setObjectName('stage111z28TachRawRegisters')
        self.tach_words.setHorizontalHeaderLabels(
            ['Тахоканал','Float32 +0','Float32 +2','UInt32 +4','UInt32 +6','UInt32 +8'])
        self.tach_words.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tach_words.verticalHeader().setVisible(False)
        self.tach_words.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tach_layout.addWidget(self.tach_words)
        self.tach_warning=QLabel(
            'Сырые регистры TACH 0x3000/0x3100 из кадра VALUES 76B. '
            'Значение частоты и оборотов НЕ восстановлено и здесь НЕ вычисляется. '
            'Время — часы приёмного ПК, не синхронизация с DSP.')
        self.tach_warning.setObjectName('stage111z28TachNoRpmNote')
        self.tach_warning.setWordWrap(True)
        tach_layout.addWidget(self.tach_warning)
        inner.addTab(tach_page,'TACH / системный DSP')
        self._reset_dsp_tach_panel('Нет проверенного источника TACH/DSP')

        # Original _Unit128:008475F5 source dispatch: 15 indices, one panel.
        # This page is deliberately labelled a source-backed research view,
        # not full original 1:1 pixel reconstruction or verified alarms/RPM.
        source_page=QWidget()
        source_layout=QVBoxLayout(source_page)
        line=QHBoxLayout()
        line.addWidget(QLabel('Режим tcStatus (исходный IDR):'))
        self.original_status_mode=QComboBox()
        self.original_status_mode.setObjectName('stage111z28bOriginalStatusMode')
        self.original_status_mode.addItems(list(MODE_NAMES))
        self.original_status_mode.currentIndexChanged.connect(
            self._refresh_source_pagestatus)
        line.addWidget(self.original_status_mode,1)
        source_layout.addLayout(line)
        self.original_status_note=QLabel()
        self.original_status_note.setObjectName('stage111z28bSourceNote')
        self.original_status_note.setWordWrap(True)
        source_layout.addWidget(self.original_status_note)
        self.original_status_table=QTableWidget(0,2)
        self.original_status_table.setObjectName('stage111z28bOriginalTable')
        self.original_status_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.original_status_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents)
        source_layout.addWidget(self.original_status_table,2)
        self.original_status_plot=self._plot(
            'Полоса, индекс (43 исходные AUX)','СКЗ, м/с² · SOURCE, НЕ pixel parity')
        self.original_status_plot.setObjectName('stage111z28b43SourceChart')
        self.original_status_plot.setMaximumHeight(195)
        source_layout.addWidget(self.original_status_plot,1)
        inner.addTab(source_page,'PageStatus · оригинальный порядок')
        self._refresh_source_pagestatus()

    def _active_tab_changed(self,index):
        if index!=1:self.wave_inspector.hide()
        if index!=2:self.spec_inspector.hide()
        # Original _Unit128:0084B2C8 clears both source graph series, then
        # 00847248 updates the active page. Refresh inactive Qt pages lazily.
        if self.session is None or self._live_active:
            return
        if index==1 and self._wave_envelope_dirty:
            self.refresh_wave()
        if index==2 and self._spectrum_envelope_dirty and self._spectrum_reference is None:
            self._toggle_spec_envelope(self.spec_envelope_button.isChecked())

    def _toggle_current_research(self):
        if self.tabs.currentIndex()==1:
            self.wave_inspector.setVisible(not self.wave_inspector.isVisible())
        elif self.tabs.currentIndex()==2:
            self.spec_inspector.setVisible(not self.spec_inspector.isVisible())

    def _signal_tab(self):
        """Original PageAdc primary controls, research options in a dock.

        The signal data, GetSignal order, and signal hover routines are
        unchanged. This is an OFFLINE usability layout, not a claim of
        byte-exact original DFM or device support.
        """
        tab=QWidget()
        self.tabs.addTab(tab,'Временной сигнал')
        page=QVBoxLayout(tab)
        page.setContentsMargins(0,0,0,0)
        page.setSpacing(0)
        self.wave_channel_tabs=make_original_channel_tabs(self,'tcAdc')
        page.addWidget(self.wave_channel_tabs)
        contents=QWidget(tab)
        page.addWidget(contents,1)
        root=QHBoxLayout(contents)
        root.setContentsMargins(4,6,4,4)
        root.setSpacing(4)
        panel=QWidget()
        panel.setObjectName('pnAdcTools')
        panel.setFixedWidth(177)
        left=QVBoxLayout(panel)
        left.setContentsMargins(6,7,6,7)
        left.setSpacing(5)

        # These existing models stay available to all former callbacks,
        # tests and original code-derived GetSignal implementations.
        self.wave_start=self._float(0,300,0)
        self.wave_seconds=self._float(.001,30,1)
        self.wave_mode=QComboBox()
        self.wave_mode.addItems([
            'AC · NoDC / GetSignal f32 (IDR)',
            'AC+DC · без удаления DC',
        ])
        self.wave_order=QComboBox()
        self.wave_order.addItems([
            'Архив: хронология BIN','Буфер GetSignal: обратный порядок',
        ])
        self.wave_order.setToolTip(
            'GetSignal buffer reversed; original TQGrapher pixel parity TODO')

        self.wave_envelope_load=QPushButton(
            'Открыть локальный оригинальный IDP для огибающей…')
        self.wave_envelope_load.clicked.connect(self.choose_private_envelope_idp)
        self.wave_envelope_code=QComboBox()
        self.wave_envelope_code.addItem('Без огибающей',0)
        for code in range(1,32):
            self.wave_envelope_code.addItem(
                f'Код огибающей {code} · таблица {ENVELOPE_RATES[code]} Гц',code)
        self.wave_envelope_code.setEnabled(False)
        self.wave_envelope_code.setToolTip(
            'Режимы по исходной таблице IDR; нужен локальный профиль.')

        self.wave_filter_button=QPushButton('Без фильтра')
        self.wave_filter_button.setObjectName('bAdcEnvelopeType')
        self.wave_filter_button.setToolTip(
            'Исходная огибающая требует профиль из локального оригинального IDP; '
            'код выбирается в «Исследование».')
        self.wave_filter_button.clicked.connect(self._wave_filter_primary_click)
        left.addWidget(self.wave_filter_button)

        self.wave_type_button=QToolButton()
        self.wave_type_button.setObjectName('bAdcType')
        self.wave_type_button.setPopupMode(QToolButton.InstantPopup)
        self.wave_type_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.wave_type_menu=QMenu(self.wave_type_button)
        for i,name in enumerate(('AC · без DC','AC+DC')):
            act=self.wave_type_menu.addAction(name)
            act.setCheckable(True)
            act.setData(i)
            act.triggered.connect(
                lambda checked=False,index=i:self.wave_mode.setCurrentIndex(index))
        self.wave_type_button.setMenu(self.wave_type_menu)
        left.addWidget(self.wave_type_button)

        self.wave_hscale_button=QToolButton()
        self.wave_hscale_button.setObjectName('bAdcHScale')
        self.wave_hscale_button.setPopupMode(QToolButton.InstantPopup)
        self.wave_hscale_menu=QMenu(self.wave_hscale_button)
        for duration in (.01,.025,.05,.1,.25,.5,1.,2.,5.,10.):
            act=self.wave_hscale_menu.addAction(f'{duration:g} с')
            act.setData(duration)
            act.triggered.connect(
                lambda checked=False,seconds=duration:self._select_wave_window(seconds))
        self.wave_hscale_button.setMenu(self.wave_hscale_menu)
        left.addWidget(self.wave_hscale_button)

        self.wave_vscale_button=QToolButton()
        self.wave_vscale_button.setObjectName('bAdcVScale')
        self.wave_vscale_button.setPopupMode(QToolButton.InstantPopup)
        vm=QMenu(self.wave_vscale_button)
        vm.addAction('Авто',lambda:self.wave_plot.enableAutoRange())
        vm.addAction('Приблизить Y',lambda:self._zoom_vertical_wave(.5))
        vm.addAction('Отдалить Y',lambda:self._zoom_vertical_wave(2))
        self.wave_vscale_button.setMenu(vm)
        self.wave_vscale_button.setText('Шкала Y · авто')
        left.addWidget(self.wave_vscale_button)

        self.wave_cursor_primary=QLabel('Курсор: —')
        self.wave_cursor_primary.setObjectName('lbAdcHintPrimary')
        self.wave_cursor_primary.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.wave_cursor_primary.setFixedHeight(55)
        self.wave_cursor_primary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        left.addWidget(self.wave_cursor_primary)
        self.wave_mean_primary=QLabel('СКЗ сигнала: —')
        self.wave_mean_primary.setObjectName('lbAdcMeanPrimary')
        self.wave_mean_primary.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.wave_mean_primary.setFixedHeight(83)
        self.wave_mean_primary.setWordWrap(True)
        self.wave_mean_primary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        left.addWidget(self.wave_mean_primary)

        self.wave_advanced_button=QPushButton('Исследование ▸')
        self.wave_advanced_button.setObjectName('openWaveResearch')
        self.wave_advanced_button.clicked.connect(
            lambda:self.wave_inspector.setVisible(not self.wave_inspector.isVisible()))
        left.addWidget(self.wave_advanced_button)
        for widget in (
            self.wave_filter_button,self.wave_type_button,
            self.wave_hscale_button,self.wave_vscale_button,
        ):
            widget.setFixedHeight(37)
            widget.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
        left.addStretch()
        root.addWidget(panel,0)

        self.wave_plot=self._plot('Время, с','Ускорение, м/с²')
        self.wave_plot.scene().sigMouseClicked.connect(self._wave_click)
        self.wave_plot.scene().sigMouseMoved.connect(self._wave_mouse_move)
        root.addWidget(self.wave_plot,1)

        # Existing diagnostic cursor text stays intact for advanced QA.
        self.wave_hint=QLabel(
            'GetSignal / IDR · ведите мышью по графику для исходного отсчёта')
        self.wave_hint.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.wave_hint.setWordWrap(True)
        self.wave_inspector=QDockWidget('Исследование · временной сигнал',self)
        self.wave_inspector.setObjectName('waveResearchDock')
        self.wave_inspector.setAllowedAreas(
            Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body=QWidget()
        form=QVBoxLayout(body)
        form.setContentsMargins(8,8,8,8)
        for name,field in (
            ('Начало, с',self.wave_start),
            ('Окно, с',self.wave_seconds),
            ('Режим GetSignal',self.wave_mode),
            ('Порядок исходных отсчётов',self.wave_order),
        ):
            label=QLabel(name)
            label.setWordWrap(True)
            form.addWidget(label)
            form.addWidget(field)
        refresh=QPushButton('Обновить сигнал')
        refresh.clicked.connect(self.refresh_wave)
        form.addWidget(refresh)
        form.addWidget(self.wave_envelope_load)
        form.addWidget(self.wave_envelope_code)
        form.addWidget(QLabel('Подробности курсора · исследовательские данные'))
        form.addWidget(self.wave_hint)
        form.addStretch()
        scroll.setWidget(body)
        self.wave_inspector.setWidget(scroll)
        self.addDockWidget(Qt.RightDockWidgetArea,self.wave_inspector)
        self.wave_inspector.hide()
        self.wave_inspector.visibilityChanged.connect(
            lambda visible:self.wave_advanced_button.setText(
                'Исследование ◂' if visible else 'Исследование ▸'))
        self.wave_mode.currentIndexChanged.connect(self._wave_mode_selected)
        self.wave_envelope_code.currentIndexChanged.connect(self._wave_filter_selected)
        self._sync_wave_primary_labels()

    def _wave_filter_primary_click(self):
        if self.envelope_profile is None:
            self.statusBar().showMessage(
                'Без фильтра. Исследовательская огибающая требует локальный IDP.')
            return
        # Only cycle between no filter and the last explicitly selected code.
        self.wave_envelope_code.setCurrentIndex(
            0 if self.wave_envelope_code.currentIndex() else 20)

    def _sync_original_envelope_menu_tag(self,source):
        """Mirror original shared ADC+Spectrum TButton.Tag (0..31).

        Source _Unit128:0084B274 sets both tags from one menu item. Here the
        Qt research-only enable checkbox remains a separate safety control.
        """
        if self._spectrum_reference is not None:
            return
        target=(self.spec_envelope_code if source is self.wave_envelope_code
                else self.wave_envelope_code)
        code=int(source.currentData() or 0)
        other_index=target.findData(code)
        if other_index<0:
            raise ValueError('Invalid original EnvelopeCode 0..31')
        if target.currentIndex()!=other_index:
            previously=target.blockSignals(True)
            try:
                target.setCurrentIndex(other_index)
            finally:
                target.blockSignals(previously)

    def _wave_filter_selected(self,*_):
        self._sync_original_envelope_menu_tag(self.wave_envelope_code)
        self._sync_wave_primary_labels()
        self._wave_envelope_dirty=True
        self.refresh_wave()
        if self.spec_envelope_button.isChecked():
            self._spectrum_envelope_dirty=True
            if self.spec_envelope_code.currentData()==0:
                self.spec_envelope_button.setChecked(False)
            elif self.tabs.currentIndex()==2:
                self._toggle_spec_envelope(True)

    def _wave_mode_selected(self,*_):
        self._sync_wave_primary_labels()
        self.refresh_wave()

    def _select_wave_window(self,seconds):
        self.wave_seconds.setValue(float(seconds))
        self._sync_wave_primary_labels()
        self.refresh_wave()

    def _zoom_vertical_wave(self,factor):
        if self.wave_line is None:
            return
        self.wave_plot.getViewBox().scaleBy((1,float(factor)))
        self.wave_vscale_button.setText('Шкала Y · изменена')

    def _sync_wave_primary_labels(self):
        code=int(self.wave_envelope_code.currentData() or 0)
        self.wave_filter_button.setText(
            'Без фильтра' if not code else f'Огибающая {code} (исслед.)')
        self.wave_type_button.setText(
            'AC · без DC' if self.wave_mode.currentIndex()==0 else 'AC+DC')
        self.wave_hscale_button.setText(f'{self.wave_seconds.value():g} с')
        for a in self.wave_type_menu.actions():
            a.setChecked(a.data()==self.wave_mode.currentIndex())

    def _spectrum_tab(self):
        """DFM-informed panel proportions with FUNCTIONAL Qt scrollbars.

        Original PageSpectrum/pnSpecTools width 177, left command order and
        24-pixel top/right scrollbars are source-verified. Current controls
        remain research Qt widgets; no claim of pixel-perfect Delphi layout.
        """
        tab=QWidget()
        self.tabs.addTab(tab,'Спектр')
        page=QVBoxLayout(tab)
        page.setContentsMargins(0,0,0,0)
        page.setSpacing(0)
        self.spec_channel_tabs=make_original_channel_tabs(self,'tcSpectrum')
        page.addWidget(self.spec_channel_tabs)
        contents=QWidget(tab)
        page.addWidget(contents,1)
        lay=QHBoxLayout(contents)
        lay.setContentsMargins(4,6,4,4)
        lay.setSpacing(0)

        self.spec_tools=QScrollArea()
        self.spec_tools.setObjectName('pnSpecTools')
        # Restore the original 177 px pane. Long research captions now live
        # in an independent dock; nine short primary controls fit here
        # without horizontal scrolling or clipped diagnostics.
        self.spec_tools.setFixedWidth(177)
        self.spec_tools.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.spec_tools.setWidgetResizable(True)
        self.spec_tools.setFrameShape(QFrame.NoFrame)
        tools=QWidget()
        tools.setObjectName('pnSpecToolsBody')
        stack=QVBoxLayout(tools)
        stack.setContentsMargins(7,9,7,9)
        stack.setSpacing(4)

        self.spec_envelope_button=QPushButton('Без фильтра')
        self.spec_envelope_button.setObjectName('bSpecEnvelopeType')
        self.spec_envelope_button.setFixedHeight(41)
        self.spec_envelope_button.setEnabled(False)
        self.spec_envelope_button.setCheckable(True)
        self.spec_envelope_button.setToolTip(
            'Включить исследовательский GetSpectrum после локальной проверки IDP; не эквивалент original MVKView')
        stack.addWidget(self.spec_envelope_button)
        self.spec_envelope_code=QComboBox()
        self.spec_envelope_code.addItem('Код не выбран',0)
        for code in range(1,32):
            self.spec_envelope_code.addItem(f'Код {code} · IDR огибающая',code)
        self.spec_envelope_code.setEnabled(False)
        self.spec_envelope_code.setToolTip('Исходные коды 1..31, только с проверенным локальным mvkview.idp')
        stack.addWidget(self.spec_envelope_code)

        self.spec_mode=QComboBox()
        self.spec_mode.setObjectName('bSpecType')
        self.spec_mode.addItems(['Логарифмич.','Линейный ВУ',
                                 'Линейный ВС','Линейный ВП'])
        self.spec_mode.setFixedHeight(41)
        stack.addWidget(self.spec_mode)

        self.spec_n=QComboBox()
        self.spec_n.setObjectName('bSpecLines')
        # Six exact original source Tag values in original Delphi order;
        # research 1024/4096 retain the short-archive testing workflow.
        for entry in original_fft_size_options():
            self.spec_n.addItem(str(entry['n_fft']),entry['n_fft'])
            self.spec_n.setItemData(self.spec_n.count()-1,
                'ИСХОДНЫЙ Delphi bSpecLines · оригинальный NFFT',Qt.ToolTipRole)
        for n in RESEARCH_FFT_SIZES:
            self.spec_n.addItem(str(n),n)
            self.spec_n.setItemData(self.spec_n.count()-1,
                'ТОЛЬКО ИССЛЕДОВАНИЕ · в оригинальном MVKView этого N нет',
                Qt.ToolTipRole)
        self.spec_n.setCurrentText('65536')
        self.spec_n.setFixedHeight(41)
        self.spec_n.setToolTip(
            '262144…8192 — шесть проверенных исходных NFFT. '
            '1024/4096 — исследовательские для коротких архивов; '
            'без полной реальной истории BIN спектр не вычисляется.')
        stack.addWidget(self.spec_n)
        self.spec_n_provenance=QLabel('FFT: исходный пресет; нужна история BIN')
        self.spec_n_provenance.setWordWrap(True)
        self.spec_n_provenance.setObjectName('lbSpecFFTProvenance')
        stack.addWidget(self.spec_n_provenance)
        # Presenter for the original bSpecLines. Keep self.spec_n as the one
        # authoritative FFT N model: existing callbacks/QA still use it.
        self.spec_lines_button=QToolButton()
        self.spec_lines_button.setObjectName('bSpecLinesPresenter')
        self.spec_lines_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.spec_lines_button.setPopupMode(QToolButton.InstantPopup)
        self.spec_lines_button.setFixedHeight(37)
        self.spec_lines_menu=QMenu(self.spec_lines_button)
        self._spec_lines_actions=[]
        for i in range(self.spec_n.count()):
            n=int(self.spec_n.itemData(i))
            a=self.spec_lines_menu.addAction(str(n))
            a.setData(n)
            a.setCheckable(True)
            a.triggered.connect(
                lambda checked=False,index=i:self.spec_n.setCurrentIndex(index))
            self._spec_lines_actions.append(a)
        self.spec_lines_button.setMenu(self.spec_lines_menu)
        self.spec_lines_button.setToolTip(
            'Частотное разрешение Δf=Fs/N. Оригинальный набор FFT и '
            'исследовательские малые N доступны только при достаточной истории.')

        # Original bSpecHScale is a VCL split button with ten numeric
        # source-defined menu presets. Preserve quick-click zoom while
        # exposing verified original menu values in the arrow popup.
        self.spec_hscale_button=QToolButton()
        self.spec_hscale_button.setText('Диапазон X')
        self.spec_hscale_button.setObjectName('bSpecHScale')
        self.spec_hscale_button.setFixedHeight(41)
        self.spec_hscale_button.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        self.spec_hscale_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.spec_hscale_button.setPopupMode(QToolButton.MenuButtonPopup)
        self.spec_hscale_button.setToolTip(
            'Стрелка: десять восстановленных шкал оригинальной MVKView. '
            'Основное нажатие выбирает ближайший меньший оригинальный масштаб.')
        self.spec_hscale_menu=QMenu(self.spec_hscale_button)
        self._spec_hscale_actions=[]
        self._spec_original_hscale_selected=None
        for entry in original_h_scale_options():
            a=self.spec_hscale_menu.addAction(entry['caption'])
            a.setCheckable(True)
            a.setData(entry['hz'])
            a.triggered.connect(
                lambda checked=False,hz=entry['hz']:self._select_original_hscale(hz))
            self._spec_hscale_actions.append(a)
        self.spec_hscale_button.setMenu(self.spec_hscale_menu)
        self.spec_hscale_button.clicked.connect(self._cycle_original_hscale)
        stack.addWidget(self.spec_hscale_button)

        self.spec_vscale_button=QToolButton()
        self.spec_vscale_button.setObjectName('bSpecVScale')
        self.spec_vscale_button.setText('Шкала Y')
        self.spec_vscale_button.setFixedHeight(41)
        self.spec_vscale_button.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        self.spec_vscale_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.spec_vscale_button.setPopupMode(QToolButton.MenuButtonPopup)
        self.spec_vscale_button.setToolTip(
            'Шесть исходных вертикальных масштабов dB/физических единиц. '
            'Qt baseline из данных — исследовательский, реальный GraphDefaultVScale не измерен.')
        self.spec_vscale_menu=QMenu(self.spec_vscale_button)
        self._spec_vscale_actions=[]
        self._spec_original_vscale_tag=None
        self._spec_original_vscale_mode=None
        self._spec_vertical_model=None
        self._spec_vscroll_source_candidate=None
        self._rebuild_original_vscale_menu()
        self.spec_vscale_button.setMenu(self.spec_vscale_menu)
        self.spec_vscale_button.clicked.connect(self._cycle_original_vscale)
        stack.addWidget(self.spec_vscale_button)

        self.spec_hint=QLabel('Спектр ещё не открыт')
        self.spec_hint.setObjectName('lbSpecHint')
        self.spec_hint.setWordWrap(True)
        self.spec_hint.setMinimumHeight(64)
        self.spec_hint.setTextInteractionFlags(Qt.TextSelectableByMouse)
        stack.addWidget(self.spec_hint)

        self.spec_mean=QLabel('Данные спектра: —')
        self.spec_mean.setObjectName('lbSpecMean')
        self.spec_mean.setWordWrap(True)
        stack.addWidget(self.spec_mean)

        self.spec_copy_button=QPushButton('Копировать')
        self.spec_copy_button.setObjectName('bSpecCopyValue')
        self.spec_copy_button.setFixedHeight(41)
        self.spec_copy_button.setEnabled(False)
        self.spec_copy_button.setToolTip(
            'Только 3 локально вычисленные значения: сумма/пик-частота/пик-амплитуда. '
            'Табуляция как в 0084BC28; оригинальная Delphi точность не принята')
        self.spec_copy_button.clicked.connect(self._copy_spec_summary)
        stack.addWidget(self.spec_copy_button)

        self.spec_save_button=QPushButton('Сохранить CSV')
        self.spec_save_button.setObjectName('bSpecSaveValue')
        self.spec_save_button.setFixedHeight(41)
        self.spec_save_button.setEnabled(False)
        self.spec_save_button.setToolTip(
            'Только локальный CSV sep=|, отдельный от оригинальных SPEC-FREQ; '
            'исходные BIN/IDP не записываются')
        self.spec_save_button.clicked.connect(self._save_spec_summary)
        stack.addWidget(self.spec_save_button)
        self.spec_original_copy_compare=QPushButton('Сверить с MVKView…')
        self.spec_original_copy_compare.setToolTip(
            'Только локальный TXT из оригинальной MVKView (TAB, десятичная запятая). '
            'Не подключается к прибору, не сохраняет исходные данные, '
            'не подтверждает побитовый паритет Delphi.')
        self.spec_original_copy_compare.setEnabled(False)
        self.spec_original_copy_compare.clicked.connect(self._compare_original_copy)
        stack.addWidget(self.spec_original_copy_compare)
        self.spec_canvas_geometry_button=QPushButton('Геометрия Canvas')
        self.spec_canvas_geometry_button.setToolTip(
            'Независимые исходные TQGrapher itosM/itosC и stoiM/с по 007CA4C8. '
            'Использует только текущие размеры шрифта Qt, НЕ оригинальный Delphi Canvas.')
        self.spec_canvas_geometry_button.setEnabled(False)
        self.spec_canvas_geometry_button.clicked.connect(self._show_canvas_geometry_candidate)
        stack.addWidget(self.spec_canvas_geometry_button)

        separator=QFrame()
        separator.setFrameShape(QFrame.HLine)
        stack.addWidget(separator)
        title=QLabel('ИССЛЕДОВАТЕЛЬСКИЕ НАСТРОЙКИ')
        title.setWordWrap(True)
        stack.addWidget(title)
        self.spec_backend=QComboBox()
        self.spec_backend.addItems(['IDR float32 · реконструкция','NumPy · контрольный расчёт'])
        stack.addWidget(self.spec_backend)

        stack.addWidget(QLabel('Частоты до, Гц'))
        self.spec_hz=self._float(10,32768,25600,1)
        stack.addWidget(self.spec_hz)
        self.spec_manual_f_range_label=QLabel(
            'FRange гипотезы архива · НЕ x32dbg')
        self.spec_manual_f_range_label.setObjectName(
            'labelArchiveAssumedFRangeDistinctFromOriginal')
        stack.addWidget(self.spec_manual_f_range_label)
        self.spec_f_range=self._float(0.000001,1000000.0,1.,6)
        self.spec_f_range.setToolTip(
            'Только исследовательская гипотеза FRange архива BIN/TSXML '
            '(по умолчанию 1). Значение НЕ равно подтверждённому FRange '
            'отдельного исходного спектра x32dbg. Для эталона читается '
            'точный Single из локального JSON; spinbox его не подменяет.')
        stack.addWidget(self.spec_f_range)
        self.spec_graph_default_label=QLabel(
            'GraphDefaultVScale: исходный расчёт ещё не применён')
        self.spec_graph_default_label.setObjectName('lbSpecGraphDefaultVScaleCandidate')
        self.spec_graph_default_label.setWordWrap(True)
        self.spec_graph_default_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.spec_graph_default_label.setToolTip(
            'Восстановленная последовательность _Unit128:0084B5D3..0084B882: '
            'FRange канала ×1/10/100, округление 1–2–5×10^n. '
            'Здесь FRange — введённая гипотеза, не подтверждённая исходным каналом; '
            'точный x87/Delphi и оригинальные пиксели Y не приняты.')
        self._spec_graph_default_vscale_candidate=None
        stack.addWidget(self.spec_graph_default_label)
        stack.addWidget(QLabel('Источник FRange · только исследование'))
        self.spec_input_domain=QComboBox()
        self.spec_input_domain.addItem('Native BIN · калиброванные данные', 'calibrated_bin')
        self.spec_input_domain.addItem('Оригинальное кольцо / FRange · гипотеза', 'original_float_storage')
        self.spec_input_domain.setToolTip(
            'Original GetSpectrum для float-кольца сначала делит на FRange '
            'ДО удаления DC и до FIR огибающей (Stage111J), потом '
            'возвращает масштаб на линейном выходе. '
            'Это ГИПОТЕЗА о происхождении Native BIN, а не автоматическая '
            'калибровка; не выбирать без независимого оригинального эталона.')
        stack.addWidget(self.spec_input_domain)
        self.spec_last=QCheckBox('Последнее полное окно')
        self.spec_last.setChecked(True)
        stack.addWidget(self.spec_last)
        self.spec_precise=QCheckBox('Пик в пикселе (IDR)')
        self.spec_precise.setChecked(True)
        self.spec_precise.setToolTip('Original TQGrapher FindPreciseXValue=1')
        stack.addWidget(self.spec_precise)
        self.spec_avg=QComboBox()
        self.spec_avg.addItems(['1 · значение бина','3 · √суммы квадратов, без деления'])
        self.spec_avg.setCurrentIndex(0)
        self.spec_avg.setToolTip('Original CursorAveraging 1/3; 3 uses sqrt(sum squares), NOT RMS')
        stack.addWidget(self.spec_avg)

        reload=QPushButton('Обновить спектр')
        reload.clicked.connect(self.refresh_spec)
        stack.addWidget(reload)
        self.spec_compare_button=QPushButton('Сравнить FFT')
        self.spec_compare_button.setToolTip('IDR float32 vs NumPy; НЕ эталонный Delphi')
        self.spec_compare_button.clicked.connect(self.compare_fft)
        stack.addWidget(self.spec_compare_button)
        reset=QPushButton('Сбросить масштаб')
        reset.clicked.connect(self.refresh_spec)
        stack.addWidget(reset)

        stack.addWidget(QLabel('IDR УЗКАЯ ПОЛОСА · исследование (не DSP)'))
        stack.addWidget(QLabel('Заданная частота, Гц'))
        self.narrow_frequency=self._float(0.001,32768,64,3)
        self.narrow_frequency.setToolTip('TMvkChannelStorage.GetNarrowbandValue InputValue, 007D0E58')
        stack.addWidget(self.narrow_frequency)
        self.narrow_noise=QCheckBox('Дополнительно шумовой пик')
        self.narrow_noise.setToolTip('GetNoisePeak=True: 3-bin scan excluding ±20*radius of reference bin')
        stack.addWidget(self.narrow_noise)
        self.narrow_run=QPushButton('Рассчитать узкую полосу')
        self.narrow_run.setToolTip('Отдельный локальный FFT, без AUX4700, сети, команды прибору или подстановки значений')
        self.narrow_run.clicked.connect(self._run_narrowband)
        stack.addWidget(self.narrow_run)
        self.narrow_result=QLabel('Узкополосный результат: —')
        self.narrow_result.setWordWrap(True)
        self.narrow_result.setTextInteractionFlags(Qt.TextSelectableByMouse)
        stack.addWidget(self.narrow_result)
        stack.addStretch()
        # Separate the NINE primary original PageSpectrum widgets from
        # numerous research-specific controls. Keep EVERY legacy widget
        # and all signals/functions, but put diagnostics into a separate
        # hideable native Qt dock, never between cursor/summary/Copy/Save.
        self.spec_cursor_primary=QLabel('Курсор: —')
        self.spec_cursor_primary.setObjectName('lbSpecHintPrimary')
        self.spec_cursor_primary.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.spec_cursor_primary.setFixedHeight(48)
        self.spec_cursor_primary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.spec_mean_primary=QLabel('Сначала откройте измерение')
        self.spec_mean_primary.setObjectName('lbSpecMeanPrimary')
        self.spec_mean_primary.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.spec_mean_primary.setWordWrap(True)
        self.spec_mean_primary.setFixedHeight(106)
        self.spec_mean_primary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.spec_advanced_button=QPushButton('Исследование ▸')
        self.spec_advanced_button.setObjectName('openSpectrumResearch')
        self.spec_advanced_button.setFixedHeight(29)
        self.spec_advanced_button.setToolTip(
            'Показать дополнительные FFT, FRange, IDR, Canvas и узкополосные '
            'исследовательские параметры; обычный спектр остаётся на виду.')
        self.spec_inspector=QDockWidget('Исследование · диагностика спектра',self)
        self.spec_inspector.setObjectName('spectrumResearchDock')
        self.spec_inspector.setAllowedAreas(
            Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        research_scroll=QScrollArea()
        research_scroll.setObjectName('spectrumResearchScroll')
        research_scroll.setWidgetResizable(True)
        research_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        research_body=QWidget()
        research_body.setObjectName('spectrumResearchBody')
        research_stack=QVBoxLayout(research_body)
        research_stack.setContentsMargins(8,8,8,8)
        research_stack.setSpacing(6)
        self.spec_source_gain_label=QLabel(
            'TSXML / FRange: источник не открыт')
        self.spec_source_gain_label.setObjectName('researchOriginalTsxmlGain')
        self.spec_source_gain_label.setWordWrap(True)
        self.spec_source_gain_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse)
        self.spec_source_gain_label.setToolTip(
            'В оригинальном TSXML InternalChannelGain берётся из '
            'TMvkCellList.GetFloatByAddr(0x0E) и при чтении попадает в '
            'TMvkChannelStorage.FRange. Это статический источник, НЕ '
            'подтверждённый численный коэффициент текущих исходных отсчётов.')
        research_stack.addWidget(self.spec_source_gain_label)
        self.spec_x32dbg_f_range_label=QLabel(
            'FRange x32dbg: эталон не открыт; ручной FRange архива — отдельно.')
        self.spec_x32dbg_f_range_label.setObjectName(
            'labelActualX32dbgFRange')
        self.spec_x32dbg_f_range_label.setWordWrap(True)
        self.spec_x32dbg_f_range_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse)
        self.spec_x32dbg_f_range_label.setToolTip(
            'FRange конкретного сохранённого оригинального GetSpectrum '
            'принимается только из проверенного локального JSON-манифеста. '
            'Поле FRange=1 ниже относится к независимой гипотезе архива.')
        research_stack.addWidget(self.spec_x32dbg_f_range_label)
        self.spec_reference_open_button=QPushButton('Эталон x32dbg · открыть Power/Y…')
        self.spec_reference_open_button.setObjectName('openOriginalX32dbgSpectrumReference')
        self.spec_reference_open_button.setToolTip(
            'Локальный проверенный манифест + Power/Y в той же папке. '
            'Проверка всех Float32, рисование на основном Qt-графике, '
            'без повторного FFT и без копирования приватных данных.')
        self.spec_reference_open_button.clicked.connect(
            self.choose_original_spectrum_reference)
        research_stack.addWidget(self.spec_reference_open_button)
        self.spec_reference_restore_button=QPushButton('Вернуться к архивному спектру')
        self.spec_reference_restore_button.setObjectName('restoreArchivedSpectrumFromReference')
        self.spec_reference_restore_button.setEnabled(False)
        self.spec_reference_restore_button.clicked.connect(
            self.restore_archive_spectrum_after_reference)
        research_stack.addWidget(self.spec_reference_restore_button)
        self.spec_source_grid_checkbox=QCheckBox(
            'Сетка TQGrapher 10×10 · исследовательская')
        self.spec_source_grid_checkbox.setObjectName(
            'toggleSourceTQGrapherGridCandidate')
        self.spec_source_grid_checkbox.setToolTip(
            'Исходные _Unit128:00844B2B/32 и _Unit115:007CAC89: '
            '10 интервалов X/Y, Single spacing. ТОЛЬКО локальный '
            'проверенный Power/Y x32dbg; реальный Delphi TCanvas, '
            'цвет сетки TCo2Draw #C0C0C0 и фон #FFFFFF восстановлены. '
            'Software AA и TCanvas.TextOut не равны Qt; '
            'runtime шрифт/DPI/пиксели ещё НЕ приняты.')
        self.spec_source_grid_checkbox.setEnabled(False)
        self.spec_source_grid_checkbox.toggled.connect(
            self._toggle_source_tqgrapher_grid_candidate)
        research_stack.addWidget(self.spec_source_grid_checkbox)
        self.spec_source_raster_checkbox=QCheckBox(
            'Растер TCo2Draw по исходному алгоритму · исследовательский')
        self.spec_source_raster_checkbox.setObjectName(
            'toggleSourceTCo2DrawRaster')
        self.spec_source_raster_checkbox.setToolTip(
            'X/Y-major, 3 пикселя и смешивание RGB из Unit115. Только '
            'проверенный эталон Power/Y, логический Qt ViewBox. '
            'НЕ оригинальный PixelRect, Delphi DPI или TCanvas.Font.')
        self.spec_source_raster_checkbox.setEnabled(False)
        self.spec_source_raster_checkbox.toggled.connect(
            self._toggle_source_tco2draw_raster)
        research_stack.addWidget(self.spec_source_raster_checkbox)
        self.spec_source_series_checkbox=QCheckBox(
            'Кривая TQGRSeries · минимум/максимум по пикселям')
        self.spec_source_series_checkbox.setObjectName(
            'toggleSourceTQGRSeriesPixelColumns')
        self.spec_source_series_checkbox.setToolTip(
            'Исходный алгоритм Unit115:007CB12F-007CB3E5: по одному '
            'экранному X собираются min/max из нескольких Float32, '
            'с сохранением ближайшего порядка обхода и клиппинга. '
            'Только SHA-verified Power/Y; Qt logical viewport НЕ '
            'равен исходному TPaintBox/Win32 DPI/пикселям.')
        self.spec_source_series_checkbox.setEnabled(False)
        self.spec_source_series_checkbox.toggled.connect(
            self._toggle_source_tqgr_series_candidate)
        research_stack.addWidget(self.spec_source_series_checkbox)
        self.spec_source_series_info=QLabel(
            'Кривая: обычная Qt. Источник TQGRSeries доступен '
            'только для проверенного оригинального Power/Y.')
        self.spec_source_series_info.setObjectName(
            'labelSourceTQGRSeriesPixelResearchOnly')
        self.spec_source_series_info.setWordWrap(True)
        self.spec_source_series_info.setTextInteractionFlags(
            Qt.TextSelectableByMouse)
        research_stack.addWidget(self.spec_source_series_info)
        self.spec_source_grid_info=QLabel(
            'Сетка Qt: обычная. TQGrapher 10×10 доступна '
            'только для проверенного оригинального Power/Y.')
        self.spec_source_grid_info.setObjectName(
            'labelSourceTQGrapherGridResearchOnly')
        self.spec_source_grid_info.setWordWrap(True)
        self.spec_source_grid_info.setTextInteractionFlags(
            Qt.TextSelectableByMouse)
        research_stack.addWidget(self.spec_source_grid_info)
        legacy=[]
        while stack.count():
            item=stack.takeAt(0)
            if item.widget() is not None:
                legacy.append(item.widget())
        primary=[
            self.spec_envelope_button,self.spec_mode,self.spec_lines_button,
            self.spec_hscale_button,self.spec_vscale_button,
            self.spec_cursor_primary,self.spec_mean_primary,
            self.spec_copy_button,self.spec_save_button,
        ]
        original_primary=set(primary)
        for widget in legacy:
            if widget not in original_primary:
                research_stack.addWidget(widget)
        research_stack.addStretch()
        research_scroll.setWidget(research_body)
        self.spec_inspector.setWidget(research_scroll)
        self.addDockWidget(Qt.RightDockWidgetArea,self.spec_inspector)
        self.spec_inspector.hide()
        self.spec_advanced_button.clicked.connect(
            lambda:self.spec_inspector.setVisible(not self.spec_inspector.isVisible()))
        self.spec_inspector.visibilityChanged.connect(
            lambda visible:self.spec_advanced_button.setText(
                'Исследование ◂' if visible else 'Исследование ▸'))
        self._spectrum_primary_order=tuple(w.objectName() for w in primary)
        for widget in primary:
            widget.setMinimumWidth(0)
            widget.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
            if widget in (
                self.spec_envelope_button,self.spec_mode,
                self.spec_hscale_button,self.spec_vscale_button,
                self.spec_copy_button,self.spec_save_button):
                widget.setFixedHeight(37)
            stack.addWidget(widget)
        stack.addWidget(self.spec_advanced_button)
        stack.addStretch()
        self._sync_spec_lines_presentation()
        # QScrollArea expands child minSizeHint from long Russian strings.
        # Explicitly permit wrapping/shrinking to the actual sidebar width,
        # so only VERTICAL scrolling is needed for research diagnostics.
        for child in tools.findChildren(QWidget):
            if isinstance(child,QLabel):
                child.setWordWrap(True)
                child.setMinimumWidth(0)
                child.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
            elif isinstance(child,(QPushButton,QComboBox,QToolButton,QDoubleSpinBox,QCheckBox)):
                child.setMinimumWidth(0)
                child.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
        tools.setMinimumWidth(0)
        research_body.setMinimumWidth(0)
        for child in research_body.findChildren(QWidget):
            if isinstance(child,QLabel):
                child.setWordWrap(True)
                child.setMinimumWidth(0)
                child.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
            elif isinstance(child,(QPushButton,QComboBox,QToolButton,QDoubleSpinBox,QCheckBox)):
                child.setMinimumWidth(0)
        self.spec_tools.setWidget(tools)
        lay.addWidget(self.spec_tools,0)

        graph=QWidget()
        graph.setObjectName('pnSpecGraph')
        grid=QVBoxLayout(graph)
        grid.setContentsMargins(8,8,0,8)
        grid.setSpacing(0)
        self.spec_hscroll=QScrollBar(Qt.Horizontal)
        self.spec_hscroll.setObjectName('sbSpecHScroll')
        self.spec_hscroll.setFixedHeight(24)
        self.spec_hscroll.setRange(0,0)
        self.spec_hscroll.setPageStep(1)
        self.spec_hscroll.setToolTip(
            'Исходная модель TScrollBar: целочисленные позиции Гц, '
            'PageSize=размер видимого окна. Исходные десять масштабов '
            'ещё не все восстановлены; это Qt-кандидат.')
        self.spec_hscroll.hide()
        grid.addWidget(self.spec_hscroll)
        chart=QHBoxLayout()
        chart.setContentsMargins(0,0,0,0)
        chart.setSpacing(0)
        self.spec_plot=self._plot('Частота, Гц','Амплитуда')
        self.spec_plot.setObjectName('pbSpectrum')
        self.spec_plot.scene().sigMouseClicked.connect(self._spec_click)
        self.spec_plot.scene().sigMouseMoved.connect(self._spec_mouse_move)
        chart.addWidget(self.spec_plot,1)
        self.spec_vscroll=QScrollBar(Qt.Vertical)
        self.spec_vscroll.setObjectName('sbSpecVScroll')
        self.spec_vscroll.setFixedWidth(24)
        self.spec_vscroll.setRange(0,1000)
        self.spec_vscroll.setPageStep(50)
        self.spec_vscroll.hide()
        chart.addWidget(self.spec_vscroll)
        grid.addLayout(chart,1)
        lay.addWidget(graph,1)
        self._spec_data_ymin=0.
        self._spec_data_ymax=1.
        self._spec_hscroll_source_candidate=None
        self.spec_hscroll.valueChanged.connect(lambda v:self._spec_scroll_changed(0,v))
        self.spec_vscroll.valueChanged.connect(lambda v:self._spec_scroll_changed(1,v))
        self.spec_plot.getViewBox().sigRangeChanged.connect(self._sync_spec_scroll)
        self.spec_plot.getViewBox().sigRangeChanged.connect(
            self._sync_source_tqgrapher_grid_candidate)
        self.spec_plot.getViewBox().sigResized.connect(
            self._sync_source_tqgrapher_grid_candidate)
        self.spec_plot.getViewBox().sigRangeChanged.connect(
            self._sync_source_tqgr_series_candidate)
        self.spec_plot.getViewBox().sigResized.connect(
            self._sync_source_tqgr_series_candidate)
        self.spec_plot.getViewBox().sigRangeChanged.connect(
            self._sync_archive_source_projection)
        self.spec_plot.getViewBox().sigResized.connect(
            self._sync_archive_source_projection)

        self.spec_mode.currentIndexChanged.connect(self._change_spectrum_mode)
        self._spec_last_valid_fft_n=None
        self.spec_n.currentIndexChanged.connect(self._spec_n_changed)
        self.spec_backend.currentIndexChanged.connect(self.refresh_spec)
        self.spec_last.toggled.connect(self.refresh_spec)
        self.spec_hz.editingFinished.connect(self.refresh_spec)
        self.spec_f_range.editingFinished.connect(self.refresh_spec)
        self.spec_input_domain.currentIndexChanged.connect(self.refresh_spec)
        self.spec_envelope_button.toggled.connect(self._toggle_spec_envelope)
        self.spec_envelope_code.currentIndexChanged.connect(self._spec_envelope_code_changed)

    def _sync_spec_lines_presentation(self, fs=None):
        """Single FFT-size model, original Hz-per-line presentation."""
        if fs is not None:
            self._spec_loaded_sample_rate_hz=float(fs)
        n=int(self.spec_n.currentData())
        sample_rate=self._spec_loaded_sample_rate_hz
        if sample_rate is None:
            caption='FFT: '+str(n)
        else:
            step=sample_rate/n
            ratio=Fraction(step).limit_denominator(10000)
            if abs(float(ratio)-step)<1e-8 and ratio.denominator<=64:
                value=(str(ratio.numerator) if ratio.denominator==1
                       else f'{ratio.numerator}/{ratio.denominator}')
            else:
                value=f'{step:.6g}'
            caption=value+' Гц/лин'
        self.spec_lines_button.setText(caption)
        self.spec_lines_button.setToolTip(
            'FFT N='+str(n)+'; Δf='+(
                f'{sample_rate/n:.10g} Гц' if sample_rate else 'неизвестно')
            +'. Спектр не дополняется нулями.')
        for index,action in enumerate(self._spec_lines_actions):
            count=int(self.spec_n.itemData(index))
            item=self.spec_n.model().item(index)
            action.setEnabled(item.isEnabled() if item is not None else True)
            action.setChecked(count==n)
            if sample_rate:
                action.setText(
                    f'{sample_rate/count:.6g} Гц/лин · FFT {count}'
                    + (' · исследование' if count in RESEARCH_FFT_SIZES else ''))
            else:
                action.setText('FFT '+str(count))

    def _sync_spectrum_summary_primary(self):
        """Compact original-looking text with explicit calibration status."""
        summary=self._spectrum_summary
        if not isinstance(summary,dict):
            self.spec_mean_primary.setText('СКЗ спектра: —\nПик спектра: —')
            return
        try:
            fields=spectrum_triplet_text(
                summary,decimal_separator=',').split('\t')
        except (ValueError,KeyError,TypeError,OverflowError):
            self.spec_mean_primary.setText('Итоги не рассчитаны')
            return
        if isinstance(self.session,DirectBinSession):
            unit='усл. ед.'
            calibration='Калибровка НЕ подтверждена'
        else:
            unit='расч. ед.'
            calibration='Расчётный спектр · оригинал не аттестован'
        self.spec_mean_primary.setText(
            f'СКЗ спектра: {fields[0]} {unit}\n'
            f'Пик спектра: {fields[1]} Гц\n'
            f'Амплитуда: {fields[2]} {unit}\n'
            + calibration)
        self.spec_mean_primary.setToolTip(
            'Результаты получены локальным GetSpectrum-кандидатом; '
            'не считать приборным DSP или оригинально калиброванными.')

    def _rebuild_original_vscale_menu(self):
        """Source Tag order changes with original spectrum mode."""
        self.spec_vscale_menu.clear()
        self._spec_vscale_actions=[]
        for entry in original_v_scale_options(self.spec_mode.currentIndex()):
            action=self.spec_vscale_menu.addAction(entry['caption'])
            action.setCheckable(True)
            action.setData(entry['tag'])
            action.triggered.connect(
                lambda checked=False,tag=entry['tag']:self._select_original_vscale(tag))
            self._spec_vscale_actions.append(action)

    def _cycle_original_vscale(self):
        if self._full_spectrum is None:return
        old=self._spec_original_vscale_tag
        next_tag=1 if old is None else min(5,old+1)
        self._select_original_vscale(next_tag)

    def _select_original_vscale(self,tag:int):
        """Actual source menu page and scroll position, Qt Y origin candidate."""
        if self._full_spectrum is None:return
        mode=self.spec_mode.currentIndex()
        old=self._spec_vertical_model if self._spec_original_vscale_mode==mode else None
        choice=source_vertical_selection(mode,tag,
            old_tag=old['source_menu_tag'] if old else None,
            old_position=old['delphi_position'] if old else 0)
        self._spec_original_vscale_mode=mode
        self._spec_original_vscale_tag=tag
        self._apply_original_vscale_candidate(choice)
        name=original_v_scale_options(mode)[tag]['caption']
        self.spec_vscale_button.setText(name)
        for action in self._spec_vscale_actions:
            action.setChecked(int(action.data())==tag)
        self.statusBar().showMessage(
            'Исходный V PageSize='+str(choice['page'])+
            '; текущий Qt GraphDefaultVScale — исследовательский, '
            'Delphi Canvas/FFT численно не принят')

    def _apply_original_vscale_candidate(self,choice:dict):
        """Source VCL range/position; Y baseline from Qt data, NOT Delphi."""
        mode=self.spec_mode.currentIndex()
        db=mode==0
        default_scale=max(1e-8,self._spec_data_ymax-self._spec_data_ymin)
        divisor=1 if db else int(choice['physical_divisor'])
        # Archive candidate keeps its local-data baseline because its
        # effective original FRange has NOT been independently established.
        # A separately imported operator x32dbg Power/Y reference *does*
        # carry an explicit FRange Single word, so it can use the original
        # source-derived absolute Y scroll model WITHOUT an invented offset.
        reference=self._spectrum_reference
        exact_operator_frange=reference is not None
        f_range=(reference.f_range if exact_operator_frange
                 else self.spec_f_range.value())
        local_native=source_spectrum_v_scr(
            choice['delphi_position'],choice['page'],choice['full'],
            db_mode=db,graph_default_v_scale=default_scale,
            scale_divisor=divisor)
        source_scale=spectrum_graph_default_vscale(f_range,mode)
        native_with_source_frange_candidate=source_spectrum_v_scr(
            choice['delphi_position'],choice['page'],choice['full'],
            db_mode=db,
            graph_default_v_scale=source_scale['candidate_graph_default_vscale_single'],
            scale_divisor=divisor)
        self._spec_graph_default_vscale_candidate=source_scale
        self._update_original_vscale_candidate_label(source_scale)
        if exact_operator_frange:
            native=native_with_source_frange_candidate
            offset=0.
        else:
            native=local_native
            # Original dB ScrBottom is relative to zero; for uncalibrated
            # archives Qt retains an explicit data-derived research offset.
            offset=(self._spec_data_ymax if db else self._spec_data_ymin)
        lower=offset+native['scr_bottom_single']
        upper=lower+native['scr_height_single']
        if not math.isfinite(lower) or not math.isfinite(upper) or upper<=lower:
            raise ValueError('Unrepresentable Qt Y view for source V scale')
        self._spec_vertical_model=choice
        self._spec_vscroll_source_candidate={
            **native,'source_v_menu_tag':choice['source_menu_tag'],
            'source_menu_values_verified':True,
            'source_graph_default_vscale_formula_candidate':source_scale,
            'source_y_scroll_using_manual_frange_candidate':native_with_source_frange_candidate,
            'local_manual_frange_is_original_verified':False,
            'qt_original_graph_default_vscale_estimated':not exact_operator_frange,
            'qt_y_baseline_from_local_spectrum':not exact_operator_frange,
            'operator_reference_f_range_word_used':exact_operator_frange,
            'original_delphi_y_canvas_parity_verified':False}
        bar=self.spec_vscroll
        bar.blockSignals(True)
        bar.setRange(0,choice['qt_maximum'])
        bar.setPageStep(choice['qt_page_step'])
        bar.setSingleStep(choice['qt_single_step'])
        bar.setValue(choice['delphi_position'])
        bar.setVisible(choice['delphi_visible'])
        bar.blockSignals(False)
        self.spec_plot.getViewBox().setYRange(lower,upper,padding=0)

    def _update_original_vscale_candidate_label(self,candidate:dict):
        """Separate original initial CW from actual runtime CW and Qt Y."""
        warning=(
            ' · На границе x87 результат Python требует аппаратной сверки'
            if candidate['original_x87_boundary_requires_runtime_reference']
            else '')
        source_scope=(
            'Single FRange взят из проверенного x32dbg JSON; '
            'оригинальное x87/Canvas ЕЩЁ НЕ СВЕРЕНЫ'
            if self._spectrum_reference is not None
            else 'FRange гипотезы архива и x87 НЕ ПОДТВЕРЖДЕНЫ')
        self.spec_graph_default_label.setText(
            "GraphDefaultVScale · реконструкция _Unit128: "
            f"FRange={candidate['candidate_f_range_single']:.7g} ×"
            f"{candidate['source_mode_multiplier']} → "
            f"{candidate['candidate_graph_default_vscale_single']:.7g}; "
            + source_scope + '; '
            f"исходное CW={candidate['original_idr_static_initial_x87_cw_hex']} "
            "(PC64, runtime не измерен)" + warning)

    def _spec_history_gate(self,n_fft:int,total_samples:int,fs:float)->dict:
        """Validate source FIR or plain FFT history before any recomputation."""
        if self.spec_envelope_button.isChecked():
            code=int(self.spec_envelope_code.currentData() or 0)
            if not code or self.envelope_profile is None:
                raise ValueError('Для исходной FFT огибающей нужен локальный IDP и код')
            if not float(fs).is_integer():
                raise ValueError('Режим исходной огибающей требует целый sample rate')
            required=required_original_history(n_fft,int(fs),code)['input_samples']
            end=(total_samples if self.spec_last.isChecked() else
                 round((self.wave_start.value()+self.wave_seconds.value())*fs))
            return fft_source_archive_gate(
                n_fft,total_samples,end_sample=end,
                required_input_samples=required)
        remaining=(total_samples if self.spec_last.isChecked() else
                   max(0,total_samples-round(self.wave_start.value()*fs)))
        return fft_source_archive_gate(n_fft,remaining)

    def _sync_fft_menu_availability(self,*,samples_count=None,sample_rate=None):
        """Disable original NFFT that needs more real BIN data; no zero padding."""
        if self.session is None:return
        if samples_count is None or sample_rate is None:
            samples,fs,_,_=self.session.samples(self._ch())
            samples_count=len(samples);sample_rate=fs
        for index in range(self.spec_n.count()):
            n=int(self.spec_n.itemData(index))
            try:
                gate=self._spec_history_gate(n,samples_count,sample_rate)
                allowed=gate['can_compute_without_padding']
            except (ValueError,TypeError):
                allowed=False
            item=self.spec_n.model().item(index)
            item.setEnabled(bool(allowed))
            label=('ОРИГИНАЛ MVKView' if n in FFT_WINDOW_SAMPLES
                   else 'ИССЛЕДОВАТЕЛЬСКИЙ FFT, не оригинальный пресет')
            item.setToolTip(
                label+(' · достаточно реальных отсчётов BIN'
                       if allowed else ' · недостаточно истории BIN; запрещён'))
        self._sync_spec_lines_presentation(sample_rate)

    def _spec_n_changed(self,*_):
        """Reject unavailable N without discarding already rendered FFT."""
        if self.session is None:return
        requested=int(self.spec_n.currentData())
        try:
            samples,fs,_,_=self.session.samples(self._ch())
            gate=self._spec_history_gate(requested,len(samples),fs)
            if not gate['can_compute_without_padding']:
                raise ValueError(
                    f"FFT N={requested}: требуется {gate['required_real_history_samples']} "
                    f"реальных отсчётов, доступно {gate['archive_end_sample']}; "
                    "нулевое дополнение запрещено")
        except (OSError,ValueError,TypeError,KeyError) as exc:
            if self._spec_last_valid_fft_n is not None:
                self.spec_n.blockSignals(True)
                self.spec_n.setCurrentText(str(self._spec_last_valid_fft_n))
                self.spec_n.blockSignals(False)
            self.statusBar().showMessage('Исходный FFT отклонён: '+str(exc))
            return
        self._sync_spec_lines_presentation()
        self.refresh_spec()

    def _cycle_original_hscale(self):
        """Main part of split button: next source-verified smaller scale."""
        if self._full_spectrum is None:return
        x0,x1=self.spec_plot.getViewBox().viewRange()[0]
        current=float(x1-x0)
        for hz in HORIZONTAL_HZ:
            if float(hz)<current-.01:
                self._select_original_hscale(hz)
                return
        self._select_original_hscale(HORIZONTAL_HZ[-1])

    def _select_original_hscale(self,hz):
        """Original _Unit128:0084C3AC menu Tag→DWORD table.

        The source frequency table is recovered exactly. The current data
        window and original Delphi runtime Canvas are *not* identical.
        """
        hz=validate_source_h_scale(hz)
        if self._full_spectrum is None:return
        full=HORIZONTAL_HZ[0]
        vb=self.spec_plot.getViewBox()
        selected=self._spec_original_hscale_selected
        # Never mix a normalized Qt zoom position with the source VCL
        # menu's integer Hz position when switching domains.
        if selected in HORIZONTAL_HZ:
            native=int(self.spec_hscroll.value())
            old=NativeScrollContract(
                'horizontal',full,selected,
                max(0,min(full-selected,native)),True)
            pos=rescale_scroll(old,selected_page=hz).position
        else:
            pos=0
        self._spec_original_hscale_selected=None
        self.spec_hz.blockSignals(True)
        self.spec_hz.setValue(float(full))
        self.spec_hz.blockSignals(False)
        self._spec_visible_max_hz=float(full)
        vb.setLimits(xMin=0.,xMax=float(full))
        vb.setXRange(float(pos),float(pos+hz),padding=0.)
        self._spec_original_hscale_selected=hz
        self.spec_hscale_button.setText(f'{hz} Гц')
        for action in self._spec_hscale_actions:
            action.setChecked(action.data()==hz)
        self._sync_spec_scroll()
        self.statusBar().showMessage(
            f'Исходный H-пресет {hz} Гц; численная FFT/Canvas '
            'идентичность с Delphi ещё НЕ подтверждена')

    def _spec_scroll_changed(self,axis:int,value:int):
        if self._full_spectrum is None:return
        if axis==1 and self._spec_original_vscale_tag is not None:
            # Original VCL Position is an integer, no normalized Qt 0..1000.
            mode=self.spec_mode.currentIndex()
            tag=self._spec_original_vscale_tag
            choice=source_vertical_selection(
                mode,tag,old_tag=tag,old_position=int(value))
            self._apply_original_vscale_candidate(choice)
            return
        vb=self.spec_plot.getViewBox()
        bounds=vb.viewRange()[axis]
        visible=max(1e-12,bounds[1]-bounds[0])
        limits=((0.,float(getattr(self,'_spec_visible_max_hz',self.spec_hz.value()))) if axis==0
                else (self._spec_data_ymin,self._spec_data_ymax))
        available=max(0.,limits[1]-limits[0]-visible)
        if available<=0:return
        if axis==0:
            # Delphi H: Position is an integer frequency unit; 0084C825.
            # Original menu has ten discrete scales; here PageSize is
            # inferred from the Qt research view, NOT a verified menu preset.
            full=max(1,int(round(limits[1]-limits[0])))
            page=max(1,min(full,int(round(visible))))
            native_pos=max(0,min(full-page,int(value)))
            source=source_spectrum_h_scr(native_pos,page,full)
            self._spec_hscroll_source_candidate={
                **source,'page_size_from_qt_view_candidate':True,
                'original_plot_coordinate_parity_verified':False}
            lower=min(limits[1]-visible,
                      max(limits[0],limits[0]+source['scr_left_single']))
            vb.setXRange(lower,lower+visible,padding=0)
        else:
            # Vertical Qt 0..1000 slider remains an explicit research candidate.
            lower=limits[0]+(value/1000.)*available
            vb.setYRange(lower,lower+visible,padding=0)

    def _sync_spec_scroll(self,*_):
        if self._full_spectrum is None:return
        vb=self.spec_plot.getViewBox()
        for axis,bar in ((0,self.spec_hscroll),(1,self.spec_vscroll)):
            if axis==1 and self._spec_vertical_model is not None:
                state=self._spec_vertical_model
                bar.blockSignals(True)
                bar.setRange(state['qt_minimum'],state['qt_maximum'])
                bar.setPageStep(state['qt_page_step'])
                bar.setSingleStep(state['qt_single_step'])
                bar.setValue(state['delphi_position'])
                bar.setVisible(state['delphi_visible'])
                bar.blockSignals(False)
                continue
            lo,hi=vb.viewRange()[axis]
            span=hi-lo
            full=((0.,float(getattr(self,'_spec_visible_max_hz',self.spec_hz.value()))) if axis==0
                  else (self._spec_data_ymin,self._spec_data_ymax))
            remaining=(full[1]-full[0])-span
            active=bool(remaining>max(1e-8,(full[1]-full[0])*1e-5))
            bar.blockSignals(True)
            if axis==0:
                # Delphi FMax=Full-1, PageSize=selected Hz; Qt effective max
                # is Full-Page instead of normalized 1000.
                native_full=max(1,int(round(full[1]-full[0])))
                native_page=max(1,min(native_full,int(round(span))))
                native_pos=max(0,min(native_full-native_page,
                                     int(round(lo-full[0]))))
                src=source_spectrum_h_scr(native_pos,native_page,native_full)
                bar.setRange(src['qt_minimum'],src['qt_maximum'])
                bar.setPageStep(src['qt_page_step'])
                bar.setSingleStep(src['qt_single_step'])
                bar.setValue(src['delphi_position'])
                self._spec_hscroll_source_candidate={
                    **src,'page_size_from_qt_view_candidate':True,
                    'original_plot_coordinate_parity_verified':False,
                    'source_presets_from_private_idp_verified':True}
                if (self._spec_original_hscale_selected is not None and
                        native_page!=self._spec_original_hscale_selected):
                    self._spec_original_hscale_selected=None
                    self.spec_hscale_button.setText(f'{native_page} Гц')
                    for action in self._spec_hscale_actions:
                        action.setChecked(False)
                bar.setVisible(active and src['delphi_visible'])
            else:
                # Before selecting an original V preset, retain the old
                # research-only normalized Qt vertical slider.
                bar.setVisible(active)
                if active:
                    bar.setValue(max(0,min(1000,round((lo-full[0])/remaining*1000))))
                    bar.setPageStep(max(1,min(1000,round(span/(full[1]-full[0])*1000))))
            bar.blockSignals(False)

    def _spec_envelope_code_changed(self,*_):
        self._sync_original_envelope_menu_tag(self.spec_envelope_code)
        self._sync_wave_primary_labels()
        self._wave_envelope_dirty=True
        if self.tabs.currentIndex()==1:
            self.refresh_wave()
        code=int(self.spec_envelope_code.currentData() or 0)
        if code==0 and self.spec_envelope_button.isChecked():
            # Original Tag=0 is no filter: clear/recalculate an active FIR
            # trace instead of leaving its old peaks under "Без фильтра".
            self.spec_envelope_button.setChecked(False)
        elif self.spec_envelope_button.isChecked():
            self._toggle_spec_envelope(True)

    def _toggle_spec_envelope(self,checked):
        if checked and self.envelope_profile is None:
            self.spec_envelope_button.blockSignals(True)
            self.spec_envelope_button.setChecked(False)
            self.spec_envelope_button.blockSignals(False)
            self.statusBar().showMessage('Для спектра огибающей нужно выбрать собственный оригинальный IDP')
            return
        self.spec_compare_button.setEnabled(not checked)
        if checked and self.session is not None:
            try:
                code=int(self.spec_envelope_code.currentData() or 0)
                if not code:raise ValueError('Выберите код огибающей 1..31')
                samples,fs,_,_=self.session.samples(self._ch())
                valid=[]
                for i in range(self.spec_n.count()):
                    n=int(self.spec_n.itemText(i))
                    try:
                        plan=required_original_history(n,int(fs),code)
                        if plan['input_samples']<=len(samples):
                            valid.append(n)
                    except ValueError:continue
                if not valid:raise ValueError('Для такого кода огибающей недостаточно исходной истории BIN')
                if int(self.spec_n.currentText()) not in valid:
                    # Avoid a premature FFT refresh while changing envelope mode.
                    self.spec_n.blockSignals(True)
                    self.spec_n.setCurrentText(str(max(valid)))
                    self.spec_n.blockSignals(False)
                    self._spec_last_valid_fft_n=None
                    self.statusBar().showMessage('FFT N уменьшен до размера с полной исходной FIR-историей')
            except (ValueError,OSError,KeyError) as e:
                self.spec_envelope_button.blockSignals(True)
                self.spec_envelope_button.setChecked(False)
                self.spec_envelope_button.blockSignals(False)
                self.spec_compare_button.setEnabled(True)
                self.statusBar().showMessage(str(e))
                # A failed FIR transition must not preserve a stale curve.
                self.refresh_spec()
                self._sync_fft_menu_availability()
                return
        self.refresh_spec()
        if self.session is not None:
            self._sync_fft_menu_availability()

    def _change_spectrum_mode(self,*_):
        self.spec_avg.setCurrentIndex(0 if self.spec_mode.currentIndex()==0 else 1)
        self._spec_original_vscale_tag=None
        self._spec_original_vscale_mode=None
        self._spec_vertical_model=None
        self.spec_vscale_button.setText('Шкала Y')
        self._rebuild_original_vscale_menu()
        self.refresh_spec()
        if self._full_spectrum is not None:
            # Original mSpecType1Click source Tag reset: 0 for dB, 3 for other.
            self._select_original_vscale(
                source_default_vertical_tag(self.spec_mode.currentIndex()))

    @staticmethod
    def _zoom_bar(layout,inc,dec):
        a=QPushButton('+')
        a.setToolTip('Приблизить по горизонтали')
        a.clicked.connect(inc)
        layout.addWidget(a)
        b=QPushButton('−')
        b.setToolTip('Отдалить по горизонтали')
        b.clicked.connect(dec)
        layout.addWidget(b)

    @staticmethod
    def _zoom(plot,factor):
        plot.getViewBox().scaleBy((factor,1))

    def _set_active(self,ready):
        # Original start/tasks must remain usable before an archive exists.
        self.tabs.setEnabled(True)
        self.tabs.setTabEnabled(0,True)
        self.tabs.setTabEnabled(1,ready)
        self.tabs.setTabEnabled(2,ready)
        self.adc.setEnabled(ready)
        self.tick.setEnabled(ready and not isinstance(self.session,DirectBinSession))
        self.task_signal_button.setEnabled(ready)
        self.task_spectrum_button.setEnabled(ready)
        self.task_metrics_button.setEnabled(ready)
        if getattr(self,'original_shell',None) is not None:
            self.original_shell.sync_availability()

    def _begin_live_capture(self):
        """Preview is a separate, explicitly unverified mode, never a ZIP session."""
        if self._live_active:
            return
        self._live_prior_session=self.session
        self._live_active=True
        self._live_preview=None
        self.session=None
        for i in range(8):
            self.adc.model().item(i).setEnabled(True)
        self._set_active(True)
        self.tick.setEnabled(False)
        self.task_metrics_button.setEnabled(False)
        self._live_control_states=[(widget,widget.isEnabled()) for widget in (
            self.wave_start,self.wave_seconds,self.wave_order,self.wave_envelope_code,
            self.wave_filter_button,self.wave_hscale_button,self.spec_n,
            self.spec_f_range,self.spec_input_domain,self.spec_last)]
        for widget,_ in self._live_control_states:
            widget.setEnabled(False)  # archive selectors are NOT live FFT windows
        # Never display previous archive's DSP/VALUES while recording new RAW.
        self.task_subpages.setCurrentIndex(0)
        for row in range(self.metrics.rowCount()):
            for col in range(self.metrics.columnCount()):
                self._cell(self.metrics,row,col,'— (ожидание проверенного AUX)')
        for row in range(self.oct_table.rowCount()):
            for col in range(self.oct_table.columnCount()):
                self._cell(self.oct_table,row,col,'—')
        self.oct_plot.clear()
        for label,widget in self.status_fields.values():
            widget.setText(label+': нет проверенного AUX нового сеанса')
        self.sensor_bit_details.setText('LIVE: исходные биты статуса видны в Native; финальная аттестация после ZIP')
        self._reset_dsp_tach_panel('LIVE PREVIEW: архивный DSP/TACH данного сеанса ещё не принят')
        self.title.setText('LIVE · Native R6.1 · предварительные данные')
        self.task_session_summary.setText(
            'Native R6.1 ведёт запись с разрешения оператора. '
            'Временной сигнал/спектр — только PREVIEW по калиброванным '
            'отсчётам. Исходный RAW и проверенный архив сохраняются отдельно.')
        self.note.setText(
            'LIVE PREVIEW: нет аппаратного паритета с MVKView; '
            'FRange уже применён Native к BIN, повторно НЕ умножать')
        self.wave_plot.clear()
        self.spec_plot.clear()
        self.wave_line=None
        self._full_spectrum=None
        self._spectrum_summary=None
        self.wave_hint.setText('LIVE: ожидаются реальные откалиброванные отсчёты R6.1')
        self.spec_hint.setText('LIVE: FFT только после достаточного окна реальных отсчётов')
        self.wave_mean_primary.setText('LIVE · СКЗ: ожидаются данные')
        self.spec_mean.setText('LIVE · спектр: ожидаются данные')
        self._sync_spectrum_summary_primary()
        self.spec_copy_button.setEnabled(False)
        self.spec_save_button.setEnabled(False)
        self.spec_original_copy_compare.setEnabled(False)
        self.spec_canvas_geometry_button.setEnabled(False)
        self.refresh_calc()
        self.tabs.setCurrentIndex(1)
        self.statusBar().showMessage('LIVE PREVIEW — единственный TCP-клиент Go R6.1, данные ещё не приняты')

    def _receive_live_preview(self, preview):
        if not self._live_active:
            return
        self._live_preview=preview
        self._render_live_wave()
        self._render_live_spectrum()

    def _invalidate_live_preview(self, reason):
        if not self._live_active:
            return
        if self._live_preview is None:
            return
        self._live_preview=None
        self.wave_plot.clear()
        self.spec_plot.clear()
        self.wave_line=None
        self._full_spectrum=None
        self._spectrum_summary=None
        self.wave_hint.setText('LIVE preview отклонён: '+str(reason))
        self.spec_hint.setText('LIVE FFT скрыт: '+str(reason))
        self.wave_mean_primary.setText('LIVE · недостоверное окно')
        self.spec_mean.setText('LIVE · недостоверное окно')
        self._sync_spectrum_summary_primary()
        self.statusBar().showMessage('Предварительные графики скрыты, RAW Native не изменён')

    def _render_live_wave(self):
        if not self._live_active or self._live_preview is None:
            return
        try:
            ch=self._ch()
            d=provisional_waveform(
                self._live_preview,ch,ac=self.wave_mode.currentIndex()==0)
            self.wave_plot.clear()
            self.wave_line=None  # Original cursor requires audited archived samples
            self._wave_hover_window=None
            self.wave_plot.setLabel('bottom','Индекс отсчёта/Fs, с · НЕ часы ПК')
            self.wave_plot.setLabel('left','Native R6.1 · калибр. preview, м/с²')
            self.wave_plot.plot(d['time_s'],d['amplitude'],
                                pen=pg.mkPen('#176c92'))
            self.wave_plot.enableAutoRange()
            self.wave_mean_primary.setText(
                f'LIVE АЦП{ch} · локальное СКЗ: {d["rms_m_s2"]:.5g} м/с²\n'
                'Не сверено с оригинальной MVKView')
            self.wave_hint.setText(
                f'LIVE PREVIEW · {d["window_samples"]} реальных Float32 отсчётов · '
                f'AC={"без DC" if self.wave_mode.currentIndex()==0 else "с DC"} · '
                'GetSignal IDR-кандидат; исходный RAW не изменён')
        except (ValueError,OSError,KeyError) as exc:
            self.wave_plot.clear()
            self.wave_hint.setText('Live signal недоступен: '+str(exc))

    def _render_live_spectrum(self):
        if not self._live_active or self._live_preview is None:
            return
        try:
            ch=self._ch()
            d=provisional_spectrum(
                self._live_preview,ch,mode=self.spec_mode.currentIndex())
            xs=np.asarray(d['frequency_hz'],dtype=float)
            ys=np.asarray(d['amplitude'],dtype=float)
            self.spec_plot.clear()
            # Preserve four existing mode selectors, but keep this DATA
            # separate from all original TQGrapher pointer/cursor acceptance.
            self.spec_plot.setLabel('bottom','Частота, Гц · Live FFT кандидат')
            self.spec_plot.setLabel('left',d['unit'])
            self.spec_plot.plot(xs,ys,pen=pg.mkPen('#000000'))
            self.spec_plot.getViewBox().setLimits(xMin=0,xMax=d['df_hz']*d['n_fft']/2)
            self.spec_plot.enableAutoRange()
            self._full_spectrum=None
            self._spectrum_summary=None
            self.spec_copy_button.setEnabled(False)
            self.spec_save_button.setEnabled(False)
            self.spec_original_copy_compare.setEnabled(False)
            self.spec_canvas_geometry_button.setEnabled(False)
            self.spec_mean.setText(
                f'LIVE ADC{ch} · FFT N={d["n_fft"]}; шаг {d["df_hz"]:.6g} Гц\n'
                'Спектр рассчитан локально · НЕ оригинальный DSP/Delphi parity')
            self.spec_mean_primary.setText('LIVE PREVIEW · численный паритет не подтверждён')
            self.spec_hint.setText(
                f'{d["source"]} · FRange повторно НЕ применялся · '
                'результат не предназначен для оригинального Copy/Save')
            self.spec_cursor_primary.setText('Live: курсор оригинала недоступен')
        except (ValueError,OSError,KeyError) as exc:
            self.spec_plot.clear()
            self.spec_hint.setText('Live FFT недоступен: '+str(exc))

    def _end_live_capture(self, exported):
        if not self._live_active:
            return
        self._live_active=False
        self._live_preview=None
        self._pagestatus_snapshot=None
        self._refresh_source_pagestatus()
        old=self._live_prior_session
        self._live_prior_session=None
        for widget,was_enabled in self._live_control_states:
            widget.setEnabled(was_enabled)
        self._live_control_states=[]
        self.session=None
        self.wave_plot.clear()
        self.spec_plot.clear()
        self.wave_line=None
        self._full_spectrum=None
        self._spectrum_summary=None
        self._set_active(False)
        self._sync_spectrum_summary_primary()
        if exported:
            # The dialog calls archiveReady AFTER this state transition.
            # Until then NO provisional plotted bytes count as accepted.
            self.title.setText('Native R6.1 · проверенный архив готовится к открытию')
            self.statusBar().showMessage('LIVE завершён; только сейчас можно открыть SHA-verified ZIP')
        elif old is not None:
            # Restore the previously verified session, not a copied preview.
            self.open_archive(old.path)
        else:
            self.title.setText('Сеанс не выбран')
            self.task_session_summary.setText('LIVE завершён без принятого архива. RAW остаётся у оператора.')
            self.note.setText('LIVE завершён; исходный RAW/диагностика не изменены')
            self.wave_hint.setText('Откройте локальное проверенное измерение')
            self.spec_hint.setText('Откройте локальное проверенное измерение')
            self.statusBar().showMessage('LIVE не принят; архив не подменён предварительными данными')

    def open_native_capture(self):
        """Use the already hardware-tested recorder; never send MVK commands."""
        from .native_capture_dialog import NativeCaptureDialog
        if self._native_dialog is not None and self._native_dialog.isVisible():
            self._native_dialog.raise_()
            self._native_dialog.activateWindow()
            return
        dlg=NativeCaptureDialog(self)
        dlg.archiveReady.connect(self.open_archive)
        dlg.captureStarted.connect(self._begin_live_capture)
        dlg.captureEnded.connect(self._end_live_capture)
        dlg.previewReady.connect(self._receive_live_preview)
        dlg.previewInvalid.connect(self._invalidate_live_preview)
        self._native_dialog=dlg
        dlg.show()

    def compare_original_native_local(self):
        """Stage111Z27 local-only forensic comparison, no network or mutation.

        The original BIN has no original TCP session identity; even equal
        bytes are not independently same-run attestation.
        """
        if self._live_active:
            self.statusBar().showMessage(
                'Сверка отклонена: сначала завершите LIVE и дождитесь RAW/SHA экспорта.')
            return
        original,_=QFileDialog.getOpenFileName(
            self,'Оригинальный MVKView ADC BIN (с парным .bin.tsxml)','',
            'Оригинальный BIN (*.bin)')
        if not original:
            return
        if (self.session is not None and
                not isinstance(self.session,DirectBinSession) and
                isinstance(self.session,OfflineSession)):
            native_path=self.session.path
        else:
            native_path,_=QFileDialog.getOpenFileName(
                self,'Проверенный завершённый ZIP Native R6.1 (НЕ live preview)','',
                'Native R6.1 завершённый ZIP (*.zip)')
            if not native_path:
                return
        try:
            comparison=compare_original_native(original,native_path)
            complete=comparison['all_eight_adc_present_in_original']
            equal=comparison['bin_bytes_equal_on_matching_file_starts']
            parts=[]
            for item in comparison['channels']:
                count=item['bitwise_mismatch_count_on_common_prefix']
                match='точное BIN совпадение' if item['observed_bin_bitwise_equal'] else (
                    f'{count} разных Float32 битовых слов; длины '
                    + ('равны' if item['lengths_equal'] else 'разные'))
                parts.append(f'АЦП{item["adc"]}: {match}')
            summary=(
                'Stage111Z.27 · локальная проверка BIN/TSXML\n'
                f'Каналов: {len(parts)}/8; вся группа: {"да" if complete else "НЕТ"}\n'
                f'BIN по началу файлов: {"СОВПАДАЮТ" if equal else "РАСХОДЯТСЯ"}\n'
                f'TSXML побайтово: {"да" if comparison["tsxml_bytes_equal"] else "нет"}\n\n'
                + '\n'.join(parts)
                + '\n\nКРИТИЧЕСКОЕ ОГРАНИЧЕНИЕ: оригинальный BIN/TSXML '
                  'не содержит SHA исходного TCP RAW и исходный индекс сэмплов. '
                  'Принадлежность одной записи, калибровка оригинала '
                  'и оригинальный численный паритет НЕ доказаны. '
                  'FRange не применялся повторно. Исходные файлы не изменены.')
            QMessageBox.information(self,'Оригинальный BIN ↔ Native · без аттестации сеанса',summary)
            self.statusBar().showMessage(
                'Stage111Z27: локальная численная сверка завершена, same-run provenance OPEN')
        except (OSError,ValueError,TypeError,KeyError,RuntimeError) as exc:
            QMessageBox.warning(self,'Сравнение оригинала отклонено',str(exc))

    def choose_archive(self):
        if self._live_active:
            self.statusBar().showMessage('Пока Native записывает RAW, архив открывать нельзя. Сначала завершите сеанс.')
            return
        path,_=QFileDialog.getOpenFileName(
            self,'Локальные измерения MVK (без подключения к прибору)','',
            'MVK измерения (*.zip *.bin *.tsxml);;'
            'Экспорт Native R6.1 (*.zip);;'
            'BIN с парным TSXML (*.bin *.tsxml)')
        if path:self.open_archive(path)

    def open_archive(self,path):
        if self._live_active:
            self.statusBar().showMessage('Архив не заменяется во время активной записи Native.')
            return
        try:
            source=Path(path)
            direct=source.suffix.lower() in ('.bin','.tsxml')
            if direct:
                s=DirectBinSession.open(source)
                channels=s.available_channels
            else:
                s=OfflineSession.open(source)
                s.calculations()
                channels=tuple(range(1,9))
            samples,fs,_,_=s.samples(channels[0])
            valid_sizes=[int(self.spec_n.itemText(i)) for i in range(self.spec_n.count())
                         if int(self.spec_n.itemText(i))<=len(samples)]
            if not valid_sizes:
                raise ValueError('Для графического FFT требуется не менее 1024 отсчётов')
        except (OSError,ValueError,KeyError,RuntimeError) as exc:
            QMessageBox.critical(self,'Архив отклонён',str(exc))
            return
        # Do not let a previous visual-only x32dbg snapshot leak into a newly
        # selected archive's data, cursor, Copy or Save.
        self._leave_original_spectrum_reference()
        self.session=s
        # A direct BIN may supply only ADC4: do not silently read ADC1
        # or mix unrelated files to fill absent channels.
        self.adc.blockSignals(True)
        try:
            for number in range(1,9):
                self.adc.model().item(number-1).setEnabled(number in channels)
            self.adc.setCurrentIndex(channels[0]-1)
        finally:
            self.adc.blockSignals(False)
        self._spec_last_valid_fft_n=None
        self._spec_original_vscale_tag=None
        self._spec_original_vscale_mode=None
        self._spec_vertical_model=None
        self._spec_vscroll_source_candidate=None
        self.spec_vscale_button.setText('Шкала Y')
        for action in self._spec_vscale_actions:
            action.setChecked(False)
        self.spec_n.blockSignals(True)
        if int(self.spec_n.currentText())>len(samples):
            self.spec_n.setCurrentText(str(max(valid_sizes)))
        self.spec_n.blockSignals(False)
        self._sync_fft_menu_availability(samples_count=len(samples),
                                         sample_rate=fs)
        self.title.setText(
            (f'{s.serial} · {len(channels)} АЦП · BIN/TSXML (DSP недоступен)'
             if direct else
             s.serial+f' · {s.updates} расчётных обновлений')
        )
        self.tick.blockSignals(True)
        self.tick.setRange(1,s.updates)
        self.tick.setValue(s.updates)
        self.tick.blockSignals(False)
        self._set_active(True)
        self.task_session_summary.setText(
            f'Открыт файл: {Path(path).name}\n'
            f'Прибор: {s.serial}; доступных АЦП: {len(channels)}.\n'
            + ('Источник BIN/TSXML Single. Калибровка/приборные DSP '
               'не подтверждены.' if direct else
               'Экспорт Native R6.1. Приборные VALUES/AUX отдельно проверены.'))
        self.original_shell.sync_file_session(s,channels)
        self.refresh_all()
        self.statusBar().showMessage(
            ('Открыт локальный BIN/TSXML Single; калибровка и приборный DSP НЕ подтверждены · '
             if direct else 'Открыт проверенный ZIP Native R6.1 · ')
            + Path(path).name
        )

    def _ch(self):
        return self.adc.currentIndex()+1

    def _close_session(self):
        """Close only the offline viewer session; never touch a live recorder."""
        if self._live_active:
            self.statusBar().showMessage(
                'Нельзя закрывать просмотр во время активной записи Native R6.1')
            return
        self._leave_original_spectrum_reference()
        self._clear_archive_source_projection()
        self.session=None
        self._full_spectrum=None
        self._spectrum_summary=None
        self._pagestatus_snapshot=None
        self.wave_plot.clear()
        self.spec_plot.clear()
        self.adc.blockSignals(True)
        try:
            for i in range(self.adc.count()):
                self.adc.model().item(i).setEnabled(True)
            self.adc.setCurrentIndex(0)
        finally:
            self.adc.blockSignals(False)
        self.tick.blockSignals(True)
        try:
            self.tick.setRange(1,1)
            self.tick.setValue(1)
        finally:
            self.tick.blockSignals(False)
        self._set_active(False)
        self.title.setText('Сеанс не выбран')
        self.task_session_summary.setText(
            'Измерение не открыто. Выберите локальный ZIP, BIN или TSXML.')
        self.original_shell.sync_file_session(None,())
        self._refresh_source_pagestatus()
        self._reset_dsp_tach_panel('Сеанс закрыт')
        self.statusBar().showMessage('Локальное измерение закрыто')

    def _update_original_gain_inspector(self):
        if not isinstance(self.session,DirectBinSession):
            self.spec_source_gain_label.setText(
                'Источник R6.1 ZIP: отдельный FRange текущего источника '
                'не аттестован автоматически.')
            return
        info=next(
            (c.source_metadata for c in self.session.channel_files
             if c.adc==self._ch()),None)
        if info is None:
            self.spec_source_gain_label.setText(
                'TSXML: канал не представлен в текущей группе')
            return
        if info.original_f_range_single_candidate is not None:
            gain=f'{info.original_f_range_single_candidate:.9g}'
            label=(
                'TSXML InternalChannelGain='+gain+
                ' · IDR source candidate FRange='+gain+
                ' · исходное значение НЕ применено повторно к BIN.')
        else:
            label=(
                'TSXML InternalChannelGain отсутствует или не положителен; '
                'оригинал использует fallback DefaultConfig.txt, '
                'эффективный FRange НЕ известен.')
        label+=(
            '\n'+'Полный формат оригинального TSXML: '+
            ('да' if info.source_meta_complete else 'не все поля присутствуют')
            +' · физических единиц/паритета по этому BIN НЕТ.')
        self.spec_source_gain_label.setText(label)

    def refresh_all(self,*_):
        if self._live_active:
            self._render_live_wave()
            self._render_live_spectrum()
            return
        if self.session is None:return
        self._update_original_gain_inspector()
        self.refresh_calc()
        self.refresh_wave()
        self.refresh_spec()

    def _reset_dsp_tach_panel(self,reason):
        self.dsp_tach_status.setText('DSP/TACH: '+reason)
        self.dsp_tach_clock.setText('Время: недоступно')
        for row in range(2):
            for col,value in enumerate((f'TACH {row+1}','—','—','—','—','—')):
                self._cell(self.tach_words,row,col,value)

    def _update_dsp_tach_panel(self,record):
        if not record or not record.get('available'):
            self._reset_dsp_tach_panel(
                'нет проверенных исходных регистров для этого архива/тика')
            return
        raw=record['global_dsp_status_hex']
        meaning=('все биты нулевые (не доказательство исправности)'
                 if record['global_dsp_all_bits_zero']
                 else 'ненулевой исходный статус, значение битов требует оригинальной карты')
        self.dsp_tach_status.setText(
            f'Системный DSP {raw}: {meaning} · '+record['source'])
        self.dsp_tach_clock.setText(
            f'VALUES tick frame={record["tick_frame"]}; AUX frame={record["aux_frame"]}; '
            f'ПК UTC={record["tick_received_utc"]} (НЕ DSP-время)')
        for i,entry in enumerate(record['tachometers']):
            floats=entry['raw_float32_words_0_2']
            integers=entry['raw_uint32_words_4_6_8']
            cols=[f'TACH {i+1} ({entry["register_base_word"]})',
                  self._value(floats[0]),self._value(floats[1]),
                  *(f'0x{x:08X}' for x in integers)]
            for col,value in enumerate(cols):
                self._cell(self.tach_words,i,col,value)

    def _refresh_source_pagestatus(self,*_):
        model=source_pagestatus_table(
            self.original_status_mode.currentIndex(),
            self._pagestatus_snapshot)
        table=self.original_status_table
        table.clearContents()
        table.setColumnCount(len(model.headers))
        table.setRowCount(len(model.rows))
        table.setHorizontalHeaderLabels(list(model.headers))
        for row,record in enumerate(model.rows):
            for col,value in enumerate(record):
                self._cell(table,row,col,value)
        self.original_status_note.setText(
            'Исследовательский показ оригинального PageStatus. '+model.note)
        self.original_status_plot.clear()
        if model.bands_for_plot is not None:
            self.original_status_plot.addItem(pg.BarGraphItem(
                x=np.arange(43),
                height=np.asarray(model.bands_for_plot,dtype=float),
                width=0.75,brush='#147b91'))
            self.original_status_plot.setVisible(True)
        else:
            self.original_status_plot.setVisible(False)
        if getattr(self,'original_shell',None) is not None:
            self.original_shell.refresh_status()

    def refresh_calc(self,*_):
        if self._live_active:
            self._pagestatus_snapshot=None
            self._refresh_source_pagestatus()
            self.calc_source.setText('LIVE PREVIEW · расчётные DSP показатели пока не аттестованы')
            self.calc_status.setText('Во время записи: состояние каналов в окне Native R6.1')
            self.calc_status.setStyleSheet('color:#9e6500')
            return
        if not self.session:return
        if isinstance(self.session,DirectBinSession):
            self._pagestatus_snapshot=None
            self._refresh_source_pagestatus()
            # BIN/TSXML contains no authenticated AUX/VALUES DSP. Do not
            # show stale values from the previously opened Native ZIP.
            self.calc_source.setText('BIN/TSXML: приборные DSP/VALUES/AUX отсутствуют')
            self.calc_status.setText('Только сигнал и исследовательский спектр')
            self.calc_status.setStyleSheet('color:#9e6500')
            for row in range(self.metrics.rowCount()):
                for col in range(self.metrics.columnCount()):
                    self._cell(self.metrics,row,col,'—')
            for row in range(self.oct_table.rowCount()):
                for col in range(self.oct_table.columnCount()):
                    self._cell(self.oct_table,row,col,'—')
            self.oct_plot.clear()
            for label,widget in self.status_fields.values():
                widget.setText(label+': нет оригинального AUX/VALUES')
            self.sensor_bit_details.setText('BIN/TSXML: нет подтверждённых исходных битов AUX')
            self._reset_dsp_tach_panel('BIN/TSXML: нет проверенных DSP/TACH регистрационных тиков')
            self.note.setText(
                'LOCAL BIN/TSXML Single: физическая калибровка не подтверждена; '
                'приборные показатели DSP/третьоктавы НЕ вычисляются')
            return
        try:
            d=self.session.calculations(self.tick.value()-1)
            self._pagestatus_snapshot=d
            self._refresh_source_pagestatus()
            channel=d['channels'][self._ch()-1]
            self.calc_source.setText('Приборный DSP: '+d['precision']+' · время '+d['timestamp'])
            self.calc_status.setText('Состояние датчика: '+channel['sensor_status']+' · '+channel['health'])
            self.calc_status.setStyleSheet('color:#ad2424' if channel['health']!='OK' else 'color:#227543')
            for i,m in enumerate(channel['parameters_24']):
                self._cell(self.metrics,i,0,m['name']+' ['+m['unit']+']')
                self._cell(self.metrics,i,1,self._value(m['value']))
                for col,key in ((2,'parameters_peak_24'),(3,'parameters_peak_peak_24')):
                    val=channel[key]
                    self._cell(self.metrics,i,col,self._value(val[i]['value']) if val else '— (нет полного AUX)')
            bands=channel['third_octave']
            for i,b in enumerate(bands):
                self._cell(self.oct_table,i,0,b['name'])
                self._cell(self.oct_table,i,1,self._value(b['rms_m_s2']))
            self.oct_plot.clear()
            self.oct_plot.addItem(pg.BarGraphItem(x=np.arange(43),
                height=np.asarray([a['rms_m_s2'] or 0 for a in bands]),width=.75,brush='#147b91'))
            for key,(label,widget) in self.status_fields.items():
                widget.setText(label+': '+self._value(channel[key]))
            self._update_dsp_tach_panel(d.get('dsp_tach',{}))
            bits=channel.get('sensor_status_details',{})
            if bits.get('raw_u32') is not None:
                flags=bits.get('not_ready') or {}
                active=[str(key) for key,value in flags.items() if value]
                self.sensor_bit_details.setText(
                    f'Приборный статус {bits["raw_hex"]} · mask 0xC00='
                    f'{bits["warning_bits_0xC00"]} · не готовы '
                    + (', '.join(active) if active else 'нет флагов fs16/fs64/fs512')
                    + ' · причина других битов не установлена')
            else:
                self.sensor_bit_details.setText(
                    'Исходные AUX status_raw/not_ready не предоставлены: '
                    'показан только текст из VALUES')
            self.note.setText('ALERT: состояние датчика '+channel['sensor_status'] if channel['health']!='OK'
                else 'MVK_DSP: штатные значения; локальный FFT обозначен отдельно')
        except (OSError,KeyError,ValueError) as e:self._error(e)

    def choose_private_envelope_idp(self):
        """Only explicit user-selected local file; no retained bytes/network."""
        path,_=QFileDialog.getOpenFileName(self,'Оригинальный локальный IDR-проект','','Original IDP (*.idp)')
        if not path:return
        try:
            profile=EnvelopeProfile.from_original_local_idp(path)
            self.set_envelope_profile(profile)
            self.statusBar().showMessage(
                'Локальные коэффициенты проверены SHA-256; огибающая исследовательская, не принята как Delphi parity')
        except (OSError,ValueError) as exc:
            QMessageBox.critical(self,'Оригинальные коэффициенты не приняты',str(exc))

    def set_envelope_profile(self,profile:EnvelopeProfile):
        if not isinstance(profile,EnvelopeProfile):
            raise ValueError('Expected verified local EnvelopeProfile')
        self.envelope_profile=profile
        self.wave_envelope_code.setEnabled(True)
        self.spec_envelope_button.setEnabled(True)
        self.spec_envelope_button.setText('Огибающая (исслед.)')
        self.spec_envelope_code.setEnabled(True)
        if self.spec_envelope_code.currentIndex()==0:
            # Retain existing research default code 20 but do not silently
            # activate FIR on the ADC merely by loading an IDP profile.
            was_blocked=self.spec_envelope_code.blockSignals(True)
            try:
                self.spec_envelope_code.setCurrentIndex(20)
            finally:
                self.spec_envelope_code.blockSignals(was_blocked)
        self.wave_envelope_load.setText('Локальные коэффициенты готовы (только этот запуск)')
        self.wave_hint.setText(
            'Огибающая доступна только по исходному IDR профилю; '
            'курсоры, исходное время и численный паритет оригинальной MVKView ещё не приняты')
        self._sync_wave_primary_labels()

    def _signal_order(self):
        return 'chronological' if self.wave_order.currentIndex()==0 else 'getsignal_buffer'

    def refresh_wave(self,*_):
        if self._live_active:
            self._render_live_wave()
            return
        if not self.session:return
        try:
            mode='ac' if self.wave_mode.currentIndex()==0 else 'acdc'
            order=self._signal_order()
            code=int(self.wave_envelope_code.currentData() or 0)
            if code:
                if self.envelope_profile is None:
                    raise ValueError('Требуются оригинальные локальные коэффициенты IDP')
                d=self.session.envelope(
                    self._ch(),code,self.wave_start.value(),
                    self.wave_seconds.value(),self.envelope_profile,
                    display_order=order)
                self.wave_plot.setLabel('bottom',
                    'Позиция буфера огибающей, с — НЕ время оригинальной MVKView')
                descr=(f"Огибающая IDR (эксперимент) код {code} · "
                    f"стадии {d['stages_used']} · отсчёты {d['output_samples']}"
                    f" · выходная частота {d['output_sample_rate_hz']} Гц"
                    f" · локальное СКЗ: {d['rms_m_s2']:.7g} "
                    f"{'усл. ед.' if isinstance(self.session,DirectBinSession) else 'расч. ед.'}"
                    " · оригинальный формат/время/курсор НЕ приняты")
            else:
                d=self.session.waveform(self._ch(),self.wave_start.value(),
                                        self.wave_seconds.value(),mode,
                                        display_order=order)
                self.wave_plot.setLabel('bottom','Время BIN, с' if order=='chronological'
                    else 'Позиция буфера GetSignal, с (НЕ время BIN)')
                units=('условн. ед. BIN' if isinstance(self.session,DirectBinSession)
                       else 'м/с²')
                descr=(f"GetSignal/IDR · {mode} · {order} · {d['window_samples']} отсчётов"
                    f" · локальное СКЗ: {d['rms_m_s2']:.7g} {units}"
                    f" · удалённое DC: {d['removed_mean_m_s2']:.7g} {units}"
                    " · паритет TQGrapher НЕ доказан")
            self.wave_plot.clear()
            self.wave_plot.setLabel(
                'left', 'Отсчёты BIN (калибровка не проверена)'
                if isinstance(self.session,DirectBinSession)
                else 'Ускорение, м/с²')
            self.wave_plot.plot(d['time_s'],d['amplitude'],pen=pg.mkPen('#176c92'))
            self.wave_line=pg.InfiniteLine(angle=90,pen=pg.mkPen('#a56017'))
            self.wave_line.setVisible(False)  # Source cursor drawn only after mouse X changes
            self.wave_plot.addItem(self.wave_line)
            self._wave_hover_window=None
            self._wave_mouse_pixel=None
            self.wave_plot.enableAutoRange()
            self.wave_hint.setText(descr)
            source_unit=('усл. ед.' if isinstance(self.session,DirectBinSession)
                         else 'расч. ед.')
            self.wave_mean_primary.setText(
                f'СКЗ сигнала: {d["rms_m_s2"]:.5g} {source_unit}\n'
                + ('Калибровка НЕ подтверждена'
                   if isinstance(self.session,DirectBinSession)
                   else 'Локальный расчёт · оригинал не аттестован'))
            self.wave_cursor_primary.setText('Курсор: —')
            self._sync_wave_primary_labels()
            self._wave_envelope_dirty=False
        except (OSError,KeyError,ValueError) as e:
            # Original invalidates both series when EnvelopeCode changes.
            self.wave_plot.clear()
            self.wave_line=None
            self._wave_hover_window=None
            self.wave_hint.setText('Нет действительного сигнала: '+str(e))
            self.wave_mean_primary.setText('Сигнал не рассчитан')
            self._error(e)



    def _clear_source_tqgr_series_overlay(self):
        """Restore unchanged original PlotDataItem without touching its data."""
        if self._spec_source_series_item is not None:
            self.spec_plot.removeItem(self._spec_source_series_item)
        self._spec_source_series_item=None
        if self._spec_source_series_raw_item is not None:
            self._spec_source_series_raw_item.setVisible(True)
        self._spec_source_series_model=None
        self._spec_source_series_signature=None

    def _restore_source_tqgr_series(self):
        """Fail closed when reference is left, replaced or archived."""
        self._clear_source_tqgr_series_overlay()
        self._spec_source_series_raw_item=None
        blocked=self.spec_source_series_checkbox.blockSignals(True)
        self.spec_source_series_checkbox.setChecked(False)
        self.spec_source_series_checkbox.blockSignals(blocked)
        self.spec_source_series_checkbox.setEnabled(False)
        self.spec_source_series_info.setText(
            'Кривая: обычная Qt. TQGRSeries доступна только '
            'для проверенного оригинального Power/Y.')

    def _source_software_composite_selected(self):
        """One original-order bitmap, opt-in on verified local Power/Y ONLY."""
        return (self._spectrum_reference is not None
                and self.spec_source_grid_checkbox.isChecked()
                and self.spec_source_raster_checkbox.isChecked()
                and self.spec_source_series_checkbox.isChecked())

    def _rebuild_source_software_layers(self):
        """Recompose layer order on mode changes; never alter original Y."""
        self._spec_source_grid_model=None
        if self.spec_source_grid_checkbox.isChecked():
            self._safe_source_grid_update()
        if self.spec_source_series_checkbox.isChecked():
            # Qt stroke item remains allocated for reversible comparison,
            # but MUST NOT be shown on top of the combined bitmap.
            self._safe_source_tqgr_series_update()

    def _toggle_source_tqgr_series_candidate(self,enabled):
        if not enabled:
            self._clear_source_tqgr_series_overlay()
            self.spec_source_series_info.setText(
                'Кривая: обычная Qt. Исходные данные не изменены.')
            # When combined preview was active, remove black series
            # strokes from software bitmap and leave gray grid only.
            if (self._spectrum_reference is not None
                    and self.spec_source_grid_checkbox.isChecked()):
                self._spec_source_grid_model=None
                self._safe_source_grid_update()
            return
        if self._spectrum_reference is None:
            self._restore_source_tqgr_series()
            return
        self._safe_source_tqgr_series_update()
        if self._source_software_composite_selected():
            self._spec_source_grid_model=None
            self._safe_source_grid_update()

    def _safe_source_tqgr_series_update(self):
        try:
            self._sync_source_tqgr_series_candidate()
        except (ValueError,TypeError,KeyError,OverflowError,MemoryError) as exc:
            self._clear_source_tqgr_series_overlay()
            blocked=self.spec_source_series_checkbox.blockSignals(True)
            self.spec_source_series_checkbox.setChecked(False)
            self.spec_source_series_checkbox.blockSignals(blocked)
            self.spec_source_series_info.setText(
                'TQGRSeries не принят: '+str(exc))
            self.statusBar().showMessage(
                'Исследовательская кривая выключена: '+str(exc))

    def _sync_source_tqgr_series_candidate(self,*_):
        """Compare source per-column extrema on ORIGINAL verified Power/Y.

        The derived Float32 input is read-only. PlotCurveItem is a Qt
        *visual* renderer of Delphi-derived segments, not the original
        TCo2Draw 32bpp software raster or physical TPaintBox pixels.
        """
        if (self._spec_source_series_busy
                or self._spectrum_reference is None
                or self._full_spectrum is None
                or not self.spec_source_series_checkbox.isChecked()):
            return
        self._spec_source_series_busy=True
        try:
            vb=self.spec_plot.getViewBox()
            xr,yr=vb.viewRange()
            w=max(4,int(round(vb.width())))
            h=max(4,int(round(vb.height())))
            size=int(self._spec_display_contract['grapher_series_bins'])
            signature=(float(xr[0]),float(xr[1]),float(yr[0]),
                       float(yr[1]),w,h,size)
            if signature==self._spec_source_series_signature:
                if self._spec_source_series_item is not None:
                    self._spec_source_series_item.setVisible(
                        not self._source_software_composite_selected())
                if self._spec_source_series_raw_item is not None:
                    self._spec_source_series_raw_item.setVisible(False)
                return
            raw=self._spec_source_series_raw_item
            if raw is None:
                raise ValueError('No original PlotDataItem for reference')
            y=np.asarray(self._full_spectrum['amplitude'],dtype='<f4')
            if size<=0 or size>y.size:
                raise ValueError('Reference TQGRSeries DataSize out of range')
            result=source_tqgr_series_columns(
                y[:size],
                scr_left=float(xr[0]),scr_width=float(xr[1]-xr[0]),
                scr_bottom=float(yr[0]),scr_height=float(yr[1]-yr[0]),
                x_start=0.,x_scale=float(self._full_spectrum['df_hz']),
                y_scale=1.,
                pixel_left=0,pixel_right=w-1,
                pixel_top=0,pixel_bottom=h-1)
            segments=result['segments']
            if not len(segments):
                raise ValueError('TQGRSeries has no visible pixel columns')
            xx=segments[:,[0,2]].reshape(-1)
            yy=segments[:,[1,3]].reshape(-1)
            data_x=float(xr[0])+xx/(w-1)*float(xr[1]-xr[0])
            data_y=float(yr[1])-yy/(h-1)*float(yr[1]-yr[0])
            curve=pg.PlotCurveItem(
                x=data_x,y=data_y,connect='pairs',
                pen=pg.mkPen('#000000',width=1),antialias=False)
            curve.setZValue(20)
            self.spec_plot.addItem(curve,ignoreBounds=True)
            old=self._spec_source_series_item
            self._spec_source_series_item=curve
            curve.setVisible(not self._source_software_composite_selected())
            if old is not None:
                self.spec_plot.removeItem(old)
            raw.setVisible(False)  # Never replace source samples or summary.
            self._spec_source_series_model=result
            self._spec_source_series_signature=signature
            if self._source_software_composite_selected():
                self.spec_source_series_info.setText(
                    f'ЕДИНЫЙ TCo2Draw: {len(segments)} source-штрихов '
                    'составляют один RGBA вместе с сеткой и рамкой. '
                    'Оригинальные TCanvas.TextOut/Font/DPI НЕ проверены.')
                return
            self.spec_source_series_info.setText(
                f'ИСТОЧНИК TQGRSeries: {result["data_size_original"]} Float32 → '
                f'{len(result["columns"])} столбцов, '
                f'{len(segments)} штрихов, Qt {w}×{h} логических px. '
                'Сохранены min/max и порядок по исходному Unit115; '
                'не доказаны Win32 PixelRect, шрифт, x87 и pixel parity.')
        finally:
            self._spec_source_series_busy=False

    def _restore_default_spec_axis_grid(self):
        """Restore standard pyqtgraph; no source raster must leak to archive."""
        applied=(self._spec_source_grid_applied or
                 bool(self._spec_source_grid_lines) or
                 self._spec_source_raster_item is not None)
        for line in self._spec_source_grid_lines:
            self.spec_plot.removeItem(line)
        self._spec_source_grid_lines=[]
        if self._spec_source_raster_item is not None:
            self.spec_plot.removeItem(self._spec_source_raster_item)
        self._spec_source_raster_item=None
        self._spec_source_raster_data=None
        if applied:
            self.spec_plot.showGrid(x=True,y=True,alpha=.2)
        if self._spec_source_grid_applied:
            for name in ('bottom','left'):
                axis=self.spec_plot.getPlotItem().getAxis(name)
                axis.setTicks(None)
                axis.setTickFont(None)
                axis.label.setVisible(True)
                if self._spec_source_grid_axis_label_fonts is not None:
                    axis.label.setFont(
                        self._spec_source_grid_axis_label_fonts[name])
        self._spec_source_grid_applied=False
        self._spec_source_grid_model=None
        self._spec_source_grid_axis_label_fonts=None
        if self._spec_source_series_item is not None:
            self._spec_source_series_item.setVisible(True)
        blocked=self.spec_source_raster_checkbox.blockSignals(True)
        self.spec_source_raster_checkbox.setChecked(False)
        self.spec_source_raster_checkbox.blockSignals(blocked)
        self.spec_source_raster_checkbox.setEnabled(False)
        self.spec_source_grid_info.setText(
            'Сетка Qt: обычная. TQGrapher 10×10 и программный TCo2Draw '
            'доступны только для проверенного оригинального Power/Y.')

    def _toggle_source_tqgrapher_grid_candidate(self,enabled):
        """Research-only source rendering, disabled for archives and Native."""
        if enabled and self._spectrum_reference is None:
            blocked=self.spec_source_grid_checkbox.blockSignals(True)
            self.spec_source_grid_checkbox.setChecked(False)
            self.spec_source_grid_checkbox.blockSignals(blocked)
            self._restore_default_spec_axis_grid()
            return
        if not enabled:
            self._restore_default_spec_axis_grid()
            if self.spec_source_series_checkbox.isChecked():
                self._safe_source_tqgr_series_update()
            return
        self.spec_source_raster_checkbox.setEnabled(True)
        self._safe_source_grid_update()

    def _toggle_source_tco2draw_raster(self,*_):
        if not (self._spectrum_reference is not None
                and self.spec_source_grid_checkbox.isChecked()):
            blocked=self.spec_source_raster_checkbox.blockSignals(True)
            self.spec_source_raster_checkbox.setChecked(False)
            self.spec_source_raster_checkbox.blockSignals(blocked)
            return
        # Recompute even if the source grid ticks have not changed.
        self._spec_source_grid_model=None
        self._safe_source_grid_update()
        if self.spec_source_series_checkbox.isChecked():
            self._safe_source_tqgr_series_update()

    def _safe_source_grid_update(self):
        try:
            self._sync_source_tqgrapher_grid_candidate()
        except (ValueError,OverflowError,TypeError,MemoryError) as exc:
            self._restore_default_spec_axis_grid()
            blocked=self.spec_source_grid_checkbox.blockSignals(True)
            self.spec_source_grid_checkbox.setChecked(False)
            self.spec_source_grid_checkbox.blockSignals(blocked)
            self.statusBar().showMessage('Растер TQGrapher отключён: '+str(exc))

    def _sync_source_tqgrapher_grid_candidate(self,*_):
        """Source-derived 10x10 and optional software raster in Qt logical px.

        Both modes use the SAME verified original Power/Y arrays. ImageItem
        is an opt-in approximation of original TCo2Draw raster coverage,
        never an attested Win32 TBitmap or TCanvas DPI pixel reference.
        """
        if (self._spec_source_grid_apply_busy
                or self._spectrum_reference is None
                or not self.spec_source_grid_checkbox.isChecked()
                or self._full_spectrum is None):
            return
        self._spec_source_grid_apply_busy=True
        try:
            vb=self.spec_plot.getViewBox()
            xr,yr=vb.viewRange()
            raster=self.spec_source_raster_checkbox.isChecked()
            combined=(raster and self._source_software_composite_selected())
            size=(max(4,int(round(vb.width()))),
                  max(4,int(round(vb.height()))))
            model=source_tqgrapher_grid_candidate(
                scr_left=float(xr[0]),scr_width=float(xr[1]-xr[0]),
                scr_bottom=float(yr[0]),scr_height=float(yr[1]-yr[0]))
            model['tco2draw_source_style']=source_tco2draw_grid_contract()
            if (self._spec_source_grid_model is not None and all(
                self._spec_source_grid_model[key]==model[key]
                for key in ('x_grid_ticks','y_grid_ticks',
                            'x_tick_labels_candidate',
                            'y_tick_labels_candidate')) and
                self._spec_source_grid_model.get('raster_preview_enabled')==raster and
                self._spec_source_grid_model.get('combined_preview_active',False)==combined and
                (not raster or
                 self._spec_source_grid_model.get('qt_raster_size')==size)):
                return
            axes=self.spec_plot.getPlotItem()
            if not self._spec_source_grid_applied:
                self._spec_source_grid_axis_label_fonts={
                    name:QFont(axes.getAxis(name).label.font())
                    for name in ('bottom','left')}
            font=qt_source_font_candidate()
            # The SAME candidate font must supply all Qt TextWidth/Height
            # and the QPainter raster. This is NOT a native GDI measurement.
            fm=QFontMetrics(font)
            for name,ticks,labels in (
                ('bottom',model['x_grid_ticks'],model['x_tick_labels_candidate']),
                ('left',model['y_grid_ticks'],model['y_tick_labels_candidate'])
            ):
                axis=axes.getAxis(name)
                axis.setTickFont(font)
                axis.label.setFont(font)
                if combined:
                    # Original tick labels will now be inside the one
                    # research bitmap. Do not double-label with Qt axis.
                    axis.setTicks([[(tick,'') for tick in ticks]])
                else:
                    axis.setTicks([list(zip(ticks,labels))])
                axis.label.setVisible(not combined)
            self.spec_plot.showGrid(x=False,y=False)
            for line in self._spec_source_grid_lines:
                self.spec_plot.removeItem(line)
            self._spec_source_grid_lines=[]
            if self._spec_source_raster_item is not None:
                self.spec_plot.removeItem(self._spec_source_raster_item)
            self._spec_source_raster_item=None
            self._spec_source_raster_data=None
            model['raster_preview_enabled']=raster
            model['combined_preview_active']=bool(combined)
            if raster:
                w,h=size
                if combined:
                    count=int(self._spec_display_contract['grapher_series_bins'])
                    data=np.asarray(self._full_spectrum['amplitude'],dtype='<f4')
                    if count<=0 or count>data.size:
                        raise ValueError('Original TQGRSeries size not accepted')
                    # One candidate source bitmap. On Windows native GDI
                    # supplies both text metrics and glyph pixels; elsewhere
                    # Qt remains the explicitly approximate fallback.
                    context=(Win32SourceTextCanvas()
                             if native_gdi_supported() else nullcontext(None))
                    with context as gdi:
                        tw=(gdi.text_width if gdi is not None
                            else lambda text:int(fm.horizontalAdvance(text)))
                        th=(gdi.text_height if gdi is not None
                            else lambda text:int(fm.height()))
                        text_renderer=(gdi.draw_text if gdi is not None
                            else lambda image,events:
                                qt_textout_source_positions_rgba(
                                    image,events,font=font))
                        composite=build_tqgrapher_composite(
                            data[:count],
                            canvas_width=w,canvas_height=h,
                            zero_text_width=int(tw('0')),
                            six_decimals_text_width=int(tw('0.000000')),
                            zero_text_height=int(th('0')),
                            scr_left=float(xr[0]),scr_width=float(xr[1]-xr[0]),
                            scr_bottom=float(yr[0]),scr_height=float(yr[1]-yr[0]),
                            series_x_start=0.,
                            series_x_scale=float(self._full_spectrum['df_hz']),
                            series_y_scale=1.,
                            x_name_present=True,y_name_present=True,
                            x_name='Гц',
                            y_name=str(self._full_spectrum.get('unit','')),
                            source_text_width=tw,source_text_height=th,
                            font_metric_provenance=(
                                'gdi_reconstructed_from_dfm' if gdi
                                else 'qt_approximation'),
                            research_textout_renderer=text_renderer)
                        model['spectrum_textout_engine']=(
                            'WIN32_GDI_DFM_CANDIDATE' if gdi
                            else 'QT_RESEARCH_FALLBACK')
                        model['spectrum_textout_native_metrics']=(
                            gdi.diagnostics() if gdi is not None else None)
                    pixels=composite['rgba']
                    model['qt_textout_candidate_rendered']=composite[
                        'qt_textout_candidate_rendered']
                    model['source_textout_placements']=composite[
                        'source_textout_layout']
                    model['combined_source']=composite['source']
                    model['combined_paintbox_rect']=(
                        composite['canvas']['pixel_left'],
                        composite['canvas']['pixel_top'],
                        composite['canvas']['pixel_right'],
                        composite['canvas']['pixel_bottom'])
                    model['combined_grid_segments']=composite['grid_segment_count']
                    model['combined_series_segments']=composite['series_segment_count']
                    model['combined_frame_segments']=composite['border_segment_count']
                    model['original_runtime_pixel_parity_verified']=False
                    model['original_runtime_tcanvas_font_verified']=False
                else:
                    segments=source_grid_segments(
                        x_ticks=model['x_grid_ticks'],
                        y_ticks=model['y_grid_ticks'],
                        view_x=xr,view_y=yr,width=w,height=h)
                    pixels=source_raster_rgba(
                        width=w,height=h,segments=segments)
                # Raster: row 0 is screen TOP. Qt image +Y goes upward,
                # therefore reverse the array rows before ImageItem.
                picture=pg.ImageItem(
                    np.ascontiguousarray(pixels[::-1]),axisOrder='row-major')
                picture.setRect(QRectF(
                    float(xr[0]),float(yr[0]),
                    float(xr[1]-xr[0]),float(yr[1]-yr[0])))
                picture.setZValue(-100)
                self.spec_plot.addItem(picture,ignoreBounds=True)
                self._spec_source_raster_item=picture
                self._spec_source_raster_data=pixels
                if self._spec_source_series_item is not None:
                    self._spec_source_series_item.setVisible(not combined)
                if combined and self._spec_source_series_raw_item is not None:
                    self._spec_source_series_raw_item.setVisible(False)
                model['qt_raster_size']=size
                model['tco2draw_raster_contract']=tco2draw_raster_contract()
            else:
                if self._spec_source_series_item is not None:
                    self._spec_source_series_item.setVisible(True)
                for angle,ticks in (
                    (90,model['x_grid_ticks']),
                    (0,model['y_grid_ticks'])
                ):
                    for value in ticks:
                        line=pg.InfiniteLine(
                            pos=value,angle=angle,movable=False,
                            pen=pg.mkPen(GRID_LINE_HEX,width=1))
                        line.setZValue(-100)
                        line.setAcceptedMouseButtons(Qt.NoButton)
                        self.spec_plot.addItem(line,ignoreBounds=True)
                        self._spec_source_grid_lines.append(line)
            self._spec_source_grid_applied=True
            self._spec_source_grid_model=model
            self.spec_source_grid_info.setText(
                f'ИССЛЕДОВАНИЕ TQGrapher: X через '
                f"{model['source_v_line_spacing_x_single']:.7g} Гц, "
                f"Y через {model['source_h_line_spacing_y_single']:.7g}; "
                f'{len(model["x_grid_ticks"])} / '
                f'{len(model["y_grid_ticks"])} линий. '
                f'Цвет исходного TCo2Draw {GRID_LINE_HEX}, фон {BACKGROUND_HEX}. '
                + ('ЕДИНЫЙ BMP: сетка → подписи → кривая → рамка; '
                   'Windows GDI Tahoma -13 из DFM (или Qt fallback); '
                   'реальный runtime Canvas/DPI оригинала НЕ проверен; '
                   if combined else
                   ('Software RGB растр сетки в Qt logical px; '
                    if raster else 'Простые линии Qt QPen; '))
                + 'Tahoma 13 Qt px — кандидат DFM; FormatFloat и Delphi '
                  'Font/PixelRect/DPI/pixel parity НЕ подтверждены.')
        finally:
            self._spec_source_grid_apply_busy=False

    def _sync_x32dbg_reference_f_range_label(self):
        """Display the real reference Single separately from archive guess."""
        ref=self._spectrum_reference
        if ref is None:
            self.spec_x32dbg_f_range_label.setText(
                'FRange x32dbg: эталон не открыт. '
                'FRange=1 ниже — отдельная гипотеза архива.')
            return
        f32bits=int(np.asarray([ref.f_range],dtype='<f4').view('<u4')[0])
        self.spec_x32dbg_f_range_label.setText(
            f'ОРИГИНАЛ x32dbg · FRange={ref.f_range:.9g} '
            f'· Single 0x{f32bits:08X} (из JSON)\n'
            'Это не ручной FRange гипотезы архива ниже; '
            'Power/Y подтверждены по SHA и всем Float32.')

    def choose_original_spectrum_reference(self):
        """User explicitly selects local reference JSON; never open a device."""
        if self._live_active:
            self.statusBar().showMessage(
                'Во время записи Native эталоны x32dbg открывать нельзя')
            return
        # Original x32dbg Power/Y is self-contained: archive selection is
        # OPTIONAL. This avoids misrepresenting a different BIN window as
        # the source of the original reference.
        path,_=QFileDialog.getOpenFileName(
            self,'Локальный эталон GetSpectrum (JSON + Power/Y BIN)','',
            'x32dbg reference manifest (*.json)')
        if not path:return
        try:
            self.show_original_spectrum_reference(path)
        except (OSError,ValueError,KeyError,TypeError,UnicodeError,RuntimeError) as exc:
            QMessageBox.warning(self,'Оригинальный Power/Y не принят',str(exc))

    def _leave_original_spectrum_reference(self):
        """Restore original archive controls, without touching source samples."""
        if self._spectrum_reference is None:return
        # Reset all opt-in research axes before any archive or empty screen
        # becomes visible. Never leak source grid/tick font into other plots.
        was_blocked=self.spec_source_grid_checkbox.blockSignals(True)
        self.spec_source_grid_checkbox.setChecked(False)
        self.spec_source_grid_checkbox.blockSignals(was_blocked)
        self._restore_default_spec_axis_grid()
        self._restore_source_tqgr_series()
        self.spec_source_grid_checkbox.setEnabled(False)
        state=self._spectrum_reference_saved
        self._spectrum_reference=None
        self._spectrum_reference_saved=None
        self._sync_x32dbg_reference_f_range_label()
        if state is None:return
        for control,was_enabled in state['enabled']:
            control.setEnabled(was_enabled)
        for control,index in (
            (self.spec_mode,state['mode_index']),
            (self.spec_n,state['n_index']),
            (self.spec_avg,state['avg_index']),
        ):
            was_blocked=control.blockSignals(True)
            control.setCurrentIndex(index)
            control.blockSignals(was_blocked)
        self._spec_loaded_sample_rate_hz=state['sample_rate_hz']
        self.spec_envelope_button.setText(state['envelope_button_text'])
        self._spec_original_vscale_mode=None
        self._spec_original_vscale_tag=None
        self._spec_vertical_model=None
        self._spec_vscroll_source_candidate=None
        self._spec_original_hscale_selected=None
        self._rebuild_original_vscale_menu()
        self._sync_spec_lines_presentation()
        self.spec_reference_restore_button.setEnabled(False)
        self.spec_reference_open_button.setEnabled(True)
        self.title.setText(state['title_text'])
        self.title.setToolTip(state['title_tooltip'])
        self.adc.setToolTip(state['adc_tooltip'])
        if self.session is None:
            self._spec_graph_default_vscale_candidate=None
            self.spec_graph_default_label.setText(
                'GraphDefaultVScale: нет активного архива или x32dbg эталона')
        if not state['spectrum_tab_enabled']:
            # With no archive, the Spectrum tab was originally disabled.
            # Switch to the previous accessible tab before disabling it.
            if self.tabs.currentIndex()==2:
                self.tabs.setCurrentIndex(state['tab_index'])
            self.tabs.setTabEnabled(2,False)
        else:
            self.tabs.setTabEnabled(2,True)

    def restore_archive_spectrum_after_reference(self):
        """Return to the actual archive, or to an EMPTY main screen."""
        if self._spectrum_reference is None:
            return
        if self.session is not None:
            self.refresh_spec()
            return
        self._leave_original_spectrum_reference()
        self._full_spectrum=None
        self._spectrum_summary=None
        self.spec_plot.clear()
        self.spec_line=None
        self.spec_hline=None
        self.spec_xor_crosshair=None
        self._spec_last_cursor=None
        self._spec_mouse_pixel=None
        self.spec_copy_button.setEnabled(False)
        self.spec_save_button.setEnabled(False)
        self.spec_original_copy_compare.setEnabled(False)
        self.spec_canvas_geometry_button.setEnabled(False)
        self.spec_mean_primary.setText('Сначала откройте измерение')
        self.spec_mean_primary.setToolTip('')
        self.spec_mean.setText('Данные спектра: —')
        self.spec_hint.setText('Спектр ещё не открыт')
        self.spec_cursor_primary.setText('Курсор: —')
        self.statusBar().showMessage(
            'Эталон закрыт; исходное измерение не было открыто')

    def show_original_spectrum_reference(self,manifest_path):
        """Display ORIGINAL operator capture in the SAME spectrum PlotWidget.

        This ONLY changes the visible research graph, never self.session,
        archived sample bytes, FFT algorithms or actual device calibration.
        The read-only loader checks every Float32 word before ANY UI change.
        """
        if self._live_active:
            raise ValueError('Оригинальный эталон нельзя открыть во время записи Native')
        ref=load_original_spectrum_reference(manifest_path)
        n_index=self.spec_n.findData(ref.n_fft)
        if n_index < 0:
            raise ValueError('FFT N оригинала отсутствует среди поддерживаемых размеров')
        if self._spectrum_reference is not None:
            # A second reference replaces only the previous *visual* snapshot.
            self._leave_original_spectrum_reference()
        frozen=(
            self.spec_mode,self.spec_n,self.spec_lines_button,
            self.spec_envelope_button,self.spec_envelope_code,
            self.spec_backend,self.spec_f_range,self.spec_input_domain,
            self.spec_last,self.spec_hz,self.adc,self.spec_compare_button,
        )
        self._spectrum_reference_saved={
            'mode_index':self.spec_mode.currentIndex(),
            'n_index':self.spec_n.currentIndex(),
            'avg_index':self.spec_avg.currentIndex(),
            'sample_rate_hz':self._spec_loaded_sample_rate_hz,
            'envelope_button_text':self.spec_envelope_button.text(),
            'enabled':[(control,control.isEnabled()) for control in frozen],
            'tab_index':self.tabs.currentIndex(),
            'spectrum_tab_enabled':self.tabs.isTabEnabled(2),
            'title_text':self.title.text(),
            'title_tooltip':self.title.toolTip(),
            'adc_tooltip':self.adc.toolTip(),
        }
        self._spectrum_reference=ref
        self._sync_x32dbg_reference_f_range_label()
        self.spec_source_grid_checkbox.setEnabled(True)
        self.spec_source_raster_checkbox.setEnabled(False)
        self.spec_source_series_checkbox.setEnabled(True)
        for control,index in (
            (self.spec_mode,ref.mode),(self.spec_n,n_index),
            (self.spec_avg,0 if ref.mode==0 else 1),
        ):
            was_blocked=control.blockSignals(True)
            control.setCurrentIndex(index)
            control.blockSignals(was_blocked)
        self._spec_loaded_sample_rate_hz=float(ref.fs_hz)
        self._rebuild_original_vscale_menu()
        self._sync_spec_lines_presentation(ref.fs_hz)
        self.spec_envelope_button.setText('ЭТАЛОН · исходные Power/Y')
        for control in frozen:
            control.setEnabled(False)
        self.spec_reference_restore_button.setEnabled(True)
        d=ref.to_spectrum_record(channel=self._ch())
        contract=spectrum_display_contract(ref.n_fft,ref.fs_hz)
        visible_bins=contract['grapher_series_bins']
        right=contract['grapher_axis_end_frequency_hz']
        xx=np.asarray(d['frequency_hz'],dtype=np.float64)
        yy=np.asarray(d['amplitude'],dtype=np.float64)
        self._full_spectrum=d
        self._spectrum_summary=d['spectrum_summary']
        self._spec_display_contract=contract
        self._spec_visible_max_hz=float(right)
        self._spec_original_vscale_mode=None
        self._spec_original_vscale_tag=None
        self._spec_vertical_model=None
        self._spec_vscroll_source_candidate=None
        self._spec_original_hscale_selected=None
        for action in self._spec_vscale_actions:
            action.setChecked(False)
        for action in self._spec_hscale_actions:
            action.setChecked(False)
        self.spec_plot.clear()
        self.spec_plot.setLabel('bottom','Гц')
        self.spec_plot.setLabel('left',d['unit'])
        self._spec_source_series_raw_item=self.spec_plot.plot(
            xx[:visible_bins],yy[:visible_bins],pen=pg.mkPen('#000000'))
        self.spec_line=pg.InfiniteLine(angle=90,pen=pg.mkPen(None))
        self.spec_line.setVisible(False)
        self.spec_plot.addItem(self.spec_line)
        self.spec_hline=pg.InfiniteLine(angle=0,pen=pg.mkPen(None))
        self.spec_hline.setVisible(False)
        self.spec_plot.addItem(self.spec_hline)
        self.spec_xor_crosshair=QtSpectrumXorCursor(self.spec_plot.getViewBox())
        self.spec_plot.addItem(self.spec_xor_crosshair,ignoreBounds=True)
        self._spec_last_cursor=None
        self._spec_mouse_pixel=None
        self._spec_data_ymin=float(np.min(yy[:visible_bins]))
        self._spec_data_ymax=float(np.max(yy[:visible_bins]))
        if self._spec_data_ymax<=self._spec_data_ymin:
            self._spec_data_ymax=self._spec_data_ymin+1.
        vb=self.spec_plot.getViewBox()
        self.spec_plot.enableAutoRange()
        if ref.mode==0:
            self._spec_data_ymax=0.
            self._spec_data_ymin=min(self._spec_data_ymin,-150.)
            vb.setYRange(-150.,0.,padding=0.)
            self.spec_vscale_button.setText(
                original_v_scale_options(0)[0]['caption'])
        else:
            self.spec_vscale_button.setText('Y · эталонные значения')
        vb.setLimits(xMin=0.,xMax=float(right))
        vb.setXRange(0.,float(right),padding=0.)
        self.spec_hscale_button.setText(f'{right:g} Гц')
        self._sync_spec_scroll()
        # Original mSpecType1Click resets default V menu Tag: 0 (dB) or 3
        # (linear). Under a reference, apply source absolute scroll with
        # the explicit user-supplied original FRange word, not a Qt data
        # min/max baseline. This does NOT establish original Canvas pixels.
        self._select_original_vscale(source_default_vertical_tag(ref.mode))
        self.spec_copy_button.setEnabled(False)
        self.spec_save_button.setEnabled(False)
        self.spec_original_copy_compare.setEnabled(False)
        self.spec_canvas_geometry_button.setEnabled(True)
        self.spec_cursor_primary.setText('Курсор эталона: —')
        # The original PageSpectrum shows the three measurement values
        # in its fixed 106px high left panel. Keep the technical Power/Y
        # provenance in the research dock and tooltip: a four-line message
        # about the debugger is too long here and clips the actual numbers.
        fields=spectrum_triplet_text(
            ref.summary,decimal_separator=',').split('\t')
        original_summary_accepted=ref.original_summary_words_equal is True
        verification=(
            'Ориг. HEX: 3/3' if original_summary_accepted
            else 'Нет HEX: из Power')
        # The native 177px tools column gives only ~144px usable QLabel
        # width. Keep each of the four lines short enough not to wrap, or
        # their 5-line height clips beyond the fixed original 106px panel.
        self.spec_mean_primary.setText(
            f'СКЗ: {fields[0]}\n'
            f'Пик: {fields[1]} Гц\n'
            f'Ампл.: {fields[2]}\n'
            + verification)
        self.spec_mean_primary.setToolTip(
            'Результаты x32dbg GetSpectrum рассчитаны из оригинального '
            'Power и сверены с тремя исходными HEX только при наличии '
            'summary_hex в JSON. Физические единицы, калибровка, '
            'конкретный АЦП, позиция окна и один runtime-вызов '
            'НЕ аттестованы. Полные Power/Y 131072/131072 '
            'проверены по SHA и по Float32.')
        self.spec_mean.setText(
            'ЭТАЛОН оригинального GetSpectrum, [EBP-2C]/[EBP-30]\n'
            f"Численное совпадение всех {ref.n_fft//2} Float32 · 0 ULP\n"
            f"Mean={ref.summary['output_mean']:.9g} · "
            f"PeakX={ref.summary['output_peak_frequency_hz']:.9g} Гц · "
            f"PeakY={ref.summary['output_peak_y']:.9g}\n"
            'Это НЕ новый FFT и НЕ проверка пикселей Delphi')
        self.spec_hint.setText(
            'Локально импортированный ЭТАЛОН x32dbg 007D17E7. '
            'Исходные массивы только прочитаны; real same-call provenance '
            'и точное совпадение Qt/TQGrapher PIXEL по-прежнему не доказаны.')
        # This must be visible even if a DIFFERENT BIN/TSXML archive is still
        # selected. Do not display its MVK serial/ADC as if it proved the
        # source of this unrelated user-captured original Power/Y.
        self.title.setText(
            f'ЭТАЛОН x32dbg · Tag{ref.mode} · N={ref.n_fft} · АЦП ?')
        self.title.setToolTip(
            'Локальный исходный массив x32dbg, а не текущий архив. '
            'АЦП, исходное окно и физическая калибровка эталона '
            'не подтверждены. FFT повторно не вычислялся.')
        self.adc.setToolTip(
            'Это канал выбранного архива, НЕ доказанный канал эталона x32dbg.')
        self.tabs.setTabEnabled(2,True)
        self.tabs.setCurrentIndex(2)
        self.statusBar().showMessage(
            'Stage111Z31A: оригинальный Y показан без FFT, SHA256 и '
            'побитовое сравнение Power/Y прошли; Copy/Save отключены')
        return ref.report()

    def _clear_archive_source_projection(self):
        """Remove display-only strokes without touching measured FFT bins."""
        curve=self._archive_source_curve
        self._archive_source_curve=None
        self._archive_source_projection_signature=None
        self._archive_source_projection_model=None
        if curve is not None and curve.scene() is not None:
            self.spec_plot.removeItem(curve)
        if (self._archive_raw_line is not None and
                self._archive_raw_line.scene() is not None):
            self._archive_raw_line.setVisible(True)

    def _sync_archive_source_projection(self,*_):
        """Original pixel-column extrema for standard BIN/TSXML plots.

        Sparse zoom falls back to the FULL original point sequence.
        Never mutate Float32 powers, displayed amplitudes or summary.
        """
        if (self._archive_source_projection_busy
                or self.session is None
                or self._live_active
                or self._spectrum_reference is not None
                or self._full_spectrum is None
                or self._archive_raw_line is None
                or self._archive_raw_line.scene() is None
                or getattr(self,'_spec_display_contract',None) is None):
            return
        self._archive_source_projection_busy=True
        try:
            vb=self.spec_plot.getViewBox()
            xr,yr=vb.viewRange()
            w=max(4,int(round(vb.width())))
            h=max(4,int(round(vb.height())))
            signature=(id(self._full_spectrum),float(xr[0]),float(xr[1]),
                       float(yr[0]),float(yr[1]),w,h)
            if signature==self._archive_source_projection_signature:
                return
            d=self._full_spectrum
            n_fft=int(self._spec_display_contract['full_fft_power_bins'])*2
            projection=spectrum_archive_plot_projection(
                d['amplitude'],n_fft=n_fft,
                sample_rate_hz=float(d['df_hz'])*n_fft,
                view_x=tuple(xr),view_y=tuple(yr),
                pixel_width=w,pixel_height=h)
            meta={key:value for key,value in projection.items()
                  if key not in ('pairs_x_hz','pairs_y')}
            if projection['draw_mode']!='original_pixel_column_minmax':
                self._clear_archive_source_projection()
                self._archive_source_projection_signature=signature
                self._archive_source_projection_model=meta
                return
            # Preserve EXACT one original PlotDataItem (all DataSize
            # source points) for cursor/export/tests, while painting the
            # compressed min/max as a separate NON-DATA QGraphics item.
            # PlotCurveItem would wrongly appear as a second spectrum
            # in PlotItem.listDataItems() and break existing contracts.
            x_pairs=projection['pairs_x_hz'].reshape(-1,2)
            y_pairs=projection['pairs_y'].reshape(-1,2)
            native_path=QPainterPath()
            for (x1,x2),(y1,y2) in zip(x_pairs,y_pairs):
                native_path.moveTo(float(x1),float(y1))
                native_path.lineTo(float(x2),float(y2))
            new_curve=QGraphicsPathItem(native_path)
            pen=pg.mkPen('#000000',width=1)
            pen.setCosmetic(True)  # one device pixel, zoom cannot thicken line
            new_curve.setPen(pen)
            new_curve.setZValue(20)
            self.spec_plot.addItem(new_curve,ignoreBounds=True)
            old=self._archive_source_curve
            self._archive_source_curve=new_curve
            self._archive_source_projection_signature=signature
            self._archive_source_projection_model=meta
            self._archive_raw_line.setVisible(False)
            if old is not None and old.scene() is not None:
                self.spec_plot.removeItem(old)
        except (ValueError,TypeError,KeyError,OverflowError,MemoryError) as exc:
            self._clear_archive_source_projection()
            self._archive_source_projection_model={
                'draw_mode':'full_original_samples_fallback',
                'reason':str(exc),
                'original_delphi_pixel_runtime_verified':False}
        finally:
            self._archive_source_projection_busy=False

    def _fft_backend(self):
        return 'idr_float32' if self.spec_backend.currentIndex()==0 else 'numpy'

    def refresh_spec(self,*_):
        # A normal refresh explicitly RETURNS from a visual-only original Y
        # snapshot to the selected local archive and its calculated FFT.
        self._leave_original_spectrum_reference()
        if self._live_active:
            self._render_live_spectrum()
            return
        if not self.session:return
        self._spec_original_hscale_selected=None
        self.spec_hscale_button.setText('Диапазон X')
        for action in self._spec_hscale_actions:
            action.setChecked(False)
        try:
            start=None if self.spec_last.isChecked() else self.wave_start.value()
            n_fft=int(self.spec_n.currentText())
            samples,fs,_,_=self.session.samples(self._ch())
            self._sync_spec_lines_presentation(fs)
            gate=self._spec_history_gate(n_fft,len(samples),fs)
            if not gate['can_compute_without_padding']:
                raise ValueError(
                    f"Отсутствует полная реальная история FFT N={n_fft}: "
                    f"нужно {gate['required_real_history_samples']}, "
                    f"доступно {gate['archive_end_sample']}; "
                    "дополнение нулями запрещено")
            # Use *all* FFT bins as candidate data. pyqtgraph downsamples only
            # the visual trace, never the original TQGrapher cursor series.
            if self.spec_envelope_button.isChecked():
                if self.envelope_profile is None:
                    raise ValueError('Для спектра огибающей требуется локальный mvkview.idp')
                code=int(self.spec_envelope_code.currentData() or 0)
                # Explicit archive-end choice; original Delphi pointer parity unknown.
                end_s=None if self.spec_last.isChecked() else (
                    self.wave_start.value()+self.wave_seconds.value())
                d=self.session.spectrum_envelope(self._ch(),code,n_fft,
                       self.envelope_profile,end_s=end_s,
                       mode=self.spec_mode.currentIndex(),
                       backend=self._fft_backend(),f_range=self.spec_f_range.value(),
                       input_domain=self.spec_input_domain.currentData())
            else:
                d=self.session.spectrum(self._ch(),n_fft,self.spec_mode.currentIndex(),
                                        start,max_hz=1e9,max_points=n_fft//2,
                                        backend=self._fft_backend(),
                                        f_range=self.spec_f_range.value(),
                                        input_domain=self.spec_input_domain.currentData())
            if len(d['amplitude'])!=n_fft//2:
                raise ValueError('Пиксельный курсор требует все N/2 FFT-бинов')
            display_contract=spectrum_display_contract(n_fft,d['df_hz']*n_fft)
            d['grapher_series_bins']=display_contract['grapher_series_bins']
            self._spec_display_contract=display_contract
            # Original TQGrapher screenshot: x-axis ends at DataSize * df;
            # last stored series bin is one df earlier (25599.75 vs 25600
            # Hz at N262144/Fs65536). Never invent a final data sample.
            self._spec_visible_max_hz=min(self.spec_hz.value(),
                                           display_contract['grapher_axis_end_frequency_hz'])
            self._full_spectrum=d
            self._spectrum_summary=d.get('spectrum_summary')
            valid_summary=(isinstance(self._spectrum_summary,dict) and
                self._spectrum_summary.get('source')==
                'APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE')
            self.spec_copy_button.setEnabled(valid_summary)
            self.spec_save_button.setEnabled(valid_summary)
            self.spec_original_copy_compare.setEnabled(valid_summary)
            self.spec_canvas_geometry_button.setEnabled(valid_summary)
            xx=np.asarray(d['frequency_hz'],dtype=np.float64)
            yy=np.asarray(d['amplitude'],dtype=np.float64)
            visible=(xx<=self._spec_visible_max_hz)&(
                np.arange(len(xx))<display_contract['grapher_series_bins'])
            # Clear previously compressed *visuals*, not stored FFT.
            self._clear_archive_source_projection()
            self._archive_raw_line=None
            self.spec_plot.clear()
            # Native TQGrapher labels the axis by its UNIT, not a long title.
            self.spec_plot.setLabel('bottom','Гц')
            # Original MVKView spectrum is a black hairline over white.
            # Original XOR-green cursor is separately studied (do not
            # approximate it by a static colored spectrum line).
            self._archive_raw_line=self.spec_plot.plot(
                xx[visible],yy[visible],pen=pg.mkPen('#000000'))
            # Preserve existing testable X/Y InfiniteLine state and callbacks,
            # but make their pen invisible. Only the last-drawn overlay uses
            # original bitwise pmXor green on top of a black spectral trace.
            self.spec_line=pg.InfiniteLine(angle=90,pen=pg.mkPen(None))
            self.spec_line.setVisible(False)
            self.spec_plot.addItem(self.spec_line)
            self.spec_hline=pg.InfiniteLine(angle=0,pen=pg.mkPen(None))
            self.spec_hline.setVisible(False)
            self.spec_plot.addItem(self.spec_hline)
            self.spec_xor_crosshair=QtSpectrumXorCursor(
                self.spec_plot.getViewBox())
            self.spec_plot.addItem(self.spec_xor_crosshair,ignoreBounds=True)
            self._spec_last_cursor=None
            self._spec_mouse_pixel=None
            # Long engineering calibration disclaimer belongs in the
            # existing visible summary. Native PageSpectrum uses the short
            # Y-axis caption 'дБ'; a verbose label consumes plot width and
            # falsely suggests a different axis unit for log spectra.
            self.spec_plot.setLabel(
                'left','дБ' if self.spec_mode.currentIndex()==0 else d['unit'])
            self._spec_data_ymin=float(np.min(yy[visible])) if np.any(visible) else 0.
            self._spec_data_ymax=float(np.max(yy[visible])) if np.any(visible) else 1.
            if self._spec_data_ymax<=self._spec_data_ymin:
                self._spec_data_ymax=self._spec_data_ymin+1.
            self.spec_plot.enableAutoRange()
            if self.spec_mode.currentIndex()==0:
                # Source default vertical log scale: 150 dB. The original
                # screenshot confirms 0..-150 for the same Tag0 case.
                # Display-only preset; NEVER adjust FFT powers.
                self._spec_data_ymax=0.
                self._spec_data_ymin=min(self._spec_data_ymin,-150.)
                self.spec_plot.setYRange(-150.,0.,padding=0)
                if self._spec_original_vscale_tag is None:
                    self.spec_vscale_button.setText(
                        original_v_scale_options(0)[0]['caption'])
            elif self._spec_original_vscale_tag is None:
                self.spec_vscale_button.setText('Шкала Y · авто')
            self.spec_plot.setXRange(0,self._spec_visible_max_hz,padding=0)
            if self._spec_original_hscale_selected is None:
                self.spec_hscale_button.setText(f'{self._spec_visible_max_hz:g} Гц')
            self.spec_plot.getViewBox().setLimits(
                xMin=0,xMax=float(self._spec_visible_max_hz))
            self._sync_spec_scroll()
            self._sync_spectrum_summary_primary()
            self.spec_cursor_primary.setText('Курсор: —')
            if valid_summary:
                summ=self._spectrum_summary
                self.spec_mean.setText(
                    ("GetSpectrum · BIN/TSXML Single (калибровка НЕ подтверждена)\n"
                     if isinstance(self.session,DirectBinSession)
                     else "GetSpectrum · IDR-кандидат\n")
                    + f"Среднее: {summ['output_mean']:.7g} (FRange пока не проверен)\n"
                    f"Пик: {summ['output_peak_frequency_hz']:.7g} Гц\n"
                    f"Амплитуда пика: {summ['output_peak_y']:.7g}\n"
                    f"Ширина FFT: {d['df_hz']:.7g} Гц, "
                    f"серия {display_contract['grapher_series_bins']}/{len(xx)} бинов\n"
                    + ("Огибающая, исходные FIR локально" if self.spec_envelope_button.isChecked()
                       else "Без огибающей") + "\nОригинальный численный паритет не доказан")
            else:
                self.spec_mean.setText('Нет принятого локального GetSpectrum summary')
            self.spec_hint.setText(
                f"{d['source']} · {d['fft_backend']} · N/2={len(xx)} исходных бинов · "
                f"TQGRSeries={display_contract['grapher_series_bins']} · "
                f"df={d['df_hz']:.7g} Гц · среднее DC "
                f"{d.get('raw_mean_removed_m_s2',d.get('removed_mean_m_s2',0.)):.6g} "
                f"{'условн. ед. BIN' if isinstance(self.session,DirectBinSession) else 'м/с²'} · "
                + ("после FIR повторного DC нет · "
                   if self.spec_envelope_button.isChecked() else "")
                + ("FIR на Single(BIN/FRange) до удаления DC: ГИПОТЕЗА "
                   "об исходном Float32-кольце · "
                   if (self.spec_envelope_button.isChecked() and
                       d.get('original_storage_read_divided_by_range')) else "")
                + f"FRange={d.get('f_range_used',1.):.7g}, "
                  f"источник={d.get('input_domain','calibrated_bin')} · "
                  "фактическая калибровка НЕ доказана · "
                  "пиксельный курсор TQGrapher — кандидат (Delphi parity НЕ доказан)")
            self._spec_graph_default_vscale_candidate=spectrum_graph_default_vscale(
                self.spec_f_range.value(),self.spec_mode.currentIndex())
            self._update_original_vscale_candidate_label(
                self._spec_graph_default_vscale_candidate)
            self._spec_last_valid_fft_n=n_fft
            label=('ОРИГИНАЛЬНЫЙ пункт bSpecLines' if n_fft in FFT_WINDOW_SAMPLES
                   else 'ИССЛЕДОВАТЕЛЬСКИЙ NFFT — в меню Delphi отсутствует')
            self.spec_n_provenance.setText(
                f"FFT {n_fft}: {label}; история BIN проверена. "
                "Численный паритет Delphi не установлен.")
            self._sync_fft_menu_availability(samples_count=len(samples),
                                             sample_rate=fs)
            if (self._spec_original_vscale_tag is not None and
                    self._spec_original_vscale_mode==self.spec_mode.currentIndex()):
                tag=self._spec_original_vscale_tag
                previous=self._spec_vertical_model
                restored=source_vertical_selection(
                    self.spec_mode.currentIndex(),tag,
                    old_tag=tag if previous else None,
                    old_position=previous['delphi_position'] if previous else 0)
                self._apply_original_vscale_candidate(restored)
            # Final source X/Y view has been applied.
            self._sync_archive_source_projection()
            self._spectrum_envelope_dirty=False
        except (OSError,KeyError,ValueError) as e:
            # An archive may change after DirectBinSession.open(). A failed
            # re-read MUST NOT leave its old plot, cursor, or three-value
            # readout visible as if they belonged to the current source.
            # Invalidate the data before clearing Qt items: range-change
            # signals must not re-project a stale FFT during cleanup.
            self._clear_archive_source_projection()
            self._full_spectrum=None
            self._spectrum_summary=None
            self._spec_display_contract=None
            self._archive_raw_line=None
            self._spec_last_cursor=None
            self._spec_mouse_pixel=None
            self.spec_line=None
            self.spec_hline=None
            self.spec_xor_crosshair=None
            self.spec_plot.clear()
            self.spec_copy_button.setEnabled(False)
            self.spec_save_button.setEnabled(False)
            self.spec_original_copy_compare.setEnabled(False)
            self.spec_canvas_geometry_button.setEnabled(False)
            self._sync_spectrum_summary_primary()
            self.spec_cursor_primary.setText('Курсор: —')
            self.spec_mean.setText('Спектр не рассчитан: '+str(e))
            self.spec_hint.setText('Нет действительного спектра: '+str(e))
            self._error(e)

    def _wave_click(self,event):
        """Keep explicit click support; original Delphi also uses MouseMove."""
        if event.button()==Qt.LeftButton:
            self._wave_at_scene_pos(event.scenePos(),force=True)

    def _wave_mouse_move(self,scene_pos):
        """Original _Unit128:0084B4AC forwards mouse X, not button or Y."""
        self._wave_at_scene_pos(scene_pos,force=False)

    def _wave_at_scene_pos(self,pos,*,force=False):
        if not self.session or self.wave_line is None or not isinstance(pos,QPointF):
            return
        try:
            vb=self.wave_plot.getViewBox()
            rect=vb.sceneBoundingRect()
            pixel=math.trunc(pos.x()-rect.left())
            # Source _Unit115:007CA75C returns immediately on unchanged X.
            # This is a Qt plot-local pixel, NOT yet original TPaintBox.X.
            if not force and pixel==self._wave_mouse_pixel:
                return
            self._wave_mouse_pixel=pixel
            if rect.width()<=2 or not 0<pixel<rect.width():
                self.wave_line.setVisible(False)
                self.wave_hint.setText(
                    'CursorString: — (курсор вне временного графика; Qt-кандидат)')
                self.wave_cursor_primary.setText('Курсор: —')
                return
            if self.wave_envelope_code.currentData():
                self.wave_line.setVisible(False)
                self.statusBar().showMessage(
                    'Исходный курсор огибающей TQGrapher ещё не принят')
                self.wave_cursor_primary.setText('Курсор огибающей: —')
                return
            if self._wave_hover_window is None:
                # Do not re-read the complete ZIP and recompute GetSignal at
                # every mouse event; retain the exact existing sample candidate.
                self._wave_hover_window=prepare_waveform_hover_window(
                    self.session,self._ch(),start_s=self.wave_start.value(),
                    seconds=self.wave_seconds.value(),
                    mode=('ac' if self.wave_mode.currentIndex()==0 else 'acdc'),
                    display_order=self._signal_order())
            x=float(vb.mapSceneToView(pos).x())
            p=self._wave_hover_window.pick(x)
            self.wave_line.setPos(p['time_s'])
            self.wave_line.setVisible(True)
            self.wave_cursor_primary.setText(
                f"{p['original_sample_time_s']:.5g} с\n"
                f"{p['value_m_s2']:.5g} "
                + ('усл. ед.' if isinstance(self.session,DirectBinSession)
                   else 'расч. ед.'))
            self.wave_hint.setText(
                f"GetSignal[{p['display_index']}] → BIN[{p['index']}]"
                f" · физическое время BIN {p['original_sample_time_s']:.8f} c"
                f" · {p['value_m_s2']:.8g} "
                f"{'усл. ед.' if isinstance(self.session,DirectBinSession) else 'расч. ед.'} · {p['mode']}"
                ' · MouseMove IDR-кандидат; координаты оригинального TQGrapher не сверены')
        except (OSError,KeyError,TypeError,ValueError,RuntimeError) as exc:
            self.statusBar().showMessage(str(exc))

    def _spec_click(self,event):
        if event.button()==Qt.LeftButton:
            self._spec_at_scene_pos(event.scenePos(),force=True)

    def _spec_mouse_move(self,scene_pos):
        """Original _Unit128:0084C918 forwards mouse X to UpdateCursor."""
        self._spec_at_scene_pos(scene_pos,force=False)

    def _spec_at_scene_pos(self,pos,*,force=False):
        if ((self.session is None and self._spectrum_reference is None)
                or self._full_spectrum is None or not isinstance(pos,QPointF)):
            return
        try:
            vb=self.spec_plot.getViewBox()
            rect=vb.sceneBoundingRect()
            pixel_native=math.trunc(pos.x()-rect.left())
            # Only X is relevant to original 007CA811..007CA832; Y is ignored.
            if not force and pixel_native==self._spec_mouse_pixel:
                return
            self._spec_mouse_pixel=pixel_native
            if rect.width()<=2 or not 0<pixel_native<rect.width():
                # Original erases previous X and each active series' Y line
                # and clears CursorString when CursorPos is out of bounds.
                if self.spec_line:self.spec_line.setVisible(False)
                if self.spec_hline:self.spec_hline.setVisible(False)
                if getattr(self,'spec_xor_crosshair',None):
                    self.spec_xor_crosshair.clear_cursor()
                self._spec_last_cursor=None
                self.spec_hint.setText(
                    'CursorString: — (курсор вне области графика; original IDR candidate)')
                self.spec_cursor_primary.setText('Курсор: —')
                return
            width=float(rect.width())
            pixel=float(pixel_native)
            mid=rect.center().y()
            f_left=float(vb.mapSceneToView(QPointF(rect.left(),mid)).x())
            f_right=float(vb.mapSceneToView(QPointF(rect.right(),mid)).x())
            df=float(self._full_spectrum['df_hz'])
            x_start=float(self._full_spectrum['frequency_hz'][0])
            # Qt view has its own pixel origin. Convert to original source
            # pixel-to-bin affine map, then let the IDR cursor pick the peak.
            geom=CursorGeometry(
                pixel_left=0.,pixel_right=width,
                stoi_m=(f_right-f_left)/(width*df),
                stoi_c=(f_left-x_start)/df,
                x_start=x_start,x_scale=df,y_scale=1.,
                # Native 007CAB94 uses independent itosM/itosC; these
                # numbers are inferred from Qt's view and are NOT the real
                # Delphi pixel rectangle.
                itos_m=width*df/(f_right-f_left),
                itos_c=(x_start-f_left)*width/(f_right-f_left))
            found=cursor_from_spectrum(
                self._full_spectrum,pixel,geom,
                precise=self.spec_precise.isChecked(),
                averaging=(1 if self.spec_avg.currentIndex()==0 else 3))
            self.spec_line.setPos(found['frequency_hz'])
            self.spec_line.setVisible(True)
            raw_y=float(self._full_spectrum['amplitude'][found['selected_bin']])
            # 007CA9BA..9D3 uses the signed selected raw Y for the drawn line.
            # 007CA9F3..AAE5 computes a DIFFERENT numeric label for averaging=3.
            # Plot uses Qt view coordinates; exact original Delphi pixel parity unknown.
            self.spec_hline.setPos(raw_y)
            self.spec_hline.setVisible(True)
            self.spec_xor_crosshair.set_cursor(found['frequency_hz'],raw_y)
            self._spec_last_cursor=found
            y_name=('дБ' if found['mode']==0 else
                    ('усл. ед.' if isinstance(self.session,DirectBinSession)
                     else ('','м/с²','мм/с','мкм')[found['mode']]))
            cursor_unit=('усл. ед.' if isinstance(self.session,DirectBinSession)
                         and found['mode']!=0 else found['unit'])
            cursor=cursor_string_candidate(
                found['x_value'],found['display_y'],
                x_name='Гц',y_name=y_name,decimal_separator=',')
            self.spec_cursor_primary.setText(
                cursor['x_text']+'\n'+cursor['y_texts'][0])
            self.spec_hint.setText(
                f"IDR pixel {int(pixel)} · bins [{found['pixel_bin_first']}.."
                f"{found['pixel_bin_last']}] → пик FFT[{found['selected_bin']}]"
                f" · {found['frequency_hz']:.6g} Гц · {found['display_y']:.7g} {cursor_unit}"
                f" · avg={found['averaging']} (без /N)"
                f" · {found['fft_backend']} · кандидат TQGrapher"
                f" · snap={found['snapped_pixel_original_int_candidate']} px (Qt-геометрия)"
                f"\nГоризонталь = raw FFT[{found['selected_bin']}]={raw_y:.8g} {cursor_unit}"
                ' · подпись может отличаться из-за усреднения; пиксели Delphi НЕ приняты'
                f"\nCursorString IDR-кандидат (не Delphi RTL):\n{cursor['text']}")
        except (OSError,KeyError,TypeError,ValueError,OverflowError) as e:
            self.statusBar().showMessage(str(e))

    def _run_narrowband(self):
        """Private original IDR candidate; never a substitute for DSP AUX4700."""
        if not self.session:return
        try:
            n_fft=int(self.spec_n.currentText())
            start=None if self.spec_last.isChecked() else self.wave_start.value()
            result=self.session.narrowband(
                self._ch(),self.narrow_frequency.value(),n_fft=n_fft,
                start_s=start,get_noise_peak=self.narrow_noise.isChecked(),
                backend=self._fft_backend(),f_range=self.spec_f_range.value(),
                input_domain=self.spec_input_domain.currentData())
            label=(f"IDR узкополосный (не приборный DSP) · {result['center_bin']} ±"
                  f"{result['radius_bins']} FFT-бин · значение {result['output_value']:.8g}"
                  f" (FRange={result['f_range_used']:.6g}, "
                  f"{result['input_domain']}, кандидат; оригинал НЕ проверен)")
            if result['noise_peak_enabled']:
                label+=(f"\nШумовой пик {result['output_peak_frequency_hz']:.7g} Гц ·"
                       f" {result['output_peak_y']:.7g},"
                       f" исключены FFT-бин(ы) {result['noise_excluded_first_bin']}.."
                       f"{result['noise_excluded_last_bin']}")
            self.narrow_result.setText(label+"\nЧисленный паритет Delphi ещё не доказан")
        except (OSError,KeyError,TypeError,ValueError,OverflowError) as exc:
            self.narrow_result.setText('Узкополосный расчёт отклонён: '+str(exc))
            self.statusBar().showMessage('Отклонено: '+str(exc))

    def _collect_canvas_geometry_candidate(self):
        """Measure actual Qt ViewBox coordinates; model Delphi separately."""
        if self._full_spectrum is None:
            raise ValueError('Текущий график ещё не построен')
        view=self.spec_plot.viewport()
        fm=view.fontMetrics()
        xr,yr=self.spec_plot.getViewBox().viewRange()
        d=source_paintbox_registration(
            pixel_width=int(view.width()),pixel_height=int(view.height()),
            zero_text_width=int(fm.horizontalAdvance('0')),
            six_decimals_text_width=int(fm.horizontalAdvance('0.000000')),
            zero_text_height=int(fm.height()),
            x_name_present=True,y_name_present=True,
            scr_left=float(xr[0]),scr_width=float(xr[1]-xr[0]),
            scr_bottom=float(yr[0]),scr_height=float(yr[1]-yr[0]),
            series_x_start=0.,series_x_scale=float(self._full_spectrum['df_hz']))
        # Geometry of the CURRENT PySide6 ViewBox in the viewport's logical
        # pixels. This is independently measured Qt geometry, NOT the
        # source-derived Delphi PixelRect above or physical screenshot px.
        scene=self.spec_plot.getViewBox().sceneBoundingRect()
        local_tl=self.spec_plot.mapFromScene(scene.topLeft())
        local_br=self.spec_plot.mapFromScene(scene.bottomRight())
        screen_origin=view.mapToGlobal(QPoint(0,0))
        d['qt_measured_runtime_geometry']=describe_qt_viewport_geometry(
            viewport_width=int(view.width()),
            viewport_height=int(view.height()),
            plot_left=float(local_tl.x()),plot_top=float(local_tl.y()),
            plot_right=float(local_br.x()),plot_bottom=float(local_br.y()),
            viewport_global_left=float(screen_origin.x()),
            viewport_global_top=float(screen_origin.y()),
            device_pixel_ratio=float(view.devicePixelRatioF()),
            logical_dpi_x=int(view.logicalDpiX()),
            logical_dpi_y=int(view.logicalDpiY()),
            research_dock_visible=bool(self.spec_inspector.isVisible()))
        # These metrics are observed Qt, not Delphi font or GDI pixels.
        d['qt_viewport_device_pixel_ratio']=float(view.devicePixelRatioF())
        d['qt_viewport_logical_dpi_x']=int(view.logicalDpiX())
        d['qt_viewport_logical_dpi_y']=int(view.logicalDpiY())
        d['qt_font_family_candidate']=view.font().family()
        d['dfm_design_form_font_family']=DFM_DESIGN_FONT_FAMILY
        d['dfm_design_form_font_height']=DFM_DESIGN_FONT_HEIGHT
        d['dfm_design_pixels_per_inch']=DFM_DESIGN_PIXELS_PER_INCH
        d['dfm_design_spectrum_paintbox_size']=PAINTBOX_DIMENSIONS['spectrum']
        d['original_dfm_runtime_canvas_font_verified']=False
        # This source-derived affine is kept ONLY as a candidate.
        bridge=QtPaintBoxBridge(
            source_canvas=d,
            qt_scene_left=float(scene.left()),qt_scene_right=float(scene.right()),
            qt_scene_top=float(scene.top()),qt_scene_bottom=float(scene.bottom()),
            qt_device_pixel_ratio=d['qt_viewport_device_pixel_ratio'])
        d['qt_to_tpaintbox_bridge_candidate']=bridge.describe()
        d['qt_scene_plot_rect_source']='OBSERVED_QT_VIEWBOX_NOT_ORIGINAL_DELPHI'
        self._spec_canvas_geometry_preview=d
        return d

    def _show_canvas_geometry_candidate(self):
        """Show observed Qt geometry separately from source-derived model."""
        if self._full_spectrum is None:return
        try:
            d=self._collect_canvas_geometry_candidate()
            observed=d['qt_measured_runtime_geometry']
            plot=observed['qt_plot_bounds_in_viewport_logical']
            device=observed['qt_plot_size_nominal_device_pixels_if_uniform_dpr']
            QMessageBox.information(
                self,'TQGrapher Canvas — только исследовательская геометрия',
                f"ФАКТИЧЕСКИЙ Qt viewport (лог.): "
                f"{observed['qt_viewport_size_logical']['width']} × "
                f"{observed['qt_viewport_size_logical']['height']}; "
                f"DPR={observed['qt_device_pixel_ratio_observed']:.3g}\n"
                f"Исследовательская сетка TQGrapher: "
                f"{'ВКЛ (10×10)' if self._spec_source_grid_applied else 'ВЫКЛ (авто Qt)'}; "
                f"TCo2Draw: исходные линии {GRID_LINE_HEX}, "
                f"фон {BACKGROUND_HEX}, software bitmap; "
                "не GDI Pen и не пиксельный Qt паритет\n"
                f"ФАКТИЧЕСКАЯ Qt ViewBox (в viewport лог.): "
                f"L{plot['left']:.0f} R{plot['right']:.0f} "
                f"T{plot['top']:.0f} B{plot['bottom']:.0f}; "
                f"док открыт={observed['research_dock_visible']}\n"
                f"Условный device-размер по DPR: "
                f"{device['width']:.1f} × {device['height']:.1f}; "
                "НЕ физическая PixelRect исходной Delphi\n"
                f"МОДЕЛЬ TQGrapher на Qt-viewport: "
                f"{d['canvas_width']} × {d['canvas_height']} (лог. Qt)\n"
                f"Margin по оригиналу: min(W/53,H/30)={d['margin_before_tqgrapher_minimum']}"
                f" → после минимума 10: {d['effective_source_margin']} px\n"
                f"МОДЕЛЬ PixelRect (не оригинал!): L={d['pixel_left']}, "
                f"R={d['pixel_right']}, T={d['pixel_top']}, B={d['pixel_bottom']}\n"
                f"itosM={d['itos_m']:.9g}, itosC={d['itos_c']:.9g}\n"
                f"stoiM={d['stoi_m']:.9g}, stoiC={d['stoi_c']:.9g}\n"
                f"ytosM={d['ytos_m']:.9g}, ytosC={d['ytos_c']:.9g}\n"
                f"Scrollbars оригинал/TPaintBox: H.Left={d['spectrum_horizontal_scroll_left']},"
                f" H.Width={d['spectrum_horizontal_scroll_width']};"
                f" V.Top={d['spectrum_vertical_scroll_top']},"
                f" V.Height={d['spectrum_vertical_scroll_height']}\n"
                f"Qt Font={d['qt_font_family_candidate']}, DPR={d['qt_viewport_device_pixel_ratio']:.3g},"
                f" logical DPI={d['qt_viewport_logical_dpi_x']}×{d['qt_viewport_logical_dpi_y']}\n"
                f"DFM design-time: {d['dfm_design_form_font_family']}"
                f" Height={d['dfm_design_form_font_height']},"
                f" PPI={d['dfm_design_pixels_per_inch']},"
                f" pbSpectrum={d['dfm_design_spectrum_paintbox_size']}"
                " (НЕ текущий исходный Canvas)\n"
                "Qt→TPaintBox affine-кандидат: "
                f"scaleX={d['qt_to_tpaintbox_bridge_candidate']['qt_scene_x_to_native_x_scale']:.9g}, "
                f"scaleY={d['qt_to_tpaintbox_bridge_candidate']['qt_scene_y_to_native_y_scale']:.9g}; "
                "DPR не применяется к исходным пикселям без измерения.\n"
                "ВНИМАНИЕ: размеры текста получены из Qt, не оригинального TPaintBox.Canvas. "
                "Это НЕ фактический прямоугольник оригинальной MVKView.\n"
                "Для pixel-to-pixel приёмки требуются метрики Delphi TCanvas "
                "и одинаковый размер окна.")
        except (ValueError,TypeError,KeyError,OverflowError) as exc:
            QMessageBox.warning(self,'Геометрия Canvas не принята',str(exc))

    def _compare_original_copy(self):
        """Offline 3-field numeric+text QA, no original export or remote sync."""
        if self._spectrum_summary is None:return
        filename,_=QFileDialog.getOpenFileName(
            self,'Выберите локальный TXT — Copy из оригинальной MVKView',
            '','Text (*.txt)')
        if not filename:return
        try:
            original=read_operator_triplet_file(
                Path(filename),separator='\t',decimal_separator=',',
                encoding='utf-8-sig')
            report=compare_operator_triplet(
                self._spectrum_summary,original,
                abs_tolerance=1e-5,rel_tolerance=.01,
                operator_confirmed_same_window=False)
            status=('ЧИСЛЕННЫЕ ЗНАЧЕНИЯ В ЗАДАННОМ ДОПУСКЕ'
                    if report['within_supplied_tolerances']
                    else 'ЧИСЛЕННЫЕ ЗНАЧЕНИЯ НЕ СОВПАЛИ')
            display=('да' if report['candidate_display_text_equal']
                     else 'нет')
            diffs=report['absolute_errors']
            QMessageBox.information(
                self,'Локальная сверка с оригинальной MVKView — только кандидат',
                status+'\n'
                f"Текст 3 полей совпал: {display} (Delphi FormatFloat ещё не принят)\n"
                f"|Δ среднего|={diffs['output_mean']:.8g}\n"
                f"|Δ частоты|={diffs['output_peak_frequency_hz']:.8g} Гц\n"
                f"|Δ амплитуды|={diffs['output_peak_y']:.8g}\n"
                f"SHA-256 оригинального TXT: {report['reference_sha256']}\n"
                'Окно, FRange и исходная программа не аттестованы. '
                'Полный численный и визуальный паритет НЕ доказан.')
        except (KeyError,OSError,ValueError,UnicodeError,TypeError) as exc:
            QMessageBox.warning(self,'Сравнение оригинальной MVKView отклонено',str(exc))

    def _copy_spec_summary(self):
        """Source-confirmed 3-column tab structure; formatter still CANDIDATE."""
        if self._spectrum_summary is None:return
        try:
            text=spectrum_triplet_text(self._spectrum_summary,decimal_separator=',')
            if isinstance(self.session,DirectBinSession):
                confirmed=QMessageBox.question(
                    self,'Некалиброванные значения BIN/TSXML',
                    'Физическая калибровка этого BIN не подтверждена. '
                    'Копировать локальные исследовательские значения '
                    'с предупреждением об условных единицах?',
                    QMessageBox.Yes | QMessageBox.No,QMessageBox.No)
                if confirmed!=QMessageBox.Yes:
                    return
                # Do not silently copy a Delphi-looking three-number line
                # as if it were certified physical measurements.
                text='НЕ КАЛИБРОВАНО · условные единицы · локальный FFT\n'+text
            QApplication.clipboard().setText(text)
            self.statusBar().showMessage(
                'Скопирован исследовательский спектр · '
                'прямой BIN без калибровки' if isinstance(self.session,DirectBinSession)
                else 'Скопированы 3 расчётных значения (не приборный DSP)')
        except (KeyError,TypeError,ValueError) as exc:
            self.statusBar().showMessage('Ошибка Copy candidate: '+str(exc))

    def _save_spec_summary(self):
        """Explicit user-selected local CSV, never silently overwrite vendor."""
        if self._spectrum_summary is None:return
        filename,_=QFileDialog.getSaveFileName(
            self,'Сохранить исследовательский CSV (не формат оригинальной MVKView)',
            'MVK_COMPATIBLE_SPEC_CANDIDATE.csv','CSV (*.csv)')
        if not filename:return
        try:
            direct=isinstance(self.session,DirectBinSession)
            if direct:
                confirmed=QMessageBox.question(
                    self,'Сохранение некалиброванного спектра',
                    'Будет сохранён отдельный исследовательский CSV с явным '
                    'заголовком «НЕ КАЛИБРОВАНО». Это не приборный DSP. Продолжить?',
                    QMessageBox.Yes | QMessageBox.No,QMessageBox.No)
                if confirmed!=QMessageBox.Yes:
                    return
            report=append_research_summary_csv(
                filename,self._spectrum_summary,uncalibrated=direct)
            self.statusBar().showMessage(
                f"Сохранены 3 локальных IDR-кандидата: {report['path']} (Delphi parity НЕ доказан)")
        except (OSError,UnicodeError,KeyError,TypeError,ValueError) as exc:
            QMessageBox.warning(self,'Локальный CSV не сохранён',str(exc))

    def compare_fft(self):
        if not self.session:return
        try:
            start=None if self.spec_last.isChecked() else self.wave_start.value()
            d=self.session.compare_fft_backends(self._ch(),int(self.spec_n.currentText()),
                                                 self.spec_mode.currentIndex(),start,
                                                 f_range=self.spec_f_range.value())
            QMessageBox.information(self,'Сравнение двух расчётов приложения',
                f"Численный паритет с оригинальным Delphi НЕ доказан.\n"
                f"IDR float32 vs NumPy, FFT N={d['n_fft']}, режим {d['mode']}\n"
                f"Вычтенное среднее: {d['window_mean_m_s2']:.8g} м/с²\n"
                f"Максимальная разница: {d['max_absolute_difference']:.8g}\n"
                f"Относительно основного пика: {100*d['relative_difference_at_reference_peak']:.6g}%")
        except (OSError,KeyError,ValueError) as exc:self._error(exc)

    def _error(self,exc):
        self.statusBar().showMessage('Ошибка: '+str(exc))
        QMessageBox.warning(self,'Ошибка чтения архива',str(exc))


    def closeEvent(self,event):
        if self._native_dialog is not None and self._native_dialog.is_busy():
            QMessageBox.warning(self,'Запись ещё выполняется',
                'Сначала завершите Native R6.1 и дождитесь проверенного экспорта. '
                'Принудительное завершение через закрытие программы не допускается.')
            event.ignore()
            return
        super().closeEvent(event)


def run():
    app=QApplication.instance() or QApplication([])
    app.setApplicationName('ТПО МВК')
    win=MainWindow()
    win.show()
    return app.exec()
