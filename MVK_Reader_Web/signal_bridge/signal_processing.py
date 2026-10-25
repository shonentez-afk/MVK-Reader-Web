"""Offline DSP for calibrated acceleration samples. No device connections.
Input SI: acceleration m/s^2. Velocity mm/s; displacement micrometres.
"""
from dataclasses import dataclass
import numpy as np
from scipy.signal import butter, sosfiltfilt, welch

@dataclass(frozen=True)
class FilterConfig:
    kind: str='none'
    low_hz: float=1.0
    high_hz: float=1000.0
    order: int=4

def filter_acceleration(signal, fs, cfg=FilterConfig()):
    x=np.asarray(signal,dtype=np.float64)
    if x.ndim!=1 or not np.isfinite(x).all():raise ValueError('Expected finite 1-D samples')
    if fs<=0:raise ValueError('Sample rate must be positive')
    if cfg.kind=='none':return x.copy()
    if cfg.order<1 or cfg.order>12:raise ValueError('Invalid filter order')
    nyq=fs/2
    if cfg.kind=='bandpass':
        if not 0<cfg.low_hz<cfg.high_hz<nyq:raise ValueError('Invalid bandpass bounds')
        cutoff=[cfg.low_hz,cfg.high_hz]
    elif cfg.kind=='highpass':
        if not 0<cfg.low_hz<nyq:raise ValueError('Invalid highpass cutoff')
        cutoff=cfg.low_hz
    elif cfg.kind=='lowpass':
        if not 0<cfg.high_hz<nyq:raise ValueError('Invalid lowpass cutoff')
        cutoff=cfg.high_hz
    else:raise ValueError('Unknown filter kind')
    sos=butter(cfg.order,cutoff,btype=cfg.kind,fs=fs,output='sos')
    return sosfiltfilt(sos,x)

def time_stats(x):
    x=np.asarray(x,dtype=np.float64)
    if x.size<1 or not np.all(np.isfinite(x)):raise ValueError('No finite samples')
    dc=float(np.mean(x)); ac=x-dc
    rms=float(np.sqrt(np.mean(ac**2)))
    peak=float(np.max(np.abs(ac)))
    return {'mean':dc,'rms_ac':rms,'peak_abs_ac':peak,'peak_to_peak':float(np.ptp(ac)),
            'crest_factor':float(peak/rms) if rms else None}

def spectra(acc, fs, nperseg=65536, overlap=0.5, window='hann', fmin=1., fmax=1000.):
    acc=np.asarray(acc,dtype=np.float64)
    if acc.ndim!=1 or not np.isfinite(acc).all():raise ValueError('Expected finite 1-D input')
    if nperseg<256 or nperseg>acc.size:raise ValueError('Invalid window length')
    if not 0<=overlap<1:raise ValueError('Invalid overlap')
    if not 0<fmin<fmax<=fs/2:raise ValueError('Invalid frequency band')
    f, pa=welch(acc,fs=fs,window=window,nperseg=nperseg,
                 noverlap=int(nperseg*overlap),detrend='constant',scaling='density')
    gain=np.zeros_like(f)
    gain[1:]=1000/(2*np.pi*f[1:])
    pv=pa*gain**2  # velocity mm/s
    pd=pa*(gain/(2*np.pi*np.maximum(f,1e-300))*1000)**2  # displacement um
    pv[0]=0;pd[0]=0
    band=(f>=fmin)&(f<=fmax)
    df=fs/nperseg
    def band_rms(p):return float(np.sqrt(np.sum(p[band])*df))
    return {'frequencies_hz':f,'accel_psd':pa,'velocity_psd':pv,'displacement_psd':pd,
      'velocity_band_rms_mm_s':band_rms(pv),'accel_band_rms_m_s2':band_rms(pa),
      'displacement_band_rms_um':band_rms(pd),'df_hz':df,
      'note':'Welch power density; RMS bin amplitudes are not coherent-tone amplitude estimates.'}

def apply_gain(raw, gain):
    if gain is None or not np.isfinite(gain) or gain<=0:raise ValueError('Channel calibration gain required')
    return np.asarray(raw,dtype=np.float64)*gain
