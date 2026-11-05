"""Stage111Z31I: one offscreen 32bpp TQGrapher grid + series + frame.

Source order is from PRIVATE operator-provided _Unit115.pas:
007CACB3 (white TCo2Draw), 007CACFC (gray grid), 007CB12F
(TQGRSeries), 007CB3FF (black plot frame), 007CB4AA (Canvas.Draw).
Do not include original Delphi source, binaries or measurement captures.

Axis labels are originally GDI TextOut on the same TBitmap, between
grid and series. Their font/pixel positions are NOT yet reproduced;
Qt-labeled research preview is NOT original Windows pixel parity.
"""
from __future__ import annotations

import math
import numpy as np
from .tco2draw_grid_source import GRID_LINE_RGB, BACKGROUND_RGB
from .tco2draw_raster_candidate import source_raster_rgba, MAX_PIXELS
from .tqgrapher_grid_idr_candidate import source_tqgrapher_grid_candidate
from .tqgr_series_source_candidate import source_tqgr_series_columns
from .tqgrapher_paintbox_registration_idr_candidate import (
    source_paintbox_registration,
)

SOURCE="APP_DERIVED_TQGRAPHER_SINGLE_TCO2DRAW_BITMAP_STAGE111Z31I"
SERIES_RGB=(0,0,0)
FRAME_RGB=(0,0,0)
SEGMENT_CHUNK=1024


def source_tqgrapher_composite_contract():
    return {
        "source":SOURCE,
        "draw_order":("white_bitmap","gray_grid","canvas_textout_open",
                      "black_series","black_frame","canvas_draw"),
        "original_blank_ffffff":True,
        "original_grid_rgb":GRID_LINE_RGB,
        "original_series_rgb":SERIES_RGB,
        "original_frame_rgb":FRAME_RGB,
        "source_software_raster_shared_for_grid_series_frame":True,
        "source_original_scanline_rgb_blend":True,
        "source_canvas_font_labels_rasterized":False,
        "original_runtime_font_verified":False,
        "original_runtime_pixel_rect_verified":False,
        "original_dpi_awareness_verified":False,
        "original_x87_pixel_parity_verified":False,
    }


def _screen_segments(grid, canvas, *,scr_left,scr_width,
                     scr_bottom,scr_height):
    """Project Unit115 grid values to source-derived PaintBox PixelRect."""
    left,right=canvas['pixel_left'],canvas['pixel_right']
    top,bottom=canvas['pixel_top'],canvas['pixel_bottom']
    pw=right-left
    ph=bottom-top
    xscale=float(np.float32(pw/scr_width))
    yscale=float(np.float32(ph/scr_height))
    x0=float(np.float32(scr_left))
    y0=float(np.float32(scr_bottom))
    lines=[]
    # The original Draw emits horizontal grid first (007CAD77),
    # then vertical lines (007CAE4E), BEFORE series and frame.
    for v in grid['y_grid_ticks']:
        y=float(np.float32(bottom-(float(np.float32(v))-y0)*yscale))
        lines.append((float(left),y,float(right),y))
    for v in grid['x_grid_ticks']:
        x=float(np.float32(left+(float(np.float32(v))-x0)*xscale))
        lines.append((x,float(top),x,float(bottom)))
    return tuple(lines)


def _compose_layer(base, width, height, segments, ink):
    """All layer passes share one logical scanline state, in exact order."""
    if len(segments)==0:
        return base
    for first in range(0,len(segments),SEGMENT_CHUNK):
        part=segments[first:first+SEGMENT_CHUNK]
        if isinstance(part,np.ndarray):
            # Stage31H produces a packed (N,4) ndarray; the Stage31G
            # bounded TCo2Draw API deliberately accepts explicit lists.
            part=part.tolist()
        base=source_raster_rgba(
            width=width,height=height,segments=part,ink=ink,
            initial_rgba=base)
    return base


def build_tqgrapher_composite(
        values, *,
        canvas_width:int,canvas_height:int,
        zero_text_width:int,six_decimals_text_width:int,
        zero_text_height:int,
        scr_left:float,scr_width:float,
        scr_bottom:float,scr_height:float,
        series_x_start:float=0.,series_x_scale:float=1.,
        series_y_scale:float=1.,
        x_name_present:bool=True,y_name_present:bool=True):
    """Return pixel RGBA and source-derived frame geometry in one result.

    The caller supplies the REAL native PaintBox pixel size and original
    TCanvas metrics when they become available. Feeding Qt font/viewport
    measurements only produces a reversible RESEARCH candidate.
    """
    for name,val in (('canvas_width',canvas_width),
                     ('canvas_height',canvas_height)):
        if type(val) is not int or not 4<=val<=10000:
            raise ValueError(name+" must be a bounded positive integer")
    if canvas_width*canvas_height>MAX_PIXELS:
        raise ValueError("TQGrapher composite exceeds safe pixel budget")
    # Validate and compute original source margins / PixelRect. This
    # function does not assume the user's 150% scaling equals native DPI.
    canvas=source_paintbox_registration(
        pixel_width=canvas_width,pixel_height=canvas_height,
        zero_text_width=zero_text_width,
        six_decimals_text_width=six_decimals_text_width,
        zero_text_height=zero_text_height,
        x_name_present=x_name_present,y_name_present=y_name_present,
        scr_left=scr_left,scr_width=scr_width,
        scr_bottom=scr_bottom,scr_height=scr_height,
        series_x_start=series_x_start,
        series_x_scale=series_x_scale)
    left,right=canvas['pixel_left'],canvas['pixel_right']
    top,bottom=canvas['pixel_top'],canvas['pixel_bottom']
    if not (1<=left<right<canvas_width-1 and
            1<=top<bottom<canvas_height-1):
        raise ValueError("source-derived PixelRect outside bounded paintbox")
    if not all(math.isfinite(float(v)) for v in
               (scr_left,scr_width,scr_bottom,scr_height,series_y_scale)):
        raise ValueError("nonfinite screen/series coordinate")
    if float(scr_width)<=0 or float(scr_height)<=0:
        raise ValueError("positive spectrum screen range required")
    grid=source_tqgrapher_grid_candidate(
        scr_left=scr_left,scr_width=scr_width,
        scr_bottom=scr_bottom,scr_height=scr_height)
    traces=source_tqgr_series_columns(
        values,
        scr_left=scr_left,scr_width=scr_width,
        scr_bottom=scr_bottom,scr_height=scr_height,
        x_start=series_x_start,x_scale=series_x_scale,
        y_scale=series_y_scale,
        pixel_left=left,pixel_right=right,
        pixel_top=top,pixel_bottom=bottom)
    # Stage111Z31G TCo2Draw line blending, in original Draw order.
    grid_segments=_screen_segments(
        grid,canvas,scr_left=scr_left,scr_width=scr_width,
        scr_bottom=scr_bottom,scr_height=scr_height)
    frame=source_raster_rgba(
        width=canvas_width,height=canvas_height,
        segments=grid_segments,ink=GRID_LINE_RGB,
        background=BACKGROUND_RGB)
    # Original GDI TextOut labels are not available at native font/DPI.
    # Do not simulate or misrepresent them as original GDI pixels.
    trace_segments=traces['segments']
    frame=_compose_layer(frame,canvas_width,canvas_height,
                         trace_segments,SERIES_RGB)
    border_segments=(
        (left,top,right,top),
        (right,top,right,bottom),
        (right,bottom,left,bottom),
        (left,bottom,left,top))
    frame=_compose_layer(frame,canvas_width,canvas_height,
                         border_segments,FRAME_RGB)
    return {
        "source":SOURCE,
        "rgba":frame,
        "canvas":canvas,
        "grid_model":grid,
        "series_model":traces,
        "grid_segments":np.asarray(grid_segments,dtype=np.float32).reshape(-1,4),
        "series_segment_count":int(len(trace_segments)),
        "grid_segment_count":len(grid_segments),
        "border_segment_count":len(border_segments),
        "layer_order":source_tqgrapher_composite_contract()['draw_order'],
        "tcanvas_textout_implemented":False,
        "font_metrics_are_native_original":False,
        "original_runtime_pixel_parity_verified":False,
        "original_signal_and_fft_data_modified":False,
    }
