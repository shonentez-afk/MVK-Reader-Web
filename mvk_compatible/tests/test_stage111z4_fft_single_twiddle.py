"""Stage111Z.4: original FFT x87 Single-store twiddle recurrence regression.

All numeric fixtures below are *synthetic*, no original signal or binary included.
Source justification: private original IDP, kernel 007CC316..007CC347:
temp real FSTP Single (007CC325), temp imag FSTP Single (007CC33A),
wr FSTP Single (007CC344), wi FSTP Single (007CC33A).
The original spectrum calls the positive-angle wrapper 007CC3F8;
negative-angle FFT wrapper 007CC404 is a separate function.
"""
from __future__ import annotations
import math
import struct
import numpy as np
import pytest

from mvk_compatible.core.fft_idr_candidate import (
    _twiddle_step_with_single_stores, _twiddles_recurrent_float32,
    fft_idr_float32_real, idr_power_spectrum,
)


def _bits(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def test_single_step_reconstructs_two_explicit_source_intermediate_stores():
    wr, wi, alpha, beta = map(np.float32, (
        -0.6754682064056396, 0.5891702771186829,
        0.002579387277364731, 0.5616893768310547
    ))
    next_wr, next_wi = _twiddle_step_with_single_stores(wr, wi, alpha, beta)
    assert isinstance(next_wr, np.float32)
    assert isinstance(next_wi, np.float32)
    assert _bits(next_wr) == 0xBF809896
    assert _bits(next_wi) == 0x3E553EC6
    # A collapsed expression (without intermediate Single stores) is
    # demonstrably different in the imaginary coefficient by one f32 ULP.
    collapsed_imag = np.float32(
        float(wi) - (float(alpha)*float(wi) - float(beta)*float(wr)))
    assert _bits(collapsed_imag) == 0x3E553EC5


def _independent_recurrence(half: int):
    """Scalar reference: no use of the application's step helper."""
    angle=np.float32(np.float32(2.*math.pi)/np.float32(2*half))
    half_sine=np.float32(math.sin(float(angle)/2.))
    alpha=np.float32(2.*float(half_sine)**2)
    beta=np.float32(math.sin(float(angle)))
    rr=np.empty(half,dtype=np.float32)
    ii=np.empty(half,dtype=np.float32)
    wr,wi=np.float32(1.0),np.float32(0.0)
    for k in range(half):
        rr[k],ii[k]=wr,wi
        temp_r=np.float32(float(alpha)*float(wr)+float(beta)*float(wi))
        temp_i=np.float32(float(alpha)*float(wi)-float(beta)*float(wr))
        new_i=np.float32(float(wi)-float(temp_i))
        new_r=np.float32(float(wr)-float(temp_r))
        wr,wi=new_r,new_i
    return rr,ii


@pytest.mark.parametrize("half",[8,16,64,256])
def test_recurrence_has_bitwise_source_store_boundaries(half):
    real,imag=_twiddles_recurrent_float32(half)
    ref_real,ref_imag=_independent_recurrence(half)
    np.testing.assert_array_equal(real.view(np.uint32),ref_real.view(np.uint32))
    np.testing.assert_array_equal(imag.view(np.uint32),ref_imag.view(np.uint32))
    assert real[0] == 1.0 and imag[0] == 0.0


def test_fft_spectrum_uses_positive_angle_while_power_stays_nonnegative():
    n=256
    t=np.arange(n)
    signal=np.sin(2*np.pi*7*t/n).astype(np.float32)
    re,im=fft_idr_float32_real(signal)
    assert re.dtype==im.dtype==np.float32
    # Positive-angle transform: sine has positive imaginary component.
    assert im[7] > 0
    assert im[7] == pytest.approx(n/2,abs=.02)
    assert abs(float(re[7])) < .02
    power,_=idr_power_spectrum(signal,remove_dc=True)
    assert power.dtype == np.float32
    assert bool(np.isfinite(power).all()) and bool((power>=0).all())
