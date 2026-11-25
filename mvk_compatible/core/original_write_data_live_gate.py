"""Stage111Z31FS — independent verification of original live WriteData.

Go performs source _Unit125:0080822F..008082DE writes AT RECEIVE TIME,
after rate/freeze checks and the first matching ADC1. This module
independently replays the unchanged SHA-checked RAW and verifies every
Go packet-gate receipt, selected channel byte and resulting local file.
No Delphi file-name / click-microsecond / tsxml parity is claimed.
"""
from __future__ import annotations

from contextlib import ExitStack
from hashlib import sha256
from pathlib import Path
import json
import re
import struct

from .original_param_gate_proof import OriginalParamGateReader,SOURCE_PARAM_GATE_NAME
from .original_values_3100_timeline import _parameter_blocks,PARAM
from .original_mode2_close_metadata import CloseConfigReplay
from .original_physical_write_replay import PhysicalWriteReplay, PHYSICAL_SCHEMA

SCHEMA="MVK_SOURCE_TMVKTHREAD_LIVE_WRITEDATA_V1"
AUDIT="SOURCE_LIVE_WRITEDATA_NATIVE_AUDIT.json"
PACKETS="SOURCE_LIVE_WRITEDATA_PACKET_GATE.jsonl"
RATES=frozenset((512,2048,8192,32768,65536))
TYPES=(0xFF800ADC,0xFF8001AC)
MAX_FRAME=0x20000
MAX_WINDOWS=8
MAX_JSON=65536
MAX_RAW=2*1024**3
HEXDIGEST=re.compile(r"[a-f0-9]{64}\Z")


def _integer(value,name,top=(1<<64)-1):
    if type(value) is not int or not 0<=value<=top:
        raise ValueError("Original native WriteData: invalid "+name)
    return value


def _digest(value,name):
    if not isinstance(value,str) or not HEXDIGEST.fullmatch(value):
        raise ValueError("Original native WriteData: invalid SHA for "+name)
    return value


def _local_file(parent:Path,name:str,*,max_bytes:int|None=None)->Path:
    if (not isinstance(name,str) or not name or
            name!=Path(name).name or name in (".","..") or
            "/" in name or "\\" in name or "\x00" in name):
        raise ValueError("Original native WriteData: unsafe local filename")
    p=parent/name
    if p.is_symlink() or not p.is_file():
        raise ValueError("Original native WriteData: absent or linked file "+name)
    if max_bytes is not None and p.stat().st_size>max_bytes:
        raise ValueError("Original native WriteData: oversized "+name)
    return p


def verify_native_live_write_data(
        run:Path|str, *, summary:dict,
        source_raw_sha256:str,
)->dict|None:
    """Verify actual Go source writer files + exact packet-wise RAW linkage.

    None means the older capture had no source-side WriteData audit.
    If the SHA is present, ANY missing/tampered event/file causes an
    error rather than falling back to an ungated reconstructed BIN.
    """
    folder=Path(run)
    if folder.is_symlink() or not folder.is_dir() or not isinstance(summary,dict):
        raise ValueError("Original native WriteData: unsafe source run")
    source_digest=_digest(source_raw_sha256,"source RAW")
    stated=summary.get("source_live_write_data_audit_sha256")
    if stated is None:
        return None
    stated=_digest(stated,"Go native writer receipt")
    path=_local_file(folder,AUDIT,max_bytes=1024*1024)
    audit_bytes=path.read_bytes()
    if sha256(audit_bytes).hexdigest()!=stated:
        raise ValueError("Original native WriteData: Go audit SHA mismatch")
    try:
        audit=json.loads(audit_bytes)
    except (ValueError,UnicodeError) as exc:
        raise ValueError("Original native WriteData: invalid Go audit JSON") from exc
    if (not isinstance(audit,dict) or audit.get("schema")!=SCHEMA
            or audit.get("session_id")!=folder.name
            or audit.get("source_raw_sha256")!=source_digest
            or summary.get("raw_sha256")!=source_digest
            or audit.get("end_frames_decoded")!=summary.get("frames_decoded")
            or audit.get("end_reason")!=summary.get("end_reason")
            or audit.get("original_delphi_file_parity_verified") is not False
            or audit.get("original_win32_click_timing_verified") is not False
            or audit.get("live_source_rate_freeze_recorded") is not True
            or summary.get("source_tcp_multi_socket",False) is True
            or summary.get("capture_only_after_parser_error",False) is True):
        raise ValueError("Original native WriteData: Go run/provenance mismatch")
    physical_schema=audit.get("physical_writer_schema")
    if physical_schema not in (None,PHYSICAL_SCHEMA):
        raise ValueError("Source physical WriteData: unknown schema")
    physical_enabled=physical_schema==PHYSICAL_SCHEMA
    raw_len=_integer(summary.get("raw_bytes"),"RAW byte count",MAX_RAW)
    raw_frames=_integer(summary.get("frames_decoded"),"frame count",raw_len//8)
    raw_tail=_integer(summary.get("incomplete_final_frame_bytes"),"RAW tail",MAX_FRAME-1)
    channels=summary.get("channels")
    expected_counts= audit.get("end_channel_samples")
    if (not isinstance(channels,list) or len(channels)!=10 or
            not isinstance(expected_counts,list) or len(expected_counts)!=10):
        raise ValueError("Original native WriteData: missing Go channel banks")
    for i,(ch,n) in enumerate(zip(channels,expected_counts)):
        if (not isinstance(ch,dict) or
                _integer(ch.get("samples"),f"source channel {i+1}")!=
                _integer(n,f"native writer channel {i+1}")):
            raise ValueError("Original native WriteData: final channel counter mismatch")
    packet_path=_local_file(folder,audit.get("packet_gate_file"))
    if packet_path.name!=PACKETS:
        raise ValueError("Original native WriteData: unexpected packet gate file")
    packet_digest=_digest(audit.get("packet_gate_sha256"),"packet gate")
    packet_total=_integer(audit.get("packet_gate_records"),"packet count",raw_frames)
    if packet_total!=_integer(summary.get("source_live_write_data_packet_records"),
                             "summary packet count",raw_frames):
        raise ValueError("Original native WriteData: source packet count mismatch")
    windows=audit.get("windows")
    if (not isinstance(windows,list) or not 1<=len(windows)<=MAX_WINDOWS
            or len(windows)!=summary.get("source_live_write_data_windows")):
        raise ValueError("Original native WriteData: source window count mismatch")
    checks=[]
    last_end=0
    for i,window in enumerate(windows,1):
        if not isinstance(window,dict) or window.get("window")!=i:
            raise ValueError("Original native WriteData: nonsequential window")
        start=_integer(window.get("begin_before_frame"),"window start",raw_frames)
        end=_integer(window.get("end_after_frame"),"window end",raw_frames)
        if start<last_end or end<start:
            raise ValueError("Original native WriteData: overlapping writer windows")
        last_end=end
        masks=window.get("channels")
        if (not isinstance(masks,list) or len(masks)!=10 or
                not all(type(v) is bool for v in masks) or not any(masks)):
            raise ValueError("Original native WriteData: invalid selected source masks")
        if window.get("outcome") not in (
                "CLOSED_BY_OPERATOR","CLOSED_BY_SOURCE_THREAD"):
            raise ValueError("Original native WriteData: interrupted/not closed")
        if (window["outcome"]=="CLOSED_BY_SOURCE_THREAD" and
                summary.get("end_reason") not in (
                    "STOPPED_BY_USER","DURATION_REACHED","SIZE_LIMIT_REACHED")):
            raise ValueError("Original native WriteData: false clean source close")
        if window.get("stage_at_end") not in (0,1):
            raise ValueError("Original native WriteData: invalid write stage")
        files=window.get("files")
        if not isinstance(files,list) or len(files)!=sum(masks):
            raise ValueError("Original native WriteData: incomplete selected files")
        by_channel={}
        for item in files:
            if not isinstance(item,dict):
                raise ValueError("Original native WriteData: invalid selected file")
            ch=_integer(item.get("channel"),"file channel",10)
            if ch==0 or not masks[ch-1] or ch in by_channel:
                raise ValueError("Original native WriteData: unexpected selected file")
            kind,idx=("ADC",ch) if ch<=8 else ("TACH",ch-8)
            expected=f"SOURCE_W{i:02d}_{kind}{idx}_LIVE_RX_UNSCALED.bin"
            if item.get("name")!=expected:
                raise ValueError("Original native WriteData: file basename mismatch")
            _digest(item.get("sha256"),"channel payload")
            _integer(item.get("bytes"),"channel bytes",raw_len)
            _integer(item.get("packets"),"channel packets",raw_frames)
            physical=item.get("physical_candidate")
            if physical_enabled and ch<=8:
                if not isinstance(physical,dict):
                    raise ValueError("Source physical WriteData: missing companion")
                expected_name=f"SOURCE_W{i:02d}_ADC{ch}_LIVE_PHYSICAL_CANDIDATE.bin"
                if physical.get("name")!=expected_name:
                    raise ValueError("Source physical WriteData: companion name mismatch")
                _digest(physical.get("sha256"),"physical candidate")
                _integer(physical.get("bytes"),"physical candidate bytes",raw_len)
                _integer(physical.get("packets"),"physical candidate packets",raw_frames)
                _integer(physical.get("skipped_packets"),"physical candidate skipped packets",raw_frames)
            elif physical is not None:
                raise ValueError("Source physical WriteData: unexpected companion")
            by_channel[ch]=item
        checks.append(dict(window=window,masks=masks,by_channel=by_channel,
                           start=start,end=end,stage=0,first=0,wrote=0,
                           frozen=0,rate=0,before_adc1=0))
    raw_path=_local_file(folder,"incoming.raw",max_bytes=MAX_RAW)
    if raw_path.stat().st_size!=raw_len:
        raise ValueError("Original native WriteData: RAW file changed")
    file_checks={}
    packet_rates={}
    packet_sum=sha256()
    raw_sum=sha256()
    actual_samples=[0]*10
    actual_packet_records=0
    window_pointer=0
    results=[]
    # Replay the exact PARAM freeze ledger while authenticating RAW and
    # actual writer packets. Snapshot at each DATA close boundary,
    # NOT at end of capture or first Stage0->1.
    close_config={}
    closes={}
    for check in checks:
        closes.setdefault(check["end"],[]).append(check)
    config=CloseConfigReplay()
    physical_replay=PhysicalWriteReplay()
    physical_checks={}
    physical_results=[]
    physical_skipped=[]
    param_sha=summary.get("source_original_param_gate_sha256")
    param_count=summary.get("source_original_param_gate_records",0)
    with ExitStack() as resources:
        param_gate=None
        if param_sha is not None:
            param_gate=resources.enter_context(OriginalParamGateReader(
                _local_file(folder,SOURCE_PARAM_GATE_NAME),
                expected_sha256=param_sha,expected_records=param_count,
                expected_frames=raw_frames))
        elif param_count:
            raise ValueError("Source close metadata: PARAM ledger SHA absent")
        if physical_enabled and param_gate is None:
            raise ValueError("Source physical WriteData: PARAM gate evidence required")
        def snapshot(boundary):
            if param_gate is not None:
                for check in closes.get(boundary,()):
                    for channel in check["by_channel"]:
                        close_config[(check["window"]["window"],channel)]=config.snapshot(channel,boundary)
        snapshot(0)
        for check in checks:
            for channel,item in check["by_channel"].items():
                file=_local_file(folder,item["name"],max_bytes=raw_len)
                if file.stat().st_size!=item["bytes"]:
                    raise ValueError("Original native WriteData: file length mismatch")
                handle=resources.enter_context(file.open("rb"))
                key=(check["window"]["window"],channel)
                file_checks[key]=(handle,sha256(),0,0,item)
                packet_rates[key]=set()
                if item.get("physical_candidate") is not None:
                    part=item["physical_candidate"]
                    path=_local_file(folder,part["name"],max_bytes=raw_len)
                    if path.stat().st_size!=part["bytes"]:
                        raise ValueError("Source physical WriteData: companion length mismatch")
                    physical_checks[key]=dict(handle=resources.enter_context(path.open("rb")),
                        digest=sha256(),size=0,packets=0,skipped=0,proof=part)
        data=resources.enter_context(raw_path.open("rb"))
        receipts=resources.enter_context(packet_path.open("rb"))
        for frame_index in range(1,raw_frames+1):
            header=data.read(8)
            if len(header)!=8:
                raise ValueError("Original native WriteData: early frame EOF")
            typ,n=struct.unpack("<II",header)
            if n<8 or n>MAX_FRAME or n%4:
                raise ValueError("Original native WriteData: bad packet envelope")
            body=data.read(n-8)
            if len(body)!=n-8:
                raise ValueError("Original native WriteData: truncated frame")
            raw_sum.update(header);raw_sum.update(body)
            if param_gate is not None:
                if typ==PARAM:
                    frame=header+body
                    blocks=list(_parameter_blocks(frame))
                    frozen=param_gate.consume(frame_index=frame_index,frame=frame,
                        descriptors=len(blocks),values3100_count=sum(a==0x3100 for a,_,_ in blocks))
                    if physical_enabled:
                        physical_replay.on_param(blocks,frozen)
                    if not frozen:
                        config.put(blocks)
                snapshot(frame_index)
            while (window_pointer<len(checks) and
                   frame_index>checks[window_pointer]["end"]):
                window_pointer+=1
            selected=(checks[window_pointer]
                      if window_pointer<len(checks) and
                      frame_index>checks[window_pointer]["start"] else None)
            if typ not in TYPES:
                continue
            if n<28:
                raise ValueError("Original native WriteData: truncated ADC/TACH")
            channel,rate=struct.unpack_from("<II",body,12)
            if ((typ==TYPES[0] and channel>=8) or
                    (typ==TYPES[1] and channel not in (8,9)) or
                    rate not in RATES):
                raise ValueError("Original native WriteData: invalid source channel/Fs")
            payload=body[20:]
            words=len(payload)//4
            prior=actual_samples[channel]
            actual_samples[channel]+=words
            if selected is None or words==0:
                continue
            rawline=receipts.readline(MAX_JSON+1)
            if not rawline or len(rawline)>MAX_JSON:
                raise ValueError("Original native WriteData: missing/oversized frame receipt")
            packet_sum.update(rawline)
            actual_packet_records+=1
            try:
                packet=json.loads(rawline)
            except (ValueError,UnicodeError) as exc:
                raise ValueError("Original native WriteData: corrupt gate JSON") from exc
            if not isinstance(packet,dict):
                raise ValueError("Original native WriteData: gate record not a map")
            gate_rate=packet.get("source_selected_rate_hz")
            frozen=packet.get("freeze_update")
            gate=(type(gate_rate) is int and gate_rate in RATES and
                  type(frozen) is bool and not frozen and gate_rate==rate)
            if type(frozen) is not bool or gate_rate not in RATES:
                raise ValueError("Original native WriteData: unsupported source rate/freeze")
            before=selected["stage"]
            after=before
            if gate and before==0 and channel==0:
                after=1
                selected["first"]=frame_index
            wrote=bool(gate and after==1 and selected["masks"][channel])
            if not gate:
                if frozen:selected["frozen"]+=1
                else:selected["rate"]+=1
            elif after==0:selected["before_adc1"]+=1
            if wrote:selected["wrote"]+=1
            expected={
                "frame_index":frame_index,
                "window":selected["window"]["window"],
                "channel":channel+1,
                "sample_words":words,
                "rx_sample_before":prior,
                "rx_sample_after":actual_samples[channel],
                "source_selected_rate_hz":gate_rate,
                "received_rate_hz":rate,
                "freeze_update":frozen,
                "source_ring_store_allowed":bool(gate),
                "write_data_stage_before":before,
                "write_data_stage_after":after,
                "channel_selected":selected["masks"][channel],
                "wrote_source_bytes":wrote,
                "rx_payload_sha256":sha256(payload).hexdigest(),
            }
            if packet!=expected:
                raise ValueError("Original native WriteData: packet gate/RAW discrepancy")
            selected["stage"]=after
            if wrote:
                key=(selected["window"]["window"],channel+1)
                handle,h,total,packets,item=file_checks[key]
                copied=handle.read(len(payload))
                if copied!=payload:
                    raise ValueError("Original native WriteData: emitted bytes differ from RX")
                h.update(copied)
                file_checks[key]=(handle,h,total+len(copied),packets+1,item)
                packet_rates[key].add(rate)
                if key in physical_checks:
                    part=physical_checks[key]
                    expected_physical=physical_replay.chunk(channel+1,payload)
                    if expected_physical is None:
                        part["skipped"]+=1
                    else:
                        got=part["handle"].read(len(expected_physical))
                        if got!=expected_physical:
                            raise ValueError("Source physical WriteData: processed bytes differ from RAW/FRange replay")
                        part["digest"].update(got)
                        part["size"]+=len(got)
                        part["packets"]+=1
        final=data.read(MAX_FRAME)
        if len(final)!=raw_tail or data.read(1):
            raise ValueError("Original native WriteData: source terminal tail changed")
        raw_sum.update(final)
        if raw_sum.hexdigest()!=source_digest or actual_samples!=expected_counts:
            raise ValueError("Original native WriteData: source SHA/channel counts mismatch")
        if param_gate is not None:
            param_gate.finish()
        if (actual_packet_records!=packet_total or
                receipts.read(1) or packet_sum.hexdigest()!=packet_digest):
            raise ValueError("Original native WriteData: packet audit SHA/length mismatch")
        for check in checks:
            window=check["window"]
            if (window.get("stage_at_end")!=check["stage"] or
                    window.get("first_accepted_adc1_frame",0)!=check["first"] or
                    window.get("written_packets")!=check["wrote"] or
                    window.get("skipped_rate_packets")!=check["rate"] or
                    window.get("skipped_frozen_packets")!=check["frozen"] or
                    window.get("skipped_before_adc1_packets")!=check["before_adc1"]):
                raise ValueError("Original native WriteData: impossible source stage transition")
            for channel,item in check["by_channel"].items():
                handle,h,total,packets,proof=file_checks[(window["window"],channel)]
                if (handle.read(1) or total!=item["bytes"] or
                        packets!=item["packets"] or
                        h.hexdigest()!=item["sha256"]):
                    raise ValueError("Original native WriteData: unverified channel file bytes")
                key=(window["window"],channel)
                if key in physical_checks:
                    part=physical_checks[key]
                    candidate=part["proof"]
                    if (part["handle"].read(1) or part["size"]!=candidate["bytes"]
                            or part["packets"]!=candidate["packets"]
                            or part["skipped"]!=candidate["skipped_packets"]
                            or part["packets"]+part["skipped"]!=packets
                            or part["digest"].hexdigest()!=candidate["sha256"]):
                        raise ValueError("Source physical WriteData: companion receipt mismatch")
                    record=dict(window=window["window"],channel=channel,
                        name=candidate["name"],bytes=part["size"],packets=part["packets"],
                        sha256=candidate["sha256"],source_raw_sha256=source_digest,
                        wire_name=item["name"],wire_sha256=item["sha256"],
                        verified_packet_rates_hz=sorted(packet_rates[key]),
                        input_domain="ORIGINAL_STORAGE_FRANGE_FLOAT32_CANDIDATE",
                        original_delphi_file_parity_verified=False,
                        source_close_config=close_config[key])
                    if part["skipped"] or not part["packets"]:
                        physical_skipped.append(dict(record,skipped_packets=part["skipped"],
                            reason="UNKNOWN_RANGE_NONFINITE_OR_EMPTY_PHYSICAL_WINDOW"))
                    else:
                        physical_results.append(dict(record,physical_raw_replay_verified=True))
                results.append({
                    "window":window["window"],"channel":channel,
                    "name":item["name"],"bytes":total,"packets":packets,
                    "sha256":item["sha256"],"source_raw_sha256":source_digest,
                    "original_live_source_rate_freeze_gate_verified":True,
                    "verified_packet_rates_hz":sorted(packet_rates[
                        (window["window"],channel)]),
                    "original_delphi_file_parity_verified":False,
                    **({"source_close_config":close_config[(window["window"],channel)]}
                       if (window["window"],channel) in close_config else {}),
                })
    return {
        "source":"STAGE111Z31FS_ORIGINAL_LIVE_WRITEDATA_GATE_V1",
        "native_writer_audit_sha256":stated,
        "source_raw_sha256":source_digest,
        "packet_gate_sha256":packet_digest,
        "verified_source_packet_records":actual_packet_records,
        "verified_source_windows":len(checks),
        "verified_channel_files":results,
        "physical_writer_schema":physical_schema,
        "verified_physical_channel_files":physical_results,
        "skipped_physical_channel_files":physical_skipped,
        "original_delphi_file_parity_verified":False,
        "original_win32_click_timing_verified":False,
    }
