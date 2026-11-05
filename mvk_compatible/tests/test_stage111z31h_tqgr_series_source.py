"""Stage111Z31H TQGRSeries source-recovered per-pixel tests: synthetic only."""
import numpy as np
import pytest
from mvk_compatible.core.tqgr_series_source_candidate import (
    SOURCE, source_tqgr_series_contract, source_tqgr_series_columns,
)


def series(values, **overrides):
    kwargs=dict(scr_left=0.,scr_width=10.,scr_bottom=-10.,scr_height=20.,
                x_start=0.,x_scale=1.,y_scale=1.,
                pixel_left=0,pixel_right=10,pixel_top=0,pixel_bottom=20)
    kwargs.update(overrides)
    return source_tqgr_series_columns(values,**kwargs)


def test_source_contract_proves_per_pixel_minmax_not_native_pixels():
    r=source_tqgr_series_contract()
    assert r['source']==SOURCE
    assert r['source_series_per_pixel_column_minmax']
    assert r['source_connect_to_closest_extreme_first']
    assert r['source_positive_width_index_window']=='(stoi(x),stoi(x+1)]'
    assert not r['original_series_x87_exact_verified']


def test_source_forward_pixel_window_is_current_plus_one():
    r=series(np.arange(20,dtype='<f4'))
    # X=1 maps indices stoi(1)+1=2 through stoi(2)=2 inclusive.
    assert r['columns'][0][0]==1
    assert r['columns'][0][3:]==(2,2)
    assert r['initial_sample_index']==0
    assert r['initial_move_pixel']==(0.0,10.0)
    assert len(r['columns'])==10


def test_minmax_keeps_one_bin_impulse_even_for_big_fft():
    a=np.zeros(131072,dtype='<f4')
    a[50004]=100.
    r=source_tqgr_series_columns(a, scr_left=0,scr_width=131072,
          scr_bottom=-5,scr_height=110,x_start=0,x_scale=1,
          pixel_left=0,pixel_right=512,pixel_top=0,pixel_bottom=500)
    assert len(r['columns'])<=512
    assert 0<len(r['segments'])<=1024
    assert any(lo<hi for _,lo,hi,*_ in r['columns'])
    # The single-bin 100-unit spike must survive source min/max collapse.
    assert any(abs(hi-lo)>400 for _,lo,hi,*_ in r['columns'])
    assert r['data_size_original']==131072
    assert np.float32(a[50004])==100.0


def test_two_extremes_in_one_column_and_connection_order():
    a=np.zeros(101,dtype='<f4')
    a[20:30]=[-2,8,-3,6,3,-5,9,1,0,3]
    r=series(a, scr_width=100,x_scale=1)
    col=[c for c in r['columns'] if c[0]==2][0]
    assert col[3:]==(21,30)
    assert col[1] < col[2]
    s=r['segments']
    assert any(x0==x1==2.0 for x0,y0,x1,y1 in s)


def test_previous_endpoint_connection_nearest_extreme_first():
    a=np.zeros(41,dtype='<f4')
    a[11:21]=[8,8,-8,-8,-8,-8,8,8,8,8]
    r=series(a, scr_width=40, pixel_right=4)
    assert any(hi-lo>0 for _,lo,hi,*_ in r['columns'])
    xs=[s[2] for s in r['segments']]
    assert any(xs.count(x)>=2 for x in set(xs))


def test_negative_screen_width_reverse_bin_walk():
    a=np.arange(21,dtype='<f4')
    r=series(a,scr_left=20,scr_width=-20,pixel_right=10)
    assert r['initial_sample_index']==20
    assert r['columns'][0][3]>=r['columns'][0][4]
    assert len(r['columns'])>=8


def test_screen_y_clips_to_source_pixel_top_bottom():
    a=np.array([0,1000,-1000,1000,0]*8,dtype='<f4')
    r=series(a,scr_width=39,pixel_right=10)
    assert all(0<=low<=high<=20 for _,low,high,*_ in r['columns'])
    assert any(lo==0 and hi==20 for _,lo,hi,*_ in r['columns'])


@pytest.mark.parametrize('patch',[
    {'scr_width':0}, {'scr_height':0}, {'x_scale':0}, {'y_scale':-1},
    {'scr_left':float('nan')}, {'pixel_left':True},
    {'pixel_left':0,'pixel_right':0}, {'pixel_right':100_000},
    {'solid':True},
])
def test_fail_closed_invalid_parameters(patch):
    with pytest.raises(ValueError):
        series(np.zeros(20,dtype='<f4'),**patch)


@pytest.mark.parametrize('data',[
    np.array([],dtype='<f4'),np.array([[1,2]],dtype='<f4'),
    np.array([1.,np.nan],dtype='<f4'),np.array([1.,np.inf],dtype='<f4'),
    np.array([True,False]),np.array(['x','y']),
])
def test_fail_closed_invalid_original_samples(data):
    with pytest.raises(ValueError):
        series(data)


def test_original_float32_input_bits_remain_exact():
    raw=np.array([0,1,2,-5,6,9,-10,1,2,3,4,7,3,2,1,0],dtype='<f4')
    bits=raw.view('<u4').copy()
    series(raw)
    np.testing.assert_array_equal(raw.view('<u4'),bits)
