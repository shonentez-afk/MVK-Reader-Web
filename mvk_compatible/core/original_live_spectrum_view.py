"""Bind LIVE PageSpectrum to a single full FFT, with separate drawing LOD.

Original _Unit128:00848148/0084819A (PageSpectrum and bSpecLines),
0084C3AC (X scale), 0084C5AC (Y scale), 0084C918 (mouse -> TQGrapher).
Only local candidate values; no commands, calibration or Win32 attestation.
"""
from __future__ import annotations
import math
import numpy as np

from .native_r6_live_preview import LivePreview
from .tqgrapher_display_idr_candidate import spectrum_display_contract
from .mvk_original_scale_tables_idr_candidate import source_spectrum_y_unit
from .original_live_adc_metadata import source_derived_units, METADATA_DOMAIN


def bind_live_spectrum_view(preview: LivePreview, adc: int, result: dict,
                            *, selected_n: int, code: int, mode: int) -> dict:
    """Attach one ADC/window identity to all contiguous N/2 FFT bins."""
    if not isinstance(preview, LivePreview) or not isinstance(result, dict):
        raise ValueError("Live PageSpectrum needs one verified input/result")
    channel = preview.channels.get(adc)
    n = result.get("n_fft")
    if (channel is None or type(n) is not int or type(selected_n) is not int
            or type(code) is not int or not 0 <= code <= 31
            or type(mode) is not int or mode not in range(4)
            or result.get("mode") != mode or result.get("channel") != adc):
        raise ValueError("Live PageSpectrum ADC/mode/N mismatch")
    if code:
        plan = result.get("original_source_fft_plan") or {}
        if (not preview.source_ring_provenance_verified
                or result.get("source") !=
                "SOURCE_SELECTED_GETSPECTRUM_FIR_IQ_IDR_CANDIDATE"
                or result.get("source_ring_sha256") != channel.sha256
                or plan.get("envelope_code") != code
                or plan.get("original_bSpecLines_pre_fir_n") != selected_n
                or plan.get("post_fir_fft_n") != n
                or plan.get("input_rate_hz") != channel.rate_hz
                or plan.get("source_getadjusted_length_samples") !=
                len(channel.samples)):
            raise ValueError("Live PageSpectrum FIR source/window mismatch")
        output_fs = plan["post_fir_sample_rate_hz"]
    else:
        evidence = result.get("input_source_window") or {}
        if (result.get("source") !=
                "LIVE_NATIVE_R6_FFT_IDR_CANDIDATE_UNVERIFIED"
                or n != selected_n
                or result.get("source_selected_fft_n") != selected_n
                or evidence.get("preview_source_calibrated_sha256") !=
                channel.sha256):
            raise ValueError("Live PageSpectrum source/window mismatch")
        output_fs = channel.rate_hz
    meta=channel.source_metadata
    if preview.input_domain==METADATA_DOMAIN:
        if meta is None or result.get("source_adc_metadata")!=meta.wire() or result.get("f_range_used",result.get("f_range"))!=meta.factor:
            raise ValueError("Live PageSpectrum metadata/factor differs from current ring")
    display = spectrum_display_contract(n, output_fs)
    x = np.asarray(result["frequency_hz"], dtype=np.float64)
    y = np.asarray(result["amplitude"], dtype=np.float64)
    df = float(result["df_hz"])
    if (x.ndim != 1 or y.ndim != 1 or len(x) != n//2 or len(y) != n//2
            or not np.isfinite(x).all() or not np.isfinite(y).all()
            or not math.isclose(df, output_fs/n, rel_tol=1e-6)
            or not np.allclose(x, np.arange(n//2)*df, atol=1e-7, rtol=1e-7)):
        raise ValueError("Live PageSpectrum requires complete contiguous N/2")
    if not isinstance(result.get("spectrum_summary"), dict):
        raise ValueError("Live PageSpectrum summary missing")
    x = x.copy()
    y = y.copy()
    x.setflags(write=False)
    y.setflags(write=False)
    return {**result,
            "frequency_hz": x, "amplitude": y,
            "unit": source_derived_units(meta,mode) if meta is not None else source_spectrum_y_unit(mode),
            "grapher_series_bins": display["grapher_series_bins"],
            "live_display_contract": display,
            "live_measurement_view": True,
            "live_session_id": preview.session_id,
            "live_window_sha256": channel.sha256,
            "live_adc_rate_hz": channel.rate_hz,
            "live_selected_bspec_lines": selected_n,
            "live_envelope_code": code,
            "live_input_ring_verified": preview.source_ring_provenance_verified,
            "provisional_not_audited": True,
            "original_delphi_numerical_parity_verified": False}


def live_spectrum_plot_points(view: dict, *, x_bounds=None,
                              max_points: int = 5000):
    """Bound curve to visible X, retaining min/max; reveal real bins on zoom."""
    if (view.get("live_measurement_view") is not True
            or type(max_points) is not int or max_points < 4):
        raise ValueError("Live spectrum view/point limit required")
    count = view["grapher_series_bins"]
    x = view["frequency_hz"][:count]
    y = view["amplitude"][:count]
    if x_bounds is None:
        first, end = 0, count
    else:
        lo, hi = map(float, x_bounds)
        if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
            raise ValueError("Invalid live spectrum viewport")
        first = max(0, int(np.searchsorted(x, lo, side="left"))-1)
        end = min(count, int(np.searchsorted(x, hi, side="right"))+1)
    if end-first <= max_points:
        return x[first:end], y[first:end]
    step = math.ceil((end-first)/(max_points//2))
    picked = []
    for start in range(first, end, step):
        part = y[start:min(end, start+step)]
        a = start+int(np.argmin(part))
        b = start+int(np.argmax(part))
        picked.extend((a,b) if a<b else (b,a) if a>b else (a,))
    return x[picked], y[picked]
