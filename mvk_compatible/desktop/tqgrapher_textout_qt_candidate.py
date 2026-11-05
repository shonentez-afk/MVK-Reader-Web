"""Stage111Z31J: Qt *approximation* of original TCanvas.TextOut glyph pixels.

The coordinates come from source-verified Unit115 placement rules.
QFontMetrics != Windows GDI TextWidth/Height, and Qt glyph bitmaps are
NOT Delphi TCanvas glyphs. Research-only, never a parity acceptance.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QImage, QPainter, QColor

SOURCE="QT_RESEARCH_TQGRAPHER_TEXTOUT_GLYPH_CANDIDATE_STAGE111Z31J"


def qt_textout_source_positions_rgba(rgba,events,*,font):
    """Return NEW opaque RGB(A) array. In-place writes are forbidden."""
    if (not isinstance(rgba,np.ndarray) or rgba.dtype!=np.uint8 or
            rgba.ndim!=3 or rgba.shape[2]!=4 or
            min(rgba.shape[:2])<4 or rgba.shape[0]*rgba.shape[1]>6_000_000
            or not bool(np.all(rgba[:,:,3]==255))):
        raise ValueError("opaque bounded RGBA ndarray required")
    if not isinstance(font,QFont):
        raise ValueError("a measured QFont must be supplied explicitly")
    if not isinstance(events,(list,tuple)) or len(events)>2048:
        raise ValueError("bounded original TextOut events required")
    for ev in events:
        if (not isinstance(ev,dict) or
                ev.get("kind") not in ("x_tick","y_tick","x_name","y_name") or
                not isinstance(ev.get("text"),str) or len(ev["text"])>256 or
                type(ev.get("x")) is not int or type(ev.get("y")) is not int):
            raise ValueError("invalid source TextOut event")
    h,w=rgba.shape[:2]
    safe=np.ascontiguousarray(rgba).copy()
    # Format_RGBA8888 is channel-exact to numpy RGBA, unlike ARGB32
    # with native platform endianness.
    image=QImage(safe.data,w,h,safe.strides[0],QImage.Format_RGBA8888).copy()
    image.setDevicePixelRatio(1.0)
    painter=QPainter(image)
    try:
        painter.setFont(font)
        painter.setPen(QColor(0,0,0))
        painter.setBackgroundMode(Qt.TransparentMode)
        painter.setRenderHint(QPainter.TextAntialiasing,False)
        painter.setRenderHint(QPainter.Antialiasing,False)
        # Original GDI TextOut(top-left) vs Qt drawText(baseline): only a
        # position candidate. QFontMetrics ascent is not native GDI ascent.
        ascent=int(painter.fontMetrics().ascent())
        for e in events:
            painter.drawText(e["x"],e["y"]+ascent,e["text"])
    finally:
        painter.end()
    out=np.frombuffer(image.bits(),dtype=np.uint8)
    if out.size!=h*w*4:
        raise ValueError("unexpected QImage RGBA byte size")
    return out.reshape((h,w,4)).copy()


def qt_source_font_candidate():
    """The DFM has Tahoma height -13 at PPI96, runtime font NOT measured."""
    font=QFont("Tahoma")
    font.setPixelSize(13)
    return font
