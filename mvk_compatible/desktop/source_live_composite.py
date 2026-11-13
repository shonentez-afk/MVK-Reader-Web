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
)


class SourceLiveCompositeOverlay(pg.GraphicsObject):
    def __init__(self, view_box):
        super().__init__()
        self._view_box = view_box
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
        return (rect.left(),rect.right(),rect.top(),rect.bottom(),
                max(0,int(round(self._view_box.width()))),
                max(0,int(round(self._view_box.height()))),
                bool(self._view_box.state.get("xInverted",False)),
                self._series[4] if self._series else None)

    def _cancel(self):
        self._generation += 1
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
        data, x_start, x_scale, provenance, digest = self._series
        try:
            plan = prepare_live_source_bitmap(
                data,view_x=(signature[0],signature[1]),
                view_y=(signature[2],signature[3]),
                width=signature[4],height=signature[5],
                x_inverted=signature[6],
                x_start=x_start,x_scale=x_scale,
                provenance=provenance,expected_series_sha256=digest)
            self._task = LiveSourceBitmapTask(plan)
            self._task_signature = signature
        except (ValueError,TypeError,KeyError,OverflowError,MemoryError) as ex:
            self.source_composite_last_error=str(ex)
            self._task = None
            self._task_signature = None
            self._image = None
            self.setVisible(False)
            return False
        self._render_slice()
        return True

    def _render_slice(self):
        task = self._task
        if task is None:
            return
        if self._task_signature != self._signature():
            self._cancel()
            return
        try:
            complete = task.step(max_segments=128)
        except (ValueError,TypeError,OverflowError,MemoryError) as ex:
            self.source_composite_last_error=str(ex)
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
        arr = result["rgba"]
        w,h=result["logical_size"]
        # Source row zero is screen TOP. Qt ViewBox +Y upward requires
        # reversing rows; source reverse-X additionally requires columns.
        if signature[6]:
            display = np.ascontiguousarray(arr[::-1, ::-1])
        else:
            display = np.ascontiguousarray(arr[::-1])
        qimage = QImage(display.data,w,h,display.strides[0],
                        QImage.Format_RGBA8888).copy()
        qimage.setDevicePixelRatio(1.0)
        if qimage.isNull():
            self.source_composite_last_error="Invalid source Qt QImage"
            self.setVisible(False)
            return False
        self._image = qimage
        self._completed_signature = signature
        self.source_composite_receipt = {
            k:v for k,v in result.items() if k!="rgba"}
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
            data,x_start,x_scale,provenance,digest=self._series
            try:
                task=LiveSourceBitmapTask(prepare_live_source_bitmap(
                    data,view_x=(signature[0],signature[1]),
                    view_y=(signature[2],signature[3]),
                    width=signature[4],height=signature[5],
                    x_inverted=signature[6],x_start=x_start,x_scale=x_scale,
                    provenance=provenance,expected_series_sha256=digest))
            except (TypeError,ValueError,OverflowError,MemoryError) as ex:
                self.source_composite_last_error=str(ex)
                return False
        try:
            result=task.finish(max_segments=256)
        except (ValueError,TypeError,OverflowError,MemoryError) as ex:
            self.source_composite_last_error=str(ex)
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
