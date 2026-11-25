"""Source-backed PRE-FIR ring -> local original-coefficient FIR/IQ -> FFT.

Three private sources checked OFFLINE: mvkview.idp, Projects.7z Pascal,
and mvk_idr(1).sqlite. These synthetic tests publish no original FIR bank,
Delphi runtime dump, original RAW or PCAP. Numerical Delphi parity false.
"""
from __future__ import annotations
from dataclasses import replace
import numpy as np
import pytest

from mvk_compatible.core.envelope_spectrum_idr_candidate import (
    source_selected_envelope_fft_plan,
    source_selected_envelope_spectrum_candidate,
)
from mvk_compatible.core.envelope_idr_candidate import EnvelopeProfile
from mvk_compatible.core.original_source_long_window import (
    submit_source_envelope_window,load_source_long_window,REQUEST_NAME,
)
from .test_stage111z31fj_original_long_window import (
    long_source_status,response_fixture,
)


@pytest.mark.parametrize("code,pre,post,fs,df",[
    (1,4193,1024,16384,16.),(2,4225,1024,16384,16.),
    (4,4289,512,8192,16.),(5,4399,512,8192,16.),
    (8,4701,256,4096,16.),(11,5305,128,2048,16.),
    (20,4147,2048,32768,16.),(21,4243,1024,16384,16.),
    (26,4145,4096,65536,16.),(27,4239,2048,32768,16.),
])
def test_source_getadjusted_and_actual_post_iq_params_count(
        code,pre,post,fs,df):
    plan=source_selected_envelope_fft_plan(4096,65536,code)
    assert plan["original_bSpecLines_pre_fir_n"]==4096
    assert plan["source_getadjusted_length_samples"]==pre
    assert plan["original_params_count_after_fir"]==post
    assert plan["post_fir_fft_n"]==post
    assert plan["post_fir_sample_rate_hz"]==fs
    assert plan["post_fir_df_hz"]==df
    assert plan["source_params_count_proven_by_pascal"]
    assert not plan["original_runtime_post_fir_float32_verified"]
    assert not plan["original_x87_hann_fft_power_parity_verified"]
    assert plan["source_fir_stage_lengths"][-1]["output_count"]==post


def _synthetic_idp_profile():
    banks=np.zeros((10,512),dtype="<f4")
    # Synthetic complex coefficient pair for source stage5; no
    # original bytes or proprietary impulse response in CI.
    banks[4,0]=np.float32(1.)
    banks[4,1]=np.float32(0.3)
    return EnvelopeProfile(banks,provenance="SYNTHETIC_QA_NOT_ORIGINAL_IDP")


@pytest.mark.parametrize("mode",[0,1,2,3])
def test_real_pre_fir_history_produces_correct_post_iq_fft_for_all_modes(mode):
    plan=source_selected_envelope_fft_plan(4096,65536,20)
    n=plan["source_getadjusted_length_samples"]
    signal=np.asarray(
        np.sin(2*np.pi*230*np.arange(n,dtype=np.float64)/65536)
        +0.3*np.sin(2*np.pi*1500*np.arange(n,dtype=np.float64)/65536),
        dtype="<f4")
    original_input=signal.tobytes()
    outcome=source_selected_envelope_spectrum_candidate(
        signal,65536,20,_synthetic_idp_profile(),
        selected_bspec_lines_n=4096,mode=mode,
        backend="numpy",f_range=1.,input_domain="calibrated_bin")
    assert original_input==signal.tobytes()
    assert outcome["source_bSpecLines_pre_fir_n"]==4096
    assert outcome["n_fft"]==2048
    assert outcome["df_hz"]==16.
    assert outcome["source_history_samples"]==4147
    assert outcome["pre_fft_envelope_samples"]==2048
    assert outcome["mean_subtraction_count"]==1
    assert outcome["fft_second_mean_subtraction"] is False
    assert outcome["source_verified_go_ring_required"]
    assert outcome["calibrated_go_ring_input"]
    assert not outcome["original_delphi_numerical_parity_verified"]
    assert len(outcome["frequency_hz"])==1024
    assert len(outcome["amplitude"])==1024
    assert np.all(np.isfinite(outcome["amplitude"]))
    assert outcome["spectrum_summary"]


def test_source_fir_refuses_missing_extra_samples_or_reinterpreting_bspec_lines():
    signal=np.ones(4096,dtype="<f4")
    profile=_synthetic_idp_profile()
    with pytest.raises(ValueError,match="Exact source"):
        source_selected_envelope_spectrum_candidate(
            signal,65536,20,profile,selected_bspec_lines_n=4096)
    # The original Delphi FFT accepts power-of-two N>=2 after FIR;
    # Code4 bSpecLines4096 yields POST-FIR N512. Former research guard
    # rejected this genuine result for an unrelated >=1024 constraint.
    small=source_selected_envelope_spectrum_candidate(
        np.ones(4289,dtype="<f4"),65536,4,profile,
        selected_bspec_lines_n=4096)
    assert small["n_fft"]==512
    assert small["source_history_samples"]==4289
    assert len(small["amplitude"])==256
    assert small["original_delphi_numerical_parity_verified"] is False
    assert source_selected_envelope_fft_plan(4096,65536,24)["post_fir_fft_n"]==128
    assert source_selected_envelope_fft_plan(1024,65536,19)["post_fir_fft_n"]==4
    with pytest.raises(ValueError,match="Invalid sample rate"):
        source_selected_envelope_fft_plan(4096,512,24)
    for bogus in (0,True,512,2048,1000,262145):
        with pytest.raises(ValueError):
            source_selected_envelope_fft_plan(bogus,65536,20)


def test_sha_verified_real_go_pre_fir_source_window_and_metadata_binding(tmp_path):
    root,status=long_source_status(tmp_path)
    req=submit_source_envelope_window(root,status,1,4096,20,
        request_id="abcdabcdabcdabcdabcdabcdabcdabcd")
    assert req is not None
    assert req.h_tag==-2 and req.envelope_code==20
    assert req.original_bspec_lines==4096 and req.samples==4147
    assert load_source_long_window(root,status,req) is None
    payload=response_fixture(root,status,req)
    window=load_source_long_window(root,status,req)
    assert window is not None and window.preview.source_ring_provenance_verified
    ch=window.preview.channels[1]
    assert len(ch.samples)==4147
    assert ch.samples[0]==0 and ch.samples[-1]==4146
    assert payload==ch.samples.tobytes()
    assert window.received_samples==req.capture_end
    # Original operator cannot attach an old Code21 / bSpecLines-N ZIP
    # to the current Code20 UI even if the Float32 SHA is intact.
    response_fixture(root,status,req,
        override=lambda m:m.update(envelope_code=21))
    with pytest.raises(ValueError,match="malformed source window"):
        load_source_long_window(root,status,req)
    response_fixture(root,status,req,
        override=lambda m:m.update(original_bspec_lines=8192))
    with pytest.raises(ValueError,match="malformed source window"):
        load_source_long_window(root,status,req)
    with pytest.raises(ValueError):
        submit_source_envelope_window(root,status,1,4096,0)
    with pytest.raises(ValueError):
        submit_source_envelope_window(root,status,1,4096,32)
    status["source_original_storage"]["channels"][0]["available_elements"]=4146
    assert submit_source_envelope_window(root,status,1,4096,20) is None
