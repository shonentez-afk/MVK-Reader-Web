"""Offline-only PCAP/PCAPNG direction audit for original MVKView TCP/10230.

It checks observed client->device payload and source SetRate 36-byte
signature, NOT whether the unrecorded original program ever transmits.
No sockets, network actions, third-party dependencies or private uploads.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import ipaddress
import json
from pathlib import Path
import struct

PORT=10230
MAX_BLOCK=16*1024*1024
MAX_COLLECT=1024*1024
SOURCE_TX={
    rate:struct.pack("<9I",0xFF800C0D,36,0,0,0,0,1,0x0002000E,rate)
    for rate in (65536,32768,8192,2048,512)
}


def _read(f,n):
    data=f.read(n)
    if len(data)!=n:raise ValueError("Truncated capture block")
    return data


def _pcapng(f):
    endian=None
    links=[]
    while True:
        header=f.read(4)
        if not header:return
        if len(header)!=4:raise ValueError("Truncated PCAPNG header")
        size_raw=_read(f,4)
        if header==b"\x0a\x0d\x0d\x0a":
            bom=_read(f,4)
            endian=("<" if bom==b"\x4d\x3c\x2b\x1a" else
                    ">" if bom==b"\x1a\x2b\x3c\x4d" else None)
            if endian is None:raise ValueError("Invalid PCAPNG byte order")
            size=struct.unpack(endian+"I",size_raw)[0]
            if not 28<=size<=MAX_BLOCK or size%4:raise ValueError("Invalid section size")
            body=_read(f,size-12)
            if struct.unpack(endian+"I",body[-4:])[0]!=size:
                raise ValueError("PCAPNG block length mismatch")
            links=[]
            continue
        if endian is None:raise ValueError("Missing PCAPNG section header")
        size=struct.unpack(endian+"I",size_raw)[0]
        if not 12<=size<=MAX_BLOCK or size%4:raise ValueError("Invalid PCAPNG block size")
        raw=_read(f,size-8)
        if struct.unpack(endian+"I",raw[-4:])[0]!=size:
            raise ValueError("PCAPNG block length mismatch")
        body=raw[:-4]
        kind=struct.unpack(endian+"I",header)[0]
        if kind==1:
            if len(body)<8:raise ValueError("Incomplete interface descriptor")
            links.append(struct.unpack_from(endian+"H",body)[0])
        elif kind==6:
            if len(body)<20:raise ValueError("Incomplete enhanced packet")
            iface,_,_,cap,_=struct.unpack_from(endian+"5I",body)
            if iface>=len(links) or cap>len(body)-20:
                raise ValueError("Invalid EPB captured packet")
            yield links[iface],body[20:20+cap]
        elif kind==3:
            if len(body)<4 or not links:raise ValueError("Invalid simple packet")
            n=struct.unpack_from(endian+"I",body)[0]
            if n>MAX_BLOCK:raise ValueError("Oversized simple packet")
            yield links[0],body[4:4+min(len(body)-4,n)]


def _pcap(f,magic):
    if magic in (b"\xd4\xc3\xb2\xa1",b"\x4d\x3c\xb2\xa1"):endian="<"
    elif magic in (b"\xa1\xb2\xc3\xd4",b"\xa1\xb2\x3c\x4d"):endian=">"
    else:raise ValueError("Not a supported PCAP/PCAPNG capture")
    link=struct.unpack_from(endian+"I",_read(f,20),16)[0]
    while True:
        header=f.read(16)
        if not header:return
        if len(header)!=16:raise ValueError("Truncated PCAP record")
        _,_,cap,original=struct.unpack(endian+"4I",header)
        if cap>MAX_BLOCK or cap>original:raise ValueError("Invalid PCAP captured size")
        yield link,_read(f,cap)


def _packets(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Capture must be an existing regular file")
    with path.open("rb") as f:
        magic=_read(f,4)
        if magic==b"\x0a\x0d\x0d\x0a":
            f.seek(0)
            yield from _pcapng(f)
        else:
            yield from _pcap(f,magic)


def _tcp(link,packet):
    if link==1:
        if len(packet)<14:return None
        proto=int.from_bytes(packet[12:14],"big")
        i=14
        while proto in (0x8100,0x88A8,0x9100):
            if len(packet)<i+4:return None
            proto=int.from_bytes(packet[i+2:i+4],"big")
            i+=4
        if proto!=0x0800:return None
    elif link==101:i=0
    elif link==113:
        if len(packet)<16 or packet[14:16]!=b"\x08\x00":return None
        i=16
    elif link==276:
        if len(packet)<20 or packet[:2]!=b"\x08\x00":return None
        i=20
    else:return None
    ip=packet[i:]
    if len(ip)<40 or ip[0]>>4!=4 or ip[9]!=6:return None
    h=(ip[0]&15)*4
    if h<20 or len(ip)<h+20 or int.from_bytes(ip[6:8],"big")&0x1FFF:
        return None
    total=int.from_bytes(ip[2:4],"big")
    if total<h+20:return None
    tcp=ip[h:min(total,len(ip))]
    if len(tcp)<20:return None
    src,dst=struct.unpack_from("!HH",tcp)
    if src!=PORT and dst!=PORT:return None
    th=(tcp[12]>>4)*4
    if th<20 or len(tcp)<th:return None
    return (str(ipaddress.IPv4Address(ip[12:16])),src,
            str(ipaddress.IPv4Address(ip[16:20])),dst,
            struct.unpack_from("!I",tcp,4)[0],tcp[13],tcp[th:])


@dataclass
class Flow:
    client:str
    client_port:int
    instrument:str
    c2d_packets:int=0
    d2c_packets:int=0
    c2d_bytes:int=0
    d2c_bytes:int=0
    syn:int=0
    segments:list[tuple[int,bytes]]=field(default_factory=list)
    saved:int=0
    truncated:bool=False

    def feed(self,direction,seq,flags,data):
        if flags&2:self.syn+=1
        if direction=="to_device":
            self.c2d_packets+=1
            self.c2d_bytes+=len(data)
            remain=MAX_COLLECT-self.saved
            if data and remain>0:
                chunk=data[:remain]
                self.segments.append((seq,chunk))
                self.saved+=len(chunk)
            if len(data)>remain:self.truncated=True
        else:
            self.d2c_packets+=1
            self.d2c_bytes+=len(data)

    def summary(self):
        runs=[]
        run=bytearray()
        end=None
        for seq,data in sorted(self.segments):
            if end is None:
                run=bytearray(data)
                end=seq+len(data)
            elif seq>end:
                runs.append(bytes(run))
                run=bytearray(data)
                end=seq+len(data)
            elif seq+len(data)>end:
                run.extend(data[end-seq:])
                end=seq+len(data)
        if end is not None:runs.append(bytes(run))
        patterns={str(rate):sum(chunk.count(signature) for chunk in runs)
                  for rate,signature in SOURCE_TX.items()}
        return {
            "client_ip":self.client,"client_port":self.client_port,
            "instrument_ip":self.instrument,"instrument_port":PORT,
            "client_to_device_packets":self.c2d_packets,
            "client_to_device_payload_bytes":self.c2d_bytes,
            "device_to_client_packets":self.d2c_packets,
            "device_to_client_payload_bytes":self.d2c_bytes,
            "syn_packets_observed":self.syn,
            "exact_source_setrate_36_byte_patterns":patterns,
            "exact_setrate_detected":any(patterns.values()),
            "no_client_payload_observed":self.c2d_bytes==0,
            "outbound_analysis_truncated":self.truncated,
        }


def analyze(path,instrument_ip=None):
    p=Path(path)
    target=str(ipaddress.IPv4Address(instrument_ip)) if instrument_ip else None
    flows={}
    packets=0
    selected=0
    for link,raw in _packets(p):
        packets+=1
        segment=_tcp(link,raw)
        if segment is None:continue
        src,sp,dst,dp,seq,flags,data=segment
        if dp==PORT and sp!=PORT:
            direction="to_device";client,client_port,instrument=src,sp,dst
        elif sp==PORT and dp!=PORT:
            direction="from_device";client,client_port,instrument=dst,dp,src
        else:continue
        if target is not None and instrument!=target:continue
        key=client,client_port,instrument
        if key not in flows:flows[key]=Flow(*key)
        flows[key].feed(direction,seq,flags,data)
        selected+=1
    results=[flow.summary() for _,flow in sorted(flows.items())]
    return {
        "schema":"MVK_OFFLINE_TCP10230_DIRECTION_AUDIT_V1",
        "file_name":p.name,
        "packets_scanned":packets,
        "tcp10230_packets":selected,
        "device_filter":target,
        "flows":results,
        "conclusion":(
            "No observed client application payload on TCP/10230"
            if results and all(x["no_client_payload_observed"] for x in results)
            else "Captured client-to-device application data exists"
            if any(x["client_to_device_payload_bytes"] for x in results)
            else "No relevant TCP/10230 packets were captured"
        ),
        "limitation":(
            "The original app, capture start, filters and missing packets "
            "cannot be determined from an absent TX signature. "
            "No physical device interaction was performed."
        ),
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pcap",type=Path)
    parser.add_argument("--instrument-ip")
    args=parser.parse_args()
    print(json.dumps(analyze(args.pcap,instrument_ip=args.instrument_ip),
                     ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
