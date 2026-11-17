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
    calculate_spectrum, plot_values, y_axis_label, db_reference_text,
)
from .live_ring import VerifiedLiveRing
from .live_ipc import discover_local_ipc, IPCNotReady, IPCPreview, IPCChannel, DOMAIN
from .original_dsp import read_original_dsp_bands
from .rotation import estimate_rotation_from_velocity
from .pipeline import analyze_live, AnalysisResult
from .advanced import (envelope_fault_lines, stft_vibration,
                       cwt_morlet_vibration, real_cepstrum,
                       gear_mesh_markers, indicative_iso10816_zone)
from .recordings import save_snapshot, load_snapshot, save_spectrum_csv
from .vibration import (
    VibrationView, analyze_vibration, vibration_plot_values,
    vibration_y_label, time_features, bearing_frequency_markers,
)

MAX_CAPTURE_MB = 2048


class LiveWindow(QtWidgets.QMainWindow):
    def __init__(self, capture_root: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("MVK Live · Независимый анализатор спектра")
        self.resize(1380, 870)
        self._capture_root = capture_root
        self._active_ip = None
        self._local_ip = None
        self._last_stamp = None
        self._preview = None
        self._gui_ring = VerifiedLiveRing()
        self._last_submitted_key = None
        self._last_status = None
        self._spectrum: VibrationView | None = None
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
        self.local_ip.setPlaceholderText("IPv4 проводного Ethernet")
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
        panel.addWidget(QtWidgets.QLabel("Native .exe"), 1, 0)
        panel.addWidget(self.exe_path, 1, 1, 1, 2)
        panel.addWidget(QtWidgets.QLabel("SHA256"), 1, 3)
        panel.addWidget(self.exe_sha, 1, 4)

        self.connect_button = QtWidgets.QPushButton("Подключить и измерять")
        self.connect_button.clicked.connect(self.start_native)
        self.stop_button = QtWidgets.QPushButton("Остановить")
        self.stop_button.clicked.connect(self.stop_native)
        self.stop_button.setEnabled(False)
        panel.addWidget(self.connect_button, 0, 4)
        panel.addWidget(self.stop_button, 0, 5, 2, 1)

        opts = QtWidgets.QGridLayout()
        main.addLayout(opts)
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
            ("1/3 октавы · СКЗ полосы","third_octave"),
            ("Спектр огибающей · Hilbert","envelope"),
        ]:
            self.analysis.addItem(name,key)
        self.yscale = QtWidgets.QComboBox()
        for txt,key in [("Линейная Y","linear"),("Логарифмическая Y (дБ)","db")]:
            self.yscale.addItem(txt,key)
        self.db_ref = QtWidgets.QComboBox()
        self.db_ref.addItem("ISO 1683 · 10⁻⁶ выбранной единицы", "iso")
        self.db_ref.addItem("Относительно 1 выбранной единицы", "unit")
        self.xscale = QtWidgets.QComboBox()
        for txt,key in [("Линейная X","linear"),("Логарифмическая X","log")]:
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
        self.envelope_band.addItem("Авто по импульсности (картограмма)", "auto")
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
        for idx,(label,widget) in enumerate([
            ("Канал",self.adc),("Тип",self.kind),("Режим",self.analysis),("Шкала Y",self.yscale),
            ("Опора дБ",self.db_ref),
            ("Шкала X",self.xscale),("FFT",self.nfft),("Полоса",self.band),
            ("Сглаживание (бин)",self.smooth),
            ("Нижняя граница",self.custom_low),("Верхняя граница",self.custom_high),
        ]):
            row,col=divmod(idx,4)
            opts.addWidget(QtWidgets.QLabel(label),row,col*2)
            opts.addWidget(widget,row,col*2+1)
        opts2=QtWidgets.QHBoxLayout()
        main.addLayout(opts2)
        opts2.addWidget(QtWidgets.QLabel("Полоса огибающей"))
        opts2.addWidget(self.envelope_band)
        opts2.addWidget(QtWidgets.QLabel("Notch (внимание: скрывает механич. гармоники)"))
        self.notch=QtWidgets.QComboBox()
        self.notch.addItem("Откл.",None)
        self.notch.addItem("50 Гц",50.0)
        self.notch.addItem("60 Гц",60.0)
        opts2.addWidget(self.notch)
        opts2.addWidget(QtWidgets.QLabel("Обороты, вручную (0 — нет)"))
        self.rpm=QtWidgets.QDoubleSpinBox()
        self.rpm.setRange(0,200000)
        self.rpm.setDecimals(1)
        self.rpm.setSuffix(" об/мин")
        opts2.addWidget(self.rpm)
        opts2.addWidget(QtWidgets.QLabel("Тел качения"))
        self.balls=QtWidgets.QSpinBox()
        self.balls.setRange(0,80)
        opts2.addWidget(self.balls)
        opts2.addWidget(QtWidgets.QLabel("Шарик, мм"))
        self.ball_diameter=QtWidgets.QDoubleSpinBox()
        self.ball_diameter.setRange(0,300)
        opts2.addWidget(self.ball_diameter)
        opts2.addWidget(QtWidgets.QLabel("Делит. диаметр, мм"))
        self.pitch_diameter=QtWidgets.QDoubleSpinBox()
        self.pitch_diameter.setRange(0,3000)
        opts2.addWidget(self.pitch_diameter)
        opts2.addWidget(QtWidgets.QLabel("Угол"))
        self.contact_angle=QtWidgets.QDoubleSpinBox()
        self.contact_angle.setRange(0,90)
        self.contact_angle.setSuffix("°")
        opts2.addWidget(self.contact_angle)
        opts2.addStretch(1)
        gears=QtWidgets.QHBoxLayout()
        main.addLayout(gears)
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
        review.addWidget(QtWidgets.QLabel("Развёртка"))
        review.addWidget(self.timebase)
        self.rpm_detect=QtWidgets.QPushButton("Предложить 1× из ВС")
        self.rpm_detect.clicked.connect(self._propose_rotation)
        review.addWidget(self.rpm_detect)
        self.rpm_accept=QtWidgets.QPushButton("Применить 1×")
        self.rpm_accept.setEnabled(False)
        self.rpm_accept.clicked.connect(self._accept_rotation)
        review.addWidget(self.rpm_accept)
        self.axis_button=QtWidgets.QPushButton("Пределы осей")
        self.axis_button.clicked.connect(self._edit_axes)
        review.addWidget(self.axis_button)
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
        storage.addWidget(self.csv_button)
        self.plot_png_button=QtWidgets.QPushButton("Сохранить график (.png)")
        self.plot_png_button.clicked.connect(self._export_plot_png)
        storage.addWidget(self.plot_png_button)
        storage.addWidget(QtWidgets.QLabel("Спец.анализ"))
        self.extra_mode=QtWidgets.QComboBox()
        self.extra_mode.addItem("STFT (частота–время)","stft")
        self.extra_mode.addItem("CWT Morlet (качественный)","cwt")
        self.extra_mode.addItem("Кепстр (кэфренция)","cepstrum")
        storage.addWidget(self.extra_mode)
        self.extra_button=QtWidgets.QPushButton("Рассчитать")
        self.extra_button.clicked.connect(self._calculate_extra)
        storage.addWidget(self.extra_button)
        storage.addStretch(1)
        self.rotation_info=QtWidgets.QLabel("1×: вручную или предложение по ВС. Тахометр не используется.")
        main.addWidget(self.rotation_info)
        self.status = QtWidgets.QLabel("Нет подтверждённого Live-потока")
        main.addWidget(self.status)
        self.quality = QtWidgets.QLabel("Показания AUX4700 не подменяются локальной FFT.")
        main.addWidget(self.quality)

        self.wave = pg.PlotWidget(title="Временной сигнал: откалиброванное виброускорение")
        self.wave.setLabel("left","ВУ · Виброускорение",units="м/с²")
        self.wave.setLabel("bottom","Время",units="с")
        self.wave.showGrid(x=True,y=True,alpha=0.2)
        self.wave_curve = self.wave.plot(pen=pg.mkPen("#27a8b2",width=1))
        main.addWidget(self.wave,stretch=2)

        self.spec = pg.PlotWidget(title="Спектр FFT · расчёт MVK Live из АЦП (не DSP)")
        self.spec.setLabel("bottom","Частота",units="Гц")
        self.spec.showGrid(x=True,y=True,alpha=0.2)
        self.spec_curve = self.spec.plot(pen=pg.mkPen("#e09b48",width=1.2))
        self.cursor = pg.InfiniteLine(pos=100,movable=True,pen=pg.mkPen("#76838b",style=QtCore.Qt.DashLine))
        self.spec.addItem(self.cursor)
        self.cursor.sigPositionChanged.connect(self._cursor_text)
        self.views=QtWidgets.QTabWidget()
        self.views.addTab(self.spec,"Спектр и курсор")
        self.waterfall=pg.PlotWidget(title="Водопад · последовательные APP_DERIVED спектры")
        self.waterfall.setLabel("bottom","Частота",units="Гц")
        self.waterfall.setLabel("left","Новые измеренные кадры",units=" ")
        self.waterfall_img=pg.ImageItem()
        self.waterfall.addItem(self.waterfall_img)
        self.views.addTab(self.waterfall,"Водопад")
        dsp_panel=QtWidgets.QWidget()
        dsp_layout=QtWidgets.QVBoxLayout(dsp_panel)
        self.dsp_plot=pg.PlotWidget(title="Оригинальный DSP · AUX4700 · 43 третьоктавных СКЗ")
        self.dsp_plot.setLabel("bottom","Центр полосы",units="Гц")
        self.dsp_plot.setLabel("left","Виброускорение СКЗ",units="м/с²")
        self.dsp_plot.showGrid(x=True,y=True,alpha=.2)
        self.dsp_curve=self.dsp_plot.plot(pen=pg.mkPen("#6b8cbd",width=1.5),
                                          symbol="o",symbolSize=4)
        dsp_layout.addWidget(self.dsp_plot)
        self.dsp_info=QtWidgets.QLabel("Данные AUX4700 от прибора ещё не получены")
        dsp_layout.addWidget(self.dsp_info)
        self.views.addTab(dsp_panel,"Оригинальный DSP")
        self.trend_plot=pg.PlotWidget(title="Тренд · локальная СКЗ ускорения")
        self.trend_plot.setLabel("bottom","Время с начала сеанса",units="с")
        self.trend_plot.setLabel("left","Виброускорение СКЗ",units="м/с²")
        self.trend_line=self.trend_plot.plot(pen=pg.mkPen("#21a179",width=1.4))
        self.views.addTab(self.trend_plot,"Тренд СКЗ")
        self.extra_plot=pg.PlotWidget(title="Дополнительный анализ механической вибрации")
        self.extra_plot.showGrid(x=True,y=True,alpha=.2)
        self.extra_image=pg.ImageItem()
        self.extra_plot.addItem(self.extra_image)
        self.extra_line=self.extra_plot.plot(pen=pg.mkPen("#c05c91",width=1.1))
        self.views.addTab(self.extra_plot,"STFT / CWT / Кепстр")
        main.addWidget(self.views,stretch=3)
        self.metrics = QtWidgets.QLabel("Нет достоверных данных")
        main.addWidget(self.metrics)
        self.features_label=QtWidgets.QLabel("Временные признаки: ожидание калиброванного канала")
        main.addWidget(self.features_label)
        self.bearing_diagnostics=QtWidgets.QLabel(
            "Подшипники: введите 1× и геометрию; локальное SNR, без эталонных измерений")
        main.addWidget(self.bearing_diagnostics)
        self._apply_axes()

        for w in (self.adc,self.kind,self.nfft,self.band,self.smooth,self.analysis,self.envelope_band,self.notch,self.custom_low,self.custom_high):
            w.currentIndexChanged.connect(self._on_control_change) if isinstance(w,QtWidgets.QComboBox) else w.valueChanged.connect(self._on_control_change)
        for w in (self.yscale,self.xscale,self.db_ref):
            w.currentIndexChanged.connect(self._redraw_from_current)
        self.rpm.valueChanged.connect(self._rpm_changed)
        for w in (self.rpm,self.balls,self.ball_diameter,self.pitch_diameter,self.contact_angle):
            w.valueChanged.connect(self._update_markers)
        self._timer=QtCore.QTimer(self)
        self._timer.setInterval(900)  # current Native sidecar is published >=750 ms
        self._timer.timeout.connect(self._poll)
        self._timer.start()
        self._ipc_timer=QtCore.QTimer(self)
        self._ipc_timer.setInterval(75)  # bounded fresh ring snapshots at up to 13 Hz
        self._ipc_timer.timeout.connect(self._poll_ipc)
        self._ipc_timer.start()

    def _read_settings(self):
        band=self.band.currentData()
        if band=="custom":
            high=float(self.custom_high.value())
            band=(float(self.custom_low.value()),high if high>0 else None)
        return (self.adc.currentData(),self.kind.currentData(),self.nfft.currentData(),
                band,self.smooth.value(),
                self.analysis.currentData(),self.envelope_band.currentData(),self.notch.currentData())

    def _on_control_change(self,*_):
        self._last_fft_submit=0.0
        self._last_submitted_key=None
        if self._spectrum is not None and (
                self._spectrum.mode!=self.analysis.currentData() or
                self._spectrum.kind!=self.kind.currentData()):
            self._waterfall_rows=[]
            self._waterfall_key=None
            self.waterfall_img.clear()
        self._render_dsp()
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
            self.metrics.setText("Пересчёт выбранного физического спектра")
        self._render_wave()
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
            prefix={"fft":"FFT","welch":"PSD Уэлча",
                    "third_octave":"1/3 октавы","envelope":"Огибающая"}[mode]
            if ys=="linear":
                vertical=f"{prefix} · {unit} СКЗ" if mode!="welch" else f"{prefix} · ({unit})²/Гц"
            else:
                ref=db_reference_text(kind,self.db_ref.currentData())
                vertical=f"{prefix} · дБ (отн. {ref})"
                if mode=="welch":vertical+="²/Гц"
        self.spec.setLabel("left",vertical)
        # Numerical amplitudes are ALREADY logarithmic dB. A second log-Y
        # transformation would distort negative and zero dB values.
        self.spec.getPlotItem().setLogMode(x=(xs=="log"),y=False)

    def _redraw_from_current(self,*_):
        self._apply_axes()
        self._render_spectrum()
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
                    markers[f"GMF±{abs(hz-gear.mesh_hz)/self.rpm.value()*60:.0f}×"]=hz
            except ValueError:
                pass  # invalid user geometry cannot inject arbitrary lines
        for label,hz in markers.items():
            if hz<=0:continue
            line=pg.InfiniteLine(pos=(math.log10(hz) if self.xscale.currentData()=="log" else hz),movable=False,
                 pen=pg.mkPen("#6e8295",width=1,style=QtCore.Qt.DashLine),
                 label=label,labelOpts={"position":0.9,"color":"#6e8295"})
            self.spec.addItem(line)
            self._marker_lines.append(line)

    def _render_dsp(self):
        status=self._last_status
        if status is None or status.get("phase")!="RECORDING":
            self.dsp_curve.setData([],[])
            self.dsp_info.setText("DSP: ожидание измерения МВК01")
            return
        try:
            band=read_original_dsp_bands(status,self.adc.currentData())
        except (ValueError,TypeError) as exc:
            self.dsp_curve.setData([],[])
            self.dsp_info.setText(f"Оригинальный AUX4700 отклонён: {exc}")
            return
        if band is None:
            self.dsp_curve.setData([],[])
            self.dsp_info.setText("AUX4700: нет реальных 43-полосных данных выбранного АЦП")
            return
        good=np.isfinite(band.acceleration_rms)
        self.dsp_curve.setData(band.frequency_hz[good],band.acceleration_rms[good])
        self.dsp_info.setText(
            f"ИСТОЧНИК: MVK_DSP_ORIGINAL_AUX4700 · АЦП {band.adc} · "
            f"пакет {band.update} · статус {band.status_hex} · "
            f"неконечных полей: {band.nonfinite_fields} · "
            "это оригинальный результат прибора, НЕ локальная PSD/FFT"
        )

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
        self.trend_line.setData(
            [p[0] for p in self._trend_points],
            [p[1] for p in self._trend_points])

    def _render_wave(self):
        if self.freeze.isChecked() and self._freeze_samples is not None:
            if self.adc.currentData()!=self._freeze_channel:
                self.wave_curve.setData([],[])
                return
            fs=self._freeze_rate
            offset=int(round(self.history.value()*fs))
            end=len(self._freeze_samples)-offset
            data=self._freeze_samples[:max(0,end)]
        else:
            ch=self._gui_ring.channel(self.adc.currentData())
            if ch is None or ch.available==0:
                self.wave_curve.setData([],[])
                return
            fs=ch.rate_hz
            data=ch.latest(min(ch.available,262144))
        if fs<=0 or len(data)==0:
            self.wave_curve.setData([],[])
            return
        # Physical timebase is explicit; no manufactured interpolation.
        n=min(len(data),max(1,int(self.timebase.currentData()*fs)))
        window=data[-n:]
        step=max(1,int(math.ceil(len(window)/2500)))
        if step>1 and len(window)>=step:
            trimmed=window[-(len(window)//step)*step:].reshape(-1,step)
            low=trimmed.min(axis=1)
            high=trimmed.max(axis=1)
            y=np.stack((low,high),axis=1).reshape(-1)
            indices=np.repeat(np.arange(len(low))*step,2)
            indices[1::2]+=step-1
            x=(indices-len(trimmed.reshape(-1)))/fs
        else:
            y=window
            x=(np.arange(len(window),dtype=np.float64)-len(window))/fs
        self.wave_curve.setData(x,y)

    def _schedule_fft(self):
        if self._preview is None or (
                self._future is not None and not self._future.done()):
            return
        s=self._read_settings()
        ch=self._gui_ring.channel(s[0])
        if ch is None or ch.available<s[2]:
            self._spectrum=None
            self.spec_curve.setData([],[])
            self.metrics.setText(f"Ожидание {s[2]} подтверждённых отсчётов АЦП {s[0]}")
            return
        if self.freeze.isChecked() and self._freeze_samples is not None:
            available=max(0,len(self._freeze_samples)-
                          int(round(self.history.value()*self._freeze_rate)))
        else:
            available=ch.available
        history=min(available,s[2]*2) if s[5] in (
            "welch","third_octave") else s[2]
        history=max(history,s[2])
        try:
            source,fs,stamp=self._current_window(history)
        except ValueError as exc:
            self._spectrum=None
            self.spec_curve.setData([],[])
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
                if result.auto_envelope is not None:
                    choice=result.auto_envelope
                    self.metrics.setText(self.metrics.text()+
                        f" · автополоса {choice.low_hz:.0f}–{choice.high_hz:.0f} Гц"
                        f" (kurt={choice.envelope_kurtosis:.2f}, {choice.confidence})")
                self._show_bearing_diagnostics()
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
            self.status.setText(f"Native R6.1: {status['phase']} · RAW {status['raw_bytes']/1048576:.1f} МиБ · "
                                f"кадров {status['frames_decoded']} · AUX {status['aux4700_updates']}")
            if status.get("source_tcp_multi_socket"):
                self._clear("Отклонено: обнаружен посторонний TCP источник")
                return
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
        count=min(self._gui_ring.capacity,max(65536,int(self.nfft.currentData())*(2 if self.analysis.currentData() in ("welch","third_octave") else 1)))
        self._ipc_channel=self.adc.currentData()
        self._ipc_future=self._ipc_executor.submit(
            self._ipc_client.read_channel,self._ipc_channel,count)

    def _clear(self,message):
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
        self.metrics.setText(message)

    def _render_spectrum(self):
        if self._spectrum is None:return
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
        self._cursor_text()
        label=({"fft":"FFT","welch":"Welch PSD",
               "third_octave":"1/3 октавы","envelope":"Hilbert огибающая"}[s.mode])
        suffix="" if s.mode=="welch" else " СКЗ"
        base=(f"{label} · АЦП {self.adc.currentData()} · N={s.nfft} · "
              f"Δf={s.resolution_hz:g} Гц · пик {s.peak[0]:.2f} Гц / "
              f"{s.peak[1]:.5g} {s.units}{suffix} · "
              f"источник APP_DERIVED (НЕ AUX4700)")
        if self.yscale.currentData()=="db":
            base+=" · дБ отн. "+db_reference_text(s.kind,self.db_ref.currentData())
        if s.mode in ("welch","third_octave"):
            base+=f" · сегментов Welch: {s.segments} · HP от {s.floor_hz:g} Гц"
        self.metrics.setText(base)

    def _cursor_text(self,*_):
        if self._spectrum is None:return
        f=self._spectrum.hz
        pos=float(self.cursor.value())
        if self.xscale.currentData()=="log":
            pos=10**np.clip(pos,-12,12)
        i=int(np.argmin(np.abs(f-pos)))
        value=self._spectrum.rms[i]
        unit=f"{self._spectrum.units}"+("" if self._spectrum.mode=="welch" else " СКЗ")
        if self.yscale.currentData()=="db":
            dbv=vibration_plot_values(self._spectrum,"db",reference=self.db_ref.currentData())[i]
            self.spec.setTitle(f"{self._spectrum.mode.upper()} · {f[i]:.2f} Гц · "
                               f"{dbv:.2f} дБ · {value:.5g} {unit}")
        else:
            self.spec.setTitle(f"{self._spectrum.mode.upper()} · курсор {f[i]:.2f} Гц · "
                               f"{value:.5g} {unit}")

    def _update_waterfall(self,job_key):
        if self._spectrum is None or self._spectrum.mode not in ("fft","welch"):
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
        self._waterfall_rows=self._waterfall_rows[-120:]
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
        self._show_bearing_diagnostics()

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
        self._show_bearing_diagnostics()

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
            self.status.setText(f"Сохранён локальный фрагмент: {out}")
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

    def _show_bearing_diagnostics(self):
        view=self._spectrum
        if view is None or view.mode!="envelope":
            self.bearing_diagnostics.setText(
                "Для локального анализа BPFO/BPFI/BSF/FTF выберите спектр огибающей")
            return
        if self.rpm.value()<=0 or self.balls.value()<3:
            self.bearing_diagnostics.setText(
                "Подшипники: укажите 1× и геометрию. Обороты только вручную/по ВС, без TACH")
            return
        try:
            lines=envelope_fault_lines(
                view,float(self.rpm.value()),balls=int(self.balls.value()),
                ball_diameter_mm=float(self.ball_diameter.value()),
                pitch_diameter_mm=float(self.pitch_diameter.value()),
                contact_angle_deg=float(self.contact_angle.value()))
        except (ValueError,TypeError) as exc:
            self.bearing_diagnostics.setText(f"Геометрия/спектр ещё не готовы: {exc}")
            return
        observations=[]
        for item in lines:
            status="выделяется" if item.noteworthy else "не выделяется"
            observations.append(
                f"{item.label} {item.expected_hz:.1f} Гц: {item.snr_db:.1f} дБ, "
                f"гарм. {item.harmonics_found} ({status})")
        self.bearing_diagnostics.setText(
            "APP_DERIVED · локальный фон текущей записи, НЕ диагноз и НЕ эталон · "+
            ("; ".join(observations) if observations else "Нет разрешённых линий")
        )

    def _calculate_extra(self):
        if self._extra_future is not None and not self._extra_future.done():
            return
        mode=self.extra_mode.currentData()
        try:
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
            if mode=="stft":
                work=stft_vibration
                kwargs={"nperseg":1024}
            elif mode=="cwt":
                work=cwt_morlet_vibration
                kwargs={"scales":40,"min_frequency_hz":max(10.,fs/4096)}
            else:
                work=real_cepstrum
                kwargs={}
            self._extra_kind=mode
            self._extra_future=self._extra_executor.submit(work,data,fs,**kwargs)
            self.extra_button.setEnabled(False)
            self.status.setText(f"Расчёт {mode.upper()} по текущему окну (без эталонов)")
        except (ValueError,RuntimeError) as exc:
            self.status.setText(f"Дополнительный анализ: {exc}")

    def _poll_extra(self):
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
        self.extra_button.setEnabled(True)
        try:
            view=pending.result()
        except (ValueError,RuntimeError,FloatingPointError) as exc:
            self.status.setText(f"Специальный анализ: {exc}")
            return
        mode=self._extra_kind
        self.views.setCurrentWidget(self.extra_plot)
        if mode=="cepstrum":
            self.extra_image.clear()
            self.extra_line.setData(view.quefrency_s,view.magnitude)
            self.extra_plot.setLabel("bottom","Кэфренция",units="с")
            self.extra_plot.setLabel("left","Вещественный кепстр",units="отн.")
            self.extra_plot.setTitle(view.description)
        else:
            self.extra_line.setData([],[])
            mag=view.magnitude
            if view.calibrated_amplitude:
                values=20*np.log10(np.maximum(mag,1e-15)/1e-6)
                self.extra_plot.setTitle(view.description+" · дБ отн. 10⁻⁶ м/с²")
            else:
                values=20*np.log10(
                    np.maximum(mag,1e-15)/max(float(np.max(mag)),1e-15))
                self.extra_plot.setTitle(view.description+" · дБ отн. локального максимума")
            self.extra_image.setImage(
                np.asarray(values,dtype=np.float32),
                autoLevels=False,levels=(-120,120))
            t=view.time_s
            freqs=view.frequency_hz
            width=max(float(t[-1]-t[0]),1e-9)
            height=max(float(freqs[-1]-freqs[0]),1e-9)
            self.extra_image.setRect(QtCore.QRectF(float(t[0]),float(freqs[0]),
                                                  width,height))
            self.extra_plot.setLabel("bottom","Время",units="с")
            self.extra_plot.setLabel("left","Частота",units="Гц")
        self.extra_plot.enableAutoRange()
        self.status.setText(
            f"Дополнительный анализ {mode.upper()} · APP_DERIVED, без внешнего эталона")

    def _edit_axes(self):
        dlg=QtWidgets.QDialog(self)
        dlg.setWindowTitle("Ручные пределы графика · по физическим координатам")
        form=QtWidgets.QFormLayout(dlg)
        axis=[]
        mode=self.yscale.currentData()
        for name,value in [
            ("X минимум, Гц",1.0 if self.xscale.currentData()=="log" else 0.0),
            ("X максимум, Гц",1000.0),
            ("Y минимум, дБ/ед.",-120.0 if mode=="db" else 0.0),
            ("Y максимум, дБ/ед.",80.0 if mode=="db" else 10.0)]:
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
            self.status.setText("Неверные пределы: Xmin < Xmax, Ymin < Ymax, Xlog > 0")
            return
        if self.xscale.currentData()=="log":
            xmin,xmax=math.log10(xmin),math.log10(xmax)
        self.spec.setXRange(xmin,xmax,padding=0)
        self.spec.setYRange(ymin,ymax,padding=0)
        self.status.setText("Ручной масштаб осей установлен (только представление)")

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
            exe=self._verify_native(self.exe_path.text(),self.exe_sha.text())
        except (ValueError,OSError,UnicodeError) as exc:
            QtWidgets.QMessageBox.warning(self,"Подключение запрещено",str(exc))
            return
        reply=QtWidgets.QMessageBox.question(
            self,"Допуск к прибору",
            f"Разрешено подключиться по TCP/10230 к {ip} через Ethernet {local}?\n"
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
        self.status.setText(f"Native завершён (код {exit_code}); папка: {self._capture_root}")

    def closeEvent(self,event):
        if self._native.state()!=QtCore.QProcess.ProcessState.NotRunning:
            QtWidgets.QMessageBox.warning(self,"Запись ещё идёт",
                "Сначала нажмите «Остановить», дождитесь завершения Native и повторите закрытие.")
            event.ignore()
            return
        self._timer.stop()
        self._ipc_timer.stop()
        # Do not leave NumPy/SciPy workers alive while the PySide6 interpreter
        # is tearing down: this can cause native Qt reference-count crashes.
        self._executor.shutdown(wait=True,cancel_futures=True)
        self._ipc_executor.shutdown(wait=True,cancel_futures=True)
        self._extra_executor.shutdown(wait=True,cancel_futures=True)
        super().closeEvent(event)


def main(argv=None):
    ap=argparse.ArgumentParser(description="MVK Live standalone, Native R6.1 sidecar viewer")
    ap.add_argument("--capture-root",type=Path,help="watch an already approved Native R6.1 session")
    options=ap.parse_args(argv)
    app=QtWidgets.QApplication([])
    window=LiveWindow(capture_root=options.capture_root)
    window.show()
    return app.exec()


if __name__=="__main__":
    raise SystemExit(main())
