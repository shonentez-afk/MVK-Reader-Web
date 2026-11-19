"""Independent time-waveform controls for verified MVK01 acceleration samples.

Time X is seconds, using SI formatting for milliseconds at small windows.
Time Y is signed acceleration in m/s² (not spectral RMS or AUX4700 DSP).
Optional local filter is distinct from the spectral filter and never touches
the native Go ring, calibrated BIN/IPC bytes or device FRange.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
import numpy as np
from scipy import signal

from .octave_filters import FAMILIES, nominal_centres, preset_band

TIME_WINDOWS_S = (
    .01, .02, .05, .1, .2, .5, 1., 2., 5., 10., 20., 30.,
)
Y_ABSOLUTE_LIMITS_M_S2 = (
    .01, .1, .5, 1., 2., 5., 10., 20., 50., 100., 200., 500., 1000.,
)
TIME_FILTERS = (
    ("Без фильтра","none"),
    ("Как в MVKView · оригинальное меню 32 полос","original_preset"),
    ("ФВЧ — высоких частот","highpass"),
    ("ФНЧ — низких частот","lowpass"),
    ("Полосовой","bandpass"),
    ("Режектор 50 Гц","notch50"),
    ("Режектор 60 Гц","notch60"),
    ("1/1 октавы · выбрать полосу","octave"),
    ("1/3 октавы · выбрать полосу","third_octave"),
    ("2 октавы · выбрать полосу","double_octave"),
)


def time_filter_waveform(samples: np.ndarray, fs: int, *,
                         mode: str="none", low: float=10.,
                         high: float=1000., center: float|None=None) -> np.ndarray:
    """Physically filtered time waveform, original calibrated domain.

    SOS zero-phase IIR or narrow explicit notch. Never apply the original
    sensor gain to the already-calibrated acceleration signal again.
    """
    x=np.asarray(samples,dtype=np.float64)
    if x.ndim!=1 or not 1<=x.size<=262144 or not np.all(np.isfinite(x)):
        raise ValueError("Временной сигнал: нет конечных подтверждённых отсчётов")
    if type(fs) is not int or fs<=0:
        raise ValueError("Временной сигнал: неизвестная Fs")
    if mode=="none":
        return x.copy()
    if mode in FAMILIES:
        if center is None:
            raise ValueError("Октавный фильтр: выберите центральную частоту")
        low,high=preset_band(mode,center,fs)
        if x.size/fs < 3.0/low:
            raise ValueError("Для выбранной октавной полосы нужно не меньше трёх периодов нижней частоты")
        mode="bandpass"
    if x.size<32:
        raise ValueError("Для фильтра временного сигнала не хватает отсчётов")
    if mode in ("notch50","notch60"):
        hz=50. if mode=="notch50" else 60.
        if hz>=fs/2:
            raise ValueError("Режектор временного сигнала превышает Nyquist")
        b,a=signal.iirnotch(hz,Q=35,fs=fs)
        return signal.filtfilt(b,a,x)
    if mode not in ("highpass","lowpass","bandpass"):
        raise ValueError("Неизвестный фильтр временного сигнала")
    if (not math.isfinite(low) or not math.isfinite(high) or
            (mode!="lowpass" and low<=0) or
            (mode!="highpass" and high<=0) or
            (mode=="bandpass" and low>=high) or
            (mode!="lowpass" and low>=fs/2) or
            (mode!="highpass" and high>=fs/2)):
        raise ValueError("Граница временного фильтра должна быть ниже Nyquist")
    if mode=="highpass":
        sos=signal.butter(4,low,btype="highpass",fs=fs,output="sos")
    elif mode=="lowpass":
        sos=signal.butter(4,high,btype="lowpass",fs=fs,output="sos")
    else:
        sos=signal.butter(4,(low,high),btype="bandpass",fs=fs,output="sos")
    return signal.sosfiltfilt(sos,x)


def signed_time_limits(x: np.ndarray, limit: float|None) -> tuple[float,float]:
    if limit is not None and (type(limit) not in (int,float) or
                               not math.isfinite(limit) or limit<=0):
        raise ValueError("Масштаб времени Y должен быть положительным")
    if limit is None:
        source=np.asarray(x,dtype=np.float64)
        valid=source[np.isfinite(source)]
        maximum=float(np.max(np.abs(valid))) if valid.size else 0.0
        limit=max(1e-9,maximum*1.15)
    return (-float(limit),float(limit))


@dataclass(frozen=True)
class TimeWindowMetrics:
    """Statistics of the COMPLETE displayed, filtered acceleration window.

    AC RMS excludes its measured mean; total RMS does not. In nonzero-DC
    measurements these are deliberately different quantities.
    """
    samples: int
    fs_hz: int
    duration_s: float
    mean_m_s2: float
    rms_ac_m_s2: float
    rms_total_m_s2: float
    minimum_m_s2: float
    maximum_m_s2: float
    absolute_peak_m_s2: float
    peak_to_peak_m_s2: float
    crest_ac: float | None


def summarize_time_window(x: np.ndarray, fs: int) -> TimeWindowMetrics:
    data=np.asarray(x,dtype=np.float64)
    if (data.ndim!=1 or data.size<2 or not np.all(np.isfinite(data)) or
            type(fs) is not int or fs<=0):
        raise ValueError("No real, finite time samples for window statistics")
    mean=float(np.mean(data))
    centered=data-mean
    ac_rms=float(np.sqrt(np.mean(centered**2)))
    total_rms=float(np.sqrt(np.mean(data**2)))
    minimum=float(np.min(data))
    maximum=float(np.max(data))
    ac_peak=float(np.max(np.abs(centered)))
    return TimeWindowMetrics(
        samples=int(data.size),fs_hz=fs,duration_s=data.size/fs,
        mean_m_s2=mean,rms_ac_m_s2=ac_rms,rms_total_m_s2=total_rms,
        minimum_m_s2=minimum,maximum_m_s2=maximum,
        absolute_peak_m_s2=max(abs(minimum),abs(maximum)),
        peak_to_peak_m_s2=maximum-minimum,
        crest_ac=(ac_peak/ac_rms if ac_rms>0 else None),
    )


def time_plot_extrema(
    samples: np.ndarray, fs: int, *, max_points: int = 5002,
) -> tuple[np.ndarray,np.ndarray]:
    """Rendering only: min and max retain their REAL sample timestamps.

    The previous renderer placed every minimum at the start of its bucket
    and every maximum at its end, inventing the temporal order of impulses.
    Here positions are taken from argmin/argmax indices and sorted before
    plotting. Include real first/last samples; do not interpolate or pad.
    Analysis and cursors must continue to use the full original samples.
    """
    data=np.asarray(samples,dtype=np.float64)
    if (data.ndim!=1 or data.size==0 or not np.all(np.isfinite(data)) or
            type(fs) is not int or fs<=0 or
            type(max_points) is not int or max_points<10):
        raise ValueError("Invalid physical time plot source")
    n=int(data.size)
    if n<=max_points:
        ix=np.arange(n,dtype=np.int64)
    else:
        step=int(math.ceil(n / ((max_points-2)//2)))
        candidates=[0]
        for start in range(0,n,step):
            segment=data[start:min(start+step,n)]
            imin=start+int(np.argmin(segment))
            imax=start+int(np.argmax(segment))
            if imin==imax:
                candidates.append(imin)
            elif imin<imax:
                candidates.extend((imin,imax))
            else:
                candidates.extend((imax,imin))
        candidates.append(n-1)
        ix=np.unique(np.asarray(candidates,dtype=np.int64))
    # Same time convention as the existing tested time_point/time_interval:
    # newest physical sample is -1/Fs, zero is the end boundary of the block.
    return (ix.astype(np.float64)-n)/fs, data[ix].copy()


def display_time_stats(x: np.ndarray,fs:int) -> tuple[float,float,float]:
    """Back-compatible: AC RMS (DC removed), raw abs peak and raw p-p."""
    m=summarize_time_window(x,fs)
    return m.rms_ac_m_s2,m.absolute_peak_m_s2,m.peak_to_peak_m_s2
