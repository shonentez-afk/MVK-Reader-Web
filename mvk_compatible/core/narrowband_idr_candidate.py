"""Stage111H: TMvkChannelStorage.GetNarrowbandValue / GetNoisePeak CANDIDATE.

Grounded in PRIVATE ORIGINAL Delphi IDR _Unit115.pas 007D0E58..007D10F3
and helper 007D21A8. Neither original IDR source nor measured samples are
distributed. This module never connects to an instrument and never replaces
original MVK DSP / AUX4700.
"""
from __future__ import annotations

import math
import numpy as np

from .fft_idr_candidate import check_n, idr_power_spectrum

SOURCE = 'APP_DERIVED_NARROWBAND_IDR_CANDIDATE'
NOISE_SOURCE = 'APP_DERIVED_NOISE_PEAK_IDR_CANDIDATE'


def _weighted_power_span(a: np.ndarray, start: int, stop: int) -> tuple[float, float]:
    """007D21A8: inclusive indexed float32 power/weighted sums.

    The Delphi IDR stores the intermediate sums back to single precision
    after every add. Exact 80-bit x87 register parity is not established.
    """
    energy = np.float32(0.)
    weighted = np.float32(0.)
    for k in range(start, stop + 1):
        p = float(a[k])
        weighted = np.float32(float(weighted) + k * p)
        energy = np.float32(float(energy) + p)
    if energy <= 0:
        return 0., 0.
    return float(energy), float(np.float32(float(weighted) / float(energy)))


def narrowband_from_full_power(
    power: np.ndarray, *, n_fft: int, sample_rate_hz: float,
    input_frequency_hz: float, f_range: float = 1.0,
    get_noise_peak: bool = False
) -> dict:
    """Evaluate original 007D0E58 output fields from complete FFT powers.

    InputValue is a float32 frequency; original bin/radius rounding uses the
    Delphi default nearest-even @ROUND. Radius is max(1,Round(bin*0.0005)).
    For noisy case, scan k=20*radius..floor((N/2)/4), excluding the closed
    interval [center-20*radius,center+20*radius]. Three-bin powers are added
    and compared STRICTLY >, first tie wins.

    Delphi's original narrowband bounds guard does NOT explicitly validate
    center+radius; we conservatively refuse any out-of-array read instead of
    reproducing memory-unsafe behavior. Never pad missing data or wrap.
    """
    n = check_n(n_fft)
    if n < 1024:
        raise ValueError('Original analysis view needs FFT N >= 1024')
    if not isinstance(get_noise_peak, bool):
        raise ValueError('get_noise_peak must be boolean')
    if (not math.isfinite(sample_rate_hz) or sample_rate_hz <= 0
        or not math.isfinite(input_frequency_hz) or input_frequency_hz <= 0
        or not math.isfinite(f_range) or f_range <= 0):
        raise ValueError('Frequency, sample rate and FRange must be positive and finite')

    a = np.asarray(power, dtype=np.float32)
    half = n // 2
    if (a.ndim != 1 or len(a) != half or not bool(np.isfinite(a).all())
        or bool((a < 0).any())):
        raise ValueError('Complete finite nonnegative, N/2-length FFT power is required')

    stored_hz = float(np.float32(input_frequency_hz))
    raw_bin = (n / float(sample_rate_hz)) * stored_hz
    center = round(raw_bin)
    radius = max(1, round(raw_bin * 0.0005))
    if not 1 <= center < half - 1:
        raise ValueError('Invalid original narrowband frequency bin')
    lower, upper = center - radius, center + radius
    if lower < 0 or upper >= half:
        raise ValueError('Original narrowband radius would access data outside FFT: refused')
    power_sum, weighted_bin = _weighted_power_span(a, lower, upper)
    output_value = float(np.float32(math.sqrt(power_sum / 2.) * (f_range / half)))
    df = float(sample_rate_hz) / n
    result = {
        'source': SOURCE, 'n_fft': n, 'sample_rate_hz': float(sample_rate_hz),
        'df_hz': df, 'requested_frequency_hz': stored_hz,
        'center_bin': center, 'radius_bins': radius,
        'band_first_bin': lower, 'band_last_bin': upper,
        'band_power_sum': power_sum, 'weighted_center_bin': weighted_bin,
        'output_value': output_value, 'f_range_used': float(f_range),
        'noise_peak_enabled': get_noise_peak, 'output_peak_x_bin': 0.,
        'output_peak_y': 0., 'output_peak_frequency_hz': 0.,
        'noise_scan_first_bin': None, 'noise_scan_last_bin': None,
        'noise_excluded_first_bin': None, 'noise_excluded_last_bin': None,
        'noise_raw_three_bin_power': 0.,
        'input_is_full_undecimated_fft_power': True,
        'original_delphi_numerical_parity_verified': False,
        'warning': ('IDR reconstruction; original x87/FRange, original '
                    'live/Archive window and Delphi output not yet compared')
    }
    if not get_noise_peak:
        return result

    exclusion = 20 * radius
    search_start = exclusion
    search_end = half // 4  # original (OutputLength * 64) >> 8
    result['source'] = NOISE_SOURCE
    result['noise_scan_first_bin'] = search_start
    result['noise_scan_last_bin'] = search_end
    result['noise_excluded_first_bin'] = center - exclusion
    result['noise_excluded_last_bin'] = center + exclusion
    if search_end < search_start:
        return result
    if search_start < 1 or search_end + 1 >= half:
        raise ValueError('Original noise search accesses outside FFT power: refused')
    best = np.float32(0.)
    best_bin = 0
    for k in range(search_start, search_end + 1):
        if center - exclusion <= k <= center + exclusion:
            continue
        # 007D103B..007D1052: add three neighboring stored float32 values.
        three = np.float32(float(a[k]) + float(a[k-1]) + float(a[k+1]))
        if three > best:
            best = three
            best_bin = k
    if best_bin:
        result['output_peak_x_bin'] = float(np.float32(best_bin))
        result['output_peak_y'] = float(
            np.float32(math.sqrt(float(best) / 2.) * (f_range / half)))
        result['output_peak_frequency_hz'] = float(np.float32(best_bin * df))
        result['noise_raw_three_bin_power'] = float(best)
    return result


def narrowband_from_samples(
    samples: np.ndarray, *, sample_rate_hz: float, input_frequency_hz: float,
    get_noise_peak: bool = False, f_range: float = 1.0,
    backend: str = 'idr_float32'
) -> dict:
    """007D0F7D..007D0FA7: raw f32 history -> remove DC once -> FFT.

    Exact input window must already be selected by an offline caller.
    Instrument DSP third-octave and RMS must NOT use this calculation.
    """
    values = np.asarray(samples, dtype=np.float32)
    if values.ndim != 1 or not bool(np.isfinite(values).all()):
        raise ValueError('Expected a one-dimensional finite BIN time window')
    n = check_n(len(values))
    power, removed = idr_power_spectrum(values, backend=backend, remove_dc=True)
    result = narrowband_from_full_power(
        power, n_fft=n, sample_rate_hz=sample_rate_hz,
        input_frequency_hz=input_frequency_hz, f_range=f_range,
        get_noise_peak=get_noise_peak)
    result['removed_mean_m_s2'] = float(removed)
    result['fft_backend'] = backend
    result['window_samples'] = n
    result['raw_archive_position_parity_verified'] = False
    return result
