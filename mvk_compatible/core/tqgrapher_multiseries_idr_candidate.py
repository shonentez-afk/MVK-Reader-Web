"""Stage111L — original TQGrapher.UpdateCursor two-series source reconstruction.

Evidence: private _Unit115.pas, 007CA76C..007CAAFB; 007CAB94, 007CABE4.
The original decompiled source is NOT included or redistributed.

Reconstruct source-visible behavior, not pixel-perfect Delphi/x87 rounding.
Original screen geometry/font metrics must be independently measured. Never
use this to replace AUX4700 instrument DSP values or send device commands.
"""
from __future__ import annotations

import math
import numbers
from collections.abc import Sequence
import numpy as np
from .cursor_format_candidate import format_cursor_idr_candidate

SOURCE = 'APP_DERIVED_TQGRAPHER_TWO_SERIES_IDR_CANDIDATE'


def _native_bin(pixel: int, *, left: int, stoi_m: float, stoi_c: float,
                data_size: int) -> int:
    # 007CA843: fild(CursorPos), fstp Single, 007CABE4: (pixel-left)*stoiM + stoiC;
    # Delphi @TRUNC rounds toward zero, then saturates to 0..DataSize-1.
    single_pixel = float(np.float32(pixel))
    position = math.trunc((single_pixel-left)*stoi_m+stoi_c)
    return max(0, min(data_size-1, position))


def _max_in_pixel(data: np.ndarray, first: int, last: int,
                  *, precise: bool) -> int:
    """Original compares signed Single with strict >; first tie wins."""
    if not precise or last < first:
        return first
    if last >= len(data) or first < 0:
        raise ValueError('Original pixel range outside series buffer')
    return first + int(np.argmax(data[first:last+1]))


def _series_y(data: np.ndarray, index: int, averaging: int,
              y_scale: float) -> tuple[float, int, int]:
    if averaging <= 1:
        return float(np.float32(float(data[index])*y_scale)), index, index
    radius=averaging//2
    start=max(index-radius,0)
    # 007CAA6B–007CAA7C clamps to DataSize, inclusive, then indexes [DataSize].
    # This is an actual potential out-of-bounds original path. Refuse rather
    # than emulate an unsafe read or silently pretend exact parity.
    source_last=min(len(data),index+radius)
    if source_last>=len(data):
        raise ValueError('Original Delphi averaging could read past Series.DataSize')
    acc=np.float32(0.)
    for i in range(start,source_last+1):
        acc=np.float32(float(acc)+float(data[i])*float(data[i]))
    y=float(np.float32(math.sqrt(float(acc))*y_scale))
    return y,start,source_last


def original_multiseries_cursor(
    series0: Sequence[float]|np.ndarray,
    *, pixel: int, canvas: dict, averaging: int=1, precise: bool=True,
    series1: Sequence[float]|np.ndarray|None=None,
    y_scale0: float=1., y_scale1: float=1.,
    x_name: str='Гц', y_name: str='м/с²',
    decimal_separator: str=',', cursor_sep: str='\r\n'
)->dict:
    """Source-structured native absolute Canvas pixel → one/two series.

    The SECOND series' plotted Y uses the SAME TQGrapher.YName as the first
    (007CAA2C / 007CAAD4), unlike a previous independent-names hypothesis.

    Original metadata must include single-float transforms from the measured
    same-size Canvas. Caller must never use Qt plot-local pixels as absolute
    Delphi TCanvas pixels without explicit origin registration.
    """
    if not isinstance(canvas, dict) or not canvas.get('source')==(
        'APP_DERIVED_TQGRAPHER_CANVAS_GEOMETRY_IDR_CANDIDATE'):
        raise ValueError('Source-derived Canvas with explicit pixel transforms required')
    if not isinstance(pixel, numbers.Integral) or isinstance(pixel, bool):
        raise ValueError('Original TQGrapher.CursorPos is a native integer')
    if averaging not in (1, 3) or not isinstance(precise,bool):
        raise ValueError('Only original CursorAveraging 1/3 and boolean precise supported')
    if (not isinstance(x_name,str) or not isinstance(y_name,str)
        or not isinstance(cursor_sep,str) or len(cursor_sep)>32
        or any(c in x_name+y_name for c in '\r\n\t')):
        raise ValueError('Original cursor names and separator invalid')
    if decimal_separator not in ('.', ','):
        raise ValueError('Explicit decimal separator required')
    if (not math.isfinite(y_scale0) or not math.isfinite(y_scale1)):
        raise ValueError('Non-finite y scale')
    raw=[np.asarray(series0,dtype=np.float32)]
    if series1 is not None:
        raw.append(np.asarray(series1,dtype=np.float32))
    if any(x.ndim!=1 or not bool(np.isfinite(x).all()) for x in raw):
        raise ValueError('Series must be finite float32 arrays')

    left=int(canvas['pixel_left']);right=int(canvas['pixel_right'])
    if right<=left:
        raise ValueError('Invalid native Canvas PixelRect')
    if pixel<=left or pixel>=right or len(raw[0])==0:
        return {
            'source':SOURCE, 'drawn':False, 'cursor_string':'',
            'reason':'OUTSIDE_PLOT_OR_EMPTY_PRIMARY',
            'original_delphi_cursor_parity_verified':False}

    stoi_m=float(canvas['stoi_m']);stoi_c=float(canvas['stoi_c'])
    itos_m=float(canvas['itos_m']);itos_c=float(canvas['itos_c'])
    x_scale=float(canvas['series_x_scale']);x_start=float(canvas['series_x_start'])
    vals=(stoi_m,stoi_c,itos_m,itos_c,x_scale,x_start)
    if (not all(math.isfinite(v) for v in vals)
        or stoi_m==0 or itos_m==0 or x_scale<=0):
        raise ValueError('Invalid original Single X transforms')
    # Native ScrWidth may be negative (reversed horizontal axis). Original
    # still computes index(pixel+1)-1: the precise-search loop may therefore
    # be empty; never silently sort/reverse the pixel indices.
    # Integer pixel+1 as in original rather than a floating point epsilon.
    first=_native_bin(pixel,left=left,stoi_m=stoi_m,stoi_c=stoi_c,
                      data_size=len(raw[0]))
    last=_native_bin(pixel+1,left=left,stoi_m=stoi_m,stoi_c=stoi_c,
                     data_size=len(raw[0]))-1
    selected=_max_in_pixel(raw[0],first,last,precise=precise)

    # Vertical line is drawn through the primary selected index, not a
    # de-quantized cursor X computed by inverting stoiM/sto iC.
    snap=float(np.float32(selected*itos_m+itos_c))
    snap=min(right,max(left,snap))
    snapped=int(round(snap))  # Delphi @ROUND nearest-even candidate.
    x_raw=float(np.float32(selected*x_scale+x_start))
    f=lambda v:format_cursor_idr_candidate(
        v,significant_digits=4,decimal_separator=decimal_separator)
    lines=[f(x_raw)+' '+x_name]
    selection=[]
    for i,a in enumerate(raw):
        # Original 007CA953..007CA96B skips series if DataSize <= first OR
        # DataSize <= last; its absolute pixel bounds are from primary series.
        if len(a)<=first or len(a)<=last:
            continue
        k=_max_in_pixel(a,first,last,precise=precise)
        y,start,end=_series_y(a,k,averaging,(y_scale0,y_scale1)[i])
        lines.append(f(y)+' '+y_name)  # Original uses one global YName.
        selection.append({
            'series':i,'selected_bin':k,
            'averaging_first_bin':start,'averaging_last_bin':end,
            'raw_at_peak':float(a[k]), 'display_y':y,
        })
    return {
        'source':SOURCE,'drawn':True,
        'cursor_string':cursor_sep.join(lines),
        'cursor_lines':lines,
        'selected_primary_bin':selected,'first_pixel_bin':first,
        'last_pixel_bin':last,'snapped_vertical_pixel':snapped,
        'x_value':x_raw,'series_results':selection,
        'second_series_uses_same_global_y_name':True,
        'pixel_coordinate_system':'ORIGINAL_CANVAS_ABSOLUTE',
        'original_delphi_cursor_parity_verified':False,
        'original_pixel_origin_verified':False,
        'original_Delphi_FormatFloat_parity_verified':False,
        'warning':'Source algorithm, synthetic/local metrics; original font/coords/x87 RTL unverified'
    }
