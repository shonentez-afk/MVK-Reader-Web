"""Offline fixed-band response model: separate Butterworth HP3 and LP3.
Manual Appendix 1 sec.1.3 -> GOST ISO 2954-2014. DSP P1.4 weights NOT recovered.
"""
import argparse
import json
import numpy as np
from scipy.signal import butter, sosfreqz, periodogram

FS_DEFAULT=65536
BANDS=((2,1000),(10,1000),(10,2000),(10,3000))

def response(frequencies_hz,fs,low_hz,high_hz):
    f=np.asarray(frequencies_hz,dtype=float)
    if not (0<low_hz<high_hz<fs/2):raise ValueError("Invalid band limits")
    if f.ndim!=1 or not np.all(np.isfinite(f)) or np.any((f<0)|(f>fs/2)):
        raise ValueError("Invalid frequency grid")
    hp=butter(3,low_hz,btype="highpass",fs=fs,output="sos")
    lp=butter(3,high_hz,btype="lowpass",fs=fs,output="sos")
    return sosfreqz(hp,worN=f,fs=fs)[1]*sosfreqz(lp,worN=f,fs=fs)[1]

def bin_psd(samples,fs=FS_DEFAULT):
    x=np.asarray(samples,dtype=float)
    if x.ndim!=1 or len(x)<2 or not np.all(np.isfinite(x)):
        raise ValueError("Invalid waveform")
    return periodogram(x,fs=fs,window="boxcar",detrend="constant",scaling="density")

def fixed_band_rms_from_psd(f,psd,fs=FS_DEFAULT,bands=BANDS):
    f=np.asarray(f,dtype=float); psd=np.asarray(psd,dtype=float)
    if f.ndim!=1 or psd.shape!=f.shape or len(f)<2 or np.any(psd<0) or not np.all(np.isfinite(psd)):
        raise ValueError("Invalid PSD")
    df=np.diff(f)
    if not np.allclose(df,df[0]) or not np.isclose(f[0],0):
        raise ValueError("Expected uniform frequency grid starting at DC")
    return {f"{low}-{high}":float(np.sqrt(np.sum(psd*np.abs(response(f,fs,low,high))**2)*df[0]))
            for low,high in bands}

def audit_bin(path,fs=FS_DEFAULT):
    from pathlib import Path
    x=np.memmap(path,dtype="<f4")
    f,psd=bin_psd(x,fs)
    return {"filename":Path(path).name,"samples":len(x),"duration_s":len(x)/fs,
            "method":"periodogram boxcar detrend constant, separate HP3 x LP3",
            "rms_m_s2":fixed_band_rms_from_psd(f,psd,fs)}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("bin_files",nargs="+")
    p.add_argument("--fs",type=int,default=FS_DEFAULT);a=p.parse_args()
    print(json.dumps([audit_bin(path,a.fs) for path in a.bin_files],indent=2,ensure_ascii=False))
