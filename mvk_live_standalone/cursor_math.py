"""Physical, non-diagnostic cursor measurements for real MVK Live samples.

All positions are in Hz or seconds, never pyqtgraph log10 view coordinates.
Calculations use the complete selected FFT or filtered time block, not chart
decimation. No original RX/FRange/AUX4700 device code is used here.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class CursorPoint:
    index: int
    position: float
    value: float


@dataclass(frozen=True)
class IntervalValues:
    start: float
    end: float
    duration: float
    samples: int
    rms: float
    peak_to_peak: float
    mean: float


@dataclass(frozen=True)
class BandValues:
    start_hz: float
    end_hz: float
    method: str
    value: float
    frequency_hz: float | None


def _series(axis, values):
    a = np.asarray(axis, dtype=np.float64)
    v = np.asarray(values, dtype=np.float64)
    if (a.ndim != 1 or v.ndim != 1 or len(a) == 0 or len(a) != len(v)
            or not np.all(np.isfinite(a)) or not np.all(np.isfinite(v))
            or (len(a) > 1 and not np.all(np.diff(a) > 0))):
        raise ValueError("Нужен реальный возрастающий ряд без пропусков")
    return a, v


def nearest_point(axis, values, position: float) -> CursorPoint:
    """Nearest original sample/bin; neither interpolation nor an invented peak."""
    a, v = _series(axis, values)
    if not math.isfinite(position):
        raise ValueError("Неверная позиция курсора")
    right = int(np.searchsorted(a, position, side="left"))
    i = min(right, len(a) - 1)
    if i > 0 and abs(a[i-1] - position) <= abs(a[i] - position):
        i -= 1
    return CursorPoint(i, float(a[i]), float(v[i]))


def nearest_local_peak(axis, amplitudes, position: float,
                       search_bins: int = 8) -> CursorPoint:
    """Local peak of actual spectrum near cursor, no sub-bin claim.

    The strongest candidate within a bounded neighbourhood is chosen.
    A flat/noisy segment may yield a maximum but it is NOT fault evidence.
    """
    a, v = _series(axis, amplitudes)
    if not isinstance(search_bins, int) or search_bins < 1 or search_bins > 256:
        raise ValueError("Неверное окно поиска пика")
    near = nearest_point(a, v, position).index
    lo = max(0, near-search_bins)
    hi = min(len(a), near+search_bins+1)
    candidates = []
    for i in range(lo, hi):
        if (i > 0 and i+1 < len(a)
                and v[i] > v[i-1] and v[i] >= v[i+1]):
            candidates.append(i)
    if not candidates:
        return nearest_point(a, v, position)
    best = max(candidates, key=lambda i: (v[i], -abs(a[i]-position)))
    return CursorPoint(best, float(a[best]), float(v[best]))


def harmonic_frequencies(fundamental_hz: float, count: int,
                         maximum_hz: float) -> list[tuple[str, float]]:
    if (not math.isfinite(fundamental_hz) or fundamental_hz <= 0
            or not math.isfinite(maximum_hz) or maximum_hz <= 0
            or type(count) is not int or not 1 <= count <= 20):
        raise ValueError("Неверная основная частота или число гармоник")
    return [(f"H{i}", fundamental_hz*i) for i in range(1, count+1)
            if fundamental_hz*i <= maximum_hz]


def sideband_frequencies(carrier_hz: float, spacing_hz: float,
                         pairs: int, maximum_hz: float
                         ) -> list[tuple[str, float]]:
    if (not math.isfinite(carrier_hz) or carrier_hz <= 0
            or not math.isfinite(spacing_hz) or spacing_hz <= 0
            or not math.isfinite(maximum_hz) or maximum_hz <= 0
            or type(pairs) is not int or not 1 <= pairs <= 10):
        raise ValueError("Неверная несущая, шаг или число боковых")
    result = [("Центр", carrier_hz)]
    for k in range(1, pairs+1):
        for sign, text in ((-1, "−"), (1, "+")):
            freq = carrier_hz + sign*k*spacing_hz
            if 0 < freq <= maximum_hz:
                result.append((f"{text}{k}", freq))
    return result


def spectral_band(axis_hz, values, start_hz: float, end_hz: float,
                  mode: str) -> BandValues:
    """RMS integral is valid only for PSD/ASD; FFT gives line maximum.

    Summing Hann-window RMS amplitudes by bins would fabricate broadband RMS.
    """
    a, v = _series(axis_hz, values)
    if (not math.isfinite(start_hz) or not math.isfinite(end_hz)
            or start_hz >= end_hz or start_hz < a[0] or end_hz > a[-1]):
        raise ValueError("Границы полосы вне реально измеренного диапазона")
    within = (a >= start_hz) & (a <= end_hz)
    if not np.any(within):
        raise ValueError("В выбранной полосе нет измеренных линий")
    x, y = a[within], v[within]
    if mode in ("welch", "asd"):
        if len(x) < 2:
            raise ValueError("Для интеграла плотности нужны хотя бы две линии")
        density = np.maximum(y, 0) if mode == "welch" else y*y
        rms = math.sqrt(max(float(np.trapezoid(density, x)), 0.0))
        return BandValues(float(x[0]), float(x[-1]), "RMS_FROM_DENSITY", rms, None)
    if mode not in ("fft", "envelope", "third_octave"):
        raise ValueError("Неподдерживаемый тип спектра")
    j = int(np.argmax(y))
    return BandValues(float(x[0]), float(x[-1]), "MAX_SPECTRAL_LINE",
                      float(y[j]), float(x[j]))


def time_interval(samples, fs: int, first_s: float,
                  second_s: float) -> IntervalValues:
    """Interval on real, uniformly sampled signal, time relative to block end."""
    data = np.asarray(samples, dtype=np.float64)
    if (data.ndim != 1 or data.size < 2 or type(fs) is not int or fs <= 0
            or not np.all(np.isfinite(data))
            or not math.isfinite(first_s) or not math.isfinite(second_s)):
        raise ValueError("Нет корректного временного сигнала")
    start, end = sorted((first_s, second_s))
    n = len(data)
    first = max(0, min(n-1, int(round(start*fs+n))))
    last = max(0, min(n-1, int(round(end*fs+n))))
    if last <= first:
        raise ValueError("Интервал меньше двух реальных отсчётов")
    section = data[first:last+1]
    return IntervalValues(
        start=float((first-n)/fs), end=float((last-n)/fs),
        duration=float((last-first)/fs), samples=len(section),
        rms=float(np.sqrt(np.mean(section*section))),
        peak_to_peak=float(np.max(section)-np.min(section)),
        mean=float(np.mean(section)),
    )


def time_point(samples, fs: int, position_s: float) -> CursorPoint:
    data = np.asarray(samples, dtype=np.float64)
    if data.ndim != 1 or not len(data) or type(fs) is not int or fs <= 0:
        raise ValueError("Нет реальных отсчётов")
    if not math.isfinite(position_s):
        raise ValueError("Неверный момент времени")
    n = len(data)
    i = max(0, min(n-1, int(round(position_s*fs+n))))
    if not math.isfinite(float(data[i])):
        raise ValueError("В выбранном отсчёте нет значения")
    return CursorPoint(i, float((i-n)/fs), float(data[i]))
