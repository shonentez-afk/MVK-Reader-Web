"""Stage111V: source-derived float32 ULP regression independent of native compiler.

Expected boundaries are based on synthetic x87 helper probe at CW=0x037f.
Not original Delphi golden measurements or signed-off x87 parity.
"""
from __future__ import annotations
import struct
import pytest
from mvk_compatible.core.spectrum_graph_default_vscale_idr_candidate import (
    spectrum_graph_default_vscale,
)


def adjacent_positive_single(value:float, direction:int)->float:
    assert value>0 and direction in (-1,+1)
    bits=struct.unpack('<I',struct.pack('<f',value))[0]
    return struct.unpack('<f',struct.pack('<I',bits+direction))[0]


@pytest.mark.parametrize('boundary,left,exact,right',[
    (2.,2.,5.,5.),(5.,5.,10.,10.),(10.,10.,10.,20.),
])
def test_float32_nearest_neighbors_have_hardware_probe_branch(boundary,left,exact,right):
    low=adjacent_positive_single(boundary,-1)
    high=adjacent_positive_single(boundary,+1)
    assert low<boundary<high
    for raw,target in ((low,left),(boundary,exact),(high,right)):
        result=spectrum_graph_default_vscale(raw,1)
        assert result['candidate_graph_default_vscale_single']==pytest.approx(target)
        assert result['original_math_helpers_x87_rounding_verified'] is False
        assert not result['local_f_range_is_original_channel_frange_verified']


@pytest.mark.parametrize('value,expected_step,expected',[
    (0.2,2,.2),(0.5,5,.5),(.05,10,.1),(2.,5,5.),(5.,10,10.),
    (20.,5,50.),(50.,10,100.)
])
def test_positive_and_negative_log_branches_match_synthetic_x87_probe(value,expected_step,expected):
    info=spectrum_graph_default_vscale(value,1)
    assert info['selected_nice_step']==expected_step
    assert info['candidate_graph_default_vscale_single']==pytest.approx(expected)
    assert not info['original_delphi_graph_default_vscale_numeric_parity_verified']


@pytest.mark.parametrize('mode,expected',[(0,.5),(1,.5),(2,5.),(3,50.)])
def test_source_multipliers_against_x87_hardware_probe(mode,expected):
    info=spectrum_graph_default_vscale(.31,mode)
    assert info['candidate_graph_default_vscale_single']==pytest.approx(expected)
    assert info['source_mode_multiplier']==(1 if mode in (0,1) else (10 if mode==2 else 100))
    assert not info['original_qt_y_canvas_parity_verified']
