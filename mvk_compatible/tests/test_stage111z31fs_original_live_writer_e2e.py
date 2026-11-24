"""Stage111Z31FS: native Go live WriteData proof checked against full RAW.

Synthetic only; no vendor binaries, real MVK01 or device commands.
"""
from __future__ import annotations

from hashlib import sha256
from xml.etree import ElementTree as ET
import json
import struct
from pathlib import Path

import pytest

from .test_stage111z31fr_marked_source_wire_e2e import _marked_wire_run
from ..core.original_live_write_stages import (
    EXPORT_SUBDIR,export_source_write_windows,
)
from ..core.original_write_data_live_gate import (
    AUDIT,PACKETS,SCHEMA,verify_native_live_write_data,
)


def with_live_writer(tmp_path):
    run,flow,ledger=_marked_wire_run(tmp_path)
    original=(run/"incoming.raw").read_bytes()
    frames=[]
    offset=0
    while offset<len(original):
        typ,length=struct.unpack_from("<II",original,offset)
        assert length>=8 and length%4==0
        frames.append(original[offset:offset+length])
        offset+=length
    assert offset==len(original) and len(frames)==20
    assert [struct.unpack_from("<I",fr)[0] for fr in frames[10:18]]==[
        0xFF800ADC]*8
    summary=json.loads((run/"summary.json").read_text())
    sha=summary["raw_sha256"]
    files=[]
    receipts=[]
    for i in range(8):
        channel=i+1
        frame=frames[10+i]
        payload=frame[28:]
        name=f"SOURCE_W01_ADC{channel}_LIVE_RX_UNSCALED.bin"
        (run/name).write_bytes(payload)
        digest=sha256(payload).hexdigest()
        files.append({
            "channel":channel,
            "name":name,
            "bytes":len(payload),
            "packets":1,
            "sha256":digest,
        })
        receipts.append({
            "frame_index":11+i,
            "window":1,
            "channel":channel,
            "sample_words":len(payload)//4,
            "rx_sample_before":256,
            "rx_sample_after":512,
            "source_selected_rate_hz":65536,
            "received_rate_hz":65536,
            "freeze_update":False,
            "source_ring_store_allowed":True,
            "write_data_stage_before":0 if i==0 else 1,
            "write_data_stage_after":1,
            "channel_selected":True,
            "wrote_source_bytes":True,
            "rx_payload_sha256":digest,
        })
    gates=b"".join((json.dumps(item,ensure_ascii=False,separators=(",",":"))+
                    "\n").encode() for item in receipts)
    (run/PACKETS).write_bytes(gates)
    audit={
        "schema":SCHEMA,
        "session_id":run.name,
        "source_raw_sha256":sha,
        "end_frames_decoded":20,
        "end_channel_samples":[512]*8+[0,0],
        "end_reason":"STOPPED_BY_USER",
        "packet_gate_file":PACKETS,
        "packet_gate_sha256":sha256(gates).hexdigest(),
        "packet_gate_records":8,
        "windows":[{
            "window":1,
            "begin_operator_sequence":1,
            "end_operator_sequence":2,
            "begin_before_frame":10,
            "end_after_frame":19,
            "first_accepted_adc1_frame":11,
            "stage_at_end":1,
            "outcome":"CLOSED_BY_OPERATOR",
            "channels":[True]*8+[False,False],
            "written_packets":8,
            "skipped_rate_packets":0,
            "skipped_frozen_packets":0,
            "skipped_before_adc1_packets":0,
            "files":files,
        }],
        "original_delphi_file_parity_verified":False,
        "live_source_rate_freeze_recorded":True,
        "original_win32_click_timing_verified":False,
    }
    doc=(json.dumps(audit,ensure_ascii=False,indent=2)+"\n").encode()
    (run/AUDIT).write_bytes(doc)
    summary.update(
        end_reason="STOPPED_BY_USER",
        ended_utc="2026-11-18T12:17:00Z",
        source_live_write_data_audit_sha256=sha256(doc).hexdigest(),
        source_live_write_data_windows=1,
        source_live_write_data_packet_records=8,
    )
    (run/"summary.json").write_text(json.dumps(summary),encoding="utf-8")
    return run,flow,ledger


def test_original_live_gate_export_byte_exact_and_non_delphi_label(tmp_path):
    run,flow,ledger=with_live_writer(tmp_path)
    summary=json.loads((run/"summary.json").read_text())
    proof=verify_native_live_write_data(
        run,summary=summary,source_raw_sha256=summary["raw_sha256"])
    assert proof is not None
    assert proof["verified_source_packet_records"]==8
    assert proof["verified_source_windows"]==1
    assert len(proof["verified_channel_files"])==8
    assert proof["original_delphi_file_parity_verified"] is False
    result=export_source_write_windows(ledger,flow,run)
    assert result["verified_frame_boundaries"]
    assert result["source_live_source_gate_verified"] is True
    assert result["source_live_original_writer_files"]==8
    assert result["source_live_original_packet_gate_records"]==8
    assert result["source_original_tsxml_structural_sidecars"]==8
    assert result["source_original_filename_algorithm_recovered"] is True
    assert result["source_original_tsxml_delphi_full_parity_verified"] is False
    output=run/EXPORT_SUBDIR
    for item in proof["verified_channel_files"]:
        original=(run/item["name"]).read_bytes()
        copied=(output/item["name"]).read_bytes()
        assert original==copied
        assert len(copied)==1024
        assert sha256(copied).hexdigest()==item["sha256"]
        xml=output/(item["name"]+".tsxml")
        assert xml.exists() and xml.read_bytes().startswith(b'<?xml')
        docxml=ET.parse(xml)
        assert docxml.findtext("DataFileName")==".\\"+item["name"]
        assert docxml.findtext("Channels/Channel/DataLength")==str(len(copied))
        assert docxml.findtext("Channels/Channel/RealDataType")=="Single"
    rec=json.loads((output/"SOURCE_WRITE_WINDOWS_AUDIT.json").read_text())
    assert rec["source_live_source_gate_verified"] is True
    assert rec["original_tmkvthread_byte_exact_recording"] is False
    assert rec["source_live_original_writer_evidence"][
        "original_win32_click_timing_verified"] is False


@pytest.mark.parametrize("mutator",[
    lambda run,s,a: (run/"SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin").write_bytes(
        (run/"SOURCE_W01_ADC1_LIVE_RX_UNSCALED.bin").read_bytes()[:-1]+b"Q"),
    lambda run,s,a: a["windows"][0].update(first_accepted_adc1_frame=10),
    lambda run,s,a: a["windows"][0]["files"][0].update(bytes=1000),
    lambda run,s,a: a.update(original_delphi_file_parity_verified=True),
    lambda run,s,a: s.update(source_tcp_multi_socket=True),
    lambda run,s,a: s.update(source_live_write_data_packet_records=9),
])
def test_forged_native_writer_or_sample_bytes_fail_closed(tmp_path,mutator):
    run,flow,ledger=with_live_writer(tmp_path)
    summary=json.loads((run/"summary.json").read_text())
    document=json.loads((run/AUDIT).read_text())
    mutator(run,summary,document)
    reserialized=(json.dumps(document,indent=2,ensure_ascii=False)+"\n").encode()
    (run/AUDIT).write_bytes(reserialized)
    summary["source_live_write_data_audit_sha256"]=sha256(reserialized).hexdigest()
    (run/"summary.json").write_text(json.dumps(summary))
    with pytest.raises(ValueError):
        export_source_write_windows(ledger,flow,run)
    assert not (run/EXPORT_SUBDIR).exists()


def test_source_writer_gate_mismatch_is_rejected_after_forging_all_hashes(tmp_path):
    run,flow,ledger=with_live_writer(tmp_path)
    # Recompute the packet log SHA, writer-audit SHA and summary SHA so
    # SHA-only checks would pass: the independent RAW/Go state check must
    # still reject the impossible first-ADC1 transition.
    lines=(run/PACKETS).read_text().splitlines()
    line=json.loads(lines[0]);line["wrote_source_bytes"]=False
    lines[0]=json.dumps(line,separators=(",",":"))
    data=("\n".join(lines)+"\n").encode()
    (run/PACKETS).write_bytes(data)
    audit=json.loads((run/AUDIT).read_text())
    audit["packet_gate_sha256"]=sha256(data).hexdigest()
    doc=(json.dumps(audit,indent=2)+"\n").encode()
    (run/AUDIT).write_bytes(doc)
    summary=json.loads((run/"summary.json").read_text())
    summary["source_live_write_data_audit_sha256"]=sha256(doc).hexdigest()
    (run/"summary.json").write_text(json.dumps(summary))
    with pytest.raises(ValueError,match="packet gate/RAW discrepancy"):
        verify_native_live_write_data(
            run,summary=summary,source_raw_sha256=summary["raw_sha256"])


def test_intentionally_interrupted_thread_is_not_accepted_writer(tmp_path):
    run,flow,ledger=with_live_writer(tmp_path)
    audit=json.loads((run/AUDIT).read_text())
    audit["windows"][0]["outcome"]="INTERRUPTED"
    doc=(json.dumps(audit,indent=2)+"\n").encode()
    (run/AUDIT).write_bytes(doc)
    summary=json.loads((run/"summary.json").read_text())
    summary["source_live_write_data_audit_sha256"]=sha256(doc).hexdigest()
    (run/"summary.json").write_text(json.dumps(summary))
    with pytest.raises(ValueError,match="interrupted"):
        verify_native_live_write_data(
            run,summary=summary,source_raw_sha256=summary["raw_sha256"])

def test_close_metadata_replays_only_through_actual_writer_end_and_ignores_frozen_param(tmp_path):
    from ..core.original_param_gate_proof import SOURCE_PARAM_GATE_NAME,SOURCE_PARAM_GATE_SCHEMA
    from ..core.original_values_3100_timeline import PARAM
    run,flow,ledger=with_live_writer(tmp_path)
    original=(run/"incoming.raw").read_bytes()
    frames=[]
    pos=0
    while pos<len(original):
        n=struct.unpack_from("<I",original,pos+4)[0]
        frames.append(original[pos:pos+n]);pos+=n
    def cfg(value):
        payload=struct.pack("<f",value)+b"V".ljust(32,b"\x00")
        block=struct.pack("<HH",0x10e,18)+payload
        return struct.pack("<II",PARAM,28+len(block))+b"\x00"*16+struct.pack("<I",1)+block
    frames[0]=cfg(2.5)
    frames[9]=cfg(9.0) # frozen
    frames[18]=cfg(4.0) # close after frame 19
    frames[19]=cfg(8.0) # after close, must not leak backwards
    raw=b"".join(frames);digest=sha256(raw).hexdigest()
    (run/"incoming.raw").write_bytes(raw)
    events=[]
    for idx in (0,9,18,19):
        events.append(dict(schema=SOURCE_PARAM_GATE_SCHEMA,
            frame_index_one_based=idx+1,frame_sha256=sha256(frames[idx]).hexdigest(),
            descriptor_count=1,freeze_update=idx==9,is_aux4700=False,
            contains_values_3100=False))
    gate=b"".join((json.dumps(x)+"\n").encode() for x in events)
    (run/SOURCE_PARAM_GATE_NAME).write_bytes(gate)
    audit=json.loads((run/AUDIT).read_text())
    audit["source_raw_sha256"]=digest
    encoded=json.dumps(audit).encode()
    (run/AUDIT).write_bytes(encoded)
    summary=json.loads((run/"summary.json").read_text())
    summary.update(raw_sha256=digest,raw_bytes=len(raw),
        source_live_write_data_audit_sha256=sha256(encoded).hexdigest(),
        source_original_param_gate_sha256=sha256(gate).hexdigest(),
        source_original_param_gate_records=len(events))
    proof=verify_native_live_write_data(run,summary=summary,source_raw_sha256=digest)
    meta=proof["verified_channel_files"][0]["source_close_config"]
    assert meta["gain"]==4.0 and meta["units"]=="V"
    assert meta["end_after_frame"]==19
    assert proof["verified_channel_files"][1]["source_close_config"]["gain"] is None
    # Change the Freeze ledger without changing its authenticated SHA.
    (run/SOURCE_PARAM_GATE_NAME).write_bytes(gate.replace(b'"freeze_update": true',b'"freeze_update":false'))
    with pytest.raises(ValueError):
        verify_native_live_write_data(run,summary=summary,source_raw_sha256=digest)
