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
from .live_ipc import discover_local_ipc, IPCNotReady
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

        opts = QtWidgets.QHBoxLayout()
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
        self.smooth = QtWidgets.QSpinBox()
        self.smooth.setRange(1,101)
        self.smooth.setSingleStep(2)
        self.smooth.setValue(1)
        for label,widget in [
            ("Канал",self.adc),("Тип",self.kind),("Режим",self.analysis),("Шкала Y",self.yscale),
            ("Опора дБ",self.db_ref),
            ("Шкала X",self.xscale),("FFT",self.nfft),("Полоса",self.band),
            ("Сглаживание (бин)",self.smooth),
        ]:
            opts.addWidget(QtWidgets.QLabel(label))
            opts.addWidget(widget)
        opts2=QtWidgets.QHBoxLayout()
        main.addLayout(opts2)
        opts2.addWidget(QtWidgets.QLabel("Полоса огибающей"))
        opts2.addWidget(self.envelope_band)
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
        self.trend_plot=pg.PlotWidget(title="Тренд · локальная СКЗ ускорения")
        self.trend_plot.setLabel("bottom","Время с начала сеанса",units="с")
        self.trend_plot.setLabel("left","Виброускорение СКЗ",units="м/с²")
        self.trend_line=self.trend_plot.plot(pen=pg.mkPen("#21a179",width=1.4))
        self.views.addTab(self.trend_plot,"Тренд СКЗ")
        main.addWidget(self.views,stretch=3)
        self.metrics = QtWidgets.QLabel("Нет достоверных данных")
        main.addWidget(self.metrics)
        self.features_label=QtWidgets.QLabel("Временные признаки: ожидание калиброванного канала")
        main.addWidget(self.features_label)
        self._apply_axes()

        for w in (self.adc,self.kind,self.nfft,self.band,self.smooth,self.analysis,self.envelope_band):
            w.currentIndexChanged.connect(self._on_control_change) if isinstance(w,QtWidgets.QComboBox) else w.valueChanged.connect(self._on_control_change)
        for w in (self.yscale,self.xscale,self.db_ref):
            w.currentIndexChanged.connect(self._redraw_from_current)
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
        return (self.adc.currentData(),self.kind.currentData(),self.nfft.currentData(),
                self.band.currentData(),self.smooth.value(),
                self.analysis.currentData(),self.envelope_band.currentData())

    def _on_control_change(self,*_):
        self._last_fft_submit=0.0
        self._last_submitted_key=None
        if self._spectrum is not None and (
                self._spectrum.mode!=self.analysis.currentData() or
                self._spectrum.kind!=self.kind.currentData()):
            self._waterfall_rows=[]
            self._waterfall_key=None
            self.waterfall_img.clear()
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
        for label,hz in markers.items():
            if hz<=0:continue
            line=pg.InfiniteLine(pos=(math.log10(hz) if self.xscale.currentData()=="log" else hz),movable=False,
                 pen=pg.mkPen("#6e8295",width=1,style=QtCore.Qt.DashLine),
                 label=label,labelOpts={"position":0.9,"color":"#6e8295"})
            self.spec.addItem(line)
            self._marker_lines.append(line)

    def _update_features(self):
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
            f"Эксцесс (Pearson) {f.acceleration_kurtosis:.3f} · "
            +("RPM задан вручную, НЕ TACH" if self.rpm.value()>0 else "RPM: нет доказанного TACH")
        )
        if len(self._trend_points) and ch.end/ch.rate_hz<=self._trend_points[-1][0]:
            self._trend_points=[]
        self._trend_points.append((ch.end/ch.rate_hz,f.acceleration_rms))
        self._trend_points=self._trend_points[-240:]
        self.trend_line.setData(
            [p[0] for p in self._trend_points],
            [p[1] for p in self._trend_points])

    def _render_wave(self):
        ch=self._gui_ring.channel(self.adc.currentData())
        if ch is None or not ch.available:
            self.wave_curve.setData([],[])
            return
        x=ch.latest(min(ch.available,250000))
        # Peak-preserving min/max decimation prevents hiding narrow spikes.
        step=max(1,len(x)//2500)
        last=x[-step*math.ceil(min(len(x),250000)/step):]
        if step>1 and len(last)>=step:
            trimmed=last[:(len(last)//step)*step].reshape(-1,step)
            ymin=trimmed.min(axis=1);ymax=trimmed.max(axis=1)
            yy=np.stack((ymin,ymax),axis=1).reshape(-1)
            xx=(np.repeat(np.arange(len(ymin))*step,2)+np.tile([0,step-1],len(ymin)))/ch.rate_hz
        else:
            yy=last
            xx=np.arange(len(last),dtype=float)/ch.rate_hz
        xx=xx-(len(last)/ch.rate_hz)
        self.wave_curve.setData(xx,yy)

    def _schedule_fft(self):
        if self._preview is None or (self._future is not None and not self._future.done()):
            return
        s=self._read_settings()
        ch=self._gui_ring.channel(s[0])
        if ch is None or ch.available<s[2]:
            self._spectrum=None
            self.spec_curve.setData([],[])
            self.metrics.setText(f"Ожидание {s[2]} подтверждённых отсчётов АЦП {s[0]}")
            return
        job_key=(self._gui_ring.session_id, s[0], ch.end, s)
        if job_key==self._last_submitted_key or (
            time.monotonic()-self._last_fft_submit<0.14):
            return  # plot may follow at 13Hz while FFT is at most ~7Hz
        history=min(ch.available,s[2]*2) if s[5] in ("welch","third_octave") else s[2]
        source=ch.latest(history)  # immutable snapshot: no race with acquisition
        self._last_fft_submit=time.monotonic()
        self._last_submitted_key=job_key
        self._job_settings=(self._generation,self._preview.updated_utc,s,job_key)
        self._future=self._executor.submit(
            analyze_vibration,source,ch.rate_hz,
            kind=s[1],mode=s[5],nfft=s[2],band_hz=s[3],
            envelope_band_hz=s[6],smooth_bins=s[4])

    def _collect_analysis(self):
        if self._future is None or not self._future.done():return
        job=self._job_settings
        try:
            result=self._future.result()
        except (ValueError,RuntimeError,FloatingPointError) as exc:
            self.metrics.setText(f"APP_DERIVED: {exc}")
            self.spec_curve.setData([],[])
            self._spectrum=None
        else:
            if job and job[2]==self._read_settings() and self._preview is not None:
                self._spectrum=result
                self._render_spectrum()
                self._update_waterfall(job[3])
        self._future=None
        self._schedule_fft()

    def _poll(self):
        self._collect_analysis()
        if self._capture_root is None:return
        try:
            status=load_capture_live_status(self._capture_root,
                    instrument_ipv4=self._active_ip,local_ipv4=self._local_ip)
            if status is None:
                self.status.setText("Ожидание Native R6.1")
                return
            self._last_status=status
            self.status.setText(f"Native R6.1: {status['phase']} · RAW {status['raw_bytes']/1048576:.1f} МиБ · "
                                f"кадров {status['frames_decoded']} · AUX {status['aux4700_updates']}")
            if status.get("source_tcp_multi_socket") or status["phase"]!="RECORDING":
                self._clear(f"Источник недоступен: {status['phase']}")
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
            if updated:
                self._update_features()
                self._request_update()
        except (OSError,ValueError,KeyError,RuntimeError) as exc:
            self._clear(f"Превью отклонено: {exc}")

    def _poll_ipc(self):
        self._collect_analysis()
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
