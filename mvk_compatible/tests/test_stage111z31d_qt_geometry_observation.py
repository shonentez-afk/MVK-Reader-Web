"""Stage111Z31D synthetic-only Qt logical/DPR geometry and screenshot cursor tests."""
from __future__ import annotations

import math

import pytest

from mvk_compatible.core.qt_spectrum_viewport_observation import (
    SOURCE, compare_normalized_cursor_geometry,
    describe_qt_viewport_geometry,
)


def _qt_observation(**kwargs):
    values = dict(
        viewport_width=789, viewport_height=522,
        plot_left=55, plot_top=0, plot_right=779, plot_bottom=502,
        viewport_global_left=160, viewport_global_top=80,
        device_pixel_ratio=1.5,
        logical_dpi_x=96, logical_dpi_y=96,
        research_dock_visible=True,
    )
    values.update(kwargs)
    return describe_qt_viewport_geometry(**values)


def test_observed_qt_geometry_does_not_mislabel_model_delphi_rect():
    d = _qt_observation()
    assert d["source"] == SOURCE
    assert d["qt_viewport_size_logical"] == {
        "width": 789, "height": 522}
    assert d["qt_plot_bounds_in_viewport_logical"] == {
        "left": 55., "top": 0., "right": 779., "bottom": 502.}
    assert d["qt_plot_size_logical"] == {
        "width": 724., "height": 502.}
    assert d["qt_viewport_origin_global_logical"] == {
        "left": 160., "top": 80.}
    assert d["qt_plot_bounds_global_logical"] == {
        "left": 215., "top": 80., "right": 939., "bottom": 582.}
    assert d["qt_plot_inside_viewport_with_2px_tolerance"]
    assert d["qt_device_pixel_ratio_observed"] == 1.5
    assert d["qt_logical_dpi_observed"] == {"x": 96, "y": 96}
    assert d["qt_plot_size_nominal_device_pixels_if_uniform_dpr"] == {
        "width": 1086., "height": 753.}
    assert d["research_dock_visible"] is True
    for key in (
        "original_tpaintbox_runtime_rectangle_verified",
        "original_tcanvas_font_metrics_verified",
        "original_windows_dpi_awareness_verified",
        "qt_global_logical_equals_screenshot_physical_verified",
        "qt_to_delphi_pixel_parity_verified",
    ):
        assert d[key] is False, key


@pytest.mark.parametrize("dpr", [1., 1.25, 1.5, 2.])
def test_dpr_does_not_change_logical_viewbox_or_global_origin(dpr):
    base = _qt_observation(device_pixel_ratio=1.)
    scaled = _qt_observation(device_pixel_ratio=dpr)
    assert (scaled["qt_plot_bounds_global_logical"]
            == base["qt_plot_bounds_global_logical"])
    assert (scaled["qt_plot_bounds_in_viewport_logical"]
            == base["qt_plot_bounds_in_viewport_logical"])
    assert scaled["qt_plot_size_nominal_device_pixels_if_uniform_dpr"]["width"] == (
        base["qt_plot_size_logical"]["width"] * dpr)
    assert scaled["qt_to_delphi_pixel_parity_verified"] is False


@pytest.mark.parametrize("patch", [
    {"viewport_width": 0}, {"viewport_width": True},
    {"viewport_height": 7}, {"logical_dpi_x": 0},
    {"logical_dpi_y": 96.5}, {"device_pixel_ratio": float("nan")},
    {"device_pixel_ratio": 0},
    {"device_pixel_ratio": 9},
    {"plot_right": 55}, {"plot_bottom": -2},
    {"plot_left": float("inf")}, {"viewport_global_left": float("nan")},
    {"research_dock_visible": "true"},
])
def test_invalid_coordinate_systems_fail_closed(patch):
    with pytest.raises(ValueError):
        _qt_observation(**patch)


def test_second_monitor_negative_global_origin_is_supported():
    d = _qt_observation(viewport_global_left=-2100,viewport_global_top=-30)
    assert d["qt_plot_bounds_global_logical"]["left"] == -2045
    assert d["qt_plot_bounds_global_logical"]["bottom"] == 472
    assert not d["original_windows_dpi_awareness_verified"]


def test_observed_screenshot_cursor_agrees_but_not_full_pixel_parity():
    # Values from the existing *user-provided* 1920x1080 screenshots.
    # Plot rectangles were estimated visually, not extracted from live
    # TCanvas or Qt QGraphicsView registers. This test MUST NOT label
    # the original runtime TPaintBox DPI or full rendering as verified.
    d = compare_normalized_cursor_geometry(
        original_bounds=(605, 193, 1639, 911),
        original_cursor=(758, 458),
        qt_bounds=(393, 195, 1910, 919),
        qt_cursor=(618, 462))
    assert d["source"] == "TWO_SCREENSHOTS_NORMALIZED_CURSOR_GEOMETRY_ONLY"
    assert d["error_projected_to_qt_plot_pixels"]["x"] == pytest.approx(
        .5309477756286, abs=1e-8)
    assert d["error_projected_to_qt_plot_pixels"]["y"] == pytest.approx(
        .2144846796657, abs=1e-8)
    assert not d["plot_height_and_width_identical"]
    assert d["qt_original_rendering_pixel_parity_verified"] is False
    assert d["original_tpaintbox_runtime_pixel_parity_verified"] is False
    assert d["windows_scaling_original_independently_verified"] is False


@pytest.mark.parametrize("patch", [
    {"original_bounds": (10, 0, 10, 50)},
    {"original_cursor": (-1, 0)},
    {"qt_bounds": (1, 2, 3)},
    {"qt_cursor": (math.nan, 10)},
    {"qt_cursor": (220, 30)},
])
def test_bad_original_qt_landmarks_are_not_compared(patch):
    values = dict(
        original_bounds=(0, 0, 100, 100),
        original_cursor=(20, 30),
        qt_bounds=(10, 20, 210, 120),
        qt_cursor=(50, 50))
    values.update(patch)
    with pytest.raises(ValueError):
        compare_normalized_cursor_geometry(**values)
