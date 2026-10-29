"""Stage111K — source-derived TQGrapher canvas geometry.

Derived from private original _Unit115.pas, TQGrapher 007CA4C8..007CA70D
and 007CABE4 / 007CAB94.  No original Delphi source/IDP is embedded.

This calculates exact *structural* expressions after text metrics have
been supplied.  Font metrics from a Qt widget are NOT original Delphi
TCanvas measurements, so original_pixel_rectangle_verified stays False.

The source uses x87 fild/fld arithmetic and stores each coefficient as
Single (float32). Numerical bit parity is not certified.
"""
from __future__ import annotations

import math
import numbers
import numpy as np

from .tqgrapher_cursor_candidate import CursorGeometry

SOURCE='APP_DERIVED_TQGRAPHER_CANVAS_GEOMETRY_IDR_CANDIDATE'


def source_canvas_geometry(*, pixel_width:int, pixel_height:int,
                           margin:int, zero_text_width:int,
                           six_decimals_text_width:int, zero_text_height:int,
                           x_name_present:bool=True, y_name_present:bool=True,
                           scr_left:float=0.,scr_width:float=1.,
                           scr_bottom:float=0.,scr_height:float=1.,
                           series_x_start:float=0.,series_x_scale:float=1.) -> dict:
    """Compute source pixel rectangle and independent Single transforms.

    See 007CA593..007CA62F for pixel rectangle, 007CA62F..007CA6C9
    for X itosM/C and stoiM/C; 007CA6CA..007CA6FE for Y conversion.
    No OpenGL, coordinates or physical sampling data are accessed.
    """
    ints=(pixel_width,pixel_height,margin,zero_text_width,
          six_decimals_text_width,zero_text_height)
    if any(not isinstance(n,numbers.Integral) or isinstance(n,bool) for n in ints):
        raise ValueError('Canvas dimensions and font metrics must be integers')
    if (pixel_width<=0 or pixel_height<=0 or margin<0
        or zero_text_width<0 or six_decimals_text_width<0 or zero_text_height<=0):
        raise ValueError('Invalid original TCanvas dimensions')
    if not isinstance(x_name_present,bool) or not isinstance(y_name_present,bool):
        raise ValueError('Axis-name presence must be explicit boolean')
    floats=(scr_left,scr_width,scr_bottom,scr_height,
            series_x_start,series_x_scale)
    if any(not math.isfinite(float(x)) for x in floats):
        raise ValueError('Original screen and series coordinates must be finite')
    # TQGrapher stores all Scr/Series coordinates as Delphi Single.
    # _Unit115:007CA4F7..007CA571 explicitly accepts REVERSED ScrWidth:
    # tiny positive/zero -> +1e-6; tiny negative -> -1e-6.
    # ScrHeight <= +1e-6 -> +1e-6; Series.XScale <= 0 -> +1.
    # These are mutations of the original object BEFORE computing itos/stoi.
    with np.errstate(over='ignore',invalid='ignore'):
        scr_left,scr_width,scr_bottom,scr_height,series_x_start,series_x_scale=(
            float(np.float32(v)) for v in floats)
    if not all(math.isfinite(v) for v in (
        scr_left,scr_width,scr_bottom,scr_height,series_x_start,series_x_scale)):
        raise ValueError('Original Single coordinate input overflow')
    min_span=float(np.float32(1e-6))
    original_scr_width=scr_width
    original_scr_height=scr_height
    original_series_x_scale=series_x_scale
    scr_width_clamped=abs(scr_width)<min_span
    scr_height_clamped=scr_height<min_span
    series_x_scale_clamped=series_x_scale<=0.
    if scr_width_clamped:
        scr_width=(-min_span if scr_width<0. else min_span)
    if scr_height_clamped:
        scr_height=min_span
    if series_x_scale_clamped:
        series_x_scale=1.

    # Source clamps Margin to 10 and canvas width/height to 3*Margin.
    margin=max(10,int(margin))
    canvas_width=max(int(pixel_width),3*margin)
    canvas_height=max(int(pixel_height),3*margin)
    left=margin+zero_text_width+six_decimals_text_width
    right=canvas_width-margin
    top=margin
    bottom=canvas_height-margin-zero_text_height-zero_text_width
    if x_name_present or y_name_present:
        bottom-=zero_text_height+zero_text_width

    x_fallback=right<left
    y_fallback=bottom<top
    if x_fallback:left=margin
    if y_fallback:bottom=canvas_height-margin
    dx=right-left
    dy=bottom-top
    if dx<=0 or dy<=0:
        raise ValueError('Degenerate TQGrapher drawable rectangle')
    # Original x87 extended operations write each resulting coefficient as
    # Single only at these four final store sites.
    itos_m=float(np.float32(dx*series_x_scale/scr_width))
    itos_c=float(np.float32(left+(series_x_start-scr_left)*dx/scr_width))
    stoi_m=float(np.float32((scr_width/dx)/series_x_scale))
    stoi_c=float(np.float32((scr_left-series_x_start)/series_x_scale))
    ytos_m=float(np.float32(-dy/scr_height))
    ytos_c=float(np.float32(bottom+dy*scr_bottom/scr_height))
    if not all(math.isfinite(x) for x in
               (itos_m,itos_c,stoi_m,stoi_c,ytos_m,ytos_c)):
        raise ValueError('Original transform not representable as Single')
    if itos_m==0 or stoi_m==0:
        raise ValueError('Unrepresentable zero original X coordinate transform')

    return {
        'source':SOURCE,
        'canvas_width':canvas_width,'canvas_height':canvas_height,
        'margin':margin,'pixel_left':left,'pixel_right':right,
        'pixel_top':top,'pixel_bottom':bottom,
        'pixel_plot_width':dx,'pixel_plot_height':dy,
        'x_fallback_to_margin':x_fallback,'y_fallback_to_margin':y_fallback,
        'x_name_present':x_name_present,'y_name_present':y_name_present,
        'scr_left':scr_left,'scr_width':scr_width,
        'scr_bottom':scr_bottom,'scr_height':scr_height,
        'series_x_start':series_x_start,'series_x_scale':series_x_scale,
        'screen_x_reversed':scr_width<0.,
        'scr_width_source_clamped':scr_width_clamped,
        'scr_height_source_clamped':scr_height_clamped,
        'series_x_scale_source_clamped':series_x_scale_clamped,
        'source_single_inputs':True,
        'itos_m':itos_m,'itos_c':itos_c,
        'stoi_m':stoi_m,'stoi_c':stoi_c,
        'ytos_m':ytos_m,'ytos_c':ytos_c,
        'original_source_formula_verified':True,
        'original_pixel_rectangle_verified':False,
        'original_canvas_font_metrics_verified':False,
        'original_x87_numeric_parity_verified':False,
    }


def cursor_geometry_from_canvas(canvas:dict, *, y_scale:float=1.) -> CursorGeometry:
    """Transfer the *actual* original pixel offsets to cursor selector.

    Pixel inputs must be in Canvas absolute coordinates; for Qt plot-local
    events these are NOT interchangeable and require measured registration.
    """
    if canvas.get('source')!=SOURCE:
        raise ValueError('A source-derived original TQGrapher canvas is required')
    geom=CursorGeometry(
        float(canvas['pixel_left']),float(canvas['pixel_right']),
        float(canvas['stoi_m']),float(canvas['stoi_c']),
        float(canvas['series_x_start']),float(canvas['series_x_scale']),
        y_scale=float(y_scale),
        itos_m=float(canvas['itos_m']),itos_c=float(canvas['itos_c']))
    geom.validate()
    return geom
