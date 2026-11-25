"""Export only the exact, freshly validated displayed LIVE spectrum triplet.

This is a local MVK Compatible result, not the original Win32 vendor
format, physical calibration certificate, or a mixed-session capture.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import math
from pathlib import Path

import numpy as np

from .original_live_view_gate import gate_live_preview
from .original_source_long_window import SourceLongWindow
from .spectrum_summary_export_candidate import spectrum_triplet_text

DISCLAIMER = "MVK Compatible LIVE · локальный GetSpectrum; не Delphi 1:1 и не приборный DSP"
FILENAME_PREFIX = "MVK-COMPATIBLE-LIVE-"
HEADER = ("СКЗ спектра (локальный)|Частота пика, Гц (локальная)|"
          "Амплитуда пика (локальная)")
SUMMARY_SOURCE = "APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE"


@dataclass(frozen=True)
class LiveSpectrumTriplet:
    session_id: str
    request_id: str
    adc: int
    mode: int
    n_fft: int
    rate_hz: int
    window_sha256: str
    capture_end: int
    epoch: tuple[int, int, int]
    values: tuple[float, float, float]

    def _numbers(self, separator):
        return spectrum_triplet_text(
            dict(source=SUMMARY_SOURCE, output_mean=self.values[0],
                 output_peak_frequency_hz=self.values[1],
                 output_peak_y=self.values[2]),
            separator=separator, decimal_separator=",")

    def clipboard_text(self):
        return DISCLAIMER + "\n" + self._numbers("\t")

    def save_new(self, path: str | Path):
        """Separate explicit local destination; no overwrite or vendor CSV append."""
        target = Path(path)
        if (not target.name.startswith(FILENAME_PREFIX) or
                target.suffix.lower() != ".csv" or
                target.is_symlink() or not target.parent.is_dir()):
            raise ValueError("Нужен отдельный файл MVK-COMPATIBLE-LIVE-*.csv")
        with target.open("x", encoding="utf-8", newline="") as stream:
            stream.write("sep=|\r\n" + DISCLAIMER + "\r\n" +
                         HEADER + "\r\n" + self._numbers("|") + "\r\n")


def current_live_spectrum_triplet(
        status, window, view, *, adc, mode, selected_n, code,
        stop_requested=False, frozen=False, now=None) -> LiveSpectrumTriplet:
    if (frozen or stop_requested or not isinstance(window, SourceLongWindow) or
            not isinstance(view, dict) or view.get("live_measurement_view") is not True or
            view.get("live_input_ring_verified") is not True):
        raise ValueError("Нет текущего проверенного окна LIVE-спектра")
    preview, req = window.preview, window.request
    if (preview.source_ring_provenance_verified is not True or
            not gate_live_preview(status, preview).allowed):
        raise ValueError("Окно LIVE больше не принадлежит текущему потоку")
    now = now or datetime.now(timezone.utc)
    if abs((now-preview.updated_utc).total_seconds())>8:
        raise ValueError("Окно LIVE устарело")
    ch = preview.channels.get(adc)
    if (ch is None or req.adc != adc or req.session_id != preview.session_id or
            req.capture_end != ch.captured_samples or req.samples != len(ch.samples) or
            req.sample_rate_hz != ch.rate_hz or req.source_epoch is None or
            req.source_epoch != ch.source_epoch or
            req.source_range_state != ch.source_range_state or
            req.h_tag != (-2 if code else -1) or req.envelope_code != code or
            selected_n != (req.original_bspec_lines if code else req.samples) or
            (view.get("live_session_id"),view.get("channel"),view.get("mode"),
             view.get("live_selected_bspec_lines"),view.get("live_envelope_code"),
             view.get("live_adc_rate_hz"),view.get("live_window_sha256"),
             view.get("live_source_request_id"),view.get("live_source_epoch")) !=
            (req.session_id,adc,mode,selected_n,code,ch.rate_hz,ch.sha256,
             req.request_id,req.source_epoch)):
        raise ValueError("АЦП, режим или окно изменились")
    if adc <= 8 and (ch.source_range_state or {}).get("origin") not in (
            "REGISTER_FLOAT32","REGISTER_ZERO_FALLBACK_ONE"):
        raise ValueError("Нет подтверждённого диапазона АЦП")
    if sha256(ch.samples.tobytes()).hexdigest() != ch.sha256:
        raise ValueError("SHA окна LIVE не совпал")

    n, summary, df = view.get("n_fft"), view.get("spectrum_summary"), view.get("df_hz")
    if (type(n) is not int or not 2 <= n <= 262144 or n & (n-1) or
            type(df) not in (int,float) or not math.isfinite(df) or df <= 0 or
            len(view["amplitude"]) != n//2 or len(view["frequency_hz"]) != n//2 or
            not isinstance(summary, dict) or summary.get("source") != SUMMARY_SOURCE or
            summary.get("spectrum_mode") != mode or summary.get("n_fft") != n):
        raise ValueError("Нет полного связанного результата GetSpectrum")
    # Original Copy/Save uses the selected channel's summary, not a
    # displayed cursor pixel; frequency is peak bin times that FFT's df.
    fields = ("output_mean", "output_peak_frequency_hz", "output_peak_y", "output_peak_x_bin")
    vals = tuple(summary.get(field) for field in fields)
    if any(type(v) not in (float,int) or not math.isfinite(v) for v in vals):
        raise ValueError("Некорректные итоговые значения FFT")
    mean, frequency, peak, index = vals
    if (not 0<=index<n//2 or not 0<=frequency<=df*(n//2) or
            not math.isclose(frequency,float(np.float32(
                np.float32(index)*np.float32(df))),rel_tol=1e-5,abs_tol=2e-5) or
            (mode!=0 and (mean<0 or peak<0))):
        raise ValueError("Итоговые значения не соответствуют текущей FFT")
    epoch=req.source_epoch
    return LiveSpectrumTriplet(req.session_id,req.request_id,adc,mode,n,ch.rate_hz,
        ch.sha256,req.capture_end,tuple(epoch[x] for x in (
            "socket_attempt","continuity_generation","start_pos_64")),
        (float(mean),float(frequency),float(peak)))
