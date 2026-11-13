"""CH source text on original PaintBox, both original X orientations.

Pure-Core: NO Qt/GDI/hardware/real original file required.
"""
import math
import pytest

from ..core.original_live_paintbox_text import (
    source_live_paintbox_text_plan, SOURCE,
)
from ..core.tqgrapher_grid_idr_candidate import (
    source_tqgrapher_grid_candidate,
)


def _width(s):
    return len(s)*7


def _height(_):
    return 13


def _plan(*,invert=False,**extra):
    cfg=dict(width=791,height=740,
        view_x=(0.,25600.),view_y=(-150.,0.),
        x_inverted=invert,x_name="Гц",y_name="дБ",
        zero_text_width=7,six_decimals_text_width=56,
        zero_text_height=13,
        text_width=_width,text_height=_height,
        font_provenance="qt_approximation")
    cfg.update(extra)
    return source_live_paintbox_text_plan(**cfg)


@pytest.mark.parametrize("invert", [False,True])
def test_full_paintbox_textout_source_single_and_original_font(invert):
    r=_plan(invert=invert)
    assert r["source"]==SOURCE
    assert r["source_dfm_font_family"]=="Tahoma"
    assert r["source_gdi_font_height"]==-13
    assert r["source_dfm_pixels_per_inch"]==96
    assert r["whole_paintbox_event_coordinates"]
    assert r["source_original_textout_after_grid_before_series"]
    assert r["source_x_inverted"] is invert
    assert not r["original_win32_font_dpi_verified"]
    assert not r["original_gdi_pixel_parity_verified"]
    assert not r["original_delphi_rtl_formatfloat_verified"]
    canvas=r["canvas"]
    assert canvas["screen_x_reversed"] is invert
    assert canvas["pixel_left"]<canvas["pixel_right"]
    assert canvas["pixel_top"]<canvas["pixel_bottom"]
    assert r["textout"]["source_x_labels_enabled"]
    assert r["textout"]["source_y_labels_enabled"]
    events=r["events"]
    assert 16<=len(events)<=27
    assert set(e["kind"] for e in events)=={
        "x_tick","y_tick","x_name","y_name"}
    for e in events:
        assert isinstance(e["text"],str)
        assert type(e["x"]) is int and type(e["y"]) is int
    assert r["grid"]["source_auto_h_spacing"]==10
    assert r["grid"]["source_auto_v_spacing"]==10
    assert r["grid"]["x_tick_labels_candidate"][0]=="0"


def test_reversed_adc_canvas_maps_original_xticks_to_opposite_pixel_positions():
    normal=_plan(invert=False)
    reversed_=_plan(invert=True)
    xn={e["source_value"]:e["x"] for e in normal["events"]
        if e["kind"]=="x_tick"}
    xr={e["source_value"]:e["x"] for e in reversed_["events"]
        if e["kind"]=="x_tick"}
    assert xn.keys()==xr.keys()
    assert xn[0.]<xn[25600.]
    assert xr[0.]>xr[25600.]
    assert normal["grid"]["x_grid_ticks"]==reversed_["grid"]["x_grid_ticks"]
    assert normal["textout"]["font_metrics_provenance"]=="qt_approximation"


def test_deterministic_margins_and_no_samples_in_paintbox_contract():
    one=_plan()
    two=_plan()
    assert one["events"]==two["events"]
    assert one["canvas"]==two["canvas"]
    assert "samples" not in one and "bin" not in one
    assert "fft" not in one and "power" not in one
    assert all(e["text_width"]>=0 for e in one["events"])


@pytest.mark.parametrize("overrides",[
    {"width":40}, {"height":33},
    {"width":2048,"height":2048},
    {"width":True}, {"height":3.5},
    {"x_inverted":1},
    {"view_x":(0.,0.)}, {"view_x":(-math.inf,5.)},
    {"view_y":(math.nan,1.)}, {"view_y":(4.,-3.)},
    {"x_name":"\x00"},
    {"zero_text_width":-1},
    {"six_decimals_text_width":1000},
    {"text_height":None},
    {"font_provenance":"unverified_stated_as_exact"},
])
def test_source_paintbox_textout_bad_source_is_rejected(overrides):
    with pytest.raises((ValueError,TypeError)):
        _plan(**overrides)
