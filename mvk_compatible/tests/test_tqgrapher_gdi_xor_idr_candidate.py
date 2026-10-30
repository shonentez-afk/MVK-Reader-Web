"""Stage111P synthetic GDI XOR raster model; no original screenshots/data."""
import numpy as np
import pytest
from mvk_compatible.core.tqgrapher_gdi_xor_idr_candidate import (
    SOURCE, GdiLineTo, OriginalGdiXorCursorModel, xor_gdi_line)


def canvas():
    return {'source':'APP_DERIVED_TQGRAPHER_CANVAS_GEOMETRY_IDR_CANDIDATE',
            'pixel_left':2,'pixel_right':12,'pixel_top':3,'pixel_bottom':10}


def cursor(vertical=6, y0=7, y1=None):
    horizontal=[{'series':0,'start_xy':[2,y0],'end_xy':[12,y0]}]
    if y1 is not None:
        horizontal.append({'series':1,'start_xy':[2,y1],'end_xy':[12,y1]})
    return {'source':'APP_DERIVED_TQGRAPHER_CROSSHAIR_IDR_CANDIDATE',
            'drawn':True,
            'vertical_line':{'start_xy':[vertical,3],'end_xy':[vertical,10]},
            'horizontal_lines':horizontal}


def canvas_empty():
    return {'source':'APP_DERIVED_TQGRAPHER_CROSSHAIR_IDR_CANDIDATE',
            'drawn':False,'vertical_line':None,'horizontal_lines':[]}


def img():
    rng=np.random.default_rng(111)
    return rng.integers(0,256,size=(15,20,3),dtype=np.uint8)


def test_gdi_linto_excludes_last_pixel_and_xors_only_green_channel():
    data=np.full((15,20,3),255,dtype=np.uint8)
    xor_gdi_line(data,GdiLineTo('vertical',None,(6,3),(6,10)))
    assert data[3,6].tolist()==[255,127,255]
    assert data[9,6].tolist()==[255,127,255]
    assert data[10,6].tolist()==[255,255,255]
    xor_gdi_line(data,GdiLineTo('horizontal',0,(2,7),(12,7)))
    assert data[7,2].tolist()==[255,127,255]
    assert data[7,11].tolist()==[255,127,255]
    assert data[7,12].tolist()==[255,255,255]
    assert data[7,6].tolist()==[255,255,255]


def test_gdi_xor_sequential_erase_vertical_then_two_y_then_redraw():
    background=img()
    frozen=background.copy()
    model=OriginalGdiXorCursorModel(canvas())
    first,first_report=model.update(6,background,cursor(6,7,8))
    assert first_report['draw_roles']==['vertical','horizontal0','horizontal1']
    assert first_report['vcl_pen_during_draw']==14
    assert first_report['vcl_pen_after_draw']==4
    assert first_report['win32_rop2_xorpen']==7
    assert len(model.active_strokes)==3
    np.testing.assert_array_equal(background,frozen)
    again,duplicate=model.update(6,first,cursor(6,4,5))
    assert duplicate['same_integer_x_noop']
    np.testing.assert_array_equal(first,again)
    second,change=model.update(9,first,cursor(9,5))
    assert change['erase_roles']==['vertical','horizontal0','horizontal1']
    assert change['draw_roles']==['vertical','horizontal0']
    assert len(model.active_strokes)==2
    fresh=OriginalGdiXorCursorModel(canvas())
    ref,_=fresh.update(9,frozen,cursor(9,5))
    np.testing.assert_array_equal(second,ref)
    removed,exit_report=model.update(1,second,canvas_empty())
    assert exit_report['erase_roles']==['vertical','horizontal0']
    assert exit_report['draw_roles']==[]
    np.testing.assert_array_equal(removed,frozen)
    assert not model.active_strokes


def test_gdi_xor_repeat_outside_x_never_repaints():
    origin=img()
    model=OriginalGdiXorCursorModel(canvas())
    a,r=model.update(0,origin,canvas_empty())
    assert r['same_integer_x_noop'] is False
    b,r=model.update(0,a,cursor())
    assert r['same_integer_x_noop'] is True
    np.testing.assert_array_equal(a,b)
    with pytest.raises(ValueError,match='out-of-range'):
        model.update(1,origin,cursor())


def test_two_horizontal_same_y_xor_cancel_without_hidden_sorting():
    original=img()
    model=OriginalGdiXorCursorModel(canvas())
    output,_=model.update(6,original,cursor(6,7,7))
    for x in (2,3,11):
        np.testing.assert_array_equal(output[7,x],original[7,x])
    assert output[7,6,1]==(original[7,6,1]^128)


@pytest.mark.parametrize('bad', [
    GdiLineTo('vertical',None,(3,2),(3,30)),
    GdiLineTo('horizontal',0,(2,3),(50,3)),
])
def test_out_of_frame_rejected_before_painting(bad):
    original=img()
    before=original.copy()
    with pytest.raises(ValueError,match='outside'):
        xor_gdi_line(original,bad)
    np.testing.assert_array_equal(original,before)


def test_cursor_provenance_and_validation_strict_and_transactional():
    original=img()
    model=OriginalGdiXorCursorModel(canvas())
    good,_=model.update(6,original,cursor())
    assert len(model.active_strokes)==2
    wrong=cursor(9,7)
    wrong['horizontal_lines'][0]['end_xy']=[13,7]
    with pytest.raises(ValueError,match='PixelLeft/Right'):
        model.update(9,good,wrong)
    assert len(model.active_strokes)==2
    good_new,_=model.update(9,good,cursor(9,6))
    fresh=OriginalGdiXorCursorModel(canvas())
    reference,_=fresh.update(9,original,cursor(9,6))
    np.testing.assert_array_equal(good_new,reference)


def test_reject_wrong_image_type_or_dimensions_and_boolean_x():
    model=OriginalGdiXorCursorModel(canvas())
    for bad in (np.zeros((10,10,4),np.uint8),np.zeros((10,10,3),float),
                np.zeros((10,10),np.uint8)):
        with pytest.raises(ValueError):model.update(6,bad,cursor())
    with pytest.raises(ValueError,match='native integer'):
        model.update(True,img(),cursor())
    img_good=img()
    model.update(6,img_good,cursor())
    with pytest.raises(ValueError,match='resized'):
        model.update(9,np.zeros((14,20,3),np.uint8),cursor(9,7))


def test_repeated_native_line_restores_exact_pixels_in_any_direction():
    data=img();before=data.copy()
    lines=[GdiLineTo('horizontal',1,(11,5),(2,5)),
           GdiLineTo('vertical',None,(4,9),(4,3))]
    for line in lines:
        xor_gdi_line(data,line)
        xor_gdi_line(data,line)
    np.testing.assert_array_equal(data,before)


def test_model_applies_crosshair_output_from_source_geometry_directly():
    from mvk_compatible.core.tqgrapher_multiseries_idr_candidate import original_multiseries_cursor
    from mvk_compatible.core.tqgrapher_crosshair_idr_candidate import original_cursor_crosshair
    c={**canvas(),
       'stoi_m':.5,'stoi_c':0.,'itos_m':2.,'itos_c':2.,
       'ytos_m':-1.,'ytos_c':8.,'series_x_scale':32.,'series_x_start':0.}
    a=np.zeros(64,dtype='f4')
    b=np.zeros(64,dtype='f4')
    a[4]=1.0
    b[4]=-1.0
    candidate=original_multiseries_cursor(a,pixel=8,canvas=c,
                                           series1=b,averaging=1)
    lines=original_cursor_crosshair(candidate,c)
    assert lines['drawn']
    expected=OriginalGdiXorCursorModel(c)
    original=img()
    rendered,info=expected.update(8,original,lines)
    assert info['draw_roles']==['vertical','horizontal0','horizontal1']
    restored,info=expected.update(1,rendered,canvas_empty())
    np.testing.assert_array_equal(restored,original)
    assert not info['delphi_original_pixel_parity_verified']
