"""Stage111Z31J: source TCanvas.TextOut axis placement (NO GDI font claims).

Recovered formulas only from operator-private _Unit115:
 Y tick 007CADD7..007CAE29, X tick 007CAF09..007CAF5F,
 YName 007CB095..007CB0CF, XName 007CB0E4..007CB129.
 Original single-precision maps 007CAB44/007CAC18. The exact
 original font, physical Canvas, DPI, RTL float ties and GDI glyphs
 remain UNVERIFIED. No original private code/data is included.
"""
from __future__ import annotations
import math
import numbers
import numpy as np

SOURCE="APP_DERIVED_TQGRAPHER_CANVAS_TEXTOUT_PLACEMENTS_STAGE111Z31J"
MAX_LABELS=2048
MAX_GLYPHS=256

def _int(value, name, *, min_value=0,max_value=16384):
    if isinstance(value,bool) or not isinstance(value,numbers.Integral):
        raise ValueError(name+" must be a genuine integer")
    n=int(value)
    if not min_value<=n<=max_value:
        raise ValueError(name+" outside bounded text metrics")
    return n

def _safe_width(callback, text):
    return _int(callback(text),"TextWidth("+repr(text[:24])+")")

def _safe_height(callback, text):
    return _int(callback(text),"TextHeight("+repr(text[:24])+")",min_value=1)

def _text(s,name):
    if not isinstance(s,str) or len(s)>MAX_GLYPHS or "\x00" in s:
        raise ValueError(name+" needs bounded Unicode text")
    return s

def _single(v):
    f=float(v)
    if not math.isfinite(f):
        raise ValueError("nonfinite source transform")
    f=float(np.float32(f))
    if not math.isfinite(f):
        raise ValueError("original Single overflow")
    return f

def _round(v):
    # Python's round nearest/even matches source @ROUND for ordinary
    # finite x87 values; exceptional ties/control-word not attested.
    return int(round(float(v)))

def _clamp(v, lo, hi):
    return max(lo,min(hi,v))

def source_textout_layout(
        *,canvas,grid,text_width,text_height,
        x_name="",y_name="",font_provenance="qt_approximation"):
    """Calculate original TextOut top-left positions on a TBitmap.

    Coordinates are *local paintbox pixels*, +Y downward. Text widths
    and heights must come from the same font/canvas as caller's bitmap.
    Passing Qt QFontMetrics is only an explicit approximate research
    preview, NOT native Windows TCanvas/FontMetrics equivalence.
    """
    if not callable(text_width) or not callable(text_height):
        raise ValueError("TextWidth/TextHeight callbacks required")
    if font_provenance not in ("qt_approximation","unverified_native_capture"):
        raise ValueError("font metric provenance must remain explicit")
    x_name=_text(x_name,"x_name")
    y_name=_text(y_name,"y_name")
    for name in ("pixel_left","pixel_right","pixel_top","pixel_bottom",
                 "canvas_width","canvas_height","margin",
                 "scr_left","scr_width","scr_bottom","scr_height",
                 "ytos_m","ytos_c"):
        if name not in canvas:
            raise ValueError("source canvas missing "+name)
    left,right=(_int(canvas[n],n) for n in ("pixel_left","pixel_right"))
    top,bottom=(_int(canvas[n],n) for n in ("pixel_top","pixel_bottom"))
    width,height=(_int(canvas[n],n,min_value=1) for n in ("canvas_width","canvas_height"))
    margin=_int(canvas["margin"],"margin")
    if not (0<=left<right<=width and 0<=top<bottom<=height):
        raise ValueError("invalid original source PixelRect")
    xvals=tuple(grid["x_grid_ticks"])
    yvals=tuple(grid["y_grid_ticks"])
    xlabels=tuple(grid["x_tick_labels_candidate"])
    ylabels=tuple(grid["y_tick_labels_candidate"])
    if (len(xvals)!=len(xlabels) or len(yvals)!=len(ylabels)
            or len(xvals)+len(yvals)>MAX_LABELS):
        raise ValueError("source tick positions/labels mismatch")
    text_offset=_safe_width(text_width,"0")  # Source [ebx+38].
    x_fallback=bool(canvas.get("x_fallback_to_margin",False))
    y_fallback=bool(canvas.get("y_fallback_to_margin",False))
    pxw=right-left
    scr_left=_single(canvas["scr_left"])
    scr_width=_single(canvas["scr_width"])
    if scr_width==0:
        raise ValueError("zero original screen span")
    # _Unit115 007CA671..007CA6A1 stores xtosM,xtosC as Single.
    xtos_m=_single(pxw/scr_width)
    xtos_c=_single(left-scr_left*pxw/scr_width)
    ytos_m=_single(canvas["ytos_m"])
    ytos_c=_single(canvas["ytos_c"])

    def y_to_px(t):
        return _clamp(_round(_single(_single(_single(t)*ytos_m)+ytos_c)),top,bottom)
    def x_to_px(t):
        return _clamp(_round(_single(_single(_single(t)*xtos_m)+xtos_c)),left,right)

    events=[]
    if not x_fallback:
        for tick,label in zip(yvals,ylabels):
            label=_text(label,"Y tick")
            events.append(dict(kind="y_tick",text=label,source_value=_single(tick),
                x=left-_safe_width(text_width,label)-text_offset,
                y=y_to_px(tick)-text_offset,
                text_width=_safe_width(text_width,label)))
    if not y_fallback:
        for tick,label in zip(xvals,xlabels):
            label=_text(label,"X tick")
            label_w=_safe_width(text_width,label)
            # Original SAR+ADC gives width div 2 toward zero.
            events.append(dict(kind="x_tick",text=label,source_value=_single(tick),
                x=x_to_px(tick)-label_w//2,
                y=bottom+text_offset,
                text_width=label_w))
    if y_name and not x_fallback:
        events.append(dict(kind="y_name",text=y_name,
            x=left-_safe_width(text_width,y_name)-text_offset,
            y=height-margin-_safe_height(text_height,y_name),
            text_width=_safe_width(text_width,y_name)))
    if x_name and not y_fallback:
        name_w=_safe_width(text_width,x_name)
        gap=right-left-name_w
        # SAR + ADC in 007CB11B rounds negative halves toward zero.
        centered=math.trunc(gap/2)
        events.append(dict(kind="x_name",text=x_name,
            x=left+centered,
            y=height-margin-_safe_height(text_height,x_name),
            text_width=name_w))
    return {
        "source":SOURCE,
        "events":tuple(events),
        "canvas_text_offset_px":text_offset,
        "source_xtos_coefficients_single":(xtos_m,xtos_c),
        "source_ytos_coefficients_single":(ytos_m,ytos_c),
        "source_y_labels_enabled":not x_fallback,
        "source_x_labels_enabled":not y_fallback,
        "font_metrics_provenance":font_provenance,
        "font_glyph_rasterization_implemented":False,
        "original_windows_native_font_verified":False,
        "original_native_dpi_verified":False,
        "original_rtl_label_decimal_verified":False,
        "original_native_pixel_parity_verified":False,
    }
