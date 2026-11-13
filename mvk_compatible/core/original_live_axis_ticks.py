"""Source-derived live TQGrapher ticks for PageAdc and PageSpectrum.

Private _Unit115:007CAC89..007CACAF computes horizontal/vertical line
spacing as Single(ScrHeight / AutoHSpacing) and
Single(abs(ScrWidth / AutoVSpacing)). 007CAD2F..007CAD67 bounds integer
multiples using the original 0.0001 tolerance. Reuse the already audited
Unit114 three-digit fixed-point formatter candidate. The SAME contract
applies to an inverted ADC time axis and to the spectrum frequency axis.

This models *numeric positions and text*, not Win32 GDI glyphs, original
Canvas clipping, device DPI or Float32/x87 0-ULP runtime parity.
"""
from __future__ import annotations

import math
import numbers
import numpy as np

from .tqgrapher_grid_idr_candidate import (
    source_tqgrapher_grid_candidate, _label,
)

SOURCE = "APP_DERIVED_TQGRAPHER_LIVE_10X10_TICKS_SOURCE"
ORIGINAL_AUTO_SPACING = 10


def source_live_axis_tick_text(value: float, spacing: float, *,
                               decimal_separator: str = ",") -> str:
    """Source Unit114 FormatFloat candidate shared with the research grid."""
    return _label(value, spacing, decimal_separator=decimal_separator)


def source_live_axis_ticks(*, scr_left: float, scr_width: float,
                           auto_spacing: int = ORIGINAL_AUTO_SPACING) -> dict:
    """One source 10-division axis, including reversed ADC ScrWidth.

    No samples, FFT arrays or calibrated physical units are passed here.
    Screen coordinates are converted to original Delphi Single before
    computing the tick interval and the candidate labels.
    """
    if (isinstance(scr_left, bool) or not isinstance(scr_left, numbers.Real)
            or isinstance(scr_width, bool) or
            not isinstance(scr_width, numbers.Real)):
        raise ValueError("ScrLeft/ScrWidth must be real scalars")
    if type(auto_spacing) is not int or not 1 <= auto_spacing <= 100:
        raise ValueError("AutoV/HSpacing must be a source integer in 1..100")
    if not all(math.isfinite(float(v)) for v in (scr_left, scr_width)):
        raise ValueError("Nonfinite TQGrapher source screen")
    with np.errstate(over="ignore", invalid="ignore"):
        left = float(np.float32(scr_left))
        width = float(np.float32(scr_width))
        low = float(np.float32(left + width)) if width < 0.0 else left
        span = float(np.float32(abs(width)))
    if not all(math.isfinite(v) for v in (left, width, low, span)):
        raise ValueError("Original Single screen overflow")
    if span < float(np.float32(1e-6)):
        raise ValueError("Screen too narrow for trustworthy source ticks")
    # The existing independently tested model handles Source Single
    # divisions, 0.0001 range tolerance and FormatFloat candidate.
    grid = source_tqgrapher_grid_candidate(
        scr_left=low, scr_width=span,
        scr_bottom=0.0, scr_height=10.0,
        auto_v_spacing=auto_spacing, auto_h_spacing=10)
    return {
        "source": SOURCE,
        "source_auto_spacing": auto_spacing,
        "source_screen_width_reversed": width < 0.0,
        "spacing_single": grid["source_v_line_spacing_x_single"],
        "values": grid["x_grid_ticks"],
        "texts": grid["x_tick_labels_candidate"],
        "source_float32_spacings": True,
        "source_index_tolerance": grid["source_approx_index_tolerance"],
        "original_font_gdi_parity_verified": False,
        "original_win32_runtime_ticks_verified": False,
        "original_x87_rounding_parity_verified": False,
    }
