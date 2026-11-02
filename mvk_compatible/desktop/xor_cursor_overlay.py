"""Stage111Z.20: original VCL clGreen/pmXor cursor paint candidate.

The original TQGrapher uses one-pixel clGreen GDI pmXor. A white
(255,255,255) source background becomes (255,127,255); a black spectrum
(0,0,0) becomes (0,128,0). The Qt QPainter RASTER operation is selected
explicitly; Porter-Duff 'CompositionMode_Xor' is NOT binary GDI XOR.

This graphics item does not modify source signal/FFT data, the original
BIN or selected cursor bin. Qt/GDI pixel parity is not attested until the
same data/window/DPI original-versus-Qt screenshots are compared.
"""
from __future__ import annotations

import math

import pyqtgraph as pg
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor,QPainter,QPen


SOURCE="APP_DERIVED_ORIGINAL_GDI_XOR_CLGREEN_QT_GRAPHICS_CANDIDATE"
ORIGINAL_XOR_PEN_RGB=(0,128,0)


def gdi_xor_rgb(rgb:tuple[int,int,int],
                pen:tuple[int,int,int]=ORIGINAL_XOR_PEN_RGB
                )->tuple[int,int,int]:
    """Real bitwise RGB XOR; NOT alpha-blend / Porter-Duff XOR."""
    if (len(rgb)!=3 or len(pen)!=3 or
            any(type(v) is not int or v<0 or v>255 for v in (*rgb,*pen))):
        raise ValueError("RGB XOR requires 3 unsigned 8-bit components")
    return tuple(src ^ ink for src,ink in zip(rgb,pen))


class QtSpectrumXorCursor(pg.GraphicsObject):
    """ViewBox-attached one-pixel crosshair, independent of FFT coordinates.

    XOR is drawn at the selected x frequency and RAW signed FFT y, matching
    the two source TQGrapher lines. Numeric CursorString averaging is separate.
    """

    def __init__(self,view_box):
        super().__init__()
        self._view_box=view_box
        self._rect=QRectF(self._view_box.viewRect())
        self._cursor=None
        self.setZValue(1_000_000)
        self._view_box.sigRangeChanged.connect(self._update_bounds)

    def _update_bounds(self,*_):
        rect=QRectF(self._view_box.viewRect())
        if rect!=self._rect:
            self.prepareGeometryChange()
            self._rect=rect
            self.update()

    def boundingRect(self):
        return QRectF(self._rect)

    @property
    def cursor(self):
        return self._cursor

    def set_cursor(self,x:float,y:float):
        if not math.isfinite(float(x)) or not math.isfinite(float(y)):
            raise ValueError("Non-finite XOR cursor coordinate")
        next_cursor=(float(x),float(y))
        if next_cursor!=self._cursor:
            self._cursor=next_cursor
            self.update()

    def clear_cursor(self):
        if self._cursor is not None:
            self._cursor=None
            self.update()

    def paint(self,painter,option,widget=None):
        if self._cursor is None:
            return
        x,y=self._cursor
        rect=self._rect
        if not rect.contains(QPointF(x,y)):
            return
        painter.save()
        try:
            painter.setRenderHint(QPainter.Antialiasing,False)
            # This raster operation is a per-channel BITWISE XOR with the
            # destination pixel color, as in original VCL/GDI pmXor.
            painter.setCompositionMode(QPainter.RasterOp_SourceXorDestination)
            ink=QColor(*ORIGINAL_XOR_PEN_RGB)
            pen=QPen(ink)
            pen.setWidth(0)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawLine(QPointF(x,rect.top()),QPointF(x,rect.bottom()))
            painter.drawLine(QPointF(rect.left(),y),QPointF(rect.right(),y))
        finally:
            painter.restore()
