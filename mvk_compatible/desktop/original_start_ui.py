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
import sys
from ..core.original_device_ip_settings import (
    startup_device_address,save_compatible_device_address,
)

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFileDialog,QLabel,QLineEdit,QListWidget,QListWidgetItem,
    QPushButton,QSizePolicy,QWidget,
)

from ..core.original_start_workbench import (
    OriginalStartWorkspace,START_BUTTONS,START_IP_DEFAULT,
    START_LIBRARY_DEFAULT,START_IP_RECT,START_LIBRARY_RECT,
    START_OPERATOR_CAPTIONS,START_OPERATOR_IP_LABEL,
    START_OPERATOR_LIBRARY_LABEL,START_OPERATOR_REFERENCE,
    source_measure_button_caption,
)
from ..core.original_ui_form_contract import ORIGINAL_TASK_BUTTONS
from .source_visual_skin import SourceStartBackdrop
from .source_start_command import SourceStartCommandButton


class OriginalStartController:
    """One real Qt PageStart bound to immutable original session options."""

    def __init__(self,window,navigation):
        self.window=window
        self.navigation=navigation
        source_ip,self._settings_origin=startup_device_address()
        self.workspace=OriginalStartWorkspace(device_ipv4=source_ip)
        self._saved_device_ip=source_ip
        home=window.task_subpages.widget(0)
        # The SOURCE PageStart hosts the whole 992x766 logical TTabSheet.
        # A fixed 494px Qt-only wrapper cropped source imLogo at y568 and
        # shifted all five DFM buttons below research headers. Use a fully
        # expandable source client with in-memory optional original TImages.
        self.host=SourceStartBackdrop(home)
        self.host.setMinimumWidth(0)
        self.host.setMinimumHeight(494)
        self.host.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        # The real original idle screenshot establishes both title and
        # smaller description. Core MODE dispatch is independent of text.
        captions=START_OPERATOR_CAPTIONS
        self.host.setProperty("sourceTaskCaptionsReference",
                              START_OPERATOR_REFERENCE)
        self.buttons={}
        expected={x[0]:x for x in ORIGINAL_TASK_BUTTONS}
        for name,x,y,w,h,image,tab,route in START_BUTTONS:
            # Original DFM is the same source as previous core contract.
            if expected[name]!=(name,x,y,w,h,image):
                raise ValueError("Source original PageStart DFM geometry drift")
            title,subtitle=captions[name]
            b=SourceStartCommandButton(title,subtitle,image,self.host)
            b.setObjectName(name)
            b.setGeometry(x,y,w,h)
            b.setProperty("originalDfmLogicalRect",(x,y,w,h))
            b.setProperty("originalDfmImageName",image)
            b.setProperty("originalDfmTabOrder",tab)
            b.setProperty("originalHandlerMode",route)
            b.setProperty("sourceOperatorCaptionEvidence",
                          "original-idle-screenshot-20261116")
            b.setProperty("sourceSafeCoreRoutePreserved",True)
            # No forensic DFM coordinates in the normal operator UI.
            b.setToolTip(subtitle or title)
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
                b.setToolTip(subtitle or title)
                b.clicked.connect(
                    lambda _=False:self.open_config_mode(4))

        ip_caption=QLabel(START_OPERATOR_IP_LABEL,self.host)
        ip_caption.setObjectName("lbStartSourceIP")
        ip_caption.setGeometry(29,208,124,24)
        ip_caption.setStyleSheet(
            "QLabel#lbStartSourceIP {font: 12px Tahoma; color: #171717;}")
        self.ip_edit=QLineEdit(self.host)
        self.ip_edit.setObjectName("edIpAddr")
        self.ip_edit.setGeometry(*START_IP_RECT)
        self.ip_edit.setText(self.workspace.device_ipv4)
        self.ip_edit.setToolTip(
            "Исходное значение из DFM, не подтверждённый IP подключённого "
            "прибора. Числовой IPv4 проверяется при явном выборе захвата.")
        self.ip_edit.editingFinished.connect(self.commit_ip)

        caption=QLabel(START_OPERATOR_LIBRARY_LABEL,self.host)
        caption.setObjectName("lbStartLibrary")
        caption.setGeometry(29,252,320,22)
        caption.setStyleSheet(
            "QLabel#lbStartLibrary {font: 12px Tahoma; color: #171717;}")
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

        self.technical_widgets=(
            self.native_note,extra,self.library_files,
            refresh,open_selected,self.status)
        for widget in self.technical_widgets:
            widget.hide()
        # Remove the extra Qt research heading, summary and 24px insets
        # from the SOURCE page. They are still held in the widget tree
        # for backward-compatible technical diagnostics.
        home.layout().setContentsMargins(0,0,0,0)
        home.layout().setSpacing(0)
        home.layout().insertWidget(0,self.host,1)
        for old in (window.task_open_button,window.task_capture_button,
                    window.task_signal_button,window.task_spectrum_button,
                    window.task_metrics_button):
            old.hide()
        for name in ("taskHomeHeading","taskSessionSummary",
                     "taskDeviceOfflineNotice"):
            obsolete=home.findChild(QWidget,name)
            if obsolete is not None:
                obsolete.hide()
        self.apply_private_icons()
        window.original_start_controller=self
        self.sync_measurement_button()

    def sync_measurement_button(self):
        """Source task command switches caption on entering/leaving Mode2.

        Original source runtime localization keys are source-verified;
        the alternative Russian text is a compatible fallback only.
        """
        mode2=bool(self.window._measurement_mode_selected)
        caption,key=source_measure_button_caption(mode2)
        button=self.buttons["bTaskConnect"]
        button.setText(caption)
        button.setProperty("sourceOriginalCaptionKey",key)
        button.setProperty("sourceOriginalCaptionTranslationVerified",not mode2)
        button.setProperty("sourceMode2ButtonDisconnectAction",mode2)
        return key

    def apply_private_icons(self):
        """Install only transient private DFM icons on real Qt buttons."""
        icons=self.host.private_task_icons
        names={row[0]:row[5] for row in START_BUTTONS}
        installed=[]
        for name,button in self.buttons.items():
            pixmap=icons.get(names[name])
            if pixmap is None:
                continue
            button.setIcon(QIcon(pixmap))
            button.setProperty("sourceOriginalCommandBitmapProvided",True)
            button.setProperty("sourceTaskCommandImageCandidate",False)
            button.setProperty("sourceIconLoadedOnlyInMemory",True)
            installed.append(name)
        return tuple(installed)

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
            f"Выбран IP: {self.workspace.device_ipv4}; "
            "прибор не опрашивался")
        if (getattr(sys,"frozen",False) and
                self._saved_device_ip!=self.workspace.device_ipv4):
            try:
                save_compatible_device_address(self.workspace.device_ipv4)
                self._saved_device_ip=self.workspace.device_ipv4
            except (ValueError,OSError) as exc:
                self.status.setText("IP изменён локально, но сохранение отклонено: "+str(exc))
        return True

    def apply_capture_device_ip(self,ip):
        """The operator explicitly approved this dialog IPv4 for ONE capture.

        Mirror the verified choice in source edIpAddr. Never change a NIC
        address, start another socket, or edit the vendor's original XML.
        """
        next_state=self.workspace.with_device_ip(ip)
        self.ip_edit.setText(next_state.device_ipv4)
        return self.commit_ip()

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
        skin=getattr(self.window,"original_visual_skin",None)
        if skin is not None:
            skin.reveal_page(5)
        else:
            self.navigation.setCurrentIndex(5)
        self.status.setText(
            "Открыта проверенная локальная запись: "+source.name+
            " · прибор не опрашивался")
        return True

    def open_config_mode(self,mode):
        if mode not in (4,6):raise ValueError("Original local config mode")
        self.window.original_config_panel.set_source_mode(mode)
        skin=getattr(self.window,"original_visual_skin",None)
        if skin is not None:
            skin.reveal_page(1)
        else:
            self.navigation.setCurrentIndex(1)
        return mode

    def open_file_page(self):
        """Original bTaskView Mode1 opens the native BIN file dialog.

        The 2026-11-16 operator screenshot shows a Windows 'Открытие'
        file picker filtered to temporal-signal BIN. It does NOT first
        navigate to PageFile. Cancel keeps the previous source page;
        accepted BIN/TSXML/ZIP is decoded by the existing verified Core.
        """
        self.workspace.source_route("bTaskView")
        self.window.choose_archive()
        return self.navigation.currentIndex()

    def open_capture_dialog(self):
        """Mode2 selects five pages before a TCP connection is attempted.

        Original _Unit128 00848E78 -> 00846D24..00846D84 -> 00846DCC:
        SetTabVisible/pnMeasure happens BEFORE TMVKThread constructor.
        Operator consent for the separate passive Go capture is unchanged.
        """
        if self.window._measurement_mode_selected:
            # Native Go has a tested, file-backed graceful stop protocol.
            return self.window.request_measurement_stop()
        panel=getattr(self.window,"original_config_panel",None)
        task0=getattr(panel,"_task0_dialog",None)
        if task0 is not None and getattr(task0,"_mode",None)=="read":
            self.status.setText(
                "Task0 считывает конфигурацию. "
                "Сначала завершите текущее TCP-соединение.")
            return False
        if not self.commit_ip():
            return False
        self.workspace.source_route("bTaskConnect")
        if not self.window.enter_measurement_mode():
            return False
        self.window.open_native_capture()
        dialog=getattr(self.window,"_native_dialog",None)
        if dialog is not None:
            dialog.device_ip.setText(self.workspace.device_ipv4)
            if self.workspace.library_path is not None:
                dialog.output_path.setText(str(self.workspace.directory()))
        self.status.setText("Режим измерения: ожидание подключения")
        return True
