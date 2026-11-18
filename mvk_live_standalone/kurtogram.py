"""Validated integration of PySDKit's true binary/ternary Fast Kurtogram.

The vendor algorithm lives unmodified numerically in _pysdkit_kurtogram.py;
this module checks ADC metadata and exposes physically labelled map cells.
APP_DERIVED: NOT the original MVK01 device DSP or a fault verdict.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np

from ._pysdkit_kurtogram import fast_kurtogram


@dataclass(frozen=True)
class KurtogramResult:
    scores: np.ndarray
    frequencies_hz: np.ndarray
    levels: np.ndarray
    fs: int
    n_samples: int
    nlevel: int
    best_row: int
    best_col: int
    best_center_hz: float
    best_bandwidth_hz: float
    best_score: float

    def cell_band(self, row: int, col: int) -> tuple[float, float, float, float, float]:
        """Band edges (Hz), centre (Hz), bandwidth (Hz), and excess kurtosis.

        Match the exact PySDKit/MATLAB coordinate equation, not the display
        centre grid (the latter is only an image-axis coordinate).
        """
        if (type(row) is not int or type(col) is not int or row < 0 or
                col < 0 or row >= self.scores.shape[0] or col >= self.scores.shape[1]):
            raise ValueError("Kurtogram cell is outside the computed map")
        level=float(self.levels[row])
        bw=float(self.fs)*2.0**(-level-1.0)
        # The PySDKit image repeats one packet-node score across several
        # raster columns. Select the NODE, not a different imaginary
        # centre for each duplicated pixel. For integer levels there are
        # 2**k bands; the ternary rows have 3*2**(k-1) bands.
        n_bands=int(round(2.0**level))
        group_width=self.scores.shape[1]//n_bands
        group_col=(col//group_width)*group_width
        fc=float(self.fs)*(group_col/(3.0*2.0**(self.nlevel+1))+
                           2.0**(-2.0-level))
        # Analytic-filter bank touches 0/Nyquist on outer cells; follow-up
        # Butterworth/Hilbert processing requires strictly interior corners.
        lo=max(fc-bw/2.0,max(1.0,self.fs/self.n_samples))
        hi=min(fc+bw/2.0,(self.fs/2.0)*(1.0-1e-6))
        if not (0.0<lo<hi<self.fs/2.0):
            raise ValueError("No valid demodulation band below Nyquist")
        return lo,hi,fc,bw,float(self.scores[row,col])

    def best_band(self) -> tuple[float, float, float, float, float]:
        return self.cell_band(self.best_row,self.best_col)


def compute_fast_kurtogram(acceleration: np.ndarray, fs: int, *,
                           nlevel: int=4) -> KurtogramResult:
    """Run the actual PySDKit Fast Kurtogram for ONE verified ADC window.

    Fs is measured/verified from Go, not chosen by the GUI. No new TCP,
    FRange, hidden synthetic samples, interpolation or zero padding.
    """
    if type(fs) is not int or not 2048<=fs<=262144:
        raise ValueError("Fs must be a verified physical sample rate")
    src=np.asarray(acceleration)
    if src.ndim!=1 or not 2048<=src.size<=65536:
        raise ValueError("Fast Kurtogram needs 2048..65536 genuine ADC samples")
    if not np.issubdtype(src.dtype,np.number):
        raise ValueError("ADC signal must contain numeric samples")
    x=np.asarray(src,dtype=np.float64)
    if not np.isfinite(x).all():
        raise ValueError("ADC signal must be entirely finite")
    if float(np.var(x))<=1e-24:
        raise ValueError("No usable vibration variance; kurtogram unavailable")
    if type(nlevel) is not int or not 2<=nlevel<=6:
        raise ValueError("Kurtogram decomposition level must be 2..6")
    allowed=math.floor(math.log2(x.size)-7)
    if nlevel>allowed:
        raise ValueError(f"Kurtogram level {nlevel} requires more genuine samples (max {allowed})")
    matrix,info=fast_kurtogram(x,nlevel,fs=float(fs))
    matrix=np.asarray(matrix,dtype=np.float64)
    if matrix.shape!=(2*nlevel,3*(2**nlevel)) or not np.isfinite(matrix).all():
        raise ValueError("PySDKit Fast Kurtogram returned invalid map coordinates")
    row,col=int(info["row"]),int(info["col"])
    return KurtogramResult(matrix,np.asarray(info["freq_w"],dtype=float),
                           np.asarray(info["level_w"],dtype=float),fs,int(x.size),
                           nlevel,row,col,float(info["fc"]),float(info["bw"]),
                           float(info["Kmax"]))
