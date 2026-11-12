"""Stage111Z31BO: original Power/Y -> CURRENT source bitmap -> original PNG.

Pure offline Core. The numeric original capture is SHA-verified, the bitmap
must be EXACTLY the software composite shown by PageSpectrum at its CURRENT
X/Y viewport, and the operator's original PNG must have the same dimensions.
Combines the existing pixel-region diagnostics with an RGBA visual diff; no
native original Windows process, private screenshot or device is involved.

Pixel equality and an operator declaration are NOT Win32/GDI authentication.
"""
from __future__ import annotations

from hashlib import sha256
import math

import numpy as np

from .original_spectrum_x32dbg_reference import (
    OriginalSpectrumReference, SOURCE as REFERENCE_SOURCE)
from .spectrum_graph_pixel_audit import (
    make_source_pixel_manifest, compare_local_graph_pixel_audit)
from .tqgrapher_viewport_sync_source import bitmap_viewport_signature


SOURCE = "SOURCE_BOUND_CURRENT_PAGESPECTRUM_ORIGINAL_PIXEL_COMPARISON_STAGE111Z31BO"
MAX_RESOLUTION = 6_000_000


def _signature(reference, spectrum, composite_bitmap, canvas, model,
               view_x, view_y):
    if not isinstance(reference, OriginalSpectrumReference):
        raise ValueError("Local original SHA-checked Power/Y reference required")
    if (sha256(np.asarray(reference.power, dtype="<f4").tobytes()).hexdigest()
            != reference.power_sha256 or
            sha256(np.asarray(reference.display_y, dtype="<f4").tobytes()).hexdigest()
            != reference.display_y_sha256):
        raise ValueError("Original Power or Y changed after SHA-checked load")
    if (not isinstance(spectrum, dict)
            or spectrum.get("source") != REFERENCE_SOURCE
            or spectrum.get("original_capture_reference_only") is not True
            or spectrum.get("mode") != reference.mode
            or spectrum.get("n_fft") != reference.n_fft):
        raise ValueError("Visible PageSpectrum does not show this original Power/Y")
    values = np.asarray(spectrum.get("amplitude"), dtype="<f4")
    if (values.ndim != 1 or len(values) != reference.n_fft // 2 or
            sha256(values.tobytes()).hexdigest() != reference.display_y_sha256):
        raise ValueError("Visible full Float32 Y differs from loaded reference")
    df = spectrum.get("df_hz")
    if (not isinstance(df, (int, float)) or not math.isfinite(df)
            or not math.isclose(
                float(df) * reference.n_fft, reference.fs_hz,
                rel_tol=0, abs_tol=0.0001)):
        raise ValueError("Current spectrum frequency grid differs from Power/Y")
    if (not isinstance(composite_bitmap, np.ndarray)
            or composite_bitmap.ndim != 3
            or composite_bitmap.dtype != np.uint8
            or composite_bitmap.shape[2] != 4):
        raise ValueError("Current pristine RGBA source bitmap required")
    h, w, _ = composite_bitmap.shape
    if (w < 64 or h < 64 or w*h > MAX_RESOLUTION):
        raise ValueError("Current bitmap dimensions outside safe limits")
    if not isinstance(model, dict) or model.get("combined_preview_active") is not True:
        raise ValueError("Combined grid, text, series and frame must be ACTIVE")
    if not isinstance(canvas, dict) or model.get("combined_canvas") is not canvas:
        raise ValueError("Current bitmap and source Canvas are not identical objects")
    expected = bitmap_viewport_signature(
        view_x=view_x, view_y=view_y, width=w, height=h,
        raster=True, composite=True)
    if model.get("bitmap_viewport_signature") != expected:
        raise ValueError("Source bitmap is STALE after zoom, pan or viewport resize")
    if model.get("qt_raster_size") != (w,h):
        raise ValueError("Current bitmap does not match the displayed image size")
    return expected


def visual_pixel_difference(original, candidate, pixelrect):
    """Bounded red plot / amber axis mismatch mask, no screenshot in report.

    Exact pixels are white; RGB errors of 1 are pale gray; >1 are colored.
    This is a DIAGNOSTIC RGBA visualization, not a new native GDI render.
    """
    a=np.asarray(original)
    b=np.asarray(candidate)
    if (a.shape != b.shape or a.dtype != np.uint8 or b.dtype != np.uint8
            or a.ndim != 3 or a.shape[2] != 4
            or a.shape[0]*a.shape[1] > MAX_RESOLUTION
            or not all(x>0 for x in a.shape[:2])):
        raise ValueError("Difference mask requires equal bounded RGBA frames")
    l,t,r,bottom=pixelrect
    h,w=a.shape[:2]
    if not (0<=l<r<w and 0<=t<bottom<h):
        raise ValueError("Invalid plot ROI in difference mask")
    delta=np.max(np.abs(
        a[:,:,:3].astype(np.int16)-
        b[:,:,:3].astype(np.int16)),axis=2)
    inside=np.zeros((h,w),dtype=bool)
    inside[t:bottom+1,l:r+1]=True
    image=np.empty((h,w,4),dtype=np.uint8)
    image[:,:,:]=[255,255,255,255]
    mild=(delta==1)
    image[mild]=[224,224,224,255]
    big=(delta>1)
    image[big & inside]=[239,65,54,255]
    image[big & ~inside]=[255,170,51,255]
    return image


def compare_current_original_pixel_view(
    reference: OriginalSpectrumReference, spectrum: dict,
    *, source_bitmap: np.ndarray, canvas: dict, source_model: dict,
    view_x, view_y, qt_device_pixel_ratio: float,
    original_png_rgba: np.ndarray,
    operator_declared_same_window: bool,
    shift_radius: int = 3,
    textout_diagnostics: dict | None = None,
) -> tuple[dict, np.ndarray]:
    """Compare ORIGINAL operator PNG to the SAME bitmap Qt currently shows.

    Reject changed Power/Y, stale composite, wrong viewport or dimensions.
    Diagnostics distinguish the graph ROI from labels and margins; no
    absolute 1:1 original runtime claim is ever returned.
    """
    _signature(
        reference, spectrum, source_bitmap, canvas,
        source_model, view_x, view_y)
    if operator_declared_same_window is not True:
        raise ValueError(
            "Operator must explicitly confirm same source, N/Tag, window, "
            "canvas size, DPI, FRange and cursor-free original screenshot")
    manifest=make_source_pixel_manifest(
        source_bitmap,canvas,spectrum=spectrum,
        view_x=view_x,view_y=view_y,
        qt_device_pixel_ratio=qt_device_pixel_ratio,
        textout_diagnostics=textout_diagnostics)
    report=compare_local_graph_pixel_audit(
        original_png_rgba,source_bitmap,manifest,
        shift_radius=shift_radius,
        operator_declared_same_measurement_and_window=True)
    roi=report["source_pixel_rect_ltrb"]
    preview=visual_pixel_difference(
        original_png_rgba,source_bitmap,roi)
    result={
        "source": SOURCE,
        "original_power_sha256": reference.power_sha256,
        "original_full_y_sha256": reference.display_y_sha256,
        "currently_visible_full_y_sha256": manifest["spectrum_series_f32_sha256"],
        "current_source_rgba_sha256": manifest["candidate_rgba_sha256"],
        "fft_n": reference.n_fft,
        "spectrum_mode": reference.mode,
        "sample_rate_hz": reference.fs_hz,
        "f_range_single": reference.f_range,
        "spectrum_channel_not_authenticated_by_reference": True,
        "same_image_dimensions": True,
        "paintbox_size_wh": report["image_size_wh"],
        "source_pixel_rect_ltrb": report["source_pixel_rect_ltrb"],
        "exact_rgb_equal_without_alignment": report[
            "exact_rgb_equal_without_alignment"],
        "plot_pixels": report["source_pixel_rect"],
        "axes_text_and_margins": report["axes_text_and_margins"],
        "full_canvas": report["full_canvas"],
        "best_shift_candidate": report["best_shift_candidate"],
        "shift_search_is_diagnostic_only": True,
        "operator_same_window_declaration": True,
        "independent_original_capture_authentication": False,
        "original_gdi_canvas_dpi_parity_verified": False,
        "physical_calibration_verified": False,
        "original_device_connected": False,
        "private_original_png_or_bin_in_report": False,
    }
    return result,preview
