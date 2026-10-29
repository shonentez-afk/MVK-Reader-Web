"""Stage111E envelope reconstruction: all coefficients are SYNTHETIC and local.

No original IDP or proprietary coefficients are uploaded in the repository.
"""
import math
import numpy as np
import pytest
from mvk_compatible.core.envelope_idr_candidate import (
    EnvelopeProfile,ENVELOPE_RATES,ENVELOPE_STAGES,FIR_TAPS,FIR_DECIM,
    envelope_plan,process_original_envelope_candidate,_fir_step)
from mvk_compatible.core.fft_idr_candidate import mean_center_float32


def fake_profile(*,i=1.,q=0.):
    banks=np.zeros((10,512),dtype=np.float32)
    banks[:,0]=i
    banks[:,1]=q
    return EnvelopeProfile(banks,provenance='SYNTHETIC_QA_COEFFICIENTS')


def test_coefficients_must_not_exist_in_repository():
    import inspect
    import mvk_compatible.core.envelope_idr_candidate as module
    source=inspect.getsource(module)
    assert 'PRIVATE_IDP_SHA256' in source
    assert 'original coefficient' not in source.lower() or 'not' in source.lower()
    assert module._PRIVATE_FIR_FLOAT_COUNT==5120


def test_profile_is_defensive_copy_and_readonly():
    raw=np.zeros((10,512),dtype='f4')
    p=EnvelopeProfile(raw)
    raw[0,0]=123
    assert p.bank(1)[0]==0
    with pytest.raises(ValueError):
        p.bank(1)[0]=42
    with pytest.raises(ValueError):EnvelopeProfile(np.zeros((4,512),dtype='f4'))


@pytest.mark.parametrize('code,fs,stage,prefix,reported',[
    (1,65536,1,388,16384), (2,65536,2,516,16384),
    (4,65536,4,1544,8192), (5,65536,2,561,8192),
    (8,65536,2,605,4096), (11,65536,2,693,2048),
    (20,65536,5,102,32768), (20,20*65536,5,853,32768),
])
def test_original_adjusted_length_address_logic(code,fs,stage,prefix,reported):
    p=envelope_plan(5000,fs,code)
    assert p['stage']==stage
    assert p['history_padding']==prefix
    assert p['adjusted_input_length']==5000+prefix
    assert p['reported_output_rate_hz']==reported


def test_original_ratio_16_is_invalid_not_approximated():
    with pytest.raises(ValueError,match='Invalid sample rate'):
        envelope_plan(2000,65536,14)


@pytest.mark.parametrize('code',[-1,0,32])
def test_invalid_envelope_code(code):
    with pytest.raises(ValueError):envelope_plan(1000,65536,code)


def test_private_idp_loader_rejects_unknown_or_truncated_file(tmp_path):
    file=tmp_path/'nonoriginal.idp'
    file.write_bytes(b'IDR proj v.3'+b'\0'*200)
    with pytest.raises(ValueError,match='fingerprint'):
        EnvelopeProfile.from_original_local_idp(file)


def test_private_coefficients_not_replaceable_with_approximation():
    with pytest.raises(ValueError,match='Private coefficient profile'):
        process_original_envelope_candidate(np.ones(4096,dtype='f4'),65536,1,None)


def test_fir_quadrature_uses_pair_coefficients_and_stored_float32_rounding():
    p=fake_profile(i=1,q=2)
    n=4096
    data=np.arange(n,dtype='f4')
    res=_fir_step(data,1,p,quadrature=True)
    assert len(res)==(n-FIR_TAPS[1])//FIR_DECIM[1]
    assert res.dtype==np.float32
    assert res[0]==pytest.approx(math.sqrt(5)*data[100],rel=2e-7)


def test_float_tap_decimator_read_index_and_output_length():
    p=fake_profile(i=1,q=0)
    data=np.arange(1024,dtype='f4')
    output=_fir_step(data,7,p,quadrature=False)
    assert len(output)==(len(data)-45)//2
    # First decimated sample uses input[(i+1)*2-1 + 45], at i=0 -> 46.
    assert output[0]==46
    assert output[1]==48


def test_envelope_code_one_removes_mean_and_quadrature_magnitude():
    p=fake_profile(i=1,q=2)
    data=(10+np.sin(2*np.pi*64*np.arange(4096)/65536)).astype('f4')
    centered,mean=mean_center_float32(data)
    r=process_original_envelope_candidate(data,65536,1,p,f_range=2)
    assert r['source'].endswith('IDR_PRIVATE_COEFFICIENT_CANDIDATE')
    assert r['profile_source']=='SYNTHETIC_QA_COEFFICIENTS'
    assert r['original_executable_numerical_parity_verified'] is False
    assert len(r['chronological'])==(len(data)-97)//4
    assert r['removed_mean_m_s2']==mean
    assert r['output_sample_rate_hz']==16384
    assert r['chronological'][0]==pytest.approx(2*math.sqrt(5)*abs(float(centered[100])),rel=1e-5)
    np.testing.assert_array_equal(r['getsignal_buffer'],r['chronological'][::-1])
    assert r['rms_m_s2']>=0


def test_stage_two_decimation_then_envelope():
    p=fake_profile(i=1,q=0)
    data=(20+np.arange(2048,dtype='f4')/7).astype('f4')
    centered,_=mean_center_float32(data)
    r=process_original_envelope_candidate(data,65536,5,p,f_range=1)
    assert r['stages_used']==(7,2)
    # Stage7 first output k=132 reads centered[(132+1)*2 -1 +45] = centered[310]
    assert r['chronological'][0]==pytest.approx(abs(float(centered[310])),rel=1e-6)


def test_high_ratio_two_decimators_before_quadrature():
    p=fake_profile(i=1,q=0)
    data=np.arange(4096,dtype='f4')
    r=process_original_envelope_candidate(data,20*65536,20,p)
    assert r['stages_used']==(7,10,5)
    assert r['output_samples']>0
    assert all(np.isfinite(r['chronological']))


def test_envelope_fail_closed_on_short_input_and_nonfinite():
    p=fake_profile()
    with pytest.raises(ValueError,match='Invalid signal length'):
        process_original_envelope_candidate(np.ones(99,dtype='f4'),65536,1,p)
    with pytest.raises(ValueError,match='finite'):
        process_original_envelope_candidate(np.full(1024,np.nan,dtype='f4'),65536,1,p)


def test_invalid_f_range_does_not_silently_rescale():
    with pytest.raises(ValueError):
        process_original_envelope_candidate(np.ones(1000,dtype='f4'),65536,1,fake_profile(),f_range=0)
