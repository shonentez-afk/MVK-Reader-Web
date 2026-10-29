"""Stage111D pixel-based TQGrapher cursor reconstruction (OFFLINE, candidate).

Derived from PRIVATE _Unit115.pas 007CA75C..007CAAFB, 007CABE4, 007CAB94
and _Unit128.pas 00844B90/00848252. No proprietary source is distributed.

Original logic: reject cursor at/outside PixelLeft..PixelRight; Trunc pixel->index
with clamp; in precise mode seek greatest *signed* stored float32 value among
bins falling into the given pixel; snap cursor line to selected index;
CursorAveraging >1 uses sqrt(SUM of squares), *without dividing by count*.
Pixel-to-bin scale/pixel geometry must be supplied by caller and matched to the
original TQGrapher before claiming pixel-for-pixel equivalence.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class CursorGeometry:
    pixel_left: float
    pixel_right: float
    stoi_m: float
    stoi_c: float
    x_start: float
    x_scale: float
    y_scale: float = 1.0
    itos_m: float | None = None
    itos_c: float | None = None

    def validate(self) -> None:
        p=(self.pixel_left,self.pixel_right,self.stoi_m,self.stoi_c,
           self.x_start,self.x_scale,self.y_scale)
        if (not all(math.isfinite(float(x)) for x in p)
                or self.pixel_right <= self.pixel_left
                or self.stoi_m <= 0 or self.x_scale <= 0
                or self.y_scale == 0
                or ((self.itos_m is None)!=(self.itos_c is None))
                or (self.itos_m is not None and (
                    not math.isfinite(self.itos_m) or not math.isfinite(self.itos_c)
                    or self.itos_m<=0))):
            raise ValueError('Invalid TQGrapher cursor pixel/series geometry')


def _index_at(pixel:float, geometry:CursorGeometry, length:int) -> int:
    """007CABE4: trunc toward zero then saturate 0..DataSize-1."""
    position=math.trunc((pixel-geometry.pixel_left)*geometry.stoi_m+geometry.stoi_c)
    return max(0,min(length-1,position))


def pick_tqgrapher_cursor(
    values:np.ndarray, pixel:float, geometry:CursorGeometry, *,
    precise:bool=True, averaging:int=1,
) -> dict:
    """Reconstructed pixel-to-bin selection and numeric cursor output.

    Compatible only with uniformly spaced linear-X series. Y-scale is applied
    to the f32 series value; the finite values must be original display data
    (NOT pre-decimated chart points). Nearest-frequency fallback is forbidden.
    """
    geometry.validate()
    if not math.isfinite(float(pixel)):
        raise ValueError('Non-finite pixel')
    if averaging not in (1,3):
        raise ValueError('Only source-verified CursorAveraging 1 and 3 are supported')
    a=np.asarray(values,dtype=np.float32)
    if a.ndim!=1 or len(a)<2 or not bool(np.isfinite(a).all()):
        raise ValueError('Full-resolution finite float32 grapher series required')
    if not geometry.pixel_left < pixel < geometry.pixel_right:
        raise ValueError('Cursor is outside original plot interior')

    first=_index_at(pixel,geometry,len(a))
    end_exclusive=_index_at(pixel+1,geometry,len(a))
    # Delphi: last := index(pixel+1)-1; when two edges map to same bin,
    # its precise-search loop is skipped and the first index is retained.
    last=end_exclusive-1
    chosen=first
    if precise and last>=first:
        # Delphi comparator is strictly >, ties keep the first bin.
        # Original IDR reads first as baseline then walks first+1..last.
        chosen=first+int(np.argmax(a[first:last+1]))
    center=chosen
    if averaging==1:
        y_stored=float(a[center])
        avg_first=avg_last=center
    else:
        radius=averaging//2
        avg_first=max(0,center-radius)
        avg_last=min(len(a)-1,center+radius)
        # Original 007CAA8A..007CAA96: f32 accumulation of squares
        # followed by sqrt, *no divisor by number of points*.
        sum_sq=np.float32(0.0)
        for item in a[avg_first:avg_last+1]:
            sum_sq=np.float32(float(sum_sq)+float(item)*float(item))
        y_stored=float(np.float32(math.sqrt(float(sum_sq))))

    # 007CA903: x = index*XScale + XStart (X axis label).
    x_value=float(np.float32(center*geometry.x_scale+geometry.x_start))
    # 007CAB94 uses its own itosM/C computed by original drawable rect; the
    # inverse of supplied stoiM/C is only a candidate for line position.
    snapped_pixel=geometry.pixel_left+(center-geometry.stoi_c)/geometry.stoi_m
    snapped_pixel=min(geometry.pixel_right,max(geometry.pixel_left,snapped_pixel))
    # 007CAB94 computes index*itosM+itosC, STP Single, CLAMP to native
    # PixelLeft..PixelRight, then Delphi @ROUND. Source independent from
    # inverse(stoiM/C). Only available if the caller supplied both fields.
    snapped_original=None
    if geometry.itos_m is not None:
        original=float(np.float32(center*geometry.itos_m+geometry.itos_c))
        original=min(geometry.pixel_right,max(geometry.pixel_left,original))
        snapped_original=int(round(original))
    return {
        'selected_bin':chosen,
        'pixel':float(pixel),
        'pixel_bin_first':first,
        'pixel_bin_last':last,
        'precise_max_search_used':bool(precise and last>=first),
        'snapped_pixel_candidate':float(snapped_pixel),
        'snapped_pixel_original_int_candidate':snapped_original,
        'independent_itos_source_supplied':geometry.itos_m is not None,
        'x_value':x_value,
        'raw_y':float(a[center]),
        'display_y':float(np.float32(y_stored*geometry.y_scale)),
        'averaging':averaging,
        'averaging_first':avg_first,
        'averaging_last':avg_last,
        'averaging_divisor':1,
        'source':'APP_DERIVED_TQGRAPHER_PIXEL_CURSOR_IDR_CANDIDATE',
        'original_delphi_cursor_parity_verified':False,
        'warning':'Source-confirmed bin selection; pixel transforms, x87 rounding and CursorString formats still require original UI comparisons',
    }


def cursor_from_spectrum(
    spectrum:dict, pixel:float, geometry:CursorGeometry, *,
    precise:bool=True, averaging:int=1
)->dict:
    """Use the FULL, non-decimated candidate FFT bin series, not chart points."""
    from math import isclose
    freqs=np.asarray(spectrum['frequency_hz'],dtype=np.float64)
    values=np.asarray(spectrum['amplitude'],dtype=np.float64)
    df=float(spectrum['df_hz'])
    full_power_bins=len(freqs)
    grapher_bins=spectrum.get('grapher_series_bins',full_power_bins)
    if (not isinstance(grapher_bins,int) or isinstance(grapher_bins,bool)
        or grapher_bins<2 or grapher_bins>full_power_bins):
        raise ValueError('Invalid source-derived TQGrapher displayed series length')
    if (len(freqs)<2 or len(freqs)!=len(values) or not math.isfinite(df)
        or df<=0 or not isclose(geometry.x_scale,df,rel_tol=1e-6)
        or not isclose(geometry.x_start,float(freqs[0]),rel_tol=1e-6,abs_tol=1e-9)
        or not bool(np.allclose(freqs,geometry.x_start+np.arange(len(freqs))*df,
                                 atol=1e-7,rtol=1e-7))):
        raise ValueError('Cursor requires full-resolution, contiguous FFT bins and matching XScale')
    found=pick_tqgrapher_cursor(values[:grapher_bins],pixel,geometry,
                               precise=precise,averaging=averaging)
    found.update({
        'channel':spectrum['channel'],
        'unit':spectrum['unit'],
        'mode':spectrum['mode'],
        'n_fft':spectrum['n_fft'],
        'df_hz':df,
        'fft_source':spectrum['source'],
        'fft_backend':spectrum.get('fft_backend','unknown'),
        'frequency_hz':float(freqs[found['selected_bin']]),
        'full_bin_count':full_power_bins,
        'grapher_series_bins':grapher_bins,
        'original_series_truncated_from_fft':
            grapher_bins < full_power_bins,
        'chart_decimation_used':False,
    })
    return found
