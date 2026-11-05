"""Stage111Z31D: explicitly separate observed Qt ViewBox geometry from Delphi.

All inputs here are measurements in *Qt device-independent logical coordinates*
from a QGraphicsView viewport and its ViewBox. DPR may inform a nominal
device-pixel SIZE, but must NOT be applied blindly to map Qt global origins
to screenshot physical pixels or to the original Delphi 32-bit TPaintBox.
No original runtime landmark, canvas font or DPI-awareness is inferred.
"""
from __future__ import annotations

import math
import numbers


SOURCE = "OBSERVED_QT_VIEWPORT_AND_VIEWBOX_RUNTIME_GEOMETRY"


def _finite(value: int | float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(f"{name} must be a real number")
    v = float(value)
    if not math.isfinite(v):
        raise ValueError(f"{name} must be finite")
    return v


def describe_qt_viewport_geometry(
        *, viewport_width: int, viewport_height: int,
        plot_left: float, plot_top: float,
        plot_right: float, plot_bottom: float,
        viewport_global_left: float, viewport_global_top: float,
        device_pixel_ratio: float, logical_dpi_x: int, logical_dpi_y: int,
        research_dock_visible: bool) -> dict:
    """Return one *current* Qt coordinate-frame observation with open gates.

    plot_left/top/right/bottom are mapped through
    QGraphicsView.mapFromScene(ViewBox.sceneBoundingRect()). Their origin
    is the Qt viewport (NOT the source-derived Delphi PixelRect).
    Global Qt coordinates may be virtualized by OS/Qt and are NOT certified
    as physical screenshot coordinates.
    """
    for name, value in (("viewport_width", viewport_width),
                        ("viewport_height", viewport_height),
                        ("logical_dpi_x", logical_dpi_x),
                        ("logical_dpi_y", logical_dpi_y)):
        if isinstance(value, bool) or not isinstance(value, numbers.Integral):
            raise ValueError(name + " must be an integer")
    if (not 8 <= viewport_width <= 100_000 or
            not 8 <= viewport_height <= 100_000 or
            not 24 <= logical_dpi_x <= 960 or
            not 24 <= logical_dpi_y <= 960):
        raise ValueError("Invalid Qt viewport size or logical DPI")
    if type(research_dock_visible) is not bool:
        raise ValueError("research_dock_visible must be a boolean")

    left = _finite(plot_left, "plot_left")
    top = _finite(plot_top, "plot_top")
    right = _finite(plot_right, "plot_right")
    bottom = _finite(plot_bottom, "plot_bottom")
    gl = _finite(viewport_global_left, "viewport_global_left")
    gt = _finite(viewport_global_top, "viewport_global_top")
    dpr = _finite(device_pixel_ratio, "device_pixel_ratio")
    if right <= left or bottom <= top or not .25 <= dpr <= 8:
        raise ValueError("Invalid Qt ViewBox bounds or DPR")
    width = right - left
    height = bottom - top
    inside = bool(
        -2 <= left < viewport_width + 2 and
        -2 <= top < viewport_height + 2 and
        -2 <= right <= viewport_width + 2 and
        -2 <= bottom <= viewport_height + 2
    )
    return {
        "source": SOURCE,
        "coordinate_system": "Qt viewport logical/device-independent pixels",
        "qt_viewport_size_logical": {
            "width": int(viewport_width), "height": int(viewport_height)},
        "qt_plot_bounds_in_viewport_logical": {
            "left": left, "top": top, "right": right, "bottom": bottom},
        "qt_plot_size_logical": {"width": width, "height": height},
        "qt_viewport_origin_global_logical": {"left": gl, "top": gt},
        "qt_plot_bounds_global_logical": {
            "left": gl + left, "top": gt + top,
            "right": gl + right, "bottom": gt + bottom},
        "qt_device_pixel_ratio_observed": dpr,
        "qt_logical_dpi_observed": {
            "x": int(logical_dpi_x), "y": int(logical_dpi_y)},
        "qt_plot_size_nominal_device_pixels_if_uniform_dpr": {
            "width": width * dpr, "height": height * dpr},
        "qt_plot_inside_viewport_with_2px_tolerance": inside,
        "research_dock_visible": research_dock_visible,
        "original_tpaintbox_runtime_rectangle_verified": False,
        "original_tcanvas_font_metrics_verified": False,
        "original_windows_dpi_awareness_verified": False,
        "qt_global_logical_equals_screenshot_physical_verified": False,
        "qt_to_delphi_pixel_parity_verified": False,
        "warning": (
            "Observed Qt logical coordinates only. DPR multiplication gives "
            "nominal sizes, not a certified absolute physical screenshot "
            "rectangle or a Delphi TPaintBox runtime PixelRect."),
    }


def compare_normalized_cursor_geometry(*,
        original_bounds: tuple[float, float, float, float],
        original_cursor: tuple[float, float],
        qt_bounds: tuple[float, float, float, float],
        qt_cursor: tuple[float, float]) -> dict:
    """Compare two independently measured screenshot rectangles by fractions.

    This records normalized landmark errors only; no claim of matching
    window sizes, DPI awareness, drawing pens, axis fonts or curve pixels.
    """
    def point_and_bounds(bounds, cursor, label):
        if not isinstance(bounds, tuple) or len(bounds) != 4:
            raise ValueError(label + " bounds must have four elements")
        if not isinstance(cursor, tuple) or len(cursor) != 2:
            raise ValueError(label + " cursor must have two elements")
        left, top, right, bottom = tuple(
            _finite(value, label) for value in bounds)
        x, y = tuple(_finite(value, label) for value in cursor)
        if right <= left or bottom <= top:
            raise ValueError(label + " bounds must be positive")
        fx = (x - left) / (right - left)
        fy = (y - top) / (bottom - top)
        if not (0 <= fx <= 1 and 0 <= fy <= 1):
            raise ValueError(label + " cursor must be inside plot bounds")
        return fx, fy, right - left, bottom - top
    ox, oy, ow, oh = point_and_bounds(original_bounds, original_cursor, "original")
    qx, qy, qw, qh = point_and_bounds(qt_bounds, qt_cursor, "Qt")
    return {
        "source": "TWO_SCREENSHOTS_NORMALIZED_CURSOR_GEOMETRY_ONLY",
        "original_cursor_fraction": {"x": ox, "y": oy},
        "qt_cursor_fraction": {"x": qx, "y": qy},
        "normalized_absolute_error": {
            "x": abs(ox - qx), "y": abs(oy - qy)},
        "error_projected_to_qt_plot_pixels": {
            "x": abs(ox - qx) * qw, "y": abs(oy - qy) * qh},
        "plot_height_and_width_identical": ow == qw and oh == qh,
        "windows_scaling_original_independently_verified": False,
        "original_tpaintbox_runtime_pixel_parity_verified": False,
        "qt_original_rendering_pixel_parity_verified": False,
    }
