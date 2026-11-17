"""Fully synthetic capture proves direction + split-TCP signature audit."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import struct
import sys

import pytest

SCRIPT=Path(__file__).resolve().parents[2]/"tools/research/offline_tcp10230_pcap_audit.py"
spec=importlib.util.spec_from_file_location("mvk_offline_pcap_direction",SCRIPT)
audit=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=audit
spec.loader.exec_module(audit)


def block(kind,data):
    while len(data)%4:data+=b"\x00"
    length=12+len(data)
    return struct.pack("<II",kind,length)+data+struct.pack("<I",length)


def capture(packets):
    section=block(0x0A0D0D0A,b"\x4d\x3c\x2b\x1a"+struct.pack("<HHq",1,0,-1))
    idb=block(1,struct.pack("<HHI",1,0,65535))
    frames=[block(6,struct.pack("<IIIII",0,0,0,len(p),len(p))+p) for p in packets]
    return section+idb+b"".join(frames)


def packet(src,dst,sp,dp,seq,data,flags=0x18):
    tcp=struct.pack("!HHIIHHHH",sp,dp,seq,0,5<<12|flags,65535,0,0)+data
    ipv4=lambda ip:bytes(int(x) for x in ip.split("."))
    ip=(b"\x45\x00"+struct.pack("!H",20+len(tcp))+
        b"\x00\x01\x00\x00\x40\x06\x00\x00"+ipv4(src)+ipv4(dst))
    return b"\x00"*12+b"\x08\x00"+ip+tcp


def test_original_delphi_command_split_across_tcp_segments_and_retransmitted(tmp_path):
    command=audit.SOURCE_TX[65536]
    p=tmp_path/"split.pcapng"
    p.write_bytes(capture([
        packet("192.168.0.151","192.168.0.30",51000,10230,1000,b"",2),
        packet("192.168.0.30","192.168.0.151",10230,51000,50,b"\x01\0\0\0\x08\0\0\0"),
        packet("192.168.0.151","192.168.0.30",51000,10230,1001,command[:11]),
        packet("192.168.0.151","192.168.0.30",51000,10230,1012,command[11:]),
        packet("192.168.0.151","192.168.0.30",51000,10230,1012,command[11:]),
    ]))
    report=audit.analyze(p,instrument_ip="192.168.0.30")
    flow=report["flows"][0]
    assert report["tcp10230_packets"]==5
    assert flow["client_to_device_payload_bytes"]==61
    assert flow["device_to_client_payload_bytes"]==8
    assert flow["exact_source_setrate_36_byte_patterns"]["65536"]==1
    assert flow["exact_setrate_detected"]


def test_no_outbound_bytes_means_only_no_bytes_in_this_capture(tmp_path):
    p=tmp_path/"passive.pcapng"
    p.write_bytes(capture([
        packet("10.0.0.5","10.0.0.7",51000,10230,100,b"",2),
        packet("10.0.0.7","10.0.0.5",10230,51000,500,b"\x01\0\0\0\x08\0\0\0"),
    ]))
    report=audit.analyze(p)
    flow=report["flows"][0]
    assert flow["no_client_payload_observed"]
    assert not flow["exact_setrate_detected"]
    assert "observed" in report["conclusion"]
    assert "cannot be determined" in report["limitation"]


def test_broken_block_and_unsupported_capture_refused(tmp_path):
    p=tmp_path/"broken.pcapng"
    data=bytearray(capture([]))
    data[-1]=255
    p.write_bytes(data)
    with pytest.raises(ValueError,match="length mismatch"):
        audit.analyze(p)
    p.write_bytes(b"junk")
    with pytest.raises(ValueError,match="supported PCAP"):
        audit.analyze(p)
