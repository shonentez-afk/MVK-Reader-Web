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
    QSpinBox,QDoubleSpinBox,QCheckBox,QFileDialog,QMessageBox,QHeaderView)
from ..core import OfflineSession
from ..core.tqgrapher_cursor_candidate import CursorGeometry, cursor_from_spectrum


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.session=None
        self.wave_line=None
        self.spec_line=None
        self._full_spectrum=None
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
        self.wave_plot=self._plot('Время, с','Ускорение, м/с²')
        self.wave_plot.scene().sigMouseClicked.connect(self._wave_click)
        lay.addWidget(self.wave_plot,1)
        self.wave_hint=QLabel('AC/AC+DC по GetSignal; огибающая не поддерживается до восстановления коэффициентов. Нажмите для точного отсчёта.')
        self.wave_hint.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.wave_hint)

    def _spectrum_tab(self):
        tab=QWidget()
        self.tabs.addTab(tab,'Спектр')
        lay=QVBoxLayout(tab)
        bar=QHBoxLayout()
        self.spec_mode=QComboBox()
        self.spec_mode.addItems(['0 · логарифмический дБ (кандидат)',
            '1 · ускорение','2 · скорость','3 · перемещение'])
        self.spec_n=QComboBox()
        self.spec_n.addItems(['1024','4096','16384','65536','262144'])
        self.spec_n.setCurrentText('65536')
        self.spec_backend=QComboBox()
        self.spec_backend.addItems(['IDR float32 · реконструкция','NumPy · контрольный расчёт'])
        self.spec_precise=QCheckBox('Пик в пикселе (IDR)')
        self.spec_precise.setChecked(True)
        self.spec_precise.setToolTip('В оригинальной MVKView при сжатии FFT выбирается максимум в пиксельном интервале')
        self.spec_avg=QComboBox()
        self.spec_avg.addItems(['1 · значение бина','3 · √суммы квадратов, без деления'])
        self.spec_avg.setCurrentIndex(1)
        self.spec_avg.setToolTip('IDR: CursorAveraging 1 или 3; при 3 Delphi НЕ делит сумму квадратов на три')
        self.spec_hz=self._float(10,32768,10000,1)
        self.spec_last=QCheckBox('Последнее полное окно')
        self.spec_last.setChecked(True)
        for name,field in (('Режим',self.spec_mode),('FFT N',self.spec_n),('Алгоритм',self.spec_backend),('Частоты до, Гц',self.spec_hz)):
            bar.addWidget(QLabel(name));bar.addWidget(field)
        bar.addWidget(self.spec_last)
        bar.addWidget(self.spec_precise)
        bar.addWidget(QLabel('Курсор'))
        bar.addWidget(self.spec_avg)
        b=QPushButton('Обновить спектр')
        b.clicked.connect(self.refresh_spec)
        bar.addWidget(b)
        compare=QPushButton('Сравнить FFT')
        compare.setToolTip('IDR float32 vs NumPy; НЕ эталонный Delphi')
        compare.clicked.connect(self.compare_fft)
        bar.addWidget(compare)
        self._zoom_bar(bar,lambda:self._zoom(self.spec_plot,.5),lambda:self._zoom(self.spec_plot,2))
        bar.addStretch()
        lay.addLayout(bar)
        self.spec_plot=self._plot('Частота, Гц','Амплитуда')
        self.spec_plot.scene().sigMouseClicked.connect(self._spec_click)
        lay.addWidget(self.spec_plot,1)
        self.spec_hint=QLabel('Локальный FFT — кандидат по Delphi IDR; численный паритет НЕ доказан.')
        self.spec_hint.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.spec_hint)
        self.spec_mode.currentIndexChanged.connect(self._change_spectrum_mode)
        self.spec_n.currentIndexChanged.connect(self.refresh_spec)
        self.spec_backend.currentIndexChanged.connect(self.refresh_spec)
        self.spec_last.toggled.connect(self.refresh_spec)
        self.spec_hz.editingFinished.connect(self.refresh_spec)

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

    def _signal_order(self):
        return 'chronological' if self.wave_order.currentIndex()==0 else 'getsignal_buffer'

    def refresh_wave(self,*_):
        if not self.session:return
        try:
            mode='ac' if self.wave_mode.currentIndex()==0 else 'acdc'
            order=self._signal_order()
            d=self.session.waveform(self._ch(),self.wave_start.value(),
                                    self.wave_seconds.value(),mode,display_order=order)
            self.wave_plot.clear()
            self.wave_plot.plot(d['time_s'],d['amplitude'],pen=pg.mkPen('#176c92'))
            self.wave_line=pg.InfiniteLine(angle=90,pen=pg.mkPen('#a56017'))
            self.wave_plot.addItem(self.wave_line)
            self.wave_plot.setLabel('bottom','Время BIN, с' if order=='chronological'
                else 'Позиция буфера GetSignal, с (НЕ время BIN)')
            self.wave_plot.enableAutoRange()
            self.wave_hint.setText(f"GetSignal/IDR · {mode} · {order} · {d['window_samples']} отсчётов"
                f" · локальное СКЗ: {d['rms_m_s2']:.7g} м/с²"
                f" · удалённое DC: {d['removed_mean_m_s2']:.7g} м/с²"
                " · огибающая не реализована; паритет TQGrapher НЕ доказан")
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
            d=self.session.spectrum(self._ch(),n_fft,self.spec_mode.currentIndex(),
                                    start,max_hz=1e9,max_points=n_fft//2,
                                    backend=self._fft_backend())
            if len(d['amplitude'])!=n_fft//2:
                raise ValueError('Пиксельный курсор требует все N/2 FFT-бинов')
            self._full_spectrum=d
            xx=np.asarray(d['frequency_hz'],dtype=np.float64)
            yy=np.asarray(d['amplitude'],dtype=np.float64)
            visible=xx<=self.spec_hz.value()
            self.spec_plot.clear()
            self.spec_plot.plot(xx[visible],yy[visible],pen=pg.mkPen('#176c92'))
            self.spec_line=pg.InfiniteLine(angle=90,pen=pg.mkPen('#a56017'))
            self.spec_plot.addItem(self.spec_line)
            self.spec_plot.setLabel('left',d['unit'])
            self.spec_plot.enableAutoRange()
            self.spec_plot.setXRange(0,self.spec_hz.value(),padding=0)
            self.spec_hint.setText(
                f"{d['source']} · {d['fft_backend']} · N/2={len(xx)} исходных бинов · "
                f"df={d['df_hz']:.7g} Гц · среднее DC {d['removed_mean_m_s2']:.6g} м/с² · "
                "пиксельный курсор TQGrapher — кандидат (Delphi parity НЕ доказан)")
        except (OSError,KeyError,ValueError) as e:
            self._full_spectrum=None
            self._error(e)

    @staticmethod
    def _clicked_x(plot,event):
        if event.button()!=Qt.LeftButton or not plot.sceneBoundingRect().contains(event.scenePos()):
            return None
        return float(plot.getViewBox().mapSceneToView(event.scenePos()).x())

    def _wave_click(self,event):
        if not self.session:return
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
                f" · {found['fft_backend']} · кандидат TQGrapher")
        except (OSError,KeyError,ValueError,OverflowError) as e:
            self.statusBar().showMessage(str(e))

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
