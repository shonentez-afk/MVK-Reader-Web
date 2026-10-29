"""Stage111J source-derived TQGrapher Spectrum display/Copy contracts.

PRIVATE ORIGINAL _Unit128.pas:00848292..008482CE:
  Series.XScale = Single(OutputSampleRate / (2*OutputLength))
  Series.DataSize = TRUNC(OutputLength/Extended(1.28))
  OutputLength is NFFT/2, so the original visible/interactive series is
  STRICTLY SHORTER than all NFFT/2 power bins used by GetSpectrum summary.

PRIVATE _Unit115.pas:007CA903..007CAAEE:
  CursorString = FORMAT4(index*XScale+XStart) + ' ' + XName
      [+ CursorSep + FORMAT4(displayY) + ' ' + YName] for each populated series
  TQGrapher.Create 007CA459 defaults CursorSep to CRLF.
The original pixel rectangle, x87 FormatFloat and localized names are still
not accepted. This module never reads private IDP or connects to devices.
"""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np
from .cursor_format_candidate import format_cursor_idr_candidate

SOURCE='APP_DERIVED_TQGRAPHER_DISPLAY_IDR_CANDIDATE'


def spectrum_display_contract(n_fft:int,output_sample_rate_hz:float)->dict:
    """Source-derived max plotted series and original Single XScale."""
    if (not isinstance(n_fft,int) or isinstance(n_fft,bool)
        or n_fft<1024 or n_fft>262144 or n_fft&(n_fft-1)):
        raise ValueError('Original spectrum N must be power of two 1024..262144')
    if (not math.isfinite(output_sample_rate_hz)
        or output_sample_rate_hz<=0):
        raise ValueError('OutputSampleRate must be positive and finite')
    half=n_fft//2
    series_count=math.trunc(half/1.28)
    x_scale=float(np.float32(float(output_sample_rate_hz)/n_fft))
    if series_count<2 or not math.isfinite(x_scale) or x_scale<=0:
        raise ValueError('Unrepresentable original TQGrapher series XScale')
    return {
        'source':SOURCE,
        'full_fft_power_bins':half,
        'grapher_series_bins':series_count,
        'grapher_last_index':series_count-1,
        'grapher_last_frequency_hz':float(np.float32((series_count-1)*x_scale)),
        'x_scale_single_hz':x_scale,
        'display_truncation':'TRUNC((NFFT/2)/EXTENDED_1_28)',
        'original_numeric_parity_verified':False,
        'original_pixel_rectangle_verified':False,
        'original_window_verified':False
    }


def cursor_string_candidate(x_value:float, displayed_y:float, *,
                            x_name:str='Гц', y_name:str='м/с²',
                            cursor_sep:str='\r\n',
                            second_y:float|None=None,
                            second_y_name:str|None=None,
                            decimal_separator:str=',')->dict:
    """Original string field order, not exact Delphi RTL FormatFloat parity.

    Single source coordinates are passed to 007B2090 for each axis with
    NumberOfSignificantDigits=4. A second nonempty TQGRSeries uses the same
    cursor X coordinate, then appends CursorSep + Y2 + YName2.
    """
    values=[x_value,displayed_y]
    if second_y is not None:values.append(second_y)
    if any(not math.isfinite(float(v)) for v in values):
        raise ValueError('TQGrapher cursor requires finite local series')
    if (not isinstance(x_name,str) or not isinstance(y_name,str)
        or not isinstance(cursor_sep,str) or len(cursor_sep)>32
        or any(c in x_name+y_name for c in '\n\r\t')):
        raise ValueError('Invalid original axis strings')
    if second_y is not None and (not isinstance(second_y_name,str)
                                 or any(c in second_y_name for c in '\r\n\t')):
        raise ValueError('Second series requires explicit valid Y name')
    fs=lambda v:format_cursor_idr_candidate(
        float(np.float32(v)),significant_digits=4,
        decimal_separator=decimal_separator)
    fields=[fs(x_value)+' '+x_name,
            fs(displayed_y)+' '+y_name]
    if second_y is not None:fields.append(fs(second_y)+' '+second_y_name)
    text=fields[0]+''.join(cursor_sep+field for field in fields[1:])
    return {
        'source':SOURCE,
        'text':text,'x_text':fields[0],
        'y_texts':fields[1:],
        'cursor_sep':cursor_sep,
        'original_Delphi_FormatFloat_parity_verified':False,
        'original_axis_localization_verified':False,
        'original_cursor_geometry_verified':False
    }
