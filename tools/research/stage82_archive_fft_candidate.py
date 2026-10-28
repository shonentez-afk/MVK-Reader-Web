#!/usr/bin/env python3
"""Stage82 offline MVKView archive spectrum candidate; NO device/network I/O.

Requires numpy. Reads a BIN and its optional .tsxml metadata. Never modifies inputs.
Numerical outputs are hypotheses until compared with a same-measurement MVKView reference.
"""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np

TABLE=262144

def metadata(path):
    root=ET.parse(path).getroot()
    def find(name):
        for element in root.iter():
            if element.tag.split("}")[-1] == name and element.text:
                return element.text.strip()
        return None
    return {name:find(name) for name in ("ChannelFrequency","FrequencyPerChannel",
            "RealDataType","InternalChannelGain","Units","DataLength","DataOffset","DataFileName")}

def load_archive(path, meta, sample_rate, dtype, apply_gain):
    kind=(dtype or (meta or {}).get("RealDataType") or "").lower()
    if kind not in ("single","byte"):
        raise ValueError("RealDataType unknown: specify --dtype Single or Byte")
    fs=sample_rate or float((meta or {}).get("ChannelFrequency") or
                            (meta or {}).get("FrequencyPerChannel") or 0)
    if not fs > 0:
        raise ValueError("Sample rate unknown: specify --fs or provide TSXML")
    data=np.fromfile(path,dtype="<f4" if kind=="single" else "u1")
    gain=float((meta or {}).get("InternalChannelGain") or 1)
    if apply_gain:
        data=data.astype(np.float64)*gain
    return data.astype(np.float32),fs,kind,gain

def spectrum(x,fs,n,offset,gain=1):
    if n<2 or n>TABLE or n&(n-1):
        raise ValueError("N must be power of two in [2,262144]")
    if offset<0 or offset+n>len(x):
        raise ValueError("requested window outside recording")
    window=(1-np.cos(2*np.pi*np.arange(n)/n))/np.sqrt(1.5)
    samples=(x[offset:offset+n]*window.astype(np.float32)).astype(np.float32)
    p=np.square(np.abs(np.fft.fft(samples))[:n//2])
    freq=np.arange(n//2)*fs/n
    linear=gain/(n/2)*np.sqrt(p/2)
    # Candidate only: original helper 0x00447DB8 is still unverified
    db=np.full(len(p),-180.0)
    pos=p>0
    db[pos]=10*np.log10(p[pos]/((n/2)**2))
    return freq,linear,db,p

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--bin",type=Path,required=True)
    ap.add_argument("--tsxml",type=Path)
    ap.add_argument("--fs",type=float)
    ap.add_argument("--dtype",choices=["Single","Byte"])
    ap.add_argument("--n",type=int,default=8192)
    ap.add_argument("--offset",type=int,default=0)
    ap.add_argument("--apply-gain",action="store_true",
                    help="EXPERIMENTAL only; default NEVER re-applies metadata gain")
    ap.add_argument("--out",type=Path,required=True,
                    help="CSV output; store outside tracked source tree if real data")
    args=ap.parse_args()
    m=metadata(args.tsxml) if args.tsxml else {}
    x,fs,kind,k=load_archive(args.bin,m,args.fs,args.dtype,args.apply_gain)
    f,a,db,p=spectrum(x,fs,args.n,args.offset)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    np.savetxt(args.out,np.column_stack((f,a,db,p)),delimiter=",",
               header="frequency_hz,linear_candidate,db_candidate,power",comments="")
    summary={"samples":len(x),"fs":fs,"dtype":kind,"metadata_gain":k,
             "gain_applied":args.apply_gain,"n":args.n,"offset":args.offset,
             "peak_bin":int(np.argmax(p[1:])+1) if len(p)>1 else 0,
             "limitations":["No original log helper confirmation",
                 "NumPy FFT not bitwise Delphi FFT","Not validated against original spectrum"]}
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
