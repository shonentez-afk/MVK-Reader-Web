"""Stage13 offline weighted fixed-band reference scaffold.

This is NOT a verified vendor algorithm. Upper/lower edge weights and zone
boundaries MUST be sourced independently; absent weights cause an error.
No TCP, no network, no changes to production collector.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
import numpy as np
from scipy.signal import periodogram

@dataclass(frozen=True)
class Zone:
    name: str
    low_hz: float
    high_hz: float
    weights: Callable[[np.ndarray], np.ndarray]

def hann_psd(samples: np.ndarray, fs: float):
    """Window-power normalized one-sided PSD; units acceleration^2/Hz."""
    x = np.asarray(samples, dtype=np.float64)
    if x.ndim != 1 or x.size < 4 or not np.isfinite(x).all():
        raise ValueError("Expected a finite one-dimensional signal")
    if not (0 < fs):
        raise ValueError("fs must be positive")
    return periodogram(x, fs=fs, window="hann", detrend="constant",
                       scaling="density")

def integrate_three_zones(freq: np.ndarray, psd: np.ndarray, zones: list[Zone]):
    """Weighted sum of powers in disjoint spectral zones, then RMS.

    Frequency-domain weights are *POWER* weights (|H|^2), not amplitude gains.
    Transition functions are user supplied and MUST NOT be silently invented.
    """
    f = np.asarray(freq)
    p = np.asarray(psd)
    if f.ndim != 1 or f.size < 2 or f.shape != p.shape:
        raise ValueError("freq and psd arrays must align")
    if not np.isfinite(p).all() or np.any(p < 0):
        raise ValueError("PSD must be nonnegative and finite")
    if not np.allclose(np.diff(f), f[1]-f[0]):
        raise ValueError("Uniform frequency grid required")
    if len(zones) != 3 or [z.name for z in zones] != ["lower", "interior", "upper"]:
        raise ValueError("Three zones required: lower, interior, upper")
    ordered = sorted(zones, key=lambda z: z.low_hz)
    if any(z.low_hz >= z.high_hz for z in ordered):
        raise ValueError("Invalid zone bounds")
    if any(a.high_hz > b.low_hz for a,b in zip(ordered, ordered[1:])):
        raise ValueError("Zones overlap; double counting prohibited")
    df = f[1]-f[0]
    parts = {}
    for z in zones:
        select = (f >= z.low_hz) & (f < z.high_hz)
        w = np.asarray(z.weights(f[select]), dtype=float)
        if w.shape != f[select].shape or not np.isfinite(w).all():
            raise ValueError(f"Invalid weight shape/values in {z.name}")
        if np.any((w < 0) | (w > 1)):
            raise ValueError("Power weights must be between 0 and 1")
        parts[z.name] = float(np.sum(p[select]*w)*df)
    return {"rms": float(np.sqrt(sum(parts.values()))),
            "power_contributions": parts}

def flat_one(f):
    return np.ones_like(f, dtype=float)

def explicit_zones(lower_bounds, interior_bounds, upper_bounds,
                   lower_power_weights, upper_power_weights):
    """Only use with externally documented/verified edge functions."""
    return [
        Zone("lower", *lower_bounds, lower_power_weights),
        Zone("interior", *interior_bounds, flat_one),
        Zone("upper", *upper_bounds, upper_power_weights),
    ]

def third_octave_centers(low: float, high: float, reference: float=1000.0):
    """Exact base-2 1/3 octave center grid; not vendor edge-window weights."""
    ks=np.arange(-80,81)
    centers=reference*2.0**(ks/3.0)
    return centers[(centers >= low)&(centers <= high)]

def third_octave_rectangular_power(freq, psd, low, high):
    """Diagnostic baseline only: ideal logarithmic bands, NOT vendor window."""
    centers=third_octave_centers(low,high)
    df=freq[1]-freq[0]
    return [(float(c),float(np.sum(psd[(freq>=c*2**(-1/6))&
                                           (freq<c*2**(1/6))])*df))
            for c in centers]
