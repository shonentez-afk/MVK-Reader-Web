"""Stage111Z31G: TCo2Draw source scanline candidate regression; synthetic only."""
import numpy as np
import pytest
from mvk_compatible.core.tco2draw_raster_candidate import (
    contract, source_raster_rgba, source_grid_segments)

def test_contract_is_explicitly_not_delphi_pixel_proof():
    d=contract()
    assert d["x_major"]=="007C98B4"
    assert d["y_major"]=="007C9A30"
    assert d["blend"]=="007C9808"
    assert d["neighbors"]==3
    assert d["excludes_endpoint"]
    assert not d["original_delphi_pixel_parity_verified"]
    assert not d["original_x87_runtime_rounding_verified"]

def test_horizontal_raster_excludes_final_endpoint():
    frame=source_raster_rgba(width=14,height=14,segments=[(1,4,10,4)])
    assert frame.shape==(14,14,4)
    assert frame.dtype==np.uint8
    assert frame[4,1,:3].tolist()==[192,192,192]
    assert frame[4,9,:3].tolist()==[192,192,192]
    assert frame[4,10,:3].tolist()==[255,255,255]
    assert frame[3,4,:3].tolist()==[255,255,255]
    assert np.all(frame[:,:,3]==255)

def test_vertical_raster_excludes_final_endpoint():
    frame=source_raster_rgba(width=14,height=14,segments=[(3,1,3,11)])
    assert frame[1,3,:3].tolist()==[192,192,192]
    assert frame[10,3,:3].tolist()==[192,192,192]
    assert frame[11,3,:3].tolist()==[255,255,255]
    assert frame[3,2,:3].tolist()==[255,255,255]

def test_diagonal_three_pixel_coverage_and_reverse_direction():
    a=source_raster_rgba(width=14,height=14,segments=[(1,1,11,11)])
    b=source_raster_rgba(width=14,height=14,segments=[(11,11,1,1)])
    assert a[5,5,0]==192
    assert 192<a[4,5,0]<255
    assert b[5,5,0]==192
    assert 192<b[4,5,0]<255
    assert a[0,0,0]==255

def test_composition_and_stable_reproducibility():
    one=source_raster_rgba(width=21,height=21,segments=[(1,4,17,4)])
    segments=[(1,4,17,4),(6,1,6,18)]
    two=source_raster_rgba(width=21,height=21,segments=segments)
    assert two[4,6,0]==192
    assert one[4,8,0]==two[4,8,0]
    np.testing.assert_array_equal(
        two,source_raster_rgba(width=21,height=21,segments=segments))

def test_grid_conversion_uses_qt_logical_not_native_pixel_rect():
    lines=source_grid_segments(
        x_ticks=(0,50,100),y_ticks=(-20,-10,0),
        view_x=(0,100),view_y=(-20,0),width=101,height=101)
    assert len(lines)==6
    assert lines[1]==(50,0,50,100)
    assert lines[-2]==(0,50,100,50)
    frame=source_raster_rgba(width=101,height=101,segments=lines)
    assert frame[50,50,0]==192
    assert frame[25,25,0]==255

@pytest.mark.parametrize('patch',[
    dict(width=3),dict(width=True),dict(width=10000,height=10000),
    dict(segments="bad"),dict(segments=[(1,2,3)]),
    dict(segments=[(0,1,float('nan'),2)]),
    dict(segments=[(0,1,True,2)]),
    dict(segments=[(0,1,1e20,2)]),
])
def test_raster_bad_inputs_fail_closed(patch):
    kw=dict(width=14,height=14,segments=[(2,2,5,5)])
    kw.update(patch)
    with pytest.raises(ValueError):
        source_raster_rgba(**kw)

def test_tick_bounds_fail_closed():
    with pytest.raises(ValueError):
        source_grid_segments(x_ticks=(101,),y_ticks=(),
            view_x=(0,100),view_y=(-10,0),width=100,height=100)
    with pytest.raises(ValueError):
        source_grid_segments(x_ticks=(),y_ticks=(0,),
            view_x=(100,0),view_y=(-10,0),width=100,height=100)
