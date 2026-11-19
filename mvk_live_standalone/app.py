"""Independent Qt spectrum application reading the sole Native R6.1 receiver.

No network socket is created by this UI. Native remains the single owner of the
TCP/10230 connection and publishes SHA-verified, calibrated float32 previews.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path
import hashlib
import ipaddress
import os
import sqlite3
import math
import tempfile
import time
import sys
from datetime import datetime, timezone

import numpy as np
from PySide6 import QtCore, QtWidgets
import pyqtgraph as pg

from mvk_compatible.core.native_r6_live_status import load_capture_live_status
from mvk_compatible.core.native_r6_live_preview import load_live_preview
from .spectrum import (
    FFT_SIZES, KINDS, PRESET_BANDS, Spectrum,
    calculate_spectrum, plot_values, y_axis_label, db_reference_text, db_reference,
)
from .live_ring import VerifiedLiveRing
from .live_ipc import discover_local_ipc, IPCNotReady, IPCPreview, IPCChannel, DOMAIN
from .original_dsp import read_original_dsp_bands
from .frange import original_applied_frange
from .octave_filters import (FAMILIES, nominal_centres, preset_band,
                             preset_description, octave_rss_from_thirds,
                             ORIGINAL_MVK_MENU)
from .spectrum_controls import (VIEW_MODES, FILTER_CHOICES, X_LIMITS_HZ,
                                view_settings, x_limit_hz, y_height_options,
                                visible_y_range)
from .rotation import estimate_rotation_from_velocity
from .pipeline import analyze_live, AnalysisResult
from .kurtogram import KurtogramResult, compute_fast_kurtogram
from .advanced import (envelope_fault_lines, stft_vibration,
                       cwt_morlet_vibration, real_cepstrum,
                       gear_mesh_markers, indicative_iso10816_zone)
from .recordings import save_snapshot, load_snapshot, save_spectrum_csv
from .ethernet import discover_single_wired_ethernet, WiredEthernet
from .measurement_history import MeasurementHistory, MAX_IMPORT_ROWS
from .history_widgets import HistoryWorkspaces
from .time_controls import (TIME_WINDOWS_S, Y_ABSOLUTE_LIMITS_M_S2,
                            TIME_FILTERS, time_filter_waveform,
                            signed_time_limits, display_time_stats)
from .graph_policies import spectrum_x_limits
from .modern_shell import install_modern_shell, open_archive_window, open_advanced_window
from .vibration import (
    VibrationView, analyze_vibration, vibration_plot_values,
    vibration_y_label, time_features, bearing_frequency_markers,
)

MAX_CAPTURE_MB = 2048


class LiveWindow(QtWidgets.QMainWindow):
    def __init__(self, capture_root: Path | None = None,
                 archive_root: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("MVK Live · Независимый анализатор спектра")
        self.resize(1380, 870)
        self._capture_root = capture_root
        self._archive_temp = None
        if archive_root is None:
            configured=os.environ.get("MVK_LIVE_ARCHIVE_DIR","")
            if configured:
                archive_root=Path(configured)
            elif os.environ.get("QT_QPA_PLATFORM","").lower()=="offscreen":
                # Each headless window is isolated; tests never import the
                # operator's local history or quietly populate their archive.
                self._archive_temp=tempfile.TemporaryDirectory(
                    prefix="mvk-live-history-test-")
                archive_root=Path(self._archive_temp.name)
            else:
                documents=QtCore.QStandardPaths.writableLocation(
                    QtCore.QStandardPaths.StandardLocation.DocumentsLocation)
                archive_root=Path(documents or str(Path.home()/"Documents"))/"MVK_Live_Archive"
        self._archive=MeasurementHistory(archive_root)
        self._archive_jobs=[]
        self._archive_dirty=False
        self._active_ip = None
        self._local_ip = None
        self._ethernet_detected: WiredEthernet | None = None
        self._ethernet_manual_override = False
        self._ethernet_detection_started = False
        self._ethernet_future: Future | None = None
        self._ethernet_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="MVK-Ethernet-Discovery")
        self._last_stamp = None
        self._preview = None
        self._gui_ring = VerifiedLiveRing()
        self._last_submitted_key = None
        self._last_status = None
        self._spectrum: VibrationView | None = None
        self._bearing_spectrum: VibrationView | None = None  # independent pinned source
        self._last_fft_submit=0.0
        self._waterfall_rows=[]
        self._waterfall_key=None
        self._trend_points=[]
        self._trend_key=None
        self._marker_lines=[]
        self._freeze_samples=None
        self._freeze_rate=None
        self._freeze_channel=None
        self._freeze_session=None
        self._freeze_end=None
        self._speed_candidate=None
        self._speed_future=None
        self._rpm_source="MANUAL"
        self._setting_rpm_from_candidate=False
        self._last_result: AnalysisResult | None=None
        self._extra_future=None
        self._extra_kind=None
        self._kurt_future=None
        self._kurt_result: KurtogramResult | None=None
        self._kurt_selected: tuple[int,int] | None=None
        self._kurt_adc: int | None=None
        self._kurt_session: str | None=None
        self._kurt_frozen: bool | None=None
        self._kurt_rx_key=None
        self._extra_executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix="MVK-advanced")
        self._future: Future | None = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="MVK-spectrum")
        self._ipc_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="MVK-local-IPC")
        self._ipc_client = None
        self._ipc_future: Future | None = None
        self._ipc_channel: int | None = None
        self._last_ipc_ok = None
        self._job_settings = None
        self._generation = 0
        # A MANUAL spectrum axis must survive every new verified FFT frame.
        self._manual_spec_axes = None
        self._native = QtCore.QProcess(self)
        self._native.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self._native.finished.connect(self._native_finished)

        pg.setConfigOptions(antialias=False)
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        main = QtWidgets.QVBoxLayout(central)
        panel = QtWidgets.QGridLayout()
        main.addLayout(panel)

        self.device_ip = QtWidgets.QLineEdit()
        self.device_ip.setPlaceholderText("IP прибора МВК01")
        self.local_ip = QtWidgets.QLineEdit()
        self.local_ip.setPlaceholderText("IPv4 Ethernet · определяется автоматически")
        self.local_ip.textEdited.connect(self._on_manual_ethernet_address)
        self.exe_path = QtWidgets.QLineEdit()
        self.exe_path.setPlaceholderText("Путь к проверенному MVK_Native_R6_1...exe")
        self.exe_sha = QtWidgets.QLineEdit()
        self.exe_sha.setPlaceholderText("Файл с SHA256 бинарного Native")
        # PyInstaller one-folder distribution includes the exact Go binary
        # built in this branch and its hash. Operator approval still applies.
        bundle=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parents[1]))
        exe=bundle/"mvk_native"/"MVK_Native_R6_1_LiveIPC_Windows_x64.exe"
        sums=bundle/"mvk_native"/"NATIVE_SHA256SUMS.txt"
        if exe.is_file() and sums.is_file():
            self.exe_path.setText(str(exe))
            self.exe_sha.setText(str(sums))
        panel.addWidget(QtWidgets.QLabel("МВК01 IP"), 0, 0)
        panel.addWidget(self.device_ip, 0, 1)
        panel.addWidget(QtWidgets.QLabel("Локальный IPv4"), 0, 2)
        panel.addWidget(self.local_ip, 0, 3)
        self.ethernet_info = QtWidgets.QLabel(
            "Ethernet: при открытии определится одна физическая проводная карта Windows")
        self.ethernet_info.setWordWrap(True)
        self.ethernet_refresh = QtWidgets.QPushButton("Обновить Ethernet")
        self.ethernet_refresh.clicked.connect(self._begin_ethernet_discovery)
        panel.addWidget(self.ethernet_info, 1, 0, 1, 4)
        panel.addWidget(self.ethernet_refresh, 1, 4)

        self.connect_button = QtWidgets.QPushButton("Подключить и измерять")
        self.connect_button.clicked.connect(self.start_native)
        self.stop_button = QtWidgets.QPushButton("Остановить")
        self.stop_button.clicked.connect(self.stop_native)
        self.stop_button.setEnabled(False)
        panel.addWidget(self.connect_button, 0, 4)
        panel.addWidget(self.stop_button, 0, 5, 2, 1)

        self.spectrum_controls_widget=QtWidgets.QWidget()
        operator = QtWidgets.QGridLayout(self.spectrum_controls_widget)
        operator.setContentsMargins(2,2,2,2)
        self.advanced_toggle=QtWidgets.QPushButton("Дополнительные расчёты и настройки ▸")
        self.advanced_toggle.setCheckable(True)
        self.advanced_panel=QtWidgets.QWidget()
        self.advanced_layout=QtWidgets.QVBoxLayout(self.advanced_panel)
        self.advanced_layout.setContentsMargins(0,0,0,0)
        self.advanced_panel.setVisible(False)
        self.advanced_toggle.toggled.connect(self._toggle_advanced)
        opts = QtWidgets.QGridLayout()
        self.advanced_layout.addLayout(opts)
        self.adc = QtWidgets.QComboBox()
        for i in range(8):
            self.adc.addItem(f"АЦП {i+1}", i+1)
        self.kind = QtWidgets.QComboBox()
        for key,(name,unit) in KINDS.items():
            self.kind.addItem(f"{name} ({unit})", key)
        self.analysis=QtWidgets.QComboBox()
        for name,key in [
            ("FFT · амплитуда СКЗ","fft"),
            ("PSD Уэлча · мощность/Гц","welch"),
            ("ASD Уэлча · амплитуда/√Гц","asd"),
            ("1/3 октавы · СКЗ полосы","third_octave"),
            ("Спектр огибающей · Hilbert","envelope"),
        ]:
            self.analysis.addItem(name,key)
        self.yscale = QtWidgets.QComboBox()
        for txt,key in [("Линейная","linear"),("В децибелах (дБ)","db")]:
            self.yscale.addItem(txt,key)
        self.db_ref = QtWidgets.QComboBox()
        self.db_ref.addItem("ISO 1683 · 10⁻⁶ выбранной единицы", "iso")
        self.db_ref.addItem("Относительно 1 выбранной единицы", "unit")
        self.xscale = QtWidgets.QComboBox()
        for txt,key in [("Линейная","linear"),("Логарифмическая","log")]:
            self.xscale.addItem(txt,key)
        self.nfft = QtWidgets.QComboBox()
        for n in FFT_SIZES:
            self.nfft.addItem(f"FFT {n} · разрешение Fs/{n} Гц",n)
        self.nfft.setCurrentIndex(2)
        self.band = QtWidgets.QComboBox()
        for label,bounds in PRESET_BANDS.items():
            self.band.addItem(label,bounds)
        self.envelope_band=QtWidgets.QComboBox()
        for name,band in [
            ("500–1500 Гц",(500.0,1500.0)),
            ("1000–3000 Гц",(1000.0,3000.0)),
            ("2000–6000 Гц",(2000.0,6000.0)),
            ("4000–12000 Гц",(4000.0,12000.0)),
        ]:
            self.envelope_band.addItem(name,band)
        self.envelope_band.setCurrentIndex(1)
        self.envelope_band.addItem("Авто · Fast Kurtogram PySDKit", "auto")
        self.band.addItem("Свой диапазон", "custom")
        self.custom_low = QtWidgets.QDoubleSpinBox()
        self.custom_low.setRange(0.0,32768.0)
        self.custom_low.setDecimals(2)
        self.custom_low.setSuffix(" Гц")
        self.custom_low.setValue(10.0)
        self.custom_high = QtWidgets.QDoubleSpinBox()
        self.custom_high.setRange(0.0,32768.0)
        self.custom_high.setDecimals(2)
        self.custom_high.setSuffix(" Гц (0=Nyquist)")
        self.custom_high.setValue(1000.0)
        self.smooth = QtWidgets.QSpinBox()
        self.smooth.setRange(1,101)
        self.smooth.setSingleStep(2)
        self.smooth.setValue(1)
        # Four views replace separate type/Y/X choices on the main screen.
        # This is only a presentation/processing change; sample rate is
        # whatever MVK01 sent, and Native already applied device FRange once.
        self.spectrum_view=QtWidgets.QComboBox()
        for label,key,_,_ in VIEW_MODES:
            self.spectrum_view.addItem(label,key)
        self.filter_choice=QtWidgets.QComboBox()
        for label,key in FILTER_CHOICES:
            self.filter_choice.addItem(label,key)
        self.filter_center=QtWidgets.QComboBox()
        self.filter_center.setToolTip(
            "Готовые центральные частоты 1/1, 1/3 и 2 октавы; "
            "локальная фильтрация, не оригинальный приборный FIR.")
        self.filter_center.setVisible(False)
        self._filter_center_family=None
        self.filter_button=QtWidgets.QPushButton("Настроить фильтр…")
        self.filter_button.clicked.connect(self._edit_filter)
        self.x_limit_choice=QtWidgets.QComboBox()
        for fmax in X_LIMITS_HZ:
            self.x_limit_choice.addItem(f"{fmax:g} Гц",fmax)
        self.x_limit_choice.setCurrentIndex(self.x_limit_choice.findData(1000))
        self.y_height_choice=QtWidgets.QComboBox()
        self._rebuild_y_height()
        operator.addWidget(QtWidgets.QLabel("АЦП"),0,0)
        operator.addWidget(self.adc,0,1)
        operator.addWidget(QtWidgets.QLabel("Вид спектра"),0,2)
        operator.addWidget(self.spectrum_view,0,3)
        operator.addWidget(QtWidgets.QLabel("Фильтр"),0,4)
        operator.addWidget(self.filter_choice,0,5)
        operator.addWidget(self.filter_center,0,6)
        operator.addWidget(self.filter_button,0,7)
        operator.addWidget(QtWidgets.QLabel("Показывать частоты до"),1,0)
        operator.addWidget(self.x_limit_choice,1,1)
        operator.addWidget(QtWidgets.QLabel("Масштаб спектра"),1,2)
        operator.addWidget(self.y_height_choice,1,3)
        self.operator_info=QtWidgets.QLabel(
            "Без фильтра · частота в Гц · уровень в единицах выбранного спектра")
        self.operator_info.setWordWrap(True)
        operator.addWidget(self.operator_info,1,4,1,3)
        for idx,(label,widget) in enumerate([
            ("Доп. метод анализа",self.analysis),
            ("FFT, число отсчётов",self.nfft),
            ("Опора для дБ",self.db_ref),
            ("Сглаживание, бин",self.smooth),
        ]):
            row,col=divmod(idx,2)
            opts.addWidget(QtWidgets.QLabel(label),row,col*2)
            opts.addWidget(widget,row,col*2+1)
        self.envelope_label=QtWidgets.QLabel("Полоса ОГИБАЮЩЕЙ (только спец. анализ)")
        opts.addWidget(self.envelope_label,2,0)
        opts.addWidget(self.envelope_band,2,1)
        self.envelope_label.hide()
        self.envelope_band.hide()
        opts.addWidget(QtWidgets.QLabel("Проверенный Native .exe"),3,0)
        opts.addWidget(self.exe_path,3,1,1,3)
        opts.addWidget(QtWidgets.QLabel("Контроль SHA256"),4,0)
        opts.addWidget(self.exe_sha,4,1,1,3)
        opts2=QtWidgets.QGridLayout()
        self.advanced_layout.addLayout(opts2)
        self.notch=QtWidgets.QComboBox()
        self.notch.addItem("Откл.",None)
        self.notch.addItem("50 Гц",50.0)
        self.notch.addItem("60 Гц",60.0)
        self.rpm=QtWidgets.QDoubleSpinBox()
        self.rpm.setRange(0,200000)
        self.rpm.setDecimals(1)
        self.rpm.setSuffix(" об/мин")
        operator.addWidget(QtWidgets.QLabel("Обороты, вручную"),2,0)
        operator.addWidget(self.rpm,2,1)
        self.balls=QtWidgets.QSpinBox()
        self.balls.setRange(0,80)
        self.ball_diameter=QtWidgets.QDoubleSpinBox()
        self.ball_diameter.setRange(0,300)
        self.pitch_diameter=QtWidgets.QDoubleSpinBox()
        self.pitch_diameter.setRange(0,3000)
        self.contact_angle=QtWidgets.QDoubleSpinBox()
        self.contact_angle.setRange(0,90)
        self.contact_angle.setSuffix("°")
        for idx,(label,widget) in enumerate([
            ("Тел качения",self.balls),
            ("Диаметр тела, мм",self.ball_diameter),
            ("Делит. диаметр, мм",self.pitch_diameter),
            ("Угол контакта",self.contact_angle),
        ]):
            row,col=divmod(idx,4)
            opts2.addWidget(QtWidgets.QLabel(label),row,col*2)
            opts2.addWidget(widget,row,col*2+1)
        gears=QtWidgets.QHBoxLayout()
        self.advanced_layout.addLayout(gears)
        gears.addWidget(QtWidgets.QLabel("Редуктор: зубьев шестерни"))
        self.gear_teeth=QtWidgets.QSpinBox()
        self.gear_teeth.setRange(0,400)
        self.gear_teeth.setSpecialValueText("Не задано")
        self.gear_teeth.valueChanged.connect(self._update_markers)
        gears.addWidget(self.gear_teeth)
        self.severity_button=QtWidgets.QPushButton(
            "Оценка виброскорости (ISO 10816-3, справочно)")
        self.severity_button.clicked.connect(self._show_severity)
        gears.addWidget(self.severity_button)
        gears.addWidget(QtWidgets.QLabel(
            "Обороты: вручную или подтверждённая гипотеза по ВС; TACH отключён"))
        gears.addStretch(1)
        review=QtWidgets.QHBoxLayout()
        main.addLayout(review)
        self.freeze=QtWidgets.QPushButton("Заморозить графики")
        self.freeze.setCheckable(True)
        self.freeze.clicked.connect(self._toggle_freeze)
        review.addWidget(self.freeze)
        review.addWidget(QtWidgets.QLabel("История"))
        self.history=QtWidgets.QDoubleSpinBox()
        self.history.setRange(0,0)
        self.history.setSingleStep(.25)
        self.history.setSuffix(" с назад")
        self.history.valueChanged.connect(self._review_changed)
        review.addWidget(self.history)
        self.timebase=QtWidgets.QComboBox()
        for seconds in (.1,.25,.5,1.,2.,5.,10.,30.):
            self.timebase.addItem(f"{seconds:g} с",seconds)
        self.timebase.setCurrentIndex(3)
        self.timebase.currentIndexChanged.connect(self._review_changed)
        self.rpm_detect=QtWidgets.QPushButton("Предложить 1× из ВС")
        self.rpm_detect.clicked.connect(self._propose_rotation)
        self.advanced_layout.addWidget(self.rpm_detect)
        self.rpm_accept=QtWidgets.QPushButton("Применить 1×")
        self.rpm_accept.setEnabled(False)
        self.rpm_accept.clicked.connect(self._accept_rotation)
        self.advanced_layout.addWidget(self.rpm_accept)
        self.axis_button=QtWidgets.QPushButton("Пределы осей")
        self.axis_button.clicked.connect(self._edit_axes)
        self.advanced_layout.addWidget(self.axis_button)
        review.addStretch(1)
        storage=QtWidgets.QHBoxLayout()
        main.addLayout(storage)
        self.save_snapshot_button=QtWidgets.QPushButton("Сохранить окно (.npz)")
        self.save_snapshot_button.clicked.connect(self._save_snapshot)
        storage.addWidget(self.save_snapshot_button)
        self.open_snapshot_button=QtWidgets.QPushButton("Открыть запись (.npz)")
        self.open_snapshot_button.clicked.connect(self._open_snapshot)
        storage.addWidget(self.open_snapshot_button)
        self.csv_button=QtWidgets.QPushButton("Экспорт спектра (.csv)")
        self.csv_button.clicked.connect(self._export_csv)
        self.plot_png_button=QtWidgets.QPushButton("Сохранить график (.png)")
        self.plot_png_button.clicked.connect(self._export_plot_png)
        self.extra_mode=QtWidgets.QComboBox()
        self.extra_mode.addItem("STFT (частота–время)","stft")
        self.extra_mode.addItem("CWT Morlet (качественный)","cwt")
        self.extra_mode.addItem("Кепстр (кэфренция)","cepstrum")
        self.extra_button=QtWidgets.QPushButton("Рассчитать STFT")
        self.extra_button.clicked.connect(lambda: self._start_extra_mode("stft"))
        storage.addStretch(1)
        self.rotation_info=QtWidgets.QLabel("1×: вручную или предложение по ВС. Тахометр не используется.")
        self.advanced_layout.addWidget(self.rotation_info)
        self.status = QtWidgets.QLabel("Нет подтверждённого Live-потока")
        main.addWidget(self.status)
        self.quality = QtWidgets.QLabel("Показания AUX4700 не подменяются локальной FFT.")
        main.addWidget(self.quality)

        self.wave = pg.PlotWidget(title="Временной сигнал: откалиброванное виброускорение")
        self.wave.setLabel("left","ВУ · Виброускорение",units="м/с²")
        self.wave.setLabel("bottom","Время",units="с")
        self.wave.showGrid(x=True,y=True,alpha=0.2)
        self.wave_curve = self.wave.plot(pen=pg.mkPen("#27a8b2",width=1))
        # The time scope is a FIRST-CLASS page with its own X/Y/filter,
        # independent of the frequency-domain spectrum controls.
        self.wave_page=QtWidgets.QWidget()
        self.wave_layout=QtWidgets.QVBoxLayout(self.wave_page)
        self.wave_toolbar=QtWidgets.QHBoxLayout()
        self.wave_layout.addLayout(self.wave_toolbar)
        self.wave_toolbar.addWidget(QtWidgets.QLabel("Развёртка времени"))
        self.timebase.blockSignals(True)
        self.timebase.clear()
        for seconds in TIME_WINDOWS_S:
            label=f"{seconds*1000:g} мс" if seconds<1 else f"{seconds:g} с"
            self.timebase.addItem(label,seconds)
        self.timebase.setCurrentIndex(self.timebase.findData(1.0))
        self.timebase.blockSignals(False)
        self.wave_toolbar.addWidget(self.timebase)
        self.wave_toolbar.addWidget(QtWidgets.QLabel("Масштаб виброускорения"))
        self.time_y_width=QtWidgets.QComboBox()
        self.time_y_width.addItem("Авто",None)
        for value in Y_ABSOLUTE_LIMITS_M_S2:
            self.time_y_width.addItem(f"±{value:g} м/с²",value)
        self.wave_toolbar.addWidget(self.time_y_width)
        self.wave_toolbar.addWidget(QtWidgets.QLabel("Фильтр временного сигнала"))
        self.time_filter_choice=QtWidgets.QComboBox()
        for label,key in TIME_FILTERS:
            self.time_filter_choice.addItem(label,key)
        self.wave_toolbar.addWidget(self.time_filter_choice)
        self.time_filter_center=QtWidgets.QComboBox()
        self.time_filter_center.setVisible(False)
        self.time_filter_center.setToolTip(
            "Выбор готовой октавной полосы без ручного задания границ.")
        self._time_center_family=None
        self.wave_toolbar.addWidget(self.time_filter_center)
        self.time_filter_button=QtWidgets.QPushButton("Настроить…")
        self.time_filter_button.setEnabled(False)
        self.time_filter_button.clicked.connect(self._edit_time_filter)
        self.wave_toolbar.addWidget(self.time_filter_button)
        self.wave_toolbar.addStretch(1)
        self.time_filter_low=10.0
        self.time_filter_high=1000.0
        self.wave_info=QtWidgets.QLabel(
            "Виброускорение после однократного FRange · время в мс/с · уровень в м/с² · без фильтра")
        self.wave_info.setWordWrap(True)
        self.wave_layout.addWidget(self.wave_info)
        self.wave_layout.addWidget(self.wave,stretch=1)
        self.wave_stats=QtWidgets.QLabel(
            "Временной сигнал: ожидание достоверных отсчётов АЦП")
        self.wave_layout.addWidget(self.wave_stats)
        self.time_filter_choice.currentIndexChanged.connect(self._time_filter_changed)
        self.time_filter_center.currentIndexChanged.connect(self._render_wave)
        self.time_y_width.currentIndexChanged.connect(self._render_wave)

        self.spec = pg.PlotWidget(title="Спектр FFT · расчёт MVK Live из АЦП (не DSP)")
        self.spec.setLabel("bottom","Частота",units="Гц")
        self.spec.showGrid(x=True,y=True,alpha=0.2)
        self.spec_curve = self.spec.plot(pen=pg.mkPen("#e09b48",width=1.2))
        self.cursor = pg.InfiniteLine(pos=100,movable=True,pen=pg.mkPen("#76838b",style=QtCore.Qt.DashLine))
        self.spec.addItem(self.cursor)
        self.cursor.sigPositionChanged.connect(self._cursor_text)
        self.views=QtWidgets.QTabWidget()
        self.spectrum_page=QtWidgets.QWidget()
        self.spectrum_layout=QtWidgets.QVBoxLayout(self.spectrum_page)
        self.spectrum_layout.addWidget(self.spectrum_controls_widget)
        self.spectrum_layout.addWidget(self.spec,stretch=1)
        spectrum_exports=QtWidgets.QHBoxLayout()
        spectrum_exports.addWidget(self.csv_button)
        spectrum_exports.addWidget(self.plot_png_button)
        spectrum_exports.addStretch(1)
        self.spectrum_layout.addLayout(spectrum_exports)
        self.spectrum_layout.addWidget(self.advanced_toggle)
        self.spectrum_layout.addWidget(self.advanced_panel)
        self.views.addTab(self.spectrum_page,"Спектр")
        self.views.addTab(self.wave_page,"Временной сигнал")
        self.extra_panel=QtWidgets.QWidget()
        self.extra_layout=QtWidgets.QVBoxLayout(self.extra_panel)
        self.extra_header=QtWidgets.QLabel(
            "Дополнительные измерения: каждый метод имеет отдельные "
            "настройки и сохраняет собственный график. "
            "Все результаты APP_DERIVED, исходный AUX4700 не изменяется.")
        self.extra_header.setWordWrap(True)
        extra_top=QtWidgets.QHBoxLayout()
        extra_top.addWidget(QtWidgets.QLabel("АЦП"))
        self.extra_adc=QtWidgets.QComboBox()
        for channel in range(1,9):
            self.extra_adc.addItem(f"АЦП {channel}",channel)
        self.extra_adc.setCurrentIndex(self.adc.currentIndex())
        self.extra_adc.currentIndexChanged.connect(
            self.adc.setCurrentIndex)
        self.adc.currentIndexChanged.connect(
            self.extra_adc.setCurrentIndex)
        extra_top.addWidget(self.extra_adc)
        extra_top.addWidget(self.extra_header,stretch=1)
        self.extra_layout.addLayout(extra_top)
        self.extra_pages=QtWidgets.QTabWidget()
        self.extra_layout.addWidget(self.extra_pages,stretch=1)
        self.waterfall=pg.PlotWidget(title="Водопад · последовательные APP_DERIVED спектры")
        self.waterfall.setLabel("bottom","Частота",units="Гц")
        self.waterfall.setLabel("left","Новые измеренные кадры",units=" ")
        self.waterfall_img=pg.ImageItem()
        self.waterfall.addItem(self.waterfall_img)
        self.waterfall_page=QtWidgets.QWidget()
        waterfall_layout=QtWidgets.QVBoxLayout(self.waterfall_page)
        waterfall_settings=QtWidgets.QHBoxLayout()
        waterfall_settings.addWidget(QtWidgets.QLabel("Кадров истории"))
        self.waterfall_max_frames=QtWidgets.QComboBox()
        for frames in (20,50,120,240):
            self.waterfall_max_frames.addItem(str(frames),frames)
        self.waterfall_max_frames.setCurrentIndex(
            self.waterfall_max_frames.findData(120))
        waterfall_settings.addWidget(self.waterfall_max_frames)
        waterfall_settings.addWidget(QtWidgets.QLabel(
            "Новый кадр только при новом RxPos АЦП, не от перерисовки"))
        waterfall_settings.addStretch(1)
        waterfall_layout.addLayout(waterfall_settings)
        waterfall_layout.addWidget(self.waterfall,stretch=1)
        self.extra_pages.addTab(self.waterfall_page,"Водопад")
        # Genuine PySDKit Fast Kurtogram: binary/ternary analytic FIR tree.
        # The heatmap is a new APP_DERIVED analytic tool, not MVK01 DSP.
        self.kurtogram_page=QtWidgets.QWidget()
        kurt_layout=QtWidgets.QVBoxLayout(self.kurtogram_page)
        kurt_controls=QtWidgets.QHBoxLayout()
        kurt_controls.addWidget(QtWidgets.QLabel("Окно кюртограммы"))
        self.kurtogram_window=QtWidgets.QComboBox()
        for count in (4096,8192,16384,32768):
            self.kurtogram_window.addItem(f"{count} отсчётов",count)
        self.kurtogram_window.setCurrentIndex(
            self.kurtogram_window.findData(8192))
        kurt_controls.addWidget(self.kurtogram_window)
        kurt_controls.addWidget(QtWidgets.QLabel("Уровни дерева"))
        self.kurtogram_levels=QtWidgets.QComboBox()
        for depth in (2,3,4,5,6):
            self.kurtogram_levels.addItem(str(depth),depth)
        self.kurtogram_levels.setCurrentIndex(
            self.kurtogram_levels.findData(4))
        kurt_controls.addWidget(self.kurtogram_levels)
        self.kurtogram_run=QtWidgets.QPushButton("Рассчитать Fast Kurtogram")
        self.kurtogram_run.clicked.connect(self._calculate_kurtogram)
        kurt_controls.addWidget(self.kurtogram_run)
        self.kurtogram_best=QtWidgets.QPushButton("Выбрать максимум")
        self.kurtogram_best.setEnabled(False)
        self.kurtogram_best.clicked.connect(self._select_kurt_best)
        kurt_controls.addWidget(self.kurtogram_best)
        self.kurtogram_apply=QtWidgets.QPushButton("Полоса → огибающая")
        self.kurtogram_apply.setEnabled(False)
        self.kurtogram_apply.clicked.connect(self._apply_kurt_band)
        kurt_controls.addWidget(self.kurtogram_apply)
        kurt_controls.addStretch(1)
        kurt_layout.addLayout(kurt_controls)
        self.kurtogram_plot=pg.PlotWidget(
            title="PySDKit Fast Kurtogram · ожидание реального АЦП")
        self.kurtogram_plot.setLabel("bottom","Центральная частота",units="Гц")
        self.kurtogram_plot.setLabel("left","Уровень разложения, k")
        # Antoni / PySDKit layout: level 0 at the TOP, deeper (narrower)
        # frequency bands towards the bottom.
        self.kurtogram_plot.getViewBox().invertY(True)
        self.kurtogram_plot.showGrid(x=False,y=False)
        self.kurtogram_img=pg.ImageItem()
        self.kurtogram_plot.addItem(self.kurtogram_img)
        self.kurtogram_marker=pg.ScatterPlotItem(
            size=12,pen=pg.mkPen("#ffffff",width=2),
            brush=pg.mkBrush("#222222"))
        self.kurtogram_plot.addItem(self.kurtogram_marker)
        self.kurtogram_colormap=pg.ColorMap(
            [0.,.25,.5,.75,1.],
            [(26,27,92),(41,88,150),(27,155,146),
             (249,191,58),(249,241,191)])
        self.kurtogram_bar=pg.ColorBarItem(
            values=(0.,5.),colorMap=self.kurtogram_colormap,
            label="Эксцесс спектрального куртозиса")
        self.kurtogram_bar.setImageItem(
            self.kurtogram_img,insert_in=self.kurtogram_plot.getPlotItem())
        self.kurtogram_plot.scene().sigMouseClicked.connect(
            self._kurtogram_clicked)
        kurt_layout.addWidget(self.kurtogram_plot,stretch=1)
        self.kurtogram_info=QtWidgets.QLabel(
            "Выберите окно и уровень дерева. Вычисляется Fast Kurtogram "
            "PySDKit (MIT), без команд в прибор и без повторного FRange. "
            "Тёплая область означает импульсность, не диагноз.")
        self.kurtogram_info.setWordWrap(True)
        kurt_layout.addWidget(self.kurtogram_info)
        self.extra_pages.addTab(self.kurtogram_page,"Кюртограмма")
        dsp_panel=QtWidgets.QWidget()
        dsp_layout=QtWidgets.QVBoxLayout(dsp_panel)
        adc_row=QtWidgets.QHBoxLayout()
        adc_row.addWidget(QtWidgets.QLabel("Расчётные данные АЦП"))
        self.dsp_adc=QtWidgets.QComboBox()
        for channel in range(1,9):
            self.dsp_adc.addItem(f"АЦП {channel}",channel)
        self.dsp_adc.setCurrentIndex(self.adc.currentIndex())
        adc_row.addWidget(self.dsp_adc)
        self.dsp_source_hint=QtWidgets.QLabel(
            "ORIGINAL AUX4700 отдельно от APP_DERIVED")
        adc_row.addWidget(self.dsp_source_hint,stretch=1)
        dsp_layout.addLayout(adc_row)
        self.dsp_pages=QtWidgets.QTabWidget(dsp_panel)
        dsp_rms_page=QtWidgets.QWidget()
        dsp_rms_layout=QtWidgets.QVBoxLayout(dsp_rms_page)
        bands_row=QtWidgets.QHBoxLayout()
        bands_row.addWidget(QtWidgets.QLabel("Частотные полосы"))
        self.dsp_band_mode=QtWidgets.QComboBox()
        self.dsp_band_mode.addItem("1/3 октавы · оригинальные 43 СКЗ","third")
        self.dsp_band_mode.addItem("1/1 октавы · сводка из 1/3 СКЗ","octave")
        bands_row.addWidget(self.dsp_band_mode)
        bands_row.addStretch(1)
        dsp_rms_layout.addLayout(bands_row)
        self.dsp_plot=pg.PlotWidget(title="АUX4700 · переданные прибором 43 третьоктавных СКЗ ВУ")
        self.dsp_plot.setLabel("bottom","Центр полосы",units="Гц")
        self.dsp_plot.setLabel("left","Виброускорение СКЗ",units="м/с²")
        self.dsp_plot.showGrid(x=True,y=True,alpha=.2)
        self.dsp_curve=self.dsp_plot.plot(pen=pg.mkPen("#6b8cbd",width=1.5),
                                          symbol="o",symbolSize=4)
        dsp_rms_layout.addWidget(self.dsp_plot,stretch=2)
        self.dsp_bands_table=QtWidgets.QTableWidget(0,2)
        self.dsp_bands_table.setHorizontalHeaderLabels(
            ["Центр полосы, Гц","ВУ СКЗ, м/с²"])
        self.dsp_bands_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.dsp_bands_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        dsp_rms_layout.addWidget(self.dsp_bands_table,stretch=1)
        self.dsp_band_trend_button=QtWidgets.QPushButton(
            "Тренд выделенной оригинальной 1/3-октавной полосы")
        self.dsp_band_trend_button.setToolTip(
            "Поиск сохранённых AUX4700 выбранного АЦП и частоты; "
            "локальные 1/1 сводки нельзя выдать за приборную полосу.")
        self.dsp_band_trend_button.clicked.connect(
            self._open_dsp_band_trend)
        dsp_rms_layout.addWidget(self.dsp_band_trend_button)
        self.dsp_band_note=QtWidgets.QLabel(
            "1/3: оригинальные 43 СКЗ AUX4700. "
            "1/1: APP_DERIVED RSS трёх исходных 1/3 полос; "
            "не самостоятельный оригинальный аппаратный фильтр.")
        self.dsp_band_note.setWordWrap(True)
        dsp_rms_layout.addWidget(self.dsp_band_note)
        self.dsp_band_mode.currentIndexChanged.connect(self._plot_dsp_bands)
        self.dsp_pages.addTab(dsp_rms_page,"Октавные полосы 1/3 · 1/1")
        dsp_extra_page=QtWidgets.QWidget()
        dsp_extra_layout=QtWidgets.QVBoxLayout(dsp_extra_page)
        dsp_controls=QtWidgets.QHBoxLayout()
        dsp_controls.addWidget(QtWidgets.QLabel("Исходный параметр"))
        self.dsp24_mode=QtWidgets.QComboBox()
        self.dsp24_mode.addItem("СКЗ · band_rms","band_rms")
        self.dsp24_mode.addItem("Пик · band_peak_equiv","band_peak_equiv")
        self.dsp24_mode.addItem("Размах / пик-пик · band_span_equiv","band_span_equiv")
        self.dsp24_mode.currentIndexChanged.connect(self._plot_dsp_24)
        dsp_controls.addWidget(self.dsp24_mode)
        dsp_controls.addStretch(1)
        dsp_extra_layout.addLayout(dsp_controls)
        self.dsp24_plot=pg.PlotWidget(title="24 оригинальные расчётные позиции · без предположений о частотах")
        self.dsp24_plot.setLabel("bottom","Номер исходной позиции (частота не подтверждена)")
        self.dsp24_plot.setLabel("left","Значение прибора (единицы уточняются)")
        self.dsp24_plot.showGrid(x=True,y=True,alpha=.2)
        self.dsp24_curve=self.dsp24_plot.plot(pen=pg.mkPen("#a070b5",width=1.3),
                                             symbol="o",symbolSize=4)
        dsp_extra_layout.addWidget(self.dsp24_plot,stretch=2)
        self.dsp24_table=QtWidgets.QTableWidget(24,4)
        self.dsp24_table.setHorizontalHeaderLabels([
            "Позиция (1–24)", "СКЗ / band_rms",
            "Пик / peak_equiv", "Размах / span_equiv"])
        self.dsp24_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.dsp24_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.dsp24_table.setAlternatingRowColors(True)
        dsp_extra_layout.addWidget(self.dsp24_table,stretch=2)
        self.dsp24_trend_button=QtWidgets.QPushButton(
            "Тренд выбранной позиции и параметра из AUX4700")
        self.dsp24_trend_button.clicked.connect(self._open_dsp_24_trend)
        dsp_extra_layout.addWidget(self.dsp24_trend_button)
        self.dsp24_note=QtWidgets.QLabel(
            "Частоты, физические единицы и точная трактовка peak/span для этих 24 позиций "
            "пока не подтверждены оригинальной схемой. Данные показаны без пересчёта.")
        self.dsp24_note.setWordWrap(True)
        dsp_extra_layout.addWidget(self.dsp24_note)
        self.dsp_pages.addTab(dsp_extra_page,"24 позиции · СКЗ / Пик / Размах")
        dsp_layout.addWidget(self.dsp_pages,stretch=1)
        self._dsp_last=None
        self.dsp_info=QtWidgets.QLabel("Данные AUX4700 от прибора ещё не получены")
        self.dsp_info.setWordWrap(True)
        dsp_layout.addWidget(self.dsp_info)
        self.views.addTab(dsp_panel,"Расчётные данные")
        self.calculated_page=dsp_panel
        self.trend_plot=pg.PlotWidget(title="Тренд · локальная СКЗ ускорения")
        self.trend_plot.setLabel("bottom","Время с начала сеанса",units="с")
        self.trend_plot.setLabel("left","Виброускорение СКЗ",units="м/с²")
        self.trend_line=self.trend_plot.plot(pen=pg.mkPen("#21a179",width=1.4))
        self.short_trend_page=QtWidgets.QWidget()
        short_trend_layout=QtWidgets.QVBoxLayout(self.short_trend_page)
        trend_settings=QtWidgets.QHBoxLayout()
        trend_settings.addWidget(QtWidgets.QLabel("Последних новых кадров"))
        self.trend_max_points=QtWidgets.QComboBox()
        for count in (30,60,120,240):
            self.trend_max_points.addItem(str(count),count)
        self.trend_max_points.setCurrentIndex(self.trend_max_points.findData(240))
        self.trend_max_points.currentIndexChanged.connect(
            self._redraw_short_trend)
        trend_settings.addWidget(self.trend_max_points)
        self.short_trend_info=QtWidgets.QLabel(
            "Локальная ВУ СКЗ · APP_DERIVED, только подтверждённые АЦП")
        trend_settings.addWidget(self.short_trend_info,stretch=1)
        short_trend_layout.addLayout(trend_settings)
        short_trend_layout.addWidget(self.trend_plot,stretch=1)
        self.extra_pages.addTab(self.short_trend_page,"Тренд СКЗ")
        # Independent workspaces instead of one plot overwritten by a
        # global STFT/CWT/Cepstrum combobox on every calculation.
        self.extra_method_pages={}
        self.extra_method_plots={}
        self.extra_method_images={}
        self.extra_method_lines={}
        self.extra_method_buttons={}
        self.extra_method_infos={}
        self.extra_method_windows={}
        for mode,label in (("stft","STFT"),("cwt","CWT Morlet"),
                           ("cepstrum","Кепстр")):
            page=QtWidgets.QWidget()
            layout=QtWidgets.QVBoxLayout(page)
            options=QtWidgets.QHBoxLayout()
            options.addWidget(QtWidgets.QLabel("Окно исходных отсчётов"))
            window=QtWidgets.QComboBox()
            for samples in (4096,8192,16384,32768):
                window.addItem(f"{samples} отсчётов",samples)
            window.setCurrentIndex(window.findData(8192))
            self.extra_method_windows[mode]=window
            options.addWidget(window)
            if mode=="stft":
                options.addWidget(QtWidgets.QLabel("STFT: отсчётов/сегмент"))
                self.stft_nperseg=QtWidgets.QComboBox()
                for nseg in (256,512,1024,2048,4096):
                    self.stft_nperseg.addItem(f"{nseg}",nseg)
                self.stft_nperseg.setCurrentIndex(
                    self.stft_nperseg.findData(1024))
                options.addWidget(self.stft_nperseg)
            elif mode=="cwt":
                options.addWidget(QtWidgets.QLabel("CWT: масштабов"))
                self.cwt_scales=QtWidgets.QComboBox()
                for count in (16,24,40,64):
                    self.cwt_scales.addItem(str(count),count)
                self.cwt_scales.setCurrentIndex(self.cwt_scales.findData(40))
                options.addWidget(self.cwt_scales)
                options.addWidget(QtWidgets.QLabel("Минимум, Гц"))
                self.cwt_min_hz=QtWidgets.QDoubleSpinBox()
                self.cwt_min_hz.setRange(2.,16000.)
                self.cwt_min_hz.setValue(10.)
                self.cwt_min_hz.setSuffix(" Гц")
                options.addWidget(self.cwt_min_hz)
            else:
                options.addWidget(QtWidgets.QLabel("Макс. кэфренция"))
                self.cepstrum_max_s=QtWidgets.QDoubleSpinBox()
                self.cepstrum_max_s.setRange(.001,1.)
                self.cepstrum_max_s.setDecimals(3)
                self.cepstrum_max_s.setValue(.1)
                self.cepstrum_max_s.setSuffix(" с")
                options.addWidget(self.cepstrum_max_s)
            button=(self.extra_button if mode=="stft" else
                    QtWidgets.QPushButton(f"Рассчитать {label}"))
            if mode!="stft":
                button.clicked.connect(
                    lambda checked=False,method=mode:
                    self._start_extra_mode(method))
            self.extra_method_buttons[mode]=button
            options.addWidget(button)
            options.addStretch(1)
            layout.addLayout(options)
            plot=pg.PlotWidget(title=f"{label} · ожидание исходного АЦП")
            plot.showGrid(x=True,y=True,alpha=.2)
            image=pg.ImageItem()
            plot.addItem(image)
            line=plot.plot(pen=pg.mkPen("#c05c91",width=1.1))
            layout.addWidget(plot,stretch=1)
            info=QtWidgets.QLabel(
                f"{label}: выберите параметры и нажмите «Рассчитать». "
                "Обработка только локального проверенного сигнала.")
            info.setWordWrap(True)
            layout.addWidget(info)
            self.extra_method_pages[mode]=page
            self.extra_method_plots[mode]=plot
            self.extra_method_images[mode]=image
            self.extra_method_lines[mode]=line
            self.extra_method_infos[mode]=info
            self.extra_pages.addTab(page,label)
        # Compatibility aliases for existing STFT integration tests.
        self.extra_plot=self.extra_method_plots["stft"]
        self.extra_image=self.extra_method_images["stft"]
        self.extra_line=self.extra_method_lines["stft"]
        self.views.addTab(self.extra_panel,"Доп. анализ")
        self.history_ui=HistoryWorkspaces(self._archive,self.adc,self)
        self.views.insertTab(3,self.history_ui.trend_page,"Тренды")
        self.views.insertTab(4,self.history_ui.compare_page,"Сравнение")
        self.history_ui.on_open_comparison=lambda: self.views.setCurrentWidget(
            self.history_ui.compare_page)
        self.history_ui.capture_requested.connect(self._archive_capture_window)
        self.history_ui.import_npz_requested.connect(self._archive_import_npz)
        self.history_ui.import_aux_requested.connect(self._archive_import_aux)
        self.views.currentChanged.connect(self._archive_tab_changed)
        self.history_ui.compare_info.setToolTip(
            "Локальный архив: "+str(self._archive.root))
        main.addWidget(self.views,stretch=3)
        self.metrics = QtWidgets.QLabel("Нет достоверных данных")
        self.derived_page=QtWidgets.QWidget()
        self.derived_layout=QtWidgets.QVBoxLayout(self.derived_page)
        self.derived_layout.addWidget(QtWidgets.QLabel(
            "ЛОКАЛЬНЫЕ APP_DERIVED · из уже калиброванных отсчётов АЦП, НЕ исходный DSP МВК01"))
        self.derived_layout.addWidget(self.metrics)
        self.features_label=QtWidgets.QLabel("Временные признаки: ожидание калиброванного канала")
        self.derived_layout.addWidget(self.features_label)
        self.frange_info=QtWidgets.QLabel(
            "FRange: ожидание начальной конфигурации МВК01. "
            "Графики используют уже откалиброванный Native BIN/IPC.")
        self.derived_layout.addWidget(self.frange_info)
        self.derived_layout.addStretch(1)
        self.local_values_table=QtWidgets.QTableWidget(10,3)
        self.local_values_table.setHorizontalHeaderLabels(
            ["Локальный показатель","Значение","Единица"])
        self.local_values_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.local_values_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.derived_layout.insertWidget(3,self.local_values_table,stretch=1)
        self.local_trend_metric_ids=(
            "time_rms","time_peak","time_pp","crest","kurtosis",
            "skew","impulse","shape","clearance","velocity_rms_10_1000")
        self.local_values_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.local_trend_button=QtWidgets.QPushButton(
            "Тренд выделенного локального показателя из сохранённых окон")
        self.local_trend_button.setToolTip(
            "Локальный тренд требует предварительно сохранить окна АЦП "
            "в архив NPZ; Live-обновления не подменяют измерения.")
        self.local_trend_button.clicked.connect(self._open_local_metric_trend)
        self.derived_layout.insertWidget(4,self.local_trend_button)
        self.dsp_pages.addTab(self.derived_page,"Показатели MVK Live")
        self.bearing_diagnostics=QtWidgets.QLabel(
            "Подшипники: введите 1× и геометрию; локальное SNR, без эталонных измерений")
        self.diagnostics_page=QtWidgets.QWidget()
        self.diagnostics_layout=QtWidgets.QVBoxLayout(self.diagnostics_page)
        self.diagnostics_layout.addWidget(QtWidgets.QLabel(
            "Подшипники · BPFO / BPFI / BSF / FTF, локальный SNR "
            "огибающей · без тахометра, внешнего эталона и диагноза"))
        bearing_form=QtWidgets.QFormLayout()
        self.bearing_rpm=QtWidgets.QDoubleSpinBox()
        self.bearing_rpm.setRange(0,200000)
        self.bearing_rpm.setSuffix(" об/мин")
        self.bearing_balls=QtWidgets.QSpinBox()
        self.bearing_balls.setRange(0,80)
        self.bearing_ball_diameter=QtWidgets.QDoubleSpinBox()
        self.bearing_ball_diameter.setRange(0,300)
        self.bearing_pitch_diameter=QtWidgets.QDoubleSpinBox()
        self.bearing_pitch_diameter.setRange(0,3000)
        self.bearing_contact_angle=QtWidgets.QDoubleSpinBox()
        self.bearing_contact_angle.setRange(0,90)
        self.bearing_contact_angle.setSuffix("°")
        for label,local,original in (
            ("Частота вращения (ручная/подтверждённая 1×)",
             self.bearing_rpm,self.rpm),
            ("Тел качения",self.bearing_balls,self.balls),
            ("Диаметр тела качения, мм",
             self.bearing_ball_diameter,self.ball_diameter),
            ("Делительный диаметр, мм",
             self.bearing_pitch_diameter,self.pitch_diameter),
            ("Угол контакта",self.bearing_contact_angle,self.contact_angle)):
            # Seed once for convenience; thereafter this window's method
            # parameters do not rewrite (or follow) the LIVE RPM/geometry.
            local.setValue(original.value())
            local.valueChanged.connect(self._show_bearing_diagnostics)
            bearing_form.addRow(label,local)
        self.diagnostics_layout.addLayout(bearing_form)
        bearing_options=QtWidgets.QHBoxLayout()
        bearing_options.addWidget(QtWidgets.QLabel("Полоса огибающей"))
        self.bearing_resonance=QtWidgets.QComboBox()
        for idx in range(self.envelope_band.count()):
            self.bearing_resonance.addItem(
                self.envelope_band.itemText(idx),
                self.envelope_band.itemData(idx))
        self.bearing_resonance.setCurrentIndex(
            self.envelope_band.currentIndex())
        bearing_options.addWidget(self.bearing_resonance)
        bearing_options.addWidget(QtWidgets.QLabel("FFT N"))
        self.bearing_fft=QtWidgets.QComboBox()
        for idx in range(self.nfft.count()):
            self.bearing_fft.addItem(
                self.nfft.itemText(idx),self.nfft.itemData(idx))
        self.bearing_fft.setCurrentIndex(self.nfft.currentIndex())
        bearing_options.addWidget(self.bearing_fft)
        bearing_run=QtWidgets.QPushButton("Рассчитать огибающую")
        bearing_run.clicked.connect(self._run_bearing_page)
        bearing_options.addWidget(bearing_run)
        bearing_options.addStretch(1)
        self.diagnostics_layout.addLayout(bearing_options)
        self.bearing_plot=pg.PlotWidget(
            title="Локальная FFT огибающей ВУ · ожидание данных")
        self.bearing_plot.setLabel("bottom","Частота",units="Гц")
        self.bearing_plot.setLabel("left","ВУ · СКЗ линии",units="м/с²")
        self.bearing_curve=self.bearing_plot.plot(
            pen=pg.mkPen("#18a3a3",width=1.2))
        self.diagnostics_layout.addWidget(self.bearing_plot,stretch=1)
        self.bearing_diagnostics.setWordWrap(True)
        self.diagnostics_layout.addWidget(self.bearing_diagnostics)
        self.extra_pages.addTab(self.diagnostics_page,"Подшипники")
        self.gears_page=QtWidgets.QWidget()
        gears_layout=QtWidgets.QVBoxLayout(self.gears_page)
        gears_layout.addWidget(QtWidgets.QLabel(
            "Редукторы · ожидаемые GMF и боковые полосы по 1× "
            "и числу зубьев; это НЕ фактически измеренные пики"))
        gear_form=QtWidgets.QFormLayout()
        self.gear_rpm=QtWidgets.QDoubleSpinBox()
        self.gear_rpm.setRange(0,200000)
        self.gear_rpm.setSuffix(" об/мин")
        self.gear_rpm.setValue(self.rpm.value())
        self.gear_rpm.valueChanged.connect(self.rpm.setValue)
        self.rpm.valueChanged.connect(self.gear_rpm.setValue)
        gear_form.addRow("Частота вращения (ручная/подтверждённая 1×)",
                         self.gear_rpm)
        self.gear_count=QtWidgets.QSpinBox()
        self.gear_count.setRange(0,400)
        self.gear_count.setValue(self.gear_teeth.value())
        self.gear_count.setSpecialValueText("Число зубьев не задано")
        self.gear_count.valueChanged.connect(self.gear_teeth.setValue)
        self.gear_teeth.valueChanged.connect(self.gear_count.setValue)
        gear_form.addRow("Число зубьев шестерни",self.gear_count)
        gears_layout.addLayout(gear_form)
        gear_run=QtWidgets.QPushButton("Показать GMF / гармоники")
        gear_run.clicked.connect(self._refresh_gear_table)
        gears_layout.addWidget(gear_run)
        self.gear_table=QtWidgets.QTableWidget(0,2)
        self.gear_table.setHorizontalHeaderLabels(
            ["Расчётная составляющая","Частота, Гц"])
        self.gear_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.gear_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        gears_layout.addWidget(self.gear_table,stretch=1)
        self.gear_note=QtWidgets.QLabel(
            "Укажите реальные/подтверждённые обороты и число зубьев. "
            "Прогноз частот не является обнаруженным дефектом.")
        self.gear_note.setWordWrap(True)
        gears_layout.addWidget(self.gear_note)
        self.extra_pages.addTab(self.gears_page,"Редукторы")
        self._apply_axes()

        for w in (self.adc,self.kind,self.nfft,self.band,self.smooth,self.analysis,self.envelope_band,self.notch,self.custom_low,self.custom_high):
            w.currentIndexChanged.connect(self._on_control_change) if isinstance(w,QtWidgets.QComboBox) else w.valueChanged.connect(self._on_control_change)
        for w in (self.yscale,self.xscale,self.db_ref):
            w.currentIndexChanged.connect(self._redraw_from_current)
        self.adc.currentIndexChanged.connect(self._advanced_adc_changed)
        self.dsp_adc.currentIndexChanged.connect(
            lambda index:self.adc.setCurrentIndex(index))
        self.adc.currentIndexChanged.connect(
            lambda index:self.dsp_adc.setCurrentIndex(index))
        self.rpm.valueChanged.connect(self._rpm_changed)
        self.rpm.valueChanged.connect(self._refresh_gear_table)
        self.gear_teeth.valueChanged.connect(self._refresh_gear_table)
        for w in (self.rpm,self.balls,self.ball_diameter,self.pitch_diameter,self.contact_angle):
            w.valueChanged.connect(self._update_markers)
        self.spectrum_view.currentIndexChanged.connect(self._select_primary_spectrum)
        self.kind.currentIndexChanged.connect(self._rebuild_y_height)
        self.yscale.currentIndexChanged.connect(self._rebuild_y_height)
        self.analysis.currentIndexChanged.connect(self._rebuild_y_height)
        self.filter_choice.currentIndexChanged.connect(self._select_primary_filter)
        self.filter_center.currentIndexChanged.connect(self._select_primary_filter)
        self.x_limit_choice.currentIndexChanged.connect(self._redraw_from_current)
        self.y_height_choice.currentIndexChanged.connect(self._redraw_from_current)
        self._select_primary_spectrum()
        self._select_primary_filter()
        self._time_filter_changed()
        self.views.setCurrentWidget(self.spectrum_page)
        install_modern_shell(self, main, panel, review, storage)
        self._timer=QtCore.QTimer(self)
        self._timer.setInterval(900)  # current Native sidecar is published >=750 ms
        self._timer.timeout.connect(self._poll)
        self._timer.start()
        self._ipc_timer=QtCore.QTimer(self)
        self._ipc_timer.setInterval(75)  # bounded fresh ring snapshots at up to 13 Hz
        self._ipc_timer.timeout.connect(self._poll_ipc)
        self._ipc_timer.start()
        self._ethernet_timer = QtCore.QTimer(self)
        self._ethernet_timer.setInterval(120)
        self._ethernet_timer.timeout.connect(self._collect_ethernet_discovery)
        self._archive_timer=QtCore.QTimer(self)
        self._archive_timer.setInterval(1100)
        self._archive_timer.timeout.connect(self._poll_archive_files)
        self._archive_timer.start()

    def _toggle_advanced(self,checked):
        self.advanced_panel.setVisible(bool(checked))
        self.advanced_toggle.setText(
            "Дополнительные расчёты и настройки ▾" if checked else
            "Дополнительные расчёты и настройки ▸")
        self._show_envelope_if_needed()

    def _show_envelope_if_needed(self):
        show=(self.advanced_toggle.isChecked() and
              self.analysis.currentData()=="envelope")
        self.envelope_label.setVisible(show)
        self.envelope_band.setVisible(show)

    def _rebuild_y_height(self,*_):
        # The original four presets are QUICK VIEWS, not a permanent
        # constraint. User overrides to kind/Y never receive stale units.
        scale=self.yscale.currentData()
        kind=self.kind.currentData()
        preset=("log_vu" if scale=="db" else
                {"acceleration":"linear_vu",
                 "velocity":"linear_vs",
                 "displacement":"linear_vp"}.get(kind,"linear_vu"))
        with QtCore.QSignalBlocker(self.y_height_choice):
            self.y_height_choice.clear()
            for label,value in y_height_options(preset):
                self.y_height_choice.addItem(label,value)
            # FFT presets are amplitudes; PSD/ASD have other dimensions.
            self.y_height_choice.setEnabled(self.analysis.currentData()=="fft")

    def _select_primary_spectrum(self,*_):
        # MVKView-like quick presets only choose physical kind and
        # ordinate; an operator's X-scale and FFT/PSD mode stay independent.
        kind,scale=view_settings(self.spectrum_view.currentData())
        old_kind=self.kind.currentData()
        old_scale=self.yscale.currentData()
        blocks=[QtCore.QSignalBlocker(w) for w in (self.kind,self.yscale)]
        try:
            self.kind.setCurrentIndex(self.kind.findData(kind))
            self.yscale.setCurrentIndex(self.yscale.findData(scale))
        finally:
            del blocks
        self._rebuild_y_height()
        self._show_envelope_if_needed()
        self._on_control_change()
        if (old_kind==kind and old_scale!=scale and
                self._spectrum is not None and
                self._spectrum.kind==kind and
                self._spectrum.mode==self.analysis.currentData()):
            # Switching log-VU(dB) <-> linear-VU reuses the SAME physical
            # acceleration FFT. The preset intentionally blocks Y signals,
            # so redraw its ordinate immediately, even without live RX.
            # A kind change (VU->VS/VP) still waits for a genuine recompute.
            self._render_spectrum()


    def _select_primary_filter(self,*_):
        mode=self.filter_choice.currentData()
        if mode in FAMILIES and self._filter_center_family!=mode:
            with QtCore.QSignalBlocker(self.filter_center):
                self.filter_center.clear()
                for hz in nominal_centres(mode):
                    self.filter_center.addItem(f"{hz:g} Гц",hz)
                selected=self.filter_center.findData(1000.)
                self.filter_center.setCurrentIndex(
                    selected if selected>=0 else self.filter_center.count()//2)
            self._filter_center_family=mode
        elif mode=="original_preset" and self._filter_center_family!=mode:
            with QtCore.QSignalBlocker(self.filter_center):
                self.filter_center.clear()
                for label,family,center in ORIGINAL_MVK_MENU:
                    self.filter_center.addItem(label,(family,center))
                self.filter_center.setCurrentIndex(0)
            self._filter_center_family=mode
        self.filter_center.setVisible(
            mode in FAMILIES or mode=="original_preset")
        with QtCore.QSignalBlocker(self.band), QtCore.QSignalBlocker(self.notch), (
                QtCore.QSignalBlocker(self.custom_low)), QtCore.QSignalBlocker(self.custom_high):
            self.band.setCurrentIndex(self.band.findData(
                "custom" if mode in ("highpass","lowpass","bandpass") or
                            mode in FAMILIES or mode=="original_preset"
                else PRESET_BANDS["Весь диапазон"]))
            self.notch.setCurrentIndex(self.notch.findData(
                {"notch50":50.0,"notch60":60.0}.get(mode)))
            if mode=="highpass":
                if self.custom_low.value()<=0:self.custom_low.setValue(10)
                self.custom_high.setValue(0)
            elif mode=="lowpass":
                self.custom_low.setValue(0)
                if self.custom_high.value()<=0:self.custom_high.setValue(1000)
            elif mode=="bandpass":
                if self.custom_low.value()<=0:self.custom_low.setValue(10)
                if self.custom_high.value()<=self.custom_low.value():
                    self.custom_high.setValue(max(1000,self.custom_low.value()+10))
        self.filter_button.setEnabled(mode in ("highpass","lowpass","bandpass"))
        self._on_control_change()

    def _filter_description(self):
        mode=self.filter_choice.currentData()
        if mode=="original_preset":
            selected=self.filter_center.currentData()
            if not isinstance(selected,tuple) or len(selected)!=2:
                return "Выберите пункт восстановленного меню MVKView"
            family,center=selected
            if family=="none":
                return "Каталог 32 названий MVKView · Без фильтра"
            return ("Каталог названий MVKView · "+self.filter_center.currentText()
                    +" · "+preset_description(family,center))
        if mode in FAMILIES:
            return preset_description(mode,self.filter_center.currentData())
        if mode=="none":
            text="Без пользовательского фильтра"
            if self.kind.currentData() in ("velocity","displacement"):
                text+=" (FFT: DC исключён; ВС/ВП вычисляются по f>0)"
            return text
        if mode=="highpass":
            return f"ФВЧ от {self.custom_low.value():g} Гц"
        if mode=="lowpass":
            return f"ФНЧ до {self.custom_high.value():g} Гц"
        if mode=="bandpass":
            return (f"Полосовой {self.custom_low.value():g}–"
                    f"{self.custom_high.value():g} Гц")
        return {"notch50":"Режектор 50 Гц, Q=35",
                "notch60":"Режектор 60 Гц, Q=35"}.get(mode,"Неизвестный фильтр")

    def _edit_filter(self):
        mode=self.filter_choice.currentData()
        if mode not in ("highpass","lowpass","bandpass"):
            return
        dlg=QtWidgets.QDialog(self)
        dlg.setWindowTitle("Фильтр спектра: параметры")
        form=QtWidgets.QFormLayout(dlg)
        lo=QtWidgets.QDoubleSpinBox(dlg)
        hi=QtWidgets.QDoubleSpinBox(dlg)
        for box in (lo,hi):
            box.setRange(0,32768)
            box.setDecimals(2)
            box.setSuffix(" Гц")
        lo.setValue(self.custom_low.value() or 10)
        hi.setValue(self.custom_high.value() or 1000)
        if mode!="lowpass":form.addRow("Нижняя граница ФВЧ",lo)
        if mode!="highpass":form.addRow("Верхняя граница ФНЧ",hi)
        ch=self._gui_ring.channel(self.adc.currentData())
        nyquist=ch.rate_hz/2 if ch else None
        note=(f"Fs={ch.rate_hz} Гц, Nyquist={nyquist:g} Гц"
              if ch else "Fs уточняется после приёма. Фильтр должен быть ниже Nyquist.")
        form.addRow(QtWidgets.QLabel(note))
        buttons=QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok|QtWidgets.QDialogButtonBox.Cancel,dlg)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec()!=QtWidgets.QDialog.DialogCode.Accepted:return
        lower=0.0 if mode=="lowpass" else lo.value()
        upper=0.0 if mode=="highpass" else hi.value()
        if ((mode!="lowpass" and lower<=0) or
            (mode!="highpass" and upper<=0) or
            (mode=="bandpass" and lower>=upper) or
            (nyquist is not None and max(lower,upper)>=nyquist)):
            QtWidgets.QMessageBox.warning(
                self,"Фильтр отклонён","Границы должны быть положительными, "
                "упорядоченными и строго ниже Nyquist АЦП.")
            return
        blocks=[QtCore.QSignalBlocker(self.custom_low),
                QtCore.QSignalBlocker(self.custom_high)]
        try:
            self.custom_low.setValue(lower)
            self.custom_high.setValue(upper)
        finally:
            del blocks
        self._select_primary_filter()

    def _apply_operator_ranges(self):
        selected=self.x_limit_choice.currentData()
        view=self._spectrum
        ch=self._gui_ring.channel(self.adc.currentData())
        rate=view.rate_hz if view is not None else (ch.rate_hz if ch else None)
        xmax,clipped=x_limit_hz(selected,rate)
        log_x=self.xscale.currentData()=="log"
        if log_x:
            # Physical FFT Hz values must stay untransformed in the data.
            # The pyqtgraph ViewBox of a log-X PlotItem uses log10(Hz).
            rate_for_axis=rate if rate is not None else 2
            length=view.nfft if view is not None else self.nfft.currentData()
            try:
                coordinates=spectrum_x_limits(int(rate_for_axis),int(length),
                                              float(xmax),True)
                xmin_view,xmax_view=coordinates.left,coordinates.right
                xmin_hz=coordinates.physical_min_hz
            except ValueError:
                xmin_hz=1.0
                xmin_view=0.0
                xmax_view=math.log10(max(10.0,float(xmax)))
        else:
            xmin_hz=0.0
            xmin_view,xmax_view=0.0,xmax
        self.waterfall.setXRange(0,xmax,padding=0)
        note=(f" · Fs={rate} Гц, доступно до {xmax:g} Гц (Nyquist)"
              if clipped else "")
        self.operator_info.setText(
            self._filter_description()+
            f" · частоты на графике: {xmin_hz:g}–{xmax:g} Гц"+
            (" · логарифмическая частотная шкала" if log_x else "")+note)
        scale=self.yscale.currentData()
        if view is not None:
            values=vibration_plot_values(
                view,scale,reference=self.db_ref.currentData())
            mask=(np.isfinite(values)&np.isfinite(view.hz)&
                  (view.hz>=xmin_hz)&(view.hz<=xmax))
            visible=values[mask].tolist()
        else:
            visible=[]
        y_height=(self.y_height_choice.currentData()
                  if self.analysis.currentData()=="fft" else None)
        ymin,ymax=visible_y_range(visible,scale,y_height)
        if self._manual_spec_axes is not None:
            left,right,bottom,top=self._manual_spec_axes
            if (not all(math.isfinite(v) for v in (left,right,bottom,top))
                    or left>=right or bottom>=top):
                self._manual_spec_axes=None
            else:
                xmin_view,xmax_view,ymin,ymax=left,right,bottom,top
        for plot in (self.spec, getattr(self,"overview_spec",None)):
            if plot is not None:
                plot.setXRange(xmin_view,xmax_view,padding=0)
                plot.setYRange(ymin,ymax,padding=0)

    def _reset_spectrum_axis(self):
        self._manual_spec_axes=None
        self._apply_operator_ranges()

    def _read_settings(self):
        band=self.band.currentData()
        if self.filter_choice.currentData()=="original_preset":
            selected=self.filter_center.currentData()
            if selected is None:
                raise ValueError("Не выбрана полоса из меню MVKView")
            family,center=selected
            band=((0.,None) if family=="none"
                  else preset_band(family,center))
        elif self.filter_choice.currentData() in FAMILIES:
            band=preset_band(self.filter_choice.currentData(),
                             self.filter_center.currentData())
        elif band=="custom":
            high=float(self.custom_high.value())
            band=(float(self.custom_low.value()),high if high>0 else None)
        return (self.adc.currentData(),self.kind.currentData(),self.nfft.currentData(),
                band,self.smooth.value(),
                self.analysis.currentData(),self.envelope_band.currentData(),self.notch.currentData())

    def _on_control_change(self,*_):
        self._manual_spec_axes = None
        self._show_envelope_if_needed()
        self._last_fft_submit=0.0
        self._last_submitted_key=None
        if self._spectrum is not None and (
                self._spectrum.mode!=self.analysis.currentData() or
                self._spectrum.kind!=self.kind.currentData()):
            self._waterfall_rows=[]
            self._waterfall_key=None
            self.waterfall_img.clear()
        self._render_dsp()
        self._update_frange_label()
        self._request_update()

    def _request_update(self,*_):
        self._generation += 1
        # The physical Y unit must update IMMEDIATELY on the operator's
        # choice, even while the next verified FFT is still calculating.
        self._apply_axes()
        if self._spectrum is not None and (
                self._spectrum.kind != self.kind.currentData() or
                self._spectrum.mode != self.analysis.currentData()):
            self._spectrum = None
            self.spec_curve.setData([],[])
            self._clear_overview_plot("spectrum")
            self.metrics.setText("Пересчёт выбранного физического спектра")
        self._render_wave()
        if self._spectrum is None:self._apply_operator_ranges()
        self._schedule_fft()

    def _apply_axes(self):
        kind=self.kind.currentData()
        ys=self.yscale.currentData()
        xs=self.xscale.currentData()
        mode=self.analysis.currentData()
        unit=KINDS[kind][1]
        if self._spectrum is not None and self._spectrum.kind==kind and self._spectrum.mode==mode:
            vertical=vibration_y_label(self._spectrum,ys,self.db_ref.currentData())
        else:
            prefix={"fft":"FFT","welch":"PSD Уэлча","asd":"ASD Уэлча",
                    "third_octave":"1/3 октавы","envelope":"Огибающая"}[mode]
            if ys=="linear":
                vertical=(f"{prefix} · ({unit})²/Гц" if mode=="welch" else
                          f"{prefix} · {unit}/√Гц" if mode=="asd" else
                          f"{prefix} · {unit} СКЗ")
            else:
                ref=db_reference(kind,self.db_ref.currentData())
                if mode=="welch":
                    vertical=f"{prefix} · дБ отн. ({ref:g} {unit})²/Гц"
                elif mode=="asd":
                    vertical=f"{prefix} · дБ отн. {ref:g} {unit}/√Гц"
                else:
                    vertical=f"{prefix} · дБ отн. {db_reference_text(kind,self.db_ref.currentData())}"
        self.spec.setLabel("left",vertical)
        # Numerical amplitudes are ALREADY logarithmic dB. A second log-Y
        # transformation would distort negative and zero dB values.
        self.spec.getPlotItem().setLogMode(x=(xs=="log"),y=False)
        overview=getattr(self,"overview_spec",None)
        if overview is not None:
            overview.getPlotItem().setLogMode(x=(xs=="log"),y=False)
            overview.setLabel("left",vertical)

    def _redraw_from_current(self,*_):
        # An explicit change to the physical view/scale resets manual axes;
        # incoming frames and ordinary _render_spectrum calls do NOT.
        self._manual_spec_axes = None
        self._apply_axes()
        if self._spectrum is None:self._apply_operator_ranges()
        else:self._render_spectrum()
        self._update_markers()

    def _update_markers(self,*_):
        for line in self._marker_lines:
            self.spec.removeItem(line)
        self._marker_lines=[]
        if self.rpm.value()<=0:
            return  # missing TACH pulses-per-revolution: RPM never invented
        try:
            if self.balls.value()>0:
                markers=bearing_frequency_markers(
                    self.rpm.value(), balls=self.balls.value(),
                    ball_diameter_mm=self.ball_diameter.value(),
                    pitch_diameter_mm=self.pitch_diameter.value(),
                    contact_angle_deg=self.contact_angle.value())
            else:
                markers=bearing_frequency_markers(self.rpm.value())
        except ValueError:
            markers=bearing_frequency_markers(self.rpm.value())
        if self.gear_teeth.value()>0:
            try:
                gear=gear_mesh_markers(
                    self.rpm.value(),self.gear_teeth.value())
                markers["GMF"]=gear.mesh_hz
                for i,hz in enumerate(gear.harmonics_hz[1:],start=2):
                    markers[f"{i}GMF"]=hz
                for hz in gear.sidebands_hz:
                    sign="−" if hz<gear.mesh_hz else "+"
                    markers[f"GMF{sign}{abs(hz-gear.mesh_hz)/self.rpm.value()*60:.0f}×"]=hz
            except ValueError:
                pass  # invalid user geometry cannot inject arbitrary lines
        for label,hz in markers.items():
            if hz<=0:continue
            line=pg.InfiniteLine(pos=(math.log10(hz) if self.xscale.currentData()=="log" else hz),movable=False,
                 pen=pg.mkPen("#6e8295",width=1,style=QtCore.Qt.DashLine),
                 label=label,labelOpts={"position":0.9,"color":"#6e8295"})
            self.spec.addItem(line)
            self._marker_lines.append(line)

    def _open_calculated_trend(self,group,position=None):
        # One operator click connects a displayed value to the exact
        # historical metric family already backed by persistent SQLite.
        index=self.history_ui.trend_group.findData(group)
        if index<0:
            self.dsp_info.setText(
                f"Для показателя {group} архивный тренд пока не поддерживается")
            return
        if getattr(self,"_modern_installed",False):
            open_archive_window(self,"trends")
        else:
            self.views.setCurrentWidget(self.history_ui.trend_page)
        self.history_ui.trend_group.setCurrentIndex(index)
        if position is not None:
            ix=self.history_ui.trend_position.findData(position)
            if ix<0:
                self.history_ui.trend_info.setText(
                    "Эта архивная позиция недоступна: выбор не подменён")
                return
            self.history_ui.trend_position.setCurrentIndex(ix)
        self.history_ui._plot_trend()

    def _open_dsp_band_trend(self):
        if self.dsp_band_mode.currentData()!="third":
            self.dsp_band_note.setText(
                "Сводная 1/1-октавная полоса не является исходной "
                "приборной метрикой AUX4700, поэтому в приборный "
                "исторический тренд не подставляется.")
            return
        row=self.dsp_bands_table.currentRow()
        if row<0 or row>=43:
            self.dsp_band_note.setText("Выберите одну из 43 исходных полос")
            return
        self._open_calculated_trend("third_octave",row)

    def _open_dsp_24_trend(self):
        row=self.dsp24_table.currentRow()
        if row<0 or row>=24:
            self.dsp24_note.setText("Выберите расчётную позицию 1–24")
            return
        self._open_calculated_trend(self.dsp24_mode.currentData(),row)

    def _open_local_metric_trend(self):
        row=self.local_values_table.currentRow()
        if row<0 or row>=len(self.local_trend_metric_ids):
            self.features_label.setText("Выберите локальный показатель в таблице")
            return
        self._open_calculated_trend(self.local_trend_metric_ids[row])

    def _plot_dsp_24(self,*_):
        packet=self._dsp_last
        if packet is None or not packet.has_extended:
            self.dsp24_curve.setData([],[])
            return
        key=self.dsp24_mode.currentData()
        data=getattr(packet,key,None)
        if data is None:
            self.dsp24_curve.setData([],[])
            return
        indices=np.arange(1,25,dtype=np.float64)
        available=np.isfinite(data)
        self.dsp24_curve.setData(indices[available],data[available],
                                 connect="finite")
        self.dsp24_plot.setTitle(
            "ОРИГИНАЛЬНЫЙ AUX4700 · "+key+
            " · номер исходной позиции (частота не подтверждена)")
        self.dsp24_plot.setLabel(
            "left","Исходное значение прибора · единицы уточняются")

    def _plot_dsp_bands(self,*_):
        packet=self._dsp_last
        self.dsp_band_trend_button.setEnabled(
            self.dsp_band_mode.currentData()=="third")
        if packet is None:
            self.dsp_curve.setData([],[])
            self.dsp_bands_table.setRowCount(0)
            return
        if self.dsp_band_mode.currentData()=="octave":
            freqs,values=octave_rss_from_thirds(
                packet.frequency_hz,packet.acceleration_rms)
            provenance="APP_DERIVED · сводные 1/1 из оригинальных 1/3 СКЗ"
        else:
            freqs,values=packet.frequency_hz,packet.acceleration_rms
            provenance="ORIGINAL AUX4700 · 43 третьоктавных СКЗ"
        mask=np.isfinite(values)
        self.dsp_curve.setData(freqs[mask],values[mask])
        self.dsp_plot.setTitle(provenance)
        self.dsp_bands_table.setRowCount(len(freqs))
        for row,(hz,val) in enumerate(zip(freqs,values)):
            for col,s in enumerate((f"{hz:g}",
                           "—" if not np.isfinite(val) else f"{val:.8g}")):
                item=QtWidgets.QTableWidgetItem(s)
                if s=="—":item.setToolTip(
                    "Недоступно: исходный NaN не подменяется нулём")
                self.dsp_bands_table.setItem(row,col,item)
        self.dsp_band_note.setText(
            provenance+" · м/с² · неполные исходные полосы сохраняют "
            "недоступность локальных сводных значений.")

    def _fill_local_values(self,features,velocity=None):
        fields=(
            ("ВУ СКЗ",features.rms_m_s2,"м/с²"),
            ("ВУ пик",features.peak_m_s2,"м/с²"),
            ("ВУ пик-пик",features.peak_to_peak_m_s2,"м/с²"),
            ("Крест-фактор",features.crest_factor,"безразм."),
            ("Куртозис Pearson",features.kurtosis_pearson,"безразм."),
            ("Асимметрия",features.skewness,"безразм."),
            ("Импульсный фактор",features.impulse_factor,"безразм."),
            ("Фактор формы",features.shape_factor,"безразм."),
            ("Фактор зазора",features.clearance_factor,"безразм."),
            ("ВС СКЗ 10–1000 Гц",(
                velocity.rms if velocity is not None and velocity.valid and
                velocity.high_hz>=1000. else None),"мм/с"),
        )
        for row,(label,value,unit) in enumerate(fields):
            for col,s in enumerate((label,
                         "—" if value is None or not math.isfinite(value)
                             else f"{value:.8g}",unit)):
                item=QtWidgets.QTableWidgetItem(s)
                item.setToolTip(
                    "APP_DERIVED из проверенного калиброванного окна; "
                    "не приборный AUX4700")
                self.local_values_table.setItem(row,col,item)

    def _reset_dsp(self,message):
        self._dsp_last=None
        self.dsp_curve.setData([],[])
        self.dsp_bands_table.setRowCount(0)
        self.dsp24_curve.setData([],[])
        self.dsp24_table.clearContents()
        self.dsp_source_hint.setText(message)
        self.dsp_info.setText(message)

    def _render_dsp(self):
        status=self._last_status
        if status is None or status.get("phase") not in ("RECORDING","VERIFYING","COMPLETED"):
            self._reset_dsp("DSP: ожидание измерения МВК01; значения не подменяются локальной FFT")
            return
        try:
            band=read_original_dsp_bands(status,self.adc.currentData())
        except (ValueError,TypeError) as exc:
            self._reset_dsp(f"Оригинальный AUX4700 отклонён: {exc}")
            return
        if band is None:
            self._reset_dsp("AUX4700: оригинальные расчётные данные выбранного АЦП ещё не получены")
            return
        self._dsp_last=band
        self._plot_dsp_bands()
        self.dsp_source_hint.setText(
            f"ORIGINAL AUX4700 · пакет {band.update} · "+
            ("LIVE" if status.get("phase")=="RECORDING" else "НЕ Live"))
        if band.has_extended:
            # Register slots 1..24 are NOT the same as 43 third-octave
            # frequencies. Original register map is kept precisely.
            for i in range(24):
                cells=[
                    f"{i+1:d} (0x{0x60+2*i:02X} / 0x{0xA0+2*i:02X} / 0x{0xE0+2*i:02X})",
                    "—" if np.isnan(band.band_rms[i]) else f"{band.band_rms[i]:.8g}",
                    "—" if np.isnan(band.band_peak_equiv[i]) else f"{band.band_peak_equiv[i]:.8g}",
                    "—" if np.isnan(band.band_span_equiv[i]) else f"{band.band_span_equiv[i]:.8g}",
                ]
                for j,value in enumerate(cells):
                    item=QtWidgets.QTableWidgetItem(value)
                    if j>0 and value=="—":
                        item.setToolTip("Оригинальный DSP: недоступно/NaN (НЕ ноль)")
                    self.dsp24_table.setItem(i,j,item)
            self._plot_dsp_24()
        else:
            self.dsp24_table.clearContents()
            self.dsp24_curve.setData([],[])
        pending=(" · не готовы: "+", ".join(band.not_ready)) if band.not_ready else ""
        lifecycle=("ПОСЛЕДНИЙ ПРИБОРНЫЙ СНИМОК · НЕ Live. " if
                   status.get("phase")!="RECORDING" else "LIVE · ")
        self.dsp_info.setText(
            lifecycle+
            f"ИСТОЧНИК: MVK_DSP_ORIGINAL_AUX4700 · АЦП {band.adc} · "
            f"пакет {band.update} · статус {band.status_hex}{pending} · "
            f"передано: {band.total_transmitted_cells} значений · "
            f"неконечных/недоступных: {band.nonfinite_fields}. "
            "43 третьоктавы — СКЗ ВУ по известным центрам; "
            "24 расчётные позиции — отдельные приборные СКЗ/Peak/Span "
            "с пока не подтверждённой привязкой к частотам и единицам. "
            "Никакой подмены локальными RMS/FFT."
        )

    def _update_frange_label(self):
        status=self._last_status
        if status is None or status.get("phase") not in ("RECORDING","VERIFYING","COMPLETED"):
            self.frange_info.setText(
                "FRange: ожидание начальной конфигурации МВК01 "
                "(недоступный коэффициент не принимается за 1,0).")
            return
        try:
            gain=original_applied_frange(status,self.adc.currentData())
        except (ValueError,TypeError) as exc:
            self.frange_info.setText(f"FRange ОТКЛОНЁН: {exc}")
            return
        if gain is None:
            self.frange_info.setText(
                "FRange: начальная конфигурация прибора ещё не получена; "
                "нет оснований считать сырые отсчёты калиброванными.")
            return
        adc=self.adc.currentData()
        self.frange_info.setText(
            f"ПРИБОР · FRange АЦП {adc} = {gain:.9g} "
            f"(конфигурация 0x{0x100+(adc-1)*0x100+0x0E:04X}). "
            "Native Go уже умножил каждый Float32 АЦП на FRange ровно один раз "
            "до записи BIN/IPC. MVK Live НЕ умножает второй раз.")

    def _update_features(self):
        if self.freeze.isChecked():return
        ch=self._gui_ring.channel(self.adc.currentData())
        if ch is None or ch.available<512:return
        key=(self._gui_ring.session_id,self.adc.currentData(),ch.end)
        if key==self._trend_key:return
        self._trend_key=key
        count=min(ch.available,max(2048,ch.rate_hz))
        f=time_features(ch.latest(count),ch.rate_hz)
        self.features_label.setText(
            f"APP_DERIVED · ВУ СКЗ {f.acceleration_rms:.5g} м/с² · "
            f"Пик {f.acceleration_peak:.5g} м/с² · Crest {f.acceleration_crest_factor:.3f} · "
            f"Куртозис Pearson {f.acceleration_kurtosis:.3f} · "
            +("Обороты: "+self._rpm_source if self.rpm.value()>0 else "Обороты: не заданы")
        )
        if len(self._trend_points) and ch.end/ch.rate_hz<=self._trend_points[-1][0]:
            self._trend_points=[]
        self._trend_points.append((ch.end/ch.rate_hz,f.acceleration_rms))
        self._trend_points=self._trend_points[-240:]
        self._redraw_short_trend()

    def _advanced_adc_changed(self,*_):
        # A previous ADC spectrum must never remain a measured cursor source
        # while the newly selected ADC has no validated current window.
        self._spectrum=None
        self.spec_curve.setData([],[])
        self._clear_overview_plot("spectrum")
        cursors=getattr(self,"_professional_cursors",None)
        if cursors is not None:
            cursors.refresh_spectrum()
            cursors.refresh_bearing()
        pinned=getattr(self,"_modern_method_pins",{})
        if "kurtogram" not in pinned:
            self._invalidate_kurtogram(
                f"АЦП {self.adc.currentData()}: кюртограмму нужно пересчитать")
        # A former channel's short-term Live results must never appear as
        # current ADC after changing channel from any of the workspaces.
        self._waterfall_rows.clear()
        self._waterfall_key=None
        self.waterfall_img.clear()
        self._trend_points.clear()
        self._trend_key=None
        self.trend_line.setData([],[])
        self.short_trend_info.setText(
            f"АЦП {self.adc.currentData()} · ожидание новых подтверждённых окон")
        for mode,plot in self.extra_method_plots.items():
            if mode in pinned:
                continue  # detached snapshot has its own independent source
            self.extra_method_images[mode].clear()
            self.extra_method_lines[mode].setData([],[])
            plot.setTitle(
                f"АЦП {self.adc.currentData()} · {mode.upper()} · "
                "нет расчёта для выбранного канала")
            self.extra_method_infos[mode].setText(
                f"АЦП {self.adc.currentData()} · выберите параметры и "
                "пересчитайте из этого канала")
        # A detached bearing window is pinned to its original ADC even when
        # the global LIVE selector changes. In legacy/no-pin mode clear it.
        if "bearing" not in pinned:
            self._bearing_spectrum=None
            self.bearing_curve.setData([],[])
            self.bearing_diagnostics.setText(
                f"АЦП {self.adc.currentData()} · выберите источник огибающей")
            if cursors is not None:
                cursors.refresh_bearing()

    def _redraw_short_trend(self,*_):
        if not hasattr(self,"short_trend_info"):return
        rows=self._trend_points[-int(self.trend_max_points.currentData()):]
        self.trend_line.setData(
            [p[0] for p in rows],[p[1] for p in rows])
        if rows:
            self.short_trend_info.setText(
                f"АЦП {self.adc.currentData()} · {len(rows)} новых окон · "
                f"ВУ СКЗ {rows[-1][1]:.5g} м/с² · APP_DERIVED, не AUX4700")


    def _time_filter_changed(self,*_):
        mode=self.time_filter_choice.currentData()
        if mode in FAMILIES and self._time_center_family!=mode:
            with QtCore.QSignalBlocker(self.time_filter_center):
                self.time_filter_center.clear()
                for hz in nominal_centres(mode):
                    self.time_filter_center.addItem(f"{hz:g} Гц",hz)
                selected=self.time_filter_center.findData(1000.)
                self.time_filter_center.setCurrentIndex(
                    selected if selected>=0 else self.time_filter_center.count()//2)
            self._time_center_family=mode
        elif mode=="original_preset" and self._time_center_family!=mode:
            with QtCore.QSignalBlocker(self.time_filter_center):
                self.time_filter_center.clear()
                for label,family,center in ORIGINAL_MVK_MENU:
                    self.time_filter_center.addItem(label,(family,center))
                self.time_filter_center.setCurrentIndex(0)
            self._time_center_family=mode
        self.time_filter_center.setVisible(
            mode in FAMILIES or mode=="original_preset")
        self.time_filter_button.setEnabled(
            mode in ("highpass","lowpass","bandpass"))
        self._render_wave()

    def _edit_time_filter(self):
        # This dialog changes ONLY the displayed time signal, never
        # spectrum processing or the device-calculated AUX4700 registers.
        mode=self.time_filter_choice.currentData()
        if mode not in ("highpass","lowpass","bandpass"):
            return
        dlg=QtWidgets.QDialog(self)
        dlg.setWindowTitle("Временной сигнал · локальные параметры фильтра")
        form=QtWidgets.QFormLayout(dlg)
        lo=QtWidgets.QDoubleSpinBox(dlg)
        hi=QtWidgets.QDoubleSpinBox(dlg)
        for box in (lo,hi):
            box.setRange(0,32768)
            box.setDecimals(2)
            box.setSuffix(" Гц")
        lo.setValue(self.time_filter_low)
        hi.setValue(self.time_filter_high)
        if mode!="lowpass":
            form.addRow("ФВЧ: нижняя граница",lo)
        if mode!="highpass":
            form.addRow("ФНЧ: верхняя граница",hi)
        channel=self._gui_ring.channel(self.adc.currentData())
        nyquist=(channel.rate_hz/2 if channel is not None else None)
        form.addRow(QtWidgets.QLabel(
            f"Nyquist текущего АЦП: {nyquist:g} Гц" if nyquist else
            "Реальная частота дискретизации станет известна при измерении"))
        buttons=QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok|QtWidgets.QDialogButtonBox.Cancel,dlg)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec()!=QtWidgets.QDialog.DialogCode.Accepted:return
        lower=lo.value() if mode!="lowpass" else 0.0
        upper=hi.value() if mode!="highpass" else 0.0
        if ((mode!="lowpass" and lower<=0) or
            (mode!="highpass" and upper<=0) or
            (mode=="bandpass" and lower>=upper) or
            (nyquist is not None and max(lower,upper)>=nyquist)):
            QtWidgets.QMessageBox.warning(
                self,"Фильтр временного сигнала отклонён",
                "Проверьте частотные границы относительно Nyquist")
            return
        if mode!="lowpass":self.time_filter_low=lower
        if mode!="highpass":self.time_filter_high=upper
        self._render_wave()

    def _clear_overview_plot(self, domain):
        """Blank obsolete cloned LIVE data instead of displaying wrong ADC."""
        if domain=="time":
            self._cursor_time_samples=None
            self._cursor_time_fs=None
            cursors=getattr(self,"_professional_cursors",None)
            if cursors is not None:
                cursors.refresh_time()
            curve=getattr(self,"overview_wave_curve",None)
            view=getattr(self,"overview_wave",None)
            text="Временной сигнал · нет подтверждённых отсчётов"
        else:
            curve=getattr(self,"overview_spec_curve",None)
            view=getattr(self,"overview_spec",None)
            text="Спектр · ожидание реальных отсчётов АЦП"
            cursors=getattr(self,"_professional_cursors",None)
            if cursors is not None:
                cursors.refresh_spectrum()
        if curve is not None:
            curve.setData([],[])
        if view is not None:
            view.setTitle(text)

    def _empty_wave_axes(self, seconds: float):
        """Match overview and detailed axes without showing fake ADC data.

        A missing ADC cannot yield RMS or auto amplitude. Until real samples
        arrive, a neutral blank ±1 m/s² range is used for Auto; a manual
        vertical scale is reflected on both plots immediately.
        """
        selected=self.time_y_width.currentData()
        height=float(selected) if selected is not None else 1.0
        for plot in (self.wave,getattr(self,"overview_wave",None)):
            if plot is not None:
                plot.setXRange(-seconds,0.0,padding=0)
                plot.setYRange(-height,height,padding=0)

    def _render_wave(self,*_):
        requested=float(self.timebase.currentData())
        if self.freeze.isChecked() and self._freeze_samples is not None:
            if self.adc.currentData()!=self._freeze_channel:
                self.wave_curve.setData([],[])
                self._clear_overview_plot("time")
                self.wave_stats.setText(
                    "В замороженном сигнале выбран другой канал АЦП")
                self._empty_wave_axes(requested)
                return
            fs=self._freeze_rate
            offset=int(round(self.history.value()*fs))
            end=len(self._freeze_samples)-offset
            data=self._freeze_samples[:max(0,end)]
        else:
            ch=self._gui_ring.channel(self.adc.currentData())
            if ch is None or ch.available==0:
                self.wave_curve.setData([],[])
                self._clear_overview_plot("time")
                self.wave_stats.setText(
                    "Временной сигнал: ожидание подтверждённых АЦП Float32")
                self._empty_wave_axes(requested)
                return
            fs=ch.rate_hz
            data=ch.latest(min(ch.available,262144))
        if fs<=0 or len(data)==0:
            self.wave_curve.setData([],[])
            self._clear_overview_plot("time")
            self.wave_stats.setText("Нет допустимых отсчётов выбранного АЦП")
            self._empty_wave_axes(requested)
            return
        # Only genuine ring samples: do not extend a 4-s packet to a
        # requested 30-s scope or assume a missing sample rate.
        n=min(len(data),max(2,int(round(requested*fs))))
        window=data[-n:]
        mode=self.time_filter_choice.currentData()
        if mode=="original_preset":
            selected=self.time_filter_center.currentData()
            if not isinstance(selected,tuple) or len(selected)!=2:
                self.wave_curve.setData([],[])
                self._clear_overview_plot("time")
                self.wave_stats.setText("Выберите полосу из меню MVKView")
                self._empty_wave_axes(requested)
                return
            filter_mode,filter_center=selected
        else:
            filter_mode=mode
            filter_center=(self.time_filter_center.currentData()
                           if mode in FAMILIES else None)
        try:
            physical=time_filter_waveform(
                window,fs,mode=filter_mode,
                low=self.time_filter_low,high=self.time_filter_high,
                center=filter_center)
        except ValueError as exc:
            self.wave_curve.setData([],[])
            self._clear_overview_plot("time")
            self.wave_stats.setText(f"Временной сигнал / фильтр: {exc}")
            self._empty_wave_axes(requested)
            return
        # Cursor measurements read the COMPLETE locally filtered physical window.
        # Screen min/max decimation below never changes cursor amplitudes/intervals.
        self._cursor_time_samples=np.asarray(physical,dtype=np.float64).copy()
        self._cursor_time_fs=int(fs)
        # Peak-preserving min/max decimation is strictly for presentation.
        # All stats below use the FULL filtered source window, not the
        # decimated trace or any AUX4700 sensor DSP registers.
        step=max(1,int(math.ceil(len(physical)/2500)))
        if step>1 and len(physical)>=step:
            block=physical[-(len(physical)//step)*step:].reshape(-1,step)
            lo=block.min(axis=1)
            hi=block.max(axis=1)
            y=np.stack((lo,hi),axis=1).reshape(-1)
            index=np.repeat(np.arange(len(block))*step,2)
            index[1::2]+=step-1
            x=(index-len(block.reshape(-1)))/fs
        else:
            y=physical
            x=(np.arange(len(physical),dtype=np.float64)-len(physical))/fs
        self.wave_curve.setData(x,y)
        overview=getattr(self,"overview_wave_curve",None)
        if overview is not None:
            overview.setData(x,y)
        self.wave.setLabel("bottom","Время",units="с")
        self.wave.setLabel("left","ВУ · Виброускорение",units="м/с²")
        # A waveform has signed peaks; never force a 0..positive spectrum Y.
        ymin,ymax=signed_time_limits(physical,self.time_y_width.currentData())
        self.wave.setYRange(ymin,ymax,padding=0)
        available_seconds=len(physical)/fs
        self.wave.setXRange(-available_seconds,0,padding=0)
        cursors=getattr(self,"_professional_cursors",None)
        if cursors is not None:
            cursors.refresh_time()
        overview_plot=getattr(self,"overview_wave",None)
        if overview_plot is not None:
            overview_plot.setTitle(
                f"Временной сигнал · АЦП {self.adc.currentData()} · Fs {fs} Гц")
            overview_plot.setYRange(ymin,ymax,padding=0)
            overview_plot.setXRange(-available_seconds,0,padding=0)
        if mode=="original_preset":
            info=("Название меню MVKView · "+self.time_filter_center.currentText()+
                  (" · "+preset_description(filter_mode,filter_center)
                   if filter_mode in FAMILIES else " · Без фильтра"))
        elif mode in FAMILIES:
            info=preset_description(mode,self.time_filter_center.currentData())
        else:
            info={"none":"Без фильтра",
                  "highpass":f"ФВЧ от {self.time_filter_low:g} Гц",
                  "lowpass":f"ФНЧ до {self.time_filter_high:g} Гц",
                  "bandpass":f"Полосовой {self.time_filter_low:g}–{self.time_filter_high:g} Гц",
                  "notch50":"Режектор 50 Гц",
                  "notch60":"Режектор 60 Гц"}[mode]
        cropped=(f" · доступно {available_seconds:g} с" if
                 available_seconds<requested-.001 else "")
        self.wave_info.setText(
            f"Временной сигнал · АЦП {self.adc.currentData()} · "
            f"Fs={fs} Гц · {info} · откалиброван Native Go ×FRange один раз"
            f"{cropped}")
        if physical.size>=2:
            rms,peak,span=display_time_stats(physical,fs)
            self.wave_stats.setText(
                f"APP_DERIVED · по выбранному временному окну · "
                f"СКЗ {rms:.5g} м/с² · Пик {peak:.5g} м/с² · "
                f"Пик-пик {span:.5g} м/с² · N={len(physical)}; "
                "не путать с исходным расчётным AUX4700 прибора")

    def _schedule_fft(self):
        if self._preview is None or (
                self._future is not None and not self._future.done()):
            return
        s=self._read_settings()
        ch=self._gui_ring.channel(s[0])
        if ch is None or ch.available<s[2]:
            self._spectrum=None
            self.spec_curve.setData([],[])
            self._clear_overview_plot("spectrum")
            self.metrics.setText(f"Ожидание {s[2]} подтверждённых отсчётов АЦП {s[0]}")
            return
        if self.freeze.isChecked() and self._freeze_samples is not None:
            available=max(0,len(self._freeze_samples)-
                          int(round(self.history.value()*self._freeze_rate)))
        else:
            available=ch.available
        history=min(available,s[2]*2) if s[5] in (
            "welch","asd","third_octave") else s[2]
        history=max(history,s[2])
        try:
            source,fs,stamp=self._current_window(history)
        except ValueError as exc:
            self._spectrum=None
            self.spec_curve.setData([],[])
            self._clear_overview_plot("spectrum")
            self.metrics.setText(str(exc))
            return
        job_key=(stamp,s)
        if job_key==self._last_submitted_key or (
                time.monotonic()-self._last_fft_submit<.14):
            return
        self._last_fft_submit=time.monotonic()
        self._last_submitted_key=job_key
        self._job_settings=(self._generation,self._preview.updated_utc,s,job_key)
        self._future=self._executor.submit(
            analyze_live,source,fs,
            kind=s[1],mode=s[5],nfft=s[2],band_hz=s[3],
            envelope_band=s[6],smooth_bins=s[4],notch_hz=s[7])

    def _collect_analysis(self):
        if self._future is None or not self._future.done():
            return
        job=self._job_settings
        try:
            result=self._future.result()
        except (ValueError,RuntimeError,FloatingPointError) as exc:
            self.metrics.setText(f"APP_DERIVED: {exc}")
            self.spec_curve.setData([],[])
            self._spectrum=None
        else:
            if (job and job[2]==self._read_settings() and
                    self._preview is not None and
                    (job[3][0][0]=="FROZEN")==self.freeze.isChecked()):
                self._last_result=result
                self._spectrum=result.view
                self._render_spectrum()
                if not self.freeze.isChecked():
                    self._update_waterfall(job[3])
                f=result.features
                detail=(f"ВУ СКЗ {f.rms_m_s2:.5g} м/с² · "
                        f"пик {f.peak_m_s2:.5g} м/с² · пик-пик {f.peak_to_peak_m_s2:.5g} · "
                        f"crest {f.crest_factor:.2f} · kurt {f.kurtosis_pearson:.2f} · "
                        f"skew {f.skewness:.2f} · shape {f.shape_factor:.2f} · "
                        f"impulse {f.impulse_factor:.2f}")
                if result.broadband_velocity is not None and result.broadband_velocity.valid:
                    v=result.broadband_velocity
                    detail+=f" · ВС {v.low_hz:g}–{v.high_hz:g} Гц: {v.rms:.3g} {v.unit} СКЗ"
                self.features_label.setText("APP_DERIVED · "+detail)
                self._fill_local_values(result.features,result.broadband_velocity)
                if result.auto_envelope is not None:
                    choice=result.auto_envelope
                    self.metrics.setText(self.metrics.text()+
                        f" · автополоса {choice.low_hz:.0f}–{choice.high_hz:.0f} Гц"
                        f" (PySDKit Fast Kurtogram, эксцесс SK={choice.envelope_kurtosis:.2f}; "
                        f"{choice.confidence})")
                # Detached bearing analysis keeps its own immutable snapshot;
                # the next LIVE FFT must not replace its spectrum.
        self._future=None
        self._schedule_fft()

    def _poll(self):
        self._collect_analysis()
        self._poll_extra()
        if self._capture_root is None:return
        try:
            status=load_capture_live_status(self._capture_root,
                    instrument_ipv4=self._active_ip,local_ipv4=self._local_ip)
            if status is None:
                self.status.setText("Ожидание Native R6.1")
                return
            self._last_status=status
            self._render_dsp()
            self._update_frange_label()
            self.status.setText(f"Native R6.1: {status['phase']} · RAW {status['raw_bytes']/1048576:.1f} МиБ · "
                                f"кадров {status['frames_decoded']} · AUX {status['aux4700_updates']}")
            if status.get("source_tcp_multi_socket"):
                self._clear("Отклонено: обнаружен посторонний TCP источник")
                return
            # Full Native AUX4700.jsonl is the source of historical frames;
            # the validated status stores the latest 8 channels meanwhile.
            # Archive failure must NEVER stop the sole TCP receiver.
            try:
                n=self._archive.record_vendor_status(status)
                if n:self._archive_dirty=True
                if self._capture_root is not None:
                    self._queue_aux_log(self._capture_root,status["session_id"])
            except (OSError,ValueError,sqlite3.DatabaseError) as hist_err:
                self.history_ui.trend_info.setText(
                    f"Локальный архив: {hist_err}; приём МВК01 не остановлен")
            if status["phase"]!="RECORDING":
                # The last already validated local history remains available
                # for operator review; it must NOT be relabeled as live.
                self._ipc_client=None
                self._capture_root=None
                self.status.setText(
                    f"Приём завершён: {status['phase']} · "
                    "последний локальный снимок (не Live)")
                return
            if self._ipc_client is None:
                self._ipc_client=discover_local_ipc(self._capture_root,status)
            if self._ipc_client is not None:
                return  # fast IPC is the sole GUI producer, never mix ZIP data
            preview=load_live_preview(self._capture_root,status)
            if preview is None or preview.updated_utc==self._last_stamp:return
            updated=self._gui_ring.ingest_preview(preview)
            self._last_stamp=preview.updated_utc
            self._preview=preview
            ch=status["channels"][self.adc.currentData()-1]
            self.quality.setText("Контроль АЦП: "+ch["quality"]+
                " · клиентский буфер: "+
                str(self._gui_ring.channel(self.adc.currentData()).available if
                    self._gui_ring.channel(self.adc.currentData()) else 0)+
                " отсчётов · DSP: AUX4700 · FFT: APP_DERIVED")
            if updated and not self.freeze.isChecked():
                self._update_features()
                self._request_update()
        except (OSError,ValueError,KeyError,RuntimeError) as exc:
            self._clear(f"Превью отклонено: {exc}")

    def _poll_ipc(self):
        self._collect_analysis()
        self._poll_extra()
        # QApplication thread owns GUI ring. HTTP is handled ONLY by worker.
        if self._ipc_future is not None and self._ipc_future.done():
            pending=self._ipc_future
            self._ipc_future=None
            try:
                preview=pending.result()
            except IPCNotReady:
                pass  # verified source needs more real samples for selected N
            except (ValueError,OSError,TimeoutError,RuntimeError) as exc:
                self.quality.setText(f"Локальный IPC: {exc}")
                # A failed authenticated source must never be shown as a
                # successful measurement or silently substituted by stale ZIP.
            else:
                if (self._ipc_client is not None and
                    preview.session_id==self._ipc_client.session_id and
                    self._last_status is not None and
                    self._last_status.get("phase")=="RECORDING"):
                    try:
                        changed=self._gui_ring.ingest_preview(preview)
                    except ValueError as exc:
                        self._clear(f"IPC последовательность отклонена: {exc}")
                        return
                    if changed:
                        self._preview=preview
                        self._last_stamp=preview.updated_utc
                        self._last_ipc_ok=time.monotonic()
                        self.quality.setText(
                            f"Локальный Go IPC · АЦП {self.adc.currentData()} · "
                            f"реальных отсчётов {self._gui_ring.channel(self.adc.currentData()).available}"
                            " · APP_DERIVED · исходный DSP отдельно")
                        if not self.freeze.isChecked():
                            self._render_wave()
                            self._update_features()
                            self._request_update()
        if (self._ipc_client is None or self._ipc_future is not None or
            self._last_status is None or
            self._last_status.get("phase")!="RECORDING" or
            self._last_status.get("snapshot_stale") or
            self._last_status.get("capture_only") or
            self._last_status.get("source_tcp_multi_socket")):
            return
        # IPC transfers the selected ADC only, not a periodic 8 MiB ZIP.
        # Welch/1/3 octave use the extra available history when configured.
        count=min(self._gui_ring.capacity,max(8192,int(self.nfft.currentData())*(2 if self.analysis.currentData() in ("welch","asd","third_octave") else 1)))
        self._ipc_channel=self.adc.currentData()
        self._ipc_future=self._ipc_executor.submit(
            self._ipc_client.read_channel,self._ipc_channel,count)

    def _clear(self,message):
        if "kurtogram" not in getattr(self,"_modern_method_pins",{}):
            self._invalidate_kurtogram("Нет проверенных отсчётов нового сеанса")
        self._preview=None
        self._ipc_client=None
        if self.freeze.isChecked():
            self.freeze.setChecked(False)
            self.freeze.setText("Заморозить графики")
        self._freeze_samples=None
        self._freeze_rate=None
        self._freeze_channel=None
        self._freeze_session=None
        self._freeze_end=None
        self.history.setRange(0,0)
        self.history.setValue(0)
        self._gui_ring.clear()
        self._last_status=None
        self.frange_info.setText("FRange: текущая калибровка неизвестна; ожидание новой конфигурации")
        self._render_dsp()
        self._last_submitted_key=None
        self._last_fft_submit=0.0
        self._trend_points=[]
        self._trend_key=None
        self._waterfall_rows=[]
        self._waterfall_key=None
        self._spectrum=None
        self._last_stamp=None
        self._generation+=1
        self.spec_curve.setData([],[])
        self.wave_curve.setData([],[])
        self._clear_overview_plot("spectrum")
        self._clear_overview_plot("time")
        self.wave_stats.setText(
            "Временной сигнал: ожидание подтверждённого АЦП для нового сеанса")
        self.wave_info.setText(
            "Ожидание новой калиброванной записи · время в секундах, виброускорение в м/с²")
        self.metrics.setText(message)
        self.features_label.setText(
            "APP_DERIVED: ожидание реальных отсчётов АЦП")
        if "bearing" not in getattr(self,"_modern_method_pins",{}):
            self._bearing_spectrum=None
            self.bearing_curve.setData([],[])
            self.bearing_diagnostics.setText(
                "Подшипники: нет подтверждённого источника для расчёта")
            cursors=getattr(self,"_professional_cursors",None)
            if cursors is not None:
                cursors.refresh_bearing()
        self._last_result=None
        self.trend_line.setData([],[])
        self.waterfall_img.clear()
        self.extra_line.setData([],[])
        self.extra_image.clear()

    def _render_spectrum(self):
        if self._spectrum is None:
            self._clear_overview_plot("spectrum")
            return
        self._apply_axes()
        s=self._spectrum
        x=s.hz
        y=vibration_plot_values(s,self.yscale.currentData(),reference=self.db_ref.currentData())
        valid=np.isfinite(x)&np.isfinite(y)
        if self.xscale.currentData()=="log":valid &= x>0
        # Peak-preserving chart reduction: physics uses full FFT.
        ix=np.flatnonzero(valid)
        if len(ix)>5000:
            segments=np.array_split(ix,2500)
            chosen=[]
            for segment in segments:
                if len(segment):
                    chosen.extend([segment[0],segment[np.argmax(s.rms[segment])]])
            ix=np.array(sorted(set(chosen)),dtype=int)
        self.spec_curve.setData(x[ix],y[ix],connect="finite")
        overview=getattr(self,"overview_spec_curve",None)
        if overview is not None:
            overview.setData(x[ix],y[ix],connect="finite")
            plot=getattr(self,"overview_spec",None)
            if plot is not None:
                plot.setTitle(
                    f"{s.mode.upper()} · АЦП {self.adc.currentData()} · "
                    f"Fs {s.rate_hz} Гц · Δf {s.resolution_hz:.3g} Гц")
        self._apply_operator_ranges()
        self._cursor_text()
        label=({"fft":"FFT","welch":"Welch PSD",
               "asd":"ASD Уэлча","third_octave":"1/3 октавы","envelope":"Hilbert огибающая"}[s.mode])
        suffix="" if s.mode in ("welch","asd") else " СКЗ"
        base=(f"{label} · АЦП {self.adc.currentData()} · N={s.nfft} · "
              f"Δf={s.resolution_hz:g} Гц · пик {s.peak[0]:.2f} Гц / "
              f"{s.peak[1]:.5g} {s.units}{suffix} · "
              f"источник APP_DERIVED (НЕ AUX4700)")
        if self.yscale.currentData()=="db":
            ref=db_reference(s.kind,self.db_ref.currentData())
            if s.mode=="welch":
                base+=f" · дБ отн. ({ref:g} {KINDS[s.kind][1]})²/Гц"
            elif s.mode=="asd":
                base+=f" · дБ отн. {ref:g} {KINDS[s.kind][1]}/√Гц"
            else:
                base+=" · дБ отн. "+db_reference_text(s.kind,self.db_ref.currentData())
        if s.mode in ("welch","asd","third_octave"):
            base+=f" · сегментов Welch: {s.segments} · HP от {s.floor_hz:g} Гц"
        self.metrics.setText(base)

    def _cursor_text(self,*_):
        layer=getattr(self, "_professional_cursors", None)
        if layer is not None:
            if _:
                layer.on_primary_moved()
            else:
                layer.refresh_spectrum()
            return
        if self._spectrum is None:return
        f=self._spectrum.hz
        pos=float(self.cursor.value())
        if self.xscale.currentData()=="log":
            pos=10**np.clip(pos,-12,12)
        i=int(np.argmin(np.abs(f-pos)))
        value=self._spectrum.rms[i]
        unit=f"{self._spectrum.units}"+("" if self._spectrum.mode in ("welch","asd") else " СКЗ")
        if self.yscale.currentData()=="db":
            dbv=vibration_plot_values(self._spectrum,"db",reference=self.db_ref.currentData())[i]
            self.spec.setTitle(f"{self._spectrum.mode.upper()} · {f[i]:.2f} Гц · "
                               f"{dbv:.2f} дБ · {value:.5g} {unit}")
        else:
            self.spec.setTitle(f"{self._spectrum.mode.upper()} · курсор {f[i]:.2f} Гц · "
                               f"{value:.5g} {unit}")

    def _update_waterfall(self,job_key):
        if self._spectrum is None or self._spectrum.mode not in ("fft","welch","asd"):
            return
        if job_key==self._waterfall_key:
            return
        s=self._spectrum
        if len(s.hz)<2:return
        self._waterfall_key=job_key
        # A waterfall frame corresponds to one NEW source RxPos, never
        # another paint of the same ADC. Convert power to dB BEFORE color.
        db=vibration_plot_values(s,"db",reference=self.db_ref.currentData())
        idx=np.linspace(1,len(s.hz)-1,min(1024,len(s.hz)-1),dtype=int)
        row=np.nan_to_num(db[idx],nan=-180.0,neginf=-180.0,posinf=180.0)
        if self._waterfall_rows and len(self._waterfall_rows[-1])!=len(row):
            self._waterfall_rows=[]
        self._waterfall_rows.append(np.asarray(row,dtype=np.float32))
        self._waterfall_rows=self._waterfall_rows[
            -int(self.waterfall_max_frames.currentData()):]
        image=np.stack(self._waterfall_rows,axis=1)
        self.waterfall_img.setImage(image,autoLevels=False,levels=(-120,120))
        self.waterfall_img.setRect(QtCore.QRectF(0.0,0.0,
                                   float(s.hz[-1]),float(len(self._waterfall_rows))))

    def _current_window(self, minimum: int, *, for_fft: bool=True):
        """Immutable, physically contiguous window for the selected ADC.

        Freeze stops only local presentation, NOT the Native RAW recorder,
        and review never requests old packets or writes to the instrument.
        """
        adc=self.adc.currentData()
        if self.freeze.isChecked() and self._freeze_samples is not None:
            if adc!=self._freeze_channel:
                raise ValueError("Заморожен другой АЦП; сначала вернитесь в Live")
            raw=self._freeze_samples
            fs=self._freeze_rate
            offset=min(int(round(self.history.value()*fs)),len(raw))
            end=len(raw)-offset
            if end<minimum:
                raise ValueError("В выбранном участке истории недостаточно реальных отсчётов")
            key=("FROZEN",self._freeze_session,adc,self._freeze_end-offset)
            return raw[:end][-minimum:].copy(),fs,key
        ch=self._gui_ring.channel(adc)
        if ch is None or ch.available<minimum:
            raise ValueError(f"Ожидание {minimum} подтверждённых отсчётов АЦП {adc}")
        return ch.latest(minimum),ch.rate_hz,(self._gui_ring.session_id,adc,ch.end)

    def _review_changed(self,*_):
        if self.freeze.isChecked() and self._freeze_samples is not None:
            self._last_submitted_key=None
            self._last_fft_submit=0.0
            self._generation+=1
            self._render_wave()
            self._schedule_fft()
        else:
            self._render_wave()

    def _toggle_freeze(self,checked):
        if "kurtogram" not in getattr(self,"_modern_method_pins",{}):
            self._invalidate_kurtogram(
                "Режим Freeze/Live изменён: требуется новая кюртограмма")
        if checked:
            channel=self._gui_ring.channel(self.adc.currentData())
            if channel is None or channel.available<256:
                self.freeze.setChecked(False)
                self.status.setText("Для заморозки нужен подтверждённый поток АЦП")
                return
            self._freeze_samples=channel.latest(channel.available)
            self._freeze_rate=channel.rate_hz
            self._freeze_session=self._gui_ring.session_id
            self._freeze_channel=channel.number
            self._freeze_end=channel.end
            self.freeze.setText("Вернуться в Live")
            max_history=max(0.0,(len(self._freeze_samples)-256)/channel.rate_hz)
            self.history.setRange(0.0,max_history)
            self.status.setText("ЗАМОРОЖЕН ТОЛЬКО ПРОСМОТР · Native RAW продолжает запись")
        else:
            self.freeze.setText("Заморозить графики")
            self._freeze_samples=None
            self._freeze_rate=None
            self._freeze_channel=None
            self._freeze_session=None
            self._freeze_end=None
            self.history.setRange(0.0,0.0)
            self.history.setValue(0.0)
        self._last_submitted_key=None
        self._last_fft_submit=0.0
        self._generation+=1
        self._render_wave()
        self._schedule_fft()

    def _rpm_changed(self,value):
        if not self._setting_rpm_from_candidate:
            self._rpm_source="MANUAL"
            self._speed_candidate=None
            self.rpm_accept.setEnabled(False)
            self.rotation_info.setText(
                f"1×: {value/60:.3f} Гц (введено вручную)" if value>0
                else "1×: не задана; можно получить гипотезу по спектру ВС")
        # Operator RPM changes the LIVE markers, not a detached method's
        # snapshot or independently entered bearing-analysis parameters.

    def _propose_rotation(self):
        if self._speed_future is not None and not self._speed_future.done():
            return
        try:
            x,fs,key=self._current_window(self.nfft.currentData())
        except ValueError as exc:
            self.rotation_info.setText(str(exc))
            return
        self._speed_candidate=None
        self.rpm_accept.setEnabled(False)
        self.rotation_info.setText("Расчёт первой гармоники по ВС · TACH не используется")
        self._speed_future=self._extra_executor.submit(
            estimate_rotation_from_velocity,x,fs,nfft=self.nfft.currentData())

    def _accept_rotation(self):
        proposal=self._speed_candidate
        if proposal is None:
            return
        self._setting_rpm_from_candidate=True
        try:
            self.rpm.setValue(proposal.rpm)
        finally:
            self._setting_rpm_from_candidate=False
        self._rpm_source="VELOCITY_FFT_OPERATOR_ACCEPTED"
        self.rpm_accept.setEnabled(False)
        self.rotation_info.setText(
            f"1× принята оператором по ВС: {proposal.hz:.2f} Гц / "
            f"{proposal.rpm:.1f} об/мин · {proposal.confidence}. НЕ тахометр.")
        self._update_markers()

    def _archive_tab_changed(self,index):
        # Do not rebuild checkboxes while the operator is choosing a
        # multi-date overlay. New original frames appear on next tab visit
        # or after an explicit "Обновить записи".
        target=self.views.widget(index)
        if self._archive_dirty and target in (
                self.history_ui.trend_page,self.history_ui.compare_page):
            self.history_ui.refresh()
            self._archive_dirty=False

    def _queue_aux_log(self,folder,session):
        # Device decoded AUX4700 row stream is already persisted by Go.
        # This GUI reads it ONLY in bounded batches; never re-encodes RAW.
        if not isinstance(session,str) or not session:
            return
        item=(Path(folder),session)
        if item not in self._archive_jobs:
            self._archive_jobs.append(item)

    def _poll_archive_files(self):
        if not self._archive_jobs:
            return
        folder,session=self._archive_jobs[0]
        try:
            count=self._archive.sync_aux_jsonl(
                folder,session,batch=MAX_IMPORT_ROWS)
        except (OSError,ValueError,sqlite3.DatabaseError) as exc:
            self._archive_jobs.pop(0)
            self.history_ui.compare_info.setText(
                f"История AUX4700: {exc}. RAW/MВК01 не изменялись. "
                "Повторный импорт — вручную.")
            return
        if count:
            self._archive_dirty=True
            if self.views.currentWidget()==self.history_ui.trend_page:
                self.history_ui._plot_trend()
                self._archive_dirty=False
        still_recording=(self._last_status is not None and
                         self._last_status.get("session_id")==session and
                         self._last_status.get("phase")=="RECORDING" and
                         self._capture_root is not None and
                         Path(self._capture_root)==folder)
        if count<MAX_IMPORT_ROWS and not still_recording:
            self._archive_jobs.pop(0)
            self.history_ui.refresh()
            self._archive_dirty=False

    def _archive_capture_window(self):
        """One explicit operator action: freeze/history or current ADC ring."""
        try:
            adc=self.adc.currentData()
            if self.freeze.isChecked() and self._freeze_samples is not None:
                if self._freeze_channel!=adc:
                    raise ValueError(
                        "Выбран другой АЦП; нельзя смешать сохранённые каналы")
                fs=self._freeze_rate
                offset=int(round(self.history.value()*fs))
                count=len(self._freeze_samples)-offset
                if count<256:
                    raise ValueError("В историческом окне недостаточно отсчётов")
                x=self._freeze_samples[:count][-min(count,262144):].copy()
                end=self._freeze_end-offset
                session=self._freeze_session
            else:
                ch=self._gui_ring.channel(adc)
                if ch is None or ch.available<256:
                    raise ValueError("Нет подтверждённого окна АЦП")
                fs=ch.rate_hz
                end=ch.end
                session=self._gui_ring.session_id
                x=ch.latest(ch.available)
            idx=self._archive.capture_npz(
                x,adc=adc,fs=fs,session=session,capture_end=end)
            self.history_ui.refresh()
            self._archive_dirty=False
            self.history_ui.compare_info.setText(
                f"Сохранена архивная запись #{idx}, АЦП {adc}, "
                f"Fs={fs} Гц, N={len(x)}. "
                "Тренды APP_DERIVED и последующий пересчёт FFT "
                "используют те же проверенные Float32. "
                "Эта запись НЕ внешний эталон.")
            self.status.setText(
                f"Сохранено измерение в локальный архив: {self._archive.root}")
        except (OSError,ValueError,sqlite3.DatabaseError) as exc:
            QtWidgets.QMessageBox.warning(
                self,"Измерение не сохранено в историю",str(exc))

    def _archive_import_npz(self):
        name,_=QtWidgets.QFileDialog.getOpenFileName(
            self,"Импорт ранее сохранённого окна МВК01",
            "","MVK Live (*.npz)")
        if not name:return
        try:
            idx=self._archive.import_npz(name)
            self.history_ui.refresh()
            self._archive_dirty=False
            self.history_ui.compare_info.setText(
                f"Запись #{idx} добавлена в каталог: {self._archive.root}. "
                "Файл проверен по SHA содержимого. "
                "Время — время архивирования, не выдуманное время прибора.")
        except (OSError,ValueError,sqlite3.DatabaseError) as exc:
            QtWidgets.QMessageBox.warning(
                self,"Импорт NPZ отклонён",str(exc))

    def _archive_import_aux(self):
        folder=QtWidgets.QFileDialog.getExistingDirectory(
            self,"Каталог предыдущего сеанса Native Go с aux4700.jsonl",
            str(self._archive.root.parent))
        if not folder:return
        path=Path(folder)
        if not (path/"aux4700.jsonl").is_file():
            QtWidgets.QMessageBox.warning(
                self,"Импорт AUX4700",
                "В каталоге нет исходного журнала aux4700.jsonl")
            return
        self._queue_aux_log(path,path.name)
        self.history_ui.compare_info.setText(
            f"Импорт исходного AUX4700 из {path} запущен "
            f"(не более {MAX_IMPORT_ROWS} строк за один проход). "
            "Прошлые измерения добавляются по исходному времени и АЦП.")
        self._poll_archive_files()

    def _save_snapshot(self):
        try:
            if self.freeze.isChecked() and self._freeze_samples is not None:
                x=self._freeze_samples.copy()
                rate=self._freeze_rate
                session=self._freeze_session
                end=self._freeze_end
                adc=self._freeze_channel
            else:
                ch=self._gui_ring.channel(self.adc.currentData())
                if ch is None or ch.available<256:
                    raise ValueError("Нет подтверждённых отсчётов для сохранения")
                x=ch.latest(ch.available)
                rate=ch.rate_hz
                session=self._gui_ring.session_id
                end=ch.end
                adc=ch.number
            name,_=QtWidgets.QFileDialog.getSaveFileName(
                self,"Сохранить калиброванный фрагмент",
                "MVK_Live_Window.npz","MVK Live (*.npz)")
            if not name:return
            out=save_snapshot(name,x,adc=adc,rate_hz=rate,
                              session_id=session,capture_end=end)
            # The file chosen by the operator remains intact; a checked
            # immutable copy also enters history/trends automatically.
            self._archive.import_npz(out)
            self._archive_dirty=True
            self.history_ui.refresh()
            self.status.setText(
                f"Сохранён локальный фрагмент и добавлен в архив: {out}")
        except (OSError,ValueError,FileExistsError) as exc:
            QtWidgets.QMessageBox.warning(self,"Сохранение не выполнено",str(exc))

    def _open_snapshot(self):
        if self._native.state()!=QtCore.QProcess.ProcessState.NotRunning:
            QtWidgets.QMessageBox.warning(
                self,"Нельзя сменить источник","Сначала остановите текущую Native запись")
            return
        file,_=QtWidgets.QFileDialog.getOpenFileName(
            self,"Открыть локальное окно MVK Live","","MVK Live (*.npz)")
        if not file:return
        try:
            record=load_snapshot(file)
            self._archive.import_npz(file)
            self._archive_dirty=True
            self.history_ui.refresh()
            # A local hash detects accidental archive corruption, not original
            # MVK origin. The independent OFFLINE session avoids implying
            # the receiver is still measuring or connected to the instrument.
            session="OFFLINE_"+record.sha256[:20]
            adc=record.adc
            data=record.acceleration_m_s2
            preview=IPCPreview(session,DOMAIN,True,datetime.now(timezone.utc),{
                adc: IPCChannel(adc,record.rate_hz,data,
                    record.capture_end%(1<<32),record.capture_end,
                    record.sha256)})
            self._capture_root=None
            self._active_ip=None
            self._local_ip=None
            self._ipc_client=None
            self._last_status=None
            self._gui_ring.clear()
            self._gui_ring.ingest_preview(preview)
            self._preview=preview
            if self.freeze.isChecked():
                self.freeze.setChecked(False)
                self._toggle_freeze(False)
            self.adc.setCurrentIndex(adc-1)
            self._waterfall_rows=[]
            self._waterfall_key=None
            self._trend_points=[]
            self._trend_key=None
            self._on_control_change()
            self.status.setText(
                f"OFFLINE · локальная запись АЦП {adc}, Fs={record.rate_hz}; "
                "не эталон и не активное соединение МВК01")
            self.quality.setText(
                "OFFLINE · SHA внутреннего файла проверен; происхождение от прибора не заверяется")
        except (OSError,ValueError,KeyError,RuntimeError) as exc:
            QtWidgets.QMessageBox.warning(self,"Запись отклонена",str(exc))

    def _export_csv(self):
        if self._spectrum is None:
            self.status.setText("Нет вычисленного спектра для CSV")
            return
        path,_=QtWidgets.QFileDialog.getSaveFileName(
            self,"Сохранить рассчитанный спектр","","CSV (*.csv)")
        if not path:return
        try:
            view=self._spectrum
            s=save_spectrum_csv(
                path,view.hz,view.rms,
                vibration_plot_values(view,self.yscale.currentData(),
                                     reference=self.db_ref.currentData()),
                mode=view.mode,unit=view.units,
                scale=self.yscale.currentData(),reference=self.db_ref.currentData(),
                adc=self.adc.currentData(),
                session_id=self._gui_ring.session_id or "NO_SESSION")
            self.status.setText(f"CSV экспортирован: {s} (APP_DERIVED, без эталонов)")
        except (OSError,ValueError,FileExistsError) as exc:
            QtWidgets.QMessageBox.warning(self,"CSV не сохранён",str(exc))

    def _export_plot_png(self):
        if self._spectrum is None:
            self.status.setText("Нет графика для PNG")
            return
        path,_=QtWidgets.QFileDialog.getSaveFileName(
            self,"Сохранить изображение спектра","","PNG (*.png)")
        if not path:return
        try:
            from pyqtgraph.exporters import ImageExporter
            exporter=ImageExporter(self.spec.plotItem)
            exporter.parameters()["width"]=1920
            exporter.export(path)
            self.status.setText(f"График сохранён: {path}")
        except (OSError,ValueError,RuntimeError) as exc:
            QtWidgets.QMessageBox.warning(self,"PNG не сохранён",str(exc))

    def _show_severity(self):
        result=self._last_result
        if result is None or result.broadband_velocity is None or (
                not result.broadband_velocity.valid):
            self.status.setText("Для оценки требуется полноценная ВС СКЗ 10–1000 Гц")
            return
        options=["Класс 1","Класс 2","Класс 3","Класс 4"]
        selected,ok=QtWidgets.QInputDialog.getItem(
            self,"Справочная диаграмма ISO 10816-3",
            "Класс и область применения машины должны быть известны оператору.",
            options,0,False)
        if not ok:return
        try:
            v=result.broadband_velocity
            out=indicative_iso10816_zone(
                v.rms,machine_class=options.index(selected)+1,
                rpm=self.rpm.value(),
                measured_band_hz=(v.low_hz,v.high_hz))
        except ValueError as exc:
            self.status.setText(f"Оценка неприменима: {exc}")
            return
        QtWidgets.QMessageBox.information(
            self,"Справочная оценка (НЕ аттестация)",
            f"Скорость {out.velocity_rms_mm_s:.3g} мм/с СКЗ; класс {out.machine_class}, "
            f"ориентировочная зона {out.zone} по исторической ISO 10816-3.\n"
            "Не является проверкой по эталонному измерению, "
            "официальной оценкой ISO 20816 или диагнозом."
        )

    def _run_bearing_page(self):
        """Calculate in the detached window; never change the main FFT.

        A modern bearing window requires an operator-pinned, SHA-verified
        ADC copy. Changing the global ADC, Freeze or incoming RX data later
        cannot change this input. FRange is already applied by Native Go.
        """
        try:
            nfft=int(self.bearing_fft.currentData())
            band=self.bearing_resonance.currentData()
            if not isinstance(band,(tuple,list)) or len(band)!=2:
                raise ValueError("Выберите корректную полосу огибающей")
            pinned=getattr(self,"_modern_method_pins",{}).get("bearing")
            if pinned is not None:
                source=pinned["samples"]
                fs=int(pinned["fs"])
                if len(source)<nfft:
                    raise ValueError(
                        "FFT N больше закреплённой выборки; нажмите "
                        "«Взять новое текущее окно АЦП»")
            elif getattr(self,"_modern_installed",False):
                raise ValueError(
                    "Источник не закреплён. Нажмите «Взять новое текущее "
                    "окно АЦП» в окне подшипников")
            else:
                source,fs,_=self._current_window(nfft)
            view=analyze_vibration(
                source,int(fs),kind="acceleration",mode="envelope",nfft=nfft,
                envelope_band_hz=(float(band[0]),float(band[1])))
        except (ValueError,TypeError,IndexError) as exc:
            self._bearing_spectrum=None
            self.bearing_curve.setData([],[])
            cursors=getattr(self,"_professional_cursors",None)
            if cursors is not None:
                cursors.refresh_bearing()
            self.bearing_diagnostics.setText(f"Огибающая не рассчитана: {exc}")
            return
        self._bearing_spectrum=view
        self.bearing_plot.enableAutoRange()
        self._show_bearing_diagnostics()

    def _refresh_gear_table(self,*_):
        if self.rpm.value()<=0 or self.gear_teeth.value()<=0:
            self.gear_table.setRowCount(0)
            self.gear_note.setText(
                "Укажите вручную или подтвердите обороты и число зубьев; "
                "тахометр не используется.")
            return
        try:
            result=gear_mesh_markers(self.rpm.value(),self.gear_teeth.value())
        except ValueError as exc:
            self.gear_table.setRowCount(0)
            self.gear_note.setText(f"Некорректные параметры: {exc}")
            return
        rows=[("GMF",result.mesh_hz)]
        rows.extend((f"{i}×GMF",freq) for i,freq in
                    enumerate(result.harmonics_hz[1:],start=2))
        rows.extend((f"GMF боковая полоса {i+1}",freq)
                    for i,freq in enumerate(result.sidebands_hz))
        self.gear_table.setRowCount(len(rows))
        for r,(label,freq) in enumerate(rows):
            for c,value in enumerate((label,f"{freq:.6g}")):
                item=QtWidgets.QTableWidgetItem(value)
                item.setToolTip(
                    "APP_DERIVED: ожидаемая частота, не реально измеренный пик")
                self.gear_table.setItem(r,c,item)
        self.gear_note.setText(
            "APP_DERIVED · теоретические GMF, гармоники и боковые полосы "
            "по введённым 1×/числу зубьев; не эталон и не диагноз.")

    def _show_bearing_diagnostics(self,*_):
        view=self._bearing_spectrum
        if view is None or view.mode!="envelope":
            self.bearing_curve.setData([],[])
            cursors=getattr(self,"_professional_cursors",None)
            if cursors is not None:
                cursors.refresh_bearing()
            self.bearing_diagnostics.setText(
                "Нажмите «Рассчитать огибающую» по закреплённому АЦП.")
            return
        self.bearing_curve.setData(view.hz,view.rms)
        cursors=getattr(self,"_professional_cursors",None)
        if cursors is not None:
            cursors.refresh_bearing()
        pinned=getattr(self,"_modern_method_pins",{}).get("bearing")
        source_label=(f"АЦП {pinned['adc']} · " if pinned is not None
                      else "текущее окно · ")
        self.bearing_plot.setTitle(
            f"APP_DERIVED · FFT огибающей · {source_label}Fs={view.rate_hz} Гц")
        if self.bearing_rpm.value()<=0 or self.bearing_balls.value()<3:
            self.bearing_diagnostics.setText(
                "Подшипники: задайте в этом окне 1× и геометрию. "
                "Без TACH; один спектр не является диагнозом.")
            return
        try:
            lines=envelope_fault_lines(
                view,float(self.bearing_rpm.value()),
                balls=int(self.bearing_balls.value()),
                ball_diameter_mm=float(self.bearing_ball_diameter.value()),
                pitch_diameter_mm=float(self.bearing_pitch_diameter.value()),
                contact_angle_deg=float(self.bearing_contact_angle.value()))
        except (ValueError,TypeError) as exc:
            self.bearing_diagnostics.setText(
                f"Геометрия/спектр ещё не готовы: {exc}")
            return
        observations=[]
        for item in lines:
            status="выделяется" if item.noteworthy else "не выделяется"
            observations.append(
                f"{item.label} {item.expected_hz:.1f} Гц: {item.snr_db:.1f} дБ, "
                f"гарм. {item.harmonics_found} ({status})")
        self.bearing_diagnostics.setText(
            "APP_DERIVED · измеренный спектр закреплённого окна; "
            "локальный SNR, НЕ диагноз и НЕ эталон · "+
            ("; ".join(observations) if observations else "Нет разрешённых линий")
        )

    def _invalidate_kurtogram(self,reason: str):
        self._kurt_result=None
        self._kurt_selected=None
        self.kurtogram_img.clear()
        self.kurtogram_marker.setData([],[])
        self.kurtogram_best.setEnabled(False)
        self.kurtogram_apply.setEnabled(False)
        self.kurtogram_plot.setTitle("Fast Kurtogram · нет расчёта этого АЦП")
        self.kurtogram_info.setText(reason)

    def _calculate_kurtogram(self):
        if self._kurt_future is not None and not self._kurt_future.done():
            return
        try:
            length=int(self.kurtogram_window.currentData())
            pinned=getattr(self,"_modern_method_pins",{}).get("kurtogram")
            if pinned is not None:
                if len(pinned["samples"])<length:
                    raise ValueError("Окно больше зафиксированной выборки; выберите новый источник")
                samples=pinned["samples"][-length:].copy()
                fs,stamp=pinned["fs"],pinned["stamp"]
            elif "kurtogram" in getattr(self,"_modern_windows",{}):
                raise ValueError("Источник отсутствует. Выберите новый источник в окне")
            else:
                samples,fs,stamp=self._current_window(length)
            level=int(self.kurtogram_levels.currentData())
            # Once the window was copied, heavy FIR processing runs OFF the
            # Qt thread; the hardware, Go RX and AUX4700 never change.
            self._invalidate_kurtogram(
                f"Fast Kurtogram: вычисление {length} реальных отсчётов "
                f"АЦП {self.adc.currentData()} · Fs={fs} · уровень {level}")
            self._kurt_adc=(pinned["adc"] if pinned else self.adc.currentData())
            self._kurt_session=(pinned["session"] if pinned else self._gui_ring.session_id)
            self._kurt_frozen=(pinned["frozen"] if pinned else self.freeze.isChecked())
            self._kurt_is_pinned=pinned is not None
            self._kurt_rx_key=stamp
            self._kurt_future=self._extra_executor.submit(
                compute_fast_kurtogram,samples,fs,nlevel=level)
            self.kurtogram_run.setEnabled(False)
        except (ValueError,TypeError) as exc:
            self.kurtogram_info.setText(f"Кюртограмма: {exc}")

    def _poll_kurtogram(self):
        if self._kurt_future is None or not self._kurt_future.done():
            return
        job=self._kurt_future
        self._kurt_future=None
        self.kurtogram_run.setEnabled(True)
        try:
            result=job.result()
        except (ValueError,RuntimeError,FloatingPointError) as exc:
            self._invalidate_kurtogram(f"Fast Kurtogram отклонён: {exc}")
            return
        if (not getattr(self,"_kurt_is_pinned",False) and
                (self._kurt_adc!=self.adc.currentData() or
                 self._kurt_session!=self._gui_ring.session_id or
                 self._kurt_frozen!=self.freeze.isChecked())):
            self._invalidate_kurtogram(
                "АЦП, сеанс или режим просмотра изменились: результат "
                "прежнего снимка отброшен")
            return
        self._display_kurtogram(result)

    def _display_kurtogram(self,result: KurtogramResult):
        self._kurt_result=result
        # PySDKit scores rows = levels, columns = frequency. Pyqtgraph
        # images have horizontal samples in their FIRST axis.
        scores=np.ascontiguousarray(result.scores.T,dtype=np.float32)
        max_k=max(1.,float(result.best_score))
        self.kurtogram_img.setImage(
            scores,autoLevels=False,levels=(0.,max_k))
        self.kurtogram_img.setRect(QtCore.QRectF(
            0.,0.,result.fs/2.,result.scores.shape[0]))
        self.kurtogram_bar.setLevels((0.,max_k))
        axis_ticks=[(i+.5,f"{level:.2f}") for i,level in
                    enumerate(result.levels)]
        self.kurtogram_plot.getAxis("left").setTicks([axis_ticks])
        self.kurtogram_plot.setXRange(0,result.fs/2.,padding=0)
        self.kurtogram_plot.setYRange(0,result.scores.shape[0],padding=0)
        self.kurtogram_plot.setTitle(
            f"PySDKit Fast Kurtogram · АЦП {self._kurt_adc} · "
            f"Fs={result.fs} Гц · N={result.n_samples} · APP_DERIVED "
            f"· снято на RxPos {self._kurt_rx_key[-1] if self._kurt_rx_key else '?'}")
        self.kurtogram_best.setEnabled(True)
        self._pick_kurt_cell(result.best_row,result.best_col)

    def _pick_kurt_cell(self,row:int,col:int):
        view=self._kurt_result
        if view is None:return
        try:
            low,high,fc,bw,score=view.cell_band(row,col)
        except ValueError:
            return
        self._kurt_selected=(row,col)
        self.kurtogram_marker.setData([fc],[row+.5])
        self.kurtogram_apply.setEnabled(score>0)
        self.kurtogram_info.setText(
            f"PySDKit Fast Kurtogram · АЦП {self._kurt_adc} · "
            f"центр {fc:.1f} Гц · ширина {bw:.1f} Гц · "
            f"полоса {low:.1f}–{high:.1f} Гц · "
            f"эксцесс SK={score:.3g} · уровень k={view.levels[row]:.2f}. "
            "Выбор полосы локальный; импульсность НЕ означает дефект.")

    def _select_kurt_best(self):
        if self._kurt_result is not None:
            self._pick_kurt_cell(
                self._kurt_result.best_row,self._kurt_result.best_col)

    def _kurtogram_clicked(self,event):
        if (self._kurt_result is None or
                event.button()!=QtCore.Qt.MouseButton.LeftButton):
            return
        vb=self.kurtogram_plot.getViewBox()
        if not vb.sceneBoundingRect().contains(event.scenePos()):
            return
        p=vb.mapSceneToView(event.scenePos())
        view=self._kurt_result
        row=int(math.floor(p.y()))
        col=int(math.floor(p.x()/(view.fs/2.)*view.scores.shape[1]))
        self._pick_kurt_cell(row,col)

    def _apply_kurt_band(self):
        view=self._kurt_result
        selected=self._kurt_selected
        if view is None or selected is None:
            return
        if (self._kurt_adc!=self.adc.currentData() or
                self._kurt_session!=self._gui_ring.session_id or
                self._kurt_frozen!=self.freeze.isChecked()):
            self._invalidate_kurtogram(
                "Результат другого АЦП/сеанса не может выбирать фильтр")
            return
        low,high,fc,bw,score=view.cell_band(*selected)
        if score<=0:
            self.kurtogram_info.setText(
                "Ненулевая импульсность не найдена: автоматический выбор недоступен")
            return
        # Reuse the existing Hilbert-envelope spectrum, not a second
        # allegedly OEM spectrum or the decimated PySDKit envelope.
        label=f"Fast Kurtogram: {low:.1f}–{high:.1f} Гц"
        # A kurtogram band is a suggestion for the DETACHED bearing method,
        # not a request to change the primary LIVE envelope/FFT controls.
        combo=self.bearing_resonance
        for i in range(combo.count()-1,-1,-1):
            if combo.itemText(i).startswith("Fast Kurtogram:"):
                combo.removeItem(i)
        combo.addItem(label,(low,high))
        combo.setCurrentIndex(combo.count()-1)
        if getattr(self,"_modern_installed",False):
            open_advanced_window(self,"bearing")
        else:
            self.views.setCurrentWidget(self.extra_panel)
            self.extra_pages.setCurrentWidget(self.diagnostics_page)
        self._run_bearing_page()
        self.kurtogram_info.setText(
            f"Полоса {low:.1f}–{high:.1f} Гц передана в локальную "
            "Hilbert-огибающую; частотная карта рассчитана PySDKit. "
            "Обе операции APP_DERIVED, не заводской алгоритм МВК01.")

    def _start_extra_mode(self,mode):
        if mode not in self.extra_method_pages:
            raise ValueError("Неизвестный дополнительный метод")
        self.extra_mode.setCurrentIndex(self.extra_mode.findData(mode))
        self._calculate_extra()

    def _calculate_extra(self):
        if self._extra_future is not None and not self._extra_future.done():
            return
        mode=self.extra_mode.currentData()
        try:
            pinned=getattr(self,"_modern_method_pins",{}).get(mode)
            if pinned is not None:
                fs=pinned["fs"]
                data=pinned["samples"].copy()
                requested_adc=pinned["adc"]
            elif mode in getattr(self,"_modern_windows",{}):
                raise ValueError("Нет зафиксированного источника. Нажмите «Взять новое текущее окно АЦП»")
            else:
                ch=self._gui_ring.channel(self.adc.currentData())
                if self.freeze.isChecked() and self._freeze_samples is not None:
                    fs=self._freeze_rate
                    limit=len(self._freeze_samples)-int(self.history.value()*fs)
                    if limit<1024:raise ValueError("Недостаточно сохранённых отсчётов")
                    data=self._freeze_samples[max(0,limit-32768):limit].copy()
                else:
                    if ch is None or ch.available<1024:
                        raise ValueError("Недостаточно подтверждённых отсчётов")
                    fs=ch.rate_hz
                    data=ch.latest(min(ch.available,32768))
                requested_adc=self.adc.currentData()
            data=data[-min(len(data),
                           self.extra_method_windows[mode].currentData()):]
            if mode=="stft":
                work=stft_vibration
                kwargs={"nperseg":self.stft_nperseg.currentData()}
            elif mode=="cwt":
                work=cwt_morlet_vibration
                kwargs={"scales":self.cwt_scales.currentData(),
                        "min_frequency_hz":self.cwt_min_hz.value()}
            else:
                work=real_cepstrum
                kwargs={}
            self._extra_kind=mode
            self._extra_request_adc=requested_adc
            self._extra_request_pinned=pinned is not None
            self._extra_future=self._extra_executor.submit(work,data,fs,**kwargs)
            for button in self.extra_method_buttons.values():
                button.setEnabled(False)
            self.extra_method_infos[mode].setText(
                f"Расчёт по N={len(data)}, Fs={fs} Гц · APP_DERIVED")
            self.status.setText(f"Расчёт {mode.upper()} по текущему окну (без эталонов)")
        except (ValueError,RuntimeError) as exc:
            self.status.setText(f"Дополнительный анализ: {exc}")

    def _poll_extra(self):
        self._poll_kurtogram()
        if self._speed_future is not None and self._speed_future.done():
            pending=self._speed_future
            self._speed_future=None
            try:
                candidate=pending.result()
            except (ValueError,RuntimeError,FloatingPointError) as exc:
                self._speed_candidate=None
                self.rpm_accept.setEnabled(False)
                self.rotation_info.setText(f"1× по спектру ВС не определена: {exc}")
            else:
                self._speed_candidate=candidate
                self.rpm_accept.setEnabled(True)
                self.rotation_info.setText(candidate.description)
        if self._extra_future is None or not self._extra_future.done():
            return
        pending=self._extra_future
        self._extra_future=None
        for button in self.extra_method_buttons.values():
            button.setEnabled(True)
        try:
            view=pending.result()
        except (ValueError,RuntimeError,FloatingPointError) as exc:
            self.extra_method_infos[self._extra_kind].setText(
                f"Расчёт отклонён: {exc}. Данные прибора не изменены.")
            self.status.setText(f"Специальный анализ: {exc}")
            return
        mode=self._extra_kind
        if (not getattr(self,"_extra_request_pinned",False)
                and self._extra_request_adc!=self.adc.currentData()):
            self.extra_method_infos[mode].setText(
                "За время расчёта АЦП изменён: старый результат "
                "отброшен, чтобы не смешивать каналы.")
            return
        plot=self.extra_method_plots[mode]
        image=self.extra_method_images[mode]
        line=self.extra_method_lines[mode]
        if getattr(self,"_modern_installed",False):
            open_advanced_window(self,mode)
        else:
            self.views.setCurrentWidget(self.extra_panel)
            self.extra_pages.setCurrentWidget(self.extra_method_pages[mode])
        if mode=="cepstrum":
            image.clear()
            line.setData(view.quefrency_s,view.magnitude)
            plot.setLabel("bottom","Кэфренция",units="с")
            plot.setLabel("left","Вещественный кепстр",units="отн.")
            plot.setTitle(view.description)
            plot.setXRange(0,self.cepstrum_max_s.value(),padding=0)
        else:
            line.setData([],[])
            mag=view.magnitude
            if view.calibrated_amplitude:
                values=20*np.log10(np.maximum(mag,1e-15)/1e-6)
                plot.setTitle(view.description+" · дБ отн. 10⁻⁶ м/с²")
            else:
                values=20*np.log10(
                    np.maximum(mag,1e-15)/max(float(np.max(mag)),1e-15))
                plot.setTitle(view.description+" · дБ отн. локального максимума")
            image.setImage(
                np.asarray(values,dtype=np.float32),
                autoLevels=False,levels=(-120,120))
            t=view.time_s
            freqs=view.frequency_hz
            width=max(float(t[-1]-t[0]),1e-9)
            height=max(float(freqs[-1]-freqs[0]),1e-9)
            image.setRect(QtCore.QRectF(float(t[0]),float(freqs[0]),
                                        width,height))
            plot.setLabel("bottom","Время",units="с")
            plot.setLabel("left","Частота",units="Гц")
            plot.enableAutoRange()
        self.extra_method_infos[mode].setText(
            f"{view.description} · APP_DERIVED · результат отдельного метода "
            "из проверенного окна; без внешнего эталона.")
        self.status.setText(
            f"Дополнительный анализ {mode.upper()} · APP_DERIVED, без внешнего эталона")

    def _edit_axes(self):
        dlg=QtWidgets.QDialog(self)
        dlg.setWindowTitle("Ручные пределы графика · по физическим координатам")
        form=QtWidgets.QFormLayout(dlg)
        unit_description=self.spec.getPlotItem().getAxis("left").label.toPlainText().strip()
        note=QtWidgets.QLabel(
            f"Частоты — в Гц; значения — {unit_description or 'в единицах выбранного спектра'}.")
        note.setWordWrap(True)
        form.addRow(note)
        axis=[]
        mode=self.yscale.currentData()
        for name,value in [
            ("Частота от, Гц",1.0 if self.xscale.currentData()=="log" else 0.0),
            ("Частота до, Гц",1000.0),
            ("Уровень от",-120.0 if mode=="db" else 0.0),
            ("Уровень до",80.0 if mode=="db" else 10.0)]:
            box=QtWidgets.QDoubleSpinBox(dlg)
            box.setDecimals(3)
            box.setRange(-1e12,1e12)
            box.setValue(value)
            form.addRow(name,box)
            axis.append(box)
        buttons=QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok|
            QtWidgets.QDialogButtonBox.Cancel,dlg)
        form.addRow(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec()!=QtWidgets.QDialog.DialogCode.Accepted:return
        xmin,xmax,ymin,ymax=[w.value() for w in axis]
        if xmin>=xmax or ymin>=ymax or (
                self.xscale.currentData()=="log" and xmin<=0):
            self.status.setText("Неверные пределы: частота от должна быть меньше частоты до; верхний уровень выше нижнего; для логарифмической частоты начало > 0 Гц")
            return
        if self.xscale.currentData()=="log":
            xmin,xmax=math.log10(xmin),math.log10(xmax)
        self._manual_spec_axes=(xmin,xmax,ymin,ymax)
        self.spec.setXRange(xmin,xmax,padding=0)
        self.spec.setYRange(ymin,ymax,padding=0)
        self.status.setText("Ручной масштаб сохранён до явного автомасштаба")

    def showEvent(self,event):
        super().showEvent(event)
        # Normal visible Windows launch: auto-fill without a manual NIC list.
        # Headless CI runs deterministic injected tests instead of probing
        # the runner's network adapters or contacting any remote endpoint.
        if (not self._ethernet_detection_started and sys.platform=="win32"
                and self._capture_root is None
                and str(__import__("os").environ.get("QT_QPA_PLATFORM","")).lower()!="offscreen"):
            self._ethernet_detection_started=True
            QtCore.QTimer.singleShot(0,self._begin_ethernet_discovery)

    def _on_manual_ethernet_address(self,*_):
        # Only textEdited is connected, not textChanged; setText by our
        # verified OS discovery must not mark itself as a manual override.
        self._ethernet_manual_override=True
        self.ethernet_info.setText(
            "Локальный IPv4 введён вручную. Native Go всё равно проверит "
            "принадлежность IPv4 активному интерфейсу перед TCP Connect.")

    def _begin_ethernet_discovery(self,*_):
        if self._native.state()!=QtCore.QProcess.ProcessState.NotRunning:
            return
        if self._ethernet_future is not None and not self._ethernet_future.done():
            return
        self._ethernet_manual_override=False
        self._ethernet_detected=None
        self.ethernet_info.setText(
            "Определение одной проводной Ethernet-карты Windows и её IPv4… "
            "К МВК01 не подключаемся.")
        self.ethernet_refresh.setEnabled(False)
        self._ethernet_future=self._ethernet_executor.submit(
            discover_single_wired_ethernet)
        self._ethernet_timer.start()

    def _collect_ethernet_discovery(self):
        future=self._ethernet_future
        if future is None or not future.done():
            return
        self._ethernet_timer.stop()
        self._ethernet_future=None
        self.ethernet_refresh.setEnabled(
            self._native.state()==QtCore.QProcess.ProcessState.NotRunning)
        try:
            nic=future.result()
        except (ValueError,OSError,RuntimeError) as exc:
            self._ethernet_detected=None
            self.ethernet_info.setText(
                f"Ethernet IPv4 не выбран автоматически: {exc} "
                "Можно ввести адрес проводной карты вручную.")
            return
        if not isinstance(nic,WiredEthernet):
            self.ethernet_info.setText("Windows вернула неверное описание Ethernet")
            return
        self._ethernet_detected=nic
        if not self._ethernet_manual_override:
            self.local_ip.setText(nic.ipv4)
            self.ethernet_info.setText(
                "Обнаружен проводной Ethernet: "+nic.description+
                ". Локальный IPv4 подставлен автоматически.")
        else:
            self.ethernet_info.setText(
                "Обнаружен Ethernet: "+nic.description+
                ". Ручной адрес не изменён.")

    @staticmethod
    def _canonical_ipv4(value:str)->str:
        ip=ipaddress.IPv4Address(value)
        if str(ip)!=value or ip.is_loopback or ip.is_multicast or ip.is_unspecified or ip.is_link_local:
            raise ValueError("Некорректный IPv4")
        return value

    @staticmethod
    def _verify_native(exe:str,sha_file:str)->Path:
        p=Path(exe)
        manifest=Path(sha_file)
        if (p.is_symlink() or manifest.is_symlink() or not p.is_file()
                or not manifest.is_file() or p.suffix.lower()!=".exe"):
            raise ValueError("Native EXE и его SHA256-файл обязательны")
        expected=manifest.read_text(encoding="ascii").strip().split()[0].lower()
        if len(expected)!=64 or any(c not in "0123456789abcdef" for c in expected):
            raise ValueError("Некорректный SHA256")
        checksum=hashlib.sha256(p.read_bytes()).hexdigest()
        if checksum!=expected:raise ValueError("SHA256 Native R6.1 не совпадает")
        return p

    def start_native(self):
        if self._native.state()!=QtCore.QProcess.ProcessState.NotRunning:return
        try:
            ip=self._canonical_ipv4(self.device_ip.text())
            local=self._canonical_ipv4(self.local_ip.text())
            if ip==local:raise ValueError("IP прибора и компьютера должны различаться")
            if (self._ethernet_detected is not None and
                    local != self._ethernet_detected.ipv4):
                raise ValueError(
                    "Введённый локальный IPv4 не совпадает с единственным "
                    "обнаруженным Ethernet. Нажмите «Обновить Ethernet».")
            exe=self._verify_native(self.exe_path.text(),self.exe_sha.text())
        except (ValueError,OSError,UnicodeError) as exc:
            QtWidgets.QMessageBox.warning(self,"Подключение запрещено",str(exc))
            return
        reply=QtWidgets.QMessageBox.question(
            self,"Допуск к прибору",
            f"Разрешено подключиться по TCP/10230 к {ip} через Ethernet {local}" +
            (f" ({self._ethernet_detected.name}, #{self._ethernet_detected.if_index})?\n"
             if self._ethernet_detected else " (локальный IPv4 указан вручную)?\n") +
            "Клиент не отправляет прикладных команд, но сам TCP Connect может "
            "изменить состояние МВК01. Максимальный RAW: 2048 МиБ.",
            QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No,QtWidgets.QMessageBox.No)
        if reply!=QtWidgets.QMessageBox.Yes:return
        self._clear("Запуск нового подтверждённого приёма")
        root=Path(tempfile.mkdtemp(prefix="mvk_live_",dir=str(Path.home())))
        self._capture_root=root
        self._active_ip=ip
        self._local_ip=local
        stop=(root/".mvk_stop_requested").resolve()
        args=["-ip",ip,"-local-ip",local,"-seconds","0",
              "-max-mb",str(MAX_CAPTURE_MB),"-out",str(root),
              "-approve=true","-export=true","-live-status=true",
              "-live-ipc=true",
              "-stop-file",str(stop)]
        self._native.start(str(exe),args)
        self.stop_button.setEnabled(True)
        self.connect_button.setEnabled(False)
        self.ethernet_refresh.setEnabled(False)

    def stop_native(self):
        if self._native.state()==QtCore.QProcess.ProcessState.NotRunning:return
        if self._capture_root is None:return
        stop=self._capture_root/".mvk_stop_requested"
        try:
            with stop.open("x",encoding="ascii") as f:f.write("STOP\n")
            self.status.setText("Запрошена штатная остановка; завершается RAW/BIN")
        except (OSError,ValueError) as exc:
            QtWidgets.QMessageBox.warning(self,"Остановка",str(exc))
        self.stop_button.setEnabled(False)

    def _native_finished(self,exit_code,exit_status):
        self.connect_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.ethernet_refresh.setEnabled(True)
        self.status.setText(f"Native завершён (код {exit_code}); папка: {self._capture_root}")

    def closeEvent(self,event):
        if self._native.state()!=QtCore.QProcess.ProcessState.NotRunning:
            QtWidgets.QMessageBox.warning(self,"Запись ещё идёт",
                "Сначала нажмите «Остановить», дождитесь завершения Native и повторите закрытие.")
            event.ignore()
            return
        if hasattr(self,"_modern_status_timer"):
            self._modern_status_timer.stop()
        for extra in getattr(self,"_modern_windows",{}).values():
            extra.close()
        self._timer.stop()
        self._ipc_timer.stop()
        self._ethernet_timer.stop()
        self._archive_timer.stop()
        # Do not leave NumPy/SciPy workers alive while the PySide6 interpreter
        # is tearing down: this can cause native Qt reference-count crashes.
        self._executor.shutdown(wait=True,cancel_futures=True)
        self._ipc_executor.shutdown(wait=True,cancel_futures=True)
        self._extra_executor.shutdown(wait=True,cancel_futures=True)
        self._ethernet_executor.shutdown(wait=True,cancel_futures=True)
        if self._archive_temp is not None:
            self._archive_temp.cleanup()
            self._archive_temp=None
        super().closeEvent(event)


def main(argv=None):
    ap=argparse.ArgumentParser(description="MVK Live standalone, Native R6.1 sidecar viewer")
    ap.add_argument("--capture-root",type=Path,help="watch an already approved Native R6.1 session")
    ap.add_argument("--archive-root",type=Path,help="persistent local measurement archive (SQLite+NPZ)")
    options=ap.parse_args(argv)
    app=QtWidgets.QApplication([])
    window=LiveWindow(capture_root=options.capture_root,
                      archive_root=options.archive_root)
    window.show()
    return app.exec()


if __name__=="__main__":
    raise SystemExit(main())
