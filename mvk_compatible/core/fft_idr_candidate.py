"""Stage111B IDR-based local FFT candidate. Offline, NO device/network/Qt.

Evidence from ORIGINAL but PRIVATE Delphi disassembly (do not publish it):
  007D2344: subtract float32-stored running mean before FFT
  008C1064: 262144 float32 periodic Hann-RMS table
  007D1FE8: windowed complex float32 samples -> single |FFT|**2
  007CC198: positive-angle, radix-2 FFT with bit reversal/twiddle recurrence
  007CC3F8: unnormalised forward FFT
Stage111Z.4: source verified four Single stores within FFT twiddle recurrence.
Exact x87 sin(), the window generator and complete Delphi numerical parity remain UNVERIFIED.
"""
from __future__ import annotations
import math
from functools import lru_cache
import numpy as np

MAX_FFT_N=262144


def check_n(n:int)->int:
    if (not isinstance(n,(int,np.integer)) or isinstance(n,bool)
        or n<2 or n>MAX_FFT_N or n&(n-1)):
        raise ValueError('FFT N must be a power of two in 2..262144')
    return int(n)


def mean_center_float32(signal:np.ndarray)->tuple[np.ndarray,float]:
    """007D2344: subtract running float32-stored mean, without mutating BIN."""
    x=np.asarray(signal,dtype=np.float32)
    if x.ndim!=1 or not x.size or not bool(np.isfinite(x).all()):
        raise ValueError('Expected finite, nonempty 1D float32 samples')
    # cumsum(dtype=f32) stores each successive partial sum, unlike np.mean.
    total=np.cumsum(x,dtype=np.float32)[-1]
    mean=np.float32(float(total)/len(x))
    return np.asarray(x.astype(np.float64)-float(mean),dtype=np.float32),float(mean)


@lru_cache(maxsize=1)
def _hann_table()->np.ndarray:
    j=np.arange(MAX_FFT_N,dtype=np.float64)
    w=np.asarray((1.-np.cos((2.*np.pi/MAX_FFT_N)*j))/math.sqrt(1.5),dtype=np.float32)
    w.setflags(write=False)
    return w


def idr_hann_rms(n:int)->np.ndarray:
    n=check_n(n)
    return _hann_table()[::(MAX_FFT_N//n)].copy()


def _bit_reverse_indices(n:int)->np.ndarray:
    bits=n.bit_length()-1
    i=np.arange(n,dtype=np.uint32)
    out=np.zeros(n,dtype=np.uint32)
    for j in range(bits):
        out=(out<<np.uint32(1))|((i>>np.uint32(j))&np.uint32(1))
    return out


def _twiddle_step_with_single_stores(wr:np.float32, wi:np.float32,
                                    alpha:np.float32, beta:np.float32
                                    )->tuple[np.float32,np.float32]:
    """007CC325/007CC33A/007CC344: four source FSTP Single boundaries.

    The original x87 stores BOTH (alpha*wr+beta*wi) and
    (alpha*wi-beta*wr) as Single before subtracting from wr/wi.
    Collapsing the intermediate arithmetic into float64 silently changes
    recurrence bits even when the final twiddles are float32.
    """
    old_wr,old_wi=float(wr),float(wi)
    temp_real=np.float32(float(alpha)*old_wr+float(beta)*old_wi)
    temp_imag=np.float32(float(alpha)*old_wi-float(beta)*old_wr)
    next_wi=np.float32(old_wi-float(temp_imag))
    next_wr=np.float32(old_wr-float(temp_real))
    return next_wr,next_wi


def _twiddles_recurrent_float32(half:int)->tuple[np.ndarray,np.ndarray]:
    """Stage angle=+2pi/(2*half); Single-stored twiddle recurrence per 007CC316."""
    angle=np.float32(np.float32(2.*math.pi)/np.float32(2*half))
    ss=np.float32(math.sin(float(angle)/2.))
    alpha=np.float32(2.*float(ss)**2)
    beta=np.float32(math.sin(float(angle)))
    rr=np.empty(half,dtype=np.float32)
    ii=np.empty(half,dtype=np.float32)
    wr,wi=np.float32(1.),np.float32(0.)
    for j in range(half):
        rr[j]=wr; ii[j]=wi
        wr,wi=_twiddle_step_with_single_stores(wr,wi,alpha,beta)
    return rr,ii


def fft_idr_float32_real(signal:np.ndarray)->tuple[np.ndarray,np.ndarray]:
    """Unnormalised positive-angle radix-2, float32 stored butterfly outputs."""
    data=np.asarray(signal,dtype=np.float32)
    if data.ndim!=1 or not bool(np.isfinite(data).all()):
        raise ValueError('FFT input must contain finite one-dimensional samples')
    n=check_n(len(data))
    real=data[_bit_reverse_indices(n)].copy()
    imag=np.zeros(n,dtype=np.float32)
    m=2
    while m<=n:
        h=m//2
        wr,wi=_twiddles_recurrent_float32(h)
        r=real.reshape(-1,m); im=imag.reshape(-1,m)
        lr=r[:,:h].copy();li=im[:,:h].copy()
        rr=r[:,h:].astype(np.float64);ri=im[:,h:].astype(np.float64)
        wrr=wr.astype(np.float64)[None,:];wii=wi.astype(np.float64)[None,:]
        tr=np.asarray(wrr*rr-wii*ri,dtype=np.float32)
        ti=np.asarray(wrr*ri+wii*rr,dtype=np.float32)
        r[:,h:]=np.asarray(lr.astype(np.float64)-tr,dtype=np.float32)
        im[:,h:]=np.asarray(li.astype(np.float64)-ti,dtype=np.float32)
        r[:,:h]=np.asarray(lr.astype(np.float64)+tr,dtype=np.float32)
        im[:,:h]=np.asarray(li.astype(np.float64)+ti,dtype=np.float32)
        m*=2
    return real,imag


def idr_power_spectrum(signal:np.ndarray,backend:str='idr_float32', *,
                       remove_dc:bool=True)->tuple[np.ndarray,float]:
    """P[0..N/2-1], Hann RMS / original-style unnormalised FFT candidate.

    GetSpectrum removes DC ONCE from raw ring samples before optional FIR/IQ.
    The envelope path passes remove_dc=False because its complex-filter
    magnitude MUST NOT be mean-subtracted a second time (007D14B3).
    All existing non-envelope callers keep the original remove_dc=True.
    """
    if not isinstance(remove_dc,bool):
        raise ValueError('remove_dc must be an explicit boolean')
    x=np.asarray(signal,dtype=np.float32)
    n=check_n(len(x))
    if x.ndim!=1 or not bool(np.isfinite(x).all()):
        raise ValueError('FFT input must be one-dimensional finite float32')
    if remove_dc:
        centered,removed_mean=mean_center_float32(x)
    else:
        centered=x.copy()
        removed_mean=0.0
    windowed=np.asarray(centered.astype(np.float64)*idr_hann_rms(n).astype(np.float64),dtype=np.float32)
    if backend=='idr_float32':
        re,im=fft_idr_float32_real(windowed)
        power=np.asarray(re[:n//2].astype(np.float64)**2+im[:n//2].astype(np.float64)**2,dtype=np.float32)
    elif backend=='numpy':
        f=np.fft.rfft(windowed.astype(np.float64))[:n//2]
        power=f.real**2+f.imag**2
    else:
        raise ValueError('Unknown local FFT backend')
    return power,removed_mean
