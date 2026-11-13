"""Source-derived live 10x10 raster preview in BOTH real Qt plots.

A single low-z QGraphicsObject renders #c0c0c0 lines before the series,
bounded by the actual Qt ViewBox. Qt cosmetic pixels are NOT the original
TCo2Draw software blended bitmap; the separate research bitmap remains
available for source-pixel studies.
"""
from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPen

from ..core.original_live_grid_cursor import source_live_grid_frame


class SourceLiveGridOverlay(pg.GraphicsObject):
    def __init__(self, view_box):
        super().__init__()
        self._view_box = view_box
        self._rect = QRectF(view_box.viewRect())
        self.source_grid_model = None
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setZValue(-100000)
        view_box.sigRangeChanged.connect(self.sync_source_grid)
        view_box.sigResized.connect(self.sync_source_grid)
        self.sync_source_grid()

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
        if self.source_grid_model != model:
            self.source_grid_model = model
            self.update()
        else:
            self.update()

    def boundingRect(self):
        return QRectF(self._rect)

    def paint(self, painter, option, widget=None):
        model = self.source_grid_model
        if model is None or not self.isVisible():
            return
        rect = self._rect
        painter.save()
        try:
            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.setClipRect(rect, Qt.IntersectClip)
            pen = QPen(QColor(model["source_grid_hex"]))
            pen.setWidth(0)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for x in model["x_ticks"]:
                painter.drawLine(QPointF(x, rect.top()),
                                 QPointF(x, rect.bottom()))
            for y in model["y_ticks"]:
                painter.drawLine(QPointF(rect.left(), y),
                                 QPointF(rect.right(), y))
        finally:
            painter.restore()
