"""Operator-controlled 1× shaft-speed proposal from VIBRATION VELOCITY ONLY.

Never contacts or reads either TACH channel. It proposes, but does not assert,
RPM from a physical velocity spectrum (mm/s line RMS) with independent
spectral peaks and harmonic support. A strong 2×/3× peak alone does not prove
the shaft frequency: the user must explicitly accept a proposed candidate.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.signal import find_peaks

from .spectrum import FFT_SIZES, calculate_spectrum


@dataclass(frozen=True)
class RotationEstimate:
    hz: float
    rpm: float
    line_rms_mm_s: float
    snr_db: float
    harmonic_hits: tuple[int, ...]
    confidence: str
    resolution_hz: float
    source: str = "VELOCITY_FFT_PROPOSAL_NO_TACH"

    @property
    def description(self) -> str:
        tail = (", ".join(f"{n}×" for n in self.harmonic_hits)
                if self.harmonic_hits else "другие гармоники не подтверждены")
        return (f"1×? {self.hz:.2f} Гц = {self.rpm:.1f} об/мин; "
                f"ВС {self.line_rms_mm_s:.4g} мм/с СКЗ; "
                f"SNR {self.snr_db:.1f} дБ; {tail}; уверенность: {self.confidence}. "
                "Гипотеза по спектру, не TACH; подтвердите применением.")


def estimate_rotation_from_velocity(
    calibrated_acceleration: np.ndarray,
    fs: int,
    *,
    nfft: int = 32768,
    min_rpm: float = 300.0,
    max_rpm: float = 18000.0,
) -> RotationEstimate:
    if (type(nfft) is not int or nfft not in FFT_SIZES or
            not np.isfinite(min_rpm) or not np.isfinite(max_rpm) or
            not 0 < min_rpm < max_rpm <= 200000):
        raise ValueError("Invalid FFT or operator shaft RPM limits")
    if type(fs) is not int or fs < 16:
        raise ValueError("Insufficient sampling frequency")
    df = fs/nfft
    low = max(2.0, min_rpm/60.0 * 0.5)
    high = min(max(300.0,max_rpm/60.0*5),fs*0.45)
    if high<=low or max_rpm/60.0>=fs*.45:
        raise ValueError("RPM range exceeds measured Nyquist band")
    spectrum=calculate_spectrum(
        calibrated_acceleration, fs, kind="velocity", nfft=nfft,
        band_hz=(low,high))
    freq=spectrum.hz
    y=spectrum.rms
    valid=(freq>=min_rpm/60.0)&(freq<=max_rpm/60.0)&np.isfinite(y)
    if np.count_nonzero(valid)<8:
        raise ValueError("Insufficient FFT resolution for configured 1× range")
    region=y[valid]
    floor=max(float(np.median(region)),np.finfo(np.float64).tiny)
    peak_max=float(np.max(region))
    if not np.isfinite(peak_max) or peak_max<1e-10:
        raise ValueError("No significant velocity harmonic")
    indices,_=find_peaks(y,distance=2)
    indices=np.array([i for i in indices if valid[i] and
                      y[i]>=max(floor*6.0,peak_max*0.065)],
                     dtype=np.int64)
    if indices.size==0:
        raise ValueError("No reliable velocity line above local noise floor")
    # Candidates are ranked mainly by the earliest significant 1× line,
    # but 2×..5× support increases confidence; no hidden TACH inference.
    candidates=[]
    for i in indices:
        f0=float(freq[i])
        strength=float(y[i])
        snr=20*math.log10(max(strength/floor,1))
        hits=[]
        for n in (2,3,4,5):
            target=f0*n
            if target>=fs/2 or target>high:
                continue
            neighbourhood=np.abs(freq-target)<=max(1.75*df,target*.012)
            if not np.any(neighbourhood):
                continue
            power=float(np.max(y[neighbourhood]))
            if power>=max(floor*6,strength*.08):
                hits.append(n)
        candidates.append((f0,i,snr,tuple(hits),strength))
    # Earliest large component tends to be 1× rather than strongest 2×.
    # Still present it only as a proposal; confidence penalizes low support.
    f0,i,snr,hits,strength=min(candidates,key=lambda row:row[0])
    if snr<12:
        raise ValueError("Rotation candidate too close to spectral noise floor")
    resolved=df/f0
    if len(hits)>=2 and resolved<.04 and snr>=20:
        confidence="высокая (только спектральная)"
    elif (len(hits)>=1 or strength>peak_max*.45) and resolved<.1:
        confidence="средняя (проверить 1×)"
    else:
        confidence="низкая (возможны 2× или посторонний источник)"
    # Quadratic frequency interpolation on log magnitudes; actual Δf is
    # reported separately so sub-bin interpolation isn't fake resolution.
    if 0<i<len(y)-1:
        vals=np.log(np.maximum(y[i-1:i+2],floor*1e-6))
        denominator=vals[0]-2*vals[1]+vals[2]
        if denominator<0:
            offset=float(np.clip(.5*(vals[0]-vals[2])/denominator,-.5,.5))
            f0=float(freq[i]+offset*df)
    return RotationEstimate(
        hz=f0, rpm=f0*60.0, line_rms_mm_s=strength,snr_db=snr,
        harmonic_hits=hits,confidence=confidence,resolution_hz=df,
    )
