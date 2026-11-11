"""Stage111Z31BK: original pnView/tbViewTime and linked signal/spectrum readouts.

Source:
  Projects/mvkform.dfm: pnView Visible=False, height 48, lbViewTime 104x25,
  tbViewTime (Max=120, PageSize=60, Frequency=60, TicksTopLeft).
  _Unit128.pas:008465FE..00846793 (duration-dependent Tag 0..3),
  0084EAD4, 0084F806..0084F8EF (track position -> source time),
  00847248..008472BB (refresh dispatch for PageAdc/PageSpectrum/Status).
Only source-derived mapping, no device, no I/O, no speculative conversion
of a standalone BIN to physical acceleration or instrument VALUES/AUX.

The independent Core owns time geometry and display readouts; Qt must not
recalculate the same wave RMS or FFT peak from a rendered/downsampled curve.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .offline_measurement_flow import OfflineMeasurementFlow

SOURCE = "IDR_PNVIEW_LINKED_TRACE_STAGE111Z31BK"
_VIEW_STEPS = (0.01, 0.1, 1.0, 10.0)
_PAGE_STEPS = (100, 10, 60, 360)


def _finite(name: str, value, *, positive=False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numerical")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0):
        raise ValueError(f"{name} is not finite/positive")
    return result


@dataclass(frozen=True)
class SourceViewTime:
    """Derived source TTrackBar Tag/range for one checked Single signal."""
    adc: int
    bin_sha256: str
    sample_count: int
    sample_rate_hz: float
    source_tag: int
    minimum: int
    maximum: int
    page_step: int
    frequency: int
    seconds_per_position: float
    position: int
    selected_start_sample: int
    selected_start_seconds: float
    source_runtime_parity_verified: bool = False
    write_to_instrument_allowed: bool = False

    @property
    def label(self) -> str:
        # Delphi hh:nn:ss.zzz from a TDateTime time-of-day; wraps after 24 h.
        milliseconds = int(round(self.selected_start_seconds * 1000))
        hours = (milliseconds // 3_600_000) % 24
        minutes = (milliseconds // 60_000) % 60
        seconds = (milliseconds // 1_000) % 60
        msec = milliseconds % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{msec:03d}"

    def summary(self) -> dict:
        return {
            "source": SOURCE,
            "original_control": "tbViewTime",
            "tag": self.source_tag, "minimum": self.minimum,
            "maximum": self.maximum, "page_step": self.page_step,
            "position": self.position,
            "start_sample": self.selected_start_sample,
            "start_s": self.selected_start_seconds,
            "source_bin_sha256": self.bin_sha256,
            "original_runtime_parity_verified": False,
            "instrument_write_enabled": False,
        }


def source_view_time(
    flow: OfflineMeasurementFlow, *, position: int | None = None,
    requested_start_s: float | None = None,
) -> SourceViewTime:
    """Original 4-level file time scale over the CURRENT verified ADC.

    A source track position maps to a real sample index without zero-fill.
    The default is position zero; caller may pass a previous REAL start time.
    This model never changes the existing sample or spectrum data.
    """
    if not isinstance(flow, OfflineMeasurementFlow):
        raise ValueError("Checked offline flow required")
    evidence = flow.source_record()
    n = evidence["sample_count"]
    fs = _finite("fs", evidence["sample_rate_hz"], positive=True)
    seconds = n / fs
    if seconds < 60:
        tag, step, divisor = 0, .01, 100
        maximum = int(n * divisor // fs)
        minimum = 0
    elif seconds < 600:
        tag, step, divisor = 1, .1, 10
        maximum = int(n * divisor // fs)
        minimum = 0
    elif seconds < 6000:
        tag, step, divisor = 2, 1., 1
        maximum = int(n // fs)
        minimum = 0
    else:
        tag, step, divisor = 3, 10., .1
        maximum = int(n // (10 * fs))
        minimum = 1
    if not minimum <= maximum <= 2_000_000_000:
        raise ValueError("Original Win32 TTrackBar range unsupported")
    if position is not None and requested_start_s is not None:
        raise ValueError("Specify position OR requested time, not both")
    if position is not None:
        if type(position) is not int or not minimum <= position <= maximum:
            raise ValueError("ViewTime position outside source range")
        p = position
    elif requested_start_s is not None:
        start = _finite("start_s", requested_start_s)
        p = max(minimum, min(maximum, int(round(start / step))))
    else:
        p = minimum
    # _Unit128:0084F81B..0084F8B6 first maps Tag+position to a 64-bit
    # REAL source sample offset using the original sampling frequency.
    index = min(n - 1, max(0, int(round(p * step * fs))))
    actual_seconds = index / fs
    return SourceViewTime(
        adc=flow.channel, bin_sha256=evidence["source_bin_sha256"],
        sample_count=n, sample_rate_hz=fs,
        source_tag=tag, minimum=minimum, maximum=maximum,
        page_step=_PAGE_STEPS[tag], frequency=_PAGE_STEPS[tag],
        seconds_per_position=step, position=p,
        selected_start_sample=index, selected_start_seconds=actual_seconds,
    )


def source_wave_readout(flow: OfflineMeasurementFlow, trace: dict,
                        time: SourceViewTime) -> dict:
    """Visible original PageAdc readout from the SAME computed GetSignal."""
    if not isinstance(trace, dict) or not isinstance(time, SourceViewTime):
        raise ValueError("An actual computed waveform and source time required")
    record = flow.source_record()
    if (record["source_bin_sha256"] != time.bin_sha256
            or record["selected_channel"] != time.adc
            or record["sample_count"] != time.sample_count):
        raise ValueError("Wave/time source provenance mismatch")
    for key in ("window_samples", "rms_m_s2", "removed_mean_m_s2"):
        if key not in trace:
            raise ValueError("Missing computed GetSignal field")
    samples = trace["window_samples"]
    if type(samples) is not int or samples <= 0 or samples > time.sample_count:
        raise ValueError("Incorrect source waveform sample count")
    rms = _finite("wave rms", trace["rms_m_s2"])
    removed_dc = _finite("wave dc", trace["removed_mean_m_s2"])
    if rms < 0:
        raise ValueError("Wave RMS cannot be negative")
    return {
        "source": SOURCE, "adc": time.adc, "source_bin_sha256": time.bin_sha256,
        "source_start_s": time.selected_start_seconds,
        "source_start_sample": time.selected_start_sample,
        "signal_samples": samples, "rms_from_core": rms,
        "removed_dc_from_core": removed_dc,
        "unit": "усл. ед. BIN" if flow.direct_bin else "расч. ед.",
        "original_runtime_parity_verified": False,
        "physical_calibration_verified": False,
    }


def source_spectrum_readout(flow: OfflineMeasurementFlow, spectrum: dict,
                            n_fft: int, *, archive_end: bool,
                            view_time: SourceViewTime) -> dict:
    """Visible PageSpectrum readout from the SAME computed FFT and summary."""
    if not isinstance(spectrum, dict) or not isinstance(view_time, SourceViewTime):
        raise ValueError("Computed spectrum and checked ViewTime required")
    if type(n_fft) is not int or n_fft < 2 or n_fft % 2:
        raise ValueError("Invalid source NFFT")
    record = flow.source_record()
    if (record["selected_channel"] != view_time.adc or
            record["source_bin_sha256"] != view_time.bin_sha256):
        raise ValueError("Spectrum/time source provenance mismatch")
    bins = spectrum.get("amplitude")
    frequencies = spectrum.get("frequency_hz")
    if bins is None or frequencies is None or (
            len(bins) != n_fft // 2 or len(frequencies) != n_fft // 2):
        raise ValueError("Spectrum must retain all N/2 original candidate bins")
    df = _finite("df_hz", spectrum.get("df_hz"), positive=True)
    summary = spectrum.get("spectrum_summary")
    if not isinstance(summary, dict) or (
            summary.get("source") !=
            "APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE"):
        raise ValueError("No source-derived numerical FFT summary")
    rms = _finite("fft output mean", summary.get("output_mean"))
    peak_f = _finite("fft peak hz", summary.get("output_peak_frequency_hz"))
    peak_y = _finite("fft peak y", summary.get("output_peak_y"))
    if peak_f < 0 or peak_f > (n_fft // 2) * df:
        raise ValueError("FFT peak outside source frequency bins")
    return {
        "source": SOURCE, "adc": view_time.adc,
        "source_bin_sha256": view_time.bin_sha256,
        "n_fft": n_fft, "df_hz": df, "fft_bins": len(bins),
        "spectrum_rms_from_core": rms,
        "peak_frequency_hz_from_core": peak_f,
        "peak_y_from_core": peak_y,
        "archive_end_selected": bool(archive_end),
        "view_time_start_s": view_time.selected_start_seconds,
        "unit": "усл. ед. BIN" if flow.direct_bin else "расч. ед.",
        "physical_calibration_verified": False,
        "original_runtime_parity_verified": False,
    }


def source_linked_caption(flow: OfflineMeasurementFlow,
                          view_time: SourceViewTime, *,
                          verified_status: dict | None = None) -> str:
    """Compact, source-backed context shown on all three WORKING pages."""
    record = flow.source_record()
    if (record["source_bin_sha256"] != view_time.bin_sha256
            or record["selected_channel"] != view_time.adc):
        raise ValueError("Cannot show a mixed ADC/file caption")
    if verified_status is not None:
        if (flow.direct_bin or verified_status.get("source") != "MVK_DSP" or
                verified_status.get("serial") != flow.session.serial or
                verified_status.get("tick") != flow.tick_index):
            raise ValueError("Stale VALUES/AUX source cannot be displayed")
        status = f"VALUES {flow.tick_index+1}/{flow.session.updates}"
    else:
        status = "VALUES/AUX НЕТ" if flow.direct_bin else "VALUES не проверены"
    return (f"АЦП{flow.channel} · {record['data_file_label']} · "
            f"{view_time.label} · {status} · "
            f"SHA {view_time.bin_sha256[:12]}…")
