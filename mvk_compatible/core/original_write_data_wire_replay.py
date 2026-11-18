"""Stage111Z31FR: source channel WriteData bytes from the accepted RX RAW.

Triple private provenance (never included in files): mvkview.idp,
Projects.7z/_Unit125.pas and mvk_idr(1).sqlite. Original TMVKThread
Execute 0080822F..008082DE: for a selected channel, the TFileStream
receives unscaled TmpStream.FMemory bytes, gated by MvkSampleRate and
FreezeUpdate and starting after ADC1 enters WriteDataStage=1.

This replay preserves precisely received ADC/TACH payload bytes.
It does NOT assume original rate/freeze transitions, original file
names, exact click timing or original Delphi BIN equivalence. The Go
next-frame marks determine only verifiable packet boundaries.
"""
from __future__ import annotations

from contextlib import ExitStack
from hashlib import sha256
from pathlib import Path
import struct

TYPE_ADC=0xFF800ADC
TYPE_TACH=0xFF8001AC
TYPE_PARAM=0xFF800C0D
TYPE_ACK=0x00010FF0
TYPE_DENIED=0x00010FFF
TYPE_IDENTITY=1
MAX_FRAME=0x20000
MAX_RAW=2*1024*1024*1024
ALLOWED_RATES=frozenset((512,2048,8192,32768,65536))
MAX_CUTS=80


def _integer(value,label,maximum=(1 << 64)-1):
    if type(value) is not int or not 0<=value<=maximum:
        raise ValueError("Original WriteData RAW: invalid "+label)
    return value


def export_source_wire_write_intervals(
    raw_path:Path|str, output_dir:Path|str, *,
    expected_sha256:str, expected_raw_bytes:int, expected_frames:int,
    expected_tail_bytes:int, expected_channel_samples:list[int],
    cuts:list[tuple[int,int,int,int]],
)->list[dict]:
    """Write original wire payload slices for checked Go frame-mark windows.

    `cuts`: (one-based window, one-based channel, first word, last word).
    Each word is 4 bytes for both wire ADC and TACH. No gain, no float
    conversion, no resampling, no synthetic final samples.
    """
    source=Path(raw_path)
    target=Path(output_dir)
    if (source.is_symlink() or not source.is_file() or
            target.is_symlink() or not target.is_dir()):
        raise ValueError("Original WriteData RAW: untrusted input/output path")
    if (not isinstance(expected_sha256,str) or len(expected_sha256)!=64
            or any(x not in "0123456789abcdef" for x in expected_sha256)):
        raise ValueError("Original WriteData RAW: invalid original digest")
    amount=_integer(expected_raw_bytes,"RAW length",MAX_RAW)
    frames=_integer(expected_frames,"Go application frame total",amount//8)
    tail=_integer(expected_tail_bytes,"terminal tail",MAX_FRAME-1)
    if source.stat().st_size!=amount:
        raise ValueError("Original WriteData RAW: source file length mismatch")
    if (not isinstance(expected_channel_samples,list) or
            len(expected_channel_samples)!=10):
        raise ValueError("Original WriteData RAW: expected ten channel counters")
    final=[_integer(n,f"ADC/TACH {i+1} count",amount//4)
           for i,n in enumerate(expected_channel_samples)]
    if type(cuts) is not list or len(cuts)>MAX_CUTS:
        raise ValueError("Original WriteData RAW: selected window limit")
    selected={}
    for row in cuts:
        if (not isinstance(row,tuple) or len(row)!=4):
            raise ValueError("Original WriteData RAW: invalid selected cut")
        number,channel,start,end=row
        _integer(number,"window",8)
        _integer(channel,"channel",10)
        if number==0 or channel==0:
            raise ValueError("Original WriteData RAW: bad channel or window")
        _integer(start,"start word",final[channel-1])
        _integer(end,"end word",final[channel-1])
        if start>=end or (number,channel) in selected:
            raise ValueError("Original WriteData RAW: empty/repeated sample range")
        label=(f"DATA{number:02d}_ADC{channel}_WIRE_RX_UNSCALED.bin"
               if channel<=8 else
               f"DATA{number:02d}_TACH{channel-8}_WIRE_RX_UNSCALED.bin")
        selected[(number,channel)]=(start,end,label)
    current=[0]*10
    digest=sha256()
    byte_count=0
    receipts=[]
    with ExitStack() as stack:
        writers={}
        for (number,channel),(start,end,label) in selected.items():
            handle=stack.enter_context((target/label).open("xb"))
            writers[(number,channel)]=(handle,sha256())
        with source.open("rb") as src:
            for i in range(frames):
                header=src.read(8)
                if len(header)!=8:
                    raise ValueError("Original WriteData RAW: early frame EOF")
                typ,length=struct.unpack("<II",header)
                if not 8<=length<=MAX_FRAME or length%4:
                    raise ValueError("Original WriteData RAW: invalid frame envelope")
                payload=src.read(length-8)
                if len(payload)!=length-8:
                    raise ValueError("Original WriteData RAW: truncated application frame")
                digest.update(header);digest.update(payload)
                byte_count+=length
                if typ in (TYPE_ADC,TYPE_TACH):
                    if length<28:
                        raise ValueError("Original WriteData RAW: short sample header")
                    channel=struct.unpack_from("<I",payload,12)[0]
                    rate=struct.unpack_from("<I",payload,16)[0]
                    if ((typ==TYPE_ADC and channel>=8) or
                            (typ==TYPE_TACH and channel not in (8,9)) or
                            rate not in ALLOWED_RATES):
                        raise ValueError("Original WriteData RAW: invalid channel/rate")
                    sample=payload[20:]
                    n=len(sample)//4
                    before=current[channel]
                    after=before+n
                    if after>final[channel]:
                        raise ValueError("Original WriteData RAW: channel sample overflow")
                    for (number,c),(start,end,label) in selected.items():
                        if c!=channel+1 or end<=before or start>=after:
                            continue
                        left=max(start,before)-before
                        right=min(end,after)-before
                        fragment=sample[left*4:right*4]
                        w,h=writers[(number,c)]
                        w.write(fragment)
                        h.update(fragment)
                    current[channel]=after
                elif typ in (TYPE_ACK,TYPE_DENIED):
                    if length!=8:
                        raise ValueError("Original WriteData RAW: bad reply size")
                elif typ==TYPE_PARAM:
                    if length<32:
                        raise ValueError("Original WriteData RAW: bad PARAM size")
                elif typ==TYPE_IDENTITY:
                    pass
                else:
                    # Source Execute consumes an otherwise well-framed
                    # unknown type and resumes the original read loop.
                    pass
            rest=src.read(MAX_FRAME)
            if len(rest)!=tail or src.read(1):
                raise ValueError("Original WriteData RAW: terminal fragment mismatch")
            digest.update(rest)
            byte_count+=len(rest)
        if (byte_count!=amount or digest.hexdigest()!=expected_sha256
                or current!=final):
            raise ValueError("Original WriteData RAW: SHA/sample counters mismatch")
        for (number,channel),(start,end,label) in selected.items():
            w,h=writers[(number,channel)]
            w.flush()
            if (target/label).stat().st_size!=(end-start)*4:
                raise ValueError("Original WriteData RAW: channel cut length mismatch")
            receipts.append({
                "window":number,"channel":channel,"name":label,
                "bytes":(end-start)*4,"samples":end-start,
                "sha256":h.hexdigest(),
                "source_raw_sha256":expected_sha256,
                "original_rx_payload_bytes_exact":True,
                "source_delphi_rate_freeze_gate_parity_verified":False,
                "original_delphi_filename_parity_verified":False,
                "original_delphi_bin_parity_verified":False,
            })
    return receipts
