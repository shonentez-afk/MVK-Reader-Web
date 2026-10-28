"""Frozen MVK-LAB-06 v3 inference. Experimental, not vendor DSP.
Requires calibrated acceleration samples in m/s2; never refits to target data.
Full-record LF energy plus 2s Hann-window median HF energies.
"""
import math
import numpy as np
from scipy.signal import periodogram
CENTERS=(.8,1,1.25,1.6,2,2.5,3.15,4,5,6.3,8,10,12.5,16,20,25,31.5,40,50,63,80,100,125,160,200,250,315,400,500,630,800,1000,1250,1600,2000,2500,3150,4000,5000,6300,8000,10000)
ROWS=((10,3000),(10,2000),(10,1000),(2,1000),(.8,300),(.8,150))
W={150:.3901703205129557,300:.17520158691879723,1000:.035655431949799005,2000:8.998696572013008e-18,3000:.4053022408746561}
S={150:.8797783659907882,300:.18932904710435094,1000:.3814628907090854,2000:.5331568219362987,3000:.10487198698380487}

def edges(center):
    k=round(3*math.log2(center/1000))
    c=1000*2**(k/3)
    return c*2**(-1/6),c*2**(1/6)

def predict(samples,fs=65536):
    x=np.asarray(samples,dtype=float)
    if x.ndim!=1 or x.size<2*fs or not np.all(np.isfinite(x)):
        raise ValueError("Need >=2 seconds calibrated acceleration m/s2")
    f,p=periodogram(x,fs=fs,window="hann",detrend="constant",scaling="density")
    df=f[1]-f[0]
    low={lo:float(np.sum(p[(f>=lo)&(f<40)])*df) for lo in (10,2,.8)}
    n=2*fs
    hf=[]
    for start in range(0,len(x)-n+1,n):
        fw,pw=periodogram(x[start:start+n],fs=fs,window="hann",detrend="constant",scaling="density")
        dw=fw[1]-fw[0]
        def power(a,b):
            return float(np.sum(pw[(fw>=a)&(fw<b)])*dw)
        block={}
        for upper in (150,300,1000,2000,3000):
            c=next(c for c in CENTERS if edges(c)[0]<upper<edges(c)[1])
            nxt=CENTERS[CENTERS.index(c)+1]
            block[upper]=power(40,edges(c)[0])+W[upper]*power(*edges(c))+S[upper]*power(*edges(nxt))
        hf.append(block)
    return {f"{lo:g}-{hi:g}":float(math.sqrt(max(0,low[lo]+np.median([z[hi] for z in hf])))) for lo,hi in ROWS}
