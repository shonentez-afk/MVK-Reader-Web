"""MVK Live history, trended device fields and multi-date spectrum/time overlays.

One archive indexed by *original measurement timestamps*, ADC and provenance.
No reference baseline: all compared curves are explicitly dated measurements.
Saved ADC windows are reprocessed locally when the operator chooses a view;
original AUX4700 43+24x3 are never substituted by an FFT or interpolated.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets

from .measurement_history import (
    MeasurementHistory, HistoryEntry, MAX_OVERLAYS, VENDOR, LOCAL,
    metric_details,
)
from .original_dsp import _THIRD_HZ
from .spectrum_controls import VIEW_MODES
from .vibration import analyze_vibration, vibration_plot_values

COLORS=("#268bd2","#e66b24","#3ba86c","#9b6ad0",
        "#d74a68","#a3a535","#18a3a3","#925f36")

TREND_GROUPS=(
    ("Прибор · 1/3 октавы · СКЗ ВУ","third_octave"),
    ("Прибор · 24 позиции · СКЗ","band_rms"),
    ("Прибор · 24 позиции · Пик","band_peak_equiv"),
    ("Прибор · 24 позиции · Размах","band_span_equiv"),
    ("MVK Live · ВУ СКЗ окна","time_rms"),
    ("MVK Live · ВУ пик окна","time_peak"),
    ("MVK Live · ВУ пик-пик окна","time_pp"),
    ("MVK Live · Крест-фактор","crest"),
    ("MVK Live · Куртозис Pearson","kurtosis"),
    ("MVK Live · Асимметрия","skew"),
    ("MVK Live · Импульсный фактор","impulse"),
    ("MVK Live · Фактор формы","shape"),
    ("MVK Live · Фактор зазора","clearance"),
    ("MVK Live · ВС СКЗ 10–1000 Гц","velocity_rms_10_1000"),
)

COMPARE_MODES=(
    ("FFT · Логарифмическая (ВУ, дБ)","fft_log"),
    ("FFT · Линейный ВУ (м/с²)","fft_vu"),
    ("FFT · Линейный ВС (мм/с)","fft_vs"),
    ("FFT · Линейный ВП (мкм)","fft_vp"),
    ("Временные сигналы · ВУ (м/с²)","wave"),
    ("Оригинальный DSP · 43 частоты · ВУ СКЗ","vendor43"),
    ("Оригинальный DSP · 24 позиции · СКЗ","vendor24_rms"),
    ("Оригинальный DSP · 24 позиции · Пик","vendor24_peak"),
    ("Оригинальный DSP · 24 позиции · Размах","vendor24_span"),
)


class HistoryWorkspaces(QtCore.QObject):
    """Two independent Qt tabs linked by a selected historical timestamp."""
    capture_requested=QtCore.Signal()
    import_npz_requested=QtCore.Signal()
    import_aux_requested=QtCore.Signal()

    def __init__(self,history:MeasurementHistory,adc:QtWidgets.QComboBox,
                 parent=None):
        super().__init__(parent)
        self.history=history
        self.adc=adc
        self.on_open_comparison=None
        self._trend_last=[]
        self._selected_trend_point=None
        self._available_entries={}
        self._table_selected=set()
        self._last_overlay=[]
        self._build_trends()
        self._build_comparison()
        self.adc.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def _build_trends(self):
        self.trend_page=QtWidgets.QWidget()
        layout=QtWidgets.QVBoxLayout(self.trend_page)
        bar=QtWidgets.QHBoxLayout()
        bar.addWidget(QtWidgets.QLabel("Тренд АЦП"))
        self.trend_adc=QtWidgets.QLabel(f"АЦП {self.adc.currentData()}")
        bar.addWidget(self.trend_adc)
        bar.addWidget(QtWidgets.QLabel("Показатель"))
        self.trend_group=QtWidgets.QComboBox()
        for label,value in TREND_GROUPS:
            self.trend_group.addItem(label,value)
        bar.addWidget(self.trend_group,stretch=2)
        self.trend_position=QtWidgets.QComboBox()
        bar.addWidget(self.trend_position)
        bar.addWidget(QtWidgets.QLabel("За период"))
        self.trend_period=QtWidgets.QComboBox()
        for label,days in (("Всё время",None),("7 дней",7),
                           ("30 дней",30),("90 дней",90),
                           ("365 дней",365)):
            self.trend_period.addItem(label,days)
        bar.addWidget(self.trend_period)
        refresh=QtWidgets.QPushButton("Обновить тренд")
        refresh.clicked.connect(self._plot_trend)
        bar.addWidget(refresh)
        layout.addLayout(bar)
        self.trend_plot=pg.PlotWidget(
            axisItems={"bottom":pg.DateAxisItem(orientation="bottom")},
            title="Сохранённые измерения · не эталон")
        self.trend_plot.setLabel("bottom","Дата и время измерения")
        self.trend_plot.showGrid(x=True,y=True,alpha=.2)
        self.trend_curve=self.trend_plot.plot(pen=pg.mkPen("#208a9b",width=1.6))
        self.trend_dots=pg.ScatterPlotItem(size=8,
                                           brush=pg.mkBrush("#208a9b"),
                                           pen=pg.mkPen("#ffffff",width=.5))
        self.trend_plot.addItem(self.trend_dots)
        self.trend_dots.sigClicked.connect(self._trend_clicked)
        layout.addWidget(self.trend_plot,stretch=1)
        nav=QtWidgets.QHBoxLayout()
        self.trend_info=QtWidgets.QLabel(
            "Ожидание исходных AUX4700 или сохранённых окон АЦП")
        self.trend_info.setWordWrap(True)
        nav.addWidget(self.trend_info,stretch=1)
        self.trend_go=QtWidgets.QPushButton("Открыть измерение в сравнении")
        self.trend_go.setEnabled(False)
        self.trend_go.clicked.connect(self._open_trend_in_comparison)
        nav.addWidget(self.trend_go)
        self.trend_export=QtWidgets.QPushButton("CSV тренда")
        self.trend_export.clicked.connect(self._export_trend_csv)
        nav.addWidget(self.trend_export)
        layout.addLayout(nav)
        self.trend_group.currentIndexChanged.connect(self._trend_group_changed)
        self.trend_position.currentIndexChanged.connect(self._plot_trend)
        self.trend_period.currentIndexChanged.connect(self._plot_trend)
        self._trend_group_changed()

    def _trend_group_changed(self,*_):
        family=self.trend_group.currentData()
        with QtCore.QSignalBlocker(self.trend_position):
            self.trend_position.clear()
            if family=="third_octave":
                for i,hz in enumerate(_THIRD_HZ):
                    self.trend_position.addItem(f"{float(hz):g} Гц",i)
            elif family in ("band_rms","band_peak_equiv","band_span_equiv"):
                for i in range(24):
                    self.trend_position.addItem(f"Позиция {i+1}",i)
            else:
                self.trend_position.addItem("Выбранный показатель",None)
        self.trend_position.setEnabled(self.trend_position.count()>1)
        self._plot_trend()

    def _chosen_metric(self):
        family=self.trend_group.currentData()
        if family in ("third_octave","band_rms",
                      "band_peak_equiv","band_span_equiv"):
            return f"{family}:{self.trend_position.currentData()}"
        return family

    def _plot_trend(self,*_):
        if not hasattr(self,"trend_curve"):return
        metric=self._chosen_metric()
        if metric is None:return
        self.trend_adc.setText(f"АЦП {self.adc.currentData()}")
        try:
            points,label,unit,truncated=self.history.trend(
                self.adc.currentData(),metric,self.trend_period.currentData())
        except (ValueError,OSError) as exc:
            self.trend_curve.setData([],[])
            self.trend_dots.setData([],[])
            self.trend_info.setText(f"Ошибка выбора тренда: {exc}")
            return
        self._trend_last=points
        self._selected_trend_point=None
        self.trend_go.setEnabled(False)
        x=np.asarray([dt.timestamp() for dt,v in points],dtype=np.float64)
        y=np.asarray([v for dt,v in points],dtype=np.float64)
        self.trend_curve.setData(x,y,connect="finite")
        self.trend_dots.setData([
            {"pos":(float(xx),float(yy)),"data":i} for i,(xx,yy)
            in enumerate(zip(x,y))])
        self.trend_plot.setLabel("left",label+f" ({unit})")
        self.trend_info.setText(
            f"АЦП {self.adc.currentData()} · {label} · {len(points)} "
            f"сохранённых измерений · {unit}"+(
            " · показаны последние 15 000 записей" if truncated else "")+
            " · UTC-метки исходного AUX, для NPZ — время добавления в архив")
        if len(points):
            self.trend_plot.enableAutoRange()
        else:
            self.trend_plot.setTitle("История пуста: требуется приём AUX4700 или сохранённое окно")
        self.trend_export.setEnabled(bool(points))

    def _trend_clicked(self,_,points,*_):
        if not points:return
        index=points[0].data()
        if type(index) is not int or not 0<=index<len(self._trend_last):return
        self._selected_trend_point=self._trend_last[index][0]
        self.trend_go.setEnabled(True)
        dt,val=self._trend_last[index]
        self.trend_info.setText(
            self.trend_info.text().split(" · выбрано:")[0]+
            f" · выбрано: {dt.isoformat()} / {val:.7g}")

    def _open_trend_in_comparison(self):
        dt=self._selected_trend_point
        if dt is None:return
        family=self.trend_group.currentData()
        kind=("window" if family in (
            "time_rms","time_peak","time_pp","crest","kurtosis","skew",
            "impulse","shape","clearance","velocity_rms_10_1000") else "vendor")
        mode={"third_octave":"vendor43",
              "band_rms":"vendor24_rms",
              "band_peak_equiv":"vendor24_peak",
              "band_span_equiv":"vendor24_span"}.get(family,"fft_vu")
        self.compare_mode.setCurrentIndex(self.compare_mode.findData(mode))
        # Select the closest *same-origin and same-ADC* saved sample. Never
        # silently link a vendor trend to a local FFT made at another time.
        rows=[r for r in self._available_entries.values()
              if (r.source==(LOCAL if kind=="window" else VENDOR))]
        if rows:
            selected=min(rows,key=lambda r:abs(
                (datetime.fromisoformat(r.time_utc)-dt).total_seconds()))
            self._table_selected={selected.key}
            self._populate_compare_table()
            self._draw_comparison()
        if self.on_open_comparison is not None:
            self.on_open_comparison()

    def _export_trend_csv(self):
        if not self._trend_last:return
        file,_=QtWidgets.QFileDialog.getSaveFileName(
            self.trend_page,"Сохранить тренд","","CSV (*.csv)")
        if not file:return
        try:
            path=Path(file)
            if path.suffix.lower()!=".csv":
                raise ValueError("Только CSV")
            label,unit=metric_details(self._chosen_metric())
            with path.open("x",newline="",encoding="utf-8-sig") as f:
                wr=csv.writer(f,delimiter=";")
                wr.writerow(["source","ADC","metric","unit","time_utc","value"])
                src=(LOCAL if self._chosen_metric() in (
                    "time_rms","time_peak","time_pp","crest","kurtosis",
                    "skew","impulse","shape","clearance",
                    "velocity_rms_10_1000") else VENDOR)
                for dt,val in self._trend_last:
                    wr.writerow([src,self.adc.currentData(),label,unit,
                                 dt.isoformat(),format(val,".11g")])
            self.trend_info.setText(f"Тренд сохранён: {path}")
        except (OSError,ValueError) as exc:
            QtWidgets.QMessageBox.warning(self.trend_page,"Ошибка CSV",str(exc))

    def _build_comparison(self):
        self.compare_page=QtWidgets.QWidget()
        layout=QtWidgets.QVBoxLayout(self.compare_page)
        bar=QtWidgets.QHBoxLayout()
        bar.addWidget(QtWidgets.QLabel("Наложение сохранённых измерений"))
        self.compare_mode=QtWidgets.QComboBox()
        for label,key in COMPARE_MODES:self.compare_mode.addItem(label,key)
        bar.addWidget(self.compare_mode,stretch=2)
        bar.addWidget(QtWidgets.QLabel("FFT N"))
        self.compare_nfft=QtWidgets.QComboBox()
        for n in (8192,16384,32768,65536):
            self.compare_nfft.addItem(str(n),n)
        bar.addWidget(self.compare_nfft)
        self.compare_refresh=QtWidgets.QPushButton("Обновить записи")
        self.compare_refresh.clicked.connect(self._reload_compare)
        bar.addWidget(self.compare_refresh)
        layout.addLayout(bar)
        splitter=QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.compare_table=QtWidgets.QTableWidget(0,4)
        self.compare_table.setHorizontalHeaderLabels(
            ["Выбрать","Дата и время UTC","АЦП","Сохранённое измерение"])
        self.compare_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.compare_table.horizontalHeader().setStretchLastSection(True)
        self.compare_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.compare_table.itemChanged.connect(self._selection_changed)
        splitter.addWidget(self.compare_table)
        self.compare_plot=pg.PlotWidget(title="Сравнение по реальным сохранённым датам")
        self.compare_plot.showGrid(x=True,y=True,alpha=.2)
        self.compare_legend=self.compare_plot.addLegend()
        splitter.addWidget(self.compare_plot)
        splitter.setStretchFactor(0,1)
        splitter.setStretchFactor(1,3)
        layout.addWidget(splitter,stretch=1)
        bottom=QtWidgets.QHBoxLayout()
        self.compare_recent=QtWidgets.QPushButton("Выбрать 2 последних")
        self.compare_recent.clicked.connect(self._choose_latest_two)
        bottom.addWidget(self.compare_recent)
        self.compare_clear=QtWidgets.QPushButton("Снять выбор")
        self.compare_clear.clicked.connect(self._clear_selection)
        bottom.addWidget(self.compare_clear)
        self.compare_draw=QtWidgets.QPushButton("Наложить выбранные")
        self.compare_draw.clicked.connect(self._draw_comparison)
        bottom.addWidget(self.compare_draw)
        self.compare_capture=QtWidgets.QPushButton("Сохранить окно АЦП в архив")
        self.compare_capture.clicked.connect(self.capture_requested.emit)
        bottom.addWidget(self.compare_capture)
        self.compare_import=QtWidgets.QPushButton("Добавить NPZ")
        self.compare_import.clicked.connect(self.import_npz_requested.emit)
        bottom.addWidget(self.compare_import)
        self.compare_aux=QtWidgets.QPushButton("Импорт AUX4700")
        self.compare_aux.clicked.connect(self.import_aux_requested.emit)
        bottom.addWidget(self.compare_aux)
        layout.addLayout(bottom)
        self.compare_info=QtWidgets.QLabel(
            "Выберите до 8 сохранённых измерений одного АЦП. "
            "Цвета соответствуют датам; нет эталонной записи.")
        self.compare_info.setWordWrap(True)
        layout.addWidget(self.compare_info)
        self.compare_mode.currentIndexChanged.connect(self._reload_compare)
        self.compare_nfft.currentIndexChanged.connect(self._draw_comparison)

    def _source_filter(self):
        return "vendor" if self.compare_mode.currentData().startswith("vendor") else "window"

    def _reload_compare(self,*_):
        self._table_selected.clear()
        self._available_entries={
            e.key:e for e in self.history.entries(
                self.adc.currentData(),kind=self._source_filter(),limit=500)}
        self._populate_compare_table()
        self._clear_plot()

    def _populate_compare_table(self):
        data=list(self._available_entries.values())
        with QtCore.QSignalBlocker(self.compare_table):
            self.compare_table.setRowCount(len(data))
            for i,row in enumerate(data):
                check=QtWidgets.QTableWidgetItem()
                check.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled|
                               QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                check.setCheckState(
                    QtCore.Qt.CheckState.Checked if row.key in self._table_selected
                    else QtCore.Qt.CheckState.Unchecked)
                check.setData(QtCore.Qt.ItemDataRole.UserRole,row.key)
                self.compare_table.setItem(i,0,check)
                for j,text in enumerate((row.time_utc[:19].replace("T"," ")+
                                        "Z",f"АЦП {row.adc}",row.detail),start=1):
                    cell=QtWidgets.QTableWidgetItem(text)
                    cell.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled|
                                  QtCore.Qt.ItemFlag.ItemIsSelectable)
                    self.compare_table.setItem(i,j,cell)
        self.compare_recent.setEnabled(len(data)>=2)
        self.compare_info.setText(
            f"АЦП {self.adc.currentData()} · {len(data)} доступных "
            f"{'пакетов AUX4700' if self._source_filter()=='vendor' else 'окон АЦП'}"
            f" · максимум {MAX_OVERLAYS} одновременно")

    def _selection_changed(self,item):
        if item.column()!=0:return
        key=item.data(QtCore.Qt.ItemDataRole.UserRole)
        if key not in self._available_entries:return
        if item.checkState()==QtCore.Qt.CheckState.Checked:
            self._table_selected.add(key)
        else:
            self._table_selected.discard(key)
        if len(self._table_selected)>MAX_OVERLAYS:
            with QtCore.QSignalBlocker(self.compare_table):
                item.setCheckState(QtCore.Qt.CheckState.Unchecked)
            self._table_selected.discard(key)
            self.compare_info.setText(
                f"Максимум {MAX_OVERLAYS} наложенных линий; уберите лишние даты")

    def _choose_latest_two(self):
        self._table_selected=set(
            list(self._available_entries.keys())[:2])
        self._populate_compare_table()
        self._draw_comparison()

    def _clear_selection(self):
        self._table_selected.clear()
        self._populate_compare_table()
        self._clear_plot()

    def _clear_plot(self):
        self.compare_plot.clear()
        if self.compare_plot.plotItem.legend is not None:
            self.compare_plot.plotItem.legend.clear()
        self._last_overlay=[]

    def _draw_comparison(self,*_):
        self._clear_plot()
        selected=[e for key,e in self._available_entries.items()
                  if key in self._table_selected]
        if not selected:
            self.compare_info.setText(
                "Отметьте сохранённые даты и нажмите «Наложить выбранные». "
                "Текущий Live-кадр не считается сохранённым измерением.")
            return
        if len(selected)>MAX_OVERLAYS:
            self.compare_info.setText("Выбрано слишком много записей")
            return
        mode=self.compare_mode.currentData()
        unit=None
        xunit="Гц"
        skipped=[]
        sample_rates=[]
        for i,entry in enumerate(selected):
            try:
                if entry.adc!=self.adc.currentData():
                    raise ValueError("АЦП не совпадает")
                if mode=="vendor43":
                    packet=self.history.get_vendor(entry)
                    x=packet.frequency_hz
                    y=packet.acceleration_rms
                    unit="м/с² · приборное СКЗ 1/3 октавы"
                elif mode.startswith("vendor24"):
                    packet=self.history.get_vendor(entry)
                    field={"vendor24_rms":"band_rms",
                           "vendor24_peak":"band_peak_equiv",
                           "vendor24_span":"band_span_equiv"}[mode]
                    data=getattr(packet,field)
                    if data is None:raise ValueError("В приборной записи нет 24 позиций")
                    x=np.arange(1,25,dtype=np.float64)
                    y=np.asarray(data)
                    xunit="Номер исходной позиции (НЕ частота)"
                    unit="Единицы/диапазоны 24 позиций не подтверждены"
                else:
                    snap=self.history.get_window(entry)
                    sample_rates.append(snap.rate_hz)
                    if mode=="wave":
                        n=len(snap.acceleration_m_s2)
                        x=np.arange(-n,0,dtype=np.float64)/snap.rate_hz
                        y=np.asarray(snap.acceleration_m_s2,dtype=np.float64)
                        unit="м/с² · временной сигнал"
                        xunit="Время относительно конца окна, с"
                        # Decimate ONLY chart curves; don't change source data.
                        if n>8000:
                            step=int(np.ceil(n/4000))
                            k=(n//step)*step
                            arr=y[-k:].reshape(-1,step)
                            low=arr.min(axis=1)
                            high=arr.max(axis=1)
                            y=np.stack((low,high),axis=1).reshape(-1)
                            inds=np.repeat(np.arange(len(low))*step,2)
                            inds[1::2]+=step-1
                            x=(inds-k)/snap.rate_hz
                    else:
                        names={"fft_log":("acceleration","db"),
                               "fft_vu":("acceleration","linear"),
                               "fft_vs":("velocity","linear"),
                               "fft_vp":("displacement","linear")}
                        kind,scale=names[mode]
                        n=self.compare_nfft.currentData()
                        if len(snap.acceleration_m_s2)<n:
                            raise ValueError(
                                f"Для FFT {n} нужно не меньше {n} сохранённых отсчётов")
                        spectrum=analyze_vibration(
                            snap.acceleration_m_s2,snap.rate_hz,
                            kind=kind,mode="fft",nfft=n,band_hz=(0.,None),
                            smooth_bins=1,notch_hz=None)
                        x=spectrum.hz
                        y=vibration_plot_values(
                            spectrum,scale,reference="iso")
                        unit=("дБ · ВУ · ISO 1683" if scale=="db"
                              else spectrum.units+" · FFT СКЗ")
                good=np.isfinite(x)&np.isfinite(y)
                if not np.any(good):
                    raise ValueError("В выбранном архивном измерении нет доступных значений")
                x=np.asarray(x)[good]
                y=np.asarray(y)[good]
                color=COLORS[i % len(COLORS)]
                name=entry.pretty
                self.compare_plot.plot(
                    x,y,pen=pg.mkPen(color,width=1.6),name=name,
                    symbol="o" if mode.startswith("vendor") else None,
                    symbolSize=4 if mode.startswith("vendor") else None)
                self._last_overlay.append((entry,x.copy(),y.copy(),unit))
            except (ValueError,OSError,KeyError,IndexError) as exc:
                skipped.append(f"{entry.time_utc[:19]}: {exc}")
        if not self._last_overlay:
            self.compare_info.setText(
                "Не удалось прочитать выбранные измерения: "+"; ".join(skipped)[:700])
            return
        self.compare_plot.setLabel("bottom",xunit)
        self.compare_plot.setLabel("left",unit or "Физическая величина")
        # Compare the common real frequency domain only. No fictional
        # resampling to equal FFT grids and no baseline normalization.
        if not mode.startswith("vendor") and mode!="wave" and sample_rates:
            fmax=min(sample_rates)/2
            self.compare_plot.setXRange(0,fmax,padding=0)
        elif mode=="wave":
            durations=[max(-float(x[0]),0.001) for _,x,_,_ in self._last_overlay]
            self.compare_plot.setXRange(-min(durations),0,padding=0)
        elif mode.startswith("vendor24"):
            self.compare_plot.setXRange(1,24,padding=0)
        else:
            self.compare_plot.setXRange(0,10000,padding=0)
        self.compare_plot.enableAutoRange(axis="y")
        mismatch=(len(set(sample_rates))>1)
        self.compare_info.setText(
            f"Наложено {len(self._last_overlay)} архивных измерений "
            f"одного АЦП · {unit} · раздельные временные метки. "
            "Все FFT пересчитаны из сохранённых калиброванных NPZ "
            "без дополнительного FRange, Butterworth или дБ-переопоры; "
            "источники AUX4700 показаны напрямую. "
            +("Fs различается: X ограничена общим реальным Nyquist, "
              "исходные частотные сетки НЕ интерполированы. " if mismatch else "")
            +(("Пропущено: "+"; ".join(skipped)[:400]) if skipped else "")
        )

    def refresh(self,*_):
        self._plot_trend()
        if hasattr(self,"compare_table"):
            self._reload_compare()
