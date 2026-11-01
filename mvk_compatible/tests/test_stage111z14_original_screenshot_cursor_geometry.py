"""Stage111Z.14: original MVKView 1.0.47 screenshot-derived graph reference.

Reference comes from ONE operator screenshot, 1920x1080 on 2026-11-01.
The PNG is PRIVATE and is NOT committed to GitHub/CircleCI. These are
only derived pixel coordinates, visible axis labels and operator-reported
original x32dbg numbers. This is NOT original Qt/GDI pixel parity.
"""
from __future__ import annotations

import math

from mvk_compatible.core.tqgrapher_display_idr_candidate import (
    spectrum_display_contract, cursor_string_candidate,
)

# Global screenshot pixels (full-resolution PNG, NOT shrunk chat preview).
ORIGINAL_SCREENSHOT_SIZE = (1920,1080)
ORIGINAL_PLOT_RECT = (605,193,1639,911)  # L,T,R,B, black border
ORIGINAL_CROSSHAIR_PIXELS = (758,458)   # observed magenta vertical/horizontal
ORIGINAL_X_RANGE_HZ = (0.,25600.)
ORIGINAL_Y_RANGE_DB = (-150.,0.)
ORIGINAL_CURSOR_DISPLAY = (3800.,-55.32)
ORIGINAL_NUMERIC_LABELS = ("6,89","3800","0,7786")


def test_original_screenshot_display_frequency_upper_limit_not_nyquist():
    """Original graph 25600 != Nyquist 32768, for N=262144 Fs=65536."""
    contract = spectrum_display_contract(262144, 65536)
    assert contract["full_fft_power_bins"] == 131072
    assert contract["grapher_series_bins"] == 102400
    assert contract["grapher_last_index"] == 102399
    assert contract["x_scale_single_hz"] == .25
    assert contract["grapher_last_frequency_hz"] == 25599.75
    # The original visible axis R is an endpoint, not the last populated bin.
    assert ORIGINAL_X_RANGE_HZ[1] == 102400*.25 == 25600
    assert ORIGINAL_X_RANGE_HZ[1] != 65536/2
    assert contract["original_pixel_rectangle_verified"] is False


def test_original_cursor_position_is_within_one_pixel_of_visible_axis_mapping():
    left,top,right,bottom = ORIGINAL_PLOT_RECT
    frequency,db = ORIGINAL_CURSOR_DISPLAY
    assert ORIGINAL_SCREENSHOT_SIZE == (1920,1080)
    assert left < right < 1920 and top < bottom < 1080
    fraction_x = (frequency-ORIGINAL_X_RANGE_HZ[0])/(
        ORIGINAL_X_RANGE_HZ[1]-ORIGINAL_X_RANGE_HZ[0])
    fraction_y = (ORIGINAL_Y_RANGE_DB[1]-db)/(
        ORIGINAL_Y_RANGE_DB[1]-ORIGINAL_Y_RANGE_DB[0])
    prediction_x = left+fraction_x*(right-left)
    prediction_y = top+fraction_y*(bottom-top)
    assert math.isclose(prediction_x,758.484375,abs_tol=1e-10)
    assert math.isclose(prediction_y,457.7984,abs_tol=1e-7)
    assert abs(ORIGINAL_CROSSHAIR_PIXELS[0]-prediction_x)<1
    assert abs(ORIGINAL_CROSSHAIR_PIXELS[1]-prediction_y)<1


def test_original_cursor_hint_text_candidate_for_displayed_rounded_values():
    """Screenshot shows 3800 Hz / -55,32 dB, NOT peak 0,7786 m/s^2."""
    hint=cursor_string_candidate(
        3800.0,-55.32,
        x_name="Гц",y_name="дБ",cursor_sep="\r\n",
        decimal_separator=",",
    )
    assert hint["x_text"] == "3800 Гц"
    assert hint["y_texts"] == ["-55,32 дБ"]
    assert hint["text"] == "3800 Гц\r\n-55,32 дБ"
    assert hint["original_Delphi_FormatFloat_parity_verified"] is False


def test_original_screenshot_peak_summary_differs_in_units_from_db_cursor():
    assert ORIGINAL_NUMERIC_LABELS == ("6,89","3800","0,7786")
    # Original left panel uses physical summary units while cursor uses dB.
    assert ORIGINAL_CURSOR_DISPLAY[1] != float(
        ORIGINAL_NUMERIC_LABELS[2].replace(",","."))
