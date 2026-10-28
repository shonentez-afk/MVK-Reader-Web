#!/usr/bin/env python3
"""Synthetic-only FFT test for Stage81e; NumPy required; no device I/O."""
import math
import numpy as np
for n in (256,1024,8192):
    k=37
    t=np.arange(n,dtype=np.float64)
    signal=np.sin(2*np.pi*k*t/n).astype(np.float32)
    window=((1-np.cos(2*np.pi*t/n))/np.sqrt(1.5)).astype(np.float32)
    power=(abs(np.fft.fft((signal*window).astype(np.float32)))[:n//2]**2).astype(np.float32)
    peak=int(np.argmax(power[1:])+1)
    amplitude=float(np.sqrt(power[k]/2)/(n/2))
    candidate_db=float(10*np.log10(float(power[k])/(n/2)**2))
    assert peak==k and math.isclose(amplitude,1/math.sqrt(3),rel_tol=1e-5)
    zero_power=np.zeros(n//2,dtype=np.float32)
    zero_db=np.where(zero_power>0,0.,-180.)
    assert np.all(zero_db==-180.)
    print(f"PASS N={n} peak={peak} amplitude={amplitude:.8f} candidate_dB={candidate_db:.4f}")
print("Candidate numeric check only; not original MVKView equivalence")
