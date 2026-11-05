"""Stage111Z31N — faithful spectrum PlotCurveItem geometry, not font parity.

Production archive data: preserve ALL N/2 Float32 bins for calculations,
but original TQGrapher draws only TRUNC((N/2)/1.28) bins and collapses
overlapping samples into (min,max) pixel-column strokes.
This adapter gives Qt frequency/amplitude coordinates from those exact
source-derived column strokes. It does NOT read device data.
"""
from __future__ import annotations

import math
import numpy as np

from .tqgrapher_display_idr_candidate import spectrum_display_contract
from .tqgr_series_source_candidate import source_tqgr_series_columns

SOURCE="SOURCE_DERIVED_SPECTRUM_ARCHIVE_GRAPH_PROJECTION_STAGE111Z31N"
MAX_RENDER_PIXELS=8192


def spectrum_archive_plot_projection(
        amplitudes, *, n_fft:int, sample_rate_hz:float,
        view_x:tuple, view_y:tuple,
        pixel_width:int, pixel_height:int,
        min_density:float=1.5):
    """Return peak-preserving connected-pairs plot coords or sparse fallback.

    The full Float32 array is READ-ONLY. Caller must retain original raw
    frequencies/values for cursor/summary and use this ONLY for display.
    The original Series has DataSize < N/2 (the summary still uses N/2).
    """
    y=np.asarray(amplitudes)
    if y.ndim!=1 or y.dtype.kind not in "fi":
        raise ValueError("Float32 spectrum vector required")
    if type(pixel_width) is not int or type(pixel_height) is not int:
        raise ValueError("plot size must be genuine integers")
    if not 4<=pixel_width<=MAX_RENDER_PIXELS or not 4<=pixel_height<=MAX_RENDER_PIXELS:
        raise ValueError("unsupported Qt plot size")
    if (not isinstance(view_x,(list,tuple)) or len(view_x)!=2 or
            not isinstance(view_y,(list,tuple)) or len(view_y)!=2):
        raise ValueError("plot X/Y bounds required")
    xlo,xhi=map(float,view_x)
    ylo,yhi=map(float,view_y)
    if not all(math.isfinite(x) for x in (xlo,xhi,ylo,yhi,min_density)):
        raise ValueError("nonfinite plot range")
    if xhi<=xlo or yhi<=ylo or not 0.5<=min_density<=10.:
        raise ValueError("invalid plot ranges/density")
    contract=spectrum_display_contract(n_fft,sample_rate_hz)
    count=contract["grapher_series_bins"]
    if y.size!=n_fft//2:
        raise ValueError("spectrum must retain all N/2 bins")
    values=np.asarray(y,dtype=np.float32)
    if not np.all(np.isfinite(values)):
        raise ValueError("nonfinite original spectrum values")
    df=contract["x_scale_single_hz"]
    # The original TQGRSeries *visible* array stops at DataSize, one bin
    # shy of the axis edge. Never plot power bins beyond its boundary.
    lo=max(0,math.floor(xlo/df))
    hi=min(count,math.ceil(xhi/df))
    visible=max(0,hi-lo)
    if visible<=min_density*pixel_width:
        return {
            "source":SOURCE,
            "draw_mode":"original_samples_when_sparse",
            "reason":"no source min/max collapsing needed at current zoom",
            "view_x_hz":(xlo,xhi),"view_y":(ylo,yhi),
            "visible_bin_count":visible,
            "source_series_bins":count,
            "full_fft_bins":int(y.size),
            "pairs_x_hz":np.empty(0,dtype=np.float64),
            "pairs_y":np.empty(0,dtype=np.float64),
            "segments_count":0,
            "original_delphi_pixel_runtime_verified":False,
            "raw_amplitudes_modified":False,
        }
    # Exact same original per-pixel min/max source function as Stage31H.
    model=source_tqgr_series_columns(
        values[:count],
        scr_left=xlo,scr_width=xhi-xlo,
        scr_bottom=ylo,scr_height=yhi-ylo,
        x_start=0.,x_scale=df,y_scale=1.,
        pixel_left=0,pixel_right=pixel_width-1,
        pixel_top=0,pixel_bottom=pixel_height-1)
    segments=model["segments"]
    if not segments.size:
        return {
            "source":SOURCE,"draw_mode":"original_samples_when_sparse",
            "reason":"source projection contains no visible line segments",
            "view_x_hz":(xlo,xhi),"view_y":(ylo,yhi),
            "visible_bin_count":visible,
            "source_series_bins":count,
            "full_fft_bins":int(y.size),
            "pairs_x_hz":np.empty(0,dtype=np.float64),
            "pairs_y":np.empty(0,dtype=np.float64),
            "segments_count":0,
            "original_delphi_pixel_runtime_verified":False,
            "raw_amplitudes_modified":False,
        }
    px=segments[:,(0,2)].reshape(-1)
    py=segments[:,(1,3)].reshape(-1)
    # Screen X grows right, screen Y grows DOWN. Qt Y grows UP.
    coords_x=xlo+px/(pixel_width-1)*(xhi-xlo)
    coords_y=yhi-py/(pixel_height-1)*(yhi-ylo)
    if not (np.isfinite(coords_x).all() and np.isfinite(coords_y).all()):
        raise ValueError("invalid source-per-pixel display coordinates")
    return {
        "source":SOURCE,
        "draw_mode":"original_pixel_column_minmax",
        "view_x_hz":(xlo,xhi),"view_y":(ylo,yhi),
        "visible_bin_count":visible,
        "source_series_bins":count,
        "full_fft_bins":int(y.size),
        "pairs_x_hz":coords_x,
        "pairs_y":coords_y,
        "segments_count":int(segments.shape[0]),
        "source_column_count":len(model["columns"]),
        "source_initial_sample_index":model["initial_sample_index"],
        "original_delphi_pixel_runtime_verified":False,
        "raw_amplitudes_modified":False,
        "source_min_max_after_display_clamp":True,
    }
