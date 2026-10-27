"""MVK01 P1.2-P1.4 offline spectral pipeline; NOT an exact factory DSP clone.
Uses pre-existing p14_two_spectrum; all proprietary windows/taps explicit.
Input acceleration must already be calibrated in m/s2.
"""
from dataclasses import dataclass
import numpy as np
from scipy.signal import resample_poly,periodogram
from p14_two_spectrum import third_octave_power,fixed_band_power

@dataclass(frozen=True)
class Spectrum:
    frequency_hz: np.ndarray
    acceleration_psd: np.ndarray
    fs_hz: float
    n_samples: int

def decimate_fir(x,factor,taps):
    x=np.asarray(x,dtype=float);t=np.asarray(taps,dtype=float)
    if x.ndim!=1 or x.size<4 or not np.isfinite(x).all():raise ValueError('Input must be finite 1D')
    if not isinstance(factor,int) or factor<1:raise ValueError('Invalid integer factor')
    if factor==1:return x.copy()
    if t.ndim!=1 or t.size<3 or t.size%2!=1 or not np.isfinite(t).all():
        raise ValueError('Explicit odd FIR taps required')
    if not np.isclose(t.sum(),1.,rtol=1e-3,atol=1e-5):raise ValueError('Invalid DC gain')
    return resample_poly(x,1,factor,window=t,padtype='constant')

def p12_hann_psd(acceleration,fs_hz):
    x=np.asarray(acceleration,dtype=float)
    if x.ndim!=1 or x.size<8 or not np.isfinite(x).all() or fs_hz<=0:
        raise ValueError('Invalid waveform')
    f,p=periodogram(x,fs=fs_hz,window='hann',detrend='constant',scaling='density')
    return Spectrum(f,p,float(fs_hz),x.size)

def p13_three_quantities(spectrum,centers_hz,accel_windows,velocity_windows,displacement_windows):
    """Velocity and displacement AMPLITUDE windows include 1/(2*pi*f) factors.
    Resulting powers have units (m/s)^2 and m^2 respectively.
    """
    args=(spectrum.frequency_hz,spectrum.acceleration_psd,centers_hz)
    return {
        'acceleration_m_s2':third_octave_power(*args,accel_windows),
        'velocity_m_s':third_octave_power(*args,velocity_windows),
        'displacement_m':third_octave_power(*args,displacement_windows)
    }

def p14_from_two_spectra(high_resolution,octaves,lower_amplitude_weights,upper_power_weights,interior_mask):
    return fixed_band_power(high_resolution.frequency_hz,high_resolution.acceleration_psd,
                            lower_amplitude_weights,octaves,upper_power_weights,interior_mask)

def reference_octave_windows(frequency_hz,centers_hz,kind='acceleration'):
    """Rectangular windows FOR DIAGNOSTIC TESTS ONLY, not certified GOST class 2."""
    f=np.asarray(frequency_hz,dtype=float);c=np.asarray(centers_hz,dtype=float)
    if kind not in ('acceleration','velocity','displacement'):raise ValueError('Unknown kind')
    w=((f[None,:]>=c[:,None]*2**(-1/6)) &
       (f[None,:]<c[:,None]*2**(1/6))).astype(float)
    if kind!='acceleration':
        with np.errstate(divide='ignore',invalid='ignore'):
            gain=np.divide(1.,2*np.pi*f,out=np.zeros_like(f),where=f>0)
        if kind=='displacement':gain=gain*gain
        w=w*gain
    return w
