"""Fail-closed live original FIR provenance for IP -> Measure -> Stop.

Private evidence cross-checked in all three sources (not embedded):
  mvkview.idp: TMvkChannelStorage params, FIR bank tables and code metadata;
  Projects.7z/_Unit115.pas 007D1158, 007D1C48, 007D1D50, 007D1E70;
  mvk_idr(1).sqlite: function/call addresses and exact source lines.

Critical: original bSpecLines N is PRE-FIR. GetAdjustedEnvelopeLength
and the inverse FIR recurrence agree only if the latter uses POST-FIR
FFT N. A plain FFT of the source raw ring is NOT its envelope spectrum.

This module is pure: no original IDP bytes, no network, hardware, Qt,
private FIR coefficients, generated samples, files or side effects.
"""
from __future__ import annotations

from .envelope_idr_candidate import ENVELOPE_RATES
from .envelope_spectrum_idr_candidate import (
    required_original_history, source_selected_envelope_fft_plan,
)

_ORIGINAL_FFT_LENGTHS=frozenset((1024,4096,8192,16384,32768,65536,131072,262144))
_ORIGINAL_SAMPLE_RATES=frozenset((512,2048,8192,32768,65536))
_ORIGINAL_RING_ELEMENTS=1<<21
SOURCE="MVK_ORIGINAL_SOURCE_FIR_LIVE_PREPARATION_007D1158_007D1C48_007D1E70"


def original_live_envelope_provenance(*, envelope_code:int,
                                      n_fft:int, sample_rate_hz:int,
                                      profile_available:bool,
                                      source_ring_verified:bool,
                                      available_elements:int) -> dict:
    """Describe original-vs-candidate histories, never authorize unfiltered FFT.

    Required_history_candidate is a mathematical inverse FIR recurrence
    that produces exactly N candidate outputs, *not* a verified Delphi
    GetSpectrum request. The original additive request is exposed
    separately so they cannot silently be treated as interchangeable.
    """
    if (type(envelope_code) is not int or not 1<=envelope_code<=31 or
        type(n_fft) is not int or n_fft not in _ORIGINAL_FFT_LENGTHS or
        type(sample_rate_hz) is not int or
        sample_rate_hz not in _ORIGINAL_SAMPLE_RATES or
        type(profile_available) is not bool or
        type(source_ring_verified) is not bool or
        type(available_elements) is not int or
        not 0<=available_elements<=_ORIGINAL_RING_ELEMENTS):
        raise ValueError("Invalid original live FIR code/N/Fs/provenance")
    # The actual original menu cannot select a filter above Fs.
    if ENVELOPE_RATES[envelope_code]>sample_rate_hz:
        raise ValueError("Original FIR target rate exceeds the current ADC Fs")
    source=source_selected_envelope_fft_plan(
        n_fft,sample_rate_hz,envelope_code)
    post=source["post_fir_fft_n"]
    source_n=source["source_getadjusted_length_samples"]
    # The inverse must use the actual POST-FIR N, not the user's
    # selected PRE-FIR bSpecLines. This is source-confirmed by the
    # mutations of Params.Count at 007D1C48 and 007D1E70.
    if post>=1024:
        inverse=required_original_history(post,sample_rate_hz,envelope_code)
        candidate_n=inverse["input_samples"]
    else:
        candidate_n=source_n  # same per-stage reverse already checked
    if source_n!=candidate_n:
        raise ValueError("Source original FIR window and inverse disagree")
    if not profile_available:
        reason="LOCAL_ORIGINAL_FIR_PROFILE_REQUIRED"
    elif not source_ring_verified:
        reason="SOURCE_GO_RING_NOT_VERIFIED"
    elif source_n>_ORIGINAL_RING_ELEMENTS:
        reason="SOURCE_FIR_HISTORY_EXCEEDS_2M_RING"
    elif available_elements<source_n:
        reason="SOURCE_FIR_HISTORY_INCOMPLETE"
    elif post<1024:
        reason="SOURCE_POST_FIR_FFT_BELOW_ACCEPTED_MODEL_N"
    else:
        reason="ORIGINAL_FIR_NUMERICAL_PARITY_UNVERIFIED"
    return {
        "source":SOURCE,
        "envelope_code":envelope_code,
        "sample_rate_hz":sample_rate_hz,
        "source_target_rate_hz":ENVELOPE_RATES[envelope_code],
        "requested_fft_n":n_fft,
        "source_get_adjusted_envelope_length_samples":source_n,
        "source_filtered_sample_count_candidate":post,
        "source_post_fir_fft_n":post,
        "source_post_fir_fft_df_hz":source["post_fir_df_hz"],
        "research_inverse_exact_fft_n_history_samples":candidate_n,
        "original_and_candidate_window_lengths_identical":source_n==candidate_n,
        "source_original_params_count_proven":True,
        "source_fir_stages":source["source_fir_stage_lengths"],
        "ring_available_elements":available_elements,
        "ring_capacity_elements":_ORIGINAL_RING_ELEMENTS,
        "full_local_profile_available":profile_available,
        "source_ring_verified":source_ring_verified,
        "reason_code":reason,
        "may_render_plain_fft_as_original_envelope":False,
        "local_fir_candidate_can_compute":(
            reason=="ORIGINAL_FIR_NUMERICAL_PARITY_UNVERIFIED"),
        "live_original_fir_result_verified":False,
        "original_x87_fir_fft_and_frange_parity_verified":False,
        "source_calibrated_bin_not_proven_original_f_range":True,
        "device_command_sent":False,
    }


def active_live_envelope_gate(*, kind:str, code:int, n_fft:int,
                              sample_rate_hz:int|None,
                              profile_available:bool,
                              source_ring_verified:bool,
                              available_elements:int=0)->dict|None:
    """Return None only for explicitly unfiltered Tag0.

    For Tag1..31, fail closed with a bounded, source-backed explanation.
    No caller may substitute unfiltered GetSignal/GetSpectrum for FIR.
    """
    if kind not in ("GetSignal","GetSpectrum") or type(code) is not int:
        raise ValueError("Unsupported original live FIR request")
    if code==0:
        return None
    if type(sample_rate_hz) is not int:
        return {
            "reason_code":"CURRENT_ADC_SOURCE_RATE_MISSING",
            "source":SOURCE,
            "may_render_plain_fft_as_original_envelope":False,
            "live_original_fir_result_verified":False,
            "device_command_sent":False,
        }
    if kind=="GetSignal":
        # GetSignal uses a time-domain HTag, not bSpecLines. Do not
        # pretend n_fft describes its post-FIR array. The original
        # GetSignal path 007D0C30/007D1158 requires separate end-position
        # and return-order acceptance before live plotting.
        if (not 1<=code<=31 or sample_rate_hz not in
                _ORIGINAL_SAMPLE_RATES or
                ENVELOPE_RATES[code]>sample_rate_hz):
            raise ValueError("Invalid original GetSignal FIR code/source Fs")
        return {
            "source":SOURCE,
            "envelope_code":code,
            "sample_rate_hz":sample_rate_hz,
            "reason_code":(
                "LOCAL_ORIGINAL_FIR_PROFILE_REQUIRED"
                if not profile_available else
                "SOURCE_GO_RING_NOT_VERIFIED"
                if not source_ring_verified else
                "ORIGINAL_GETSIGNAL_POST_FIR_WINDOW_UNVERIFIED"),
            "ring_available_elements":available_elements,
            "may_render_plain_fft_as_original_envelope":False,
            "live_original_fir_result_verified":False,
            "device_command_sent":False,
        }
    return original_live_envelope_provenance(
        envelope_code=code,n_fft=n_fft,sample_rate_hz=sample_rate_hz,
        profile_available=profile_available,
        source_ring_verified=source_ring_verified,
        available_elements=available_elements)
