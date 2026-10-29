"""Stage111F synthetic regression: original envelope -> full FFT. NO production samples."""
import math
import numpy as np
import pytest
from mvk_compatible.core.envelope_spectrum_idr_candidate import (
    SOURCE, required_original_history, envelope_spectrum_idr_candidate)
from mvk_compatible.core.fft_idr_candidate import idr_power_spectrum
from mvk_compatible.tests.test_envelope_idr_candidate import fake_profile


@pytest.mark.parametrize('code,n,expected,fs_out,stages',[
    (1,1024,4193,16384,(1,)),
    (20,1024,2099,32768,(5,)),
    (20,2048,4147,32768,(5,)),
    (5,1024,4399,8192,(7,2))
])
def test_fir_exact_inverse_length(code,n,expected,fs_out,stages):
    plan=required_original_history(n,65536,code)
    assert plan['input_samples']==expected
    assert plan['output_sample_rate_hz']==fs_out
    assert plan['stages']==stages
    assert plan['original_window_selection_verified'] is False


def test_envelope_fft_never_removes_dc_twice():
    n=1024
    x=np.ones(n,dtype='f4')*3.
    detrended,removed=idr_power_spectrum(x,backend='numpy')
    untouched,removed2=idr_power_spectrum(x,backend='numpy',remove_dc=False)
    assert removed==3 and removed2==0
    assert detrended[0]==0
    assert untouched[0]>1e5
    assert untouched[1]>0


def source_signal(code=20,n_fft=1024):
    plan=required_original_history(n_fft,65536,code)
    t=np.arange(plan['input_samples'])
    return (12.5+1.1*np.sin(2*np.pi*128*t/65536)+.2*np.cos(2*np.pi*512*t/65536)).astype('f4')


@pytest.fixture
def original_like_spectrum():
    return envelope_spectrum_idr_candidate(
        source_signal(),65536,20,fake_profile(i=1.,q=.4),
        n_fft=1024,mode=1,backend='numpy')


def test_envelope_spectrum_exact_size_and_provenance(original_like_spectrum):
    d=original_like_spectrum
    assert d['source']==SOURCE
    assert d['n_fft']==1024 and d['output_samples']==1024
    assert d['source_history_samples']==2099
    assert d['envelope_stages']==(5,)
    assert d['df_hz']==32
    assert d['output_sample_rate_hz']==32768
    assert d['mean_subtraction_count']==1
    assert not d['fft_second_mean_subtraction']
    assert d['raw_mean_removed_m_s2']>12
    assert d['low_bins_zeroed']==2
    assert d['amplitude'][0]==d['amplitude'][1]==0
    assert d['original_delphi_numerical_parity_verified'] is False
    assert d['original_window_selection_verified'] is False
    assert len(d['frequency_hz'])==len(d['amplitude'])==512
    assert all(np.isfinite(d['amplitude']))


@pytest.mark.parametrize('mode',[0,1,2,3])
def test_all_four_delphi_modes_have_finite_full_bins(mode):
    d=envelope_spectrum_idr_candidate(source_signal(),65536,20,
      fake_profile(i=1.,q=.4),n_fft=1024,mode=mode,backend='numpy')
    assert d['power_integration_passes']==max(0,mode-1)
    assert d['frequency_hz'][3]==96
    assert all(np.isfinite(d['amplitude']))
    if mode==0:
        assert d['amplitude'][0]==d['amplitude'][1]==-180.
    else:
        assert d['amplitude'][0]==d['amplitude'][1]==0.


def test_original_007d2164_mode2_integration_per_frequency_bin():
    a=envelope_spectrum_idr_candidate(source_signal(),65536,20,
        fake_profile(i=1.,q=.4),n_fft=1024,mode=1,backend='numpy')
    b=envelope_spectrum_idr_candidate(source_signal(),65536,20,
        fake_profile(i=1.,q=.4),n_fft=1024,mode=2,backend='numpy')
    c=envelope_spectrum_idr_candidate(source_signal(),65536,20,
        fake_profile(i=1.,q=.4),n_fft=1024,mode=3,backend='numpy')
    k=4
    factor=159.154943091895/a['frequency_hz'][k]
    assert b['amplitude'][k]==pytest.approx(a['amplitude'][k]*factor,rel=2e-5)
    assert c['amplitude'][k]==pytest.approx(a['amplitude'][k]*factor**2,rel=2e-5)
    assert (a['unit'],b['unit'],c['unit'])==('м/с²','мм/с','мкм')


def test_float32_backend_and_numpy_peak_close_without_delphi_claim():
    a=envelope_spectrum_idr_candidate(source_signal(),65536,20,
        fake_profile(),n_fft=1024,backend='numpy')
    b=envelope_spectrum_idr_candidate(source_signal(),65536,20,
        fake_profile(),n_fft=1024,backend='idr_float32')
    assert a['original_delphi_numerical_parity_verified'] is False
    peak=int(np.argmax(a['amplitude']))
    assert b['amplitude'][peak]==pytest.approx(a['amplitude'][peak],rel=.005)


def test_original_db_mode_ignores_f_range():
    a=envelope_spectrum_idr_candidate(source_signal(),65536,20,fake_profile(),
        n_fft=1024,mode=0,f_range=1.,backend='numpy')
    b=envelope_spectrum_idr_candidate(source_signal(),65536,20,fake_profile(),
        n_fft=1024,mode=0,f_range=12.,backend='numpy')
    np.testing.assert_allclose(a['amplitude'],b['amplitude'],atol=0,rtol=0)


def test_linear_modes_scale_f_range_only_once():
    a=envelope_spectrum_idr_candidate(source_signal(),65536,20,fake_profile(),
        n_fft=1024,mode=1,f_range=1.,backend='numpy')
    b=envelope_spectrum_idr_candidate(source_signal(),65536,20,fake_profile(),
        n_fft=1024,mode=1,f_range=2.5,backend='numpy')
    k=int(np.argmax(a['amplitude']))
    assert b['amplitude'][k]/a['amplitude'][k]==pytest.approx(2.5,rel=1e-6)


@pytest.mark.parametrize('bad_n',[0,1000,500000])
def test_invalid_fft_sizes_fail_closed(bad_n):
    with pytest.raises(ValueError):
        required_original_history(bad_n,65536,20)


def test_reject_padding_truncation_and_missing_idp_profile():
    exact=source_signal()
    for x in (exact[:-1],np.pad(exact,(0,1))):
        with pytest.raises(ValueError,match='Exact recorded'):
            envelope_spectrum_idr_candidate(x,65536,20,fake_profile(),n_fft=1024)
    with pytest.raises(ValueError,match='EnvelopeProfile'):
        envelope_spectrum_idr_candidate(exact,65536,20,None,n_fft=1024)


def test_bad_modes_f_range_and_nonfinite_rejected():
    x=source_signal()
    with pytest.raises(ValueError):envelope_spectrum_idr_candidate(x,65536,20,fake_profile(),n_fft=1024,mode=4)
    with pytest.raises(ValueError):envelope_spectrum_idr_candidate(x,65536,20,fake_profile(),n_fft=1024,f_range=float('nan'))
    x[30]=np.nan
    with pytest.raises(ValueError):envelope_spectrum_idr_candidate(x,65536,20,fake_profile(),n_fft=1024)


def test_original_getadjustedlength_is_not_inverse_fft_length():
    from mvk_compatible.core.envelope_idr_candidate import envelope_plan
    # Original returns input padded for its caller's REQUESTED input length;
    # our inverse computes input needed for an EXACT post-FIR radix2 N.
    a=envelope_plan(1024,65536,20)
    b=required_original_history(1024,65536,20)
    assert a['adjusted_input_length'] != b['input_samples']
    assert b['input_samples']==2099


def test_input_zero_is_handled_without_approximate_envelope():
    x=np.zeros(required_original_history(1024,65536,20)['input_samples'],dtype='f4')
    out=envelope_spectrum_idr_candidate(x,65536,20,fake_profile(),n_fft=1024,mode=0,backend='numpy')
    assert all(z==-180. for z in out['amplitude'])
