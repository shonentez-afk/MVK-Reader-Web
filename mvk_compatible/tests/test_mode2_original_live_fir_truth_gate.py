"""Integrated original Mode2 live FIR truth, provenance and FRange contract.

Source three-way verification was performed offline with original IDP,
Projects.7z Pascal and mvk_idr(1).sqlite. Tests contain NO private FIR
coefficients or proprietary measurement data. They do not claim 1:1 parity.
"""
from __future__ import annotations

import numpy as np
import pytest

from mvk_compatible.core.original_live_envelope_provenance import (
    active_live_envelope_gate,original_live_envelope_provenance,
)
from mvk_compatible.core.storage_f_range_idr_candidate import (
    prepare_original_fft_input,
)


def _evidence(code=20,n_fft=4096,rate=65536,available=1<<21,
              profile=True,ring=True):
    return original_live_envelope_provenance(
        envelope_code=code,n_fft=n_fft,sample_rate_hz=rate,
        profile_available=profile,
        source_ring_verified=ring,available_elements=available)


def test_source_fir_length_vs_inverse_not_a_verified_identical_runtime():
    # _Unit115.pas:007D1158 uses N + taps*Fs/target, NOT taps*decim.
    # bSpecLines N=4096 is BEFORE FIR; after Code20 FFT N=2048.
    # The independent inverse MUST use 2048, not input 4096.
    code20=_evidence()
    assert code20["source_get_adjusted_envelope_length_samples"]==4147
    assert code20["research_inverse_exact_fft_n_history_samples"]==4147
    assert code20["source_filtered_sample_count_candidate"]==2048
    assert code20["source_post_fir_fft_n"]==2048
    assert code20["source_post_fir_fft_df_hz"]==16.
    assert code20["original_and_candidate_window_lengths_identical"]
    assert code20["reason_code"]=="ORIGINAL_FIR_NUMERICAL_PARITY_UNVERIFIED"
    assert code20["local_fir_candidate_can_compute"]
    assert not code20["live_original_fir_result_verified"]
    assert not code20["may_render_plain_fft_as_original_envelope"]
    assert code20["device_command_sent"] is False
    # For stage6 at ratio=1, the source and inverse happen to coincide.
    # Even then a matching N is not proof of Delphi I/Q/x87 parity.
    code26=_evidence(code=26)
    assert code26["source_get_adjusted_envelope_length_samples"]==4145
    assert code26["research_inverse_exact_fft_n_history_samples"]==4145
    assert code26["source_filtered_sample_count_candidate"]==4096
    assert code26["original_and_candidate_window_lengths_identical"]
    assert not code26["live_original_fir_result_verified"]


def test_fir_gate_fails_closed_when_private_idp_or_source_ring_unavailable():
    assert _evidence(profile=False)["reason_code"]=="LOCAL_ORIGINAL_FIR_PROFILE_REQUIRED"
    assert _evidence(ring=False)["reason_code"]=="SOURCE_GO_RING_NOT_VERIFIED"
    assert _evidence(available=4146)["reason_code"]=="SOURCE_FIR_HISTORY_INCOMPLETE"
    assert _evidence(available=4147)["reason_code"]==(
        "ORIGINAL_FIR_NUMERICAL_PARITY_UNVERIFIED")
    assert active_live_envelope_gate(
        kind="GetSpectrum",code=0,n_fft=4096,sample_rate_hz=None,
        profile_available=False,source_ring_verified=False) is None
    assert active_live_envelope_gate(
        kind="GetSpectrum",code=20,n_fft=4096,sample_rate_hz=None,
        profile_available=True,source_ring_verified=False
    )["reason_code"]=="CURRENT_ADC_SOURCE_RATE_MISSING"
    wave=active_live_envelope_gate(
        kind="GetSignal",code=20,n_fft=0,sample_rate_hz=65536,
        profile_available=True,source_ring_verified=True,
        available_elements=262144)
    assert wave["reason_code"]=="ORIGINAL_GETSIGNAL_POST_FIR_WINDOW_UNVERIFIED"
    assert wave["may_render_plain_fft_as_original_envelope"] is False
    for bad in (True,-1,0,32,"20"):
        with pytest.raises(ValueError):
            _evidence(code=bad)
    for bad in (0,512,2048,1000,262145,True):
        with pytest.raises(ValueError):
            _evidence(n_fft=bad)
    for bad in (0,1024,16000,65537,False):
        with pytest.raises(ValueError):
            _evidence(rate=bad)
    with pytest.raises(ValueError,match="target rate"):
        _evidence(code=20,rate=8192)
    for bad in (-1,2**21+1,True):
        with pytest.raises(ValueError):
            _evidence(available=bad)
    with pytest.raises(ValueError,match="Unsupported"):
        active_live_envelope_gate(
            kind="Other",code=20,n_fft=4096,sample_rate_hz=65536,
            profile_available=True,source_ring_verified=True)


def test_original_float_storage_and_calibrated_bin_are_not_equivalent_frange():
    # _Unit115:007D23D5 multiplies stored Float32 when ApplyRange,
    # GetSpectrum:007D14A5 divides original storage by FRange.
    # Go CALIBRATED_NATIVE_R6_BIN_SPOOL is NOT source-proven to be that
    # original Delphi storage. These two input domains must not mix.
    observed=np.array([0.125,2.5,-3.0,16.0],dtype="<f4")
    as_calibrated=prepare_original_fft_input(
        observed,f_range=4.0,input_domain="calibrated_bin")
    as_original=prepare_original_fft_input(
        observed,f_range=4.0,input_domain="original_float_storage")
    assert np.array_equal(as_calibrated["samples_before_dc_removal"],observed)
    np.testing.assert_array_equal(
        as_original["samples_before_dc_removal"],
        np.asarray(observed/np.float32(4.0),dtype="<f4"))
    assert not as_calibrated["original_storage_read_divided_by_range"]
    assert as_original["original_storage_read_divided_by_range"]
    assert not as_original["original_source_buffer_provenance_verified"]
    assert not as_calibrated["calibrated_native_bin_is_original_storage_verified"]
