"""Modern MVK Live main-shell adapter for the existing verified receiver.

A single Qt main window owns the Native service. Other windows never create
network sockets. This module only reorganizes and renders already decoded
Float32 samples: Native gain, device Fs and AUX4700 are not modified.
"""
from __future__ import annotations

import json
import math
import os

from PySide6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from .graph_policies import filter_magnitude_response


DARK = {
    "canvas": "#0D141C", "panel": "#17212D", "plot": "#101A24",
    "border": "#293847", "text": "#EBF1F7", "muted": "#A7B6C7",
    "accent": "#4CAFCB", "fft": "#F3B85C", "time": "#5CCFC5",
}
LIGHT = {
    "canvas": "#F5F7FA", "panel": "#FFFFFF", "plot": "#FFFFFF",
    "border": "#DFE5EB", "text": "#182633", "muted": "#566575",
    "accent": "#167F9C", "fft": "#A85F0C", "time": "#007C78",
}


def _detach_layout(layout, parent):
    parent.removeItem(layout)
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget() is not None:
            item.widget().hide()
        elif item.layout() is not None:
            _hide_layout(item.layout())


def _hide_layout(layout):
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget() is not None:
            item.widget().hide()
        elif item.layout() is not None:
            _hide_layout(item.layout())


def _field(column, text, widget):
    """Responsive vertical label+control, never a 2-column legacy form."""
    row = QtWidgets.QWidget()
    body = QtWidgets.QVBoxLayout(row)
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(3)
    label = QtWidgets.QLabel(text)
    label.setProperty("fieldLabel", True)
    label.setWordWrap(True)
    body.addWidget(label)
    # Long MVKView labels must not enlarge the inspector beyond the dock.
    widget.setMinimumWidth(0)
    widget.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored,
                         QtWidgets.QSizePolicy.Policy.Fixed)
    body.addWidget(widget)
    column.addWidget(row)
    row.show()
    widget.show()
    if isinstance(widget, QtWidgets.QComboBox):
        widget.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        widget.setMinimumContentsLength(8)
        if not widget.toolTip():
            widget.setToolTip(widget.currentText())
            widget.currentTextChanged.connect(widget.setToolTip)
    return row


def _title(text):
    lab = QtWidgets.QLabel(text)
    lab.setWordWrap(True)
    lab.setProperty("sectionTitle", True)
    return lab


def _hint(text):
    label = QtWidgets.QLabel(text)
    label.setWordWrap(True)
    label.setProperty("helpText", True)
    return label


def _filter_selector_for_operators(combo):
    """Readable display groups over the existing filter keys and DSP logic.

    Keep every legacy filter available; the MVKView nomenclature is grouped
    under compatibility instead of being confused with the normal workflow.
    """
    selected = combo.currentData()
    groups = (
        (
            ("Без фильтра", "none",
             "Пропускать исходный подтверждённый сигнал без локального фильтра."),
            ("ФВЧ · высокочастотный", "highpass",
             "Оставить частоты выше указанной нижней границы."),
            ("ФНЧ · низкочастотный", "lowpass",
             "Оставить частоты ниже указанной верхней границы."),
            ("Полосовой · диапазон частот", "bandpass",
             "Оставить полосу от нижней до верхней границы."),
            ("Режектор 50 Гц", "notch50",
             "Только вручную: частота 50 Гц может быть полезным признаком вибрации."),
            ("Режектор 60 Гц", "notch60",
             "Только вручную: частота 60 Гц может быть полезным признаком вибрации."),
        ),
        (
            ("1/1 октавы · фильтр сигнала", "octave",
             "Локальная полосовая фильтрация; не режим 1/3-октавного спектра."),
            ("1/3 октавы · фильтр сигнала", "third_octave",
             "Локальная полосовая фильтрация; не приборные данные AUX4700."),
            ("2 октавы · фильтр сигнала", "double_octave",
             "Локальная полосовая фильтрация до расчёта."),
        ),
        (
            ("Меню MVKView · 32 полосы", "original_preset",
             "Исторические названия полос; локальный фильтр, не OEM FIR."),
        ),
    )
    with QtCore.QSignalBlocker(combo):
        combo.clear()
        for pos, group in enumerate(groups):
            if pos:
                combo.insertSeparator(combo.count())
            for label, key, tooltip in group:
                combo.addItem(label, key)
                combo.setItemData(
                    combo.count() - 1, tooltip,
                    QtCore.Qt.ItemDataRole.ToolTipRole)
        index = combo.findData(selected)
        combo.setCurrentIndex(index if index >= 0 else 0)


def _mirror_control(source, column, label, *, rebuild_on=(),
                    force_select=None):
    """One source of truth across Overview and the detailed graph page.

    The source may rebuild its physical Y-height choices when switching
    from dB to m/s², mm/s or µm; the overview must mirror the NEW list,
    not retain a stale menu created at application startup.
    """
    proxy = QtWidgets.QComboBox()
    def sync(*_):
        values = [(source.itemText(i), source.itemData(i))
                  for i in range(source.count())]
        current = [(proxy.itemText(i), proxy.itemData(i))
                   for i in range(proxy.count())]
        with QtCore.QSignalBlocker(proxy):
            if current != values:
                proxy.clear()
                for caption, value in values:
                    proxy.addItem(caption, value)
            proxy.setCurrentIndex(source.currentIndex())
            proxy.setEnabled(source.isEnabled())
    def quick_changed(index):
        if index < 0:
            return
        if index != source.currentIndex():
            source.setCurrentIndex(index)
        elif force_select is not None:
            # An operator can restore the same four-mode preset after
            # choosing an advanced kind/dB combination on the Spectrum tab.
            force_select()
    source.currentIndexChanged.connect(sync)
    for signal in rebuild_on:
        signal.connect(sync)
    sync()
    proxy.currentIndexChanged.connect(quick_changed)
    _field(column, label, proxy)
    return proxy


def _quick_card(title, subtitle):
    frame = QtWidgets.QFrame()
    frame.setObjectName("quickSettingsCard")
    layout = QtWidgets.QVBoxLayout(frame)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)
    layout.addWidget(_title(title))
    layout.addWidget(_hint(subtitle))
    return frame, layout


def apply_theme(win, theme="system"):
    if theme not in ("system", "dark", "light"):
        theme = "system"
    if theme == "system":
        try:
            scheme = QtGui.QGuiApplication.styleHints().colorScheme()
            dark = scheme == QtCore.Qt.ColorScheme.Dark
        except (AttributeError, RuntimeError):
            dark = False
    else:
        dark = theme == "dark"
    c = DARK if dark else LIGHT
    win._modern_theme = theme
    if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
        QtCore.QSettings("MVK", "MVK Live").setValue("ui/theme_v1", theme)
    win.setStyleSheet("""
        QWidget { background-color: %(canvas)s; color: %(text)s;
                  font-family: 'Segoe UI'; font-size: 13px; }
        QMenuBar, QMenu { background-color: %(panel)s; }
        QMenuBar::item:selected, QMenu::item:selected {
            background-color: %(border)s; }
        QTabWidget::pane { border: 0; }
        QTabBar::tab { background: transparent; color: %(muted)s;
            padding: 9px 15px; border: none; border-bottom: 2px solid transparent; }
        QTabBar::tab:selected { color: %(text)s; border-bottom: 2px solid %(accent)s; }
        QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
            background-color: %(panel)s; border: 1px solid %(border)s;
            border-radius: 6px; padding: 6px 9px; min-height: 21px; }
        QPushButton:hover, QComboBox:hover { border-color: %(accent)s; }
        QPushButton:disabled { color: %(muted)s; }
        QPushButton[primary="true"] { background-color: %(accent)s;
             border: 1px solid %(accent)s; color: %(canvas)s; font-weight: 600; }
        QToolTip { background-color: %(panel)s; color: %(text)s;
                   border: 1px solid %(border)s; }
        QDockWidget::title { background-color: %(panel)s; padding: 8px; }
        QScrollArea, QFrame { border: none; }
        QTableWidget, QTableView { background-color: %(panel)s;
            alternate-background-color: %(canvas)s; gridline-color: %(border)s; }
        QLabel[sectionTitle="true"] { font-weight: 600; font-size: 15px; }
        QLabel[metricLabel="true"] { color: %(muted)s; font-size: 11px; }
        QLabel[fieldLabel="true"] { color: %(muted)s; font-size: 12px; }
        QLabel[metricValue="true"] { font-weight: 600; font-size: 18px; }
        QFrame#kpiCard { background-color: %(panel)s;
             border-radius: 8px; border: 1px solid %(border)s; }
        QFrame#kpiCard QLabel { background: transparent; border: none; }
        QFrame#quickSettingsCard {
            background-color: %(panel)s; border-radius: 8px;
            border: 1px solid %(border)s; }
        QFrame#quickSettingsCard QLabel { background: transparent; }
        QLabel[helpText="true"] { color: %(muted)s; font-size: 12px; }
    """ % c)
    for plot in (getattr(win, "spec", None),
                 getattr(win, "wave", None),
                 getattr(win, "overview_spec", None),
                 getattr(win, "overview_wave", None)):
        if plot is None:
            continue
        plot.setBackground(c["plot"])
        for ax in ("left", "bottom"):
            obj = plot.getPlotItem().getAxis(ax)
            obj.setPen(pg.mkPen(c["border"]))
            obj.setTextPen(pg.mkPen(c["muted"]))
    win.spec_curve.setPen(pg.mkPen(c["fft"], width=1.3))
    win.wave_curve.setPen(pg.mkPen(c["time"], width=1.2))
    if hasattr(win, "overview_spec_curve"):
        win.overview_spec_curve.setPen(pg.mkPen(c["fft"], width=1.3))
        win.overview_wave_curve.setPen(pg.mkPen(c["time"], width=1.2))


def _filter_response_dialog(win, which):
    if which == "spectrum":
        s = win._read_settings()
        band, notch = s[3], s[7]
        mode = win.filter_choice.currentData()
    else:
        mode = win.time_filter_choice.currentData()
        notch = {"notch50": 50., "notch60": 60.}.get(mode)
        if mode == "original_preset":
            pair = win.time_filter_center.currentData()
            if not isinstance(pair, tuple) or len(pair) != 2:
                QtWidgets.QMessageBox.warning(win, "АЧХ фильтра", "Выберите полосу")
                return
            mode, centre = pair
        elif mode in ("octave", "third_octave", "double_octave"):
            centre = win.time_filter_center.currentData()
        else:
            centre = None
        if mode in ("octave", "third_octave", "double_octave"):
            from .octave_filters import preset_band
            ch = win._gui_ring.channel(win.adc.currentData())
            if ch is None:
                QtWidgets.QMessageBox.information(
                    win, "АЧХ фильтра", "Нужна подтверждённая Fs выбранного АЦП")
                return
            band = preset_band(mode, centre, ch.rate_hz)
        elif mode == "highpass":
            band = (win.time_filter_low, None)
        elif mode == "lowpass":
            band = (0., win.time_filter_high)
        elif mode == "bandpass":
            band = (win.time_filter_low, win.time_filter_high)
        else:
            band = (0., None)
    ch = win._gui_ring.channel(win.adc.currentData())
    if ch is None:
        QtWidgets.QMessageBox.information(
            win, "АЧХ фильтра", "Частота дискретизации пока неизвестна. Приём данных обязателен для физической шкалы.")
        return
    try:
        freq, magnitude = filter_magnitude_response(
            int(ch.rate_hz), band_hz=band, notch_hz=notch)
    except (ValueError, TypeError) as exc:
        QtWidgets.QMessageBox.warning(win, "АЧХ фильтра", str(exc))
        return
    dlg = QtWidgets.QDialog(win)
    dlg.setWindowTitle(f"АЧХ локального фильтра · {which} · АЦП {win.adc.currentData()}")
    dlg.resize(690, 410)
    lay = QtWidgets.QVBoxLayout(dlg)
    notice = QtWidgets.QLabel(
        "Расчётная АЧХ двухпроходного локального фильтра (SOS / filtfilt), "
        "без внесения изменений в Native RAW и приборный FRange. "
        "Не является оригинальной АЧХ OEM FIR.")
    notice.setWordWrap(True)
    lay.addWidget(notice)
    plot = pg.PlotWidget()
    plot.setLabel("left", "Ослабление", units="дБ")
    plot.setLabel("bottom", "Частота", units="Гц")
    plot.showGrid(x=True, y=True, alpha=0.15)
    plot.plot(freq, magnitude, pen=pg.mkPen("#4CAFCB", width=1.5))
    plot.setYRange(-160, 5, padding=0)
    lay.addWidget(plot, 1)
    btn = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
    btn.rejected.connect(dlg.reject)
    lay.addWidget(btn)
    dlg.exec()


def _connection_dialog(win):
    dlg = QtWidgets.QDialog(win)
    dlg.setWindowTitle("Профили подключения МВК01")
    dlg.resize(450, 240)
    lay = QtWidgets.QVBoxLayout(dlg)
    form = QtWidgets.QFormLayout()
    name = QtWidgets.QLineEdit()
    name.setText(getattr(win, "_modern_profile_name", "") or "МВК01")
    target = QtWidgets.QLineEdit(win.device_ip.text())
    target.setPlaceholderText("IPv4 прибора")
    local = QtWidgets.QLineEdit(win.local_ip.text())
    local.setPlaceholderText("IPv4 физического Ethernet интерфейса")
    form.addRow("Название профиля", name)
    form.addRow("Прибор (IPv4)", target)
    form.addRow("Компьютер (IPv4)", local)
    lay.addLayout(form)
    detail = QtWidgets.QLabel(
        "Выбор и редактирование профиля не подключают прибор. "
        "TCP/10230 используется только после кнопки «Измерить» "
        "и отдельного подтверждения.")
    detail.setWordWrap(True)
    lay.addWidget(detail)
    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    lay.addWidget(buttons)
    if dlg.exec() != QtWidgets.QDialog.Accepted:
        return
    try:
        ip = win._canonical_ipv4(target.text().strip())
        lip = win._canonical_ipv4(local.text().strip())
        if ip == lip:
            raise ValueError("Адреса прибора и компьютера должны различаться")
    except ValueError as exc:
        QtWidgets.QMessageBox.warning(win, "Профиль не сохранён", str(exc))
        return
    label = name.text().strip() or "МВК01"
    win.device_ip.setText(ip)
    win.local_ip.setText(lip)
    win._modern_profile_name = label
    profiles = getattr(win, "_modern_profiles", {})
    profiles[label] = {"device": ip, "local": lip}
    win._modern_profiles = profiles
    _refresh_profile_selector(win, label)
    if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
        store = QtCore.QSettings("MVK", "MVK Live")
        store.setValue("connections/profiles_v1", json.dumps(profiles, ensure_ascii=False))
        store.setValue("connections/active", label)


def _refresh_profile_selector(win, selected=None):
    combo = win._modern_profile_combo
    with QtCore.QSignalBlocker(combo):
        combo.clear()
        combo.addItem("Выберите профиль", None)
        for name in sorted(win._modern_profiles):
            combo.addItem(name, name)
        if selected is not None:
            idx = combo.findData(selected)
            combo.setCurrentIndex(idx if idx >= 0 else 0)


def _profile_changed(win):
    label = win._modern_profile_combo.currentData()
    if not label:
        return
    if win._native.state() != QtCore.QProcess.ProcessState.NotRunning:
        return
    p = win._modern_profiles.get(label)
    if not p:
        return
    win.device_ip.setText(p["device"])
    win.local_ip.setText(p["local"])
    win._modern_profile_name = label


def _present_window(win, key, title, page, *, remove_from_tabs=None):
    existing = win._modern_windows.get(key)
    if existing is not None:
        existing.show()
        existing.raise_()
        existing.activateWindow()
        return existing
    if remove_from_tabs is not None:
        idx = remove_from_tabs.indexOf(page)
        if idx >= 0:
            remove_from_tabs.removeTab(idx)
    other = QtWidgets.QMainWindow(win, QtCore.Qt.Window)
    other.setObjectName("mvk-window-" + key)
    other.setWindowTitle(title)
    other.resize(990, 670)
    other.setCentralWidget(page)
    other.statusBar().showMessage(
        "APP_DERIVED / источник МВК01 · исходные отсчёты не изменяются")
    win._modern_windows[key] = other
    other.show()
    return other


def _pin_method_source(win, key, child):
    """Operator-approved immutable source for standalone expensive methods.

    Only a verified, already-calibrated local snapshot is copied; reopening
    the window doesn't silently change ADC, Fs, Freeze state or RAW.
    """
    if key not in ("stft", "cwt", "cepstrum", "kurtogram", "bearing"):
        return False
    length = (int(win.kurtogram_window.currentData()) if key == "kurtogram"
              else int(win.bearing_fft.currentData()) if key == "bearing"
              else int(win.extra_method_windows[key].currentData()))
    try:
        samples, fs, stamp = win._current_window(length)
    except (ValueError, TypeError) as exc:
        child.statusBar().showMessage(
            f"Источник не выбран: {exc}. Сначала получите реальные отсчёты.")
        return False
    samples.setflags(write=False)
    win._modern_method_pins[key] = {
        "samples": samples, "fs": int(fs),
        "stamp": stamp, "adc": int(win.adc.currentData()),
        "session": win._gui_ring.session_id,
        "frozen": bool(win.freeze.isChecked()),
    }
    if key == "bearing":
        # A new, explicit capture invalidates only the detached bearing view.
        # Neither Live FFT settings nor the running Native recorder are touched.
        win._bearing_spectrum = None
        win.bearing_curve.setData([], [])
        cursors = getattr(win, "_professional_cursors", None)
        if cursors is not None:
            cursors.refresh_bearing()
        win.bearing_diagnostics.setText(
            f"Закреплён АЦП {win.adc.currentData()} · Fs={fs} Гц · "
            f"N={len(samples)}. Нажмите «Рассчитать огибающую». "
            "Главный спектр не изменяется.")
    label = "Подшипники · огибающая" if key == "bearing" else key.upper()
    child.setWindowTitle(
        f"{label} · АЦП {win.adc.currentData()} · "
        f"Fs {fs} Гц · N {len(samples)} · ЗАФИКСИРОВАНО")
    child.statusBar().showMessage(
        "Подтверждённая копия АЦП; смена АЦП в главном окне "
        "не меняет источник этого расчёта.")
    return True


def open_advanced_window(win, key):
    pages = {
        "waterfall": ("Водопад · LIVE", win.waterfall_page),
        "kurtogram": ("W03 · Fast Kurtogram", win.kurtogram_page),
        "short_trend": ("Оперативный тренд СКЗ · LIVE", win.short_trend_page),
        "stft": ("W05 · STFT", win.extra_method_pages["stft"]),
        "cwt": ("W06 · CWT Morlet", win.extra_method_pages["cwt"]),
        "cepstrum": ("W07 · Кепстр", win.extra_method_pages["cepstrum"]),
        "bearing": ("Подшипники · огибающая", win.diagnostics_page),
        "gears": ("Редукторы · GMF", win.gears_page),
    }
    if key not in pages:
        raise ValueError("Неизвестный метод анализа")
    title, page = pages[key]
    first = key not in win._modern_windows
    w = _present_window(win, key, title, page, remove_from_tabs=win.extra_pages)
    if first and key in ("stft", "cwt", "cepstrum", "kurtogram", "bearing"):
        toolbar = QtWidgets.QToolBar("Источник окна", w)
        toolbar.setMovable(False)
        toolbar.addAction(
            "Взять новое текущее окно АЦП",
            lambda checked=False, mode=key, child=w:
                _pin_method_source(win, mode, child))
        w.addToolBar(toolbar)
        _pin_method_source(win, key, w)
    return w


def open_archive_window(win, key):
    pages = {
        "trends": ("Архив · Тренды", win.history_ui.trend_page),
        "comparison": ("Архив · Сравнение измерений", win.history_ui.compare_page),
    }
    if key not in pages:
        raise ValueError("Неизвестное окно архива")
    title, page = pages[key]
    return _present_window(win, "archive-" + key, title, page,
                           remove_from_tabs=win.views)


def _open_windows_dialog(win):
    dlg = QtWidgets.QDialog(win)
    dlg.setWindowTitle("Открытые окна")
    dlg.resize(500, 350)
    layout = QtWidgets.QVBoxLayout(dlg)
    listing = QtWidgets.QListWidget()
    for key, child in win._modern_windows.items():
        item = QtWidgets.QListWidgetItem(child.windowTitle())
        item.setData(QtCore.Qt.UserRole, key)
        listing.addItem(item)
    layout.addWidget(listing)
    def go():
        item = listing.currentItem()
        if item:
            chosen = win._modern_windows.get(item.data(QtCore.Qt.UserRole))
            if chosen:
                chosen.show()
                chosen.raise_()
                chosen.activateWindow()
    listing.itemDoubleClicked.connect(lambda _: go())
    action = QtWidgets.QPushButton("Перейти к окну")
    action.clicked.connect(go)
    layout.addWidget(action)
    dlg.exec()


def _build_menu(win):
    bar = win.menuBar()
    win._modern_actions = {}
    menus = {}
    for name in ("Файл", "Измерение", "Анализ", "Диагностика",
                 "Архив", "Вид", "Настройки", "Справка"):
        menus[name] = bar.addMenu(name)
    def action(section, label, callback, *, key=None, shortcut=None):
        a = menus[section].addAction(label)
        a.triggered.connect(callback)
        if shortcut:
            a.setShortcut(shortcut)
            a.setShortcutContext(QtCore.Qt.WindowShortcut)
        if key:
            win._modern_actions[key] = a
        return a
    action("Файл", "Открыть измерение NPZ…", win._open_snapshot, shortcut="Ctrl+O")
    action("Файл", "Сохранить текущее окно в архив", win._archive_capture_window,
           key="save_window", shortcut="Ctrl+S")
    action("Файл", "Сохранить NPZ как…", win._save_snapshot)
    action("Файл", "Экспорт спектра CSV…", win._export_csv)
    action("Файл", "Экспорт графика PNG…", win._export_plot_png)
    menus["Файл"].addSeparator()
    action("Файл", "Выход", win.close)
    action("Измерение", "Выбрать / настроить профиль…",
           lambda: _connection_dialog(win))
    action("Измерение", "Обновить Ethernet",
           win._begin_ethernet_discovery)
    menus["Измерение"].addSeparator()
    action("Измерение", "Измерить", win.start_native,
           key="measure", shortcut="F5")
    action("Измерение", "Остановить", win.stop_native,
           key="stop", shortcut="Shift+F5")
    action("Измерение", "Заморозить / продолжить отображение",
           win.freeze.click, shortcut="Space")
    action("Измерение", "Сохранить текущее окно",
           win._archive_capture_window)
    action("Анализ", "Параметры спектра", lambda: _focus_inspector(win, "spectrum"))
    action("Анализ", "Параметры временного сигнала",
           lambda: _focus_inspector(win, "time"))
    action("Анализ", "АЧХ выбранного фильтра FFT…",
           lambda: _filter_response_dialog(win, "spectrum"))
    action("Анализ", "АЧХ фильтра временного сигнала…",
           lambda: _filter_response_dialog(win, "time"))
    menus["Анализ"].addSeparator()
    for name, key in (
        ("Fast Kurtogram", "kurtogram"), ("STFT", "stft"),
        ("CWT Morlet", "cwt"), ("Кепстр", "cepstrum"),
        ("Водопад LIVE", "waterfall"), ("Тренд СКЗ LIVE", "short_trend")
    ):
        action("Анализ", name + " — отдельное окно",
               lambda checked=False, mode=key: open_advanced_window(win, mode))
    action("Диагностика", "Подшипники — окно",
           lambda: open_advanced_window(win, "bearing"))
    action("Диагностика", "Редукторы — окно",
           lambda: open_advanced_window(win, "gears"))
    action("Архив", "Тренды — отдельное окно",
           lambda: open_archive_window(win, "trends"))
    action("Архив", "Сравнение — отдельное окно",
           lambda: open_archive_window(win, "comparison"))
    action("Архив", "Импортировать NPZ…", win._archive_import_npz)
    action("Архив", "Импортировать AUX4700…", win._archive_import_aux)
    for i, name in enumerate(("Обзор", "Спектр", "Временной сигнал",
                              "Расчётные данные")):
        action("Вид", name,
               lambda checked=False, index=i: win.views.setCurrentIndex(index))
    menus["Вид"].addSeparator()
    dock_action = action(
        "Вид", "Показать параметры графика",
        lambda checked=False: _set_inspector_visible(win, checked),
        key="inspector_toggle", shortcut="Ctrl+Alt+P")
    dock_action.setCheckable(True)
    dock_action.setChecked(True)
    popup_action = action(
        "Вид", "Плавающая панель параметров",
        lambda checked=False: _set_inspector_floating(win, checked),
        key="inspector_float")
    popup_action.setCheckable(True)
    menus["Вид"].addSeparator()
    action("Вид", "Автомасштаб спектра", lambda: win._reset_spectrum_axis())
    action("Вид", "Измерительные курсоры спектра",
           lambda: _focus_inspector(win, "spectrum"))
    action("Вид", "Измерительные курсоры временного сигнала",
           lambda: _focus_inspector(win, "time"))
    action("Вид", "Открытые окна анализа…", lambda: _open_windows_dialog(win))
    action("Настройки", "Подключения и IP-профили…",
           lambda: _connection_dialog(win))
    for label, mode in (("Системная тема", "system"), ("Светлая тема", "light"),
                        ("Тёмная тема", "dark")):
        action("Настройки", label, lambda checked=False, m=mode: apply_theme(win, m))
    action("Справка", "О программе", lambda: QtWidgets.QMessageBox.information(
        win, "MVK Live", "MVK Live · собственный анализатор проверенных АЦП МВК01.\n"
        "Приём Native Go, RAW и AUX4700 не изменены.\n"
        "Дополнительные методы APP_DERIVED; это не автоматически поставленный диагноз."))


def _inspector_page_has_settings(win):
    return win.views.currentWidget() in (
        win.overview_page, win.spectrum_page, win.wave_page)


def _update_inspector_buttons(win):
    """Mirror actual visibility; never create duplicate processing state."""
    dock = win._modern_inspector_dock
    showing = _inspector_page_has_settings(win) and not dock.isHidden()
    for widget in (
        win._modern_inspector_button,
        win._modern_actions.get("inspector_toggle"),
    ):
        if widget is not None:
            with QtCore.QSignalBlocker(widget):
                widget.setChecked(showing)
    popup = win._modern_actions.get("inspector_float")
    if popup is not None:
        with QtCore.QSignalBlocker(popup):
            popup.setChecked(dock.isFloating())


def _sync_inspector_for_tab(win):
    """Tab changes do not undo an operator's manual close of the inspector."""
    active = win.views.currentWidget()
    mapping = (
        (win.overview_page, 2, "Обзор · масштабы графиков"),
        (win.spectrum_page, 0, "Спектр · настройки частотного графика"),
        (win.wave_page, 1, "Временной сигнал · настройки осциллограммы"),
    )
    dock = win._modern_inspector_dock
    win._modern_inspector_syncing = True
    try:
        for page, index, title in mapping:
            if active is page:
                win._modern_inspector.setCurrentIndex(index)
                dock.setWindowTitle(title)
                with QtCore.QSignalBlocker(dock):
                    dock.setVisible(bool(win._modern_inspector_wanted))
                break
        else:
            # Calculation tables have no active plot options, but returning
            # to Overview restores only what the operator wanted visible.
            with QtCore.QSignalBlocker(dock):
                dock.hide()
    finally:
        win._modern_inspector_syncing = False
    _update_inspector_buttons(win)


def _inspector_visibility_changed(win, visible):
    # QDockWidget's titlebar X is a real user close. Hiding it via another
    # main tab is programmatic and must not overwrite that preference.
    if getattr(win, "_modern_inspector_syncing", False):
        return
    if _inspector_page_has_settings(win) and win.isVisible():
        win._modern_inspector_wanted = bool(visible)
    _update_inspector_buttons(win)


def _set_inspector_visible(win, visible):
    win._modern_inspector_wanted = bool(visible)
    if visible and not _inspector_page_has_settings(win):
        win.views.setCurrentWidget(win.overview_page)
    _sync_inspector_for_tab(win)
    if visible:
        win._modern_inspector_dock.raise_()
        if win._modern_inspector_dock.isFloating():
            win._modern_inspector_dock.activateWindow()


def _set_inspector_floating(win, floating):
    if not _inspector_page_has_settings(win):
        win.views.setCurrentWidget(win.overview_page)
    dock = win._modern_inspector_dock
    win._modern_inspector_syncing = True
    try:
        dock.setFloating(bool(floating))
        if floating:
            dock.resize(380, 650)
    finally:
        win._modern_inspector_syncing = False
    # Both menu and toolbar selection are explicit OPEN requests.
    _set_inspector_visible(win, True)


def _focus_inspector(win, kind):
    target = win.spectrum_page if kind == "spectrum" else win.wave_page
    if win.views.currentWidget() is not target:
        win.views.setCurrentWidget(target)
    _set_inspector_visible(win, True)


def _refresh_status(win):
    phase = "ЗАПИСЬ" if win._native.state() != QtCore.QProcess.ProcessState.NotRunning else "НЕТ ПРИЁМА"
    ch = win._gui_ring.channel(win.adc.currentData())
    fs = f"Fs {ch.rate_hz} Гц" if ch is not None else "Fs —"
    state = win.status.text().replace("\n", " ")
    if len(state) > 150:
        state = state[:147] + "…"
    win.statusBar().showMessage(
        f"{phase} · АЦП {win.adc.currentData()} · {fs} · {state}")
    win._modern_actions["measure"].setEnabled(
        win._native.state() == QtCore.QProcess.ProcessState.NotRunning)
    win._modern_actions["stop"].setEnabled(
        win._native.state() != QtCore.QProcess.ProcessState.NotRunning)
    if hasattr(win, "_modern_metric_values"):
        res = getattr(win, "_last_result", None)
        if res is not None and getattr(win, "_spectrum", None) is not None:
            try:
                f = res.features
                velocity = getattr(res, "broadband_velocity", None)
                v = (f"{velocity.rms:.3g} мм/с"
                     if velocity is not None and velocity.valid else "—")
                values = {
                    "rms": f"{f.rms_m_s2:.4g} м/с²",
                    "velocity": v,
                    "peak": f"{f.peak_m_s2:.4g} м/с²",
                    "crest": f"{f.crest_factor:.3g}",
                }
                for key, text in values.items():
                    win._modern_metric_values[key].setText(text)
            except (AttributeError, TypeError, ValueError):
                pass
        else:
            for label in win._modern_metric_values.values():
                label.setText("—")


def _chart_focus(win, kind, event=None):
    # A single click in the overview belongs to cursors/graph interaction.
    # A double click, or its explicit details button, opens the owning tab.
    if win.views.currentWidget() is win.overview_page:
        if event is not None and event.double():
            _focus_inspector(win, kind)
        return
    _focus_inspector(win, kind)


def install_modern_shell(win, main, panel, review, storage):
    """Recompose existing verified UI in one pass without changing its DSP."""
    win._modern_windows = {}
    win._modern_method_pins = {}
    win._modern_profile_name = None
    win._modern_profiles = {}
    if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
        settings = QtCore.QSettings("MVK", "MVK Live")
        try:
            raw = json.loads(settings.value("connections/profiles_v1", "{}"))
            if isinstance(raw, dict):
                win._modern_profiles = {k: v for k, v in raw.items()
                                        if isinstance(k, str) and isinstance(v, dict)
                                        and isinstance(v.get("device"), str)
                                        and isinstance(v.get("local"), str)}
        except (TypeError, ValueError):
            pass
        win._modern_profile_name = settings.value("connections/active", None)
    # Unmount three large old operator form rows; retained widgets and
    # callbacks are reparented into the toolbar and contextual inspector.
    for legacy in (panel, review, storage):
        _detach_layout(legacy, main)
    for control in (win.status, win.quality):
        main.removeWidget(control)
        control.hide()
    main.removeWidget(win.views)

    win._modern_profile_combo = QtWidgets.QComboBox()
    _refresh_profile_selector(win, win._modern_profile_name)
    win._modern_profile_combo.currentIndexChanged.connect(
        lambda _: _profile_changed(win))
    win.connect_button.setText("Измерить")
    win.connect_button.setProperty("primary", True)
    win.stop_button.setText("Стоп")
    win.freeze.setText("Freeze")
    win.freeze.setToolTip("Заморозить только отображение; Native RAW продолжает запись")
    win._modern_capture = QtWidgets.QPushButton("Сохранить окно")
    win._modern_capture.clicked.connect(win._archive_capture_window)
    tools = QtWidgets.QWidget(win)
    line = QtWidgets.QHBoxLayout(tools)
    line.setContentsMargins(4, 3, 4, 3)
    line.setSpacing(8)
    line.addWidget(win._modern_profile_combo)
    for widget in (win.connect_button, win.stop_button, win.freeze,
                   win._modern_capture):
        line.addWidget(widget)
        widget.show()
    line.addStretch(1)
    line.addWidget(QtWidgets.QLabel("АЦП"))
    line.addWidget(win.adc)
    win.adc.show()

    # Always-visible recovery for an intentionally closed inspector.
    # Its arrow opens a mode menu: docked right or floating non-modal panel.
    win._modern_inspector_button = QtWidgets.QToolButton(tools)
    win._modern_inspector_button.setText("Параметры")
    win._modern_inspector_button.setToolTip(
        "Показать/скрыть свойства текущего графика · Ctrl+Alt+P. "
        "Стрелка справа открывает выбор плавающего окна.")
    win._modern_inspector_button.setCheckable(True)
    win._modern_inspector_button.setChecked(True)
    win._modern_inspector_button.setPopupMode(
        QtWidgets.QToolButton.ToolButtonPopupMode.MenuButtonPopup)
    inspector_modes = QtWidgets.QMenu(win._modern_inspector_button)
    win._modern_inspector_popup_action = inspector_modes.addAction(
        "Открыть параметры отдельным окном")
    win._modern_inspector_popup_action.triggered.connect(
        lambda checked=False: _set_inspector_floating(win, True))
    win._modern_inspector_dock_action = inspector_modes.addAction(
        "Закрепить параметры справа")
    win._modern_inspector_dock_action.triggered.connect(
        lambda checked=False: _set_inspector_floating(win, False))
    win._modern_inspector_button.setMenu(inspector_modes)
    line.addWidget(win._modern_inspector_button)
    win._modern_windows_button = QtWidgets.QPushButton("Открытые окна…")
    win._modern_windows_button.setMinimumWidth(110)
    win._modern_windows_button.clicked.connect(lambda: _open_windows_dialog(win))
    line.addWidget(win._modern_windows_button)
    main.addWidget(tools)

    # Existing detailed plots retain their own QWidget; the overview has
    # independent renderers receiving the SAME full-resolution analysis.
    overview = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(overview)
    layout.setContentsMargins(6, 4, 6, 4)
    layout.setSpacing(6)
    # Four compact metric cards, instead of one tiny run-on text label.
    win.overview_metrics = QtWidgets.QLabel("—", overview)
    win.overview_metrics.hide()  # compatibility alias only
    win._modern_metric_values = {}
    metric_strip = QtWidgets.QHBoxLayout()
    metric_strip.setSpacing(8)
    for key, title in (
        ("rms", "ВУ · СКЗ"), ("velocity", "ВС · СКЗ"),
        ("peak", "Пиковая ВУ"), ("crest", "Крест-фактор")):
        card = QtWidgets.QFrame()
        card.setObjectName("kpiCard")
        column = QtWidgets.QVBoxLayout(card)
        column.setContentsMargins(10, 6, 10, 6)
        column.setSpacing(2)
        heading = QtWidgets.QLabel(title)
        heading.setProperty("metricLabel", True)
        value = QtWidgets.QLabel("—")
        value.setProperty("metricValue", True)
        column.addWidget(heading)
        column.addWidget(value)
        metric_strip.addWidget(card, stretch=1)
        win._modern_metric_values[key] = value
    layout.addLayout(metric_strip)
    splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
    win.overview_spec = pg.PlotWidget(title="Спектр · ожидание реального АЦП")
    win.overview_spec.setLabel("bottom", "Частота", units="Гц")
    win.overview_spec.setLabel("left", "FFT", units="м/с²")
    win.overview_spec.showGrid(x=True, y=True, alpha=0.14)
    win.overview_spec_curve = win.overview_spec.plot(pen=pg.mkPen("#F3B85C"))
    win.overview_wave = pg.PlotWidget(title="Временной сигнал · нет отсчётов")
    win.overview_wave.setLabel("bottom", "Время", units="с")
    win.overview_wave.setLabel("left", "ВУ", units="м/с²")
    win.overview_wave.showGrid(x=True, y=True, alpha=0.14)
    win.overview_wave_curve = win.overview_wave.plot(pen=pg.mkPen("#5CCFC5"))
    splitter.addWidget(win.overview_spec)
    splitter.addWidget(win.overview_wave)
    splitter.setStretchFactor(0, 55)
    splitter.setStretchFactor(1, 45)
    layout.addWidget(splitter, 1)
    win.overview_page = overview
    win._modern_splitter = splitter

    # Remove non-LIVE tabs but leave the original page objects intact.
    for page in (win.extra_panel, win.history_ui.trend_page,
                 win.history_ui.compare_page):
        idx = win.views.indexOf(page)
        if idx >= 0:
            win.views.removeTab(idx)
    win.views.insertTab(0, overview, "Обзор")
    win.views.setCurrentWidget(overview)
    win.history_ui.on_open_comparison = lambda: open_archive_window(win, "comparison")
    main.addWidget(win.views, stretch=1)

    # Move the original individual controls into ONE contextual inspector.
    # The old spectrum form is hidden, not recreated with different DSP.
    win.spectrum_layout.removeWidget(win.spectrum_controls_widget)
    win.spectrum_controls_widget.hide()
    win.advanced_toggle.hide()
    win.advanced_panel.hide()
    # Hidden legacy combo boxes must not appear as a second channel selector.
    # Their signals still maintain compatibility with existing calculations.
    win.extra_adc.hide()
    win.dsp_adc.hide()
    # Original time toolbar labels would otherwise remain with empty fields.
    _hide_layout(win.wave_toolbar)
    inspector = QtWidgets.QStackedWidget()
    # QtStackedWidget normally propagates the widest page's sizeHint to
    # QScrollArea. Ignore those hints: the dock is deliberately responsive.
    inspector.setMinimumWidth(0)
    inspector.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored,
                            QtWidgets.QSizePolicy.Policy.Preferred)
    # Filters are grouped by their physical purpose instead of a flat list.
    # This changes only labels and choice order, never the existing values.
    _filter_selector_for_operators(win.filter_choice)
    _filter_selector_for_operators(win.time_filter_choice)

    spectrum_panel = QtWidgets.QWidget()
    spectrum_panel.setMinimumWidth(0)
    spectrum_panel.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored,
                                 QtWidgets.QSizePolicy.Policy.Preferred)
    ss = QtWidgets.QVBoxLayout(spectrum_panel)
    ss.setContentsMargins(12, 12, 12, 12)
    ss.setSpacing(8)
    ss.addWidget(_title("СПЕКТР · параметры анализа"))
    ss.addWidget(_hint(
        "Действует на спектр выбранного АЦП и верхний график «Обзора». "
        "Исходный Native RAW и временная осциллограмма не изменяются."))

    # As in DewesoftX, OROS and Adash, distinguish RESULT from processing
    # parameters and from axes. Reuse real original widgets; no fake controls.
    ss.addWidget(_title("1. Результат и разрешение"))
    result_fields = QtWidgets.QVBoxLayout()
    result_fields.setSpacing(8)
    _field(result_fields, "Физическая величина", win.kind)
    _field(result_fields, "Метод расчёта", win.analysis)
    _field(result_fields, "Отсчётов в FFT · N", win.nfft)
    ss.addLayout(result_fields)
    envelope_row = _field(
        result_fields, "Полоса резонанса огибающей, Гц",
        win.envelope_band)
    win._modern_spectrum_envelope_row = envelope_row
    calc_info = _hint("")
    win._modern_spectrum_setup_info = calc_info
    ss.addWidget(calc_info)

    ss.addWidget(_title("2. Отображение и шкалы"))
    axes_fields = QtWidgets.QVBoxLayout()
    axes_fields.setSpacing(8)
    _field(axes_fields, "Амплитуда · линейно / дБ", win.yscale)
    db_row = _field(
        axes_fields, "Опорный уровень в дБ", win.db_ref)
    _field(axes_fields, "Частота · линейно / логарифмически",
           win.xscale)
    _field(axes_fields, "Частотный диапазон до, Гц",
           win.x_limit_choice)
    amplitude_row = _field(
        axes_fields, "Вертикальный масштаб в единицах результата",
        win.y_height_choice)
    ss.addLayout(axes_fields)
    scale_note = _hint("")
    ss.addWidget(scale_note)
    win.xscale.setToolTip(
        "Линейная либо логарифмическая ОСЬ ЧАСТОТЫ в Гц. "
        "Не меняет амплитуду в децибелах.")
    win.yscale.setToolTip(
        "Линейные физические значения либо дБ относительно заданного "
        "опорного уровня. Это НЕ второе логарифмирование оси Y.")

    ss.addWidget(_title("3. Фильтрация до расчёта"))
    ss.addWidget(_hint(
        "Отдельный локальный фильтр спектра: обработка настоящего "
        "калиброванного АЦП, не аппаратный FIR и не фильтр осциллограммы."))
    filter_fields = QtWidgets.QVBoxLayout()
    filter_fields.setSpacing(8)
    _field(filter_fields, "Фильтр", win.filter_choice)
    centre = _field(filter_fields, "Частота фильтра, Гц",
                    win.filter_center)
    centre_label = centre.findChild(QtWidgets.QLabel)
    ss.addLayout(filter_fields)
    ss.addWidget(win.filter_button)
    win.filter_button.setText("Установить границы фильтра…")
    filter_note = _hint("")
    win._modern_spectrum_filter_note = filter_note
    ss.addWidget(filter_note)

    details = QtWidgets.QToolButton()
    details.setText("Дополнительно · АЧХ, сглаживание и масштаб")
    details.setCheckable(True)
    details.setArrowType(QtCore.Qt.ArrowType.RightArrow)
    details.setToolButtonStyle(
        QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    ss.addWidget(details)
    advanced_frame = QtWidgets.QWidget()
    advanced = QtWidgets.QVBoxLayout(advanced_frame)
    advanced.setContentsMargins(0, 0, 0, 0)
    advanced.setSpacing(8)
    smoothing_row = _field(
        advanced, "Сглаживание мощности FFT, число линий", win.smooth)
    win._modern_spectrum_smoothing_row = smoothing_row
    advanced.addWidget(win.axis_button)
    auto = QtWidgets.QPushButton("Сбросить масштаб и увеличить автоматически")
    auto.clicked.connect(win._reset_spectrum_axis)
    advanced.addWidget(auto)
    response = QtWidgets.QPushButton("АЧХ выбранного локального фильтра…")
    response.clicked.connect(lambda: _filter_response_dialog(win, "spectrum"))
    advanced.addWidget(response)
    win.operator_info.setWordWrap(True)
    win.operator_info.setProperty("helpText", True)
    advanced.addWidget(win.operator_info)
    ss.addWidget(advanced_frame)
    advanced_frame.hide()
    def toggle_details(checked):
        advanced_frame.setVisible(checked)
        details.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if checked
            else QtCore.Qt.ArrowType.RightArrow)
    details.toggled.connect(toggle_details)
    win._modern_spectrum_detail = details

    filter_notes = {
        "none": "Без дополнительного локального фильтра.",
        "highpass": "ФВЧ: оставляет частоты выше нижней границы.",
        "lowpass": "ФНЧ: оставляет частоты ниже верхней границы.",
        "bandpass": "Полосовой: нижняя и верхняя границы.",
        "notch50": "Режектор 50 Гц · Q=35. Не включается автоматически.",
        "notch60": "Режектор 60 Гц · Q=35. Не включается автоматически.",
        "octave": "1/1 октавы — входной фильтр, не расчёт октавного спектра.",
        "third_octave": "1/3 октавы — входной фильтр, не AUX4700.",
        "double_octave": "2 октавы — входной полосовой фильтр.",
        "original_preset": "Названия 32 полос MVKView, локальная реализация, не OEM FIR.",
    }
    def refresh_setup(*_):
        mode = win.analysis.currentData()
        kind = win.kind.currentData()
        ymode = win.yscale.currentData()
        envelope_row.setVisible(mode == "envelope")
        db_row.setVisible(ymode == "db")
        amplitude_row.setVisible(mode == "fft")
        win.y_height_choice.setEnabled(mode == "fft")
        smoothing_row.setVisible(mode == "fft")
        win.smooth.setEnabled(mode == "fft")
        scale_note.setText(
            "Плотность мощности PSD, амплитудная плотность ASD и "
            "СКЗ третьоктавных полос имеют собственные единицы; "
            "используется автомасштаб."
            if mode != "fft" else
            "Амплитуда спектральных линий — СКЗ; масштаб задаётся "
            "в выбранной физической единице или дБ.")
        ch = win._gui_ring.channel(win.adc.currentData())
        current = getattr(win, "_spectrum", None)
        fs = (
            int(current.rate_hz)
            if current is not None and
            current.kind == kind and current.mode == mode
            else int(ch.rate_hz) if ch is not None else None
        )
        nfft = int(win.nfft.currentData())
        if fs is not None and fs > 0:
            timing = (
                f"Fs {fs:g} Гц · Δf {fs/nfft:.5g} Гц · "
                f"длительность окна {nfft/fs:.5g} с · "
                f"Nyquist {fs/2:g} Гц")
        else:
            timing = "Fs неизвестна: Δf и длительность пока не подтверждены"
        processing = {
            "fft": "FFT: окно Хэнна (фиксировано), амплитуда линий СКЗ.",
            "welch": "PSD Welch: окно Хэнна, перекрытие 50%, мощность/Гц.",
            "asd": "ASD Welch: окно Хэнна, перекрытие 50%, √PSD.",
            "third_octave": "1/3 октавы: интеграл PSD Welch по реальным полосам.",
            "envelope": "Огибающая: полосовой фильтр + Hilbert, только ВУ.",
        }.get(mode, "")
        if mode in ("welch", "asd", "third_octave") and kind != "acceleration":
            processing += (
                " ВС/ВП: локальный ФВЧ ≥2 Гц для подавления дрейфа.")
        if current is not None and current.kind == kind and current.mode == mode:
            if mode in ("welch", "asd", "third_octave"):
                processing += f" Принято {current.segments} сегм. Welch."
        calc_info.setText(f"{timing}. {processing}")
        filter_mode = win.filter_choice.currentData()
        centre.setVisible(filter_mode in (
            "original_preset", "octave", "third_octave", "double_octave"))
        centre_label.setText(
            "Полоса меню MVKView" if filter_mode == "original_preset"
            else "Центральная частота, Гц")
        win.filter_button.setVisible(filter_mode in (
            "highpass", "lowpass", "bandpass"))
        filter_text = filter_notes.get(filter_mode, "Неизвестный фильтр.")
        if fs is not None and fs > 0:
            try:
                settings = win._read_settings()
                low, high = settings[3]
                if low >= fs/2 or (high is not None and high >= fs/2):
                    filter_text += (
                        f" НЕДОПУСТИМО для Fs={fs} Гц: "
                        f"граница должна быть ниже {fs/2:g} Гц (Nyquist).")
                if settings[7] is not None and settings[7] >= fs/2:
                    filter_text += (
                        f" Режектор {settings[7]:g} Гц недопустим "
                        f"для Nyquist {fs/2:g} Гц.")
            except (ValueError, TypeError) as exc:
                filter_text += f" Проверьте полосу: {exc}."
        filter_note.setText(filter_text)

    win._modern_refresh_spectrum_setup = refresh_setup
    for control in (
        win.nfft, win.analysis, win.kind, win.yscale, win.db_ref,
        win.adc, win.filter_choice, win.filter_center):
        control.currentIndexChanged.connect(refresh_setup)
    refresh_setup()
    ss.addStretch(1)
    inspector.addWidget(spectrum_panel)

    time_panel = QtWidgets.QWidget()
    time_panel.setMinimumWidth(0)
    time_panel.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored,
                             QtWidgets.QSizePolicy.Policy.Preferred)
    ts = QtWidgets.QVBoxLayout(time_panel)
    ts.setContentsMargins(12, 12, 12, 12)
    ts.setSpacing(9)
    ts.addWidget(_title("ВРЕМЕННОЙ СИГНАЛ · осциллограмма"))
    ts.addWidget(_hint(
        "Здесь настраивается нижний график обзора и вкладка "
        "«Временной сигнал». Значения — мгновенное ускорение "
        "в м/с² со знаком, не спектральный СКЗ."))
    ts.addWidget(_title("Отображение во времени"))
    tform = QtWidgets.QVBoxLayout()
    tform.setSpacing(9)
    for label, widget in (
        ("Развёртка времени", win.timebase),
        ("Масштаб виброускорения", win.time_y_width),
    ):
        _field(tform, label, widget)
    ts.addLayout(tform)
    ts.addWidget(_title("Обработка · только временной сигнал"))
    ts.addWidget(_hint(
        "Свой локальный фильтр. Его изменение не влияет на FFT и "
        "не переписывает калиброванные отсчёты."))
    tf = QtWidgets.QVBoxLayout()
    tf.setSpacing(9)
    _field(tf, "Тип фильтра", win.time_filter_choice)
    time_centre = _field(tf, "Центральная частота полосы",
                         win.time_filter_center)
    time_centre_label = time_centre.findChild(QtWidgets.QLabel)
    ts.addLayout(tf)
    ts.addWidget(win.time_filter_button)
    win.time_filter_button.setText("Задать границы фильтра…")
    time_note = _hint("")
    ts.addWidget(time_note)
    def time_filter_visibility(*_):
        mode = win.time_filter_choice.currentData()
        time_centre.setVisible(mode in (
            "original_preset", "octave", "third_octave", "double_octave"))
        time_centre_label.setText(
            "Полоса из меню MVKView" if mode == "original_preset"
            else "Центральная частота полосы")
        win.time_filter_button.setVisible(mode in (
            "highpass", "lowpass", "bandpass"))
        time_note.setText(filter_notes.get(mode, "").replace(
            "спектр", "временной сигнал"))
    win.time_filter_choice.currentIndexChanged.connect(time_filter_visibility)
    time_filter_visibility()
    time_detail = QtWidgets.QToolButton()
    time_detail.setText("Просмотр участка и АЧХ")
    time_detail.setCheckable(True)
    time_detail.setArrowType(QtCore.Qt.ArrowType.RightArrow)
    time_detail.setToolButtonStyle(
        QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    ts.addWidget(time_detail)
    time_advanced = QtWidgets.QWidget()
    time_advanced_layout = QtWidgets.QVBoxLayout(time_advanced)
    time_advanced_layout.setContentsMargins(0, 0, 0, 0)
    _field(time_advanced_layout, "Смещение в режиме Freeze", win.history)
    response_time = QtWidgets.QPushButton("Посмотреть АЧХ временного фильтра…")
    response_time.clicked.connect(lambda: _filter_response_dialog(win, "time"))
    time_advanced_layout.addWidget(response_time)
    ts.addWidget(time_advanced)
    time_advanced.hide()
    def toggle_time_detail(checked):
        time_advanced.setVisible(checked)
        time_detail.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if checked
            else QtCore.Qt.ArrowType.RightArrow)
    time_detail.toggled.connect(toggle_time_detail)
    ts.addStretch(1)
    inspector.addWidget(time_panel)

    # Overview keeps only four quick controls for two different graphs.
    # Proxies reuse the same core setting; the ADC selector stays in the
    # measurement toolbar and is never duplicated here.
    # Overview intentionally exposes only FIVE sizing/view controls.
    # Each is a proxy of its real, single-purpose detailed-page setting.
    overview_panel = QtWidgets.QWidget()
    overview_panel.setMinimumWidth(0)
    overview_panel.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored,
                                 QtWidgets.QSizePolicy.Policy.Preferred)
    ov = QtWidgets.QVBoxLayout(overview_panel)
    ov.setContentsMargins(12, 12, 12, 12)
    ov.setSpacing(11)
    ov.addWidget(_title("ОБЗОР · масштабы графиков"))

    spec_card, spec_column = _quick_card(
        "СПЕКТР", "Верхний график · четыре привычных вида")
    win._overview_spectrum_view = _mirror_control(
        win.spectrum_view, spec_column, "Вид спектра",
        force_select=win._select_primary_spectrum)
    win._overview_spectrum_view.setToolTip(
        "Логарифмический вид = виброускорение в дБ; частотная ось "
        "остаётся отдельной настройкой на вкладке «Спектр».")
    win._overview_frequency_limit = _mirror_control(
        win.x_limit_choice, spec_column, "Показывать частоты до")
    win._overview_y_height = _mirror_control(
        win.y_height_choice, spec_column, "Вертикальный масштаб",
        rebuild_on=(win.kind.currentIndexChanged,
                    win.yscale.currentIndexChanged,
                    win.spectrum_view.currentIndexChanged,
                    win.analysis.currentIndexChanged))
    win._overview_y_height.setToolTip(
        "Доступный масштаб зависит от выбранного вида спектра: "
        "дБ, м/с², мм/с или мкм.")

    # Detailed Spectrum controls may select a combination outside the four
    # overview presets (e.g. velocity measured in dB). Never pretend that
    # such a combination is one of the four quick modes.
    def sync_overview_mode(*_):
        kind = win.kind.currentData()
        scale = win.yscale.currentData()
        chosen = {
            ("acceleration", "db"): "log_vu",
            ("acceleration", "linear"): "linear_vu",
            ("velocity", "linear"): "linear_vs",
            ("displacement", "linear"): "linear_vp",
        }.get((kind, scale))
        quick = win._overview_spectrum_view
        with QtCore.QSignalBlocker(quick):
            if chosen is None:
                quick.setPlaceholderText("Особый вид · вкладка «Спектр»")
                quick.setCurrentIndex(-1)
            else:
                quick.setCurrentIndex(quick.findData(chosen))
    win.kind.currentIndexChanged.connect(sync_overview_mode)
    win.yscale.currentIndexChanged.connect(sync_overview_mode)
    win.spectrum_view.currentIndexChanged.connect(sync_overview_mode)
    sync_overview_mode()
    ov.addWidget(spec_card)

    time_card, time_column = _quick_card(
        "ВРЕМЕННОЙ СИГНАЛ", "Нижний график · размер осциллограммы")
    win._overview_timebase = _mirror_control(
        win.timebase, time_column, "Развёртка по времени")
    win._overview_time_y_width = _mirror_control(
        win.time_y_width, time_column, "Вертикальный масштаб · м/с²")
    ov.addWidget(time_card)
    ov.addStretch(1)
    inspector.addWidget(overview_panel)

    win._modern_inspector = inspector
    dock = QtWidgets.QDockWidget("Параметры активного графика", win)
    dock.setObjectName("mainGraphInspector")
    dock.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
    scroll = QtWidgets.QScrollArea()
    scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    scroll.setSizeAdjustPolicy(
        QtWidgets.QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
    scroll.setWidget(inspector)
    # Avoid recursive widening when combo-box popup contents are wider than
    # the viewport. The field widgets are Ignores and resize to dock width.
    scroll.viewport().setMinimumWidth(0)
    dock.setWidget(scroll)
    dock.setMinimumWidth(246)
    win.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
    win._modern_inspector_dock = dock
    win._modern_inspector_wanted = True
    win._modern_inspector_syncing = False
    dock.setFeatures(
        QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable
        | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
        | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable)
    dock.visibilityChanged.connect(
        lambda visible: _inspector_visibility_changed(win, visible))
    dock.topLevelChanged.connect(lambda _: _update_inspector_buttons(win))
    win._modern_inspector_button.toggled.connect(
        lambda checked: _set_inspector_visible(win, checked))
    win.resizeDocks([dock], [318], QtCore.Qt.Horizontal)

    # Clicking a plot switches the inspector. The main tab navigation
    # is deliberately separate from the 43 standalone method windows.
    for plot, kind in (
        (win.overview_spec, "spectrum"), (win.overview_wave, "time"),
        (win.spec, "spectrum"), (win.wave, "time")):
        plot.scene().sigMouseClicked.connect(
            lambda event, k=kind: _chart_focus(win, k, event))
    win.views.currentChanged.connect(lambda _: _sync_inspector_for_tab(win))
    # pyqtgraph's manually changed signal is distinct from programmatic
    # LIVE repaints; remember zoom coordinates after a user drag/wheel.
    def remember_zoom(plot):
        def save(*_):
            def commit():
                r = plot.viewRange()
                if len(r) == 2 and all(len(ax) == 2 for ax in r):
                    win._manual_spec_axes = (
                        float(r[0][0]), float(r[0][1]),
                        float(r[1][0]), float(r[1][1]))
            QtCore.QTimer.singleShot(0, commit)
        plot.getViewBox().sigRangeChangedManually.connect(save)
    remember_zoom(win.spec)
    remember_zoom(win.overview_spec)
    win.setWindowTitle("MVK Live · Анализатор вибрации")
    _build_menu(win)
    _sync_inspector_for_tab(win)
    _refresh_status(win)
    win._modern_status_timer = QtCore.QTimer(win)
    win._modern_status_timer.setInterval(700)
    win._modern_status_timer.timeout.connect(lambda: _refresh_status(win))
    win._modern_status_timer.start()

    theme = "system"
    if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
        theme = QtCore.QSettings("MVK", "MVK Live").value("ui/theme_v1", "system")
    apply_theme(win, theme)
    # The overview is attached after the original app's first _apply_axes.
    # Initialize actual FFT/dB/PSD axis units and configured X limits now;
    # an empty source still must never render synthetic samples.
    win._apply_axes()
    win._apply_operator_ranges()
    # There is no ADC at startup; even the EMPTY oscilloscope uses a
    # signed acceleration axis, never a misleading 0..positive scale.
    # No samples are fabricated or inferred by this blank redraw.
    win._render_wave()
    from .cursor_overlay import install_measurement_cursors
    install_measurement_cursors(win)
    win._modern_installed = True
