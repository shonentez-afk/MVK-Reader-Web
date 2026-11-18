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


def _field(form, text, widget):
    form.addRow(text, widget)
    widget.show()
    return widget


def _title(text):
    lab = QtWidgets.QLabel(text)
    lab.setProperty("sectionTitle", True)
    return lab


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
    w = _present_window(win, key, title, page, remove_from_tabs=win.extra_pages)
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
    action("Вид", "Автомасштаб спектра", lambda: win._reset_spectrum_axis())
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


def _focus_inspector(win, kind):
    win._modern_inspector.setCurrentIndex(0 if kind == "spectrum" else 1)
    win._modern_inspector_dock.show()
    win._modern_inspector_dock.raise_()


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
    if hasattr(win, "overview_metrics"):
        res = getattr(win, "_last_result", None)
        if res is not None and getattr(win, "_spectrum", None) is not None:
            try:
                f = res.features
                velocity = getattr(res, "broadband_velocity", None)
                v = (f"{velocity.rms:.3g} мм/с"
                     if velocity is not None and velocity.valid else "—")
                win.overview_metrics.setText(
                    f"ВУ RMS  {f.rms_m_s2:.4g} м/с²    ·    "
                    f"ВС RMS  {v}    ·    "
                    f"Пик  {f.peak_m_s2:.4g} м/с²    ·    "
                    f"Crest  {f.crest_factor:.3g}")
            except (AttributeError, TypeError, ValueError):
                pass


def _chart_focus(win, kind):
    _focus_inspector(win, kind)


def install_modern_shell(win, main, panel, review, storage):
    """Recompose existing verified UI in one pass without changing its DSP."""
    win._modern_windows = {}
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
    win._modern_windows_button = QtWidgets.QPushButton("Окна…")
    win._modern_windows_button.clicked.connect(lambda: _open_windows_dialog(win))
    line.addWidget(win._modern_windows_button)
    main.addWidget(tools)

    # Existing detailed plots retain their own QWidget; the overview has
    # independent renderers receiving the SAME full-resolution analysis.
    overview = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(overview)
    layout.setContentsMargins(6, 4, 6, 4)
    layout.setSpacing(6)
    win.overview_metrics = QtWidgets.QLabel(
        "ВУ RMS  —    ·    ВС RMS  —    ·    Пик  —    ·    Crest  —")
    win.overview_metrics.setObjectName("overviewMetrics")
    layout.addWidget(win.overview_metrics)
    splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
    win.overview_spec = pg.PlotWidget()
    win.overview_spec.setLabel("bottom", "Частота", units="Гц")
    win.overview_spec.setLabel("left", "FFT", units="м/с²")
    win.overview_spec.showGrid(x=True, y=True, alpha=0.14)
    win.overview_spec_curve = win.overview_spec.plot(pen=pg.mkPen("#F3B85C"))
    win.overview_wave = pg.PlotWidget()
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
    spectrum_panel = QtWidgets.QWidget()
    ss = QtWidgets.QVBoxLayout(spectrum_panel)
    ss.addWidget(_title("Спектр"))
    basic = QtWidgets.QFormLayout()
    for label, widget in (
        ("Быстрый вид MVKView", win.spectrum_view),
        ("Величина ВУ / ВС / ВП", win.kind),
        ("Метод FFT / PSD / ASD", win.analysis),
        ("Шкала Y", win.yscale),
        ("Шкала частоты X", win.xscale),
        ("Предел X", win.x_limit_choice),
        ("Масштаб Y", win.y_height_choice),
        ("Локальный фильтр", win.filter_choice),
        ("Полоса / центр", win.filter_center),
    ):
        _field(basic, label, widget)
    ss.addLayout(basic)
    ss.addWidget(win.filter_button)
    _field(basic, "FFT, N отсчётов", win.nfft)
    _field(basic, "Опора дБ", win.db_ref)
    _field(basic, "Сглаживание", win.smooth)
    ss.addWidget(win.axis_button)
    auto = QtWidgets.QPushButton("Вернуть автомасштаб")
    auto.clicked.connect(win._reset_spectrum_axis)
    ss.addWidget(auto)
    response = QtWidgets.QPushButton("Показать АЧХ локального фильтра…")
    response.clicked.connect(lambda: _filter_response_dialog(win, "spectrum"))
    ss.addWidget(response)
    ss.addWidget(win.operator_info)
    ss.addStretch(1)
    inspector.addWidget(spectrum_panel)

    time_panel = QtWidgets.QWidget()
    ts = QtWidgets.QVBoxLayout(time_panel)
    ts.addWidget(_title("Временной сигнал"))
    tform = QtWidgets.QFormLayout()
    for label, widget in (
        ("Развёртка", win.timebase),
        ("Масштаб ±Y", win.time_y_width),
        ("Фильтр времени", win.time_filter_choice),
        ("Октавная полоса", win.time_filter_center),
        ("Смещение Freeze", win.history),
    ):
        _field(tform, label, widget)
    ts.addLayout(tform)
    ts.addWidget(win.time_filter_button)
    response_time = QtWidgets.QPushButton("Показать АЧХ фильтра времени…")
    response_time.clicked.connect(lambda: _filter_response_dialog(win, "time"))
    ts.addWidget(response_time)
    ts.addWidget(QtWidgets.QLabel(
        "Мгновенная знаковая амплитуда ±м/с²; фильтр времени "
        "не меняет спектральный фильтр."))
    ts.addStretch(1)
    inspector.addWidget(time_panel)
    win._modern_inspector = inspector
    dock = QtWidgets.QDockWidget("Параметры активного графика", win)
    dock.setObjectName("mainGraphInspector")
    dock.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(inspector)
    dock.setWidget(scroll)
    win.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
    win._modern_inspector_dock = dock
    win.resizeDocks([dock], [310], QtCore.Qt.Horizontal)

    # Clicking a plot switches the inspector. The main tab navigation
    # is deliberately separate from the 43 standalone method windows.
    for plot, kind in (
        (win.overview_spec, "spectrum"), (win.overview_wave, "time"),
        (win.spec, "spectrum"), (win.wave, "time")):
        plot.scene().sigMouseClicked.connect(
            lambda event, k=kind: _chart_focus(win, k))
    win.views.currentChanged.connect(
        lambda _: _focus_inspector(
            win, "time" if win.views.currentWidget() is win.wave_page
            else "spectrum"))
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
    _refresh_status(win)
    win._modern_status_timer = QtCore.QTimer(win)
    win._modern_status_timer.setInterval(700)
    win._modern_status_timer.timeout.connect(lambda: _refresh_status(win))
    win._modern_status_timer.start()

    theme = "system"
    if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
        theme = QtCore.QSettings("MVK", "MVK Live").value("ui/theme_v1", "system")
    apply_theme(win, theme)
    win._modern_installed = True
