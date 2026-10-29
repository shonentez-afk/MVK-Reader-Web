"""Stage111E candidate of Delphi cursor numeric formatting, NOT exact FormatFloat.

Private reference: _Unit114.pas 007B2090..007B21DE. The original function
uses 007B1CC0 (binary32 NaN test), a dynamic '0.' + zeroes FormatFloat
pattern, TFormatSettings decimal separator and trailing-zero removal.
Exact Delphi RTL/x87 rounding and locale behavior still need golden fixtures.
"""
from __future__ import annotations
import math
import numpy as np


def format_cursor_idr_candidate(
    value:float,significant_digits:int=4,decimal_separator:str='.'
)->str:
    """Source-structured decimal formatter; explicitly NOT Delphi-bitwise parity.

    007B2100..214F: keep multiplying stored float32 |value| by 10 until
    reaching 10^(digits-1), appending a zero to the decimal pattern each time.
    007B2166..21BC: remove trailing decimal zeros and separator.
    """
    if (not isinstance(significant_digits,int) or isinstance(significant_digits,bool)
        or not 1<=significant_digits<=12):
        raise ValueError('Invalid number of cursor significant digits')
    if decimal_separator not in ('.',','):
        raise ValueError('Only explicit decimal separator dot/comma is supported')
    v=np.float32(value)
    if np.isnan(v):return 'NAN'
    if not math.isfinite(float(v)):
        raise ValueError('Original Delphi infinity FormatFloat is not verified')
    if float(v)==0.0 or significant_digits<=0:return '0'
    m=np.float32(abs(float(v)))
    threshold=np.float32(10.0**(significant_digits-1))
    places=0
    while m<threshold and places<60:
        m=np.float32(float(m)*10.0)
        places+=1
    # Delphi's TFormatSettings.FormatFloat gets Extended, but the caller
    # pushes a float32 source. Python formatting is only a numerical candidate.
    rendered=format(float(v),f'.{places}f')
    if places:
        rendered=rendered.rstrip('0').rstrip('.')
    return rendered.replace('.',decimal_separator)
