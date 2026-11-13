"""Source original-order grid+series+frame on live Qt ViewBox.

A new *independent* overlay is placed above the ordinary Qt curve and
the CF grid/frame candidates, but below both cursor XOR overlays.
The Qt curve remains allocated for autorange/cursor/exports. Unverified
live-Receiver frames, arbitrary research spectra and incomplete archive
data are NEVER bound to this overlay.

Debounced, bounded TCo2Draw raster slices let user input run between
steps and discard stale pan/zoom images. The only final result is an
immutable QImage of source visual data; it cannot modify Core arrays.
"""
from __future__ import annotations

from hashlib import sha256
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QImage, QPainter

from ..core.original_live_plot_composite import (
    prepare_live_source_bitmap, LiveSourceBitmapTask,
    SOURCE as CG_SOURCE,
)
from ..core.original_live_whole_paintbox import (
    WholePaintboxTask, SOURCE as WHOLE_SOURCE,
)
from .source_whole_canvas_adapter import (
    prepare_qt_source_whole_paintbox_task,
)


class SourceLiveCompositeOverlay(pg.GraphicsObject):
    def __init__(self, view_box, plot_widget=None):
        super().__init__()
        self._view_box = view_box
        self._plot_widget = plot_widget
        self.source_textout_sink = None
        self.source_whole_paintbox_last_error = None
        self._rect = QRectF(view_box.viewRect())
        self._series = None
        self._generation = 0
        self._task = None
        self._task_signature = None
        self._image = None
        self._completed_signature = None
        self.source_composite_receipt = None
        self.source_composite_render_count = 0
        self.source_composite_last_error = None
        self._start_timer = QTimer(self)
        self._start_timer.setSingleShot(True)
        self._start_timer.timeout.connect(self._start_render)
        self._slice_timer = QTimer(self)
        self._slice_timer.setSingleShot(True)
        self._slice_timer.timeout.connect(self._render_slice)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setZValue(600000)  # Above data/frame, below clGreen XOR z1e6
        self.setVisible(False)
        view_box.sigRangeChanged.connect(self._schedule_view)
        view_box.sigResized.connect(self._schedule_view)

    @property
    def source_series_bound(self):
        return self._series is not None

    def bind_source_series(self, values, *, x_start, x_scale,
                           provenance, expected_series_sha256):
        data = np.asarray(values)
        if (data.ndim != 1 or data.size < 2 or data.dtype.kind not in "fi"
                or data.dtype.kind == "b"):
            raise ValueError("Full source TQGRSeries Float32 required")
        copy = np.array(data, dtype="<f4", order="C", copy=True)
        digest = sha256(copy.tobytes()).hexdigest()
        if digest != expected_series_sha256:
            raise ValueError("Qt source series and Core digest disagree")
        if not bool(np.isfinite(copy).all()):
            raise ValueError("Nonfinite original series not allowed")
        copy.setflags(write=False)
        self._series = (copy, float(x_start), float(x_scale),
                        provenance, digest)
        self.source_composite_last_error = None
        self._schedule_view()

    def clear_source_series(self):
        self._series = None
        self.source_composite_last_error = None
        self._cancel()
        self.update()

    def _signature(self):
        rect = self._rect
        if self._plot_widget is None:
            labels=("","")
        else:
            item=self._plot_widget.getPlotItem()
            labels=(item.getAxis("bottom").labelText or "",
                    item.getAxis("left").labelText or "")
        return (rect.left(),rect.right(),rect.top(),rect.bottom(),
                max(0,int(round(self._view_box.width()))),
                max(0,int(round(self._view_box.height()))),
                bool(self._view_box.state.get("xInverted",False)),
                self._series[4] if self._series else None,
                *labels)

    def _cancel(self):
        self._generation += 1
        if self.source_textout_sink is not None:
            self.source_textout_sink.invalidate_adopted_bitmap()
        self._start_timer.stop()
        self._slice_timer.stop()
        self._task = None
        self._task_signature = None
        self._image = None
        self._completed_signature = None
        self.source_composite_receipt = None
        self.setVisible(False)

    def _schedule_view(self, *_):
        rect = QRectF(self._view_box.viewRect())
        if rect != self._rect:
            self.prepareGeometryChange()
            self._rect = rect
        self._cancel()
        if self._series is not None and self._view_box.isVisible():
            # Do not perform an expensive full-viewport draw after
            # EVERY intermediate mouse-drag/scroll wheel signal.
            self._start_timer.start(65)
        self.update()

    def _start_render(self):
        self._start_timer.stop()
        if self._series is None or not self._view_box.isVisible():
            return False
        signature = self._signature()
        if self._completed_signature == signature and self._image is not None:
            return True
        self.source_whole_paintbox_last_error = None
        try:
            self._task = self._build_source_task(signature)
            self._task_signature = signature
        except (ValueError,TypeError,KeyError,OverflowError,MemoryError,
                OSError,RuntimeError) as ex:
            self.source_composite_last_error=str(ex)
            self._task = None
            self._task_signature = None
            self._image = None
            self.setVisible(False)
            if self.source_textout_sink is not None:
                self.source_textout_sink.schedule_fallback_text()
            return False
        self._render_slice()
        return True

    def _build_source_task(self, signature, *, allow_whole=True):
        data, x_start, x_scale, provenance, digest = self._series
        if allow_whole and self._plot_widget is not None:
            try:
                return prepare_qt_source_whole_paintbox_task(
                    self._plot_widget,data,signature=signature,
                    x_start=x_start,x_scale=x_scale,provenance=provenance,
                    expected_series_sha256=digest)
            except (ValueError,TypeError,KeyError,OverflowError,MemoryError,
                    OSError,RuntimeError) as ex:
                # Native GDI/paintbox registration must never make a
                # previously accepted archive waveform/spectrum invisible.
                self.source_whole_paintbox_last_error = str(ex)
        plan = prepare_live_source_bitmap(
            data,view_x=(signature[0],signature[1]),
            view_y=(signature[2],signature[3]),
            width=signature[4],height=signature[5],
            x_inverted=signature[6],
            x_start=x_start,x_scale=x_scale,
            provenance=provenance,expected_series_sha256=digest)
        return LiveSourceBitmapTask(plan)

    def _render_slice(self):
        task = self._task
        if task is None:
            return
        if self._task_signature != self._signature():
            self._cancel()
            return
        try:
            complete = task.step(max_segments=128)
        except (ValueError,TypeError,OverflowError,MemoryError,
                OSError,RuntimeError) as ex:
            self.source_composite_last_error=str(ex)
            if isinstance(task, WholePaintboxTask):
                self.source_whole_paintbox_last_error = str(ex)
                try:
                    self._task = self._build_source_task(
                        self._task_signature,allow_whole=False)
                    if self.source_textout_sink is not None:
                        self.source_textout_sink.schedule_fallback_text()
                    self._render_slice()
                    return
                except (ValueError,TypeError,OverflowError,MemoryError):
                    pass
            self._cancel()
            return
        if not complete:
            self._slice_timer.start(0)
            return
        result = task.result()
        self._task = None
        self._task_signature = None
        self._install_frame(result, self._signature())

    def _install_frame(self, result, signature):
        if self._series is None or signature != self._signature():
            return False
        whole = result.get("source") == WHOLE_SOURCE
        arr = result["rgba"]
        if whole:
            canvas=result["canvas"]
            left,right=canvas["pixel_left"],canvas["pixel_right"]
            top,bottom=canvas["pixel_top"],canvas["pixel_bottom"]
            if not (0<=left<right<=arr.shape[1]
                    and 0<=top<bottom<=arr.shape[0]):
                self.source_composite_last_error=(
                    "Full PaintBox source crop outside GDI pixel bounds")
                return False
            # ONE immutable source bitmap is split only at presentation
            # time: QGraphicsView draws the plot, the mouse-transparent
            # widget draws its axis margins. Source TextOut was already
            # applied before all black series strokes in THIS array.
            plot_pixels=arr[top:bottom,left:right]
            h,w=plot_pixels.shape[:2]
        else:
            plot_pixels=arr
            w,h=result["logical_size"]
        if signature[6]:
            display = np.ascontiguousarray(plot_pixels[::-1, ::-1])
        else:
            display = np.ascontiguousarray(plot_pixels[::-1])
        qimage = QImage(display.data,w,h,display.strides[0],
                        QImage.Format_RGBA8888).copy()
        qimage.setDevicePixelRatio(1.0)
        if qimage.isNull():
            self.source_composite_last_error="Invalid source Qt QImage"
            self.setVisible(False)
            return False
        if whole and self.source_textout_sink is not None:
            if not self.source_textout_sink.accept_whole_paintbox_bitmap(
                    result,signature):
                self.source_composite_last_error=(
                    "Full PaintBox text margin crop rejected")
                return False
        self._image = qimage
        self._completed_signature = signature
        self.source_composite_receipt = {
            k:v for k,v in result.items() if k not in ("rgba","text_plan")}
        if whole:
            self.source_composite_receipt.update({
                "source":CG_SOURCE,
                "whole_paintbox_source":WHOLE_SOURCE,
                "source_software_grid_and_series_and_frame_one_bitmap":True,
                "source_textout_full_paintbox_implemented":True,
                "original_win32_gdi_pixel_parity_verified":False,
            })
        else:
            if self.source_textout_sink is not None:
                self.source_textout_sink.schedule_fallback_text()
        self.source_composite_render_count += 1
        self.source_composite_last_error = None
        self.setVisible(True)
        self.update()
        return True

    def render_source_composite_now(self):
        """Synchronous explicit QA hook; UI normally uses incremental slices."""
        self._start_timer.stop()
        self._slice_timer.stop()
        if self._series is None:
            return False
        signature = self._signature()
        if self._completed_signature == signature and self._image is not None:
            return True
        if self._task is not None and self._task_signature == signature:
            task = self._task
        else:
            try:
                task=self._build_source_task(signature)
            except (TypeError,ValueError,OverflowError,MemoryError,
                    OSError,RuntimeError) as ex:
                self.source_composite_last_error=str(ex)
                return False
        try:
            result=task.finish(max_segments=256)
        except (ValueError,TypeError,OverflowError,MemoryError,
                OSError,RuntimeError) as ex:
            self.source_composite_last_error=str(ex)
            if isinstance(task,WholePaintboxTask):
                self.source_whole_paintbox_last_error=str(ex)
                try:
                    task=self._build_source_task(signature,allow_whole=False)
                    result=task.finish(max_segments=256)
                except (ValueError,TypeError,OverflowError,MemoryError):
                    return False
            else:
                return False
        self._task=None
        self._task_signature=None
        return self._install_frame(result,signature)

    def boundingRect(self):
        return QRectF(self._rect)

    def paint(self,painter,option,widget=None):
        if (self._image is None or not self.isVisible()
                or self._completed_signature != self._signature()):
            return
        painter.save()
        try:
            painter.setRenderHint(QPainter.Antialiasing,False)
            painter.setRenderHint(QPainter.SmoothPixmapTransform,False)
            painter.setClipRect(self._rect,Qt.IntersectClip)
            painter.drawImage(self._rect,self._image)
        finally:
            painter.restore()
