"""Stage111L source synthetic bin/text/cursor contracts, no instrument data."""
import numpy as np
import pytest
from mvk_compatible.core.tqgrapher_multiseries_idr_candidate import original_multiseries_cursor


def canvas():
    return dict(source='APP_DERIVED_TQGRAPHER_CANVAS_GEOMETRY_IDR_CANDIDATE',
                pixel_left=10,pixel_right=90,
                stoi_m=.5,stoi_c=0.,itos_m=2.,itos_c=10.,
                series_x_scale=32.,series_x_start=0.)


def test_outside_and_empty_primary_clear_original_cursor_string():
    a=np.ones(48,dtype='f4')
    for pixel in (10,90,9,91):
        r=original_multiseries_cursor(a,pixel=pixel,canvas=canvas())
        assert not r['drawn'] and r['cursor_string']==''
    r=original_multiseries_cursor([],pixel=50,canvas=canvas())
    assert not r['drawn']


def test_real_two_series_uses_identical_global_y_name():
    x=np.zeros(40,dtype='f4'); y=np.zeros(40,dtype='f4')
    x[12]=5; y[12]=8
    # At pixel 34, first=12, last=11: window empty; pick first bin.
    r=original_multiseries_cursor(x,pixel=34,canvas=canvas(),
        series1=y,averaging=1,precise=True,y_name='мм/с',decimal_separator=',')
    assert r['drawn']
    assert r['selected_primary_bin']==12
    assert r['snapped_vertical_pixel']==34
    assert r['cursor_string']=='384 Гц\r\n5 мм/с\r\n8 мм/с'
    assert r['second_series_uses_same_global_y_name']
    assert [z['selected_bin'] for z in r['series_results']]==[12,12]
    assert not r['original_delphi_cursor_parity_verified']


def test_precise_search_signed_maximum_and_first_tie():
    c=canvas();c['stoi_m']=1.5;c['itos_m']=2/3.
    x=np.zeros(100,dtype='f4')
    # Pixel 30 => first=30, pixel+1=>31 so last=30 (1 bin); @31 next => first=31
    x[30]=-2;x[31]=-1;x[32]=-1
    r=original_multiseries_cursor(x,pixel=31,canvas=c,averaging=1)
    assert r['selected_primary_bin']==31
    assert r['series_results'][0]['raw_at_peak']==-1


def test_original_primary_index_and_second_series_independent_peak():
    c=canvas();c['stoi_m']=3.;c['itos_m']=1/3.
    x=np.zeros(120,dtype='f4');y=np.zeros(120,dtype='f4')
    # pixel 22 -> first=36, pixel+1=39, last=38
    x[36:39]=[1,8,2]
    y[36:39]=[9,1,2]
    r=original_multiseries_cursor(x,pixel=22,canvas=c,series1=y)
    assert r['selected_primary_bin']==37
    assert r['series_results'][0]['selected_bin']==37
    assert r['series_results'][1]['selected_bin']==36
    assert r['snapped_vertical_pixel']==22


def test_short_second_series_is_skipped_but_primary_label_remains():
    x=np.ones(40,dtype='f4');y=np.ones(10,dtype='f4')
    r=original_multiseries_cursor(x,pixel=34,canvas=canvas(),series1=y)
    assert len(r['series_results'])==1
    assert len(r['cursor_lines'])==2


def test_original_averaging_three_is_square_sum_not_mean():
    x=np.zeros(40,dtype='f4');x[11:14]=[3,4,12]
    # first=12 (center), averaging uses 11..13, sqrt(3^2+4^2+12^2)=13
    r=original_multiseries_cursor(x,pixel=34,canvas=canvas(),averaging=3)
    assert r['series_results'][0]['display_y']==13
    assert '13 м/с²' in r['cursor_string']


def test_original_unsafe_averaging_at_last_bin_is_refused():
    x=np.ones(13,dtype='f4')
    with pytest.raises(ValueError,match='Series.DataSize'):
        original_multiseries_cursor(x,pixel=34,canvas=canvas(),averaging=3)


def test_second_series_y_scale_is_separate_but_yname_global():
    x=np.zeros(40,dtype='f4');y=np.zeros(40,dtype='f4')
    x[12]=2;y[12]=3
    r=original_multiseries_cursor(x,pixel=34,canvas=canvas(),series1=y,
                                  y_scale0=4.,y_scale1=.5,y_name='у.е.')
    assert r['cursor_string']=='384 Гц\r\n8 у.е.\r\n1,5 у.е.'


@pytest.mark.parametrize('wrong',[0.,12.4,None,True])
def test_only_native_original_integer_mouse_coordinate(wrong):
    with pytest.raises(ValueError,match='native integer'):
        original_multiseries_cursor(np.ones(40),pixel=wrong,canvas=canvas())


def test_reject_non_original_canvas_and_nonfinite_f32_data():
    with pytest.raises(ValueError,match='Canvas'):
        original_multiseries_cursor(np.ones(30),pixel=34,canvas={})
    a=np.ones(40);a[9]=np.nan
    with pytest.raises(ValueError,match='finite'):
        original_multiseries_cursor(a,pixel=34,canvas=canvas())


def test_strict_signed_maximum_equal_value_chooses_first_bin():
    c=canvas();c['stoi_m']=3.;c['itos_m']=1/3.
    a=np.full(120,-10.,dtype='f4')
    a[36:39]=[-2.,-2.,-3.]
    r=original_multiseries_cursor(a,pixel=22,canvas=c,precise=True)
    assert r['selected_primary_bin']==36
    assert r['series_results'][0]['display_y']==-2.


def test_no_precise_mode_keeps_first_even_when_later_larger():
    c=canvas();c['stoi_m']=3.;c['itos_m']=1/3.
    a=np.zeros(120,dtype='f4');a[36:39]=[1,2,100]
    r=original_multiseries_cursor(a,pixel=22,canvas=c,precise=False)
    assert r['selected_primary_bin']==36
    assert r['series_results'][0]['display_y']==1.


def test_nonfinite_geometry_refused():
    c=canvas();c['itos_m']=float('inf')
    with pytest.raises(ValueError,match='transforms'):
        original_multiseries_cursor(np.ones(40),pixel=34,canvas=c)


def test_invalid_y_name_rejected_and_rtl_parity_unverified():
    a=np.ones(40,dtype='f4')
    with pytest.raises(ValueError,match='names'):
        original_multiseries_cursor(a,pixel=34,canvas=canvas(),y_name='a\nb')
    r=original_multiseries_cursor(a,pixel=34,canvas=canvas())
    assert r['original_Delphi_FormatFloat_parity_verified'] is False
    assert r['pixel_coordinate_system']=='ORIGINAL_CANVAS_ABSOLUTE'
