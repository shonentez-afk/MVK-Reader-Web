"""Stage111J: source-derived FRange data-flow for original float-ring GetSpectrum.

PRIVATE _Unit115.pas:
  ProcessBufferChunk 007D23B7..23E5: for FAdcDataType==1 and ApplyRange,
      PAdcFloatData[k] <- Single(PAdcFloatData[k]*FRange).
  GetSpectrum 007D1494..14A5: passes flag 1 to helper 007D2228.
  helper 007D22A1..22D4: for FAdcDataType==1 and flag=1,
      copied[i] <- Single(PAdcFloatData[k]/FRange).
  GetSpectrum 007D1667,16F1,17B0,185A,18F9: multiply linear
      spectrum and summary outputs by FRange.

A Native R6.1 calibrated BIN is NOT proven to be an original Delphi
PAdcFloatData ring. Do not silently interpret it as one. Explicit operator
choice is required for that research hypothesis; no auto calibration.
"""
from __future__ import annotations
import numpy as np
from .calibration_candidate import resolve_f_range

DOMAIN_CALIBRATED_BIN='calibrated_bin'
DOMAIN_ORIGINAL_STORAGE='original_float_storage'


def prepare_original_fft_input(samples,*,f_range=None,
                               input_domain=DOMAIN_CALIBRATED_BIN)->dict:
    scale,src=resolve_f_range(f_range)
    if input_domain not in (DOMAIN_CALIBRATED_BIN,DOMAIN_ORIGINAL_STORAGE):
        raise ValueError('Unknown FRange input domain')
    raw=np.asarray(samples,dtype=np.float32)
    if raw.ndim!=1 or not bool(np.isfinite(raw).all()):
        raise ValueError('Expected finite one-dimensional original FFT window')
    if input_domain==DOMAIN_ORIGINAL_STORAGE:
        with np.errstate(over='ignore',under='ignore',invalid='ignore'):
            normalized=np.asarray(raw.astype(np.float64)/scale,dtype=np.float32)
        if not bool(np.isfinite(normalized).all()):
            raise ValueError('Delphi storage / FRange would overflow float32')
    else:
        normalized=raw.copy()
    return {
        'samples_before_dc_removal':normalized,
        'f_range_used':scale,
        'f_range_source':src,
        'input_domain':input_domain,
        'source':'APP_DERIVED_FRANGE_FLOAT_RING_CANDIDATE',
        'original_storage_read_divided_by_range':
            input_domain==DOMAIN_ORIGINAL_STORAGE,
        'output_linear_scales_by_f_range':True,
        'original_source_buffer_provenance_verified':False,
        'calibrated_native_bin_is_original_storage_verified':False,
        'warning':('Original Delphi f32 ring read divides by FRange; '
                   'Native R6.1 BIN storage equivalence is not established')
    }
