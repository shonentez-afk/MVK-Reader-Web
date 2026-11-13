"""Actual TCo2Draw 32-bit software GRID on ordinary PageAdc/PageSpectrum.

Use previously audited Unit115 TCo2Draw 007C98B4/007C9A30
scanline line blending and the existing 10x10 Single grid candidate,
rather than QPainter QPen stroke approximation. Unit115 Draw renders
horizontal grid lines first, vertical grid lines second, before series.
This paints only the VIEWBOX viewport, not Delphi's complete PaintBox
TextOut/frame; original native Win32 TCanvas/DPI pixel parity is open.

Neither ZIP/BIN, FIR, FFT, nor series samples are accepted as inputs.
"""
from __future__ import annotations

from hashlib import sha256
import numbers
import numpy as np

from .original_live_grid_cursor import source_live_grid_frame
from .tco2draw_raster_candidate import (
    source_grid_segments, source_raster_rgba,
)
from .tco2draw_grid_source import GRID_LINE_RGB, BACKGROUND_RGB

SOURCE = "SOURCE_DERIVED_LIVE_TCO2DRAW_SOFTWARE_GRID_STAGE111Z31CF"
MAX_SOURCE_SOFTWARE_PIXELS = 2_500_000


def source_live_software_grid_bitmap(*, view_x, view_y, width, height):
    """Render a bounded RGBA TCo2Draw grid in Qt LOGICAL plot pixels.

    Source point order is horizontal (Y) first then vertical (X), as
    Unit115:007CAD77 and 007CAE4E. A 150% Windows DPR must NOT be
    multiplied into this image: QWidget painting already scales device
    pixels. The caller retains its full Core signal/FFT independently.
    """
    if (type(width) is not int or type(height) is not int or
            not 4 <= width <= 10000 or not 4 <= height <= 10000 or
            width * height > MAX_SOURCE_SOFTWARE_PIXELS):
        raise ValueError("Source Qt logical ViewBox outside raster budget")
    frame = source_live_grid_frame(view_x=view_x, view_y=view_y)
    segments = source_grid_segments(
        x_ticks=frame["x_ticks"], y_ticks=frame["y_ticks"],
        view_x=frame["viewport_x"], view_y=frame["viewport_y"],
        width=width, height=height)
    nx = len(frame["x_ticks"])
    # source_grid_segments lists vertical first; original TQGrapher
    # draws horizontal first, before source series and plot frame.
    ordered = segments[nx:] + segments[:nx]
    image = source_raster_rgba(
        width=width, height=height, segments=ordered,
        ink=GRID_LINE_RGB, background=BACKGROUND_RGB)
    if image.shape != (height,width,4) or image.dtype!=np.uint8:
        raise ValueError("Invalid source TCo2Draw RGBA raster")
    return {
        "source": SOURCE,
        "rgba": image,
        "view_x": frame["viewport_x"],
        "view_y": frame["viewport_y"],
        "logical_size": (width,height),
        "grid_x_count": nx,
        "grid_y_count": len(frame["y_ticks"]),
        "original_source_layer_order": (
            "background", "horizontal_grid", "vertical_grid",
            "series_in_separate_live_Qt_layer", "frame_in_separate_live_Qt_layer"),
        "source_scanline_32bit_blending": True,
        "source_actual_software_grid_raster_not_qt_pen": True,
        "source_original_rgb_grid": GRID_LINE_RGB,
        "source_original_rgb_background": BACKGROUND_RGB,
        "rgba_sha256": sha256(image.tobytes()).hexdigest(),
        "original_native_tcanvas_gdi_font_verified": False,
        "original_win32_pixel_parity_verified": False,
        "full_original_paintbox_bitmap_rendered": False,
        "qt_device_pixel_ratio_inflation_used": False,
    }
