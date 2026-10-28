"""Offline-only BIN Welch/Hann preflight for Stage13 P1.2-P1.4.
This does NOT implement manufacturer edge windows or final fixed-band RMS.
"""
import argparse
import json
import numpy as np
from scipy.signal import welch

def audit(path, fs=65536):
    data=np.memmap(path,dtype="<f4")
    if not np.isfinite(data).all():
        raise ValueError("BIN contains NaN or Inf")
    f,psd=welch(data,fs=fs,window="hann",nperseg=65536,
                noverlap=32768,detrend="constant",scaling="density")
    df=f[1]-f[0]
    bands=[(10,1000),(10,2000),(10,3000),(3000,3536),
           (3000,3500),(3500,5000),(5000,10000)]
    return {"n_samples":int(data.size),"duration_s":float(data.size/fs),
            "mean":float(data.mean()),"std":float(data.std()),
            "bands_welch_hann_rms":{
                f"{lo}-{hi}":float(np.sqrt(np.sum(
                    psd[(f>=lo)&(f<hi)])*df))
                for lo,hi in bands}}
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("files",nargs="+")
    args=parser.parse_args()
    print(json.dumps({p:audit(p) for p in args.files},indent=2))
