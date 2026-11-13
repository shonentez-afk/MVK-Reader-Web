"""Adapter: current live Qt PlotWidget -> ONE source PaintBox bitmap.

Uses the accepted Stage111Z31M Win32 TextOut memory DIB and Stage111Z31J
Qt fallback. All geometry, Float32 pixels, axis events and data SHA live
in Core. This module owns the platform font/DC *only* during TextOut.

This is not the original process or a certified Win32 GDI screenshot.
"""
from __future__ import annotations

from PySide6.QtGui import QFontMetrics

from ..core.original_live_paintbox_text import (
    source_live_paintbox_text_plan,
)
from ..core.original_live_whole_paintbox import (
    prepare_whole_paintbox_plan, WholePaintboxTask,
)
from .win32_gdi_source_candidate import (
    Win32SourceTextCanvas, native_gdi_supported,
)
from .tqgrapher_textout_qt_candidate import (
    qt_source_font_candidate,qt_textout_source_positions_rgba,
)


def prepare_qt_source_whole_paintbox_task(
        plot, values, *, signature, x_start, x_scale,
        provenance, expected_series_sha256):
    """Bound view, measured source margins and one RGB source renderer.

    The paintbox and viewbox are in Qt logical pixels; do not multiply
    by Windows DPR=1.5. Fail closed if their plot rectangles disagree.
    """
    if plot is None or not hasattr(plot,"source_canvas_model"):
        raise ValueError("Actual source PageAdc/PageSpectrum plot required")
    if (not isinstance(signature,tuple) or len(signature)!=10):
        raise ValueError("Complete source Qt view signature required")
    w,h=int(plot.viewport().width()),int(plot.viewport().height())
    xmin,xmax,ymin,ymax=signature[0:4]
    inverse=signature[6]
    bottom=plot.getPlotItem().getAxis("bottom").labelText or ""
    left=plot.getPlotItem().getAxis("left").labelText or ""
    if native_gdi_supported():
        with Win32SourceTextCanvas(
                font_face="Tahoma",font_height=-13) as dc:
            metrics=dc.diagnostics()
            text=source_live_paintbox_text_plan(
                width=w,height=h,view_x=(xmin,xmax),view_y=(ymin,ymax),
                x_inverted=inverse,x_name=bottom,y_name=left,
                zero_text_width=metrics["gdi_width_zero"],
                six_decimals_text_width=metrics["gdi_width_sixdecimals"],
                zero_text_height=metrics["gdi_height_zero"],
                text_width=dc.text_width,text_height=dc.text_height,
                font_provenance="gdi_reconstructed_from_dfm")
        def draw_text(rgb,events):
            with Win32SourceTextCanvas(
                    font_face="Tahoma",font_height=-13) as dc:
                return dc.draw_text(rgb,events)
    else:
        font=qt_source_font_candidate()
        fm=QFontMetrics(font)
        text=source_live_paintbox_text_plan(
            width=w,height=h,view_x=(xmin,xmax),view_y=(ymin,ymax),
            x_inverted=inverse,x_name=bottom,y_name=left,
            zero_text_width=fm.horizontalAdvance("0"),
            six_decimals_text_width=fm.horizontalAdvance("0.000000"),
            zero_text_height=fm.height(),
            text_width=fm.horizontalAdvance,text_height=lambda _:fm.height(),
            font_provenance="qt_approximation")
        def draw_text(rgb,events):
            return qt_textout_source_positions_rgba(
                rgb,events,font=font)
    # Layout and series must use the same source-derived PixelRect,
    # rather than the old CG 1px inset. If this Qt widget is not yet
    # laid out at the source size, DO NOT claim a source bitmap.
    registered=plot.source_canvas_model
    if registered is None:
        raise ValueError("Source plot geometry has not settled")
    for key in ("pixel_left","pixel_right","pixel_top","pixel_bottom"):
        if abs(int(registered[key])-int(text["canvas"][key])) > 2:
            raise ValueError("Qt view source font/PixelRect disagree: "+key)
    plan=prepare_whole_paintbox_plan(
        values,source_text_plan=text,x_start=x_start,x_scale=x_scale,
        provenance=provenance,
        expected_series_sha256=expected_series_sha256)
    return WholePaintboxTask(plan,draw_text)
