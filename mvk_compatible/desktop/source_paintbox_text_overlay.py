"""Visible full-PaintBox source TextOut on ordinary PageAdc/PageSpectrum.

The baseline CG grid+series+frame QImage lives in the actual Qt ViewBox.
This transparent QWidget covers the full PlotWidget viewport and draws
the *source-derived PaintBox margin glyphs* at their original positions:
native Win32 GetTextExtentPoint32W/TextOutW (Tahoma -13) on Windows,
explicitly labelled Qt candidate elsewhere.

No double labels: normal pyqtgraph tick values/captions are hidden only
after a successful, fully prepared PaintBox label image. An invalid
source window, old research reference or cancelled image restores them.

The marginal TextOut plane is NOT YET the same physical GDI TBitmap as
the CG source software series; original 1:1 GDI/Win32 parity is open.
"""
from __future__ import annotations

from hashlib import sha256
import sys

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPainter, QFontMetrics
from PySide6.QtWidgets import QWidget

from ..core.original_live_paintbox_text import (
    source_live_paintbox_text_plan,
)
from .tqgrapher_textout_qt_candidate import (
    qt_source_font_candidate, qt_textout_source_positions_rgba,
)
from .win32_gdi_source_candidate import (
    Win32SourceTextCanvas, native_gdi_supported,
)


def source_paintbox_font_metrics():
    """Source DFM font metrics from Windows GDI, Qt fallback elsewhere."""
    if native_gdi_supported():
        with Win32SourceTextCanvas(
                font_face="Tahoma",font_height=-13) as dc:
            d=dc.diagnostics()
            return {
                "zero":d["gdi_width_zero"],
                "six":d["gdi_width_sixdecimals"],
                "height":d["gdi_height_zero"],
                "font_metrics_provenance":"gdi_reconstructed_from_dfm",
                "requested_font_height":-13,
                "source_native_original_font_verified":False,
            }
    fm=QFontMetrics(qt_source_font_candidate())
    return {
        "zero":fm.horizontalAdvance("0"),
        "six":fm.horizontalAdvance("0.000000"),
        "height":fm.height(),
        "font_metrics_provenance":"qt_approximation",
        "requested_font_height":-13,
        "source_native_original_font_verified":False,
    }


class SourcePaintBoxTextOverlay(QWidget):
    """Transparent mouse-pass-through, bounded source PaintBox text plane."""
    def __init__(self, plot):
        super().__init__(plot.viewport())
        self.plot=plot
        self.source_textout_receipt=None
        self.source_textout_image=None
        self.source_textout_last_error=None
        self._enabled=False
        self._signature_last=None
        self._timer=QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.render_source_text_now)
        self.setAttribute(Qt.WA_TransparentForMouseEvents,True)
        self.setAttribute(Qt.WA_TranslucentBackground,True)
        self.setAttribute(Qt.WA_NoSystemBackground,True)
        self.setGeometry(plot.viewport().rect())
        self.hide()
        self.raise_()

    def _axes(self):
        item=self.plot.getPlotItem()
        return item.getAxis("bottom"),item.getAxis("left")

    def _restore_axes(self):
        for axis in self._axes():
            axis.setStyle(showValues=True)
            if axis.labelText:
                axis.label.show()
            else:
                axis.label.hide()

    def _hide_axes(self):
        for axis in self._axes():
            axis.setStyle(showValues=False)
            axis.label.hide()

    def set_source_enabled(self,enable):
        enable=bool(enable)
        if not enable:
            self._enabled=False
            self._timer.stop()
            self._signature_last=None
            self.source_textout_receipt=None
            self.source_textout_image=None
            self.hide()
            self._restore_axes()
            return
        self._enabled=True
        self.schedule_source_text()

    def schedule_source_text(self,*_):
        if not self._enabled:
            return
        rect=self.plot.viewport().rect()
        if self.geometry()!=rect:
            self.setGeometry(rect)
        self._timer.start(50)

    def _signature(self):
        vb=self.plot.getViewBox()
        xr,yr=vb.viewRange()
        xaxis,yaxis=self._axes()
        return (
            self.plot.viewport().width(),self.plot.viewport().height(),
            float(xr[0]),float(xr[1]),
            float(yr[0]),float(yr[1]),
            bool(vb.state.get("xInverted",False)),
            xaxis.labelText,yaxis.labelText,
        )

    def render_source_text_now(self):
        """Explicit synchronous QA path; normal UI uses debounced update."""
        self._timer.stop()
        if not self._enabled:
            return False
        signature=self._signature()
        if (signature==self._signature_last and
                self.source_textout_image is not None):
            return True
        w,h,x0,x1,y0,y1,invert,xname,yname=signature
        if not (64<=w<=4096 and 64<=h<=4096 and w*h<=3_000_000):
            self._render_fail("Invalid source PaintBox logical pixel size")
            return False
        # Original TCanvas.TextOut is drawn into an opaque white
        # 32bpp memory bitmap first. Convert its black/gray glyphs
        # into alpha on this OVERLAY, leaving the Qt ViewBox/cursor
        # unmodified. This is not the original *one* final bitmap yet.
        white=np.full((h,w,4),255,dtype=np.uint8)
        try:
            if native_gdi_supported():
                with Win32SourceTextCanvas(
                        font_face="Tahoma",font_height=-13) as dc:
                    d=dc.diagnostics()
                    plan=source_live_paintbox_text_plan(
                        width=w,height=h,view_x=(x0,x1),view_y=(y0,y1),
                        x_inverted=invert,x_name=xname,y_name=yname,
                        zero_text_width=d["gdi_width_zero"],
                        six_decimals_text_width=d["gdi_width_sixdecimals"],
                        zero_text_height=d["gdi_height_zero"],
                        text_width=dc.text_width,text_height=dc.text_height,
                        font_provenance="gdi_reconstructed_from_dfm")
                    raw=dc.draw_text(white,plan["events"])
                    backend="WIN32_GDI_DFM_TEXT_OUT"
                    font_report=d
            else:
                font=qt_source_font_candidate()
                fm=QFontMetrics(font)
                plan=source_live_paintbox_text_plan(
                    width=w,height=h,view_x=(x0,x1),view_y=(y0,y1),
                    x_inverted=invert,x_name=xname,y_name=yname,
                    zero_text_width=fm.horizontalAdvance("0"),
                    six_decimals_text_width=fm.horizontalAdvance("0.000000"),
                    zero_text_height=fm.height(),
                    text_width=fm.horizontalAdvance,text_height=lambda _:fm.height(),
                    font_provenance="qt_approximation")
                raw=qt_textout_source_positions_rgba(
                    white,plan["events"],font=font)
                backend="QT_GLYPHS_NOT_GDI"
                font_report=None
            # Only glyph pixels in AXIS MARGINS are painted. The data
            # rect and original XOR cursor remain visible underneath.
            rgba=np.zeros((h,w,4),dtype=np.uint8)
            alpha=255-np.min(raw[:,:,:3],axis=2)
            canvas=plan["canvas"]
            alpha[canvas["pixel_top"]:canvas["pixel_bottom"],
                  canvas["pixel_left"]:canvas["pixel_right"]]=0
            rgba[:,:,3]=alpha
            image=QImage(rgba.data,w,h,rgba.strides[0],
                         QImage.Format_RGBA8888).copy()
            image.setDevicePixelRatio(1.0)
            if image.isNull():
                raise ValueError("Invalid source GDI text RGBA image")
        except (ValueError,TypeError,RuntimeError,OSError,OverflowError,
                MemoryError) as exc:
            self._render_fail(str(exc))
            return False
        self.source_textout_image=image
        self._signature_last=signature
        self.source_textout_last_error=None
        self.source_textout_receipt={
            "source":plan["source"],
            "axis_event_count":len(plan["events"]),
            "axis_event_kinds":tuple(
                sorted({e["kind"] for e in plan["events"]})),
            "textout_engine":backend,
            "native_gdi_metrics":font_report,
            "font_metrics_provenance":plan["font_metrics_provenance"],
            "source_dfm_font_family":"Tahoma",
            "source_dfm_font_height":-13,
            "source_dfm_design_ppi":96,
            "source_paintbox_canvas":canvas,
            "source_textout_placements":plan["textout"],
            "axis_glyph_sha256":sha256(rgba.tobytes()).hexdigest(),
            "source_inverted_x":invert,
            "native_original_font_verified":False,
            "original_gdi_pixel_parity_verified":False,
            "original_whole_tcanvas_bitmap_implemented":False,
            "original_delphi_text_formatfloat_parity_verified":False,
            "qt_logical_pixels":True,
        }
        self._hide_axes()
        self.setGeometry(self.plot.viewport().rect())
        self.show()
        self.raise_()
        self.update()
        return True

    def _render_fail(self,error):
        self.source_textout_last_error=error
        self.source_textout_receipt=None
        self.source_textout_image=None
        self._signature_last=None
        self.hide()
        self._restore_axes()

    def paintEvent(self,event):
        if not self._enabled or self.source_textout_image is None:
            return
        painter=QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing,False)
            painter.setRenderHint(QPainter.SmoothPixmapTransform,False)
            painter.drawImage(0,0,self.source_textout_image)
        finally:
            painter.end()
