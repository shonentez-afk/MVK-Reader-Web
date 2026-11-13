"""Visible TQGrapher grid/late plot frame on BOTH normal Qt pages.

The grid uses the actual audited TCo2Draw software scanline raster in
an opaque Qt-logical ViewBox image, under both independently computed
sample curves. The original Delphi TCanvas draws TextOut on the FULL
PaintBox; Qt axis labels and the separate frame are explicitly candidates.
Never claim original GDI text, physical DPI or screenshot pixel parity.
"""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QImage

from ..core.original_live_grid_cursor import source_live_grid_frame
from ..core.original_live_software_grid import (
    source_live_software_grid_bitmap,
)


class SourceLiveGridOverlay(pg.GraphicsObject):
    """Software TCo2Draw paint on the real Qt ViewBox, below the data."""

    def __init__(self, view_box):
        super().__init__()
        self._view_box = view_box
        self._rect = QRectF(view_box.viewRect())
        self.source_grid_model = None
        self.source_software_raster_receipt = None
        self.source_software_rgba = None
        self._image = None
        self._image_signature = None
        self._requested_signature = None
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self.render_source_grid_bitmap_now)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setZValue(-100000)
        view_box.sigRangeChanged.connect(self.sync_source_grid)
        view_box.sigResized.connect(self.sync_source_grid)
        self.sync_source_grid()

    def _signature(self):
        rect = self._rect
        return (rect.left(),rect.right(),rect.top(),rect.bottom(),
                int(round(self._view_box.width())),
                int(round(self._view_box.height())))

    def sync_source_grid(self, *_):
        rect = QRectF(self._view_box.viewRect())
        if rect != self._rect:
            self.prepareGeometryChange()
            self._rect = rect
        try:
            model = source_live_grid_frame(
                view_x=(rect.left(), rect.right()),
                view_y=(rect.top(), rect.bottom()))
        except (ValueError, TypeError, OverflowError):
            model = None
        self.source_grid_model = model
        signature = self._signature()
        if signature != self._requested_signature:
            # Never paint a raster belonging to an old zoom/pan/resize.
            self._requested_signature = signature
            self._image = None
            self._image_signature = None
            self.source_software_rgba = None
            self.source_software_raster_receipt = None
        if model is not None and self.isVisible():
            self._render_timer.start(0)
        self.update()

    def render_source_grid_bitmap_now(self):
        """Create only the latest requested offscreen source grid.

        Qt mouse/pan events may arrive faster than a software scanline
        render: QTimer collapses them, avoiding stale-viewport painting.
        """
        self._render_timer.stop()
        if (self.source_grid_model is None or not self.isVisible() or
                not self._view_box.isVisible()):
            return False
        signature = self._signature()
        if self._image is not None and signature == self._image_signature:
            return True
        w,h = signature[-2:]
        try:
            result = source_live_software_grid_bitmap(
                view_x=(signature[0],signature[1]),
                view_y=(signature[2],signature[3]),
                width=w,height=h)
        except (TypeError, ValueError, OverflowError, MemoryError):
            # Large/transient viewports retain the earlier safe Qt
            # stroke fallback; never display unrelated stale pixels.
            self._image = None
            self._image_signature = signature
            self.source_software_rgba = None
            self.source_software_raster_receipt = None
            self.update()
            return False
        arr = result["rgba"]
        # Source ndarray row zero is screen TOP. Qt ViewBox graph +Y
        # increases upward, so reverse rows when painting as QImage.
        flipped = np.ascontiguousarray(arr[::-1])
        image = QImage(flipped.data, w,h,flipped.strides[0],
                       QImage.Format_RGBA8888).copy()
        image.setDevicePixelRatio(1.0)
        if image.isNull():
            raise ValueError("Qt could not take a bounded source RGB snapshot")
        self.source_software_rgba = arr
        self.source_software_rgba.setflags(write=False)
        self.source_software_raster_receipt = {
            k:v for k,v in result.items() if k != "rgba"}
        self._image=image
        self._image_signature=signature
        self.update()
        return True

    def boundingRect(self):
        return QRectF(self._rect)

    def paint(self, painter, option, widget=None):
        if self.source_grid_model is None or not self.isVisible():
            return
        rect = self._rect
        painter.save()
        try:
            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
            painter.setClipRect(rect, Qt.IntersectClip)
            if (self._image is not None and
                    self._image_signature == self._signature()):
                painter.drawImage(rect,self._image)
                return
            # During the deferred raster pass, keep already accepted
            # source 10x10 tick geometry, but never an old bitmap.
            pen = QPen(QColor(self.source_grid_model["source_grid_hex"]))
            pen.setWidth(0)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for x in self.source_grid_model["x_ticks"]:
                painter.drawLine(QPointF(x, rect.top()),
                                 QPointF(x, rect.bottom()))
            for y in self.source_grid_model["y_ticks"]:
                painter.drawLine(QPointF(rect.left(), y),
                                 QPointF(rect.right(), y))
        finally:
            painter.restore()


class SourceLiveFrameOverlay(pg.GraphicsObject):
    """Source TQGrapher frame paint order AFTER series, BEFORE XOR cursor.

    The original 007CB3FF frame uses TCo2Draw scanlines on a full bitmap;
    this live QWidget-free overlay draws a restrained Qt cosmetic candidate.
    """

    def __init__(self, view_box):
        super().__init__()
        self._view_box=view_box
        self._rect=QRectF(view_box.viewRect())
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setZValue(500000)
        view_box.sigRangeChanged.connect(self.sync_source_frame)
        view_box.sigResized.connect(self.sync_source_frame)

    def sync_source_frame(self,*_):
        r=QRectF(self._view_box.viewRect())
        if r != self._rect:
            self.prepareGeometryChange()
            self._rect=r
            self.update()

    def boundingRect(self):
        return QRectF(self._rect)

    def paint(self,painter,option,widget=None):
        if not self.isVisible():
            return
        painter.save()
        try:
            painter.setRenderHint(QPainter.Antialiasing,False)
            painter.setClipRect(self._rect,Qt.IntersectClip)
            pen=QPen(QColor(0,0,0))
            pen.setWidth(0)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self._rect)
        finally:
            painter.restore()
