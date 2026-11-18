"""Plot geometry and real *local* filter response for MVK Live.

These helpers never touch a device or the Native packet receiver. Every
frequency is a physical frequency in Hz. In log-X mode pyqtgraph displays
log10-transformed X coordinates; a DC bin must not enter that view.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy import signal


@dataclass(frozen=True)
class AxisLimits:
    """View-box X limits, alongside actual physical Hz limits."""
    left: float
    right: float
    physical_min_hz: float
    physical_max_hz: float


def spectrum_x_limits(fs: int, nfft: int, maximum_hz: float,
                      log_x: bool = False) -> AxisLimits:
    if not isinstance(fs, int) or fs <= 0:
        raise ValueError("Fs must be a verified positive integer")
    if not isinstance(nfft, int) or nfft <= 0:
        raise ValueError("NFFT must be a positive integer")
    if not math.isfinite(maximum_hz) or maximum_hz <= 0:
        raise ValueError("Invalid frequency limit")
    nyquist = fs / 2.0
    high = min(float(maximum_hz), nyquist)
    if not log_x:
        return AxisLimits(0.0, high, 0.0, high)
    first_bin = fs / nfft
    if high <= first_bin:
        raise ValueError("Logarithmic X needs more than one positive frequency bin")
    # The curve's X array remains in physical Hz; pyqtgraph handles the
    # log10 conversion for the PlotDataItem, while the ViewBox is log10 Hz.
    return AxisLimits(math.log10(first_bin), math.log10(high),
                      first_bin, high)


def filter_magnitude_response(
    fs: int,
    *,
    band_hz: tuple[float, float | None] = (0.0, None),
    notch_hz: float | None = None,
    order: int = 4,
    samples: int = 512,
) -> tuple[np.ndarray, np.ndarray]:
    """Real amplitude response of a two-pass *local* Butterworth/notch filter.

    SciPy's sosfiltfilt/filtfilt produce a zero-phase two-pass magnitude
    |H|**2, not the single-pass magnitude shown by ordinary IIR designs.

    The no-filter selection returns 0 dB, including DC for the preview.
    This does NOT describe the instrument's undocumented original FIR,
    the sensor's calibration, FRange, or an FFT-only display crop.
    """
    if not isinstance(fs, int) or fs <= 1 or samples < 32:
        raise ValueError("Unknown sampling rate / too few preview samples")
    low, high = band_hz
    nyquist = fs / 2.0
    if (not math.isfinite(low) or low < 0 or low >= nyquist or
            (high is not None and (not math.isfinite(high) or
                                   high <= low or high >= nyquist))):
        if low == 0 and high is None:
            pass
        else:
            raise ValueError("Filter cutoff must be inside verified Nyquist")
    if notch_hz is not None and (
            not math.isfinite(notch_hz) or not 0 < notch_hz < nyquist):
        raise ValueError("Notch is outside Nyquist")
    if notch_hz is not None and (low != 0 or high is not None):
        raise ValueError("Filter preview accepts band or notch, not both")
    freq = np.linspace(0.0, nyquist, samples, dtype=np.float64)
    if notch_hz is not None:
        b, a = signal.iirnotch(notch_hz, Q=35, fs=fs)
        _, response = signal.freqz(b, a, worN=freq, fs=fs)
    elif low == 0 and high is None:
        return freq, np.zeros_like(freq)
    else:
        if low > 0 and high is not None:
            sos = signal.butter(order, (low, high), btype="bandpass",
                                fs=fs, output="sos")
        elif low:
            sos = signal.butter(order, low, btype="highpass",
                                fs=fs, output="sos")
        else:
            sos = signal.butter(order, high, btype="lowpass",
                                fs=fs, output="sos")
        _, response = signal.sosfreqz(sos, worN=freq, fs=fs)
    amplitude = np.abs(response) ** 2
    attenuation_db = 20 * np.log10(np.maximum(amplitude, 1e-10))
    return freq, attenuation_db


def preserve_manual_axis(
    manual_limits: tuple[float, float, float, float] | None,
    automatic_limits: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """User zoom wins over the next LIVE update unless explicitly reset."""
    if manual_limits is None:
        return automatic_limits
    vals = tuple(float(v) for v in manual_limits)
    if (len(vals) != 4 or not all(math.isfinite(v) for v in vals)
            or vals[0] >= vals[1] or vals[2] >= vals[3]):
        raise ValueError("Invalid manual axis range")
    return vals
