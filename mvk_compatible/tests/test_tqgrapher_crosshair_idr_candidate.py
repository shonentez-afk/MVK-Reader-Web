"""Stage111M: native TQGrapher horizontal crosshair is NOT the Y averaged label."""
import numpy as np
import pytest
from mvk_compatible.core.tqgrapher_multiseries_idr_candidate import original_multiseries_cursor
from mvk_compatible.core.tqgrapher_crosshair_idr_candidate import original_cursor_crosshair


def canvas():
    return {
        'source':'APP_DERIVED_TQGRAPHER_CANVAS_GEOMETRY_IDR_CANDIDATE',
        'pixel_left':10,'pixel_right':90,'pixel_top':20,'pixel_bottom':120,
        'stoi_m':.5,'stoi_c':0.,'itos_m':2.,'itos_c':10.,
        'ytos_m':-2.,'ytos_c':100.,
        'series_x_scale':32.,'series_x_start':0.
    }


def test_horizontal_line_uses_raw_selected_bin_not_avg3_label():
    x=np.zeros(40,dtype='f4')
    x[11:14]=[3,4,12]
    c=canvas()
    a=original_multiseries_cursor(x,pixel=34,canvas=c,averaging=3)
    assert a['series_results'][0]['display_y']==13.
    r=original_cursor_crosshair(a,c)
    assert r['drawn']
    assert r['horizontal_pixels']==[92]   # 100 - 2*raw[12]=92
    assert r['horizontal_lines'][0]['label_display_y']==13.
    assert r['horizontal_lines'][0]['label_y_is_a_separate_operation']
    assert r['horizontal_lines'][0]['selected_bin']==12
    assert r['horizontal_lines'][0]['start_xy']==[10,92]
    assert r['horizontal_lines'][0]['end_xy']==[90,92]
    assert r['vertical_line']=={'start_xy':[34,20],'end_xy':[34,120]}
    assert not r['original_Delphi_pixel_parity_verified']


def test_two_series_create_independent_signed_horizontal_lines():
    x=np.zeros(40,dtype='f4')
    y=np.zeros(40,dtype='f4')
    x[12]=4.
    y[12]=-2.
    c=canvas()
    sel=original_multiseries_cursor(x,pixel=34,canvas=c,series1=y)
    result=original_cursor_crosshair(sel,c,y_scale0=1.,y_scale1=1.5)
    assert result['horizontal_pixels']==[92,106]
    assert [r['series'] for r in result['horizontal_lines']]==[0,1]
    assert result['horizontal_lines'][1]['y_scaled_single']==-3.
    assert result['horizontal_lines'][1]['start_xy']==[10,106]
    assert result['horizontal_lines'][1]['end_xy']==[90,106]
    assert not result['original_font_and_canvas_registration_verified']


def test_original_horizontal_line_clamps_each_series_to_canvas_top_bottom():
    x=np.zeros(40,dtype='f4')
    y=np.zeros(40,dtype='f4')
    x[12]=100.
    y[12]=-100.
    c=canvas()
    sel=original_multiseries_cursor(x,pixel=34,canvas=c,series1=y)
    crosshair=original_cursor_crosshair(sel,c)
    assert crosshair['horizontal_pixels']==[20,120]


def test_original_round_half_to_even_after_single_and_clamp():
    x=np.zeros(40,dtype='f4')
    x[12]=5.
    c=canvas()
    c['ytos_m']=-1.
    c['ytos_c']=45.5  # 45.5 - 5 = 40.5 -> @ROUND to even 40
    sel=original_multiseries_cursor(x,pixel=34,canvas=c)
    assert original_cursor_crosshair(sel,c)['horizontal_pixels']==[40]
    c['ytos_c']=46.5  # 41.5 -> @ROUND to even 42
    assert original_cursor_crosshair(sel,c)['horizontal_pixels']==[42]


def test_crosshair_selected_bin_and_vertical_does_not_change_with_averaging():
    x=np.zeros(40,dtype='f4');x[11:14]=[3,4,12]
    c=canvas()
    plain=original_multiseries_cursor(x,pixel=34,canvas=c,averaging=1)
    avg=original_multiseries_cursor(x,pixel=34,canvas=c,averaging=3)
    a=original_cursor_crosshair(plain,c)
    b=original_cursor_crosshair(avg,c)
    assert a['horizontal_pixels']==b['horizontal_pixels']==[92]
    assert a['vertical_line']==b['vertical_line']
    assert plain['cursor_string']!=avg['cursor_string']


def test_no_cursor_does_not_draw_y_crosshair():
    c=canvas()
    x=np.ones(40,dtype='f4')
    cursor=original_multiseries_cursor(x,pixel=10,canvas=c)
    d=original_cursor_crosshair(cursor,c)
    assert not d['drawn']
    assert d['horizontal_lines']==[]
    assert d['vertical_line'] is None


def test_bad_source_and_canvas_missing_y_fields_fail_closed():
    c=canvas()
    cursor=original_multiseries_cursor(np.ones(40),pixel=34,canvas=c)
    with pytest.raises(ValueError,match='cursor candidate'):
        original_cursor_crosshair({},c)
    with pytest.raises(ValueError,match='Canvas'):
        original_cursor_crosshair(cursor,{})
    bad=canvas();bad.pop('ytos_c')
    with pytest.raises(ValueError,match='missing'):
        original_cursor_crosshair(cursor,bad)


def test_bad_y_canvas_scale_and_overflow_fail_closed():
    c=canvas()
    x=np.zeros(40,dtype='f4');x[12]=1.
    cursor=original_multiseries_cursor(x,pixel=34,canvas=c)
    c['ytos_m']=float('nan')
    with pytest.raises(ValueError,match='ytos'):
        original_cursor_crosshair(cursor,c)
    c=canvas()
    c['ytos_c']=1e99
    with pytest.raises(ValueError,match='overflows'):
        original_cursor_crosshair(cursor,c)


def test_raw_crosshair_is_not_stored_back_in_original_samples():
    c=canvas()
    x=np.zeros(40,dtype='f4');x[12]=5.
    copy=x.copy()
    cursor=original_multiseries_cursor(x,pixel=34,canvas=c)
    d=original_cursor_crosshair(cursor,c)
    np.testing.assert_array_equal(x,copy)
    assert 'original_crosshair_independent_of_CursorAveraging' in d
