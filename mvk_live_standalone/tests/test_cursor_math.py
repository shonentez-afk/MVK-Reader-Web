"""Physically defined measurements of existing samples without device access."""
from __future__ import annotations

import math

import numpy as np
import pytest

from mvk_live_standalone.cursor_math import (
    harmonic_frequencies, nearest_point, nearest_local_peak,
    sideband_frequencies, spectral_band, time_interval, time_point,
)


def test_cursor_snaps_to_real_fft_bin_not_interpolated_value():
    f = np.arange(0., 201., 1.)
    values = np.zeros_like(f)
    values[99:102] = [1., 12., 4.]
    nearest = nearest_point(f, values, 99.7)
    assert (nearest.index, nearest.position, nearest.value) == (100, 100., 12.)
    assert nearest_local_peak(f, values, 102.1).position == 100.
    assert nearest_point(f, values, -10).position == 0.
    assert nearest_point(f, values, 500).position == 200.


def test_harmonic_and_symmetric_sideband_markers_are_theoretical_only():
    assert harmonic_frequencies(20., 5, 72.) == [
        ("H1", 20.), ("H2", 40.), ("H3", 60.)]
    assert sideband_frequencies(100., 10., 2, 115.) == [
        ("Центр", 100.), ("−1", 90.), ("+1", 110.),
        ("−2", 80.)]
    with pytest.raises(ValueError):
        harmonic_frequencies(0., 5, 100.)
    with pytest.raises(ValueError):
        sideband_frequencies(100., 0., 3, 1000.)


def test_psd_and_asd_band_rms_integrate_power_not_fft_amplitudes():
    f = np.arange(0., 101., 1.)
    psd = np.full_like(f, 4.)
    a = spectral_band(f, psd, 20., 30., "welch")
    b = spectral_band(f, np.sqrt(psd), 20., 30., "asd")
    assert a.method == b.method == "RMS_FROM_DENSITY"
    assert a.value == pytest.approx(math.sqrt(40.))
    assert b.value == pytest.approx(a.value)
    peak = spectral_band(f, psd, 20., 30., "fft")
    assert peak.method == "MAX_SPECTRAL_LINE"
    assert peak.value == 4.
    with pytest.raises(ValueError):
        spectral_band(f, psd, 99., 100.5, "welch")


def test_time_cursor_reads_original_samples_and_interval_without_decimation():
    fs = 1000
    x = np.sin(2*np.pi*10*np.arange(1000)/fs)
    p = time_point(x, fs, -0.25)
    assert p.index == 750
    assert p.position == pytest.approx(-0.25)
    assert p.value == pytest.approx(x[750])
    span = time_interval(x, fs, -0.5, -0.1)
    assert span.duration == pytest.approx(.4)
    assert span.samples == 401
    assert span.rms == pytest.approx(math.sqrt(.5), abs=.005)
    assert span.peak_to_peak == pytest.approx(2., abs=.001)
    with pytest.raises(ValueError):
        time_interval(x, fs, -.1, -.1)


@pytest.mark.parametrize("axis,values", [
    ([0, 1, 1], [1, 2, 3]),
    ([0, 2, 1], [1, 2, 3]),
    ([0, float("nan")], [1, 2]),
    ([0, 1], [float("nan"), 2]),
    ([], []),
])
def test_invalid_sample_series_is_rejected(axis, values):
    with pytest.raises(ValueError):
        nearest_point(axis, values, 1.)


def test_single_impulse_does_not_change_interval_source_or_create_samples():
    fs = 8192
    x = np.zeros(8192)
    x[100] = 3.0
    measured = time_interval(x, fs, -.99, -.95)
    assert measured.samples > 1
    assert measured.rms >= 0
    assert np.count_nonzero(x) == 1  # cursor never modifies source
