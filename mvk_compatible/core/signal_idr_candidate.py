"""Stage111C reconstruction of unfiltered TMvkChannelStorage.GetSignal.

Evidence: private Delphi IDR 0x007D0C30..0x007D0E57 and 0x007D2228.
This models the return array, *not* the TQGrapher display or envelope DSP.
No sockets, GUI, HTTP, proprietary sources or device operations.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
from .fft_idr_candidate import mean_center_float32


@dataclass(frozen=True)
class SignalFrame:
    """A reconstructed GetSignal return buffer plus chronological data."""
    chronological: np.ndarray
    getsignal_buffer: np.ndarray
    removed_mean: float
    window_mean: float
    rms_value: float
    no_dc: bool
    sample_rate: float
    output_length: int
    provenance: str = 'APP_DERIVED_GETSIGNAL_NO_ENVELOPE_IDR_CANDIDATE'


def unfiltered_getsignal(samples: np.ndarray, sample_rate: float,
                         *, no_dc: bool = True, envelope_code: int = 0,
                         f_range: float = 1.0) -> SignalFrame:
    """Reconstruct normal *float storage* GetSignal, preserving BIN input.

    007D0CE1: when NoDC true call 007D2344 (sequential f32 mean).
    007D0DEC: copy results into Output[n - 1 - i] in both modes.
    007D0DFB: RMS via f64 accumulating squared stored float32 values,
              final sqrt rounded to f32.
    No-envelope float path *does not multiply by FRange* (007D22DD).
    Envelope path is a separate, unverified filter and is REFUSED.
    """
    if envelope_code:
        raise NotImplementedError('Original GetSignal envelope filter requires original coefficient tables; no approximation')
    if not math.isfinite(sample_rate) or sample_rate <= 0:
        raise ValueError('Sample rate must be positive and finite')
    if not math.isfinite(f_range) or f_range <= 0:
        raise ValueError('Invalid storage FRange')
    a = np.asarray(samples, dtype=np.float32)
    if a.ndim != 1 or not a.size or not bool(np.isfinite(a).all()):
        raise ValueError('Input must be a nonempty finite float32 signal')
    centered, removed = mean_center_float32(a)
    chronological = centered if no_dc else a.copy()
    output = chronological[::-1].copy()
    power = np.sum(np.square(chronological.astype(np.float64)), dtype=np.float64)
    rms = float(np.float32(math.sqrt(float(power) / len(chronological))))
    return SignalFrame(chronological=chronological, getsignal_buffer=output,
                       removed_mean=removed if no_dc else 0.0,
                       window_mean=removed,
                       rms_value=rms, no_dc=bool(no_dc),
                       sample_rate=float(sample_rate),output_length=int(a.size))


def read_ring_float32(ring: np.ndarray, *, rx_position: int,
                      valid_position: int, output_length: int) -> np.ndarray:
    """Emulate 007D2228 float ring read with prefix zero-fill.

    Ring data are indexed by absolute sample number & FBufferMask.
    The current valid range is [valid_position, rx_position).
    When requested data exceed valid history, prefix missing samples with
    zeros (before GetSignal reverses the array).  Not used to pad an
    incomplete offline BIN.
    """
    data = np.asarray(ring, dtype=np.float32)
    capacity = len(data)
    if (data.ndim != 1 or capacity <= 0 or capacity & (capacity - 1)
        or not bool(np.isfinite(data).all())):
        raise ValueError('Float32 ring must have finite power-of-two capacity')
    if (not isinstance(rx_position, int) or not isinstance(valid_position, int)
        or not isinstance(output_length, int) or rx_position < 0
        or valid_position < 0 or rx_position < valid_position
        or rx_position-valid_position > capacity or output_length < 0
        or output_length > capacity):
        raise ValueError('Invalid ring positions or requested length')
    available = min(output_length, rx_position-valid_position)
    prefix = output_length-available
    result = np.zeros(output_length, dtype=np.float32)
    if available:
        indices = (np.arange(rx_position-available, rx_position, dtype=np.int64)
                   & np.int64(capacity-1))
        result[prefix:] = data[indices]
    return result
