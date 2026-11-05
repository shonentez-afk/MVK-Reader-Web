"""Stage111Z31H: source-derived TQGRSeries per-pixel min/max stroke model.

Recreated from operator-private Delphi _Unit115 007CB12F..007CB3E5,
007CA4C8, 007CABE4 and 007CAC18. No original PAS, measurement,
Windows binary, screenshots, or device data are distributed here.

This is source-control-flow parity, NOT native x87 or PixelRect parity.
A preview caller supplies its OWN pixel/axis frame (Qt logical pixels).
"""
from __future__ import annotations

import math
import numbers
import numpy as np

SOURCE = "SOURCE_DERIVED_TQGRSERIES_PIXEL_MINMAX_007CB12F_007CB3E5"
MAX_SAMPLES = 2_100_000
MAX_COLUMNS = 8_192


def _single(value, name):
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(name + " must be a finite real")
    out = float(value)
    if not math.isfinite(out) or abs(out) > 1e9:
        raise ValueError(name + " outside supported range")
    out = float(np.float32(out))
    if not math.isfinite(out):
        raise ValueError(name + " overflows Single")
    return out


def _pixel(value, name):
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise ValueError(name + " must be an integer")
    out = int(value)
    if not -100_000 <= out <= 100_000:
        raise ValueError(name + " outside bounded pixel frame")
    return out


def source_tqgr_series_contract():
    return {
        "source": SOURCE,
        "original_code_offsets": "007CA4C8/007CABE4/007CAC18/007CB12F-007CB3E5",
        "source_series_per_pixel_column_minmax": True,
        "source_initial_move_from_pixel_left_sample": True,
        "source_solid_false_required": True,
        "source_positive_width_index_window": "(stoi(x),stoi(x+1)]",
        "source_negative_width_index_window": "[stoi(x),stoi(x+1)+1] descending",
        "source_connect_to_closest_extreme_first": True,
        "source_column_clamps_y_to_pixel_top_bottom": True,
        "original_series_x87_exact_verified": False,
        "original_runtime_paintbox_verified": False,
        "original_series_native_tco2draw_pixels_verified": False,
    }


def source_tqgr_series_columns(
    values, *, scr_left, scr_width, scr_bottom, scr_height,
    x_start=0.0, x_scale=1.0, y_scale=1.0,
    pixel_left=0, pixel_right=800, pixel_top=0, pixel_bottom=400,
    solid=False,
):
    """Build original-style *column strokes*, independent of FFT and Qt.

    Each input is a TQGRSeries.Data Single, not raw ADC, Power or re-FFT.
    The mapping and collapse are performed in caller-supplied screen pixels.
    Returns ordered connected stroke segments in +Y-down pixel coordinates.
    Blending/line AA is a different original TCo2Draw stage, not done here.
    """
    if solid is not False:
        raise ValueError("only source Spectrum series Solid=False is modeled")
    data = np.asarray(values)
    if data.ndim != 1 or data.size == 0 or data.size > MAX_SAMPLES:
        raise ValueError("TQGRSeries requires bounded nonempty 1D samples")
    if data.dtype.kind not in "fi" or data.dtype.kind == "b":
        raise ValueError("series samples must be numeric Float32-compatible")
    data = np.asarray(data, dtype=np.float32)
    if not bool(np.isfinite(data).all()):
        raise ValueError("nonfinite source series is not pixel-certified")
    left = _pixel(pixel_left, "pixel_left")
    right = _pixel(pixel_right, "pixel_right")
    top = _pixel(pixel_top, "pixel_top")
    bottom = _pixel(pixel_bottom, "pixel_bottom")
    if not 2 <= right - left <= MAX_COLUMNS or not 2 <= bottom - top <= MAX_COLUMNS:
        raise ValueError("invalid research plot PixelRect")
    sleft = _single(scr_left, "scr_left")
    swidth = _single(scr_width, "scr_width")
    sbottom = _single(scr_bottom, "scr_bottom")
    sheight = _single(scr_height, "scr_height")
    xstart = _single(x_start, "x_start")
    xscale = _single(x_scale, "x_scale")
    yscale = _single(y_scale, "y_scale")
    if abs(swidth) < 1e-6 or sheight <= 1e-6 or xscale <= 0 or yscale <= 0:
        raise ValueError("invalid original TQGrapher screen or series scale")

    # 007CA638..007CA6C6 source: affine Single coordinates. 007CABE4
    # uses @TRUNC on x87 expression and clamps to [0,DataSize-1].
    pixw = right - left
    pixh = bottom - top
    stoi_m = float(np.float32(np.float32(swidth / pixw) / np.float32(xscale)))
    stoi_c = float(np.float32((sleft - xstart) / xscale))
    itos_m = float(np.float32(float(pixw) * xscale / swidth))
    itos_c = float(np.float32(left + (xstart - sleft) * pixw / swidth))
    ytos_m = float(np.float32(-pixh / sheight))
    ytos_c = float(np.float32(bottom + pixh * sbottom / sheight))
    if not all(math.isfinite(v) for v in (
            stoi_m, stoi_c, itos_m, itos_c, ytos_m, ytos_c)):
        raise ValueError("unrepresentable original Single affine transform")

    def index_at(pixel_x):
        raw = math.trunc((pixel_x - left) * stoi_m + stoi_c)
        return min(max(raw, 0), len(data) - 1)

    def project_y(arr):
        # 007CB251 and 007CAC18 round the y-scale product and then
        # the affine result to Single, before clamping PixelTop/Bottom.
        scaled = np.asarray(arr, dtype=np.float32) * np.float32(yscale)
        projected = np.float32(
            scaled.astype(np.float64) * ytos_m + ytos_c)
        return np.clip(projected, top, bottom)

    seed_index = index_at(left)
    seed_x = min(max(float(np.float32(seed_index * itos_m + itos_c)), left), right)
    seed_y = float(project_y(data[seed_index]))
    last_x, last_y = seed_x, seed_y
    result_columns = []
    strokes = []
    for x in range(left + 1, right + 1):
        a = index_at(x)
        b = index_at(x + 1)
        if swidth > 0:
            first = a + 1
            last = b
            if first > last:
                continue
            indices = data[first:last + 1]
        else:
            first = a
            last = b + 1
            if first < last:
                continue
            indices = data[last:first + 1]
        if len(indices) == 0:
            continue
        projected = project_y(indices)
        lo = float(np.min(projected))
        hi = float(np.max(projected))
        if lo > bottom or hi < top:
            continue
        # 007CB352..007CB3D7: connect to the closer extreme first,
        # then the other. This retains narrow peaks and preserves the
        # original zigzag stroke order; min/max alone is insufficient.
        first_y, second_y = (
            (hi, lo) if last_y - hi >= lo - last_y else (lo, hi)
        )
        strokes.append((last_x, last_y, float(x), first_y))
        last_x, last_y = float(x), first_y
        if second_y != first_y:
            strokes.append((last_x, last_y, float(x), second_y))
            last_y = second_y
        result_columns.append((x, lo, hi, first, last))

    return {
        "source": SOURCE,
        "data_size_original": int(data.size),
        "source_pixel_rect": (left, top, right, bottom),
        "screen_single": (sleft, swidth, sbottom, sheight),
        "source_series_single": (xstart, xscale, yscale),
        "single_stoi_coefficients": (stoi_m, stoi_c),
        "single_itos_coefficients": (itos_m, itos_c),
        "single_ytos_coefficients": (ytos_m, ytos_c),
        "initial_sample_index": seed_index,
        "initial_move_pixel": (seed_x, seed_y),
        "columns": tuple(result_columns),
        "segments": np.asarray(strokes, dtype=np.float64).reshape(-1, 4),
        "original_windows_pixel_parity_verified": False,
        "original_delphi_x87_parity_verified": False,
    }
