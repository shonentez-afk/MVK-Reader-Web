"""Independent time-waveform controls for verified MVK01 acceleration samples.

Time X is seconds, using SI formatting for milliseconds at small windows.
Time Y is signed acceleration in m/s² (not spectral RMS or AUX4700 DSP).
Optional local filter is distinct from the spectral filter and never touches
the native Go ring, calibrated BIN/IPC bytes or device FRange.
"""
from __future__ import annotations

import math
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


def display_time_stats(x: np.ndarray,fs:int) -> tuple[float,float,float]:
    """RMS of time-window acceleration, absolute peak and true max-min."""
    data=np.asarray(x,dtype=np.float64)
    if data.ndim!=1 or data.size<2 or not np.all(np.isfinite(data)) or fs<=0:
        raise ValueError("No real time series for local statistics")
    centered=data-data.mean()
    return (float(np.sqrt(np.mean(centered**2))),
            float(np.max(np.abs(data))),
            float(np.max(data)-np.min(data)))
