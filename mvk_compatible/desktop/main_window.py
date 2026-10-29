"""Stage111 native Qt window. OFFLINE only; no device commands, HTTP or server.

Delphi MVKView parity is IN PROGRESS: FFT and AC remain labelled candidates.
"""
from __future__ import annotations
from pathlib import Path
import math
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,
    QPushButton,QLabel,QComboBox,QTabWidget,QTableWidget,QTableWidgetItem,
    QSpinBox,QDoubleSpinBox,QCheckBox,QFileDialog,QMessageBox,QHeaderView,
    QScrollBar,QScrollArea,QFrame)
from ..core import OfflineSession
from ..core.envelope_idr_candidate import EnvelopeProfile,ENVELOPE_RATES
from ..core.cursor_format_candidate import format_cursor_idr_candidate
from ..core.spectrum_summary_export_candidate import (spectrum_triplet_text,append_research_summary_csv)
from ..core.envelope_spectrum_idr_candidate import required_original_history
from ..core.tqgrapher_cursor_candidate import CursorGeometry, cursor_from_spectrum


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.session=None
        self.wave_line=None
        self.spec_line=None
        self._full_spectrum=None
        self._spectrum_summary=None
        self.envelope_profile=None  # Optional original local user IDP; never saved or uploaded
        self.setWindowTitle('MVKView Compatible — Stage111 | архив, исследовательская версия')
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
        action=QAction('Открыть локальный архив R6.1/Stage107 ZIP…',self)
        action.setShortcut('Ctrl+O')
        action.triggered.connect(self.choose_archive)
        file_menu.addAction(action)
        file_menu.addAction('Выход',self.close)
        wrapper=QWidget()
        self.setCentralWidget(wrapper)
        layout=QVBoxLayout(wrapper)
        bar=QHBoxLayout()
        button=QPushButton('Открыть архив ZIP…')
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
        layout.addLayout(bar)

        self.tabs=QTabWidget()
        layout.addWidget(self.tabs,1)
        self._calculated_tab()
        self._signal_tab()
        self._spectrum_tab()
        self.note=QLabel('OFFLINE READ-ONLY · TCP/10230 не подключается · команды прибору отсутствуют')
        self.note.setStyleSheet('color: #9e6500; padding: 5px')
        layout.addWidget(self.note)
        self.statusBar().showMessage('Открывайте только локальный ZIP завершённого сеанса Native R6.1')

    def _calculated_tab(self):
        tab=QWidget()
        self.tabs.addTab(tab,'Расчётные данные')
        lay=QVBoxLayout(tab)
        self.calc_source=QLabel('Штатные данные МВК (AUX4700 / VALUES)')
        self.calc_status=QLabel('Статус: —')
        row=QHBoxLayout()
        row.addWidget(self.calc_source)
        row.addStretch()
        row.addWidget(self.calc_status)
        lay.addLayout(row)
        inner=QTabWidget()
        lay.addWidget(inner,1)

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
        sl.addStretch()
        inner.addTab(statuses,'Диагностика')

    def _signal_tab(self):
        tab=QWidget()
        self.tabs.addTab(tab,'Временной сигнал')
        lay=QVBoxLayout(tab)
        bar=QHBoxLayout()
        self.wave_start=self._float(0,300,0)
        self.wave_seconds=self._float(.001,30,1)
        self.wave_mode=QComboBox()
        self.wave_mode.addItems(['AC · NoDC / GetSignal f32 (IDR)','AC+DC · без удаления DC'])
        self.wave_order=QComboBox()
        self.wave_order.addItems(['Архив: хронология BIN','Буфер GetSignal: обратный порядок'])
        self.wave_order.setToolTip('Буфер GetSignal возвращается в обратном порядке; координаты оригинального TQGrapher пока не сверены')
        for name,field in (('Начало, с',self.wave_start),('Окно, с',self.wave_seconds),('Режим',self.wave_mode),('Порядок',self.wave_order)):
            bar.addWidget(QLabel(name));bar.addWidget(field)
        b=QPushButton('Обновить сигнал')
        b.clicked.connect(self.refresh_wave)
        bar.addWidget(b)
        self._zoom_bar(bar,lambda:self._zoom(self.wave_plot,.5),lambda:self._zoom(self.wave_plot,2))
        bar.addStretch()
        lay.addLayout(bar)
        envbar=QHBoxLayout()
        self.wave_envelope_load=QPushButton('Открыть локальный оригинальный IDP для огибающей…')
        self.wave_envelope_load.clicked.connect(self.choose_private_envelope_idp)
        envbar.addWidget(self.wave_envelope_load)
        self.wave_envelope_code=QComboBox()
        self.wave_envelope_code.addItem('Без огибающей',0)
        for code in range(1,32):
            self.wave_envelope_code.addItem(
                f'Код огибающей {code} · таблица {ENVELOPE_RATES[code]} Гц',code)
        self.wave_envelope_code.setEnabled(False)
        self.wave_envelope_code.setToolTip(
            'Режимы по оригинальной таблице IDR; не все доступны при конкретном FSampleRate')
        self.wave_envelope_code.currentIndexChanged.connect(self.refresh_wave)
        envbar.addWidget(self.wave_envelope_code)
        lay.addLayout(envbar)
        self.wave_plot=self._plot('Время, с','Ускорение, м/с²')
        self.wave_plot.scene().sigMouseClicked.connect(self._wave_click)
        lay.addWidget(self.wave_plot,1)
        self.wave_hint=QLabel('AC/AC+DC по GetSignal; огибающая не поддерживается до восстановления коэффициентов. Нажмите для точного отсчёта.')
        self.wave_hint.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.wave_hint)

    def _spectrum_tab(self):
        """DFM-informed panel proportions with FUNCTIONAL Qt scrollbars.

        Original PageSpectrum/pnSpecTools width 177, left command order and
        24-pixel top/right scrollbars are source-verified. Current controls
        remain research Qt widgets; no claim of pixel-perfect Delphi layout.
        """
        tab=QWidget()
        self.tabs.addTab(tab,'Спектр')
        lay=QHBoxLayout(tab)
        lay.setContentsMargins(4,6,4,4)
        lay.setSpacing(0)

        self.spec_tools=QScrollArea()
        self.spec_tools.setObjectName('pnSpecTools')
        self.spec_tools.setFixedWidth(177)
        self.spec_tools.setWidgetResizable(True)
        self.spec_tools.setFrameShape(QFrame.NoFrame)
        tools=QWidget()
        tools.setObjectName('pnSpecToolsBody')
        stack=QVBoxLayout(tools)
        stack.setContentsMargins(9,9,6,9)
        stack.setSpacing(6)

        self.spec_envelope_button=QPushButton('Огибающая — нет')
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
        self.spec_mode.addItems(['0 · дБ (исследователь.)','1 · ускорение',
                                 '2 · скорость','3 · перемещение'])
        self.spec_mode.setFixedHeight(41)
        stack.addWidget(self.spec_mode)

        self.spec_n=QComboBox()
        self.spec_n.setObjectName('bSpecLines')
        self.spec_n.addItems(['1024','4096','16384','65536','262144'])
        self.spec_n.setCurrentText('65536')
        self.spec_n.setFixedHeight(41)
        self.spec_n.setToolTip('Количество отсчётов FFT (оригинальные пресеты bSpecLines требуют дальнейшей сверки)')
        stack.addWidget(self.spec_n)

        self.spec_hscale_button=QPushButton('Горизонталь +')
        self.spec_hscale_button.setObjectName('bSpecHScale')
        self.spec_hscale_button.setFixedHeight(41)
        self.spec_hscale_button.setToolTip('Реальное горизонтальное увеличение ×2; полоса прокрутки появится после приближения')
        self.spec_hscale_button.clicked.connect(lambda:self._zoom(self.spec_plot,.5))
        stack.addWidget(self.spec_hscale_button)

        self.spec_vscale_button=QPushButton('Вертикаль +')
        self.spec_vscale_button.setObjectName('bSpecVScale')
        self.spec_vscale_button.setFixedHeight(41)
        self.spec_vscale_button.setToolTip('Реальное вертикальное увеличение ×2')
        self.spec_vscale_button.clicked.connect(lambda:self.spec_plot.getViewBox().scaleBy((1,.5)))
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

        self.spec_copy_button=QPushButton('Копировать (IDR-кандидат)')
        self.spec_copy_button.setObjectName('bSpecCopyValue')
        self.spec_copy_button.setFixedHeight(41)
        self.spec_copy_button.setEnabled(False)
        self.spec_copy_button.setToolTip(
            'Только 3 локально вычисленные значения: сумма/пик-частота/пик-амплитуда. '
            'Табуляция как в 0084BC28; оригинальная Delphi точность не принята')
        self.spec_copy_button.clicked.connect(self._copy_spec_summary)
        stack.addWidget(self.spec_copy_button)

        self.spec_save_button=QPushButton('Сохранить CSV (IDR-кандидат)')
        self.spec_save_button.setObjectName('bSpecSaveValue')
        self.spec_save_button.setFixedHeight(41)
        self.spec_save_button.setEnabled(False)
        self.spec_save_button.setToolTip(
            'Только локальный CSV sep=|, отдельный от оригинальных SPEC-FREQ; '
            'исходные BIN/IDP не записываются')
        self.spec_save_button.clicked.connect(self._save_spec_summary)
        stack.addWidget(self.spec_save_button)

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
        self.spec_hz=self._float(10,32768,10000,1)
        stack.addWidget(self.spec_hz)
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
        stack.addStretch()
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
        self.spec_hscroll.setRange(0,1000)
        self.spec_hscroll.setPageStep(50)
        self.spec_hscroll.hide()
        grid.addWidget(self.spec_hscroll)
        chart=QHBoxLayout()
        chart.setContentsMargins(0,0,0,0)
        chart.setSpacing(0)
        self.spec_plot=self._plot('Частота, Гц','Амплитуда')
        self.spec_plot.setObjectName('pbSpectrum')
        self.spec_plot.scene().sigMouseClicked.connect(self._spec_click)
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
        self.spec_hscroll.valueChanged.connect(lambda v:self._spec_scroll_changed(0,v))
        self.spec_vscroll.valueChanged.connect(lambda v:self._spec_scroll_changed(1,v))
        self.spec_plot.getViewBox().sigRangeChanged.connect(self._sync_spec_scroll)

        self.spec_mode.currentIndexChanged.connect(self._change_spectrum_mode)
        self.spec_n.currentIndexChanged.connect(self.refresh_spec)
        self.spec_backend.currentIndexChanged.connect(self.refresh_spec)
        self.spec_last.toggled.connect(self.refresh_spec)
        self.spec_hz.editingFinished.connect(self.refresh_spec)
        self.spec_envelope_button.toggled.connect(self._toggle_spec_envelope)
        self.spec_envelope_code.currentIndexChanged.connect(self._spec_envelope_code_changed)

    def _spec_scroll_changed(self,axis:int,value:int):
        if self._full_spectrum is None:return
        vb=self.spec_plot.getViewBox()
        bounds=vb.viewRange()[axis]
        visible=max(1e-12,bounds[1]-bounds[0])
        limits=((0.,float(self.spec_hz.value())) if axis==0
                else (self._spec_data_ymin,self._spec_data_ymax))
        available=max(0.,limits[1]-limits[0]-visible)
        if available<=0:return
        lower=limits[0]+(value/1000.)*available
        if axis==0:vb.setXRange(lower,lower+visible,padding=0)
        else:vb.setYRange(lower,lower+visible,padding=0)

    def _sync_spec_scroll(self,*_):
        if self._full_spectrum is None:return
        vb=self.spec_plot.getViewBox()
        for axis,bar in ((0,self.spec_hscroll),(1,self.spec_vscroll)):
            lo,hi=vb.viewRange()[axis]
            span=hi-lo
            full=((0.,float(self.spec_hz.value())) if axis==0
                  else (self._spec_data_ymin,self._spec_data_ymax))
            remaining=(full[1]-full[0])-span
            active=bool(remaining>max(1e-8,(full[1]-full[0])*1e-5))
            bar.blockSignals(True)
            bar.setVisible(active)
            if active:
                bar.setValue(max(0,min(1000,round((lo-full[0])/remaining*1000))))
                bar.setPageStep(max(1,min(1000,round(span/(full[1]-full[0])*1000))))
            bar.blockSignals(False)

    def _spec_envelope_code_changed(self,*_):
        if self.spec_envelope_button.isChecked():
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
                    # Do not alter source samples; pick the largest exact N
                    self.spec_n.setCurrentText(str(max(valid)))
                    self.statusBar().showMessage('FFT N уменьшен до размера с полной исходной FIR-историей')
            except (ValueError,OSError,KeyError) as e:
                self.spec_envelope_button.blockSignals(True)
                self.spec_envelope_button.setChecked(False)
                self.spec_envelope_button.blockSignals(False)
                self.spec_compare_button.setEnabled(True)
                self.statusBar().showMessage(str(e))
                return
        self.refresh_spec()

    def _change_spectrum_mode(self,*_):
        self.spec_avg.setCurrentIndex(0 if self.spec_mode.currentIndex()==0 else 1)
        self.refresh_spec()

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
        self.tabs.setEnabled(ready)
        self.adc.setEnabled(ready)
        self.tick.setEnabled(ready)

    def choose_archive(self):
        path,_=QFileDialog.getOpenFileName(self,'Локальный экспорт Native R6.1','','ZIP files (*.zip)')
        if path:self.open_archive(path)

    def open_archive(self,path):
        try:
            s=OfflineSession.open(Path(path))
            s.calculations()
            samples,fs,_,_=s.samples(1)
            valid_sizes=[int(self.spec_n.itemText(i)) for i in range(self.spec_n.count())
                         if int(self.spec_n.itemText(i))<=len(samples)]
            if not valid_sizes:
                raise ValueError('Для графического FFT требуется не менее 1024 отсчётов')
        except (OSError,ValueError,KeyError,RuntimeError) as exc:
            QMessageBox.critical(self,'Архив отклонён',str(exc))
            return
        self.session=s
        if int(self.spec_n.currentText())>len(samples):
            self.spec_n.setCurrentText(str(max(valid_sizes)))
        self.title.setText(s.serial+f' · {s.updates} расчётных обновлений')
        self.tick.blockSignals(True)
        self.tick.setRange(1,s.updates)
        self.tick.setValue(s.updates)
        self.tick.blockSignals(False)
        self._set_active(True)
        self.refresh_all()
        self.statusBar().showMessage('Открыт локальный архив · '+Path(path).name)

    def _ch(self):
        return self.adc.currentIndex()+1

    def refresh_all(self,*_):
        if self.session is None:return
        self.refresh_calc()
        self.refresh_wave()
        self.refresh_spec()

    def refresh_calc(self,*_):
        if not self.session:return
        try:
            d=self.session.calculations(self.tick.value()-1)
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
        self.spec_envelope_button.setText('Огибающая IDR (эксперимент)')
        self.spec_envelope_code.setEnabled(True)
        if self.spec_envelope_code.currentIndex()==0:
            self.spec_envelope_code.setCurrentIndex(20)
        self.wave_envelope_load.setText('Локальные коэффициенты готовы (только этот запуск)')
        self.wave_hint.setText(
            'Огибающая доступна только по исходному IDR профилю; '
            'курсоры, исходное время и численный паритет оригинальной MVKView ещё не приняты')

    def _signal_order(self):
        return 'chronological' if self.wave_order.currentIndex()==0 else 'getsignal_buffer'

    def refresh_wave(self,*_):
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
                    f" · локальное СКЗ: {d['rms_m_s2']:.7g} м/с²"
                    " · оригинальный формат/время/курсор НЕ приняты")
            else:
                d=self.session.waveform(self._ch(),self.wave_start.value(),
                                        self.wave_seconds.value(),mode,
                                        display_order=order)
                self.wave_plot.setLabel('bottom','Время BIN, с' if order=='chronological'
                    else 'Позиция буфера GetSignal, с (НЕ время BIN)')
                descr=(f"GetSignal/IDR · {mode} · {order} · {d['window_samples']} отсчётов"
                    f" · локальное СКЗ: {d['rms_m_s2']:.7g} м/с²"
                    f" · удалённое DC: {d['removed_mean_m_s2']:.7g} м/с²"
                    " · паритет TQGrapher НЕ доказан")
            self.wave_plot.clear()
            self.wave_plot.plot(d['time_s'],d['amplitude'],pen=pg.mkPen('#176c92'))
            self.wave_line=pg.InfiniteLine(angle=90,pen=pg.mkPen('#a56017'))
            self.wave_plot.addItem(self.wave_line)
            self.wave_plot.enableAutoRange()
            self.wave_hint.setText(descr)
        except (OSError,KeyError,ValueError) as e:self._error(e)

    def _fft_backend(self):
        return 'idr_float32' if self.spec_backend.currentIndex()==0 else 'numpy'

    def refresh_spec(self,*_):
        if not self.session:return
        try:
            start=None if self.spec_last.isChecked() else self.wave_start.value()
            n_fft=int(self.spec_n.currentText())
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
                       backend=self._fft_backend(),f_range=1.)
            else:
                d=self.session.spectrum(self._ch(),n_fft,self.spec_mode.currentIndex(),
                                        start,max_hz=1e9,max_points=n_fft//2,
                                        backend=self._fft_backend())
            if len(d['amplitude'])!=n_fft//2:
                raise ValueError('Пиксельный курсор требует все N/2 FFT-бинов')
            self._full_spectrum=d
            self._spectrum_summary=d.get('spectrum_summary')
            valid_summary=(isinstance(self._spectrum_summary,dict) and
                self._spectrum_summary.get('source')==
                'APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE')
            self.spec_copy_button.setEnabled(valid_summary)
            self.spec_save_button.setEnabled(valid_summary)
            xx=np.asarray(d['frequency_hz'],dtype=np.float64)
            yy=np.asarray(d['amplitude'],dtype=np.float64)
            visible=xx<=self.spec_hz.value()
            self.spec_plot.clear()
            self.spec_plot.plot(xx[visible],yy[visible],pen=pg.mkPen('#176c92'))
            self.spec_line=pg.InfiniteLine(angle=90,pen=pg.mkPen('#a56017'))
            self.spec_plot.addItem(self.spec_line)
            self.spec_plot.setLabel('left',d['unit'])
            self._spec_data_ymin=float(np.min(yy[visible])) if np.any(visible) else 0.
            self._spec_data_ymax=float(np.max(yy[visible])) if np.any(visible) else 1.
            if self._spec_data_ymax<=self._spec_data_ymin:
                self._spec_data_ymax=self._spec_data_ymin+1.
            self.spec_plot.enableAutoRange()
            self.spec_plot.setXRange(0,self.spec_hz.value(),padding=0)
            self.spec_plot.getViewBox().setLimits(xMin=0,xMax=float(self.spec_hz.value()))
            self._sync_spec_scroll()
            if valid_summary:
                summ=self._spectrum_summary
                self.spec_mean.setText(
                    "GetSpectrum · IDR-кандидат\n"
                    f"Среднее: {summ['output_mean']:.7g} (FRange пока не проверен)\n"
                    f"Пик: {summ['output_peak_frequency_hz']:.7g} Гц\n"
                    f"Амплитуда пика: {summ['output_peak_y']:.7g}\n"
                    f"Ширина FFT: {d['df_hz']:.7g} Гц, N/2={len(xx)}\n"
                    + ("Огибающая, исходные FIR локально" if self.spec_envelope_button.isChecked()
                       else "Без огибающей") + "\nОригинальный численный паритет не доказан")
            else:
                self.spec_mean.setText('Нет принятого локального GetSpectrum summary')
            self.spec_hint.setText(
                f"{d['source']} · {d['fft_backend']} · N/2={len(xx)} исходных бинов · "
                f"df={d['df_hz']:.7g} Гц · среднее DC "
                f"{d.get('raw_mean_removed_m_s2',d.get('removed_mean_m_s2',0.)):.6g} м/с² · "
                + ("после FIR повторного DC нет · "
                   if self.spec_envelope_button.isChecked() else "")
                + "пиксельный курсор TQGrapher — кандидат (Delphi parity НЕ доказан)")
        except (OSError,KeyError,ValueError) as e:
            self._full_spectrum=None
            self._spectrum_summary=None
            self.spec_copy_button.setEnabled(False)
            self.spec_save_button.setEnabled(False)
            self._error(e)

    @staticmethod
    def _clicked_x(plot,event):
        if event.button()!=Qt.LeftButton or not plot.sceneBoundingRect().contains(event.scenePos()):
            return None
        return float(plot.getViewBox().mapSceneToView(event.scenePos()).x())

    def _wave_click(self,event):
        if not self.session:return
        if self.wave_envelope_code.currentData():
            self.statusBar().showMessage('Точный курсор исходной огибающей не принят: показана относительная позиция буфера')
            return
        x=self._clicked_x(self.wave_plot,event)
        if x is None:return
        try:
            mode='ac' if self.wave_mode.currentIndex()==0 else 'acdc'
            order=self._signal_order()
            p=self.session.exact_sample(self._ch(),x,self.wave_start.value(),
                                        self.wave_seconds.value(),mode,order)
            self.wave_line.setPos(p['time_s'])
            self.wave_hint.setText(f"GetSignal[{p['display_index']}] → BIN[{p['index']}]"
                f" · физическое время BIN {p['original_sample_time_s']:.8f} c"
                f" · {p['value_m_s2']:.8g} м/с² · {mode}"
                " · координаты оригинального TQGrapher не сверены")
        except (OSError,KeyError,ValueError) as e:self.statusBar().showMessage(str(e))

    def _spec_click(self,event):
        if not self.session or self._full_spectrum is None:return
        if event.button()!=Qt.LeftButton:return
        try:
            vb=self.spec_plot.getViewBox()
            rect=vb.sceneBoundingRect()
            pos=event.scenePos()
            if not rect.contains(pos) or rect.width()<=2:return
            width=float(rect.width())
            pixel=float(math.trunc(pos.x()-rect.left()))
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
                x_start=x_start,x_scale=df,y_scale=1.)
            found=cursor_from_spectrum(
                self._full_spectrum,pixel,geom,
                precise=self.spec_precise.isChecked(),
                averaging=(1 if self.spec_avg.currentIndex()==0 else 3))
            self.spec_line.setPos(found['frequency_hz'])
            self.spec_hint.setText(
                f"IDR pixel {int(pixel)} · bins [{found['pixel_bin_first']}.."
                f"{found['pixel_bin_last']}] → пик FFT[{found['selected_bin']}]"
                f" · {found['frequency_hz']:.6g} Гц · {found['display_y']:.7g} {found['unit']}"
                f" · avg={found['averaging']} (без /N)"
                f" · {found['fft_backend']} · кандидат TQGrapher"
                f" · текст IDR-кандидат {format_cursor_idr_candidate(found['frequency_hz'])} Гц /"
                f" {format_cursor_idr_candidate(found['display_y'])} {found['unit']}")
        except (OSError,KeyError,ValueError,OverflowError) as e:
            self.statusBar().showMessage(str(e))

    def _copy_spec_summary(self):
        """Source-confirmed 3-column tab structure; formatter still CANDIDATE."""
        if self._spectrum_summary is None:return
        try:
            text=spectrum_triplet_text(self._spectrum_summary,decimal_separator=',')
            QApplication.clipboard().setText(text)
            self.statusBar().showMessage(
                'Скопированы 3 исследовательских значения (IDR кандидат; не приборный DSP)')
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
            report=append_research_summary_csv(filename,self._spectrum_summary)
            self.statusBar().showMessage(
                f"Сохранены 3 локальных IDR-кандидата: {report['path']} (Delphi parity НЕ доказан)")
        except (OSError,UnicodeError,KeyError,TypeError,ValueError) as exc:
            QMessageBox.warning(self,'Локальный CSV не сохранён',str(exc))

    def compare_fft(self):
        if not self.session:return
        try:
            start=None if self.spec_last.isChecked() else self.wave_start.value()
            d=self.session.compare_fft_backends(self._ch(),int(self.spec_n.currentText()),
                                                 self.spec_mode.currentIndex(),start)
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


def run():
    app=QApplication.instance() or QApplication([])
    app.setApplicationName('MVKView Compatible — Stage111')
    win=MainWindow()
    win.show()
    return app.exec()
