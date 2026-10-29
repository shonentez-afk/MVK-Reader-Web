"""Stage111D original TQGrapher pixel-cursor: synthetic-only regression.

Original Delphi/IDR evidence is private; no original app or industrial captures.
"""
import math
import numpy as np
import pytest
from mvk_compatible.core.tqgrapher_cursor_candidate import (
    CursorGeometry, pick_tqgrapher_cursor, cursor_from_spectrum)
from mvk_compatible.core import OfflineSession
from mvk_compatible.tests.test_offline_core import fixture_zip


def geometry(m=3.,c=0.,left=10.,right=30.,scale=.5,yscale=2.):
    return CursorGeometry(left,right,m,c,0.,scale,yscale)


def sample_values():
    a=np.zeros(60,dtype=np.float32)
    a[6:9]=[2,8,4]
    return a


def test_cursor_uses_max_bin_inside_pixel_not_nearest_frequency():
    picked=pick_tqgrapher_cursor(sample_values(),12.,geometry(),precise=True)
    assert (picked['pixel_bin_first'],picked['pixel_bin_last'])==(6,8)
    assert picked['selected_bin']==7
    assert picked['x_value']==3.5
    assert picked['raw_y']==8 and picked['display_y']==16
    assert picked['snapped_pixel_candidate']==pytest.approx(12+1/3)
    assert picked['precise_max_search_used'] is True
    assert picked['averaging_divisor']==1
    assert picked['original_delphi_cursor_parity_verified'] is False


def test_can_disable_precise_search():
    picked=pick_tqgrapher_cursor(sample_values(),12.,geometry(),precise=False)
    assert picked['selected_bin']==6
    assert picked['raw_y']==2
    assert picked['precise_max_search_used'] is False


def test_signed_max_not_absolute_max_and_ties_choose_first():
    a=sample_values()
    a[6:9]=[-8,-1,-3]
    assert pick_tqgrapher_cursor(a,12.,geometry())['selected_bin']==7
    a[6:9]=[7,7,3]
    assert pick_tqgrapher_cursor(a,12.,geometry())['selected_bin']==6


def test_one_screen_pixel_can_cover_fraction_of_one_bin():
    g=geometry(m=.2,c=0,left=0,right=30,scale=1,yscale=1)
    data=np.arange(8,dtype=np.float32)
    p=pick_tqgrapher_cursor(data,15.,g)
    assert (p['pixel_bin_first'],p['pixel_bin_last'])==(3,2)
    assert p['selected_bin']==3
    assert not p['precise_max_search_used']


def test_averaging_three_is_sqrt_sum_squares_not_rms():
    r=pick_tqgrapher_cursor(sample_values(),12.,geometry(),averaging=3)
    assert (r['averaging_first'],r['averaging_last'])==(6,8)
    assert r['display_y']==pytest.approx(2*math.sqrt(2**2+8**2+4**2),rel=1e-6)
    assert r['display_y']!=pytest.approx(2*math.sqrt((2**2+8**2+4**2)/3))
    assert r['averaging_divisor']==1


def test_averaging_three_clamps_at_first_sample():
    r=pick_tqgrapher_cursor(np.array([3,4,5],dtype=np.float32),.5,
                            geometry(m=1,c=0,left=0,right=2,scale=1,yscale=1),
                            averaging=3)
    assert r['selected_bin']==0
    assert r['averaging_first']==0 and r['averaging_last']==1
    assert r['display_y']==pytest.approx(5.)


def test_pixel_at_or_beyond_edges_clears_cursor():
    for px in (10.,30.,-1.,31.):
        with pytest.raises(ValueError,match='outside'):
            pick_tqgrapher_cursor(sample_values(),px,geometry())


@pytest.mark.parametrize('px',[float('nan'),float('inf'),-float('inf')])
def test_nonfinite_pixel_is_rejected(px):
    with pytest.raises(ValueError,match='Non-finite'):
        pick_tqgrapher_cursor(sample_values(),px,geometry())


@pytest.mark.parametrize('scale,offset',[(0,0),(-1,0),(float('nan'),0),(3,float('inf'))])
def test_invalid_geometry_rejected(scale,offset):
    with pytest.raises(ValueError,match='geometry'):
        pick_tqgrapher_cursor(sample_values(),12.,geometry(m=scale,c=offset))


def test_nonfinite_series_refused_instead_of_fake_cursor():
    a=sample_values();a[7]=np.nan
    with pytest.raises(ValueError):
        pick_tqgrapher_cursor(a,12.,geometry())


def test_cursor_requires_source_verified_averaging_modes():
    with pytest.raises(ValueError,match='only|Only'):
        pick_tqgrapher_cursor(sample_values(),12.,geometry(),averaging=2)


def synthetic_full_spectrum(n=32):
    return {'frequency_hz':(np.arange(n)*.5).tolist(),
            'amplitude':sample_values()[:n].tolist(),
            'df_hz':.5,'channel':2,'unit':'м/с²','mode':1,'n_fft':64,
            'source':'APP_DERIVED_FFT_MVKVIEW_CANDIDATE','fft_backend':'idr_float32'}


def test_spectrum_cursor_refuses_decimation_or_wrong_xscale():
    d=synthetic_full_spectrum()
    d['frequency_hz'][7]=3.7
    with pytest.raises(ValueError,match='contiguous'):
        cursor_from_spectrum(d,12.,geometry())
    d=synthetic_full_spectrum()
    with pytest.raises(ValueError,match='contiguous'):
        cursor_from_spectrum(d,12.,geometry(scale=.6))


def test_complete_spectrum_cursor_has_units_provenance_and_bin():
    d=synthetic_full_spectrum()
    p=cursor_from_spectrum(d,12.,geometry(),averaging=1)
    assert p['selected_bin']==7
    assert p['frequency_hz']==3.5
    assert p['fft_source']=='APP_DERIVED_FFT_MVKVIEW_CANDIDATE'
    assert p['fft_backend']=='idr_float32'
    assert p['chart_decimation_used'] is False
    assert p['full_bin_count']==32
    assert p['channel']==2 and p['n_fft']==64


def test_complete_offline_session_same_candidate_backend(tmp_path):
    s=OfflineSession.open(fixture_zip(tmp_path))
    full=s.spectrum(1,4096,1,0,32768,2048,'numpy')
    assert len(full['frequency_hz'])==2048
    assert full['frequency_hz'][5]==80.
    # 64Hz peak is bin 4, choose a pixel spanning 2..5
    g=CursorGeometry(0.,64.,4.,0.,0.,16.,1.)
    p=cursor_from_spectrum(full,1.,g,averaging=3)
    assert p['pixel_bin_first']==4
    assert p['selected_bin']==4
    assert p['frequency_hz']==64.
    assert p['display_y']>=p['raw_y']
