"""Stage111E candidate of Delphi cursor numeric formatting, NOT exact FormatFloat.

Private reference: _Unit114.pas 007B2090..007B21DE. The original function
uses 007B1CC0 (binary32 NaN test), a dynamic '0.' + zeroes FormatFloat
pattern, TFormatSettings decimal separator and trailing-zero removal.
Exact Delphi RTL/x87 rounding and locale behavior still need golden fixtures.
"""
from __future__ import annotations
import math
import numpy as np




def cursor_decimal_mask_candidate(
    value:float,significant_digits:int=4,decimal_separator:str='.'
)->dict:
    """Reconstruct source mask '0.' + zeros before the Delphi RTL call.

    007B20F3..007B214F: original initializes mask as '0.' and repeatedly
    stores abs(single) * 10 into Single until >= 10^(digits-1). One zero is
    appended per iteration. 0042EE10 subsequently calls Delphi RTL with
    that mask and global TFormatSettings. The *actual RTL text rounding*
    is not proven solely from this mask reconstruction.
    """
    if (not isinstance(significant_digits,int) or isinstance(significant_digits,bool)
        or not 1<=significant_digits<=12):
        raise ValueError('Invalid number of cursor significant digits')
    if decimal_separator not in ('.',','):
        raise ValueError('Only explicit decimal separator dot/comma is supported')
    with np.errstate(over='ignore',invalid='ignore',under='ignore'):
        v=np.float32(value)
    if np.isnan(v):
        return {
            'source':'DELPHI_007B2090_MASK_CANDIDATE',
            'special':'NAN','mask':None,'decimal_places':0,
            'source_single':float(v),'digits':significant_digits,
            'original_delphi_rtl_verified':False}
    if not math.isfinite(float(v)):
        raise ValueError('Original Delphi infinity FormatFloat is not verified')
    if float(v)==0.:
        return {
            'source':'DELPHI_007B2090_MASK_CANDIDATE',
            'special':'ZERO','mask':None,'decimal_places':0,
            'source_single':float(v),'digits':significant_digits,
            'original_delphi_rtl_verified':False}
    val=np.float32(abs(float(v)))
    threshold=np.float32(10.0**(significant_digits-1))
    places=0
    while val<threshold:
        if places>=60:
            raise ValueError('Original decimal mask would exceed safe bound')
        val=np.float32(float(val)*10.)
        places+=1
    return {
        'source':'DELPHI_007B2090_MASK_CANDIDATE',
        'special':None,'mask':'0.'+('0'*places),
        'decimal_places':places,
        'source_single':float(v),'digits':significant_digits,
        'decimal_separator':decimal_separator,
        'original_delphi_rtl_verified':False}

def format_cursor_idr_candidate(
    value:float,significant_digits:int=4,decimal_separator:str='.'
)->str:
    """Source-structured decimal formatter; explicitly NOT Delphi-bitwise parity.

    007B2100..214F: keep multiplying stored float32 |value| by 10 until
    reaching 10^(digits-1), appending a zero to the decimal pattern each time.
    007B2166..21BC: remove trailing decimal zeros and separator.
    """
    contract=cursor_decimal_mask_candidate(value,significant_digits,decimal_separator)
    if contract['special']=='NAN':return 'NAN'
    if contract['special']=='ZERO':return '0'
    v=contract['source_single']
    places=contract['decimal_places']
    # Delphi's TFormatSettings.FormatFloat gets Extended, but the caller
    # pushes a float32 source. Python formatting is only a numerical candidate.
    rendered=format(float(v),f'.{places}f')
    if places:
        rendered=rendered.rstrip('0').rstrip('.')
    return rendered.replace('.',decimal_separator)
