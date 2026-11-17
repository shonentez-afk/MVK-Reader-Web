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
        self._spectrum: Spectrum | None = None
        self._future: Future | None = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="MVK-spectrum")
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
        self.smooth = QtWidgets.QSpinBox()
        self.smooth.setRange(1,101)
        self.smooth.setSingleStep(2)
        self.smooth.setValue(1)
        for label,widget in [
            ("Канал",self.adc),("Тип",self.kind),("Шкала Y",self.yscale),
            ("Опора дБ",self.db_ref),
            ("Шкала X",self.xscale),("FFT",self.nfft),("Полоса",self.band),
            ("Сглаживание (бин)",self.smooth),
        ]:
            opts.addWidget(QtWidgets.QLabel(label))
            opts.addWidget(widget)
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
        main.addWidget(self.spec,stretch=3)
        self.metrics = QtWidgets.QLabel("Нет достоверных данных")
        main.addWidget(self.metrics)
        self._apply_axes()

        for w in (self.adc,self.kind,self.nfft,self.band,self.smooth):
            w.currentIndexChanged.connect(self._request_update) if isinstance(w,QtWidgets.QComboBox) else w.valueChanged.connect(self._request_update)
        for w in (self.yscale,self.xscale,self.db_ref):
            w.currentIndexChanged.connect(self._redraw_from_current)
        self._timer=QtCore.QTimer(self)
        self._timer.setInterval(900)  # current Native sidecar is published >=750 ms
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def _read_settings(self):
        return (self.adc.currentData(),self.kind.currentData(),self.nfft.currentData(),
                self.band.currentData(),self.smooth.value())

    def _request_update(self,*_):
        self._generation += 1
        # The physical Y unit must update IMMEDIATELY on the operator's
        # choice, even while the next verified FFT is still calculating.
        self._apply_axes()
        if self._spectrum is not None and self._spectrum.kind != self.kind.currentData():
            self._spectrum = None
            self.spec_curve.setData([],[])
            self.metrics.setText("Пересчёт выбранного физического спектра")
        self._render_wave()
        self._schedule_fft()

    def _apply_axes(self):
        kind=self.kind.currentData()
        ys=self.yscale.currentData()
        xs=self.xscale.currentData()
        self.spec.setLabel("left",y_axis_label(kind,ys,self.db_ref.currentData()))
        # dB data is a logarithm already. Never apply logY to it again.
        self.spec.getPlotItem().setLogMode(x=(xs=="log"),y=False)

    def _redraw_from_current(self,*_):
        self._apply_axes()
        self._render_spectrum()

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
        if job_key==self._last_submitted_key:
            return
        source=ch.latest(s[2])  # independent snapshot for worker thread
        self._last_submitted_key=job_key
        self._job_settings=(self._generation,self._preview.updated_utc,s)
        self._future=self._executor.submit(calculate_spectrum,source,ch.rate_hz,
                 kind=s[1],nfft=s[2],band_hz=s[3],smooth_bins=s[4])

    def _poll(self):
        if self._future is not None and self._future.done():
            job=self._job_settings
            try:
                result=self._future.result()
            except (ValueError,RuntimeError,FloatingPointError) as exc:
                self.metrics.setText(f"FFT: {exc}")
                self.spec_curve.setData([],[])
                self._spectrum=None
            else:
                if job and job[2]==self._read_settings() and self._preview is not None:
                    # A verified preview may arrive while the FFT worker runs.
                    # Showing that completed result is preferable to starving
                    # the graph when new previews arrive every 750-900 ms.
                    self._spectrum=result
                    self._render_spectrum()
            self._future=None
            self._schedule_fft()
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
                self._request_update()
        except (OSError,ValueError,KeyError,RuntimeError) as exc:
            self._clear(f"Превью отклонено: {exc}")

    def _clear(self,message):
        self._preview=None
        self._gui_ring.clear()
        self._last_submitted_key=None
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
        y=plot_values(s,self.yscale.currentData(),reference=self.db_ref.currentData())
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
        self.metrics.setText(
            f"АЦП {self.adc.currentData()} · {s.nfft} отсчётов · Δf {s.resolution_hz:g} Гц · "
            f"пик {s.peak[0]:.2f} Гц / {s.peak[1]:.5g} {s.units} СКЗ · "
            ("· дБ отн. "+db_reference_text(s.kind,self.db_ref.currentData())+
             " · локальная FFT, не DSP" if self.yscale.currentData()=="db"
             else "· локальная FFT, не приборный DSP")
        )

    def _cursor_text(self,*_):
        if self._spectrum is None:return
        f=self._spectrum.hz
        i=int(np.argmin(np.abs(f-self.cursor.value())))
        value=self._spectrum.rms[i]
        if self.yscale.currentData()=="db":
            dbv=plot_values(self._spectrum,"db",reference=self.db_ref.currentData())[i]
            self.spec.setTitle(f"FFT · {f[i]:.2f} Гц · {dbv:.2f} дБ · {value:.5g} {self._spectrum.units} СКЗ")
        else:
            self.spec.setTitle(f"FFT · курсор {f[i]:.2f} Гц · {value:.5g} {self._spectrum.units} СКЗ")

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
        self._executor.shutdown(wait=False,cancel_futures=True)
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
