"""Stage111Z31AZ: local, non-attesting same-canvas TQGrapher pixel audit.

User-supplied ORIGINAL screenshot crops may be compared to an explicit
candidate source bitmap saved from the offline Desktop. This core component
never touches original processes, GDI handles, private files or network.
Only simple synthetic tests are checked into GitHub; real screenshots,
BIN/IDP/DFM/PAS and comparison reports remain on the operator's PC.

A numerical/pixel match MUST NOT be called proven original parity without
independent original capture provenance, identical window/DPI, and review.
"""
from __future__ import annotations

from hashlib import sha256
import math
import numbers

import numpy as np

from .spectrum_bitmap_diff import compare_spectrum_bitmap_crops
from .tqgrapher_canvas_idr_candidate import SOURCE as CANVAS_SOURCE

SOURCE = "SOURCE_DERIVED_LOCAL_SPECTRUM_PIXEL_AUDIT_STAGE111Z31AZ"
FORMAT_VERSION = 1
MAX_PIXELS = 6_000_000


def _rgba(image, name: str) -> np.ndarray:
    if (not isinstance(image, np.ndarray)
            or image.dtype != np.uint8
            or image.ndim != 3
            or image.shape[2] != 4
            or min(image.shape[:2]) < 64
            or image.shape[0] * image.shape[1] > MAX_PIXELS
            or not bool(np.all(image[:, :, 3] == 255))):
        raise ValueError(name + " must be a bounded, opaque RGBA ndarray")
    return image


def _finite(v, name: str) -> float:
    if isinstance(v, bool) or not isinstance(v, numbers.Real):
        raise ValueError(name + " must be a real number")
    f = float(v)
    if not math.isfinite(f):
        raise ValueError(name + " must be finite")
    return f


def _range(vals, name: str) -> list[float]:
    if not isinstance(vals, (list, tuple)) or len(vals) != 2:
        raise ValueError(name + " must have two bounds")
    a, b = (_finite(x, name) for x in vals)
    if not a < b:
        raise ValueError(name + " bounds must be increasing")
    return [a, b]


def _canvas_rect(canvas, width: int, height: int) -> list[int]:
    if not isinstance(canvas, dict) or canvas.get("source") != CANVAS_SOURCE:
        raise ValueError("Source-derived TQGrapher canvas required")
    if (type(canvas.get("canvas_width")) is not int
            or type(canvas.get("canvas_height")) is not int
            or (canvas["canvas_width"], canvas["canvas_height"]) !=
            (width, height)):
        raise ValueError("Bitmap and source PaintBox dimensions differ")
    rect = [canvas.get(k) for k in
            ("pixel_left", "pixel_top", "pixel_right", "pixel_bottom")]
    if (any(type(n) is not int for n in rect)
            or not 0 <= rect[0] < rect[2] < width
            or not 0 <= rect[1] < rect[3] < height
            or rect[2] - rect[0] < 64 or rect[3] - rect[1] < 64):
        raise ValueError("Invalid/inadequate source PixelRect")
    return rect


def _frame_sha(image) -> str:
    return sha256(np.ascontiguousarray(image).tobytes()).hexdigest()


def make_source_pixel_manifest(
        bitmap, canvas, *, spectrum: dict, view_x, view_y,
        qt_device_pixel_ratio: float,
        textout_diagnostics: dict | None = None) -> dict:
    """Whitelisted export with NO source filename, paths or raw FFT arrays."""
    frame = _rgba(bitmap, "source bitmap")
    height, width = frame.shape[:2]
    rect = _canvas_rect(canvas, width, height)
    if not isinstance(spectrum, dict):
        raise ValueError("Full-resolution offline spectrum dict required")
    mode = spectrum.get("mode")
    if type(mode) is not int or mode not in (0, 1, 2, 3):
        raise ValueError("Original Tag0..3 display mode required")
    amplitude = np.asarray(spectrum.get("amplitude"), dtype=np.float32)
    if (amplitude.ndim != 1 or not 2 <= len(amplitude) <= 2_100_000
            or not bool(np.isfinite(amplitude).all())):
        raise ValueError("Finite full TQGrapher series required")
    nfft = spectrum.get("n_fft")
    if type(nfft) is not int or nfft < 2 or nfft > 4_194_304:
        raise ValueError("Bounded native FFT size required")
    df = _finite(spectrum.get("df_hz"), "df_hz")
    if df <= 0:
        raise ValueError("Positive source FFT spacing required")
    dpr = _finite(qt_device_pixel_ratio, "qt_device_pixel_ratio")
    if not 0.25 <= dpr <= 8:
        raise ValueError("Unsupported observed Qt DPR")
    x, y = _range(view_x, "view_x"), _range(view_y, "view_y")
    if textout_diagnostics is not None and not isinstance(
            textout_diagnostics, dict):
        raise ValueError("GDI text diagnostics must be a dict or null")

    # Explicit whitelist: NEVER serialize the original manifest, operator
    # paths, private BIN bytes, arbitrary diagnostics or original screenshots.
    diag = {}
    if textout_diagnostics:
        for key in ("requested_font_face", "requested_font_height",
                    "gdi_width_zero", "gdi_width_sixdecimals",
                    "gdi_height_zero"):
            val = textout_diagnostics.get(key)
            if (key == "requested_font_face" and
                    type(val) is str and 0 < len(val) <= 32):
                diag[key] = val
            elif key != "requested_font_face" and type(val) is int:
                diag[key] = val

    return {
        "format": "mvkview_spectrum_local_pixel_audit",
        "version": FORMAT_VERSION,
        "source": SOURCE,
        "candidate_source_only": True,
        "source_canvas_provenance": canvas["source"],
        "paintbox_size_logical_wh": [width, height],
        "source_pixel_rect_ltrb": rect,
        "source_margin_logical": int(canvas["margin"]),
        "source_x_view_hz": x,
        "source_y_view": y,
        "spectrum_tag": mode,
        "spectrum_fft_n": nfft,
        "spectrum_display_bin_count": int(len(amplitude)),
        "spectrum_df_hz": df,
        "spectrum_series_f32_sha256": sha256(
            np.asarray(amplitude, dtype="<f4").tobytes()).hexdigest(),
        "candidate_rgba_sha256": _frame_sha(frame),
        "qt_device_pixel_ratio_observed": dpr,
        "dfm_font_face_and_height_only_design_time": ["Tahoma", -13],
        "font_metrics_candidate": diag,
        "source_image_includes_original_verified_runtime_gdi": False,
        "original_runtime_font_and_dpi_verified": False,
        "original_capture_provenance_independently_authenticated": False,
        "real_original_pixel_parity_verified": False,
        "raw_original_data_or_paths_in_report": False,
    }


def _roi_score(original, candidate, mask) -> dict:
    diff = np.abs(
        original[:, :, :3].astype(np.int16) -
        candidate[:, :, :3].astype(np.int16))
    considered = int(np.count_nonzero(mask))
    if considered < 1:
        raise ValueError("No pixels inside image region")
    selected = diff[mask]
    nonwhite = np.any(original[:, :, :3] != 255, axis=2) | np.any(
        candidate[:, :, :3] != 255, axis=2)
    return {
        "pixels_compared": considered,
        "informative_ink_pixels": int(np.count_nonzero(nonwhite & mask)),
        "exact_rgb_pixels": int(np.count_nonzero(np.all(selected == 0, axis=1))),
        "pixels_any_rgb_channel_gt_1": int(np.count_nonzero(
            np.any(selected > 1, axis=1))),
        "mean_abs_rgb_channel_error": float(selected.mean()),
        "maximum_abs_rgb_channel_error": int(selected.max()),
    }


def compare_local_graph_pixel_audit(
        original_rgba, candidate_rgba, manifest: dict, *,
        shift_radius: int = 0,
        operator_declared_same_measurement_and_window: bool = False) -> dict:
    """Strict, non-resizing same-size comparison with explicit source ROI.

    Reports difference statistics ONLY. A zero-difference candidate is not
    independent authentication of the original process, physical DPI or
    original-source measurement identity. A ±5 px search is diagnostic only.
    """
    original = _rgba(original_rgba, "original screenshot crop")
    candidate = _rgba(candidate_rgba, "candidate screenshot crop")
    if original.shape != candidate.shape:
        raise ValueError("Screenshots must be exactly same-sized; NEVER auto-resize")
    if (not isinstance(manifest, dict)
            or manifest.get("format") != "mvkview_spectrum_local_pixel_audit"
            or manifest.get("version") != FORMAT_VERSION
            or manifest.get("source") != SOURCE):
        raise ValueError("Unrecognized local source-pixel audit manifest")
    h, w = original.shape[:2]
    if manifest.get("paintbox_size_logical_wh") != [w, h]:
        raise ValueError("Candidate image differs from manifest PaintBox size")
    if _frame_sha(candidate) != manifest.get("candidate_rgba_sha256"):
        raise ValueError("Candidate PNG differs from original exported pixels")
    if (type(operator_declared_same_measurement_and_window) is not bool
            or type(shift_radius) is not int
            or not 0 <= shift_radius <= 5):
        raise ValueError("Invalid explicit same-window declaration or shift radius")
    rect = manifest.get("source_pixel_rect_ltrb")
    if (not isinstance(rect, list) or len(rect) != 4
            or any(type(n) is not int for n in rect)):
        raise ValueError("Invalid saved source PixelRect")
    l, t, r, b = rect
    if not 0 <= l < r < w or not 0 <= t < b < h:
        raise ValueError("Saved source PixelRect outside bitmap")
    plot = np.zeros((h, w), dtype=np.bool_)
    plot[t:b + 1, l:r + 1] = True
    whole = np.ones((h, w), dtype=np.bool_)
    whole_stats = _roi_score(original, candidate, whole)
    if whole_stats["informative_ink_pixels"] < 1:
        raise ValueError("Blank white images are not useful pixel evidence")
    plot_stats = _roi_score(original, candidate, plot)
    axis_stats = _roi_score(original, candidate, ~plot)
    shift = compare_spectrum_bitmap_crops(
        original, candidate, shift_radius=shift_radius)
    exact = whole_stats["exact_rgb_pixels"] == w * h
    return {
        "source": SOURCE,
        "image_size_wh": [w, h],
        "spectrum_tag": manifest.get("spectrum_tag"),
        "source_pixel_rect_ltrb": rect.copy(),
        "operator_declared_same_measurement_and_window":
            operator_declared_same_measurement_and_window,
        "independent_capture_authentication": False,
        "exact_rgb_equal_without_alignment": bool(exact),
        "full_canvas": whole_stats,
        "source_pixel_rect": plot_stats,
        "axes_text_and_margins": axis_stats,
        "best_shift_candidate": shift["best_match"],
        "shift_search_is_diagnostic_not_acceptance": True,
        "original_runtime_tcanvas_font_dpi_proven": False,
        "complete_mvkview_pixel_parity_verified": False,
        "raw_image_bytes_paths_or_original_data_exported": False,
    }
