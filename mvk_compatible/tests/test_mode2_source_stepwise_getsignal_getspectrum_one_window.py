"""Source GetSignal/FFT same-window Single and binary64 store-order regressions.

Follows private original _Unit115.pas 007D0D9F/007D0DFB (x87 f64
per-sample power sum), 007D2344 (f32-stored running DC),
007D14B3 (one DC subtraction), 007D1FE8 (Hann/FFT).
All waveforms below are synthetic, not original user BIN/TSXML.
"""
from __future__ import annotations

from hashlib import sha256
import math

import numpy as np
import pytest

from ..core.signal_idr_candidate import (
    unfiltered_getsignal,source_stepwise_signal_power_f64,
)
from ..core.fft_idr_candidate import (
    mean_center_float32,idr_power_spectrum,
)
from ..core.spectrum_metrics_idr_candidate import original_spectrum_summary


def _f64_stored_power_loop(samples):
    # Independent Python scalar specification: each step writes float64.
    total=0.
    for v in samples:
        fv=float(v)
        total=float(total+fv*fv)
    return total


def test_original_source_rms_f64_accumulator_not_pairwise_on_262144_samples():
    n=262144
    values=np.concatenate((np.full(n//2,1000.,dtype="<f4"),
                           np.full(n//2,.01,dtype="<f4")))
    saved=sha256(values.tobytes()).hexdigest()
    sequential=source_stepwise_signal_power_f64(values)
    explicit=_f64_stored_power_loop(values)
    pairwise=float(np.sum(values.astype(np.float64)**2,dtype=np.float64))
    assert sequential==explicit
    assert abs(pairwise-sequential)>.1
    frame=unfiltered_getsignal(values,65536,no_dc=False)
    expected=float(np.float32(math.sqrt(sequential/n)))
    assert frame.rms_value==expected
    assert frame.window_mean != 0.
    assert frame.removed_mean == 0.
    assert frame.output_length == n
    assert frame.getsignal_buffer.dtype==np.float32
    assert frame.provenance.startswith("APP_DERIVED")
    assert sha256(values.tobytes()).hexdigest()==saved


@pytest.mark.parametrize("count",[3,7,1024,65536])
def test_power_f64_stepwise_against_independent_scalar_path(count):
    rng=np.random.default_rng(0xD2344+count)
    values=np.asarray(rng.normal(size=count),dtype="<f4")
    got=source_stepwise_signal_power_f64(values)
    expected=_f64_stored_power_loop(values)
    assert got==expected
    assert unfiltered_getsignal(values,65536,no_dc=False).rms_value==float(
        np.float32(math.sqrt(expected/count)))


def test_same_original_float32_window_ac_and_fft_remove_identical_dc_once():
    fs=65536
    n=1024
    rng=np.random.default_rng(0xD14B3)
    values=np.asarray(5.125+rng.normal(0.,.25,size=n),dtype="<f4")
    original_sha=sha256(values.tobytes()).hexdigest()
    # GetSignal unfiltered with NoDC=1 has the same 007D2344
    # mean-subtraction source as original GetSpectrum pre-Hann.
    raw=unfiltered_getsignal(values,fs,no_dc=False)
    ac=unfiltered_getsignal(values,fs,no_dc=True)
    direct,mean=mean_center_float32(values)
    assert ac.removed_mean==mean
    assert ac.window_mean==mean
    assert np.array_equal(ac.chronological.view("<u4"),direct.view("<u4"))
    assert np.array_equal(raw.getsignal_buffer,values[::-1])
    assert np.array_equal(ac.getsignal_buffer,ac.chronological[::-1])
    assert raw.rms_value>ac.rms_value
    from_raw,removed=idr_power_spectrum(values,backend="idr_float32")
    from_precentered,precentered_mean=idr_power_spectrum(
        direct,backend="idr_float32",remove_dc=False)
    assert removed==mean
    assert precentered_mean==0.
    assert np.array_equal(
        np.asarray(from_raw,dtype="<f4").view("<u4"),
        np.asarray(from_precentered,dtype="<f4").view("<u4"))
    # Current source DSP candidate still has no Win32 x87 bit oracle.
    assert len(from_raw)==n//2
    assert sha256(values.tobytes()).hexdigest()==original_sha


def test_spectrum_full_power_sum_uses_float64_per_bin_store_without_ui_lag():
    n=262144
    data=np.ones(n//2,dtype="<f4")
    data[3]=np.float32(1e16)
    source_sha=sha256(data.tobytes()).hexdigest()
    model=original_spectrum_summary(
        data,n_fft=n,fs_out=65536.,spectrum_mode=1)
    first,last=model["summary_first_bin"],model["summary_last_bin"]
    total=0.
    for v in data[first:last+1]:
        total=float(total+float(v))
    pairwise=float(np.sum(data[first:last+1].astype(np.float64),
                          dtype=np.float64))
    assert model["raw_total_band_power"]==total
    assert abs(total-pairwise)>1000.
    assert model["power_sum_order"]=="DELPHI_STEPWISE_F64_STORED"
    assert model["original_delphi_numerical_parity_verified"] is False
    assert sha256(data.tobytes()).hexdigest()==source_sha


@pytest.mark.parametrize("bad",[
    np.array([],dtype="<f4"),
    np.array([1.,float("inf")],dtype="<f4"),
    np.array([float("nan")],dtype="<f4"),
    np.ones((2,2),dtype="<f4"),
])
def test_source_rms_rejects_empty_invalid_and_nondimensional(bad):
    with pytest.raises(ValueError):
        source_stepwise_signal_power_f64(bad)
    with pytest.raises(ValueError):
        unfiltered_getsignal(bad,65536,no_dc=False)


def test_original_getsignal_source_finite_indicators_do_not_prove_delphi():
    w=np.array([0.01,-0.02,0.03,-0.04],dtype="<f4")
    f=unfiltered_getsignal(w,65536,no_dc=True)
    assert f.provenance.endswith("IDR_CANDIDATE")
    assert source_stepwise_signal_power_f64(f.chronological)>0
    assert f.getsignal_buffer[0]==f.chronological[-1]
