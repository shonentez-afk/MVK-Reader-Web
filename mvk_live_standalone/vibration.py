"""Vibration-specific analysis, not an audio level meter.

Design informed by enDAQ's PSD/integration/one-third-octave pipeline and
CWRU bearing-envelope analysis. This is independent, new code; no copying.

Only verified, calibrated acceleration Float32 from Native R6.1 is accepted.
APP_DERIVED outputs must never overwrite the device's original AUX4700 DSP.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

import numpy as np
from scipy import signal

from .spectrum import KINDS, Spectrum, calculate_spectrum, db_reference

Mode = Literal["fft", "welch", "asd", "third_octave", "envelope"]
OCTAVE_CENTERS = np.asarray((
    0.63,0.8,1.0,1.25,1.6,2.0,2.5,3.15,4,5,6.3,8,10,12.5,
    16,20,25,31.5,40,50,63,80,100,125,160,200,250,315,
    400,500,630,800,1000,1250,1600,2000,2500,3150,4000,
    5000,6300,8000,10000),dtype=np.float64
)


@dataclass(frozen=True)
class VibrationView:
    hz: np.ndarray
    rms: np.ndarray  # for Welch this field holds PSD, NOT RMS!
    kind: str
    units: str
    rate_hz: int
    nfft: int
    mode: Mode
    waveform: np.ndarray
    segments: int
    resolution_hz: float
    floor_hz: float

    @property
    def peak(self) -> tuple[float,float]:
        mask=(self.hz>0) & np.isfinite(self.rms)
        if not mask.any():
            return (float("nan"),float("nan"))
        ids=np.flatnonzero(mask)
        i=ids[int(np.argmax(self.rms[mask]))]
        return float(self.hz[i]),float(self.rms[i])


@dataclass(frozen=True)
class VibrationFeatures:
    acceleration_rms: float
    acceleration_peak: float
    acceleration_crest_factor: float
    acceleration_kurtosis: float
    sample_count: int
    rate_hz: int


def time_features(samples: np.ndarray, fs: int) -> VibrationFeatures:
    x=np.asarray(samples,dtype=np.float64)
    if x.ndim!=1 or x.size<4 or not np.all(np.isfinite(x)) or fs<=0:
        raise ValueError("Need real, finite calibrated acceleration samples")
    x=x-x.mean()
    rms=float(np.sqrt(np.mean(np.square(x))))
    peak=float(np.max(np.abs(x)))
    kurt=float(np.mean(x**4)/np.mean(x*x)**2) if rms>0 else 0.0
    return VibrationFeatures(rms,peak,peak/rms if rms>0 else 0.0,kurt,len(x),fs)


def _checked_input(x: np.ndarray, fs: int, nfft: int) -> np.ndarray:
    signal_data=np.asarray(x,dtype=np.float64)
    if (type(fs) is not int or fs<2 or type(nfft) is not int
        or nfft<256 or (nfft & (nfft-1)) != 0
        or signal_data.ndim!=1 or signal_data.size<nfft
        or signal_data.size>2**21 or not np.isfinite(signal_data).all()):
        raise ValueError("Need real contiguous calibrated acceleration and power-of-two FFT")
    return signal_data


def _conversion(frequencies: np.ndarray, kind: str) -> np.ndarray:
    if kind not in KINDS:
        raise ValueError("Unknown vibration quantity")
    mult=np.ones_like(frequencies,dtype=np.float64)
    if kind=="acceleration":
        return mult
    omega=2*np.pi*frequencies
    mult[0]=0.0
    if kind=="velocity":
        mult[1:]=1e3/omega[1:]  # m/s => mm/s
    else:
        mult[1:]=1e6/(omega[1:]**2)  # m => micrometers
    return mult


def _welch_acceleration(x: np.ndarray, fs: int, nfft: int):
    # Density is acceleration²/Hz; integrate PSD*df for true broadband RMS².
    nseg=len(x)//nfft
    f,p=signal.welch(x,fs=fs,window="hann",
                     nperseg=nfft,noverlap=nfft//2,detrend="constant",
                     scaling="density",return_onesided=True)
    p=np.maximum(np.asarray(p,dtype=np.float64),0)
    p[0]=0
    return f,p,max(1,2*nseg-1)


def _precondition(x: np.ndarray,fs: int,kind: str,band: tuple[float,float|None]) -> tuple[np.ndarray,float]:
    low,high=band
    if low<0 or not np.isfinite(low) or (high is not None and (not np.isfinite(high) or high<=low)):
        raise ValueError("Invalid physical filter cutoff")
    # Integration below 2 Hz can strongly magnify drift and calibration DC.
    # Clearly record this local high-pass; DO NOT claim it is the MVK DSP path.
    effective_low=max(float(low),2.0) if kind!="acceleration" else float(low)
    if effective_low>=fs/2:
        raise ValueError("High-pass cutoff beyond Nyquist")
    if high is not None and high>=fs/2:
        raise ValueError("Low-pass cutoff beyond Nyquist")
    data=x-x.mean()
    if effective_low>0 and high is not None:
        sos=signal.butter(4,[effective_low,float(high)],btype="bandpass",fs=fs,output="sos")
    elif effective_low>0:
        sos=signal.butter(4,effective_low,btype="highpass",fs=fs,output="sos")
    elif high is not None:
        sos=signal.butter(4,float(high),btype="lowpass",fs=fs,output="sos")
    else:
        return data,effective_low
    return signal.sosfiltfilt(sos,data),effective_low


def analyze_vibration(
    calibrated_acceleration: np.ndarray,
    fs: int,
    *,
    kind: str="acceleration",
    mode: Mode="fft",
    nfft: int=32768,
    band_hz: tuple[float,float|None]=(0.0,None),
    envelope_band_hz: tuple[float,float]=(1000.0,3000.0),
    smooth_bins: int=1,
    notch_hz: float|None=None,
) -> VibrationView:
    x=_checked_input(calibrated_acceleration,fs,nfft)
    if notch_hz is not None:
        if not np.isfinite(notch_hz) or not 0<notch_hz<fs/2:
            raise ValueError("Notch must be within the physical Nyquist range")
        # Explicit ONLY; for rotating machinery 50/60 Hz may be a genuine
        # fault harmonic. Never enable this automatically.
        b,a=signal.iirnotch(notch_hz,Q=35,fs=fs)
        x=signal.filtfilt(b,a,x)
    if kind not in KINDS or mode not in ("fft","welch","asd","third_octave","envelope"):
        raise ValueError("Unknown vibration analysis mode")
    if mode=="envelope" and kind!="acceleration":
        raise ValueError("Bearing envelope uses acceleration units only; select VU")
    if mode=="fft":
        # Existing physically validated one-sided line RMS; no second gain.
        result: Spectrum=calculate_spectrum(x,fs,kind=kind,nfft=nfft,band_hz=band_hz,smooth_bins=smooth_bins)
        return VibrationView(result.hz,result.rms,kind,result.units,fs,nfft,mode,
                             result.waveform,1,float(fs/nfft),0.0)
    if mode=="envelope":
        low,high=envelope_band_hz
        if not (0<low<high<fs/2):
            raise ValueError("Envelope resonance band must be below Nyquist")
        # CWRU: resonance band -> analytic Hilbert envelope -> subtract DC ->
        # one-sided RMS FFT. This spectrum's unit is m/s², not native DSP.
        sos=signal.butter(4,[low,high],btype="bandpass",fs=fs,output="sos")
        filtered=signal.sosfiltfilt(sos,x)
        analytic=np.abs(signal.hilbert(filtered))
        demodulated=analytic-analytic.mean()
        p=calculate_spectrum(demodulated[-nfft:],fs,kind="acceleration",nfft=nfft)
        return VibrationView(p.hz,p.rms,"acceleration","м/с²",fs,nfft,mode,
                             demodulated,1,float(fs/nfft),0.0)

    conditioned,effective_low=_precondition(x,fs,kind,band_hz)
    f,psd,segments=_welch_acceleration(conditioned,fs,nfft)
    converted=psd*_conversion(f,kind)**2
    converted[f<effective_low]=0
    if mode=="welch":
        # Units are squared per hertz and MUST NOT be labeled as RMS.
        return VibrationView(f,converted,kind,f"({KINDS[kind][1]})²/Гц",
                             fs,nfft,mode,conditioned,segments,float(fs/nfft),effective_low)
    if mode=="asd":
        # ASD is the square root of Welch PSD, (physical unit)/sqrt(Hz).
        # It is amplitude spectral density, never FFT line RMS or DSP.
        return VibrationView(f,np.sqrt(converted),kind,
                             f"{KINDS[kind][1]}/√Гц",fs,nfft,mode,
                             conditioned,segments,float(fs/nfft),effective_low)
    # Fractional octave power summation (enDAQ): integrate density over
    # frequency; reject bands with insufficient resolution/coverage.
    # 2**(+/-1/6) gives one-third-octave edges for exact binary octaves.
    df=fs/nfft
    bands=np.full(OCTAVE_CENTERS.shape,np.nan,dtype=np.float64)
    nyquist=fs/2
    for i,center in enumerate(OCTAVE_CENTERS):
        lo=center*(2.0**(-1/6))
        hi=center*(2.0**(+1/6))
        if lo<max(effective_low,df) or hi>=nyquist or (hi-lo)<2*df:
            continue
        valid=(f>=lo)&(f<hi)
        if valid.sum()<2:
            continue  # unavailable, not a fake 0 band
        bands[i]=float(np.sqrt(np.sum(converted[valid])*df))
    return VibrationView(OCTAVE_CENTERS.copy(),bands,kind,KINDS[kind][1],
                         fs,nfft,mode,conditioned,segments,df,effective_low)


def vibration_y_label(view: VibrationView, scale: str, reference: str="iso") -> str:
    label={"fft":"FFT","welch":"PSD Уэлча","asd":"ASD Уэлча","third_octave":"1/3 октавы",
           "envelope":"Спектр огибающей"}[view.mode]
    if scale=="linear":
        return f"{label} · {KINDS[view.kind][0]}, {view.units}"
    if scale not in ("db","log"):
        raise ValueError("Invalid vertical scale")
    ref=db_reference(view.kind,reference)
    if view.mode=="welch":
        return f"{label} · дБ отн. ({ref:g} {KINDS[view.kind][1]})²/Гц"
    if view.mode=="asd":
        return f"{label} · дБ отн. {ref:g} {KINDS[view.kind][1]}/√Гц"
    return f"{label} · дБ отн. {ref:g} {KINDS[view.kind][1]} СКЗ"


def vibration_plot_values(view: VibrationView, scale: str, reference: str="iso",
                          floor_db: float=-180.0) -> np.ndarray:
    y=view.rms.copy()
    if scale=="linear":
        return y
    if scale not in ("db","log") or floor_db>=0 or not np.isfinite(floor_db):
        raise ValueError("Invalid dB mode")
    ref=db_reference(view.kind,reference)
    if view.mode=="welch":
        reff=ref**2  # relative PSD must be 10 log10, NOT 20 log10
        floor=reff * 10**(floor_db/10)
        return 10*np.log10(np.maximum(y,floor)/reff)
    floor=ref*10**(floor_db/20)
    return 20*np.log10(np.maximum(y,floor)/ref)


def bearing_frequency_markers(
    rpm: float, *, balls: int|None=None,ball_diameter_mm: float|None=None,
    pitch_diameter_mm: float|None=None,contact_angle_deg: float=0.0
) -> dict[str,float]:
    # RPM may be entered by the operator; never claim TACH proof without a
    # confirmed TACH decoder and physical pulses/revolution calibration.
    if not np.isfinite(rpm) or rpm<=0 or rpm>200000:
        raise ValueError("RPM must be a positive, explicitly provided measurement")
    fr=rpm/60
    result={f"{i}X":fr*i for i in (1,2,3,4,5)}
    if balls is None and ball_diameter_mm is None and pitch_diameter_mm is None:
        return result
    if (type(balls) is not int or not 3<=balls<=80
        or ball_diameter_mm is None or pitch_diameter_mm is None
        or not np.isfinite(ball_diameter_mm) or not np.isfinite(pitch_diameter_mm)
        or not 0<ball_diameter_mm<pitch_diameter_mm
        or not 0<=contact_angle_deg<=90):
        raise ValueError("Incomplete/invalid physical bearing geometry")
    factor=(ball_diameter_mm/pitch_diameter_mm)*math.cos(math.radians(contact_angle_deg))
    result["BPFO"]=balls/2*fr*(1-factor)
    result["BPFI"]=balls/2*fr*(1+factor)
    result["BSF"]=pitch_diameter_mm/(2*ball_diameter_mm)*fr*(1-factor*factor)
    result["FTF"]=fr/2*(1-factor)
    return result
