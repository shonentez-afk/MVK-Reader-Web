"""Stage111Z29C1: exact SAME local BIN history through envelope GetSignal/FFT.

All test input/coefficients SYNTHETIC. This verifies local alignment, not
that original Delphi selected this archive end or that x87 matched.
"""
from __future__ import annotations

import hashlib
import numpy as np
import pytest

from mvk_compatible.core.offline_export import OfflineSession
from mvk_compatible.core.getsignal_input_evidence import compare_local_input_windows
from .test_offline_core import fixture_zip
from .test_envelope_idr_candidate import fake_profile


def _pair(tmp_path,f_range=1.):
    session=OfflineSession.open(fixture_zip(tmp_path))
    profile=fake_profile(i=1.,q=.4)
    # source:GetAdjustedEnvelopeLength(code20, desired1997) = 2099,
    # inverse GetSpectrum history(code20,N1024) = 2099.
    wave=session.envelope(
        1,20,start_s=2099/65536,seconds=1997/65536,profile=profile,
        f_range=f_range,display_order='chronological',points=2000)
    fft=session.spectrum_envelope(
        1,20,1024,profile,end_s=4096/65536,
        mode=1,f_range=f_range,backend="numpy")
    return session,profile,wave,fft


def test_getsignal_envelope_and_getspectrum_share_exact_pre_fir_source_window(tmp_path):
    _,_,wave,fft=_pair(tmp_path)
    a=wave["input_source_window"]
    b=fft["input_source_window"]
    assert a["channel"]==b["channel"]==1
    assert a["first_archive_sample_index"]==b["first_archive_sample_index"]==4096-2099
    assert a["last_archive_sample_exclusive"]==b["last_archive_sample_exclusive"]==4096
    assert a["source_sample_count"]==b["source_sample_count"]==2099
    assert a["source_is_native_r6_sha_audited_export"]
    assert compare_local_input_windows(a,b)["same_input_bytes_and_bounds"]
    assert wave["post_fir_unreversed_float32_sha256"]==fft["pre_fft_envelope_float32_sha256"]
    assert fft["pre_fft_envelope_samples"]==wave["output_samples"]==1024
    assert fft["pre_fft_envelope_is_unreversed_chronological"]
    assert wave["original_getsignal_vs_getspectrum_envelope_numeric_parity_verified"] is False
    assert fft["original_pre_fft_envelope_runtime_parity_verified"] is False
    assert not fft["original_archive_position_parity_verified"]
    assert wave["post_fir_getsignal_return_float32_sha256"]!=wave["post_fir_unreversed_float32_sha256"]


def test_original_getsignal_envelope_f_range_scaled_output_not_same_as_pre_fft_input(tmp_path):
    _,_,wave,fft=_pair(tmp_path,f_range=2.5)
    assert compare_local_input_windows(
        wave["input_source_window"],fft["input_source_window"]
    )["same_input_bytes_and_bounds"]
    # GetSignal original envelope multiplies FRange AFTER FIR; the source
    # spectrum candidate passes unscaled I/Q magnitude into Hann/FFT.
    assert wave["post_fir_unreversed_float32_sha256"]!=fft["pre_fft_envelope_float32_sha256"]
    assert fft["f_range_used"]==2.5
    assert fft["original_pre_fft_envelope_runtime_parity_verified"] is False


def test_different_source_history_not_treated_as_equal_by_fft(tmp_path):
    session,profile,wave,fft=_pair(tmp_path)
    other=session.spectrum_envelope(
        1,20,1024,profile,end_s=4095/65536,mode=1,
        f_range=1.,backend="numpy")
    assert other["input_source_window"]["last_archive_sample_exclusive"]==4095
    assert not compare_local_input_windows(
        wave["input_source_window"],other["input_source_window"]
    )["same_input_bytes_and_bounds"]
    assert other["pre_fft_envelope_float32_sha256"]!=fft["pre_fft_envelope_float32_sha256"]


def test_incomplete_envelope_source_never_zero_pads_archive(tmp_path):
    session=OfflineSession.open(fixture_zip(tmp_path))
    profile=fake_profile()
    with pytest.raises(ValueError,match="Insufficient actual BIN history"):
        session.spectrum_envelope(
            1,20,1024,profile,end_s=1000/65536,mode=1)
    with pytest.raises(ValueError,match="no zero-padding"):
        session.envelope(
            1,20,start_s=0,seconds=1997/65536,profile=profile)
