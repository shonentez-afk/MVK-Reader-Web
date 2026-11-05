"""Stage111Z31E synthetic SOURCE-grid model; not GDI screenshot parity."""
from __future__ import annotations

import math
import pytest

from mvk_compatible.core.tqgrapher_grid_idr_candidate import (
    SOURCE, source_tqgrapher_grid_candidate,
)


def test_source_specgrapher_10_divisions_per_direction_at_tag0_original_axis():
    g = source_tqgrapher_grid_candidate(
        scr_left=0, scr_width=25600,
        scr_bottom=-150, scr_height=150)
    assert g["source"] == SOURCE
    assert g["source_auto_h_spacing"] == 10
    assert g["source_auto_v_spacing"] == 10
    assert g["source_h_line_spacing_y_single"] == 15
    assert g["source_v_line_spacing_x_single"] == 2560
    assert g["x_grid_ticks"] == tuple(range(0, 25601, 2560))
    assert g["y_grid_ticks"] == tuple(range(-150, 1, 15))
    assert g["x_tick_labels_candidate"][0] == "0"
    assert g["x_tick_labels_candidate"][-1] == "25600"
    assert g["y_tick_labels_candidate"][0] == "-150"
    assert g["y_tick_labels_candidate"][-1] == "0"
    assert len(g["x_grid_ticks"]) == len(g["y_grid_ticks"]) == 11
    for key in (
        "original_runtime_source_grid_counts_verified",
        "original_rtl_tick_format_parity_verified",
        "original_gdi_grid_pen_color_verified",
        "original_runtime_tcanvas_font_verified",
        "original_delphi_pixel_grid_parity_verified",
        "native_canvas_or_dpi_inputs_used",
    ):
        assert g[key] is False, key


def test_candidate_regenerates_from_changing_range_not_pixel_count_or_dpr():
    full = source_tqgrapher_grid_candidate(
        scr_left=0, scr_width=25600, scr_bottom=-150, scr_height=150)
    zoom = source_tqgrapher_grid_candidate(
        scr_left=5000, scr_width=10000, scr_bottom=-90, scr_height=30)
    assert full["source_v_line_spacing_x_single"] == 2560
    assert zoom["source_v_line_spacing_x_single"] == 1000
    assert zoom["x_grid_ticks"][0] == 5000
    assert zoom["x_grid_ticks"][-1] == 15000
    assert zoom["source_h_line_spacing_y_single"] == 3
    assert zoom["y_grid_ticks"] == tuple(range(-90, -59, 3))
    assert "dpr" not in "".join(zoom.keys()).lower()


def test_noninteger_signed_screen_ranges_and_no_negative_zero_labels():
    g = source_tqgrapher_grid_candidate(
        scr_left=0.5, scr_width=10., scr_bottom=-1., scr_height=2.)
    assert g["source_v_line_spacing_x_single"] == 1
    assert g["x_grid_ticks"] == tuple(range(1, 11))
    assert g["source_h_line_spacing_y_single"] == pytest.approx(.2)
    assert g["y_tick_labels_candidate"][-1] == "1"
    assert "0" in g["y_tick_labels_candidate"]
    assert "-0" not in g["y_tick_labels_candidate"]


@pytest.mark.parametrize("patch", [
    {"scr_left": float("nan")},
    {"scr_width": 0},
    {"scr_width": -1},
    {"scr_bottom": float("-inf")},
    {"scr_height": 0},
    {"scr_height": -100},
    {"scr_left": 1e100},
    {"auto_v_spacing": 0},
    {"auto_v_spacing": 101},
    {"auto_v_spacing": 10.0},
    {"auto_h_spacing": True},
    {"auto_h_spacing": 0},
])
def test_invalid_grid_ranges_and_counts_rejected(patch):
    kwargs=dict(scr_left=0,scr_width=25600,scr_bottom=-150,scr_height=150)
    kwargs.update(patch)
    with pytest.raises(ValueError):
        source_tqgrapher_grid_candidate(**kwargs)


def test_custom_count_only_a_research_synthetic_not_source_acceptance():
    result=source_tqgrapher_grid_candidate(
        scr_left=0,scr_width=25600,scr_bottom=-150,scr_height=150,
        auto_v_spacing=5,auto_h_spacing=5)
    assert result["source_v_line_spacing_x_single"] == 5120
    assert result["source_h_line_spacing_y_single"] == 30
    assert len(result["x_grid_ticks"]) == len(result["y_grid_ticks"]) == 6
    assert result["original_runtime_source_grid_counts_verified"] is False



@pytest.mark.parametrize("value,expected", [
    (0., "0"),
    (-0., "0"),
    (1000., "1000"),
    (123.456, "123"),
    (99.5, "99,5"),
    (12.34, "12,3"),
    (-1.25, "-1,25"),
    (.00123, "0,00123"),
    (.000001234, "0,00000123"),
])
def test_source_unit114_007b2090_fixed_point_three_digit_mask(value,expected):
    from mvk_compatible.core.tqgrapher_grid_idr_candidate import _label
    assert _label(value,1.) == expected


def test_original_rtl_formatting_control_flow_not_fake_delphi_parity():
    from mvk_compatible.core.tqgrapher_grid_idr_candidate import _label
    assert _label(1.25,1.,decimal_separator=".") == "1.25"
    with pytest.raises(ValueError,match="decimal"):
        _label(1.25,1.,decimal_separator=";")
    g=source_tqgrapher_grid_candidate(
        scr_left=0,scr_width=10,scr_bottom=-1,scr_height=2)
    assert g["source_label_formatter"].startswith("UNIT114_007B2090")
    assert g["source_label_decimal_separator_qt_candidate"] == ","
    assert g["y_tick_labels_candidate"][1].startswith("-0,")
    assert g["original_rtl_tick_format_parity_verified"] is False
