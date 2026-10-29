"""Stage111K source formulas for full TQGrapher canvas, synthetic-only."""
import math
import numpy as np
import pytest
from mvk_compatible.core.tqgrapher_canvas_idr_candidate import (
    source_canvas_geometry,cursor_geometry_from_canvas)
from mvk_compatible.core.tqgrapher_cursor_candidate import pick_tqgrapher_cursor


def sample(**override):
    config=dict(pixel_width=800,pixel_height=500,margin=10,
        zero_text_width=8,six_decimals_text_width=64,
        zero_text_height=14,x_name_present=True,y_name_present=True,
        scr_left=0.,scr_width=200.,scr_bottom=-1.,
        scr_height=2.,series_x_start=0.,series_x_scale=2.)
    config.update(override)
    return source_canvas_geometry(**config)


def test_original_pixel_rectangle_uses_all_three_text_measurements_and_labels():
    r=sample()
    assert (r['pixel_left'],r['pixel_right'])==(82,790)
    assert (r['pixel_top'],r['pixel_bottom'])==(10,446)
    assert (r['pixel_plot_width'],r['pixel_plot_height'])==(708,436)
    assert r['original_source_formula_verified']
    assert not r['original_canvas_font_metrics_verified']
    assert not r['original_pixel_rectangle_verified']


def test_original_second_label_consumes_only_one_extra_bottom_margin():
    two=sample(x_name_present=True,y_name_present=True)
    one=sample(x_name_present=True,y_name_present=False)
    none=sample(x_name_present=False,y_name_present=False)
    assert two['pixel_bottom']==one['pixel_bottom']==446
    assert none['pixel_bottom']==468


def test_original_independent_itos_stoi_single_coefficients():
    r=sample()
    assert r['itos_m']==float(np.float32(708*2/200))
    assert r['itos_c']==82.
    assert r['stoi_m']==float(np.float32(200/708/2))
    assert r['stoi_c']==0.
    assert r['ytos_m']==float(np.float32(-436/2))
    assert r['ytos_c']==float(np.float32(446-436/2))
    assert r['original_x87_numeric_parity_verified'] is False
    geom=cursor_geometry_from_canvas(r)
    vals=np.zeros(128,dtype='f4')
    vals[12:15]=[1,5,3]
    click=r['itos_m']*13+r['itos_c']+.35
    cursor=pick_tqgrapher_cursor(vals,click,geom,precise=False)
    assert cursor['selected_bin']==13
    assert cursor['snapped_pixel_original_int_candidate']==int(round(
        float(np.float32(r['itos_m']*13+r['itos_c']))))
    assert cursor['independent_itos_source_supplied']


def test_original_scr_left_and_series_x_start_are_not_interchangeable():
    r=sample(scr_left=20.,series_x_start=4.)
    assert r['itos_c']==float(np.float32(82+(4.-20.)*708/200))
    assert r['stoi_c']==float(np.float32((20.-4.)/2.))
    geom=cursor_geometry_from_canvas(r)
    assert geom.stoi_c==8.
    assert geom.itos_c==r['itos_c']


def test_fallback_when_plot_is_too_narrow_or_font_too_large():
    r=sample(pixel_width=45,zero_text_width=16,
             six_decimals_text_width=500)
    assert r['x_fallback_to_margin']
    assert r['pixel_left']==10
    assert r['pixel_right']==35
    r=sample(pixel_height=41,zero_text_width=16,zero_text_height=36)
    assert r['y_fallback_to_margin']
    assert r['pixel_top']==10
    assert r['pixel_bottom']==31


def test_tqgrapher_canvas_minimum_margin_and_dimensions():
    r=sample(pixel_width=1,pixel_height=1,margin=0)
    assert r['margin']==10
    assert r['canvas_width']==r['canvas_height']==30
    assert r['pixel_right']==20
    assert r['x_fallback_to_margin']
    assert r['y_fallback_to_margin']


@pytest.mark.parametrize('kw',[{'pixel_width':0},{'margin':-1},
    {'pixel_width':2.5},{'zero_text_width':True},
    {'zero_text_height':0},{'scr_width':0},{'scr_width':1e-9},
    {'series_x_scale':0},{'scr_height':0},
    {'scr_left':float('nan')},{'x_name_present':1}])
def test_invalid_metrics_and_spans_fail_closed(kw):
    with pytest.raises(ValueError):
        sample(**kw)


def test_invalid_external_canvas_dict_rejected():
    with pytest.raises(ValueError):
        cursor_geometry_from_canvas({'source':'not original'})
