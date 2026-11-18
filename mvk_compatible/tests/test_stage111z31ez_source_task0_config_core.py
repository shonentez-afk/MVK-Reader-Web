"""Original Task0 IP config download: synthetic RAW, no real industrial TCP."""
from __future__ import annotations

from hashlib import sha256
import json
import struct

import pytest

from ..core.original_task0_config_live import (
    SourceTask0DownloadSpec,SCHEMA,FILENAME,SOURCE_MODE,END_REASON,
    _safe_specs,load_source_task0_config,
)


def _fake_task0_run(tmp_path):
    root=tmp_path/"mvk_task0_session_mock"
    run=root/"TEST_2026-11-17_13-00-00.001"
    run.mkdir(parents=True)
    # PARAM at 0004 of 12 UInt16 words. Not a real MVK device payload.
    payload=bytes(range(24))
    frame=(struct.pack("<II",0xFF800C0D,56)+bytes(16)
           +struct.pack("<I",1)+struct.pack("<I",(12<<16)|4)+payload)
    (run/"incoming.raw").write_bytes(frame)
    digest=sha256(frame).hexdigest()
    original={
        "mode":SOURCE_MODE,"end_reason":END_REASON,
        "read_only_no_app_payload_sent":True,
        "capture_only_after_parser_error":False,
        "target_ipv4":"192.168.0.30",
        "raw_bytes":len(frame),"raw_sha256":digest,
        "source_rx_nonempty_parameter_frames":1,
        "incomplete_final_frame_bytes":0,
    }
    (run/"summary.json").write_text(json.dumps(original),encoding="utf-8")
    fields=[]
    count=0
    for key,addr,words in _safe_specs():
        valid=addr>=4 and addr+words<=16
        fields.append({
            "key":key,"register_address":addr,"word_count":words,
            "valid":valid,
            "raw_hex_le":payload[(addr-4)*2:(addr-4+words)*2].hex()
            if valid else None,
        })
        count+=int(valid)
    snap={
        "schema":SCHEMA,"original_task":0,"session_id":run.name,
        "instrument_ipv4":"192.168.0.30",
        "source_raw_sha256":digest,
        "raw_bytes":len(frame),"device_commands_not_sent":True,
        "source_nonempty_param_received":True,
        "config_fields_confirmed":count,
        "original_delphi_byte_parity_verified":False,
        "fields":fields,
    }
    (run/FILENAME).write_text(json.dumps(snap),encoding="utf-8")
    return root,run,original,snap


def test_source_task0_native_argv_ensures_approved_passive_read_only(tmp_path):
    spec=SourceTask0DownloadSpec(
        "192.168.0.30","192.168.0.31",tmp_path)
    root=spec.create_root()
    argv=spec.native_args(root)
    assert argv[argv.index("-seconds")+1]=="20"
    assert argv[argv.index("-source-task0-config-read=true")]=="-source-task0-config-read=true"
    for key in ("-approve=true","-live-status=true","-export=false",
                "-source-task0-config-read=true"):
        assert key in argv
    assert "-stop-file" in argv and argv[-1].endswith(".mvk_stop_requested")
    assert not any("setrate" in x.lower() or "reconnect" in x.lower()
                   or "flash" in x.lower() or "reboot" in x.lower()
                   for x in argv)


def test_task0_shows_only_sha_verified_receipt_fields(tmp_path):
    root,_,_,_= _fake_task0_run(tmp_path)
    proof=load_source_task0_config(root,expected_ip="192.168.0.30")
    assert proof["source_original_task"]==0
    assert proof["read_only"] and not proof["device_commands_sent"]
    assert proof["confirmed_fields"]>=4
    assert proof["fields"]["ConfigIP"]["raw_hex_le"]=="00010203"
    assert not proof["fields"]["ConfigWifiMode"]["valid"]
    assert "ConfigWifiSSID" not in proof["fields"]
    assert "ConfigWifiPassword" not in proof["fields"]


@pytest.mark.parametrize("mutation",[
    "raw","sha","source_mode","outbound","field","field_count",
    "original_task","secret","param",
])
def test_task0_rejects_contradicted_device_provenance(tmp_path,mutation):
    root,run,summary,snap=_fake_task0_run(tmp_path)
    if mutation=="raw":
        (run/"incoming.raw").write_bytes(b"CHANGED")
    elif mutation=="sha":
        summary["raw_sha256"]="0"*64
    elif mutation=="source_mode":
        summary["mode"]="LIVE_SOURCE_SET_RATE_APPROVED"
    elif mutation=="outbound":
        summary["read_only_no_app_payload_sent"]=False
    elif mutation=="field":
        snap["fields"][0]["raw_hex_le"]="BADC0DE"
    elif mutation=="field_count":
        snap["config_fields_confirmed"]+=1
    elif mutation=="original_task":
        snap["original_task"]=3
    elif mutation=="secret":
        snap["fields"][0]["key"]="ConfigWifiPassword"
    elif mutation=="param":
        summary["source_rx_nonempty_parameter_frames"]=0
    (run/"summary.json").write_text(json.dumps(summary),encoding="utf-8")
    (run/FILENAME).write_text(json.dumps(snap),encoding="utf-8")
    with pytest.raises(ValueError):
        load_source_task0_config(root,expected_ip="192.168.0.30")


def test_task0_requires_same_operator_ipv4_and_one_run(tmp_path):
    root,_,_,_=_fake_task0_run(tmp_path)
    with pytest.raises(ValueError):
        load_source_task0_config(root,expected_ip="192.168.0.32")
    another=root/"TEST_2026-11-17_13-00-00.002"
    another.mkdir()
    (another/FILENAME).write_text("{}")
    with pytest.raises(ValueError,match="ровно один"):
        load_source_task0_config(root,expected_ip="192.168.0.30")


@pytest.mark.parametrize("duration",[0,61,True,"20"])
def test_task0_rejects_unbounded_timeout(tmp_path,duration):
    with pytest.raises(ValueError,match="Task0"):
        SourceTask0DownloadSpec(
            "192.168.0.30","192.168.0.31",tmp_path,
            seconds=duration).validate()


def test_original_task0_idp_ip_netmask_and_port_text_preserves_raw():
    from ..core.original_task0_config_live import original_task0_field_text
    raw={"valid":True,"raw_hex_le":"01020304"}
    assert original_task0_field_text("ConfigIP",raw)=="4.3.2.1"
    assert original_task0_field_text("ConfigNetmask",raw)=="4.3.2.1"
    assert original_task0_field_text("ConfigGateway",raw)=="4.3.2.1"
    assert original_task0_field_text("ConfigWifiIP",raw)=="4.3.2.1"
    assert original_task0_field_text("ConfigModbusPort",raw)=="67305985"
    # Numeric source GetDword decodes 01 02 03 04 as 0x04030201.
    # Missing original selector ID uses the exact (0xXXXXXXXX) fallback.
    assert original_task0_field_text("ConfigOption",raw)==(
        "0x04030201 · (0x04030201)")
    assert original_task0_field_text(
        "ConfigWifiPassword",raw)=="•••••••• (скрыто)"
    assert original_task0_field_text("ConfigIP",{
        "valid":False,"raw_hex_le":None})=="—"
    with pytest.raises(ValueError):
        original_task0_field_text("ConfigIP",{"valid":True,"raw_hex_le":"0000"})


def test_original_task0_default_config_basename_is_source_fixed(tmp_path):
    from ..core.original_task0_config_live import (
        SOURCE_DEFAULT_CONFIG_FILENAME,source_original_default_config_path,
    )
    executable=tmp_path/"MVKViewCompatible.exe"
    assert SOURCE_DEFAULT_CONFIG_FILENAME=="DefaultConfig.txt"
    assert source_original_default_config_path(executable)==(
        tmp_path/"DefaultConfig.txt")
    assert source_original_default_config_path(
        tmp_path/"ApplicationPreview.exe").name=="DefaultConfig.txt"
