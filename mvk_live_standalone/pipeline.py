"""Single bounded worker entry point for interactive mechanical-vibration DSP."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np

from .advanced import (
    DemodulationBand, ExtendedFeatures, BandRMS,
    extended_time_features, broadband_rms, DemodulationBand,
)
from .vibration import VibrationView, analyze_vibration
from .kurtogram import compute_fast_kurtogram


@dataclass(frozen=True)
class AnalysisResult:
    view: VibrationView
    features: ExtendedFeatures
    broadband_velocity: BandRMS | None
    auto_envelope: DemodulationBand | None


def analyze_live(
    samples: np.ndarray, fs: int, *,
    kind: str, mode: str, nfft: int,
    band_hz: tuple[float,float|None],
    smooth_bins: int,
    envelope_band: tuple[float,float] | str,
    notch_hz: float | None,
) -> AnalysisResult:
    x=np.asarray(samples,dtype=np.float64)
    if x.ndim!=1 or len(x)<nfft or not np.isfinite(x).all():
        raise ValueError("Need a real finite calibrated window without padding")
    selected=None
    if mode=="envelope" and envelope_band=="auto":
        # Former approximate dyadic Butterworth search is NOT Fast Kurtogram.
        # Use the pinned MIT PySDKit binary/ternary filter-bank instead.
        source=x[-min(len(x),32768):]
        depth=min(4,math.floor(math.log2(source.size)-7))
        view=compute_fast_kurtogram(source,fs,nlevel=depth)
        lo,hi,_,_,_=view.best_band()
        selected=DemodulationBand(
            lo,hi,view.best_score,int(view.scores.size),
            "максимальная импульсность, не доказательство дефекта",
            method="PYSDKIT_FAST_KURTOGRAM_ANTONI_2007")
        envelope=(selected.low_hz,selected.high_hz)
    elif isinstance(envelope_band,tuple) and len(envelope_band)==2:
        envelope=envelope_band
    elif mode=="envelope":
        raise ValueError("Unknown requested envelope resonance band")
    else:
        envelope=(1000.0,min(3000.0,fs*.4))
    view=analyze_vibration(
        x,fs,kind=kind,mode=mode,nfft=nfft,
        band_hz=band_hz,envelope_band_hz=envelope,
        smooth_bins=smooth_bins,notch_hz=notch_hz)
    features=extended_time_features(x[-min(len(x),max(2048,fs)):])
    velocity=None
    hi=min(1000.0,fs*.45)
    low=10.0
    if hi>low+max(3*fs/nfft,1.0):
        velocity=broadband_rms(x,fs,kind="velocity",
                               band_hz=(low,hi),nfft=min(nfft,8192))
    return AnalysisResult(view,features,velocity,selected)
