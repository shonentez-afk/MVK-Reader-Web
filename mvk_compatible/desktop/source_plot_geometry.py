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
from .source_live_grid import SourceLiveGridOverlay, SourceLiveFrameOverlay
from .source_live_composite import SourceLiveCompositeOverlay
from .source_paintbox_text_overlay import (
    SourcePaintBoxTextOverlay, source_paintbox_font_metrics,
)


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
        # Original Unit115:007CB3FF draws its black plot frame after
        # the source data, but before the clGreen pmXor cursor.
        self.source_frame_overlay = SourceLiveFrameOverlay(self.getViewBox())
        self.getViewBox().addItem(self.source_frame_overlay,
                                  ignoreBounds=True)
        # Source Draw's full software bitmap covers Qt curve/frame,
        # while preserving original Qt PlotDataItems for autorange.
        self.source_composite_overlay = SourceLiveCompositeOverlay(
            self.getViewBox(),plot_widget=self)
        self.getViewBox().addItem(self.source_composite_overlay,
                                  ignoreBounds=True)
        self._geometry_timer = QTimer(self)
        self._geometry_timer.setSingleShot(True)
        self._geometry_timer.timeout.connect(self.sync_source_geometry)
        self.getViewBox().sigResized.connect(self.schedule_source_geometry)
        # A full PaintBox margin plane (not an extra axis label hack)
        # carries source TextOut glyph pixels for current verified data.
        self.source_paintbox_text_overlay=SourcePaintBoxTextOverlay(self)
        self.source_composite_overlay.source_textout_sink=(
            self.source_paintbox_text_overlay)
        self.sourceGeometryChanged.connect(
            self.source_paintbox_text_overlay.schedule_source_text)
        self.getViewBox().sigRangeChanged.connect(
            self.source_paintbox_text_overlay.schedule_source_text)
        self.getViewBox().sigResized.connect(
            self.source_paintbox_text_overlay.schedule_source_text)
        self.schedule_source_geometry()

    def bind_source_tqgr_series(self, values, *, x_start, x_scale,
                                provenance, expected_series_sha256):
        """Bind verified original-order Core Float32 samples to ONE bitmap.

        This is a pure graphics binding: original GetSignal / FFT arrays
        and all cursor/export readouts remain outside the renderer.
        """
        self.source_grid_overlay.suspend_automatic_raster(True)
        try:
            self.source_composite_overlay.bind_source_series(
                values,x_start=x_start,x_scale=x_scale,
                provenance=provenance,
                expected_series_sha256=expected_series_sha256)
            self.source_paintbox_text_overlay.set_source_enabled(True)
        except (TypeError,ValueError,OverflowError,MemoryError):
            self.source_composite_overlay.clear_source_series()
            self.source_paintbox_text_overlay.set_source_enabled(False)
            self.source_grid_overlay.suspend_automatic_raster(False)
            raise

    def clear_source_tqgr_series(self):
        self.source_composite_overlay.clear_source_series()
        self.source_paintbox_text_overlay.set_source_enabled(False)
        self.source_grid_overlay.suspend_automatic_raster(False)

    def enable_source_grid(self, enabled: bool):
        enabled = bool(enabled)
        self.source_grid_overlay.setVisible(enabled)
        self.source_frame_overlay.setVisible(enabled)
        if not enabled:
            self.source_composite_overlay.setVisible(False)
            self.source_paintbox_text_overlay.set_source_enabled(False)
        else:
            self.source_grid_overlay.sync_source_grid()
            self.source_frame_overlay.sync_source_frame()
            self.source_composite_overlay._schedule_view()
            if self.source_composite_overlay.source_series_bound:
                self.source_paintbox_text_overlay.set_source_enabled(True)

    def showEvent(self,event):
        super().showEvent(event)
        if hasattr(self,"source_composite_overlay"):
            self.source_composite_overlay._schedule_view()
        if hasattr(self,"source_paintbox_text_overlay"):
            self.source_paintbox_text_overlay.schedule_source_text()

    def setLabel(self, *args, **kwargs):
        # Existing MainWindow updates the native unit labels dynamically.
        # Keep the event/text plan in sync without changing Qt data curves.
        self.getPlotItem().setLabel(*args,**kwargs)
        if hasattr(self,"source_paintbox_text_overlay"):
            self.source_paintbox_text_overlay.schedule_source_text()
        if hasattr(self,"source_composite_overlay"):
            self.source_composite_overlay._schedule_view()

    def schedule_source_geometry(self, *_):
        if hasattr(self, '_geometry_timer') and not self._geometry_busy:
            self._geometry_timer.start(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.schedule_source_geometry()
        if hasattr(self,"source_paintbox_text_overlay"):
            self.source_paintbox_text_overlay.schedule_source_text()

    def sync_source_geometry(self):
        if self._geometry_busy:
            return
        self._geometry_busy = True
        try:
            item = self.getPlotItem()
            # On Windows the actual source-derived DFM GDI Font.Height
            # (-13 logical px), not Qt QFontMetrics, defines margins.
            # The original executable's runtime font/PPI remain OPEN.
            fonts=source_paintbox_font_metrics()
            model = source_graph_layout(
                width=max(30, self.viewport().width()),
                height=max(30, self.viewport().height()),
                zero_width=fonts['zero'],
                six_decimals_width=fonts['six'],
                text_height=fonts['height'],
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
            model['source_font_metrics_backend'] = fonts[
                'font_metrics_provenance']
            model['source_dfm_font_height'] = -13
            model['original_canvas_font_metrics_verified'] = False
            changed = model != self.source_canvas_model
            self.source_canvas_model = model
            if changed:self.sourceGeometryChanged.emit()
        finally:
            self._geometry_busy = False
