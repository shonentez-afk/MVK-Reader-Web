"""Bind both live Qt plots to source TQGrapher margin expressions.

Unit115 007CA593..007CA62F supplies the rectangle. Qt font measurements
and logical pixels are deliberately recorded as Qt, never native GDI proof.
"""
from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QFontMetrics
import pyqtgraph as pg

from ..core.original_graph_layout import source_graph_layout
from ..core.original_live_axis_ticks import (
    source_live_axis_ticks, source_live_axis_tick_text,
)
from .tqgrapher_textout_qt_candidate import qt_source_font_candidate
from .source_live_grid import SourceLiveGridOverlay


class SourceTickAxis(pg.AxisItem):
    """Source 10x10 tick model for the actual Qt graph, not a GDI glyph oracle.

    This is deliberately an AxisItem: 10-division ticks and labels update
    from the *current* view range for pan, resize, FIR Fs and FFT zoom,
    without touching the underlying sampled values or drawing a stale
    bitmap overlay. Research setTicks() still overrides this model.
    """
    def __init__(self, orientation, **kwargs):
        super().__init__(orientation=orientation, **kwargs)
        self.source_tick_model = None

    def tickValues(self, minVal, maxVal, size):
        try:
            lo = float(min(minVal, maxVal))
            span = float(max(minVal, maxVal)-lo)
            model = source_live_axis_ticks(scr_left=lo, scr_width=span)
        except (ValueError, OverflowError, TypeError):
            self.source_tick_model = None
            return super().tickValues(minVal, maxVal, size)
        self.source_tick_model = model
        return [(model["spacing_single"], list(model["values"]))]

    def tickStrings(self, values, scale, spacing):
        # Native Delphi "3-digit" fixed point candidate: Qt's default
        # engineering prefixes would generate different source labels.
        try:
            return [source_live_axis_tick_text(v, spacing) for v in values]
        except (ValueError, OverflowError, TypeError):
            return super().tickStrings(values, scale, spacing)


class SourceGeometryPlot(pg.PlotWidget):
    sourceGeometryChanged = Signal()

    def __init__(self, *args, **kwargs):
        self.source_canvas_model = None
        self._geometry_busy = False
        # Only the two source geometry plots use source numeric ticks;
        # Status/Config/Calib/research charts retain their own axis models.
        if "axisItems" not in kwargs:
            kwargs["axisItems"] = {
                "bottom": SourceTickAxis(orientation="bottom"),
                "left": SourceTickAxis(orientation="left"),
            }
        super().__init__(*args, **kwargs)
        # This overlay is added straight to ViewBox, not PlotItem.items:
        # normal spectrum/waveform .clear() never removes the source grid.
        self.source_grid_overlay = SourceLiveGridOverlay(self.getViewBox())
        self.getViewBox().addItem(self.source_grid_overlay,
                                  ignoreBounds=True)
        self._geometry_timer = QTimer(self)
        self._geometry_timer.setSingleShot(True)
        self._geometry_timer.timeout.connect(self.sync_source_geometry)
        self.getViewBox().sigResized.connect(self.schedule_source_geometry)
        self.schedule_source_geometry()

    def enable_source_grid(self, enabled: bool):
        self.source_grid_overlay.setVisible(bool(enabled))
        if enabled:
            self.source_grid_overlay.sync_source_grid()

    def schedule_source_geometry(self, *_):
        if hasattr(self, '_geometry_timer') and not self._geometry_busy:
            self._geometry_timer.start(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.schedule_source_geometry()

    def sync_source_geometry(self):
        if self._geometry_busy:
            return
        self._geometry_busy = True
        try:
            item = self.getPlotItem()
            fm = QFontMetrics(qt_source_font_candidate())
            model = source_graph_layout(
                width=max(30, self.viewport().width()),
                height=max(30, self.viewport().height()),
                zero_width=fm.horizontalAdvance('0'),
                six_decimals_width=fm.horizontalAdvance('0.000000'),
                text_height=fm.height(),
                x_name=bool(item.getAxis('bottom').labelText),
                y_name=bool(item.getAxis('left').labelText))
            # Empty top/right axes must not reserve a second set of margins.
            # Qt still draws its own ticks/text inside these fixed spaces.
            item.layout.setSpacing(0)
            item.layout.setContentsMargins(0, model['pixel_top'],
                                           model['margin'], 0)
            item.getAxis('left').setWidth(model['pixel_left'])
            item.getAxis('bottom').setHeight(
                model['canvas_height'] - model['pixel_bottom'])
            for name in ('left', 'bottom'):
                item.getAxis(name).setTickFont(qt_source_font_candidate())
            item.layout.activate()
            model['qt_logical_pixels'] = True
            model['original_canvas_font_metrics_verified'] = False
            changed = model != self.source_canvas_model
            self.source_canvas_model = model
            if changed:self.sourceGeometryChanged.emit()
        finally:
            self._geometry_busy = False
