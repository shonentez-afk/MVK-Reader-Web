"""Stage111Z31AR: Original task UI components (PageStart buttons, Config, Calib).

Provides:
- OriginalTaskButtons: the 5 DFM-derived task launcher buttons
- OriginalConfigWidget: DFM-style parameter table with proper button sizing
- OriginalCalibWidget: calibration parameters/results skeleton
- No device commands are enabled; all UI is offline read-only.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
)

# DFM constants
DFM_TASK_BUTTON_HEIGHT = 44
DFM_CONFIG_BUTTON_MIN_WIDTH = 120
DFM_CONFIG_BUTTON_MIN_HEIGHT = 44


class OriginalTaskButtons(QWidget):
    """DFM PageStart task launcher with 4 visible + 1 hidden button.

    Buttons:
    - bTaskConnect: Open measurement (ZIP/BIN/TSXML)
    - bTaskConfigCh: Channel setup (research)
    - bTaskView: Open waveform tab
    - bTaskConfigIP: Open spectrum tab
    - bTaskConfigCalib: Hidden by DFM, opens calib tab
    """

    task_connect = Signal()
    task_config_ch = Signal()
    task_view = Signal()
    task_config_ip = Signal()
    task_config_calib = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)

        # Header
        header = QLabel('MVKView Compatible - просмотр измерений')
        header.setObjectName('taskHomeHeading')
        header.setStyleSheet('font-size: 19px; font-weight: 600;')
        lay.addWidget(header)

        # Task buttons
        self.bTaskConnect = self._create_button('Открыть измерение...',
                                                 'Открыть ZIP/BIN/TSXML файл',
                                                 self.task_connect)
        self.bTaskConfigCh = self._create_button('Настройка каналов',
                                                  'Настройка каналов (исследование)',
                                                  self.task_config_ch)
        self.bTaskView = self._create_button('Временной сигнал',
                                             'Перейти к вкладке Сигнал',
                                             self.task_view)
        self.bTaskConfigIP = self._create_button('Спектр',
                                                  'Перейти к вкладке Спектр',
                                                  self.task_config_ip)
        self.bTaskConfigCalib = self._create_button('Калибровка',
                                                     'Перейти к вкладке Калибровка',
                                                     self.task_config_calib,
                                                     visible=False)

        for btn in (self.bTaskConnect, self.bTaskConfigCh,
                     self.bTaskView, self.bTaskConfigIP):
            lay.addWidget(btn)

        # Offline notice
        note = QLabel(
            'Команды настройки прибора и калибровка недоступны. '
            'Запись с прибора - через проверенный Native R6.1. '
            'Оригинальные команды МВК не отправляются.')
        note.setObjectName('taskDeviceOfflineNotice')
        note.setWordWrap(True)
        note.setStyleSheet('color:#776235; padding-top:10px;')
        lay.addWidget(note)
        lay.addStretch()

    @staticmethod
    def _create_button(text: str, tooltip: str, signal=None,
                       visible: bool = True) -> QPushButton:
        btn = QPushButton(text)
        btn.setMinimumHeight(DFM_TASK_BUTTON_HEIGHT)
        btn.setToolTip(tooltip)
        btn.setVisible(visible)
        if signal is not None:
            btn.clicked.connect(signal)
        return btn


class OriginalConfigWidget(QWidget):
    """DFM PageConfig: parameter table with properly-sized buttons.

    Buttons are DFM_CONFIG_BUTTON_MIN_WIDTH (120px), NOT the broken 48px.
    All controls are read-only offline; device commands disabled.
    """

    config_load = Signal()
    config_save = Signal()
    config_get = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)

        header = QLabel('Настройка - параметры прибора')
        header.setObjectName('pageConfigHeader')
        lay.addWidget(header)

        # Parameter table (read-only)
        self.config_table = QTableWidget(0, 3)
        self.config_table.setObjectName('tcConfig')
        self.config_table.setHorizontalHeaderLabels(['Параметр', 'Значение', 'Ед.изм'])
        self.config_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.config_table.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self.config_table, 1)

        # Action buttons with proper sizing
        btn_h = DFM_CONFIG_BUTTON_MIN_HEIGHT
        btn_w = DFM_CONFIG_BUTTON_MIN_WIDTH
        btn_layout = QHBoxLayout()

        self.btnConfigLoad = QPushButton('Загрузить')
        self.btnConfigLoad.setMinimumWidth(btn_w)
        self.btnConfigLoad.setMinimumHeight(btn_h)
        self.btnConfigLoad.setToolTip('Открыть файл параметров')
        self.btnConfigLoad.clicked.connect(self.config_load)
        btn_layout.addWidget(self.btnConfigLoad)

        self.btnConfigSave = QPushButton('Сохранить')
        self.btnConfigSave.setMinimumWidth(btn_w)
        self.btnConfigSave.setMinimumHeight(btn_h)
        self.btnConfigSave.setToolTip('Сохранить параметры')
        self.btnConfigSave.clicked.connect(self.config_save)
        btn_layout.addWidget(self.btnConfigSave)

        self.btnConfigGet = QPushButton('Получить')
        self.btnConfigGet.setMinimumWidth(btn_w)
        self.btnConfigGet.setMinimumHeight(btn_h)
        self.btnConfigGet.setToolTip('Получить с прибора (недоступно)')
        self.btnConfigGet.clicked.connect(self.config_get)
        self.btnConfigGet.setEnabled(False)  # no device connection
        btn_layout.addWidget(self.btnConfigGet)

        btn_layout.addStretch()
        lay.addLayout(btn_layout)


class OriginalCalibWidget(QWidget):
    """DFM PageCalib: calibration parameters/results skeleton.

    All controls disabled for offline mode. Status label explains
    that calibration data is only available through Native R6.1.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)

        header = QLabel('Калибровка - параметры и результаты')
        lay.addWidget(header)

        calib_params = QLabel('Параметры калибровки:')
        lay.addWidget(calib_params)

        # Calibration table (read-only)
        self.calib_table = QTableWidget(0, 3)
        self.calib_table.setObjectName('tblCalib')
        self.calib_table.setHorizontalHeaderLabels(['Параметр', 'Значение', 'Статус'])
        self.calib_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.calib_table.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self.calib_table, 1)

        # Status
        self.calib_status = QLabel(
            'Калибровка недоступна офлайн. Данные калибровки загружаются '
            'только через Native R6.1 с подтверждением.')
        self.calib_status.setObjectName('calibStatus')
        self.calib_status.setStyleSheet('color:#9e6500; padding:4px;')
        lay.addWidget(self.calib_status)
