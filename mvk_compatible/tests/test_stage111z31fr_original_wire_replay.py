"""Original Stage111Z31FR wire payload replay; no hardware involved."""
from __future__ import annotations

from hashlib import sha256
import struct

import pytest

from ..core.original_write_data_wire_replay import (
    TYPE_ADC, TYPE_TACH, TYPE_PARAM, export_source_wire_write_intervals,
)


def sample(kind,channel,rate,words,sequence=0):
    b=b"".join(struct.pack("<I",word) for word in words)
    return (struct.pack("<IIIIIII",kind,28+len(b),
                        0,sequence,0,channel,rate) + b)


def param():
    # Well-framed minimal PARAM with one 2-word source descriptor.
    return (struct.pack("<IIIIIII",TYPE_PARAM,36,0,0,0,0,1)
            + struct.pack("<II",2<<16|0x3100,0))


def session(tmp_path):
    p=[
        struct.pack("<II",1,8),
        sample(TYPE_ADC,0,65536,[0x3F800000,0x40000000,0x40400000],0),
        sample(TYPE_TACH,8,65536,[0x12020304,0x25060708],0),
        param(),
        sample(TYPE_ADC,0,65536,[0x40800000,0x40A00000],3),
        sample(TYPE_ADC,1,65536,[0x3F000000],0),
        struct.pack("<IIII",0xDEADBEEF,16,0,0),
    ]
    tail=b"XYZ"
    raw=b"".join(p)+tail
    file=tmp_path/"incoming.raw"
    file.write_bytes(raw)
    args=dict(
        expected_sha256=sha256(raw).hexdigest(),
        expected_raw_bytes=len(raw),
        expected_frames=len(p),
        expected_tail_bytes=len(tail),
        expected_channel_samples=[5,1]+[0]*6+[2,0],
    )
    out=tmp_path/"verified_exports"
    out.mkdir()
    return file,out,args


def test_original_wire_adc_tach_cuts_are_byte_for_byte_original(tmp_path):
    file,out,args=session(tmp_path)
    cuts=[(1,1,1,4),(1,9,0,2),(2,1,4,5),(1,2,0,1)]
    result=export_source_wire_write_intervals(
        file,out,**args,cuts=cuts)
    assert len(result)==4
    expected=struct.pack("<III",0x40000000,0x40400000,0x40800000)
    actual=(out/"DATA01_ADC1_WIRE_RX_UNSCALED.bin").read_bytes()
    assert actual==expected
    assert (out/"DATA01_TACH1_WIRE_RX_UNSCALED.bin").read_bytes()==(
        struct.pack("<II",0x12020304,0x25060708))
    assert (out/"DATA02_ADC1_WIRE_RX_UNSCALED.bin").read_bytes()==(
        struct.pack("<I",0x40A00000))
    assert (out/"DATA01_ADC2_WIRE_RX_UNSCALED.bin").read_bytes()==(
        struct.pack("<I",0x3F000000))
    for proof in result:
        assert proof["original_rx_payload_bytes_exact"] is True
        assert proof["original_delphi_bin_parity_verified"] is False
        assert proof["source_delphi_rate_freeze_gate_parity_verified"] is False
        assert proof["source_raw_sha256"]==args["expected_sha256"]
        data=(out/proof["name"]).read_bytes()
        assert proof["sha256"]==sha256(data).hexdigest()


@pytest.mark.parametrize("change",(
    lambda p,a:p.write_bytes(p.read_bytes()[:-1]+b"Q"),
    lambda p,a:a.update(expected_raw_bytes=a["expected_raw_bytes"]+1),
    lambda p,a:a.update(expected_frames=a["expected_frames"]-1),
    lambda p,a:a.update(expected_channel_samples=[6,1]+[0]*6+[2,0]),
    lambda p,a:a.update(expected_tail_bytes=1),
    lambda p,a:a.update(expected_sha256="f"*64),
))
def test_write_data_raw_or_go_counter_tampering_fails(tmp_path,change):
    file,out,args=session(tmp_path)
    change(file,args)
    with pytest.raises(ValueError):
        export_source_wire_write_intervals(
            file,out,**args,cuts=[(1,1,0,5)])


def test_source_wire_rejects_invalid_masks_and_channel(tmp_path):
    file,out,args=session(tmp_path)
    for invalid in [[(1,0,0,1)],[(1,11,0,1)],
                    [(1,1,1,1)],[(1,1,0,6)],
                    [(1,1,0,3),(1,1,3,5)]]:
        with pytest.raises(ValueError):
            export_source_wire_write_intervals(
                file,out,**args,cuts=invalid)


def test_original_payload_constrained_by_channel_sample_count(tmp_path):
    file,out,args=session(tmp_path)
    data=file.read_bytes()
    old=sample(TYPE_TACH,8,65536,[0x12020304,0x25060708],0)
    fake=sample(TYPE_TACH,7,65536,[0x12020304,0x25060708],0)
    file.write_bytes(data.replace(old,fake))
    args["expected_sha256"]=sha256(file.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match="channel/rate"):
        export_source_wire_write_intervals(
            file,out,**args,cuts=[(1,1,0,5)])
