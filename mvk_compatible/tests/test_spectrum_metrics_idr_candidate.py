"""Stage111G: synthetic-only output peak centroid QA against hand-computed cases."""
import math
import numpy as np
import pytest
from mvk_compatible.core.spectrum_metrics_idr_candidate import original_spectrum_summary as measure


def power(n=1024):
    a=np.zeros(n//2,dtype='f4')
    a[98:103]=[2,5,10,3,1]
    return a


def test_peak_centroid_is_not_max_bin():
    d=measure(power(),n_fft=1024,fs_out=32768)
    expected=(98*2+99*5+100*10+101*3+102)/21
    assert d['raw_max_power_bin']==100
    assert d['output_peak_x_bin']==pytest.approx(expected,rel=1e-6)
    assert d['output_peak_frequency_hz']==pytest.approx(expected*32,rel=1e-6)
    assert d['output_peak_y']==pytest.approx(math.sqrt(21/2)/512,rel=1e-6)
    assert d['output_mean']==pytest.approx(math.sqrt(21/2)/512,rel=1e-6)
    assert (d['summary_first_bin'],d['summary_last_bin'])==(2,400)
    assert not d['original_delphi_numerical_parity_verified']


def test_integrated_power_band_excludes_high_nyquist_bins():
    a=power()
    a[401]=1000
    d=measure(a,n_fft=1024,fs_out=32768)
    assert d['raw_max_power_bin']==100
    assert d['raw_total_band_power']==pytest.approx(21.)


def test_first_equal_peak_wins():
    a=np.zeros(512,dtype='f4');a[20]=a[30]=10
    d=measure(a,n_fft=1024,fs_out=32768)
    assert d['raw_max_power_bin']==20
    assert d['output_peak_x_bin']==20


def test_peak_at_bin_two_does_not_generate_peak_output():
    a=np.zeros(512,dtype='f4');a[2]=20;a[3]=7
    d=measure(a,n_fft=1024,fs_out=32768)
    assert d['raw_max_power_bin']==2
    assert d['output_peak_x_bin']==d['output_peak_y']==0.
    assert d['output_mean']>0


def test_peak_neighborhood_is_plus_minus_two_not_single_bin():
    a=np.zeros(512,dtype='f4');a[400]=9;a[401]=8;a[398]=4
    d=measure(a,n_fft=1024,fs_out=32768)
    assert d['raw_max_power_bin']==400
    assert (d['peak_neighborhood_first_bin'],d['peak_neighborhood_last_bin'])==(398,402)
    assert d['peak_neighborhood_power_sum']==pytest.approx(21.)
    assert d['output_peak_y']>0.


def test_f_range_changes_levels_not_peak_frequency():
    a=measure(power(),n_fft=1024,fs_out=32768)
    b=measure(power(),n_fft=1024,fs_out=32768,f_range=5)
    assert b['output_peak_x_bin']==a['output_peak_x_bin']
    assert b['output_mean']==pytest.approx(a['output_mean']*5,rel=1e-6)
    assert b['output_peak_y']==pytest.approx(a['output_peak_y']*5,rel=1e-6)


def test_no_bin_mutation():
    a=power();ref=a.copy()
    measure(a,n_fft=1024,fs_out=32768)
    np.testing.assert_array_equal(a,ref)


@pytest.mark.parametrize('bad',[float('nan'),-1,float('inf')])
def test_reject_nonnumerical_or_negative_power(bad):
    a=power();a[33]=bad
    with pytest.raises(ValueError):measure(a,n_fft=1024,fs_out=32768)


@pytest.mark.parametrize('n',[0,500,1234,500000])
def test_invalid_fft_n_rejected(n):
    with pytest.raises(ValueError):measure(np.zeros(512,dtype='f4'),n_fft=n,fs_out=32768)


def test_zero_power_output():
    d=measure(np.zeros(512,dtype='f4'),n_fft=1024,fs_out=32768)
    assert d['output_mean']==d['output_peak_x_bin']==d['output_peak_y']==0.


@pytest.mark.parametrize('mode',[0,1,2,3])
def test_all_original_modes_have_numeric_summary(mode):
    d=measure(power(),n_fft=1024,fs_out=32768,spectrum_mode=mode)
    assert d['spectrum_mode']==mode
    assert d['energy_weighted_peak']


def test_source_summary_uses_full_resolution_not_decimated_curve():
    with pytest.raises(ValueError,match='complete'):
        measure(power()[:100],n_fft=1024,fs_out=32768)


def test_stage111i_original_stepwise_float64_power_sum_not_numpy_pairwise():
    """007D1807 fadd Single -> fstp qword EACH bin, sensitive to sum order."""
    n=262144
    a=np.ones(n//2,dtype='f4')
    a[3]=np.float32(1.e16)
    d=measure(a,n_fft=n,fs_out=65536)
    first,last=d['summary_first_bin'],d['summary_last_bin']
    sequential=0.
    for p in a[first:last+1]:
        sequential=float(sequential+float(p))
    numpy_pairwise=float(np.sum(a[first:last+1].astype(np.float64),dtype=np.float64))
    assert d['power_sum_order']=='DELPHI_STEPWISE_F64_STORED'
    assert d['raw_total_band_power']==sequential
    assert abs(numpy_pairwise-sequential)>1000  # source-visible rounding difference
    assert not d['original_delphi_numerical_parity_verified']
