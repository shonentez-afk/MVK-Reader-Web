#!/usr/bin/env python3
"""Stage 45. Numeric check of IDR-reconstructed MVKView linear FFT branch.
Needs NumPy. Runs offline, no device interaction.
"""
import math
import numpy as np

if __name__ == "__main__":
    for n in (512, 2048, 8192, 32768, 65536, 262144):
        j=np.arange(n,dtype=np.float64)
        window=(1-np.cos(2*np.pi*j/n))/math.sqrt(1.5)
        enbw=n*np.sum(window**2)/np.sum(window)**2
        assert abs(enbw-1.5)<1e-8
        for offset in (0,0.5):
            signal=2*np.sin(2*np.pi*(37+offset)*j/n)
            signal-=np.mean(signal)
            power=np.abs(np.fft.rfft(signal*window))**2
            peak=np.max(np.sqrt(power[:-1]/2)/(n/2))
            ratio=float(peak/math.sqrt(2))
            expected=math.sqrt(2/3) if offset==0 else 0.69306443
            assert abs(ratio-expected)<1e-7,(n,offset,ratio)
            print(f"N={n} offset={offset} peak={peak:.9f} ratio={ratio:.9f}")
    print("PASS 12/12")
