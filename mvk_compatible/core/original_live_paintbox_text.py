"""Live source TQGrapher axis TextOut placement on the complete PaintBox.

Static source recovery:
  private _Unit115.pas 007CACE4..007CACF9 copies the caller Canvas.Font
  into TCo2Draw bitmap Canvas BEFORE any 007CAE29 / 007CAF5F TextOut.
  007CAD77..007CB129 places 10x10 source-grid axis glyphs/names.
  DFM: Tahoma, Font.Height=-13, PixelsPerInch=96.

This is a *placement* and metric contract. Real Windows GDI glyphs may
be drawn with Win32SourceTextCanvas; Qt candidates are explicitly marked.
The original runtime's font, charset, DPI-awareness, FormatFloat/x87 and
full PaintBox bitmap parity have NOT been independently captured.

No device, networking, BIN read or changed sample is involved.
"""
from __future__ import annotations

import math
import numbers

from .tqgrapher_paintbox_registration_idr_candidate import (
    source_paintbox_registration,
)
from .tqgrapher_grid_idr_candidate import source_tqgrapher_grid_candidate
from .tqgrapher_textout_source_candidate import source_textout_layout

SOURCE = "SOURCE_DERIVED_LIVE_PAINTBOX_TEXTOUT_STAGE111Z31CH"
MAX_LABEL_CANVAS_PIXELS = 3_000_000


def _check_dimension(value, name):
    if type(value) is not int or not 64 <= value <= 4096:
        raise ValueError(name + " must be a bounded PaintBox logical pixel count")
    return value


def _check_metric(value, name, minimum=1):
    if (isinstance(value,bool) or not isinstance(value,numbers.Integral)
            or not minimum <= int(value) <= 512):
        raise ValueError(name + " requires a bounded measured font metric")
    return int(value)


def _bounds(value, name):
    if not isinstance(value,(tuple,list)) or len(value)!=2:
        raise ValueError(name + " requires a view range")
    lo,hi=value
    if (any(isinstance(v,bool) or not isinstance(v,numbers.Real)
            for v in (lo,hi))):
        raise ValueError(name + " requires real bounds")
    a,b=map(float,(lo,hi))
    if not math.isfinite(a) or not math.isfinite(b) or not b>a:
        raise ValueError(name + " requires finite increasing bounds")
    return a,b


def source_live_paintbox_text_plan(*, width, height, view_x, view_y,
        x_inverted, x_name, y_name, zero_text_width,
        six_decimals_text_width, zero_text_height,
        text_width, text_height, font_provenance):
    """Source coordinates for text on a *whole* PaintBox, not ViewBox.

    The original PageAdc axis is reversed: ScrLeft=x_max and
    ScrWidth=-(x_max-x_min). The grid divides the absolute range,
    while the TextOut X coordinate follows source signed itosM/C.
    """
    w=_check_dimension(width,"PaintBox width")
    h=_check_dimension(height,"PaintBox height")
    if w*h > MAX_LABEL_CANVAS_PIXELS:
        raise ValueError("Bounded label canvas exceeds source pixel budget")
    if type(x_inverted) is not bool:
        raise ValueError("Explicit native source X inversion flag needed")
    if any(not isinstance(name,str) or "\x00" in name or len(name)>128
           for name in (x_name,y_name)):
        raise ValueError("Source axis name must be bounded Unicode")
    x0,x1=_bounds(view_x,"X view")
    y0,y1=_bounds(view_y,"Y view")
    zero=_check_metric(zero_text_width,"TextWidth('0')")
    six=_check_metric(six_decimals_text_width,"TextWidth('0.000000')")
    fontheight=_check_metric(zero_text_height,"TextHeight('0')")
    if not callable(text_width) or not callable(text_height):
        raise ValueError("Measured Canvas TextWidth/Height required")
    if font_provenance not in ("gdi_reconstructed_from_dfm",
                               "qt_approximation",
                               "unverified_native_capture"):
        raise ValueError("Font provenance must be explicit")
    source_left=x1 if x_inverted else x0
    source_width=(x0-x1) if x_inverted else (x1-x0)
    canvas=source_paintbox_registration(
        pixel_width=w,pixel_height=h,
        zero_text_width=zero,
        six_decimals_text_width=six,
        zero_text_height=fontheight,
        x_name_present=bool(x_name),
        y_name_present=bool(y_name),
        scr_left=source_left,scr_width=source_width,
        scr_bottom=y0,scr_height=y1-y0,
        series_x_start=0.,series_x_scale=1.)
    # _Unit115 VLineSpacing uses ABS(ScrWidth)/10, even when ADC
    # ScrWidth is negative; tick set itself is ascending.
    grid=source_tqgrapher_grid_candidate(
        scr_left=x0,scr_width=x1-x0,
        scr_bottom=y0,scr_height=y1-y0)
    layout=source_textout_layout(
        canvas=canvas,grid=grid,
        text_width=text_width,text_height=text_height,
        x_name=x_name,y_name=y_name,
        font_provenance=font_provenance)
    events=layout["events"]
    return {
        "source": SOURCE,
        "canvas": canvas,
        "grid": grid,
        "textout": layout,
        "events": events,
        "source_x_inverted": x_inverted,
        "source_gdi_font_height": -13,
        "source_dfm_pixels_per_inch": 96,
        "source_dfm_font_family": "Tahoma",
        "font_metrics_provenance": font_provenance,
        "source_original_textout_after_grid_before_series": True,
        "whole_paintbox_event_coordinates": True,
        "qt_viewbox_registration_verified": False,
        "original_win32_font_dpi_verified": False,
        "original_gdi_pixel_parity_verified": False,
        "original_delphi_rtl_formatfloat_verified": False,
    }
