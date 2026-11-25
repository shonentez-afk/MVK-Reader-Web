"""Source hex ratio and complete supported menu matrix; synthetic no hardware."""
import numpy as np
import pytest
from ..core.envelope_idr_candidate import (
    EnvelopeProfile, ENVELOPE_RATES, ENVELOPE_STAGES, FIR_TAPS, FIR_DECIM,
    envelope_plan,process_original_envelope_candidate)
from ..core.envelope_spectrum_idr_candidate import (
    source_selected_envelope_fft_plan,source_selected_envelope_spectrum_candidate)
from ..core.storage_f_range_idr_candidate import DOMAIN_ORIGINAL_STORAGE
from ..core.original_adc_view_controls import ADC_HORIZONTAL_MS
from ..core.tqgrapher_display_idr_candidate import spectrum_display_contract

RATES=(512,2048,8192,32768,65536)
PAIRS=tuple((fs,code) for fs in RATES for code in range(1,32)
            if ENVELOPE_RATES[code]<=fs)
LENGTHS=(1024,4096,8192,16384,32768,65536,131072,262144)

def test_complete_menu_and_source_window_arithmetic():
    assert len(PAIRS)==76
    for fs,code in PAIRS:
        target=ENVELOPE_RATES[code]
        ratio=fs//target
        stage=ENVELOPE_STAGES[code]
        for selected in LENGTHS:
            plan=source_selected_envelope_fft_plan(selected,fs,code)
            post=selected//ratio//FIR_DECIM[stage]
            assert plan["post_fir_fft_n"]==post
            assert plan["post_fir_sample_rate_hz"]==target//FIR_DECIM[stage]
            assert plan["post_fir_df_hz"]==fs/selected
            # Independent inversion of actual decimator stages from source.
            pre=post*FIR_DECIM[stage]+FIR_TAPS[stage]
            if ratio>=32:
                pre=pre*16+353
            first={1:0,2:7,4:8,8:9,16:10,32:7}[ratio]
            if first:
                pre=pre*FIR_DECIM[first]+FIR_TAPS[first]
            assert pre==plan["source_getadjusted_length_samples"]
        for ms in ADC_HORIZONTAL_MS:
            selected=fs*ms//1000
            if selected:
                w=envelope_plan(selected,fs,code)
                assert w["post_fir_output_samples"]==selected//ratio//FIR_DECIM[stage]
    assert len(PAIRS)*len(LENGTHS)==608

@pytest.mark.parametrize("fs,code",PAIRS)
def test_every_filter_rate_with_nonunit_storage_and_four_modes(fs,code):
    bank=np.zeros((10,512),dtype=np.float32)
    bank[:,0]=1.
    bank[:6,1]=.25
    profile=EnvelopeProfile(bank,provenance="SYNTHETIC_QA_NOT_ORIGINAL_IDP")
    selected=1024
    plan=source_selected_envelope_fft_plan(selected,fs,code)
    n=plan["source_getadjusted_length_samples"]
    raw=((np.arange(n,dtype=np.int64)%61)-30).astype(np.float32)/32
    stored=(raw*2.5).astype(np.float32)
    before=stored.tobytes()
    for mode in range(4):
        common=dict(selected_bspec_lines_n=selected,mode=mode,backend="idr_float32",
                    input_domain=DOMAIN_ORIGINAL_STORAGE)
        a=source_selected_envelope_spectrum_candidate(raw,fs,code,profile,
                                                     f_range=1.0,**common)
        b=source_selected_envelope_spectrum_candidate(stored,fs,code,profile,
                                                     f_range=2.5,**common)
        assert b["pre_fir_read_float32_sha256"]==a["pre_fir_read_float32_sha256"]
        assert b["pre_fft_envelope_float32_sha256"]==a["pre_fft_envelope_float32_sha256"]
        assert len(b["amplitude"])==plan["post_fir_fft_n"]//2
        assert b["df_hz"]==fs/selected
        np.testing.assert_allclose(b["amplitude"],np.asarray(a["amplitude"])*(1 if mode==0 else 2.5),
                                   rtol=2e-6,atol=1e-9)
        assert b["spectrum_summary"]["output_mean"]==pytest.approx(
            a["spectrum_summary"]["output_mean"]*2.5,rel=2e-6,abs=1e-9)
        assert not b["original_delphi_numerical_parity_verified"]
    assert before==stored.tobytes()
    # GetSignal runs the same FIR on normalized chronological history,
    # with exact reversal and non-unit output scale.
    signal=process_original_envelope_candidate(raw,fs,code,profile,f_range=2.5)
    assert signal["output_samples"]==plan["post_fir_fft_n"]
    np.testing.assert_array_equal(signal["getsignal_buffer"],signal["chronological"][::-1])

def test_minimum_real_menu_post_fir_four_samples():
    plan=source_selected_envelope_fft_plan(1024,65536,19)
    assert plan["post_fir_fft_n"]==4
    profile=EnvelopeProfile(np.zeros((10,512),dtype=np.float32),provenance="SYNTHETIC")
    x=np.zeros(plan["source_getadjusted_length_samples"],dtype=np.float32)
    for mode in range(4):
        result=source_selected_envelope_spectrum_candidate(
            x,65536,19,profile,selected_bspec_lines_n=1024,mode=mode)
        assert result["amplitude"]==([-180.,-180.] if mode==0 else [0.,0.])
        summary=result["spectrum_summary"]
        assert summary["source_summary_interval_empty"]
        assert summary["output_mean"]==summary["output_peak_y"]==summary["output_peak_frequency_hz"]==0
    assert spectrum_display_contract(4,256)["grapher_series_bins"]==1
