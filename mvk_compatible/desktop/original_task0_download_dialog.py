"""Original bConfigDownloadClick: safe asynchronous Task0 real TCP read.

This is intentionally a *read* action from source PageConfig/Mode4:
never send original Task3/4/5 Flash, reboot or config upload commands.
There is one QProcess -> one selected-NIC Go socket; Qt owns no TCP
client. A real industrial TCP connection requires separate approval.
"""
from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import QProcess,Qt,Signal
from PySide6.QtWidgets import (
    QCheckBox,QComboBox,QDialog,QFileDialog,QFormLayout,QHBoxLayout,
    QLabel,QLineEdit,QMessageBox,QPushButton,QVBoxLayout,
)

from ..core.native_r6_bridge import (
    native_executable,request_graceful_stop,validate_ipv4,
)
from ..core.original_task0_config_live import (
    SourceTask0DownloadSpec,load_source_task0_config,
)


class OriginalTask0DownloadDialog(QDialog):
    readCompleted=Signal(object)
    _NIC_RE=re.compile(
        r"^\s*\d+\)\s*(.+?)\s*\|\s*IPv4\s+([0-9.]+)/\d+\s*\|\s*индекс\s+\d+",
        re.I,
    )

    def __init__(self,device_ip:str,parent=None):
        super().__init__(parent)
        self._device_ip=validate_ipv4(device_ip,field="edIpAddr")
        self.setObjectName("originalTask0DownloadDialog")
        self.setWindowTitle("МВК01 — Считать конфигурацию")
        self.resize(540,290)
        self._root=None
        self._mode=None
        self._output=""
        self._process=QProcess(self)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._received_stdout)
        self._process.finished.connect(self._process_finished)
        self._process.errorOccurred.connect(self._process_error)
        try:
            self._native=native_executable()
        except (ValueError,OSError,UnicodeError):
            self._native=None
        layout=QVBoxLayout(self)
        note=QLabel(
            "Исходная функция «Считать»: TMVKThread Task0. "
            "Получает конфигурацию с прибора, без передачи SetRate, "
            "записи во Flash и перезагрузки.",self)
        note.setWordWrap(True)
        layout.addWidget(note)
        form=QFormLayout()
        self.device_edit=QLineEdit(self._device_ip,self)
        self.device_edit.setObjectName("originalTask0DeviceIP")
        self.device_edit.setReadOnly(True)
        form.addRow("IP-адрес прибора:",self.device_edit)
        ethernet=QHBoxLayout()
        self.interfaces=QComboBox(self)
        self.interfaces.setObjectName("originalTask0Ethernet")
        self.interfaces.currentIndexChanged.connect(self._buttons)
        ethernet.addWidget(self.interfaces,1)
        self.refresh_button=QPushButton("Найти Ethernet",self)
        self.refresh_button.clicked.connect(self.refresh_interfaces)
        ethernet.addWidget(self.refresh_button)
        form.addRow("Проводной адаптер:",ethernet)
        folder=QHBoxLayout()
        preferred=Path.home()/"Documents"
        self.output_edit=QLineEdit(
            str(preferred if preferred.is_dir() else Path.home()),self)
        self.output_edit.setObjectName("originalTask0SaveDir")
        folder.addWidget(self.output_edit,1)
        self.browse=QPushButton("…",self)
        self.browse.clicked.connect(self.choose_folder)
        folder.addWidget(self.browse)
        form.addRow("Локальный RAW:",folder)
        layout.addLayout(form)
        self.confirm=QCheckBox(
            "Разрешаю отдельное TCP/10230-подключение для чтения конфигурации "
            "с выбранного проводного Ethernet",self)
        self.confirm.setObjectName("originalTask0OperatorConsent")
        self.confirm.toggled.connect(self._buttons)
        layout.addWidget(self.confirm)
        row=QHBoxLayout()
        self.download=QPushButton("Считать конфигурацию",self)
        self.download.setObjectName("originalTask0StartDownload")
        self.download.clicked.connect(self.start_read)
        row.addWidget(self.download)
        self.stop=QPushButton("Остановить",self)
        self.stop.clicked.connect(self.stop_read)
        row.addWidget(self.stop)
        layout.addLayout(row)
        self.status=QLabel(
            "Прибор не опрашивался. Сначала выберите Ethernet и подтвердите допуск.",
            self)
        self.status.setObjectName("originalTask0DownloadStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        if self._native is None:
            self.status.setText(
                "Встроенный Go-приёмник с проверенным SHA256 недоступен; "
                "реальное считывание Task0 не запускается.")
        self._buttons()

    def _busy(self)->bool:
        return self._mode in ("interfaces","read")

    def _buttons(self,*_):
        free=not self._busy() and self._process.state()==QProcess.NotRunning
        self.refresh_button.setEnabled(free and self._native is not None)
        self.download.setEnabled(
            free and self._native is not None and
            self.confirm.isChecked() and self.interfaces.currentData() is not None)
        self.stop.setEnabled(self._mode=="read")
        self.browse.setEnabled(free)

    def choose_folder(self):
        if self._busy():return
        p=QFileDialog.getExistingDirectory(
            self,"Локальный каталог Task0",self.output_edit.text())
        if p:self.output_edit.setText(p)

    def refresh_interfaces(self):
        if self._busy() or self._native is None:return False
        self.interfaces.clear()
        self._output=""
        self._mode="interfaces"
        self._process.start(str(self._native),["-list-interfaces"])
        self.status.setText("Только локальный список адаптеров; к МВК не подключаемся.")
        self._buttons()
        return True

    def _received_stdout(self):
        text=bytes(self._process.readAllStandardOutput()).decode(
            "utf-8",errors="replace")
        self._output=(self._output+text)[-100000:]

    def _process_error(self,error):
        if error==QProcess.FailedToStart:
            self._mode=None
            self.status.setText("Не удалось запустить проверенный Native Go для Task0.")
            self._buttons()

    def start_read(self):
        if (self._busy() or self._native is None or not self.confirm.isChecked()
                or self.interfaces.currentData() is None):
            return False
        try:
            spec=SourceTask0DownloadSpec(
                self._device_ip,str(self.interfaces.currentData()),
                Path(self.output_edit.text()))
            spec.validate()
        except (ValueError,OSError) as exc:
            QMessageBox.warning(self,"Task0: запуск отклонён",str(exc))
            return False
        response=QMessageBox.question(
            self,"Подтвердите соединение с МВК01",
            f"Подключиться к {spec.device_ipv4}:10230 через "
            f"Ethernet {spec.local_ipv4} для чтения конфигурации Task0?\n"
            "TCP-соединение может повлиять на промышленный прибор. "
            "Исходящие SetRate, Flash, Reset и Upload запрещены.",
            QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if response!=QMessageBox.Yes:return False
        try:
            self._root=spec.create_root()
            args=spec.native_args(self._root)
        except (ValueError,OSError) as exc:
            QMessageBox.warning(self,"Task0: каталог",str(exc))
            return False
        self._output=""
        self._mode="read"
        self.confirm.setChecked(False)  # never persist hardware approval
        self.status.setText(
            "Чтение исходного Task0. Ожидается проверенный непустой PARAM; "
            "поля конфигурации ещё неизвестны.")
        self._process.start(str(self._native),args)
        self._buttons()
        return True

    def stop_read(self):
        if self._mode!="read" or self._root is None:return False
        try:
            request_graceful_stop(self._root)
        except FileExistsError:
            pass
        except (ValueError,OSError) as exc:
            QMessageBox.warning(self,"Остановка Task0",str(exc))
            return False
        self.stop.setEnabled(False)
        self.status.setText(
            "Запрошено штатное завершение Task0. Не выдаём незавершённый "
            "RAW за конфигурацию прибора.")
        return True

    def _process_finished(self,exit_code,exit_status):
        previous=self._mode
        self._received_stdout()
        self._mode=None
        if previous=="interfaces":
            self.interfaces.clear()
            if exit_code==0 and exit_status==QProcess.NormalExit:
                for line in self._output.splitlines():
                    found=self._NIC_RE.match(line)
                    if found:self.interfaces.addItem(
                        f"{found.group(1)} · {found.group(2)}",found.group(2))
            self.status.setText(
                f"Доступных IPv4: {self.interfaces.count()}. "
                "Проверьте, что выбран именно проводной Ethernet.")
        elif previous=="read":
            if exit_code!=0 or exit_status!=QProcess.NormalExit:
                self.status.setText(
                    "Task0 не завершил проверенное чтение. "
                    "Локальный RAW сохранён для диагностики, "
                    "конфигурация прибора не обновлена.")
            else:
                try:
                    proof=load_source_task0_config(
                        self._root,expected_ip=self._device_ip)
                except (ValueError,OSError,UnicodeError) as exc:
                    self.status.setText(
                        "Ответ Task0 не прошёл независимую проверку RAW: "
                        +str(exc))
                else:
                    self.status.setText(
                        f"Task0: проверенных полей {proof['confirmed_fields']}; "
                        "данные получены без команд устройству.")
                    self.readCompleted.emit(proof)
        self._buttons()

    def closeEvent(self,event):
        if self._busy():
            QMessageBox.warning(
                self,"Task0 работает",
                "Сначала завершите Task0 кнопкой «Остановить». "
                "Активный процесс нельзя прерывать без закрытия RAW.")
            event.ignore()
        else:
            super().closeEvent(event)
