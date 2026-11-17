"""Additional mechanical-vibration diagnostics (no TACH and no reference corpus).

Algorithms inspired by enDAQ, CWRU Bearing Analysis and viblearn. All
features are APP_DERIVED engineering aids. No historical reference/benchmark,
instrument DSP substitution or automatic fault verdict is provided.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy import signal

from .vibration import VibrationView, analyze_vibration, bearing_frequency_markers


@dataclass(frozen=True)
class ExtendedFeatures:
    rms_m_s2: float
    peak_m_s2: float
    peak_to_peak_m_s2: float
    crest_factor: float
    kurtosis_pearson: float
    skewness: float
    impulse_factor: float
    shape_factor: float
    clearance_factor: float
    sample_count: int


def extended_time_features(samples: np.ndarray) -> ExtendedFeatures:
    x=np.asarray(samples,dtype=np.float64)
    if x.ndim!=1 or x.size<16 or not np.isfinite(x).all():
        raise ValueError("Expected finite calibrated acceleration samples")
    x=x-np.mean(x)
    rms=float(np.sqrt(np.mean(x*x)))
    peak=float(np.max(abs(x)))
    mean_abs=float(np.mean(abs(x)))
    absroot=float(np.mean(np.sqrt(abs(x))))
    kurt=float(np.mean(x**4)/(rms**4)) if rms>0 else 0.0
    skew=float(np.mean(x**3)/(rms**3)) if rms>0 else 0.0
    return ExtendedFeatures(
        rms_m_s2=rms,peak_m_s2=peak,
        peak_to_peak_m_s2=float(np.ptp(x)),
        crest_factor=peak/rms if rms else 0.0,
        kurtosis_pearson=kurt,skewness=skew,
        impulse_factor=peak/mean_abs if mean_abs else 0.0,
        shape_factor=rms/mean_abs if mean_abs else 0.0,
        clearance_factor=peak/(absroot**2) if absroot else 0.0,
        sample_count=len(x),
    )


@dataclass(frozen=True)
class BandRMS:
    low_hz: float
    high_hz: float
    rms: float
    unit: str
    valid: bool


def broadband_rms(
    calibrated_acceleration: np.ndarray, fs: int, *,
    kind: str = "velocity", band_hz: tuple[float,float] = (10.0,1000.0),
    nfft: int = 8192,
) -> BandRMS:
    low,high=band_hz
    if not (np.isfinite(low) and np.isfinite(high) and 0<=low<high<fs/2):
        raise ValueError("Band must be entirely below Nyquist")
    view=analyze_vibration(calibrated_acceleration,fs,mode="welch",
                           kind=kind,nfft=nfft,band_hz=(0.0,None))
    df=view.resolution_hz
    valid=(view.hz>=low)&(view.hz<=high)
    if np.count_nonzero(valid)<3:
        return BandRMS(low,high,float("nan"),view.units.replace("²/Гц",""),False)
    variance=float(np.sum(np.maximum(view.rms[valid],0.0))*df)
    unit={"acceleration":"м/с²","velocity":"мм/с","displacement":"мкм"}[kind]
    return BandRMS(low,high,math.sqrt(max(variance,0.0)),unit,True)


@dataclass(frozen=True)
class DemodulationBand:
    low_hz: float
    high_hz: float
    envelope_kurtosis: float
    tested_bands: int
    confidence: str
    method: str="KURTOGRAM_LIKE_ENVELOPE_KURTOSIS_FILTER_BANK"


def select_envelope_band(
    acceleration: np.ndarray, fs: int, *, min_hz: float=300.0,
    max_level: int=4,
) -> DemodulationBand:
    """Dyadic bandpass search by Hilbert-envelope kurtosis.

    A bounded filter-bank kurtogram approximation, NOT Antoni's complete
    Fast Kurtogram or a reference-calibrated defect detector. Restrict search
    away from DC and Nyquist, keeping the resonance above fault orders.
    """
    x=np.asarray(acceleration,dtype=np.float64)
    if (type(fs) is not int or fs<2048 or x.ndim!=1
        or x.size<4096 or not np.isfinite(x).all()
        or type(max_level) is not int or max_level<1 or max_level>5):
        raise ValueError("Need finite high-rate accelerometer samples")
    x=x[-min(len(x),32768):]
    nyq=fs/2
    hi_limit=.86*nyq
    low_limit=max(80.0,float(min_hz))
    if low_limit>=hi_limit:
        raise ValueError("No resonance search area below Nyquist")
    best=None
    count=0
    for level in range(1,max_level+1):
        bandwidth=nyq/(2**level)
        for band_num in range(2**level):
            low=band_num*bandwidth
            high=(band_num+1)*bandwidth
            if low<low_limit or high>hi_limit or (high-low)<max(80.0,fs/len(x)*8):
                continue
            sos=signal.butter(4,[low,high],btype="bandpass",fs=fs,output="sos")
            conditioned=signal.sosfiltfilt(sos,x)
            env=np.abs(signal.hilbert(conditioned))
            centered=env-np.mean(env)
            variance=float(np.mean(centered**2))
            if variance<=1e-24:
                continue
            score=float(np.mean(centered**4)/(variance**2))
            if not np.isfinite(score):continue
            count+=1
            if best is None or score>best[0]:
                best=(score,float(low),float(high))
    if best is None:
        raise ValueError("No valid bearing resonance band in current Fs")
    confidence=("выраженная импульсность" if best[0]>=6 else
                "умеренная импульсность" if best[0]>=4 else
                "низкая: максимум может быть шумом")
    return DemodulationBand(best[1],best[2],best[0],count,confidence)


@dataclass(frozen=True)
class FaultLine:
    label: str
    expected_hz: float
    measured_hz: float
    amplitude: float
    snr_db: float
    harmonics_found: int
    noteworthy: bool


def envelope_fault_lines(
    envelope: VibrationView, rpm: float, *,
    balls: int, ball_diameter_mm: float,
    pitch_diameter_mm: float, contact_angle_deg: float=0.0,
    harmonic_limit: int=4,
) -> list[FaultLine]:
    """Detect spectral peaks close to theoretical orders; never pronounce faults.

    Uses SAME recording's neighbouring noise floor, not an external reference.
    Requires operator-supplied RPM and bearing geometry. No TACH data.
    """
    if envelope.mode!="envelope" or envelope.kind!="acceleration":
        raise ValueError("Only an actual envelope RMS spectrum is supported")
    markers=bearing_frequency_markers(
        rpm,balls=balls,ball_diameter_mm=ball_diameter_mm,
        pitch_diameter_mm=pitch_diameter_mm,
        contact_angle_deg=contact_angle_deg)
    f=envelope.hz
    y=envelope.rms
    df=envelope.resolution_hz
    result=[]
    for name in ("BPFO","BPFI","BSF","FTF"):
        nominal=markers[name]
        checked=[]
        for n in range(1,harmonic_limit+1):
            target=n*nominal
            if target<=0 or target>=f[-1]*.97:
                break
            tolerance=max(1.8*df,target*.012)
            near=(f>=target-tolerance)&(f<=target+tolerance)
            adjacent=(f>=target-max(10*df,target*.12)) & (
                f<=target+max(10*df,target*.12)) & (~near)
            if not np.any(near) or np.count_nonzero(adjacent)<4:
                continue
            ix=np.flatnonzero(near)[int(np.argmax(y[near]))]
            amp=float(y[ix])
            floor=max(float(np.median(y[adjacent])),1e-20)
            snr=20*math.log10(max(amp/floor,1e-20))
            checked.append((n,float(f[ix]),amp,snr))
        if checked:
            # The diagnostic threshold is a *local* signal/noise ratio, not
            # a machine health threshold or a fault classification.
            good=[c for c in checked if c[3]>=6.0]
            best=max(checked,key=lambda v:v[3])
            result.append(FaultLine(
                name,nominal,best[1],best[2],best[3],len(good),
                noteworthy=bool(good),
            ))
    return result


@dataclass(frozen=True)
class TimeFrequencyView:
    time_s: np.ndarray
    frequency_hz: np.ndarray
    magnitude: np.ndarray
    description: str
    calibrated_amplitude: bool


def stft_vibration(acceleration: np.ndarray, fs: int, *,
                   max_frequency_hz: float|None=None,
                   nperseg: int=1024) -> TimeFrequencyView:
    """STFT spectrogram from raw *calibrated acceleration*, not audio."""
    x=np.asarray(acceleration,dtype=np.float64)
    if (x.ndim!=1 or x.size<nperseg or not np.isfinite(x).all() or
        type(fs) is not int or fs<2 or type(nperseg) is not int or
        nperseg<256 or nperseg>4096 or nperseg>len(x)):
        raise ValueError("Invalid STFT window or sampling")
    x=x[-min(len(x),32768):]
    freq,t,z=signal.stft(x-x.mean(),fs=fs,window="hann",
               nperseg=nperseg,noverlap=nperseg*3//4,
               boundary=None,padded=False,scaling="spectrum")
    limit=min(float(max_frequency_hz) if max_frequency_hz else fs/2,fs/2)
    selected=np.flatnonzero((freq>=0)&(freq<=limit))
    if selected.size==0:raise ValueError("STFT frequency band empty")
    freq_ix=selected[np.linspace(0,len(selected)-1,min(256,len(selected)),dtype=int)]
    time_ix=np.linspace(0,len(t)-1,min(128,len(t)),dtype=int)
    # Single-sided sinusoidal RMS, approximate per-window for visualization.
    amplitudes=np.abs(z[np.ix_(freq_ix,time_ix)])*np.sqrt(2.0)
    return TimeFrequencyView(t[time_ix],freq[freq_ix],amplitudes,
                             "STFT · ВУ, м/с² амплитуда RMS/окно",True)


def cwt_morlet_vibration(acceleration: np.ndarray, fs: int, *,
                         min_frequency_hz: float=10.0,
                         max_frequency_hz: float|None=None,
                         scales: int=40) -> TimeFrequencyView:
    """Bounded complex Morlet scalogram; normalized, QUALITATIVE amplitude.

    This cannot replace the calibrated FFT/PSD; report only relative power.
    """
    x=np.asarray(acceleration,dtype=np.float64)
    high=min(fs*.4,float(max_frequency_hz) if max_frequency_hz else fs*.4)
    if (x.ndim!=1 or x.size<1024 or not np.isfinite(x).all()
        or type(fs) is not int or fs<100 or
        not 2.0<=min_frequency_hz<high or type(scales) is not int
        or not 8<=scales<=64):
        raise ValueError("Invalid bounded CWT settings")
    x=x[-min(len(x),8192):]
    freqs=np.geomspace(float(min_frequency_hz),high,scales)
    # Downsample for interactive Qt usage, with no implicit interpolation.
    columns=np.linspace(0,len(x)-1,min(256,len(x)),dtype=int)
    mat=np.empty((scales,len(columns)),dtype=np.float32)
    for row,f in enumerate(freqs):
        sigma=5/(2*math.pi*f)
        half=min(int(4*sigma*fs),len(x)//2)
        if half<4:half=4
        t=np.arange(-half,half+1,dtype=np.float64)/fs
        wave=np.exp(2j*math.pi*f*t)*np.exp(-.5*(t/sigma)**2)
        wave/=np.sqrt(np.sum(abs(wave)**2))
        response=signal.fftconvolve(x-x.mean(),np.conjugate(wave[::-1]),mode="same")
        mat[row]=np.abs(response[columns])
    return TimeFrequencyView(columns/fs,freqs,mat,
                             "CWT Morlet · качественная относительная амплитуда",False)


@dataclass(frozen=True)
class CepstrumView:
    quefrency_s: np.ndarray
    magnitude: np.ndarray
    description: str="Вещественный кепстр · лог-спектр; ось X: кэфренция, с"


def real_cepstrum(acceleration: np.ndarray, fs: int, *,
                  max_quefrency_s: float=.2) -> CepstrumView:
    x=np.asarray(acceleration,dtype=float)
    if (x.ndim!=1 or len(x)<1024 or not np.isfinite(x).all() or
        type(fs) is not int or fs<2 or not 0<max_quefrency_s<=2):
        raise ValueError("Invalid cepstrum input")
    x=x[-min(len(x),32768):]
    spectrum=np.fft.rfft((x-x.mean())*np.hanning(len(x)))
    # Relative, unitless real cepstrum. Avoid log(0) without fake peaks.
    logmag=np.log(np.maximum(np.abs(spectrum),1e-15))
    cep=np.fft.irfft(logmag,n=len(x))
    times=np.arange(len(x)//2)/fs
    keep=(times>=1/fs)&(times<=max_quefrency_s)
    return CepstrumView(times[keep],cep[:len(times)][keep])



@dataclass(frozen=True)
class GearMeshMarkers:
    mesh_hz: float
    harmonics_hz: tuple[float, ...]
    sidebands_hz: tuple[float, ...]
    source: str = "OPERATOR_RPM_AND_GEAR_TEETH_NO_TACH"


def gear_mesh_markers(rpm: float, teeth: int, *, harmonics: int=3,
                      sideband_orders: int=3) -> GearMeshMarkers:
    """Gear-mesh hypothesis from operator's/manual-confirmed 1× and teeth."""
    if (not np.isfinite(rpm) or not 0<rpm<=200000
        or type(teeth) is not int or not 4<=teeth<=400
        or type(harmonics) is not int or not 1<=harmonics<=6
        or type(sideband_orders) is not int or not 1<=sideband_orders<=6):
        raise ValueError("Requires explicitly provided RPM and gear tooth count")
    fr=rpm/60.0
    mesh=fr*teeth
    bands=tuple(sorted([
        freq for order in range(1,sideband_orders+1)
        for freq in (mesh-order*fr,mesh+order*fr)
        if freq>0
    ]))
    return GearMeshMarkers(mesh,tuple(mesh*i for i in range(1,harmonics+1)),bands)


@dataclass(frozen=True)
class InformativeSeverity:
    zone: str
    velocity_rms_mm_s: float
    machine_class: int
    limits_mm_s: tuple[float,float,float]
    source: str = "HISTORICAL_ISO_10816_3_INDICATIVE_NOT_CERTIFIED"


def indicative_iso10816_zone(
    velocity_rms_mm_s: float, *,
    machine_class: int,
    rpm: float,
    measured_band_hz: tuple[float,float] = (10.0,1000.0),
) -> InformativeSeverity:
    """Historical ISO 10816-3 chart, USER-OPT-IN and explicitly informative.

    Not a reference measurement and NOT an ISO 20816 conformity statement.
    Applicability of machine group, power, support and measuring positions
    must be checked by a specialist before any real condition assessment.
    """
    if type(machine_class) is not int or machine_class not in (1,2,3,4):
        raise ValueError("Machine class must be selected by operator")
    if not np.isfinite(rpm) or not 120<=rpm<=15000:
        raise ValueError("Historical ISO chart limited to 120..15000 RPM")
    if (not np.isfinite(velocity_rms_mm_s) or velocity_rms_mm_s<0
        or len(measured_band_hz)!=2 or
        measured_band_hz[0]>10.0 or measured_band_hz[1]<1000.0):
        raise ValueError("Full measured velocity RMS in 10..1000 Hz is required")
    limits={
        1:(2.3,4.5,7.1),
        2:(3.5,7.1,11.0),
        3:(3.5,7.1,11.0),
        4:(7.1,11.0,18.0),
    }[machine_class]
    zone="A"
    for limit,new_zone in zip(limits,("B","C","D")):
        if velocity_rms_mm_s>=limit:zone=new_zone
    return InformativeSeverity(zone,velocity_rms_mm_s,machine_class,limits)
