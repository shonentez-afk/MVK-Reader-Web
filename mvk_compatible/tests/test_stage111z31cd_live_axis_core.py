"""Source numeric tick contract, including original reversed ADC X."""
import math
import pytest

from ..core.original_live_axis_ticks import (
    source_live_axis_ticks, source_live_axis_tick_text,
)
from ..core.tqgrapher_grid_idr_candidate import source_tqgrapher_grid_candidate


@pytest.mark.parametrize("left,width", [
    (0.0, 25600.0), (100.0, -100.0), (2.5, -2.5),
    (-50.0, 100.0), (0.0, 0.0125), (20.0, -0.02),
])
def test_source_live_ticks_share_the_verified_10x10_numeric_candidate(left,width):
    model = source_live_axis_ticks(scr_left=left,scr_width=width)
    original = source_tqgrapher_grid_candidate(
        scr_left=min(left,left+width),scr_width=abs(width),
        scr_bottom=0.0,scr_height=10.0)
    assert model["values"] == original["x_grid_ticks"]
    assert model["texts"] == original["x_tick_labels_candidate"]
    assert model["spacing_single"] == original["source_v_line_spacing_x_single"]
    assert model["source_screen_width_reversed"] == (width < 0)
    assert 2 <= len(model["values"]) <= 12
    assert not model["original_win32_runtime_ticks_verified"]
    assert not model["original_font_gdi_parity_verified"]


def test_source_tick_format_is_not_qt_autorange_locale_guess():
    assert source_live_axis_tick_text(1.25, 1.25) == "1,25"
    assert source_live_axis_tick_text(0, 1) == "0"
    assert source_live_axis_tick_text(-2.5, 1,decimal_separator=".") == "-2.5"


@pytest.mark.parametrize("left,width,count", [
    (0,0,10), (0,1e-10,10), (math.nan,1,10),
    (0,math.inf,10), (True,1,10), (0,False,10),
    (0,1,True), (0,1,0), (0,1,101),
])
def test_source_ticks_fail_closed_for_unrepresentable_ranges(left,width,count):
    with pytest.raises(ValueError):
        source_live_axis_ticks(scr_left=left,scr_width=width,
                               auto_spacing=count)
