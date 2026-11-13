"""Full source live grid + X-only cursor/clip contracts (no GUI or BIN)."""
import math

import pytest

from ..core.original_graph_layout import source_graph_layout
from ..core.original_live_axis_ticks import source_live_axis_ticks
from ..core.original_live_grid_cursor import (
    source_live_grid_frame, source_live_cursor_hit,
    source_live_clip_crosshair,
)
from ..core.tco2draw_grid_source import GRID_LINE_HEX


@pytest.mark.parametrize("xlo,xhi,ylo,yhi", [
    (0., 25600., -150., 0.),
    (0., 1., -5., 5.),
    (19.98, 20., -0.001, 0.009),
    (-50., 50., -1., 1.),
])
def test_live_grid_reuses_source_single_tick_model_and_order(xlo,xhi,ylo,yhi):
    frame=source_live_grid_frame(view_x=(xlo,xhi),view_y=(ylo,yhi))
    x=source_live_axis_ticks(scr_left=xlo,scr_width=xhi-xlo)
    y=source_live_axis_ticks(scr_left=ylo,scr_width=yhi-ylo)
    assert frame["x_ticks"]==x["values"]
    assert frame["y_ticks"]==y["values"]
    assert frame["x_tick_labels"]==x["texts"]
    assert frame["y_tick_labels"]==y["texts"]
    assert frame["source_grid_hex"]==GRID_LINE_HEX
    assert frame["source_original_grid_before_series"]
    assert len(frame["x_ticks"])<=12
    assert len(frame["y_ticks"])<=12
    assert not frame["original_gdi_raster_pixel_parity_verified"]


def test_strict_original_pixelrect_and_source_mouse_y_ignored():
    canvas=source_graph_layout(width=791,height=740,zero_width=7,
                               six_decimals_width=56,text_height=15)
    left=canvas["pixel_left"]
    right=canvas["pixel_right"]
    assert (left,right)==(77,777)
    for x, expected in [(100., False),(101.,True),(450.,True),
                        (799.,True),(800.,False),(-100.,False)]:
        hit=source_live_cursor_hit(
            canvas=canvas,scene_left=100.,scene_right=800.,
            scene_x=x)
        assert hit["inside_original_pixel_rect"]==expected
        assert hit["qt_logical_pixel_space"]
        assert not hit["original_paintbox_runtime_registration_verified"]


def test_cursor_clip_rejects_x_edges_and_clamps_raw_y_without_changing_sample():
    args=dict(left=100.,right=800.,top=-3.,bottom=7.)
    for x in (99.,100.,800.,801.):
        assert source_live_clip_crosshair(**args,x=x,y=2.) is None
    low=source_live_clip_crosshair(**args,x=250.,y=-30.)
    high=source_live_clip_crosshair(**args,x=250.,y=40.)
    assert low["y"] == -3. and low["raw_y_unchanged"] == -30.
    assert high["y"] == 7. and high["raw_y_unchanged"] == 40.
    assert low["source_vertical_segment"]==(250.,-3.,250.,7.)
    assert high["source_horizontal_segment"]==(100.,7.,800.,7.)
    assert low["source_original_pm_xor"]
    assert not low["original_windows_gdi_pixel_parity_verified"]


@pytest.mark.parametrize("bad", [
    ((2.,2.),(0.,1.)), ((5.,2.),(0.,1.)),
    ((0.,1.),(math.nan,1.)),
    ((0.,1.),(0.,math.inf)),
])
def test_invalid_viewport_cannot_publish_source_grid(bad):
    with pytest.raises(ValueError):
        source_live_grid_frame(view_x=bad[0],view_y=bad[1])


def test_invalid_canvas_and_numeric_mouse_fail_closed():
    canvas=source_graph_layout(width=791,height=740,zero_width=7,
                               six_decimals_width=56,text_height=15)
    for x in (math.nan, math.inf, True):
        with pytest.raises(ValueError):
            source_live_cursor_hit(canvas=canvas,
                scene_left=100.,scene_right=800.,scene_x=x)
    with pytest.raises(ValueError):
        source_live_cursor_hit(canvas={},
            scene_left=100.,scene_right=800.,scene_x=500.)
