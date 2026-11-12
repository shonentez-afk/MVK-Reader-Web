"""Stage111Z31BM: same-window original Power/Y vs CURRENT PageSpectrum Y.

A UI-independent, read-only computational contract. Reuses the local SHA-
verified original Win32 capture and independent RAW-window comparator. A
capture manifest is operator-attested, not independently authenticated.
No instrument, network, calibration, file writes or private signal outputs.
"""
from __future__ import annotations

import hashlib
import math
import numbers
from pathlib import Path
import numpy as np

from .offline_measurement_flow import OfflineMeasurementFlow
from .original_spectrum_x32dbg_reference import load_original_spectrum_reference
from ..private_same_window_spectrum_compare import (
    _evidence, compare_original_same_window_spectrum,
)
from ..private_getspectrum_prefft_envelope_compare import _ordered_f32_words

SCHEMA = "MVKVIEW_VISIBLE_ORIGINAL_SAME_WINDOW_PAIR_V1"
SOURCE = "LOCAL_VISIBLE_FULL_Y_ORIGINAL_SAME_WINDOW_PAIR_STAGE111Z31BM"
_PLAIN = "APP_DERIVED_FFT_MVKVIEW_CANDIDATE"
_DIRECT_PLAIN = "APP_DERIVED_DIRECT_BIN_FFT_CANDIDATE"
_FIR = "APP_DERIVED_ENVELOPE_SPECTRUM_IDR_CANDIDATE"


def _f32_word(value):
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError("Current spectrum has no numeric Single FRange")
    if not math.isfinite(float(value)) or float(value) <= 0:
        raise ValueError("Current FRange must be finite and positive")
    single = np.asarray([value], dtype="<f4")
    if not bool(np.isfinite(single).all()) or single[0] <= 0:
        raise ValueError("Current FRange is not a positive finite Single")
    return int(single.view("<u4")[0])


def compare_visible_original_spectrum_pair(
    flow: OfflineMeasurementFlow,
    visible: dict,
    reference_manifest: str | Path,
    window_evidence: str | Path,
    *, envelope_code: int = 0,
    original_idp: str | Path | None = None,
) -> dict:
    """Check actual screen N/2 bins PLUS independent model against original Y.

    Do not trust the file name, chosen ADC, plot pixels, manual FRange or a
    screenshot alone. Reject all changes in window SHA, ADC, N, Tag, FRange
    Single word, FFT input domain, frequency grid or source backend. Viewport
    X/Y changes alone do not alter full Float32 samples or numeric proof.
    """
    if type(flow) is not OfflineMeasurementFlow or type(visible) is not dict:
        raise ValueError("One checked offline flow and visible spectrum required")
    if type(envelope_code) is not int or not 0 <= envelope_code <= 31:
        raise ValueError("EnvelopeCode must be integer 0..31")
    record = flow.source_record()  # revalidates ZIP/BIN/TSXML before pairing
    claim = _evidence(window_evidence)
    ref = load_original_spectrum_reference(reference_manifest)
    n, mode = visible.get("n_fft"), visible.get("mode")
    if (type(n) is not int or not 1024 <= n <= 262144
            or n & (n - 1) or type(mode) is not int or mode not in range(4)):
        raise ValueError("Invalid visible FFT N or mode")
    if (visible.get("channel") != flow.channel
            or claim["channel"] != flow.channel
            or claim["fft_n"] != n or ref.n_fft != n
            or claim["spectrum_mode"] != mode or ref.mode != mode
            or claim["envelope_code"] != envelope_code):
        raise ValueError("Visible and original ADC/N/Tag/EnvelopeCode differ")
    expected_sources = (_FIR,) if envelope_code else (_PLAIN, _DIRECT_PLAIN)
    if visible.get("source") not in expected_sources:
        raise ValueError("Visible Y is not selected original-path FFT")
    if visible.get("fft_backend") != "idr_float32":
        raise ValueError("Source-IDR Float32 FFT backend required for pairing")
    if visible.get("input_domain") != claim["input_domain"]:
        raise ValueError("Current spectrum and original storage domains differ")
    if _f32_word(visible.get("f_range_used")) != _f32_word(ref.f_range):
        raise ValueError("Visible Single FRange differs from x32dbg original")
    if bool(envelope_code) != bool(original_idp):
        raise ValueError("FIR needs local original IDP; plain FFT must not")
    win = visible.get("input_source_window")
    if not isinstance(win, dict):
        raise ValueError("Visible spectrum has no checked source window")
    for key, expected in (
        ("channel", flow.channel),
        ("first_archive_sample_index", claim["first_archive_sample_index"]),
        ("last_archive_sample_exclusive", claim["last_archive_sample_exclusive"]),
        ("source_float32_le_sha256", claim["original_raw_window_float32_sha256"]),
    ):
        if win.get(key) != expected:
            raise ValueError("Visible screen uses another RAW interval: " + key)
    if record["sample_rate_hz"] != claim["raw_sample_rate_hz"]:
        raise ValueError("Recorded ADC Fs differs from the original claim")
    df = float(visible.get("df_hz", float("nan")))
    if not math.isfinite(df) or df <= 0 or not math.isclose(
            df * n, ref.fs_hz, rel_tol=0, abs_tol=1e-6):
        raise ValueError("Original and visible output FFT Fs differ")
    ys = np.asarray(visible.get("amplitude"), dtype="<f4")
    xs = np.asarray(visible.get("frequency_hz"), dtype=np.float64)
    if (ys.ndim != 1 or xs.ndim != 1 or len(ys) != n // 2
            or len(xs) != n // 2 or not bool(np.isfinite(ys).all())
            or not bool(np.isfinite(xs).all())):
        raise ValueError("Current Y must retain all finite N/2 Float32 bins")
    if not bool(np.allclose(
            xs, np.arange(n // 2) * df, rtol=1e-10, atol=1e-7)):
        raise ValueError("Current screen frequency grid is not the full FFT")

    # No second file picker for the source archive: only THIS checked session.
    pair = compare_original_same_window_spectrum(
        flow.session.path, reference_manifest, window_evidence,
        original_idp=original_idp,
    )
    if (pair["channel"] != flow.channel
            or pair["source_window_float32_sha256"] !=
               win["source_float32_le_sha256"]):
        raise ValueError("Recomputed model no longer matches current screen")
    current_words = ys.view("<u4")
    original_words = np.asarray(ref.display_y, dtype="<f4").view("<u4")
    matching = current_words == original_words
    different = np.flatnonzero(~matching)
    ulp = np.abs(
        _ordered_f32_words(current_words) -
        _ordered_f32_words(original_words),
    )
    current_matches_model = (
        hashlib.sha256(ys.tobytes()).hexdigest() == pair["candidate_full_y_sha256"]
    )
    current_exact = bool(np.all(matching))
    return {
        "schema": SCHEMA, "source": SOURCE,
        "channel": flow.channel, "fft_n": n,
        "spectrum_mode": mode, "envelope_code": envelope_code,
        "input_domain": claim["input_domain"],
        "source_window_sha256": pair["source_window_float32_sha256"],
        "source_bin_sha256": record["source_bin_sha256"],
        "original_full_y_sha256": pair["original_full_y_sha256"],
        "original_f_range_float32_hex": f"{_f32_word(ref.f_range):08X}",
        "full_y_bins": n // 2,
        "recomputed_y_matching_bins": pair["full_y_bitwise_equal_bins"],
        "recomputed_y_exact": pair["full_y_all_bitwise_equal"],
        "visible_y_matching_bins": int(np.count_nonzero(matching)),
        "visible_y_exact": current_exact,
        "visible_y_matches_recomputed_candidate": current_matches_model,
        "first_visible_differing_bin": (
            None if not len(different) else int(different[0])),
        "maximum_visible_float32_ulp_difference": int(np.max(ulp)),
        "paired_numeric_pass": bool(
            pair["full_y_all_bitwise_equal"] and current_exact
            and current_matches_model),
        "operator_window_assertion_independently_authenticated": False,
        "original_win32_runtime_and_pixel_parity_verified": False,
        "hardware_calibration_or_device_commands_used": False,
        "private_paths_or_signal_arrays_in_report": False,
    }
