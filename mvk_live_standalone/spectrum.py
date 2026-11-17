"""Independent MVK Live vibration spectrum engine.

Input: *already calibrated* ADC acceleration in m/s², from verified Native R6.1
BIN spool / LIVE_PREVIEW. Never apply sensor gain a second time.

These are one-sided RMS amplitudes PER FFT LINE of a Hann-windowed waveform,
not PSD or ASD and not the instrument's original AUX4700 DSP readings.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.signal import butter, sosfiltfilt

Kind = Literal["acceleration", "velocity", "displacement"]
Scale = Literal["linear", "db", "log"]
KINDS: dict[str, tuple[str, str]] = {
    "acceleration": ("ВУ · Виброускорение", "м/с²"),
    "velocity": ("ВС · Виброскорость", "мм/с"),
    "displacement": ("ВП · Виброперемещение", "мкм"),
}
PRESET_BANDS: dict[str, tuple[float, float | None]] = {
    "Весь диапазон": (0.0, None),
    "0,62–150 Гц": (0.62, 150.0),
    "0,62–300 Гц": (0.62, 300.0),
    "2–1000 Гц": (2.0, 1000.0),
    "10–1000 Гц": (10.0, 1000.0),
    "10–2000 Гц": (10.0, 2000.0),
    "10–3000 Гц": (10.0, 3000.0),
}
FFT_SIZES = (8192, 16384, 32768, 65536, 131072, 262144)

# ISO 1683 vibratory RMS reference levels, expressed in the same units
# as the already-calibrated one-sided FFT amplitude for each spectrum kind.
# 1e-6 m/s², 1e-9 m/s == 1e-6 mm/s, 1e-12 m == 1e-6 um.
# These are NOT the device's proprietary dB references. Every result is
# explicitly labeled with the reference; the user can select 1 physical unit.
DB_REFERENCES: dict[str, dict[str, float]] = {
    "iso": {key: 1e-6 for key in KINDS},
    "unit": {key: 1.0 for key in KINDS},
}
DEFAULT_DB_FLOOR = -180.0  # display floor, never a physical measurement


def db_reference(kind: Kind, reference: str = "iso") -> float:
    if kind not in KINDS or reference not in DB_REFERENCES:
        raise ValueError("Unknown decibel reference")
    return DB_REFERENCES[reference][kind]


def db_reference_text(kind: Kind, reference: str = "iso") -> str:
    value = db_reference(kind, reference)
    number = "1×10⁻⁶" if value == 1e-6 else f"{value:g}"
    return f"{number} {KINDS[kind][1]} СКЗ"



@dataclass(frozen=True)
class Spectrum:
    hz: np.ndarray
    rms: np.ndarray
    kind: Kind
    units: str
    rate_hz: int
    nfft: int
    band_hz: tuple[float, float | None]
    waveform: np.ndarray

    @property
    def resolution_hz(self) -> float:
        return self.rate_hz / self.nfft

    @property
    def peak(self) -> tuple[float, float]:
        valid = (self.hz > 0) & np.isfinite(self.rms)
        if not np.any(valid):
            return (float("nan"), float("nan"))
        positions = np.flatnonzero(valid)
        i = positions[int(np.argmax(self.rms[valid]))]
        return (float(self.hz[i]), float(self.rms[i]))


def y_axis_label(kind: Kind, scale: Scale = "linear",
                 reference: str = "iso") -> str:
    if kind not in KINDS:
        raise ValueError("Unknown physical spectrum kind")
    if scale == "linear":
        return f"{KINDS[kind][0]}, {KINDS[kind][1]} СКЗ"
    if scale in ("log", "db"):  # legacy log == dB, never pyqtgraph log-Y
        return f"{KINDS[kind][0]}, дБ (отн. {db_reference_text(kind, reference)})"
    raise ValueError("Unknown Y scale")


def plot_values(spectrum: Spectrum, scale: Scale, *,
                reference: str = "iso",
                floor_db: float = DEFAULT_DB_FLOOR) -> np.ndarray:
    """dB = 20*log10(RMS / explicit reference), returned as LINEAR-Y dB data.

    The display floor prevents -Inf for silence and is never reported as a
    real measurement. In the Qt plot the Y axis MUST NOT be log-transformed
    again. The optional legacy "log" spelling means this SAME dB mode.
    """
    y = spectrum.rms.astype(np.float64, copy=True)
    if scale == "linear":
        return y
    if scale not in ("db", "log"):
        raise ValueError("Unknown Y scale")
    ref = db_reference(spectrum.kind, reference)
    if not np.isfinite(floor_db) or not -400 < floor_db < 0:
        raise ValueError("Invalid dB display floor")
    floor = ref * (10.0 ** (floor_db / 20.0))
    return 20.0 * np.log10(np.maximum(y, floor) / ref)


def _filter_waveform(wave: np.ndarray, fs: int, low: float, high: float | None) -> np.ndarray:
    """Zero-phase Butterworth filter, before FFT. No filtering of RMS magnitudes."""
    nyquist = fs / 2.0
    if not np.isfinite(low) or low < 0:
        raise ValueError("Low cutoff must be nonnegative")
    if high is not None and (not np.isfinite(high) or high <= 0 or low >= high):
        raise ValueError("High cutoff must exceed low cutoff")
    if high is not None and high >= nyquist:
        raise ValueError("High cutoff exceeds Nyquist; choose a valid filter band")
    if low >= nyquist:
        raise ValueError("Low cutoff exceeds Nyquist")
    if low == 0 and high is None:
        return wave.copy()
    if low and high is not None:
        sos = butter(4, (low, high), btype="bandpass", fs=fs, output="sos")
    elif low:
        sos = butter(4, low, btype="highpass", fs=fs, output="sos")
    else:
        sos = butter(4, high, btype="lowpass", fs=fs, output="sos")
    return sosfiltfilt(sos, wave)


def calculate_spectrum(
    calibrated_acceleration: np.ndarray,
    fs: int,
    *,
    kind: Kind = "acceleration",
    nfft: int = 32768,
    band_hz: tuple[float, float | None] = (0.0, None),
    smooth_bins: int = 1,
) -> Spectrum:
    if kind not in KINDS:
        raise ValueError("Unsupported spectrum kind")
    if type(fs) is not int or fs < 2:
        raise ValueError("Invalid sample rate")
    if type(nfft) is not int or nfft not in FFT_SIZES:
        raise ValueError("FFT size must be explicitly selected")
    x = np.asarray(calibrated_acceleration, dtype=np.float64)
    if x.ndim != 1 or len(x) < nfft or not np.all(np.isfinite(x[-nfft:])):
        raise ValueError("Need N real, finite calibrated ADC samples; do not pad")
    if smooth_bins < 1 or smooth_bins > 101 or smooth_bins % 2 == 0:
        raise ValueError("Smoothing width must be an odd number 1..101")
    low, high = band_hz
    x = x[-nfft:].copy()
    x = x - np.mean(x, dtype=np.float64)  # suppress DC before integration
    if low > 0 or high is not None:
        x = _filter_waveform(x, fs, float(low), None if high is None else float(high))
    window = np.hanning(nfft)
    coherent_gain = np.sum(window)
    fft = np.fft.rfft(x * window)
    # Hann coherent-gain correction makes an on-bin sinusoid's peak amplitude
    # independent of the FFT size. Convert peak -> RMS (sqrt(2)).
    rms = (np.abs(fft) * (np.sqrt(2.0) / coherent_gain))
    rms[-1] *= 0.5  # Nyquist is not paired with a negative-frequency bin
    rms[0] = 0.0
    f = np.fft.rfftfreq(nfft, 1.0 / fs)
    if kind != "acceleration":
        omega = 2.0 * np.pi * f
        nonzero = omega > 0
        multiplier = np.zeros_like(omega)
        if kind == "velocity":
            multiplier[nonzero] = 1_000.0 / omega[nonzero]  # m/s -> mm/s
        else:
            multiplier[nonzero] = 1_000_000.0 / (omega[nonzero] ** 2)  # m -> µm
        rms *= multiplier
        rms[0] = 0.0  # no physically valid DC integration
    if smooth_bins > 1:
        # Power-domain smoothing; never manufacture new signal frequencies.
        kernel = np.ones(smooth_bins, dtype=np.float64)
        power = np.convolve(rms * rms, kernel, mode="same")
        counts = np.convolve(np.ones_like(rms), kernel, mode="same")
        rms = np.sqrt(power / counts)
        rms[0] = 0.0
    return Spectrum(hz=f, rms=rms, kind=kind, units=KINDS[kind][1],
                    rate_hz=fs, nfft=nfft, band_hz=band_hz, waveform=x)
