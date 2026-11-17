"""Stage111Z.25: native Windows Qt controller for the verified Go R6.1 recorder.

No second Qt networking client. The Go helper runs only after consent; the
original 36-byte SetRate is separately authorized and is OFF by default.
Completed output is rechecked offline before use in the GUI.
"""
from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import QProcess, QThread, QTimer, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
                               QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem,
                               QHeaderView, QVBoxLayout)

from ..core.native_r6_bridge import (CaptureSpec, native_executable,
                                     pack_completed_export, request_graceful_stop)
from ..core.native_r6_live_status import load_capture_live_status
from ..core.native_r6_live_preview import load_live_preview
from ..core.source_frame_mark_protocol import submit_native_frame_mark
from ..core.original_mode2_source_rate_input import source_setrate_stdin_line
from ..core.source_tcp_segments import verify_source_tcp_session_segments


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
    # Source-validated Go JSON transport status, never a device STATUS
    # snapshot or a second TCP connection.
    statusReady = Signal(object)
    statusInvalid = Signal(str)
    captureStarted = Signal()
    captureEnded = Signal(bool)
    previewReady = Signal(object)
    previewInvalid = Signal(str)
    _NIC_RE = re.compile(r"^\s*\d+\)\s*(.+?)\s*\|\s*IPv4\s+([0-9.]+)/\d+\s*\|\s*индекс\s+\d+", re.I)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Запись с МВК01 · Native R6.1")
        self.resize(750, 650)
        self.setMinimumSize(550, 500)
        self._mode = None
        self._source_mode2_disarmed = False
        self._capture_root = None
        self._zip = None
        self._raw_only_dir = None
        self._worker = None
        self._stdout = ""
        self._active_device_ipv4 = None
        self._active_local_ipv4 = None
        self._source_rate_tx_enabled = False
        self._source_auto_reconnect_enabled = False
        self._live_last_error = None
        self._last_preview_stamp = None
        self._preview_last_error = None
        self._frame_mark_sequence = 0
        self._timer = QTimer(self)
        self._timer.setInterval(900)
        self._timer.timeout.connect(self._poll_live_status)
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
            "TCP/10230: приём без команд по умолчанию. Оригинальная SetRate "
            "доступна только после отдельного разрешения; Flash/Reboot запрещены.")
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
        self.seconds.setRange(0, 300)
        self.seconds.setSpecialValueText("До отключения")
        self.seconds.setSuffix(" с")
        self.seconds.setValue(0)  # original TMVKThread runs until stopped
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
            "Разрешение на подключение получено, выбран именно Ethernet")
        self.confirm.setObjectName("r6OperatorApproval")
        self.confirm.toggled.connect(self._sync_buttons)
        root.addWidget(self.confirm)
        self.source_rate_tx = QCheckBox(
            "Разрешаю оригинальную передачу SetRate при измерении "
            "и изменение частоты через штатное меню (36 байт; только эта команда)")
        self.source_rate_tx.setObjectName("r6OriginalSourceSetRateTX")
        self.source_rate_tx.setChecked(False)
        self.source_rate_tx.setToolTip(
            "На реальном МВК это может изменить параметры измерения. "
            "Не включайте без допуска к управлению прибором. "
            "Flash, reboot и запись конфигурации не разрешаются.")
        root.addWidget(self.source_rate_tx)
        self.source_auto_reconnect=QCheckBox(
            "Автоматически переподключаться после обрыва измерения; "
            "сохранять каждый TCP-сеанс как отдельный RAW с SHA256")
        self.source_auto_reconnect.setObjectName("r6OriginalTask2ReconnectAfterRAW")
        self.source_auto_reconnect.setChecked(False)
        # Separate opt-in source TCP connection; never toggles SetRate.
        self.source_auto_reconnect.setEnabled(True)
        self.source_auto_reconnect.setToolTip(
            "Без отдельного разрешения SetRate команды прибору не передаются. "
            "Повторные TCP-подключения возможны только с отдельным согласием; "
            "все сокеты хранятся отдельными SHA256 RAW, общий BIN запрещён.")
        root.addWidget(self.source_auto_reconnect)

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
        self.progress = QProgressBar()
        self.progress.setObjectName("r6LiveProgress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)
        self.live_quality = QLabel("Каналы: ожидаются данные Native R6.1; DSP ещё не получен.")
        self.live_quality.setObjectName("r6LiveQuality")
        self.live_quality.setWordWrap(True)
        root.addWidget(self.live_quality)
        self.live_tabs = QTabWidget()
        self.live_channels = QTableWidget(10, 6)
        self.live_channels.setObjectName("r6LiveChannelQuality")
        self.live_channels.setHorizontalHeaderLabels(
            ["Канал", "Отсчётов", "Fs, Гц", "Разрывы", "Статус DSP", "Качество"])
        self.live_channels.setEditTriggers(QTableWidget.NoEditTriggers)
        self.live_channels.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.live_channels.verticalHeader().setVisible(False)
        self._reset_live_channels()
        self.live_tabs.addTab(self.live_channels, "Каналы · live")
        self.log = QPlainTextEdit()
        self.log.setObjectName("r6CaptureLog")
        self.log.setReadOnly(True)
        self.log.document().setMaximumBlockCount(200)
        self.live_tabs.addTab(self.log, "Журнал")
        root.addWidget(self.live_tabs, 1)
        self._sync_buttons()

    def _reset_live_channels(self):
        for i in range(10):
            name = f"АЦП {i+1}" if i < 8 else f"TACH {i-7}"
            for col, value in enumerate((name, "—", "—", "—", "—", "Нет данных")):
                self.live_channels.setItem(i, col, QTableWidgetItem(str(value)))

    def _poll_live_status(self):
        if self._capture_root is None:
            return
        try:
            snapshot = load_capture_live_status(
                self._capture_root, instrument_ipv4=self._active_device_ipv4,
                local_ipv4=self._active_local_ipv4)
        except (ValueError, OSError) as exc:
            message = str(exc)
            if message != self._live_last_error:
                self.log.appendPlainText("Live статус не подтверждён: " + message)
                self._live_last_error = message
            self.live_quality.setText("Live-индикатор недостоверен. RAW продолжает писаться Native R6.1.")
            self.statusInvalid.emit(message)
            self.previewInvalid.emit("Статус потока не проверен: "+message)
            return
        if snapshot is None:
            self.live_quality.setText("Ожидание локального состояния Native R6.1; нет второй сети.")
            self.statusInvalid.emit("Нет текущего подтверждённого состояния")
            self.previewInvalid.emit("Ожидание подтверждённого статуса Native R6.1")
            return
        self._live_last_error = None
        self.statusReady.emit(snapshot)
        target = snapshot["target_seconds"]
        elapsed = snapshot["elapsed_seconds"]
        phase = snapshot["phase"]
        if target == 0:
            # A time-unbounded source session has no honest time-based
            # percentage; Go still enforces the selected RAW byte limit.
            active = phase in ("CONNECTING","RECORDING")
            self.progress.setRange(0,0 if active else 100)
            if not active:
                self.progress.setValue(100 if phase == "COMPLETED" else 0)
            self.progress.setFormat("До отключения · ограничение по RAW")
            duration = f"{elapsed:.1f} с с момента запуска · до отключения"
        else:
            self.progress.setRange(0,100)
            self.progress.setValue(min(100, max(0, round(100 * elapsed / target))))
            self.progress.setFormat("%p%")
            duration = f"{elapsed:.1f} / {target} с"
        frames = snapshot["frames_decoded"]
        raw_mb = snapshot["raw_bytes"] / (1024 * 1024)
        phase_names = {
            "CONNECTING": "Подключение (после разрешения оператора)",
            "RECORDING": "Запись RAW",
            "VERIFYING": "Проверка экспорта",
            "COMPLETED": "Проверенный экспорт Native готов",
            "REFUSED": "Native отказал в проверенном экспорте",
        }
        attempts=snapshot.get("source_initial_retry_attempts",0)
        if phase=="CONNECTING" and attempts:
            causes={
                "CONNECT_FAILED":"ошибки установления TCP",
                "REMOTE_DISCONNECTED":"разрыва соединения",
                "SOURCE_READ_TIMEOUT":"тайм-аута чтения 5 с",
                "SOCKET_READ_FAILED":"ошибки чтения сокета",
            }
            reason=causes.get(snapshot.get("source_retry_last_error"),"обрыва связи")
            phase_names["CONNECTING"]=(
                f"Повторное подключение TCP #{attempts} после {reason}")
        freshness = (" · УСТАРЕВШИЙ статус" if snapshot["snapshot_stale"] else "")
        self.status_label.setText(
            f'{phase_names.get(phase, phase)}: {duration}, '
            f'RAW {raw_mb:.1f} МиБ, кадров {frames}, AUX {snapshot["aux4700_updates"]}'
            f'{freshness}')
        invalid = snapshot["invalid_frames"]
        warning = snapshot["warning_count"]
        alerts = sum(c["quality"] in ("ОШИБКА ПОТОКА", "DSP: ПРЕДУПРЕЖДЕНИЕ")
                     for c in snapshot["channels"])
        if snapshot["quality_alert"]:
            label = f"ВНИМАНИЕ: {alerts} каналов с замечаниями, ошибок кадров {invalid}, предупреждений {warning}"
        else:
            label = "Нет обнаруженных ошибок потока; это НЕ подтверждение точности датчиков/FFT."
        if snapshot["aux4700_updates"] == 0:
            label += " · Статусы DSP пока НЕ получены."
        source_ticks=snapshot.get("source_values_ticks_address_3100")
        if source_ticks is not None:
            label += (f" · Исходные VALUES 0x3100: {source_ticks}; "
                      f"AUX4700: {snapshot['aux4700_updates']} "
                      "(разные события).")
        if snapshot.get("source_rate_transition_during_live"):
            label += (" · ИЗМЕНЕНИЕ ЧД: весь RAW сохраняется, но одиночный "
                      "BIN не может считаться проверенным; экспорт будет отклонён.")
        if snapshot.get("source_tcp_multi_socket"):
            label += (" · ПЕРЕПОДКЛЮЧЕНИЕ: TCP-сеансов "
                      f"{snapshot['source_tcp_connection_count']}; "
                      "отдельные RAW, единый BIN не допускается.")
        if attempts and phase=="CONNECTING":
            label += (
                f" · Исходная пауза перед повтором: "
                f"{snapshot.get('source_retry_wait_ms',0)} мс."
                " Соединение ещё НЕ подтверждено.")
        self.live_quality.setText(label)
        for i, ch in enumerate(snapshot["channels"]):
            fs = ", ".join(str(x) for x in ch["sample_rates_hz"]) or "—"
            status = ch["dsp_sensor_status_hex"] or "Не получен"
            values = [f"АЦП {i+1}" if i < 8 else f"TACH {i-7}",
                      str(ch["samples"]), fs,
                      str(ch["sequence_discontinuities"]), status, ch["quality"]]
            for col, value in enumerate(values):
                self.live_channels.item(i, col).setText(value)
        # At most one bounded preview per new atomic snapshot, never a second
        # TCP client and never an on-disk partial BIN. Failed provenance must
        # CLEAR any previously displayed provisional data.
        if snapshot.get("source_tcp_multi_socket"):
            self.previewInvalid.emit(
                "После переподключения исходная история графиков не может "
                "считаться непрерывной; RAW разделён по TCP-сеансам")
            return
        if snapshot.get("source_rate_transition_during_live"):
            self.previewInvalid.emit(
                "Исходная ЧД изменилась в текущем сеансе; прежнее "
                "превью скрыто, полный RAW продолжает сохраняться")
            return
        if snapshot["phase"] != "RECORDING":
            self.previewInvalid.emit("Запись не в фазе RECORDING: предварительные графики скрыты")
            return
        try:
            preview = load_live_preview(self._capture_root, snapshot)
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            message = str(exc)
            if message != self._preview_last_error:
                self.log.appendPlainText("Live preview: " + message)
                self._preview_last_error = message
            self.previewInvalid.emit(message)
            return
        if preview is None:
            return
        self._preview_last_error = None
        if preview.updated_utc != self._last_preview_stamp:
            self._last_preview_stamp = preview.updated_utc
            self.previewReady.emit(preview)

    def is_busy(self):
        return self._mode is not None or self._worker is not None

    def _original_mode2_authorized(self):
        """The selected source Mode2 must still own this preflight dialog.

        This check prevents a previously opened consent form from
        starting an industrial socket after «Отключить» was clicked.
        """
        if self._source_mode2_disarmed:
            return False
        owner=self.parent()
        return (owner is None or
                not hasattr(owner,"_measurement_mode_selected") or
                bool(owner._measurement_mode_selected))

    def disarm_before_tcp(self):
        """Detach an unused source preflight after the second Measure click.

        Never kills an approved live process; the owner may only call
        this while _live_active is false.
        """
        if self._mode=="capture":
            return False
        self._source_mode2_disarmed=True
        self.confirm.setChecked(False)
        self.status_label.setText(
            "Измерение отменено до TCP; ранее открытое подтверждение "
            "не даёт права нового подключения.")
        self._sync_buttons()
        self.hide()
        return True

    def _sync_buttons(self, *_):
        idle = not self.is_busy() and self._process.state() == QProcess.NotRunning
        self.refresh_button.setEnabled(idle and self._available)
        self.start_button.setEnabled(
            idle and self._available and self._original_mode2_authorized()
            and self.confirm.isChecked() and
            self.adapters.currentData() is not None)
        self.stop_button.setEnabled(self._mode == "capture")
        self.open_button.setEnabled(self._zip is not None or self._raw_only_dir is not None)
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
        if error == QProcess.FailedToStart:
            if self._mode == "capture":
                self.previewInvalid.emit("Локальный приёмник не запущен")
                self.captureEnded.emit(False)
            self._timer.stop()
            self._mode = None
            self._sync_buttons()

    def _expose_verified_socket_raw(self):
        """Open local raw-only evidence when uninterrupted BIN is impossible.

        No second network client and no fake ZIP accepted by original pages.
        """
        if self._capture_root is None:
            return False
        try:
            receipt=verify_source_tcp_session_segments(self._capture_root)
        except (OSError,ValueError):
            return False
        self._raw_only_dir=self._capture_root
        self.log.appendPlainText(
            f"RAW TCP-сеансов проверены: {receipt['connection_count']}; "
            "отдельные SHA256 и SOURCE_TASK2_TCP_SEGMENTS.json подтверждены.")
        return True

    def _process_finished(self, exit_code, exit_status):
        mode = self._mode
        self._read_process()
        if mode == "capture":
            self._poll_live_status()
            self._timer.stop()
        self._mode = None
        self._source_rate_tx_enabled = False
        self._source_auto_reconnect_enabled = False
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
                if self._expose_verified_socket_raw():
                    self.status_label.setText(
                        "Измерение завершено. TCP-сеансы и отдельные RAW с SHA256 "
                        "сохранены и проверены. Единый BIN/TSXML не создаётся; "
                        "кнопка «Открыть результат» откроет локальную папку.")
                else:
                    self.status_label.setText(
                        "Native R6.1 завершился с ошибкой. RAW/диагностика оставлены в "
                        f"{self._capture_root}; неподтверждённый BIN не открывается.")
                self.captureEnded.emit(False)
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
        self.captureEnded.emit(True)
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
        self.captureEnded.emit(False)
        self.status_label.setText("Автоматическое открытие отклонено: " + message)
        if self._expose_verified_socket_raw():
            self.log.appendPlainText(
                "BIN отклонён; отдельные TCP RAW с SHA256 доступны по кнопке результата.")
        else:
            self.log.appendPlainText(
                "Проверка отказала. Исходный RAW остался нетронутым.")
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.wait()
            worker.deleteLater()
        self._sync_buttons()

    def start_capture(self):
        if not self._original_mode2_authorized():
            self.status_label.setText(
                "Запуск запрещён: исходный режим «Измерить» уже отключён.")
            return False
        if self.is_busy() or not self._available:
            return False
        try:
            local_ip = self.adapters.currentData()
            if local_ip is None:
                raise ValueError("Выберите локальный проводной Ethernet")
            spec = CaptureSpec(self.device_ip.text(), str(local_ip),
                               int(self.seconds.value()), int(self.max_mb.value()),
                               Path(self.output_path.text()),
                               source_rate_tx=self.source_rate_tx.isChecked(),
                               source_auto_reconnect=self.source_auto_reconnect.isChecked())
            spec.validate()
            if not self.confirm.isChecked():
                raise ValueError("Отсутствует разрешение оператора")
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Запуск запрещён", str(exc))
            return
        response = QMessageBox.question(
            self, "Подтверждение соединения с промышленным МВК",
            f"Начать подключение TCP/10230 к {spec.device_ipv4} через "
            f"выбранный Ethernet {spec.local_ipv4} "
            f"{spec.duration_description()}?\n" +
            ("ВНИМАНИЕ: будет отправлена исходная 36-байтная SetRate(65536) "
             "после подтверждённого PARAM; меню сможет отправлять новые SetRate. "
             "Это может изменить частоту прибора. Flash/Reboot исключены. "
             if spec.source_rate_tx else
             "Пассивный режим: клиент только читает. ")+
            ("ПОСЛЕ РАЗРЫВА возможны повторные TCP-подключения "
             + ("с отдельно разрешённой SetRate; " if spec.source_rate_tx
                else "БЕЗ исходящих команд SetRate; ")
             + "каждый сеанс будет отдельным RAW, единый BIN не создаётся. "
             if spec.source_auto_reconnect else "")+
            "Сам TCP Connect может влиять на прибор. Подтвердите производственный допуск.",
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
        self._raw_only_dir = None
        self._stdout = ""
        self._active_device_ipv4 = spec.device_ipv4
        self._active_local_ipv4 = spec.local_ipv4
        self._source_rate_tx_enabled = spec.source_rate_tx
        self._source_auto_reconnect_enabled=spec.source_auto_reconnect
        # Source edIpAddr remains the one operator-selected device address.
        # A dialog override is reflected into PageStart before Go starts;
        # this is not Ethernet NIC autodetection or a second TCP socket.
        controller=getattr(self.parent(),"original_start_controller",None)
        if controller is not None:
            controller.apply_capture_device_ip(spec.device_ipv4)
        self._live_last_error = None
        self._last_preview_stamp = None
        self._preview_last_error = None
        self._frame_mark_sequence = 0
        self._reset_live_channels()
        self.progress.setRange(0,100)
        self.progress.setValue(0)
        self.live_quality.setText("Подключение ожидается. Состояние датчиков ещё неизвестно.")
        self.log.clear()
        self.confirm.setChecked(False)  # every separate live session needs fresh consent
        self.source_rate_tx.setChecked(False)  # reset dangerous permission after use
        self.source_auto_reconnect.setChecked(False)
        self._mode = "capture"
        self.status_label.setText(
            "Запись запускается через Native R6.1. RAW сохраняется без изменений.")
        self._process.start(str(self._executable), args)
        self.captureStarted.emit()
        self._timer.start()
        self._sync_buttons()

    def send_source_frame_mark(self,kind,begin,plan,session_id):
        """Send an operator mark to the ONE Go local recorder, never MVK TCP.

        The file is atomically published in the previously approved local
        capture root. Go acknowledges at its NEXT decoded frame boundary,
        not at this Qt button click or the previous 900ms status poll.
        """
        if (self._mode!="capture" or self._capture_root is None or
                self._process.state()!=QProcess.Running):
            raise ValueError("Source frame recording has no active native receiver")
        if kind not in ("data","values") or type(begin) is not bool:
            raise ValueError("Invalid original source start/stop operation")
        next_sequence=self._frame_mark_sequence+1
        event=kind+("_begin" if begin else "_end")
        receipt=submit_native_frame_mark(
            self._capture_root,next_sequence,session_id,event,plan)
        self._frame_mark_sequence=next_sequence
        self.log.appendPlainText(
            f"Локальный запрос {next_sequence}: {event}; "
            "ожидается точная граница следующего декодированного кадра. "
            "Приборных команд нет.")
        return receipt

    def source_rate_tx_active(self):
        return bool(self._source_rate_tx_enabled and
                    self._mode == "capture" and
                    self._process.state() == QProcess.Running)

    def send_source_rate(self,rate:int)->bool:
        """Source original mRate1Click → SetRate through EXISTING Go socket.

        Per-capture QProcess stdin. Never open a separate TCP client or
        send a generic register/Flash/reboot command.
        """
        if not self.source_rate_tx_active():
            raise ValueError("Реальная отправка SetRate не была разрешена")
        if type(rate) is not int or rate not in (65536,32768,8192,2048,512):
            raise ValueError("Неподтверждённая исходная частота")
        command=source_setrate_stdin_line(rate)
        actual=self._process.write(command)
        if actual!=len(command):
            raise RuntimeError("Очередь изменения частоты Go не приняла запрос")
        self.log.appendPlainText(f"Запрошена оригинальная SetRate({rate}); "
                                 "фактическая TX подтверждается Native статусом")
        return True

    def stop_capture(self):
        if self._mode != "capture" or self._capture_root is None:
            return False
        try:
            request_graceful_stop(self._capture_root)
        except FileExistsError:
            pass
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Остановка", str(exc))
            return False
        self.stop_button.setEnabled(False)
        self.status_label.setText(
            "Запрошена штатная остановка. Native проверяет RAW и завершает экспорт. "
            "Принудительное завершение процесса не используется.")
        return True

    def open_result(self):
        if self._zip is not None:
            self.archiveReady.emit(self._zip)
        elif self._raw_only_dir is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._raw_only_dir)))

    def closeEvent(self, event):
        if self.is_busy():
            QMessageBox.warning(
                self, "Запись ещё выполняется",
                "Сначала завершите запись и дождитесь проверки архива. "
                "Приёмник нельзя прерывать закрытием окна.")
            event.ignore()
        else:
            self._timer.stop()
            super().closeEvent(event)
