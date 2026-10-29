"""Stage111H — offline synthetic QA, GetNarrowbandValue and GetNoisePeak."""
import math
import numpy as np
import pytest

from mvk_compatible.core.narrowband_idr_candidate import (
    narrowband_from_full_power, narrowband_from_samples,
    SOURCE, NOISE_SOURCE
)


def power(n=1024):
    return np.zeros(n//2,dtype=np.float32)


def test_narrowband_center_radius_and_float32_power_sum():
    p=power()
    p[49:52]=[2.,6.,4.]
    res=narrowband_from_full_power(p,n_fft=1024,sample_rate_hz=32768,
                                   input_frequency_hz=1600.)
    assert res['source']==SOURCE
    assert res['center_bin']==50
    assert res['radius_bins']==1
    assert (res['band_first_bin'],res['band_last_bin'])==(49,51)
    assert res['band_power_sum']==12.
    assert res['weighted_center_bin']==pytest.approx(
        (49*2+50*6+51*4)/12,rel=1e-6)
    assert res['output_value']==pytest.approx(math.sqrt(6)/512,rel=1e-6)
    assert res['output_peak_y']==0.
    assert not res['original_delphi_numerical_parity_verified']


def test_original_round_nearest_even_and_radius_minimum_one():
    p=power()
    a=narrowband_from_full_power(p,n_fft=1024,sample_rate_hz=32768,
                                 input_frequency_hz=81.*32.) 
    assert a['center_bin']==81
    assert a['radius_bins']==1
    # Half-bin exactly midway: Delphi @ROUND follows nearest-even.
    b=narrowband_from_full_power(p,n_fft=1024,sample_rate_hz=32768,
                                 input_frequency_hz=80.5*32.)
    assert b['center_bin']==80


def test_noise_search_excludes_reference_frequency_neighborhood():
    p=power()
    p[49:52]=[4,20,6]
    p[89:92]=[2,8,3]
    r=narrowband_from_full_power(p,n_fft=1024,sample_rate_hz=32768,
                                 input_frequency_hz=50*32.,
                                 get_noise_peak=True)
    assert r['source']==NOISE_SOURCE
    assert r['center_bin']==50
    assert (r['noise_scan_first_bin'],r['noise_scan_last_bin'])==(20,128)
    assert (r['noise_excluded_first_bin'],r['noise_excluded_last_bin'])==(30,70)
    # Three-bin sliding sum is equal for 89,90,91? At 90 it is maximum 13.
    assert r['output_peak_x_bin']==90
    assert r['noise_raw_three_bin_power']==13
    assert r['output_peak_y']==pytest.approx(math.sqrt(13/2)/512,rel=1e-6)
    assert r['output_peak_frequency_hz']==90*32
    assert r['output_value']>0  # reference band independent from noise peak


def test_noise_scan_exclusive_bounds_and_first_tie_wins():
    p=power()
    p[29]=1000  # just outside exclusion; first eligible window 28/29 may win
    p[90]=8
    res=narrowband_from_full_power(p,n_fft=1024,sample_rate_hz=32768,
                                  input_frequency_hz=50*32,get_noise_peak=True)
    assert res['noise_excluded_first_bin']==30
    assert res['output_peak_x_bin']==28
    # If peaks tie, the first scanned window retains selection.
    p[:]=0
    p[90]=p[110]=8
    res=narrowband_from_full_power(p,n_fft=1024,sample_rate_hz=32768,
                                  input_frequency_hz=50*32,get_noise_peak=True)
    assert res['output_peak_x_bin']==89


def test_noise_zero_power_returns_all_zero_peak_fields():
    r=narrowband_from_full_power(power(),n_fft=1024,sample_rate_hz=32768,
                                 input_frequency_hz=100*32.,get_noise_peak=True)
    assert r['output_value']==0
    assert r['output_peak_x_bin']==r['output_peak_y']==0
    assert r['output_peak_frequency_hz']==0


def test_output_scaling_without_recalibrating_raw_power():
    p=power()
    p[49:52]=[2.,6.,4.]
    a=narrowband_from_full_power(p,n_fft=1024,sample_rate_hz=32768,
                                 input_frequency_hz=1600.,f_range=1.)
    b=narrowband_from_full_power(p,n_fft=1024,sample_rate_hz=32768,
                                 input_frequency_hz=1600.,f_range=6.)
    assert b['output_value']==pytest.approx(a['output_value']*6,rel=1e-6)
    assert b['center_bin']==a['center_bin']


def test_center_outside_original_range_rejected():
    for f in (0., 32768., 70000., -100., 1e30):
        with pytest.raises(ValueError):
            narrowband_from_full_power(power(),n_fft=1024,
               sample_rate_hz=32768,input_frequency_hz=f)


def test_memory_unsafe_upper_edge_candidate_refused():
    # Delphi center may be valid yet center+radius exceed N/2; avoid OOB.
    p=power()
    with pytest.raises(ValueError,match='outside FFT'):
        narrowband_from_full_power(p,n_fft=1024,sample_rate_hz=32768,
                                   input_frequency_hz=510*32.)


@pytest.mark.parametrize('bad',[np.nan,np.inf,-1])
def test_nonfinite_or_negative_fft_power_rejected(bad):
    p=power();p[40]=bad
    with pytest.raises(ValueError,match='finite nonnegative'):
        narrowband_from_full_power(p,n_fft=1024,sample_rate_hz=32768,
                                   input_frequency_hz=1600.)


@pytest.mark.parametrize('invalid',[0,-10,float('nan'),float('inf')])
def test_invalid_rate_refused(invalid):
    with pytest.raises(ValueError):
        narrowband_from_full_power(power(),n_fft=1024,
                                   sample_rate_hz=invalid,input_frequency_hz=1600.)


def test_fft_samples_path_nonzero_and_preserves_user_signal():
    fs=65536
    n=4096
    times=np.arange(n,dtype=np.float64)/fs
    x=np.asarray(4+np.sin(2*np.pi*64*times),dtype=np.float32)
    baseline=x.copy()
    a=narrowband_from_samples(x,sample_rate_hz=fs,input_frequency_hz=64.,
                              backend='numpy')
    assert a['center_bin']==4 and a['radius_bins']==1
    assert a['output_value']>0.
    assert a['removed_mean_m_s2']==pytest.approx(4,rel=1e-5)
    np.testing.assert_array_equal(x,baseline)
    assert a['fft_backend']=='numpy'
    assert not a['raw_archive_position_parity_verified']


def test_noise_uses_same_raw_spectrum_window_as_narrowband():
    p=power();p[49:52]=[2,6,4];p[89:92]=[2,8,3]
    a=narrowband_from_full_power(p,n_fft=1024,sample_rate_hz=32768,
                                 input_frequency_hz=1600)
    b=narrowband_from_full_power(p,n_fft=1024,sample_rate_hz=32768,
                                 input_frequency_hz=1600,get_noise_peak=True)
    assert a['output_value']==b['output_value']
    assert a['band_power_sum']==b['band_power_sum']
    assert a['output_peak_y']==0 and b['output_peak_y']>0


def test_decimated_curve_cannot_replace_full_power_fft():
    with pytest.raises(ValueError,match='Complete'):
        narrowband_from_full_power(np.ones(100,dtype='f4'),n_fft=1024,
                                   sample_rate_hz=32768,input_frequency_hz=1600.)


@pytest.mark.parametrize('invalid', [0, 123, 500000])
def test_invalid_fft_n_rejected(invalid):
    with pytest.raises(ValueError):
        narrowband_from_full_power(power(),n_fft=invalid,
                                   sample_rate_hz=32768,input_frequency_hz=1600.)
