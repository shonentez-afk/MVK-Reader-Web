#!/usr/bin/env python3
"""Synthetic self-test for Stage82. No real recordings, no network."""
import importlib.util
import tempfile
from pathlib import Path
import numpy as np
path=Path(__file__).with_name("stage82_archive_fft_candidate.py")
spec=importlib.util.spec_from_file_location("stage82",path)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    fs=8192
    n=8192
    k=37
    raw=np.sin(2*np.pi*k*np.arange(n)/n).astype("<f4")
    binary=root/"example.bin"
    raw.tofile(binary)
    xml=root/"example.bin.tsxml"
    xml.write_text("""<?xml version="1.0" encoding="utf-8"?>
<MainRoot><Channels><Channel Index="0"><ChannelFrequency>8192</ChannelFrequency>
<RealDataType>Single</RealDataType><InternalChannelGain>510.6</InternalChannelGain>
</Channel></Channels></MainRoot>""",encoding="utf-8")
    meta=m.metadata(xml)
    samples,read_fs,kind,gain=m.load_archive(binary,meta,None,None,False)
    assert len(samples)==n and read_fs==fs and kind=="single" and gain==510.6
    assert np.array_equal(raw,samples), "gain must not be applied by default"
    f,a,db,p=m.spectrum(samples,fs,n,0)
    assert np.argmax(p[1:])+1 == k
    assert abs(f[k]-37)<1e-12
    assert abs(a[k]-1/np.sqrt(3))<1e-5
    _,_,dz,pz=m.spectrum(np.zeros(n,dtype=np.float32),fs,n,0)
    assert np.all(pz==0) and np.all(dz==-180)
    data2,_,_,_=m.load_archive(binary,meta,None,None,True)
    assert np.allclose(data2,raw*gain,rtol=1e-6)
    print("PASS synthetic single, tsxml, gain-policy, peak-bin, zero-input")
    print("NOT a validation against MVKView or any industrial archive")
