"""Synthetic physical WriteData: independent RAW replay and reopened BIN."""
from hashlib import sha256
import json
import struct
import numpy as np
import pytest
from .test_stage111z31fs_original_live_writer_e2e import with_live_writer
from ..core.original_write_data_live_gate import AUDIT,verify_native_live_write_data
from ..core.original_param_gate_proof import SOURCE_PARAM_GATE_NAME,SOURCE_PARAM_GATE_SCHEMA
from ..core.original_values_3100_timeline import PARAM
from ..core.original_physical_write_replay import PhysicalWriteReplay,PHYSICAL_SCHEMA
from ..core.original_mode2_source_files import write_verified_source_tsxml_sidecars
from ..core.direct_bin_session import DirectBinSession


def test_latched_range_uses_first_descriptor_not_later_or_frozen():
    model=PhysicalWriteReplay()
    two=struct.pack("<f",2)
    assert model.chunk(1,two)==two
    model.on_param([],False)
    model.on_param([(0x10e,2,struct.pack("<f",4)),
                    (0x20e,2,struct.pack("<f",3))],False)
    assert model.chunk(1,two)==struct.pack("<f",8)
    assert model.chunk(2,two) is None
    model.on_param([(0x10e,2,struct.pack("<f",9))],False)
    assert model.chunk(1,two)==struct.pack("<f",8)
    assert model.chunk(1,struct.pack("<f",float("nan"))) is None
    frozen=PhysicalWriteReplay()
    frozen.on_param([(0x10e,2,struct.pack("<f",4))],True)
    assert frozen.chunk(1,two) is None
    frozen.on_param([(0x10e,2,struct.pack("<f",4))],False)
    assert frozen.chunk(1,two) is None
    zero=PhysicalWriteReplay()
    zero.on_param([(0x10e,2,struct.pack("<f",0))],False)
    assert zero.chunk(1,two)==two


def _physical_run(tmp_path):
    run,_,_=with_live_writer(tmp_path)
    raw=(run/"incoming.raw").read_bytes()
    frames=[]
    i=0
    while i<len(raw):
        n=struct.unpack_from("<I",raw,i+4)[0]
        frames.append(raw[i:i+n]);i+=n
    def cfg(value):
        data=struct.pack("<f",value)+b"V".ljust(32,b"\x00")
        block=struct.pack("<HH",0x10e,18)+data
        return struct.pack("<II",PARAM,28+len(block))+b"\x00"*16+struct.pack("<I",1)+block
    for index,value in ((0,4),(9,7),(18,9),(19,8)):
        frames[index]=cfg(value)
    raw=b"".join(frames)
    digest=sha256(raw).hexdigest()
    (run/"incoming.raw").write_bytes(raw)
    events=[dict(schema=SOURCE_PARAM_GATE_SCHEMA,
        frame_index_one_based=i+1,frame_sha256=sha256(frames[i]).hexdigest(),
        descriptor_count=1,freeze_update=i==9,is_aux4700=False,
        contains_values_3100=False) for i in (0,9,18,19)]
    gate=b"".join((json.dumps(e)+"\n").encode() for e in events)
    (run/SOURCE_PARAM_GATE_NAME).write_bytes(gate)
    audit=json.loads((run/AUDIT).read_text())
    audit.update(source_raw_sha256=digest,physical_writer_schema=PHYSICAL_SCHEMA)
    for item in audit["windows"][0]["files"]:
        ch=item["channel"]
        name=f"SOURCE_W01_ADC{ch}_LIVE_PHYSICAL_CANDIDATE.bin"
        # Only ADC1 is known in the first descriptor. Expected bytes are
        # computed independently with struct, not the implementation under test.
        wire=(run/item["name"]).read_bytes()
        physical=b"".join(struct.pack("<f",v[0]*4) for v in
            struct.iter_unpack("<f",wire)) if ch==1 else b""
        (run/name).write_bytes(physical)
        item["physical_candidate"]=dict(name=name,bytes=len(physical),
            packets=int(ch==1),skipped_packets=int(ch!=1),
            sha256=sha256(physical).hexdigest())
    doc=json.dumps(audit).encode()
    (run/AUDIT).write_bytes(doc)
    summary=json.loads((run/"summary.json").read_text())
    summary.update(raw_sha256=digest,raw_bytes=len(raw),
        source_live_write_data_audit_sha256=sha256(doc).hexdigest(),
        source_original_param_gate_sha256=sha256(gate).hexdigest(),
        source_original_param_gate_records=len(events))
    return run,summary,audit


def test_physical_candidate_replay_and_reopen_without_second_gain(tmp_path):
    run,summary,audit=_physical_run(tmp_path)
    proof=verify_native_live_write_data(run,summary=summary,
        source_raw_sha256=summary["raw_sha256"])
    assert len(proof["verified_channel_files"])==8
    assert len(proof["verified_physical_channel_files"])==1
    assert len(proof["skipped_physical_channel_files"])==7
    item=proof["verified_physical_channel_files"][0]
    assert item["source_close_config"]["gain"]==9
    assert item["physical_raw_replay_verified"]
    assert not item["original_delphi_file_parity_verified"]
    payload=(run/item["name"]).read_bytes()
    wire=(run/item["wire_name"]).read_bytes()
    assert payload!=wire
    assert payload==b"".join(struct.pack("<f",v[0]*4)
        for v in struct.iter_unpack("<f",wire))
    receipts=write_verified_source_tsxml_sidecars(run,
        live_proof=dict(proof,verified_channel_files=[item]),
        source_run_end_utc="2026-11-24T10:00:00Z")
    assert receipts[0]["sidecar_created"]
    session=DirectBinSession.open(run/item["name"])
    samples,fs,info,_=session.samples(1)
    assert fs==65536
    np.testing.assert_array_equal(samples,np.frombuffer(payload,dtype="<f4"))
    assert info["metadata_gain_was_applied_to_bin_samples"] is False
    assert info["declared_internal_channel_gain_single"]==9


def test_forged_physical_hash_still_refused(tmp_path):
    run,summary,audit=_physical_run(tmp_path)
    item=audit["windows"][0]["files"][0]
    part=item["physical_candidate"]
    path=run/part["name"]
    data=(run/item["name"]).read_bytes()  # forged unscaled data
    path.write_bytes(data)
    part["sha256"]=sha256(data).hexdigest()
    doc=json.dumps(audit).encode()
    (run/AUDIT).write_bytes(doc)
    summary["source_live_write_data_audit_sha256"]=sha256(doc).hexdigest()
    with pytest.raises(ValueError,match="processed bytes differ"):
        verify_native_live_write_data(run,summary=summary,
            source_raw_sha256=summary["raw_sha256"])
