"""Stage111Z.25: native Windows Qt controller for the verified Go R6.1 recorder.

No Qt networking and no instrument commands. The Go helper is run only after
operator consent; completed output is rechecked offline before use in the GUI.
"""
from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import QProcess, QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QPushButton,
                               QSpinBox, QVBoxLayout)

from ..core.native_r6_bridge import (CaptureSpec, native_executable,
                                     pack_completed_export, request_graceful_stop)


class ExportPackWorker(QThread):
    ready = Signal(str)
    failed = Signal(str)

    def __init__(self, capture_root: Path, parent=None):
        super().__init__(parent)
        self.capture_root = capture_root

    def run(self):
        try:
            path = pack_completed_export(self.capture_root)
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            self.failed.emit(str(exc))
        else:
            self.ready.emit(str(path))


class NativeCaptureDialog(QDialog):
    archiveReady = Signal(str)
    _NIC_RE = re.compile(r"^\s*\d+\)\s*(.+?)\s*\|\s*IPv4\s+([0-9.]+)/\d+\s*\|\s*индекс\s+\d+", re.I)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Запись с МВК01 · Native R6.1")
        self.resize(750, 650)
        self.setMinimumSize(550, 500)
        self._mode = None
        self._capture_root = None
        self._zip = None
        self._worker = None
        self._stdout = ""
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._read_process)
        self._process.finished.connect(self._process_finished)
        self._process.errorOccurred.connect(self._process_error)
        try:
            self._executable = native_executable()
            self._available = True
            availability = "Встроенный Native R6.1 прошёл локальную проверку SHA256."
        except (OSError, ValueError, UnicodeError) as exc:
            self._executable = None
            self._available = False
            availability = f"Приёмник недоступен: {exc}"

        root = QVBoxLayout(self)
        label = QLabel(
            "Измерения с МВК01 · отдельный уже испытанный приёмник Native R6.1.\n"
            "TCP/10230: только connect → read; команды, изменение параметров и Modbus отсутствуют.")
        label.setWordWrap(True)
        root.addWidget(label)
        self.availability_label = QLabel(availability)
        self.availability_label.setWordWrap(True)
        root.addWidget(self.availability_label)

        form = QFormLayout()
        self.device_ip = QLineEdit()
        self.device_ip.setPlaceholderText("Числовой IPv4 прибора, например 192.168.1.83")
        form.addRow("IP-адрес МВК:", self.device_ip)
        adapter_row = QHBoxLayout()
        self.adapters = QComboBox()
        self.adapters.setObjectName("r6EthernetAdapter")
        self.adapters.setMinimumWidth(270)
        self.adapters.currentIndexChanged.connect(self._sync_buttons)
        adapter_row.addWidget(self.adapters, 1)
        self.refresh_button = QPushButton("Найти адаптеры")
        self.refresh_button.setObjectName("r6ListInterfaces")
        self.refresh_button.clicked.connect(self.refresh_interfaces)
        adapter_row.addWidget(self.refresh_button)
        form.addRow("Проводной Ethernet:", adapter_row)
        self.seconds = QSpinBox()
        self.seconds.setRange(1, 300)
        self.seconds.setValue(30)
        self.seconds.setSuffix(" с")
        form.addRow("Длительность:", self.seconds)
        self.max_mb = QSpinBox()
        self.max_mb.setRange(1, 2048)
        self.max_mb.setValue(256)
        self.max_mb.setSuffix(" МиБ")
        form.addRow("Лимит исходного RAW:", self.max_mb)
        out_row = QHBoxLayout()
        self.output_path = QLineEdit()
        default_output = Path.home() / "Documents" / "MVK10230_Tests"
        # Require explicit existing output directory: the operator can create it
        # using the standard system directory picker.
        self.output_path.setText(str(default_output if default_output.is_dir() else Path.home()))
        out_row.addWidget(self.output_path, 1)
        self.browse_button = QPushButton("Папка…")
        self.browse_button.clicked.connect(self.choose_folder)
        out_row.addWidget(self.browse_button)
        form.addRow("Каталог хранения:", out_row)
        root.addLayout(form)

        info = QLabel(
            "Выбирайте ТОЛЬКО проводной Ethernet. Список показывает активные IPv4, "
            "но не доказывает тип кабельного подключения: Wi-Fi/VPN выбирать нельзя. "
            "Само TCP-подключение может влиять на промышленный прибор. "
            "Для записи необходим допуск ответственного персонала. "
            "RAW и проверенные выгрузки остаются только на этом ПК.")
        info.setWordWrap(True)
        root.addWidget(info)
        self.confirm = QCheckBox(
            "Разрешение на подключение получено, выбран именно Ethernet; "
            "подтверждаю запуск только чтения")
        self.confirm.setObjectName("r6OperatorApproval")
        self.confirm.setWordWrap(True)
        self.confirm.toggled.connect(self._sync_buttons)
        root.addWidget(self.confirm)

        actions = QHBoxLayout()
        self.start_button = QPushButton("Начать запись")
        self.start_button.setObjectName("r6StartCapture")
        self.start_button.clicked.connect(self.start_capture)
        actions.addWidget(self.start_button)
        self.stop_button = QPushButton("Завершить корректно")
        self.stop_button.setObjectName("r6GracefulStop")
        self.stop_button.clicked.connect(self.stop_capture)
        actions.addWidget(self.stop_button)
        self.open_button = QPushButton("Открыть результат")
        self.open_button.setObjectName("r6OpenExport")
        self.open_button.clicked.connect(self.open_result)
        actions.addWidget(self.open_button)
        root.addLayout(actions)
        self.status_label = QLabel("Нет активного подключения. Прибор не опрашивался.")
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("r6CaptureStatus")
        root.addWidget(self.status_label)
        self.log = QPlainTextEdit()
        self.log.setObjectName("r6CaptureLog")
        self.log.setReadOnly(True)
        self.log.document().setMaximumBlockCount(200)
        root.addWidget(self.log, 1)
        self._sync_buttons()

    def is_busy(self):
        return self._mode is not None or self._worker is not None

    def _sync_buttons(self, *_):
        idle = not self.is_busy() and self._process.state() == QProcess.NotRunning
        self.refresh_button.setEnabled(idle and self._available)
        self.start_button.setEnabled(
            idle and self._available and self.confirm.isChecked() and
            self.adapters.currentData() is not None)
        self.stop_button.setEnabled(self._mode == "capture")
        self.open_button.setEnabled(self._zip is not None)
        self.browse_button.setEnabled(idle)

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, "Папка для оригинального RAW и проверенных данных",
            self.output_path.text())
        if path:
            self.output_path.setText(path)

    def refresh_interfaces(self):
        if self.is_busy() or not self._available:
            return
        self.adapters.clear()
        self._stdout = ""
        self._mode = "interfaces"
        self.status_label.setText("Локальный список интерфейсов; подключения к МВК нет.")
        self._process.start(str(self._executable), ["-list-interfaces"])
        self._sync_buttons()

    def _read_process(self):
        message = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._stdout += message
        if len(self._stdout) > 160_000:
            self._stdout = self._stdout[-160_000:]
        if self._mode == "capture" and message:
            # Local screen-only log; no telemetry/upload or raw sample printing.
            self.log.appendPlainText(message.rstrip()[-1800:])

    def _process_error(self, error):
        self.status_label.setText(
            f"Ошибка локального запуска Native R6.1: {self._process.errorString()}. "
            "Подключение и экспорт не подтверждены.")

    def _process_finished(self, exit_code, exit_status):
        mode = self._mode
        self._read_process()
        self._mode = None
        if mode == "interfaces":
            self.adapters.clear()
            if exit_code == 0 and exit_status == QProcess.NormalExit:
                for line in self._stdout.splitlines():
                    match = self._NIC_RE.match(line)
                    if match:
                        self.adapters.addItem(f"{match.group(1)} · {match.group(2)}",
                                              match.group(2))
            self.status_label.setText(
                f"Найдено активных IPv4: {self.adapters.count()}. "
                "Укажите именно проводной Ethernet в Windows."
                if self.adapters.count() else
                "Не удалось получить подходящие IPv4; подключение не выполнялось.")
        elif mode == "capture":
            if exit_code != 0 or exit_status != QProcess.NormalExit:
                self.status_label.setText(
                    "Native R6.1 завершился с ошибкой. RAW/диагностика оставлены в "
                    f"{self._capture_root}; неподтверждённый BIN не открывается.")
            else:
                self.status_label.setText(
                    "Приём окончен. Независимо сверяю RAW, BIN, AUX и создаю архив для Qt…")
                self._worker = ExportPackWorker(self._capture_root, self)
                self._worker.ready.connect(self._pack_ready)
                self._worker.failed.connect(self._pack_failed)
                self._worker.start()
        self._sync_buttons()

    def _pack_ready(self, path):
        self._zip = path
        self.status_label.setText(
            "Проверенный экспорт готов; исходный RAW сохранён в каталоге сессии. "
            "Физическая/графическая идентичность оригиналу пока не аттестована.")
        self.log.appendPlainText("Локальный ZIP для просмотра: " + path)
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.wait()
            worker.deleteLater()
        self._sync_buttons()
        self.archiveReady.emit(path)

    def _pack_failed(self, message):
        self.status_label.setText("Автоматическое открытие отклонено: " + message)
        self.log.appendPlainText(
            "Проверка отказала. Исходный RAW остался нетронутым.")
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.wait()
            worker.deleteLater()
        self._sync_buttons()

    def start_capture(self):
        if self.is_busy() or not self._available:
            return
        try:
            local_ip = self.adapters.currentData()
            if local_ip is None:
                raise ValueError("Выберите локальный проводной Ethernet")
            spec = CaptureSpec(self.device_ip.text(), str(local_ip),
                               int(self.seconds.value()), int(self.max_mb.value()),
                               Path(self.output_path.text()))
            spec.validate()
            if not self.confirm.isChecked():
                raise ValueError("Отсутствует разрешение оператора")
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Запуск запрещён", str(exc))
            return
        response = QMessageBox.question(
            self, "Подтверждение соединения с промышленным МВК",
            f"Начать подключение TCP/10230 к {spec.device_ipv4} через "
            f"выбранный Ethernet {spec.local_ipv4} на {spec.seconds} секунд?\n"
            "Приёмник только читает. Сам TCP Connect может влиять на прибор. "
            "Подтвердите производственный допуск.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if response != QMessageBox.Yes:
            return
        try:
            self._capture_root = spec.create_root()
            args = spec.native_args(self._capture_root)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Ошибка подготовки", str(exc))
            return
        self._zip = None
        self._stdout = ""
        self.log.clear()
        self.confirm.setChecked(False)  # every separate live session needs fresh consent
        self._mode = "capture"
        self.status_label.setText(
            "Запись запускается через Native R6.1. RAW сохраняется без изменений.")
        self._process.start(str(self._executable), args)
        self._sync_buttons()

    def stop_capture(self):
        if self._mode != "capture" or self._capture_root is None:
            return
        try:
            request_graceful_stop(self._capture_root)
        except FileExistsError:
            pass
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Остановка", str(exc))
            return
        self.stop_button.setEnabled(False)
        self.status_label.setText(
            "Запрошена штатная остановка. Native проверяет RAW и завершает экспорт. "
            "Принудительное завершение процесса не используется.")

    def open_result(self):
        if self._zip is not None:
            self.archiveReady.emit(self._zip)

    def closeEvent(self, event):
        if self.is_busy():
            QMessageBox.warning(
                self, "Запись ещё выполняется",
                "Сначала завершите запись и дождитесь проверки архива. "
                "Приёмник нельзя прерывать закрытием окна.")
            event.ignore()
        else:
            super().closeEvent(event)
