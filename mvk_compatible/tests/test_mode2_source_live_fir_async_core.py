"""Whole source-backed LIVE filtered GetSignal DSP/LOD/cursor contract.

Synthetic ADC and FIR coefficients only. No original private data,
device commands, or claim of Delphi x87/pixel parity. The one real Go
2**21-ring selector and its SHA/HTag receipt are exercised first.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import numpy as np
import pytest

from mvk_compatible.core.original_source_long_window import (
    submit_source_getsignal_envelope_window,load_source_long_window,
)
from mvk_compatible.core.envelope_idr_candidate import (
    EnvelopeProfile,envelope_plan,
)
from mvk_compatible.core.original_live_getsignal_fir_processing import (
    source_live_filtered_getsignal,source_live_filtered_cursor,
)
from .test_stage111z31fj_original_long_window import (
    long_source_status,response_fixture,
)


def source_window_and_synthetic_profile(tmp_path):
    root,status=long_source_status(tmp_path)
    req=submit_source_getsignal_envelope_window(
        root,status,1,9,20,
        request_id='0123456789abcdef0123456789abcdef')
    assert req is not None and req.samples==1361
    response_fixture(root,status,req,
        override=lambda meta:meta.update(original_h_tag=9))
    window=load_source_long_window(root,status,req)
    assert window is not None and window.preview.source_ring_provenance_verified
    banks=np.zeros((10,512),dtype='<f4')
    banks[4,0]=1.
    banks[4,1]=.4
    return window,EnvelopeProfile(banks,provenance='SYNTHETIC_QA_NOT_IDP')


def test_source_live_fir_20ms_full_buf_peak_preserving_plot_and_cursor(tmp_path):
    window,profile=source_window_and_synthetic_profile(tmp_path)
    original=window.preview.channels[1].samples.copy()
    result=source_live_filtered_getsignal(
        window,profile,tag=9,code=20,max_plot_points=100)
    assert result['source_pre_fir_samples']==1361
    assert result['output_samples']==655
    assert result['output_rate_hz']==32768
    assert result['plot_points']<=100 and result['plot_points']>1
    assert len(result['full_reversed_getsignal'])==655
    assert not result['full_reversed_getsignal'].flags.writeable
    assert result['source_float32_sha256']==sha256(original.tobytes()).hexdigest()
    assert result['output_float32_sha256']==sha256(
        result['full_reversed_getsignal'].tobytes()).hexdigest()
    assert not result['original_delphi_numerical_parity_verified']
    assert result['calibration_already_applied']
    assert np.array_equal(window.preview.channels[1].samples,original)
    for x in (0.,1.,5.,10.,19.):
        picked=source_live_filtered_cursor(result,x)
        assert picked is not None
        k=picked['output_index']
        assert picked['value_from_full_filtered_float32']==float(
            result['full_reversed_getsignal'][k])
        assert picked['output_float32_sha256']==result['output_float32_sha256']
    assert source_live_filtered_cursor(result,-1) is None
    assert source_live_filtered_cursor(result,21) is None
    # Plot LOD retains the first and final sample and each segment extrema.
    assert result['plot_y'][0]==result['full_reversed_getsignal'][0]
    assert result['plot_y'][-1]==result['full_reversed_getsignal'][-1]
    assert result['plot_y'].max()==result['full_reversed_getsignal'].max()
    assert result['plot_y'].min()==result['full_reversed_getsignal'].min()


def test_source_live_fir_rejects_forged_checksum_or_wrong_htag(tmp_path):
    window,profile=source_window_and_synthetic_profile(tmp_path)
    with pytest.raises(ValueError,match='HTag'):
        source_live_filtered_getsignal(window,profile,tag=8,code=20)
    with pytest.raises(ValueError,match='FIR'):
        source_live_filtered_getsignal(window,profile,tag=9,code=21)
    ch=window.preview.channels[1]
    wrong=replace(ch,sha256='0'*64)
    bad=replace(window,preview=replace(
        window.preview,channels={1:wrong}))
    with pytest.raises(ValueError,match='SHA mismatch'):
        source_live_filtered_getsignal(bad,profile,tag=9,code=20)


def test_source_live_fir_dsp_cancellation_never_returns_partial_output(tmp_path):
    window,profile=source_window_and_synthetic_profile(tmp_path)
    with pytest.raises(InterruptedError):
        source_live_filtered_getsignal(
            window,profile,tag=9,code=20,cancelled=lambda:True)
    checks=[0]
    def after_first_tap():
        checks[0]+=1
        return checks[0]>3
    with pytest.raises(InterruptedError):
        source_live_filtered_getsignal(
            window,profile,tag=9,code=20,cancelled=after_first_tap)
    assert checks[0]>3


def test_source_live_fir_full_20sec_history_fits_original_two_million_ring():
    selected=65536*20000//1000
    plan=envelope_plan(selected,65536,20)
    assert selected==1310720
    assert plan['adjusted_input_length']==1310771
    assert plan['adjusted_input_length']<(1<<21)
    # This history must be selected intact; no 262144-preview downshift,
    # fake zeros or on-GUI 20-second FIR calculation.
    assert plan['adjusted_input_length']-selected==51
    assert (plan['adjusted_input_length']-51)//2==655360


def test_source_live_fir_cursor_rejects_bad_coordinate(tmp_path):
    window,profile=source_window_and_synthetic_profile(tmp_path)
    result=source_live_filtered_getsignal(
        window,profile,tag=9,code=20,max_plot_points=100)
    with pytest.raises(ValueError,match='valid full-data'):
        source_live_filtered_cursor(result,float('nan'))
    with pytest.raises(ValueError,match='valid full-data'):
        source_live_filtered_cursor(result,float('inf'))
    assert source_live_filtered_cursor(result,20.01) is None
