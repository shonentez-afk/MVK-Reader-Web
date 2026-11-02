"""Stage111Z.22: synthetic validation of independent local original FFT checker."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

from mvk_compatible.core.original_spectrum_independent_check import (
    independent_numpy_hann_power,compare_original_snapshot_pair,REFERENCE_SOURCE
)


def _pair(tmp_path,n=4096):
    i=np.arange(n,dtype=np.float64)
    x=np.asarray(.3*np.sin(2*np.pi*50*i/n)+.04*np.cos(
        2*np.pi*180*i/n),dtype="<f4")
    y=independent_numpy_hann_power(x)
    t=tmp_path/"source-before-fft.bin"
    p=tmp_path/"source-after-power.bin"
    t.write_bytes(x.tobytes())
    p.write_bytes(y.tobytes())
    return t,p,x,y


def test_independent_window_fft_power_synthetic_exact_self_consistency(tmp_path):
    t,p,x,y=_pair(tmp_path)
    d=compare_original_snapshot_pair(t,p,sample_rate_hz=4096)
    assert d["source"]==REFERENCE_SOURCE
    assert d["n_fft"]==4096 and d["power_bins"]==2048
    assert d["original_power_peak_bin"]==50
    assert d["independent_power_peak_bin"]==50
    assert d["peak_frequency_hz"]==50.
    assert d["float32_bit_exact_bins"]==2048
    assert d["within_0_1_percent_bins"]==2048
    assert d["within_1_percent_bins"]==2048
    assert d["relative_error_median"]==0
    assert d["original_float32_radix2_bit_parity_verified"] is False
    assert d["original_bin_to_storage_calibration_verified"] is False
    assert d["original_runtime_gdi_plot_pixel_parity_verified"] is False
    assert d["privacy"]["source_file_paths_in_report"] is False
    assert str(t) not in str(d) and str(p) not in str(d)
    assert d["before_fft_sha256"]!=d["after_power_sha256"]


def test_original_262144_periodic_hann_has_nominal_rms_one():
    n=262144
    indices=np.arange(n,dtype=np.float64)
    w=(1.-np.cos(2*np.pi*indices/n))/np.sqrt(1.5)
    assert abs(float(np.mean(w*w))-1.)<1e-14
    assert w[0]==pytest.approx(0)
    assert w[n//2]==pytest.approx(2/np.sqrt(1.5))
    assert w[-1]>0


def test_wrong_half_size_rejected(tmp_path):
    t,p,_,_=_pair(tmp_path)
    p.write_bytes(p.read_bytes()[:-4])
    with pytest.raises(ValueError,match="NFFT/2"):
        compare_original_snapshot_pair(t,p)


def test_zero_placeholder_x32dbg_snapshots_rejected(tmp_path):
    t,p,_,_=_pair(tmp_path)
    t.write_bytes(bytes(t.stat().st_size))
    with pytest.raises(ValueError,match="нулевой"):
        compare_original_snapshot_pair(t,p)
    t,p,_,_=_pair(tmp_path)
    p.write_bytes(bytes(p.stat().st_size))
    with pytest.raises(ValueError,match="нулевой"):
        compare_original_snapshot_pair(t,p)


def test_symmetric_nonfinite_and_negative_power_rejected(tmp_path):
    t,p,x,y=_pair(tmp_path)
    x[100]=np.float32(np.nan)
    t.write_bytes(x.tobytes())
    with pytest.raises(ValueError,match="NaN/Inf"):
        compare_original_snapshot_pair(t,p)
    t,p,x,y=_pair(tmp_path)
    y[7]=-1
    p.write_bytes(y.tobytes())
    with pytest.raises(ValueError,match="отрицательной"):
        compare_original_snapshot_pair(t,p)


@pytest.mark.parametrize("rate",[0,-1,65536.5,True,"65536",1_000_001])
def test_reject_unverified_sampling_rate(tmp_path,rate):
    t,p,_,_=_pair(tmp_path)
    with pytest.raises(ValueError,match="Частота отсчётов"):
        compare_original_snapshot_pair(t,p,sample_rate_hz=rate)


def test_symlink_is_not_followed(tmp_path):
    t,p,_,_=_pair(tmp_path)
    alias=tmp_path/"shortcut.bin"
    try:alias.symlink_to(t)
    except (OSError,NotImplementedError):pytest.skip("Symlink unavailable")
    with pytest.raises(ValueError,match="symlink"):
        compare_original_snapshot_pair(alias,p)


def test_input_signal_does_not_change_when_window_and_fft_are_evaluated(tmp_path):
    t,p,x,y=_pair(tmp_path)
    snapshot=x.tobytes()
    out=independent_numpy_hann_power(x)
    assert out.shape==(len(x)//2,)
    assert x.tobytes()==snapshot
    assert np.array_equal(out,y)
