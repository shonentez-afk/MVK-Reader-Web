"""Stage111Z31BU: visible original PageStart DFM-geometry and real library.

Source _Unit128:
  bTaskViewClick 00848E84         -> original Mode1 (local view)
  bTaskConnectClick 00848E78      -> original Mode2 (device flow)
  bTaskConfigIPClick 00848E6C     -> original Mode4
  bTaskConfigChClick 00848E60     -> original Mode6
  bTaskConfigCalibClick 00848D78  -> original Mode5 after UserQuery
  edLibraryPathAfterDialog 00848E90 normalises selected folder.
  DFM edIpAddr 157,208,173x24; edLibraryPath 29,276,301x24.
  Five original bsCommandLink buttons use exact source logical rectangles.

Private original icon/bitmap assets are NOT copied. Additional local
file list is explicitly labelled COMPATIBLE offline functionality.
No programmatic device connection or background scans happen here.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt,QSize
from PySide6.QtWidgets import (
    QFileDialog,QLabel,QLineEdit,QListWidget,QListWidgetItem,
    QPushButton,QSizePolicy,QStyle,QWidget,
)

from ..core.original_start_workbench import (
    OriginalStartWorkspace,START_BUTTONS,START_IP_DEFAULT,
    START_LIBRARY_DEFAULT,START_IP_RECT,START_LIBRARY_RECT,
)
from ..core.original_ui_form_contract import ORIGINAL_TASK_BUTTONS


class OriginalStartController:
    """One real Qt PageStart bound to immutable original session options."""

    def __init__(self,window,navigation):
        self.window=window
        self.navigation=navigation
        self.workspace=OriginalStartWorkspace()
        home=window.task_subpages.widget(0)
        self.host=QWidget(home)
        self.host.setObjectName("SourcePageStartLauncher")
        self.host.setMinimumWidth(840)
        self.host.setFixedHeight(494)
        self.host.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        captions={
            "bTaskConnect":"Подключение к прибору",
            "bTaskConfigCh":"Настройка каналов",
            "bTaskView":"Просмотр измерений",
            "bTaskConfigIP":"Настройка IP",
            "bTaskConfigCalib":"Калибровка",
        }
        images={
            "bTaskConnect":QStyle.SP_DriveNetIcon,
            "bTaskConfigCh":QStyle.SP_FileDialogDetailedView,
            "bTaskView":QStyle.SP_DialogOpenButton,
            "bTaskConfigIP":QStyle.SP_ComputerIcon,
            "bTaskConfigCalib":QStyle.SP_FileDialogContentsView,
        }
        self.buttons={}
        expected={x[0]:x for x in ORIGINAL_TASK_BUTTONS}
        for name,x,y,w,h,image,tab,route in START_BUTTONS:
            # Original DFM is the same source as previous core contract.
            if expected[name]!=(name,x,y,w,h,image):
                raise ValueError("Source original PageStart DFM geometry drift")
            b=QPushButton(captions[name],self.host)
            b.setObjectName(name)
            b.setGeometry(x,y,w,h)
            b.setProperty("originalDfmLogicalRect",(x,y,w,h))
            b.setProperty("originalDfmImageName",image)
            b.setProperty("originalDfmTabOrder",tab)
            b.setProperty("originalHandlerMode",route)
            b.setIcon(b.style().standardIcon(images[name]))
            b.setIconSize(QSize(32,32))
            b.setToolTip(
                f"Original _Unit128 {name}: DFM ({x},{y},{w},{h}), "
                f"Mode{route}; иконка системная, не исходная.")
            self.buttons[name]=b
            if name=="bTaskConfigCalib":
                b.setEnabled(False)
                b.hide()  # source design-time Visible=False
            elif name=="bTaskView":
                b.clicked.connect(self.open_file_page)
            elif name=="bTaskConnect":
                b.clicked.connect(self.open_capture_dialog)
            elif name=="bTaskConfigCh":
                b.clicked.connect(
                    lambda _=False:self.open_config_mode(6))
            elif name=="bTaskConfigIP":
                b.setToolTip(
                    "Исходный Mode4 ConfigIP · локальный файл, без прибора")
                b.clicked.connect(
                    lambda _=False:self.open_config_mode(4))

        ip_caption=QLabel("IP-адрес МВК:",self.host)
        ip_caption.setObjectName("lbStartSourceIP")
        ip_caption.setGeometry(29,208,124,24)
        self.ip_edit=QLineEdit(self.host)
        self.ip_edit.setObjectName("edIpAddr")
        self.ip_edit.setGeometry(*START_IP_RECT)
        self.ip_edit.setText(START_IP_DEFAULT)
        self.ip_edit.setToolTip(
            "Исходное значение из DFM, не подтверждённый IP подключённого "
            "прибора. Числовой IPv4 проверяется при явном выборе захвата.")
        self.ip_edit.editingFinished.connect(self.commit_ip)

        caption=QLabel("Каталог записей (исходный edLibraryPath):",self.host)
        caption.setObjectName("lbStartLibrary")
        caption.setGeometry(29,252,320,22)
        self.library_edit=QLineEdit(self.host)
        self.library_edit.setObjectName("edLibraryPath")
        self.library_edit.setGeometry(*START_LIBRARY_RECT)
        self.library_edit.setText(START_LIBRARY_DEFAULT)
        self.library_edit.setReadOnly(True) # Original TJvDirectoryEdit DirectInput=False
        self.library_edit.setToolTip(
            "Выбор только существующей локальной папки; звёздочка из DFM "
            "не обозначает доступную папку и не запускает поиск.")
        browse=QPushButton("…",self.host)
        browse.setObjectName("sourceLibraryBrowse")
        browse.setGeometry(305,276,25,24)
        browse.clicked.connect(self.choose_library)

        self.native_note=QLabel(
            "Native R6.1: подключение только после подтверждения "
            "оператором в отдельном окне. IP и каталог не применяются "
            "автоматически.",self.host)
        self.native_note.setObjectName("sourceStartSafeConnectionNote")
        self.native_note.setWordWrap(True)
        self.native_note.setGeometry(370,206,455,85)

        extra=QLabel(
            "Локальные записи выбранного каталога · дополнительный "
            "офлайн-просмотр (не оригинальный DFM список):",self.host)
        extra.setObjectName("sourceStartLibraryListLabel")
        extra.setGeometry(29,315,800,25)
        self.library_files=QListWidget(self.host)
        self.library_files.setObjectName("localSourceLibraryFiles")
        self.library_files.setGeometry(29,340,800,80)
        self.library_files.setToolTip(
            "Нет фонового сканирования. Только явная локальная папка; "
            "каждый файл перед открытием повторно проверяется Core.")
        refresh=QPushButton("Обновить список файлов",self.host)
        refresh.setObjectName("localSourceLibraryRefresh")
        refresh.setGeometry(29,427,185,29)
        refresh.clicked.connect(self.refresh_files)
        open_selected=QPushButton("Открыть выбранное измерение",self.host)
        open_selected.setObjectName("localSourceLibraryOpen")
        open_selected.setGeometry(228,427,235,29)
        open_selected.setEnabled(False)
        open_selected.clicked.connect(self.open_selected_file)
        self.library_files.currentRowChanged.connect(
            lambda index:open_selected.setEnabled(
                index>=0 and self.workspace.library_path is not None))
        self.open_selected=open_selected
        self.status=QLabel(
            "Исходный IP DFM: 192.168.0.30 · каталог '*': ещё не выбран",
            self.host)
        self.status.setObjectName("sourceStartEvidence")
        self.status.setGeometry(29,461,800,24)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)

        home.layout().insertWidget(2,self.host)
        for old in (window.task_open_button,window.task_capture_button,
                    window.task_signal_button,window.task_spectrum_button,
                    window.task_metrics_button):
            old.hide()
        window.original_start_controller=self

    def commit_ip(self):
        try:
            next_state=self.workspace.with_device_ip(
                self.ip_edit.text())
        except (ValueError,OSError) as exc:
            self.ip_edit.setStyleSheet(
                "QLineEdit#edIpAddr { border: 1px solid #bf6a40; }")
            self.status.setText("Неверный локальный IPv4: "+str(exc))
            return False
        self.workspace=next_state
        self.ip_edit.setStyleSheet("")
        self.status.setText(
            f"Числовой IP сохранён только в интерфейсе: "
            f"{self.workspace.device_ipv4} · прибор не опрашивался")
        return True

    def set_library(self,path):
        self.workspace=self.workspace.with_library(path)
        self.library_edit.setText(str(self.workspace.directory()))
        self.refresh_files()
        return self.workspace

    def choose_library(self):
        path=QFileDialog.getExistingDirectory(
            self.host,"Исходный каталог локальных измерений","")
        if not path:return
        try:self.set_library(path)
        except (ValueError,OSError) as exc:
            self.status.setText("Каталог записи отклонён: "+str(exc))

    def refresh_files(self):
        blocked=self.library_files.blockSignals(True)
        try:
            self.library_files.clear()
            self.open_selected.setEnabled(False)
            entries=self.workspace.list_recordings()
            for record in entries:
                item=QListWidgetItem(
                    f"{record.basename}  · {record.size_bytes} байт",
                    self.library_files)
                item.setData(Qt.UserRole,record.basename)
        except (ValueError,OSError) as exc:
            self.status.setText(
                "Исходная библиотека недоступна: "+str(exc))
            return ()
        finally:
            self.library_files.blockSignals(blocked)
        self.status.setText(
            f"Каталог выбран · доступных локальных файлов: {len(entries)}; "
            "ничего не передано прибору")
        return entries

    def open_selected_file(self):
        item=self.library_files.currentItem()
        if item is None or self.window._live_active:
            return False
        try:
            source=self.workspace.selected_file(item.data(Qt.UserRole))
        except (ValueError,OSError) as exc:
            self.status.setText("Локальная запись отклонена: "+str(exc))
            return False
        # MainWindow.open_archive validates the source BIN/TSXML/SHA
        # and independently binds PageAdc/Spectrum/Status/File.
        prior=self.window.session
        self.window.open_archive(source)
        if self.window.session is None or self.window.session is prior:
            self.status.setText("Локальный источник не открыт")
            return False
        self.navigation.setCurrentIndex(5)
        self.status.setText(
            "Открыта проверенная локальная запись: "+source.name+
            " · прибор не опрашивался")
        return True

    def open_config_mode(self,mode):
        if mode not in (4,6):raise ValueError("Original local config mode")
        self.window.original_config_panel.set_source_mode(mode)
        self.navigation.setCurrentIndex(1)
        return mode

    def open_file_page(self):
        self.workspace.source_route("bTaskView")
        self.navigation.setCurrentIndex(5)
        return 5

    def open_capture_dialog(self):
        """Only show consent-gated Native dialog; absolutely no auto-start."""
        if not self.commit_ip():
            return False
        self.workspace.source_route("bTaskConnect")
        self.window.open_native_capture()
        dialog=getattr(self.window,"_native_dialog",None)
        if dialog is not None:
            dialog.device_ip.setText(self.workspace.device_ipv4)
            if self.workspace.library_path is not None:
                dialog.output_path.setText(str(self.workspace.directory()))
        self.status.setText(
            "Открыт диалог Native R6.1: требуется явное разрешение "
            "оператора; приёмник ещё не запущен")
        return True
