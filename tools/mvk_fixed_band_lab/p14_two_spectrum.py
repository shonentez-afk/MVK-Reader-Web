"""Offline MVK01 P1.3/P1.4 structural reconstruction. Not factory-calibrated.

All input powers are in (m/s2)^2. Exported BIN is already in physical units.
Unknown window coefficients are required as explicit inputs.
"""
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class ThirdOctavePower:
    centers_hz: np.ndarray
    acceleration_power: np.ndarray

def third_octave_power(freq_hz, acceleration_psd, centers_hz, window_amplitudes):
    """Compute 1/3-octave power via individually supplied AMPLITUDE windows.

    p_j=sum_k PSD(f_k)*df*window_j(f_k)^2.
    Vendor windows must be provided; rectangular bands are NOT assumed.
    """
    f=np.asarray(freq_hz, dtype=float)
    psd=np.asarray(acceleration_psd, dtype=float)
    c=np.asarray(centers_hz, dtype=float)
    a=np.asarray(window_amplitudes, dtype=float)
    if f.ndim!=1 or len(f)<2 or psd.shape!=f.shape:
        raise ValueError("Invalid PSD grid")
    if a.shape!=(len(c),len(f)):
        raise ValueError("Window matrix must be bands x frequencies")
    if not np.all(np.isfinite(a)) or np.any(a<0):
        raise ValueError("Invalid band amplitude windows")
    if not np.all(np.isfinite(psd)) or np.any(psd<0):
        raise ValueError("Invalid PSD")
    delta=np.diff(f)
    if not np.allclose(delta,delta[0]):
        raise ValueError("Uniform FFT grid required")
    return ThirdOctavePower(c, np.sum((a*a)*psd[None,:],axis=1)*delta[0])

def fixed_band_power(high_res_f, high_res_psd, lower_amplitude_weights,
                     octaves: ThirdOctavePower, upper_power_weights,
                     interior_mask):
    """P1.4: lower high-resolution edge + upper third-octave edge + interior.

    Coefficients are not inferred from edge frequencies, GOST filter class,
    or post-hoc agreement with MVKView.
    """
    f=np.asarray(high_res_f,dtype=float)
    p=np.asarray(high_res_psd,dtype=float)
    w=np.asarray(lower_amplitude_weights,dtype=float)
    u=np.asarray(upper_power_weights,dtype=float)
    mask=np.asarray(interior_mask,dtype=bool)
    op=np.asarray(octaves.acceleration_power,dtype=float)
    if any(x.shape!=f.shape for x in (p,w)):
        raise ValueError("Lower edge arrays must align with high-res PSD")
    if len(f)<2 or not np.allclose(np.diff(f),f[1]-f[0]):
        raise ValueError("High-resolution grid must be uniformly spaced")
    if u.shape!=op.shape or mask.shape!=op.shape:
        raise ValueError("Upper edge and interior mask must index third-octave bands")
    if np.any(mask & (u!=0)):
        raise ValueError("Third-octave upper and interior terms overlap")
    if not all(np.all(np.isfinite(x)) for x in (p,w,u,op)):
        raise ValueError("Non-finite data")
    if np.any(p<0) or np.any(w<0) or np.any(op<0) or np.any((u<0)|(u>1)):
        raise ValueError("Invalid powers or weights")
    e_low=float(np.sum(p*w*w)*(f[1]-f[0]))
    e_top=float(np.sum(op*u))
    e_mid=float(np.sum(op[mask]))
    return {"rms_m_s2":float(np.sqrt(e_low+e_top+e_mid)),
            "energy_low":e_low,"energy_upper":e_top,"energy_interior":e_mid}
