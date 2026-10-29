"""Stage111M: original TQGrapher cursor crosshair lines, separate from Y text.

Private ORIGINAL _Unit115.pas:
  007CA7B6..007CA7CF / 007CA7E8..007CA804 erase prior vertical/horizontal
  007CA8D4..007CA900 draw a vertical line at @ROUND(index*itosM+itosC)
  007CA9BA..007CA9C3: Single(raw_selected_bin*Series.YScale)
  007CA9C7..007CA9D3: sub_007CAC18 then Delphi @ROUND
  007CA9D8..007CA9F0: horizontal line PixelLeft..PixelRight at result
  007CA9F3..007CAAE5: value LABEL uses raw bin for average=1,
     or sqrt(sum raw neighbors squared)*YScale for average=3.

Important: ORIGINAL averaged label does not move the horizontal line.
Pixel origin, Delphi font, floating-point/x87 parity require original
same-window reference and are NOT certified by this formula implementation.
No instrument, network or vendor source code is included.
"""
from __future__ import annotations

import math
import numbers
import numpy as np

SOURCE='APP_DERIVED_TQGRAPHER_CROSSHAIR_IDR_CANDIDATE'
EXPECTED_CURSOR_SOURCE='APP_DERIVED_TQGRAPHER_TWO_SERIES_IDR_CANDIDATE'
EXPECTED_CANVAS_SOURCE='APP_DERIVED_TQGRAPHER_CANVAS_GEOMETRY_IDR_CANDIDATE'


def _native_horizontal_pixel(raw_y:float,y_scale:float,*,canvas:dict)->dict:
    """007CA9BA -> 007CAC18 -> @ROUND, explicit Single stores."""
    if (not isinstance(raw_y,numbers.Real) or not isinstance(y_scale,numbers.Real)
        or isinstance(raw_y,bool) or isinstance(y_scale,bool)
        or not math.isfinite(raw_y) or not math.isfinite(y_scale)):
        raise ValueError('A finite original raw series Y and scale are required')
    coeff=(canvas['ytos_m'],canvas['ytos_c'])
    if not all(isinstance(x,numbers.Real) and math.isfinite(x) for x in coeff):
        raise ValueError('Original Canvas ytosM/C must be finite')
    with np.errstate(over='ignore',invalid='ignore',under='ignore'):
        # 007CA9BA: FSTP dword before 007CAC18 receives its by-value Single.
        scaled=np.float32(float(raw_y)*float(y_scale))
        transformed=np.float32(float(scaled)*float(coeff[0])+float(coeff[1]))
    if not math.isfinite(float(scaled)) or not math.isfinite(float(transformed)):
        raise ValueError('Original Y crosshair transform overflows Single')
    top,bottom=int(canvas['pixel_top']),int(canvas['pixel_bottom'])
    clipped=min(bottom,max(top,float(transformed)))
    return {
        'y_scaled_single':float(scaled),
        'y_pixel_unclipped_single':float(transformed),
        'y_pixel_clamped':clipped,
        'horizontal_pixel':int(round(clipped)),  # Delphi @ROUND nearest-even
    }


def original_cursor_crosshair(candidate:dict,canvas:dict, *,
                              y_scale0:float=1.,y_scale1:float=1.)->dict:
    """Original vertical + one independent horizontal line per active series.

    Input is an independent SOURCE candidate from original_multiseries_cursor
    with its original per-series raw_at_peak and selected bin.  We DO NOT
    project the averaged label back to a Y pixel (a common UI drift bug).

    Does not alter candidate/arrays or infer original real TCanvas metrics.
    """
    if not isinstance(candidate,dict) or candidate.get('source')!=EXPECTED_CURSOR_SOURCE:
        raise ValueError('An original multi-series cursor candidate is required')
    if not isinstance(canvas,dict) or canvas.get('source')!=EXPECTED_CANVAS_SOURCE:
        raise ValueError('An original source-derived TQGrapher Canvas is required')
    for key in ('pixel_left','pixel_right','pixel_top','pixel_bottom','ytos_m','ytos_c'):
        if key not in canvas:raise ValueError('Source Canvas missing '+key)
    left,right,top,bottom=(canvas['pixel_left'],canvas['pixel_right'],
                           canvas['pixel_top'],canvas['pixel_bottom'])
    if (not all(isinstance(x,numbers.Integral) and not isinstance(x,bool)
                for x in (left,right,top,bottom))
        or not left<right or not top<bottom):
        raise ValueError('Invalid original drawable pixel rectangle')
    if not candidate.get('drawn',False):
        return {
            'source':SOURCE,'drawn':False,'vertical_line':None,
            'horizontal_lines':[],'original_Delphi_pixel_parity_verified':False,
            'original_font_and_canvas_registration_verified':False,
        }
    pixel=candidate.get('snapped_vertical_pixel')
    if (not isinstance(pixel,numbers.Integral) or isinstance(pixel,bool)
        or not left<=pixel<=right):
        raise ValueError('Invalid original snapped vertical cursor X')
    segments=candidate.get('series_results')
    if not isinstance(segments,list) or not 1<=len(segments)<=2:
        raise ValueError('An original 1/2-series cursor selection is required')

    lines=[]
    for line in segments:
        idx=line.get('series')
        if idx not in (0,1) or any(x['series']==idx for x in lines):
            raise ValueError('Unexpected or duplicate original series index')
        y=line['raw_at_peak']
        scale=(y_scale0,y_scale1)[idx]
        calculated=_native_horizontal_pixel(y,scale,canvas=canvas)
        lines.append({
            'series':idx,
            'selected_bin':line['selected_bin'],
            'start_xy':[int(left),calculated['horizontal_pixel']],
            'end_xy':[int(right),calculated['horizontal_pixel']],
            'label_y_is_a_separate_operation':True,
            'label_display_y':line['display_y'],
            **calculated,
        })
    return {
        'source':SOURCE,'drawn':True,
        'vertical_line':{'start_xy':[int(pixel),int(top)],
                         'end_xy':[int(pixel),int(bottom)]},
        'horizontal_lines':lines,
        'horizontal_pixels':[x['horizontal_pixel'] for x in lines],
        'original_crosshair_independent_of_CursorAveraging':True,
        'original_Delphi_pixel_parity_verified':False,
        'original_font_and_canvas_registration_verified':False,
        'warning':('Original source formulas; Qt TCanvas registration, Delphi '
                   'x87 and original numeric outputs are not certified'),
    }
