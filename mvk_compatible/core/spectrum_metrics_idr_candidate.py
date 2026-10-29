"""Stage111G GetSpectrum summary fields reconstructed from PRIVATE Delphi IDR.

Source _Unit115.pas: 007D1558 upper bin Trunc(N/2.56);
007D17F9..1830 strict max and f64 power sum; 007D1832..1860 OutputMean;
007D1861..18CC +/-2-bin weighted peak; 007D21A8 f32 accumulators;
007D18D1..18FF OutputPeakY; _Unit128 00848218 derives series XScale.

APP_DERIVED research only, not AUX4700 and not bitwise-verified Delphi/x87.
"""
from __future__ import annotations
import math
import numpy as np


def original_spectrum_summary(power:np.ndarray,*,n_fft:int,fs_out:float,
                              f_range:float=1.,spectrum_mode:int=1)->dict:
    """Source-derived mean and energy centroid from ORIGINAL float32 power bins.

    Input: full power N/2, after 007D2164 integration if mode 2/3 and
    before display conversion; no values taken from a decimated plotted line.
    """
    if (not isinstance(n_fft,(int,np.integer)) or isinstance(n_fft,bool)
        or n_fft<1024 or n_fft>262144 or n_fft&(n_fft-1)):
        raise ValueError('Original spectrum requires power-of-two N=1024..262144')
    if (not math.isfinite(fs_out) or fs_out<=0 or not math.isfinite(f_range)
        or f_range<=0 or spectrum_mode not in range(4)):
        raise ValueError('Invalid original GetSpectrum frequency, range or mode')
    a=np.asarray(power,dtype=np.float32)
    half=n_fft//2
    if (a.ndim!=1 or len(a)!=half or not bool(np.isfinite(a).all())
        or bool((a<0).any())):
        raise ValueError('Original summary needs complete finite nonnegative FFT power')
    first=max(2,round(n_fft/(2.*fs_out)))
    last=min(half-1,math.trunc(n_fft/2.56))
    if first>last:
        raise ValueError('Invalid original spectral summary interval')
    corrected=a.copy()
    corrected[:first]=0
    # Original _Unit115:007D1807..007D1810 loads a qword accumulator,
    # adds ONE Single power bin, then FSTP qword on every iteration.
    # NumPy sum uses a pairwise reduction and is NOT the source operation.
    total=0.0
    for k in range(first,last+1):
        total=float(total+float(corrected[k]))
    # Source uses strict >, so NumPy argmax correctly keeps first tie.
    candidate=int(np.argmax(corrected[first:last+1]))+first
    peak_raw_power=float(corrected[candidate])
    scale=float(f_range)/half
    mean=float(np.float32(math.sqrt(total/2.)*scale))
    x=float(np.float32(0.))
    peak_amp=float(np.float32(0.))
    local_power=0.
    neighborhood=(0,0)
    if candidate>2 and peak_raw_power>0.:
        lower=candidate-2
        upper=min(half-1,candidate+2)
        energy=np.float32(0.)
        weighted=np.float32(0.)
        # Source FSTP Single after every step; retain float32 boundaries.
        for index in range(lower,upper+1):
            value=float(corrected[index])
            energy=np.float32(float(energy)+value)
            weighted=np.float32(float(weighted)+index*value)
        local_power=float(energy)
        neighborhood=(lower,upper)
        if energy>0.:
            x=float(np.float32(float(weighted)/float(energy)))
            peak_amp=float(np.float32(math.sqrt(float(energy)/2.)*scale))
    df=fs_out/n_fft
    freq=float(np.float32(float(np.float32(x))*float(np.float32(df))))
    return {
        'source':'APP_DERIVED_GETSPECTRUM_PEAK_SUMMARY_IDR_CANDIDATE',
        'original_delphi_numerical_parity_verified':False,
        'n_fft':int(n_fft),'spectrum_mode':int(spectrum_mode),
        'fs_out_hz':float(fs_out),'df_hz':float(df),'f_range':float(f_range),
        'summary_first_bin':int(first),'summary_last_bin':int(last),
        'raw_max_power_bin':candidate,'raw_max_power':peak_raw_power,
        'raw_total_band_power':total,'power_sum_order':'DELPHI_STEPWISE_F64_STORED',
        'output_mean':mean,
        'output_peak_x_bin':x,'output_peak_frequency_hz':freq,
        'output_peak_y':peak_amp,
        'peak_neighborhood_first_bin':neighborhood[0],
        'peak_neighborhood_last_bin':neighborhood[1],
        'peak_neighborhood_power_sum':local_power,
        'energy_weighted_peak':True,
        'warning':'Power band/centroid source-derived; x87 numerical parity and format settings unverified'
    }
