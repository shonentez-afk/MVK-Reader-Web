"""Stage111I: explicit FRange Single validation and provenance, never ADC calibration.

Original _Unit115.pas TMvkChannelStorage.FRange is a 32-bit Single:
constructor 007D0A61 sets 1.0; GetSpectrum/GetSignal/GetNarrowbandValue
multiply outputs by this field. ProcessBufferChunk also has an ApplyRange
path, so an archived BIN's effective calibration CANNOT be inferred merely
from the default value or file contents.

This helper only normalizes an operator-supplied research candidate value.
It does not read or derive sensor gain, original DSP, AUX4700 or device state.
"""
from __future__ import annotations
import math
import numbers
import numpy as np

DEFAULT_RANGE_SOURCE='DEFAULT_ONE_NOT_CALIBRATION_VERIFIED'
OPERATOR_RANGE_SOURCE='OPERATOR_SUPPLIED_UNVERIFIED'


def resolve_f_range(value:float|None)->tuple[float,str]:
    """Validate a positive finite original 32-bit Single without silent clipping."""
    if value is None:
        return 1.,DEFAULT_RANGE_SOURCE
    if (isinstance(value,bool) or not isinstance(value,numbers.Real)
        or not math.isfinite(float(value)) or float(value)<=0):
        raise ValueError('FRange должен быть конечным положительным числом')
    # Explicitly model one unavoidable original Delphi Single store.
    with np.errstate(over='ignore',under='ignore',invalid='ignore'):
        one=float(np.float32(value))
    if not math.isfinite(one) or one<=0:
        raise ValueError('FRange не представим как положительный конечный Single')
    return one,OPERATOR_RANGE_SOURCE
