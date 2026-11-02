"""Stage111Z30B: source-derived original GetSpectrum power -> display Y.

Original PRIVATE source _Unit115 GetSpectrum:
  007D15DD..1649 Tag0 uses 00447DB8 LOG10 and stores -180 or Single Y.
  007D1652..16A2 / 16DC..172C / 179B..17E7 Tag1/2/3 apply
  FSTP Single(FRange/(N/2)), SQRT(power/2), FSTP Single Y.
Original helper 00447DB8 at Winapi.Messages.pas: FLDLG2; FLD Single;
FYL2X = log10(Single). Source verified, NOT original x87 runtime parity.

Input must be already source-ordered, post-low-bin/mode-integration power;
this helper does NOT repeat FFT, low-bin clipping, integration or FRange
division. It never connects to equipment or changes archived measurements.
"""
from __future__ import annotations

import math
import numpy as np

SOURCE = "APP_DERIVED_GETSPECTRUM_DISPLAY_FLOAT32_SOURCE_CANDIDATE"


def source_derived_mode_display(power: np.ndarray, *, n_fft: int,
                                mode: int, f_range: float = 1.) -> np.ndarray:
    """GetSpectrum [EBP-2C] full powers -> [EBP-30] full stored Single Y.

    Source-compatible intermediate Single stores are honored, but NumPy
    log10 and sqrt are NOT certified bitwise against Delphi Win32/x87.
    Input may be a view; no data are modified in place.
    """
    if (type(n_fft) is not int or n_fft < 1024 or n_fft > 262144
        or (n_fft & (n_fft - 1)) or type(mode) is not int
        or mode not in (0, 1, 2, 3)):
        raise ValueError("Original FFT size or display mode invalid")
    if not math.isfinite(f_range) or f_range <= 0:
        raise ValueError("Original FRange must be positive and finite")
    range32 = np.float32(f_range)
    if not np.isfinite(range32) or range32 <= 0:
        raise ValueError("Original Float32 FRange is unrepresentable")
    p = np.asarray(power, dtype="<f4")
    half = n_fft // 2
    if (p.ndim != 1 or p.size != half
        or not bool(np.isfinite(p).all()) or bool((p < 0).any())):
        raise ValueError("Full N/2 finite nonnegative post-mode Float32 powers required")
    if mode == 0:
        # 007D15DD: call LOG10(Single(half)), *2, FSTP Single [EBP-18].
        # 007D161E: LOG10(Single(power)), subtract stored Single offset,
        # *10, FSTP Single output. Zero/negative source -> -180 Single.
        offset = float(np.float32(2. * math.log10(float(np.float32(half)))))
        y = np.full(half, np.float32(-180.), dtype="<f4")
        positive = p > 0
        if np.any(positive):
            y[positive] = np.asarray(
                (np.log10(p[positive].astype(np.float64)) - offset) * 10.,
                dtype="<f4")
    else:
        # 007D165D (or 16E7/17A6): FSTP Single original Y scale.
        # 007D167F (or 1709/17C4): sqrt(power/2) * stored Single scale,
        # FSTP Single output. The preceding power integration is elsewhere.
        scale = float(np.float32(float(range32) / float(half)))
        y = np.asarray(np.sqrt(p.astype(np.float64) / 2.) * scale,
                       dtype="<f4")
    if not bool(np.isfinite(y).all()):
        raise ValueError("Original-inspired display overflowed Float32")
    return y


def display_source_provenance() -> dict:
    """Static original-source anchors, not a runtime original parity claim."""
    return {
        "source": SOURCE,
        "original_log10_helper_flDLG2_FYL2X_source_verified": True,
        "original_mode0_log10_and_single_offset_source_verified": True,
        "original_linear_single_scale_and_output_source_verified": True,
        "original_mode2_3_integration_done_upstream": True,
        "original_x87_log10_sqrt_float32_bitwise_parity_verified": False,
        "original_full_display_y_runtime_parity_verified": False,
    }
