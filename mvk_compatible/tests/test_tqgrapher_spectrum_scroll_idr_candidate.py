"""Stage111S source H/V scrollbar behavior on synthetic ranges, no device."""
import pytest
from mvk_compatible.core.tqgrapher_spectrum_scroll_idr_candidate import (
    SOURCE,DELPHI_H_FIRST_MENU_SCALE_HZ,NativeScrollContract,rescale_scroll,
    source_spectrum_h_scr,source_spectrum_v_scr)


def test_default_first_menu_scale_is_original_25600_and_hidden():
    assert DELPHI_H_FIRST_MENU_SCALE_HZ==25600
    full=NativeScrollContract('horizontal',25600,25600,0,True)
    d=full.view()
    assert d['source']==SOURCE
    assert d['delphi_max']==25599
    assert d['delphi_page_size']==25600
    assert d['delphi_position']==0
    assert d['qt_maximum']==0
    assert not d['delphi_visible']
    assert d['source_menu_preset_verified']
    assert not d['runtime_delphi_vcl_scrollbar_parity_verified']


def test_horizontal_zoom_rescale_holds_integer_position_and_clamps():
    full=NativeScrollContract('horizontal',25600,25600,0,True)
    zoom=rescale_scroll(full,selected_page=6400)
    assert zoom.position==0
    assert zoom.view()['delphi_visible']
    assert zoom.view()['qt_maximum']==19200
    assert zoom.view()['qt_page_step']==6400
    assert zoom.view()['delphi_small_change']==640
    assert zoom.view()['delphi_large_change']==6400
    moved=NativeScrollContract('horizontal',25600,6400,18000)
    other=rescale_scroll(moved,selected_page=10000)
    assert other.position==15600
    assert other.view()['qt_maximum']==15600
    restored=rescale_scroll(other,selected_page=25600)
    assert restored.position==0 and not restored.view()['delphi_visible']


def test_original_h_view_start_is_position_in_hz_not_1000_fraction():
    for position in (0,1,12800,19200):
        r=source_spectrum_h_scr(position,6400,25600)
        assert r['scr_width_single']==6400.
        assert r['scr_left_single']==float(position)
        assert r['delphi_page_size']==6400
        assert r['qt_maximum']==19200
        assert not r['original_menu_scale_values_verified']
        assert not r['original_delphi_x87_parity_verified']


def test_source_vertical_rescale_anchors_bottom_to_prior_page_extent():
    full=NativeScrollContract('vertical',150,150,0)
    zoom=rescale_scroll(full,selected_page=75,vertical=True)
    assert zoom.position==75
    assert zoom.view()['delphi_small_change']==7
    assert zoom.view()['qt_page_step']==75
    narrow=rescale_scroll(zoom,selected_page=30,vertical=True)
    assert narrow.position==120
    assert narrow.view()['qt_maximum']==120
    wider=rescale_scroll(narrow,selected_page=140,vertical=True)
    assert wider.position==10
    assert rescale_scroll(wider,selected_page=150,vertical=True).position==0


def test_vertical_source_has_different_db_and_non_db_bottom_math():
    db=source_spectrum_v_scr(20,75,150,db_mode=True,
                            graph_default_v_scale=4.,scale_divisor=2)
    assert db['scr_height_single']==75
    assert db['scr_bottom_single']==-95
    eng=source_spectrum_v_scr(5,20,100,db_mode=False,
                             graph_default_v_scale=80.,scale_divisor=4)
    assert eng['scr_height_single']==20.
    assert eng['scr_bottom_single']==55.
    assert not eng['original_vertical_menu_values_verified']


@pytest.mark.parametrize('axis,full,page,pos',[
    ('x',100,10,5),('horizontal',0,1,0),
    ('horizontal',100,0,0),('horizontal',100,101,0),
    ('horizontal',100,30,71),('horizontal',100,30,-1),
    ('horizontal',100,30,True),('horizontal',True,10,0),
    ('vertical',100,10,100),('vertical',2_000_001,1,0),
])
def test_invalid_or_unsafe_scroll_contract_is_rejected(axis,full,page,pos):
    with pytest.raises(ValueError):NativeScrollContract(axis,full,page,pos)


def test_wrong_source_flags_and_mode_mismatch_are_rejected():
    with pytest.raises(ValueError,match='preset'):
        NativeScrollContract('horizontal',25600,6400,0,True)
    with pytest.raises(ValueError,match='preset'):
        NativeScrollContract('vertical',150,150,0,True)
    with pytest.raises(ValueError,match='direction'):
        rescale_scroll(NativeScrollContract('horizontal',100,100,0),
                       selected_page=50,vertical=True)
    with pytest.raises(ValueError):
        source_spectrum_v_scr(0,50,150,db_mode=True,
                              graph_default_v_scale=0.)
    with pytest.raises(ValueError):
        source_spectrum_v_scr(0,50,150,db_mode=False,
                              graph_default_v_scale=100.,scale_divisor=0)
    with pytest.raises(ValueError):
        source_spectrum_v_scr(0,50,150,db_mode=1,
                              graph_default_v_scale=100.)
