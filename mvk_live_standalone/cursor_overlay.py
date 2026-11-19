"""Shared professional-style operator cursors for actual MVK Live chart data.

The same physical frequency/time is shown in Overview and detailed views.
A vertical line is only a display marker. No cursor opens device sockets,
changes RX, original FRange, saved NPZ, RAW or AUX4700.
"""
from __future__ import annotations

import math

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from .cursor_math import (
    harmonic_frequencies, nearest_local_peak, nearest_point,
    sideband_frequencies, spectral_band, time_interval, time_point,
)
from .vibration import vibration_plot_values


_A_COLOR = "#EDB954"
_B_COLOR = "#48B5D0"


def _line(color, *, movable=True, text=None):
    return pg.InfiniteLine(
        pos=0, movable=movable,
        pen=pg.mkPen(color, width=1.6, style=QtCore.Qt.PenStyle.DashLine),
        hoverPen=pg.mkPen(color, width=2.3),
        label=text, labelOpts={"position":0.93, "color":color} if text else None)


class MeasurementCursors(QtCore.QObject):
    """Per LiveWindow, with independent physical spectrum and time domains."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.a_hz = 100.0
        self.b_hz = 200.0
        self.a_seconds = -0.1
        self.b_seconds = -0.05
        self.bearing_hz = 100.0
        # The Overview cursor tracks the strongest visible measured line
        # until the operator explicitly picks a frequency. From then on,
        # the chosen frequency is stable across incoming verified FFT frames.
        self._overview_peak_manual = False
        self._busy = False
        self._comb_key = None
        self._comb_lines = []
        self._build_controls()
        self._build_lines()
        self._connect_plots()
        self._mode_changed()
        self._time_mode_changed()
        self.refresh_spectrum()
        self.refresh_time()
        self.refresh_bearing()

    def _build_controls(self):
        group = QtWidgets.QGroupBox("Измерительные курсоры")
        column = QtWidgets.QVBoxLayout(group)
        column.setContentsMargins(8, 8, 8, 8)
        column.setSpacing(6)
        column.addWidget(QtWidgets.QLabel("Режим курсора"))
        self.mode = QtWidgets.QComboBox(group)
        for label, key in (
            ("Один курсор", "single"),
            ("Курсор по пику", "peak"),
            ("Два курсора", "dual"),
            ("Измерение полосы", "band"),
            ("Гармоники", "harmonics"),
            ("Боковые частоты", "sidebands"),
        ):
            self.mode.addItem(label, key)
        self.mode.setMinimumWidth(0)
        self.mode.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored,
                                QtWidgets.QSizePolicy.Policy.Fixed)
        column.addWidget(self.mode)

        self.active_row = QtWidgets.QWidget(group)
        active_line = QtWidgets.QHBoxLayout(self.active_row)
        active_line.setContentsMargins(0, 0, 0, 0)
        active_line.setSpacing(4)
        self.active = QtWidgets.QComboBox(group)
        self.active.addItem("Курсор А", "a")
        self.active.addItem("Курсор Б", "b")
        self.active.setMinimumWidth(0)
        active_line.addWidget(self.active, stretch=1)
        previous = QtWidgets.QPushButton("◀")
        following = QtWidgets.QPushButton("▶")
        for button in (previous, following):
            button.setFixedWidth(32)
        previous.setToolTip("Предыдущая измеренная спектральная линия")
        following.setToolTip("Следующая измеренная спектральная линия")
        previous.clicked.connect(lambda: self.step_spectrum(-1))
        following.clicked.connect(lambda: self.step_spectrum(1))
        active_line.addWidget(previous)
        active_line.addWidget(following)
        column.addWidget(self.active_row)

        self.harmonics_row = QtWidgets.QWidget(group)
        harmonics_layout = QtWidgets.QVBoxLayout(self.harmonics_row)
        harmonics_layout.setContentsMargins(0, 0, 0, 0)
        harmonics_layout.addWidget(QtWidgets.QLabel("Количество гармоник"))
        self.harmonics_count = QtWidgets.QSpinBox(group)
        self.harmonics_count.setRange(1, 10)
        self.harmonics_count.setValue(5)
        self.harmonics_count.setSuffix(" линий")
        harmonics_layout.addWidget(self.harmonics_count)
        column.addWidget(self.harmonics_row)

        self.sideband_row = QtWidgets.QWidget(group)
        sideband_layout = QtWidgets.QVBoxLayout(self.sideband_row)
        sideband_layout.setContentsMargins(0, 0, 0, 0)
        sideband_layout.setSpacing(4)
        sideband_layout.addWidget(QtWidgets.QLabel("Шаг боковых частот"))
        spacing_line = QtWidgets.QHBoxLayout()
        spacing_line.setContentsMargins(0, 0, 0, 0)
        self.sideband_spacing = QtWidgets.QDoubleSpinBox(group)
        self.sideband_spacing.setRange(0.001, 100000.0)
        self.sideband_spacing.setDecimals(3)
        self.sideband_spacing.setValue(25)
        self.sideband_spacing.setSuffix(" Гц")
        spacing_line.addWidget(self.sideband_spacing, stretch=1)
        use_rpm = QtWidgets.QPushButton("Из 1×")
        use_rpm.setToolTip(
            "Принять шаг из заданных оператором оборотов; это не тахометр")
        use_rpm.clicked.connect(self._spacing_from_rpm)
        spacing_line.addWidget(use_rpm)
        sideband_layout.addLayout(spacing_line)
        sideband_layout.addWidget(QtWidgets.QLabel("Пар боковых полос"))
        self.pairs = QtWidgets.QSpinBox(group)
        self.pairs.setRange(1, 6)
        self.pairs.setValue(3)
        sideband_layout.addWidget(self.pairs)
        column.addWidget(self.sideband_row)

        self.spec_readout = QtWidgets.QLabel(
            "Нет подтверждённого спектра", group)
        self.spec_readout.setWordWrap(True)
        self.spec_readout.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        column.addWidget(self.spec_readout)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.active.currentIndexChanged.connect(self.refresh_spectrum)
        self.harmonics_count.valueChanged.connect(self.refresh_spectrum)
        self.sideband_spacing.valueChanged.connect(self.refresh_spectrum)
        self.pairs.valueChanged.connect(self.refresh_spectrum)
        self.spectrum_group = group
        spectrum_panel = self.win._modern_inspector.widget(0)
        layout = spectrum_panel.layout()
        layout.insertWidget(max(0, layout.count()-1), group)

        time_group = QtWidgets.QGroupBox("Курсоры временного сигнала")
        time_layout = QtWidgets.QVBoxLayout(time_group)
        self.time_mode = QtWidgets.QComboBox(time_group)
        for name, key in (
            ("Один момент", "single"),
            ("Два момента", "dual"),
            ("Интервал: СКЗ и размах", "interval"),
        ):
            self.time_mode.addItem(name, key)
        time_layout.addWidget(self.time_mode)
        row = QtWidgets.QHBoxLayout()
        self.time_active = QtWidgets.QComboBox(time_group)
        self.time_active.addItem("Курсор А", "a")
        self.time_active.addItem("Курсор Б", "b")
        row.addWidget(self.time_active)
        for caption, amount in (("◀", -1), ("▶", 1)):
            button = QtWidgets.QPushButton(caption)
            button.clicked.connect(lambda checked=False, d=amount:
                                   self.step_time(d))
            row.addWidget(button)
        time_layout.addLayout(row)
        self.time_readout = QtWidgets.QLabel(
            "Нет подтверждённого временного сигнала", time_group)
        self.time_readout.setWordWrap(True)
        self.time_readout.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        time_layout.addWidget(self.time_readout)
        self.time_mode.currentIndexChanged.connect(self._time_mode_changed)
        self.time_active.currentIndexChanged.connect(self.refresh_time)
        self.time_group = time_group
        time_panel = self.win._modern_inspector.widget(1)
        layout = time_panel.layout()
        layout.insertWidget(max(0, layout.count()-1), time_group)

    def _build_lines(self):
        self.a_spec = self.win.cursor   # retain the existing tested cursor
        self.a_spec.setPen(pg.mkPen(_A_COLOR, width=1.8,
                                  style=QtCore.Qt.PenStyle.DashLine))
        self.a_overview = _line(_A_COLOR)
        self.b_spec = _line(_B_COLOR)
        self.b_overview = _line(_B_COLOR)
        self.win.spec.addItem(self.b_spec)
        self.win.overview_spec.addItem(self.a_overview)
        self.win.overview_spec.addItem(self.b_overview)
        # Compact, on-graph measured peak readout. Only the COMPLETE FFT
        # drives its physical values, never the decimated rendered curve.
        self.overview_peak_dot = pg.ScatterPlotItem(
            size=10, pen=pg.mkPen(_A_COLOR, width=1.8),
            brush=pg.mkBrush("#17212D"))
        self.overview_peak_label = pg.TextItem(
            text="", anchor=(0.5, 0),
            color="#EBF1F7",
            border=pg.mkPen("#61798C", width=1),
            fill=pg.mkBrush(23, 33, 45, 228))
        self.win.overview_spec.addItem(self.overview_peak_dot,
                                       ignoreBounds=True)
        self.win.overview_spec.addItem(self.overview_peak_label,
                                       ignoreBounds=True)
        self.overview_peak_dot.setData(x=[], y=[])
        self.overview_peak_label.hide()
        self.a_time = _line(_A_COLOR)
        self.b_time = _line(_B_COLOR)
        self.a_time_overview = _line(_A_COLOR)
        self.b_time_overview = _line(_B_COLOR)
        for plot, first, second in (
            (self.win.wave, self.a_time, self.b_time),
            (self.win.overview_wave, self.a_time_overview,
             self.b_time_overview),
        ):
            plot.addItem(first)
            plot.addItem(second)
        self.bearing_line = _line(_A_COLOR)
        self.win.bearing_plot.addItem(self.bearing_line)
        self.bearing_readout = QtWidgets.QLabel(
            "Огибающая · курсор ожидает рассчитанный спектр")
        self.bearing_readout.setWordWrap(True)
        self.bearing_readout.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.win.diagnostics_layout.addWidget(self.bearing_readout)

    def _connect_plots(self):
        self.a_overview.sigPositionChanged.connect(
            lambda *_: self._spectrum_line_moved(self.a_overview, "a"))
        for first in (self.a_spec, self.a_overview):
            first.sigPositionChangeFinished.connect(
                lambda *_args, item=first:
                self._snap_primary_after_drag(item))
        self.b_spec.sigPositionChanged.connect(
            lambda *_: self._spectrum_line_moved(self.b_spec, "b"))
        self.b_overview.sigPositionChanged.connect(
            lambda *_: self._spectrum_line_moved(self.b_overview, "b"))
        for line, slot in (
            (self.a_time, "a"), (self.a_time_overview, "a"),
            (self.b_time, "b"), (self.b_time_overview, "b"),
        ):
            line.sigPositionChanged.connect(
                lambda *_args, item=line, side=slot:
                self._time_line_moved(item, side))
        self.bearing_line.sigPositionChanged.connect(
            lambda *_: self._bearing_line_moved())
        for plot, kind in (
            (self.win.spec, "spectrum"),
            (self.win.overview_spec, "spectrum"),
            (self.win.wave, "time"),
            (self.win.overview_wave, "time"),
            (self.win.bearing_plot, "bearing"),
        ):
            plot.scene().sigMouseClicked.connect(
                lambda event, p=plot, k=kind: self._plot_clicked(event, p, k))
            plot.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
            for name, direction in (
                ("Left", -1), ("Right", 1), ("Shift+Left", -10),
                ("Shift+Right", 10),
            ):
                shortcut = QtGui.QShortcut(QtGui.QKeySequence(name), plot)
                shortcut.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
                if kind == "time":
                    shortcut.activated.connect(
                        lambda d=direction: self.step_time(d))
                elif kind == "spectrum":
                    if plot is self.win.overview_spec:
                        shortcut.activated.connect(
                            lambda d=direction: self.step_overview_peak(d))
                    else:
                        shortcut.activated.connect(
                            lambda d=direction: self.step_spectrum(d))
        self.win.xscale.currentIndexChanged.connect(self.refresh_spectrum)

    def _mode_changed(self, *_):
        mode = self.mode.currentData()
        self.active.setEnabled(mode in ("dual", "band"))
        self.harmonics_row.setVisible(mode == "harmonics")
        self.sideband_row.setVisible(mode == "sidebands")
        self._comb_key = None
        self.refresh_spectrum()

    def _time_mode_changed(self, *_):
        self.time_active.setEnabled(self.time_mode.currentData() != "single")
        self.refresh_time()

    def _spacing_from_rpm(self):
        rpm = float(self.win.rpm.value())
        if rpm <= 0:
            self.spec_readout.setText(
                "Сначала задайте обороты вручную или примите оценку 1× по ВС. "
                "Тахометр не используется.")
            return
        self.sideband_spacing.setValue(rpm / 60.0)

    def _freq_to_view(self, hz: float) -> float:
        return math.log10(max(hz, 1e-12)) if (
            self.win.xscale.currentData() == "log") else hz

    def _view_to_freq(self, position: float) -> float:
        return (10 ** max(-12.0, min(12.0, position))
                if self.win.xscale.currentData() == "log" else position)

    def _spec_data(self):
        s = self.win._spectrum
        if s is None or len(s.hz) == 0:
            return None
        return s

    def _unit(self, s) -> str:
        if self.win.yscale.currentData() == "db":
            return "дБ (от выбранной опоры)"
        if s.mode == "welch":
            return f"({s.units})²/Гц"
        if s.mode == "asd":
            return f"{s.units}/√Гц"
        return f"{s.units} СКЗ линии"

    def _visible_spec(self, ready):
        for line in (self.a_spec, self.a_overview):
            line.setVisible(bool(ready))
        for line in (self.b_spec, self.b_overview):
            line.setVisible(bool(ready and self.mode.currentData()
                                 in ("dual", "band")))

    def on_primary_moved(self, *_):
        """Existing app.py signal path for directly dragging original line."""
        if self._busy:
            return
        self.a_hz = self._view_to_freq(float(self.a_spec.value()))
        self.refresh_spectrum()

    def _spectrum_line_moved(self, line, side):
        if self._busy:
            return
        freq = self._view_to_freq(float(line.value()))
        if side == "a":
            self.a_hz = freq
            self._overview_peak_manual = True
        else:
            self.b_hz = freq
        self.refresh_spectrum()

    def _snap_primary_after_drag(self, source=None):
        if self._busy:
            return
        if source is self.a_overview:
            # Overview always snaps to measured local maxima on release.
            self._set_spectrum_selection(self.a_hz, "a", snap_peak=True)
        elif self.mode.currentData() == "peak":
            self._set_spectrum_selection(self.a_hz, "a")

    def _set_spectrum_selection(self, freq: float, side=None, *,
                                snap_peak=False):
        s = self._spec_data()
        if s is None or not math.isfinite(freq):
            return
        if snap_peak or self.mode.currentData() == "peak":
            point = nearest_local_peak(s.hz, s.rms, freq)
        else:
            point = nearest_point(s.hz, s.rms, freq)
        side = side or self.active.currentData()
        if side == "b" and self.mode.currentData() in ("dual", "band"):
            self.b_hz = point.position
        else:
            self.a_hz = point.position
            self._overview_peak_manual = True
        self.refresh_spectrum()

    def step_spectrum(self, amount: int):
        s = self._spec_data()
        if s is None:
            return
        side = (self.active.currentData() if self.mode.currentData()
                in ("dual", "band") else "a")
        current = self.b_hz if side == "b" else self.a_hz
        idx = nearest_point(s.hz, s.rms, current).index
        idx = max(0, min(len(s.hz)-1, idx + int(amount)))
        self._set_spectrum_selection(float(s.hz[idx]), side)

    def step_overview_peak(self, amount: int):
        """Arrows on Overview traverse REAL measured local peaks, not bins."""
        s = self._spec_data()
        if s is None or not amount:
            return
        # The same full-resolution samples drive the cursor and the chart.
        indices = np.flatnonzero(
            (s.rms[1:-1] > s.rms[:-2]) &
            (s.rms[1:-1] >= s.rms[2:])) + 1
        maximum = min(float(self.win.x_limit_choice.currentData()),
                      float(s.hz[-1]))
        displayed = np.flatnonzero((s.hz > 0) & (s.hz <= maximum) &
                                  np.isfinite(s.rms))
        if not len(displayed):
            return
        # Float32/Hann leakage creates tiny mathematical local maxima even
        # between two strong, physically meaningful spectral lines. Arrows
        # should jump to audible-sized measured peaks, not numerical ripple.
        # This 60 dB-relative NAVIGATION threshold is only a UI preference:
        # manual clicks still select every actual peak/bin and all measured
        # FFT values remain unmodified and visible.
        minimum = max(float(np.max(s.rms[displayed])) * 1e-3,
                      np.finfo(np.float64).eps)
        indices = indices[(s.hz[indices] > 0) &
                          (s.hz[indices] <= maximum) &
                          (s.rms[indices] >= minimum)]
        if not len(indices):
            return
        frequencies = s.hz[indices]
        if amount > 0:
            next_index = int(np.searchsorted(
                frequencies, self.a_hz, side="right"))
            chosen = min(len(indices)-1, next_index + abs(int(amount))-1)
        else:
            before = int(np.searchsorted(
                frequencies, self.a_hz, side="left")) - 1
            chosen = max(0, before - abs(int(amount)) + 1)
        self.a_hz = float(frequencies[chosen])
        self._overview_peak_manual = True
        self.refresh_spectrum()

    def _plot_clicked(self, event, plot, kind):
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        vb = plot.getPlotItem().getViewBox()
        if not vb.sceneBoundingRect().contains(event.scenePos()):
            return
        plot.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
        position = float(vb.mapSceneToView(event.scenePos()).x())
        if not math.isfinite(position):
            return
        if kind == "spectrum":
            if plot is self.win.overview_spec:
                # A simple click on Overview must behave professionally:
                # nearest local peak, irrespective of detailed cursor mode.
                self._set_spectrum_selection(
                    self._view_to_freq(position), "a", snap_peak=True)
            else:
                side = (self.active.currentData() if self.mode.currentData()
                        in ("dual", "band") else "a")
                self._set_spectrum_selection(
                    self._view_to_freq(position), side)
                if side == "a" and self.mode.currentData() in ("dual", "band"):
                    self.active.setCurrentIndex(1)
        elif kind == "time":
            side = (self.time_active.currentData() if self.time_mode.currentData()
                    != "single" else "a")
            self._set_time_selection(position, side)
            if side == "a" and self.time_mode.currentData() != "single":
                self.time_active.setCurrentIndex(1)
        elif kind == "bearing":
            self.bearing_hz = max(0.0, position)
            self.refresh_bearing()

    def refresh_spectrum(self, *_):
        s = self._spec_data()
        if s is None:
            self._visible_spec(False)
            self.overview_peak_dot.setData(x=[], y=[])
            self.overview_peak_label.hide()
            self._overview_peak_manual = False
            self.spec_readout.setText("Нет подтверждённого спектра")
            self._clear_comb()
            return
        if not self._overview_peak_manual:
            # At first measurement show the strongest REAL line in the
            # visible frequency range. Do not fabricate an RMS or a peak.
            maximum = min(float(self.win.x_limit_choice.currentData()),
                          float(s.hz[-1]))
            visible = np.flatnonzero((s.hz > 0) & (s.hz <= maximum) &
                                   np.isfinite(s.rms))
            if len(visible):
                strongest = visible[int(np.argmax(s.rms[visible]))]
                self.a_hz = float(s.hz[strongest])
        self.a_hz = float(np.clip(self.a_hz, s.hz[0], s.hz[-1]))
        self.b_hz = float(np.clip(self.b_hz, s.hz[0], s.hz[-1]))
        self._busy = True
        try:
            self._visible_spec(True)
            for line, hz in (
                (self.a_spec, self.a_hz), (self.a_overview, self.a_hz),
                (self.b_spec, self.b_hz), (self.b_overview, self.b_hz),
            ):
                line.setValue(self._freq_to_view(hz))
        finally:
            self._busy = False
        display = vibration_plot_values(
            s, self.win.yscale.currentData(),
            reference=self.win.db_ref.currentData())
        units = self._unit(s)
        try:
            a = nearest_point(s.hz, display, self.a_hz)
            text = f"А · {a.position:.4g} Гц · {a.value:.6g} {units}"
            mode = self.mode.currentData()
            if mode in ("dual", "band"):
                b = nearest_point(s.hz, display, self.b_hz)
                text += (f"\nБ · {b.position:.4g} Гц · {b.value:.6g} {units}"
                         f"\nРазность частот: {abs(b.position-a.position):.4g} Гц"
                         f" · уровней: {b.value-a.value:+.6g} {units}")
                if mode == "band" and a.position != b.position:
                    band = spectral_band(
                        s.hz, s.rms, min(a.position, b.position),
                        max(a.position, b.position), s.mode)
                    if band.method == "RMS_FROM_DENSITY":
                        text += f"\nСКЗ выбранной полосы: {band.value:.6g} {s.units}"
                    else:
                        text += (f"\nНаибольшая спектральная линия: "
                                 f"{band.frequency_hz:.4g} Гц · "
                                 f"{band.value:.6g} {s.units}"
                                 "\nНе суммировать FFT-линии как плотность")
            elif mode == "peak":
                text += "\nПривязка к локальному максимуму (не диагностика)"
            elif mode in ("harmonics", "sidebands"):
                text += ("\nТонкие линии — расчётные кратные частоты, "
                         "не отдельно подтверждённые дефекты")
        except ValueError as exc:
            text = str(exc)
        self.spec_readout.setText(text)
        self._update_overview_peak(s, display)
        self._draw_comb(s)

    def _update_overview_peak(self, s, display):
        """In-graph frequency/amplitude at the SELECTED original FFT bin."""
        try:
            point = nearest_point(s.hz, display, self.a_hz)
        except ValueError:
            self.overview_peak_dot.setData(x=[], y=[])
            self.overview_peak_label.hide()
            return
        index = point.index
        local_max = (0 < index < len(s.rms)-1 and
                     s.rms[index] > s.rms[index-1] and
                     s.rms[index] >= s.rms[index+1])
        units = ("дБ" if self.win.yscale.currentData() == "db"
                 else self._unit(s))
        self.overview_peak_label.setText(
            f"{point.position:.5g} Гц\n"
            f"{point.value:.5g} {units}"
            + (" · пик" if local_max else " · линия"))
        # The TextItem is in ViewBox coordinates, so log X needs log10 Hz;
        # the ScatterPlotItem is a plotted data item and takes actual Hz.
        self.overview_peak_label.setPos(
            self._freq_to_view(point.position), point.value)
        self.overview_peak_dot.setData(
            x=[point.position], y=[point.value])
        self.overview_peak_label.show()

    def _clear_comb(self):
        for plot, line in self._comb_lines:
            plot.removeItem(line)
        self._comb_lines.clear()
        self._comb_key = None

    def _draw_comb(self, s):
        mode = self.mode.currentData()
        if mode not in ("harmonics", "sidebands"):
            if self._comb_lines:
                self._clear_comb()
            return
        if mode == "harmonics":
            if self.a_hz <= 0:
                self._clear_comb()
                return
            markers = harmonic_frequencies(
                self.a_hz, self.harmonics_count.value(), float(s.hz[-1]))
        else:
            if self.a_hz <= 0:
                self._clear_comb()
                return
            markers = sideband_frequencies(
                self.a_hz, self.sideband_spacing.value(), self.pairs.value(),
                float(s.hz[-1]))
        key = (mode, tuple((label, round(freq, 9))
                           for label, freq in markers),
               self.win.xscale.currentData())
        if self._comb_key == key:
            return
        self._clear_comb()
        for label, freq in markers:
            for plot in (self.win.spec, self.win.overview_spec):
                line = _line("#7F95AB", movable=False, text=label)
                line.setValue(self._freq_to_view(freq))
                plot.addItem(line)
                self._comb_lines.append((plot, line))
        self._comb_key = key

    def _time_data(self):
        samples = getattr(self.win, "_cursor_time_samples", None)
        fs = getattr(self.win, "_cursor_time_fs", None)
        if samples is None or fs is None or fs <= 0 or len(samples) < 2:
            return None
        return samples, int(fs)

    def _time_line_moved(self, line, side):
        if self._busy:
            return
        if side == "a":
            self.a_seconds = float(line.value())
        else:
            self.b_seconds = float(line.value())
        self.refresh_time()

    def _set_time_selection(self, position, side):
        data = self._time_data()
        if data is None:
            return
        p = time_point(data[0], data[1], position)
        if side == "b" and self.time_mode.currentData() != "single":
            self.b_seconds = p.position
        else:
            self.a_seconds = p.position
        self.refresh_time()

    def step_time(self, amount: int):
        data = self._time_data()
        if data is None:
            return
        side = (self.time_active.currentData() if self.time_mode.currentData()
                != "single" else "a")
        current = self.b_seconds if side == "b" else self.a_seconds
        self._set_time_selection(current + int(amount)/data[1], side)

    def refresh_time(self, *_):
        data = self._time_data()
        ready = data is not None
        show_b = self.time_mode.currentData() != "single"
        for line in (self.a_time, self.a_time_overview):
            line.setVisible(ready)
        for line in (self.b_time, self.b_time_overview):
            line.setVisible(ready and show_b)
        if not ready:
            self.time_readout.setText("Нет подтверждённого временного сигнала")
            return
        values, fs = data
        first = time_point(values, fs, self.a_seconds)
        second = time_point(values, fs, self.b_seconds)
        self.a_seconds = first.position
        self.b_seconds = second.position
        self._busy = True
        try:
            for line, moment in (
                (self.a_time, self.a_seconds),
                (self.a_time_overview, self.a_seconds),
                (self.b_time, self.b_seconds),
                (self.b_time_overview, self.b_seconds),
            ):
                line.setValue(moment)
        finally:
            self._busy = False
        text = f"А · {first.position:.6g} с · {first.value:.6g} м/с²"
        if show_b:
            text += (f"\nБ · {second.position:.6g} с · {second.value:.6g} м/с²"
                     f"\nΔt = {abs(second.position-first.position):.6g} с"
                     f" · Δa = {second.value-first.value:+.6g} м/с²")
            if self.time_mode.currentData() == "interval":
                try:
                    span = time_interval(values, fs, first.position, second.position)
                    text += (
                        f"\nВыделено {span.samples} реальных отсчётов · "
                        f"СКЗ полный {span.rms:.6g} м/с² · "
                        f"размах {span.peak_to_peak:.6g} м/с²")
                except ValueError as exc:
                    text += f"\n{exc}"
        self.time_readout.setText(text)

    def _bearing_line_moved(self):
        if self._busy:
            return
        self.bearing_hz = float(self.bearing_line.value())
        self.refresh_bearing()

    def refresh_bearing(self):
        # Detached bearing view is not the LIVE/overview spectrum.
        s = self.win._bearing_spectrum
        if s is None or s.mode != "envelope":
            self.bearing_line.hide()
            self.bearing_readout.setText(
                "Огибающая · курсор ожидает рассчитанный спектр")
            return
        self.bearing_hz = float(np.clip(
            self.bearing_hz, s.hz[0], s.hz[-1]))
        self._busy = True
        try:
            self.bearing_line.show()
            self.bearing_line.setValue(self.bearing_hz)
        finally:
            self._busy = False
        p = nearest_point(s.hz, s.rms, self.bearing_hz)
        self.bearing_readout.setText(
            f"Измеренная линия огибающей · {p.position:.5g} Гц · "
            f"{p.value:.6g} м/с² СКЗ линии. "
            "Это локальный APP_DERIVED спектр, не заключение о дефекте.")


def install_measurement_cursors(win):
    """Called once, after four-tab modern shell is assembled."""
    if hasattr(win, "_professional_cursors"):
        return win._professional_cursors
    win._professional_cursors = MeasurementCursors(win)
    return win._professional_cursors
