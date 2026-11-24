"""Source-faithful WriteData/WriteValues transition ledger and REAL local
verified sample-window export for the single Native R6.1 TCP receiver.

PRIVATE Delphi _Unit125.pas:00809414..008099CF:
  WriteDataStage initial 2; flag starts => open 10 selected files -> 0;
  first ADC1 buffer -> stage 1; flag false => close -> stage 2.
  WriteValuesStage initial 2; starts => CSV open -> 1; stops => close -> 2.
_PRIVATE_ _Unit128.pas:0084E914 / 0084E988 copies ten + 43/24/43/6 masks.

This compatible implementation does not own Delphi TMVKThread. The FULL,
unchanged read-only Go RAW stream is the only acquisition source. Button
clicks pin verified Go channel sample counters/AUX ticks (last status
poll) and after the same run is SHA-accepted, extract the selected
native FLOAT32 intervals into separately named LOCAL files. These cuts
are status-poll anchored, NOT the original Win32 TFileStream exact
microsecond boundaries or its original BIN/TSXML format. No socket or
command encoder exists here; source SetRate never leaves the operator PC.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import csv
import json
import shutil
import zipfile

from .original_connected_status import connected_system_status
from .original_mode2_active_tx_provenance import verify_source_native_tx_origin
from .original_live_pagefile import OriginalLiveFilePlan
from .offline_measurement_flow import OfflineMeasurementFlow
from .offline_export import require_members
from .native_r6_tach_evidence import validate_tach_evidence
from .original_pagefile_recording import OriginalPageFileSelection,OriginalFileNameOptions
from .original_measure_controls import table_rows
from .original_values_3100_timeline import scan_original_values_3100
from .original_param_gate_proof import SOURCE_PARAM_GATE_NAME
from .original_write_data_wire_replay import export_source_wire_write_intervals
from .original_write_data_live_gate import verify_native_live_write_data
from .original_mode2_source_files import (
    write_verified_source_tsxml_sidecars, source_writer_name_candidates,
)
from .original_live_values_proof import verify_original_live_values

SOURCE="SOURCE_IDR_00809414_008099CF_LIVE_WRITE_STAGES_COMPAT_V1"
STAGE_OPEN=0
STAGE_STREAMING=1
STAGE_IDLE=2
MAX_WINDOWS=8
MAX_TICKS_PER_WINDOW=64
MAX_SELECTED_ROWS=70000
EXPORT_SUBDIR="LOCAL_SOURCE_WRITE_WINDOWS_NATIVE"
SOURCE_RATES=tuple(sorted((512,2048,8192,32768,65536)))


def _int(value,name,ceiling=2**64-1):
    if type(value) is not int or not 0<=value<=ceiling:
        raise ValueError(f"Original live writer: invalid {name}")
    return value


def _status_proof(payload):
    if not isinstance(payload,dict):
        raise ValueError("Writer needs authenticated Go evidence")
    proof=connected_system_status(payload)
    # Original SetRate sends real outgoing bytes on the SAME Go socket.
    # An authorized physical SetRate must not disable the separate local
    # WriteData/WriteValues buttons or be relabeled as a read-only run.
    verify_source_native_tx_origin(payload)
    if payload.get("source_tcp_multi_socket",False) is True:
        raise ValueError(
            "Original write intervals cannot cross physically separate TCP sockets; "
            "use individually SHA-verified source RAW segments")
    if (not proof.connection_verified or proof.data_integrity_alert
            or payload.get("capture_only") is True
            or payload.get("snapshot_stale") is not False
            or payload.get("phase")!="RECORDING"):
        raise ValueError("Cannot write from a stale or damaged live stream")
    session_id=payload.get("session_id")
    if (not isinstance(session_id,str) or
            not 1<=len(session_id)<=160 or
            any(c in session_id for c in ("/","\\","\x00"))):
        raise ValueError("Live writer has no authenticated single run identity")
    if payload.get("source_rate_transition_during_live",False) is True:
        raise ValueError("Original writer multi-frequency session requires separated rate intervals")
    channels=payload.get("channels")
    if not isinstance(channels,list) or len(channels)!=10:
        raise ValueError("Original live writer requires all ten Go channel banks")
    counters=[]
    for number,ch in enumerate(channels,1):
        if (not isinstance(ch,dict) or ch.get("channel")!=number or
                ch.get("type")!=("ADC" if number<=8 else "TACH")):
            raise ValueError("Source 10 channel order/counter mismatch")
        count=_int(ch.get("samples"),f"channel {number} samples")
        frames=_int(ch.get("frames"),f"channel {number} frames")
        # Original _Unit125:0080819E supports variable-sized ADC/TACH
        # packets (and zero-size frames); 256/64 are common PCAP lengths,
        # NOT a requirement. Native Go counts only nonempty sample frames.
        max_words=(0x20000-28)//4
        if ((frames==0)!=(count==0) or count<frames or
                count>frames*max_words):
            raise ValueError("Go source frames/samples outside variable-size protocol")
        rates=ch.get("sample_rates_hz")
        if (not isinstance(rates,list) or len(rates)>5 or
                any(type(v) is not int or v not in SOURCE_RATES for v in rates)):
            raise ValueError("Native Go source rate values not checked")
        counters.append(count)
    aux=_int(payload.get("aux4700_updates"),"AUX updates")
    frames=_int(payload.get("frames_decoded"),"decoded frames")
    raw=_int(payload.get("raw_bytes"),"RAW bytes")
    if frames==0 or raw==0:
        raise ValueError("No source frames")
    # _Unit125:008085A5..008085BD writes a VALUES row only when the
    # observed PARAM descriptor starts at address 0x3100, not on AUX4700.
    ticks=payload.get("source_values_ticks_address_3100")
    if ticks is not None and _int(ticks,"actual source 0x3100 VALUES ticks")>frames:
        raise ValueError("Source VALUES ticks cannot exceed received frames")
    return (session_id,tuple(counters),aux,frames,raw)


@dataclass(frozen=True)
class OriginalSourceWriteWindow:
    kind:str  # "data" or "values"
    session_id:str
    channels:tuple[bool,...]
    spec:tuple[bool,...]
    values:tuple[bool,...]
    start_samples:tuple[int,...]
    end_samples:tuple[int,...]
    start_aux:int
    end_aux:int
    start_frames:int
    end_frames:int
    operator_begin_utc:str
    operator_end_utc:str
    boundary_mode:str="LAST_VERIFIED_NATIVE_STATUS"
    start_source_values_ticks:int|None=None
    end_source_values_ticks:int|None=None
    source_setrate_commands_seen:int=0
    # Immutable original PageFile choices captured at each writer BEGIN.
    file_options:OriginalFileNameOptions|None=None

    def receipt(self):
        return {
            "kind":self.kind,
            "selected_channels":[i+1 for i,v in enumerate(self.channels) if v],
            "source_spec_flags":sum(self.spec),
            "source_values_flags":sum(self.values),
            "sample_bounds_from_last_verified_status":
                self.boundary_mode=="LAST_VERIFIED_NATIVE_STATUS",
            "sample_bounds_from_go_decoded_frame":
                self.boundary_mode=="BEFORE_NEXT_REASSEMBLED_APPLICATION_FRAME",
            "source_boundary_mode":self.boundary_mode,
            "start_samples":list(self.start_samples),
            "end_samples":list(self.end_samples),
            "start_aux":self.start_aux,
            "end_aux":self.end_aux,
            "operator_begin_utc":self.operator_begin_utc,
            "operator_end_utc":self.operator_end_utc,
            "hardware_command_sent":self.source_setrate_commands_seen>0,
            "source_setrate_commands_seen":self.source_setrate_commands_seen,
            "source_pagefile_options_snapshot_present":self.file_options is not None,
            "source_pagefile_write_tsxml_requested":(
                self.file_options.write_tsxml if self.file_options is not None
                else None),
            "original_source_values_ticks_0x3100":{
                "start":self.start_source_values_ticks,
                "end":self.end_source_values_ticks,
                "source_trigger_is_param_address_3100":True,
                "native_aux_tick_is_not_source_values_tick":True},
            "original_tmkvthread_file_byte_parity_verified":False,
        }


class OriginalLiveWriteLedger:
    """Single operator Mode2 run; a real Core owner for BOTH record buttons."""

    def __init__(self):
        self.session_id=None
        self._last=None
        self.data_stage=STAGE_IDLE
        self.values_stage=STAGE_IDLE
        self._active_data=None
        self._active_values=None
        self.windows=[]
        self.errors=[]
        self.finished=False
        self.finalizing=False
        self._finalizing_utc=None
        self.frame_marks_required=False
        self.frame_marks_verified=False
        self.frame_marks_failed=False
        self.frame_mark_actions=[]
        self.source_setrate_commands_seen=0
        self.source_tcp_connection_count=0
        self.source_values_ticks=None

    @property
    def trustworthy(self):
        # An operator frame-mark failure is terminal for this run.
        # A later good TCP status must not silently re-arm the same
        # source recording buttons with an unusable pending mark log.
        return (self._last is not None and not self.finished
                and not self.frame_marks_failed)

    def observe(self,payload):
        # The final verified Go archive/mark audit owns the true final
        # counters. A late periodic JSON status cannot re-arm a writer.
        if self.finalizing or self.finished:
            return self.receipt()
        try:
            proof=_status_proof(payload)
            sid,counters,aux,frames,raw=proof
            current_socket=payload.get("source_tcp_connection_count",0)
            if type(current_socket) is not int or not 0<=current_socket<=128:
                raise ValueError("Source writer TCP session count invalid")
            if current_socket < self.source_tcp_connection_count:
                raise ValueError("Source writer TCP epoch rolled back")
            if (current_socket>self.source_tcp_connection_count and
                    self.source_tcp_connection_count and
                    (self._active_data is not None or self._active_values is not None)):
                raise ValueError("Original live WriteData/WriteValues stopped on TCP disconnect")
            source_tick=payload.get("source_values_ticks_address_3100")
            if (source_tick is not None and self.source_values_ticks is not None
                    and source_tick<self.source_values_ticks):
                raise ValueError("Source 0x3100 VALUES row tick count rolled back")
            tx=payload.get("source_mode2_tx_evidence")
            current_tx=(tx.get("source_tx_sent_commands",0)
                        if isinstance(tx,dict) else 0)
            _int(current_tx,"original source command count")
            if current_tx<self.source_setrate_commands_seen:
                raise ValueError("Actual Go source SetRate command count rolled back")
            if self.finished:
                raise ValueError("Capture already finished")
            if self.session_id is not None and sid!=self.session_id:
                raise ValueError("A second Go run cannot inherit original writer masks")
            if self._last is not None:
                _,old_counts,old_aux,old_frames,old_raw=self._last
                if (any(x<y for x,y in zip(counters,old_counts))
                        or aux<old_aux or frames<old_frames or raw<old_raw):
                    raise ValueError("Native sample/counter rollback")
            self.session_id=sid
            self._last=proof
            self.source_tcp_connection_count=current_socket
            self.source_values_ticks=source_tick
            self.source_setrate_commands_seen=current_tx
            # Original WriteDataStage=0 reaches 1 on the first ADC1 block.
            if (self.data_stage==STAGE_OPEN and self._active_data is not None
                    and counters[0]>self._active_data[1][0]):
                self.data_stage=STAGE_STREAMING
        except (ValueError,TypeError,KeyError) as exc:
            self.invalidate(str(exc))
            raise
        return self.receipt()

    def invalidate(self,reason:str):
        if self.frame_marks_required:
            self.frame_marks_failed=True
        self._last=None
        if self._active_data is not None or self._active_values is not None:
            self.errors.append("Активная запись не подтверждена: "+str(reason))
        self._active_data=None
        self._active_values=None
        self.data_stage=STAGE_IDLE
        self.values_stage=STAGE_IDLE

    @staticmethod
    def _utc(now=None):
        value=now if now is not None else datetime.now(timezone.utc)
        if not isinstance(value,datetime) or value.tzinfo is None:
            raise ValueError("Operator write time must include timezone")
        return value.astimezone(timezone.utc)

    def begin_finalization(self,*,now=None):
        """Stop accepting operator marks; keep pending intervals for SHA audit."""
        if not self.finished and not self.finalizing:
            self._finalizing_utc=self._utc(now)
            self.finalizing=True
        return self.receipt()

    def elapsed_receipt(self,*,now=None):
        """Independent source-style hh:nn:ss timers.

        These are operator-request durations, frozen at the stop/finalize
        boundary. Delphi also resets its timer at actual file open; do not
        claim that runtime timestamp from a pending local Go mark.
        """
        stamp=self._finalizing_utc if self.finalizing else self._utc(now)
        result={"time_basis":"OPERATOR_REQUEST_UTC_NOT_DELPHI_FILE_OPEN",
                "delphi_file_open_time_verified":False}
        for kind,active in (("data",self._active_data),("values",self._active_values)):
            elapsed=None
            if active is not None:
                start=datetime.fromisoformat(active[4])
                elapsed=max(0,int((stamp-start).total_seconds()))
            result[kind+"_elapsed_seconds"]=elapsed
            result[kind+"_elapsed_text"]=(None if elapsed is None else
                f"{elapsed//3600%24:02d}:{elapsed//60%60:02d}:{elapsed%60:02d}")
        return result

    def plan_for_frame_mark(self,kind:str,plan:OriginalLiveFilePlan):
        """Use the BEGIN mask for END, even if the other writer's flags changed."""
        if kind not in ("data","values") or not isinstance(plan,OriginalLiveFilePlan):
            raise ValueError("Original write kind/selection invalid")
        active=self._active_data if kind=="data" else self._active_values
        return active[0] if active is not None else plan

    def toggle(self,kind:str,plan:OriginalLiveFilePlan,*,now=None,
               file_options:OriginalFileNameOptions|None=None):
        if kind not in ("data","values"):
            raise ValueError("Unknown original source write flag")
        if not isinstance(plan,OriginalLiveFilePlan):
            raise ValueError("Source channel/SPEC/VALUES mask is missing")
        if (file_options is not None and
                not isinstance(file_options,OriginalFileNameOptions)):
            raise ValueError("Source PageFile recording options invalid")
        if self.finalizing:
            raise ValueError("Source recording is finalizing; new operator marks forbidden")
        if not self.trustworthy:
            raise ValueError("Source recording requires verified active Go status")
        if plan.session_id is not None and plan.session_id!=self.session_id:
            raise ValueError("Operator checkboxes belong to another Native run")
        stamp=self._utc(now).isoformat()
        attr="_active_data" if kind=="data" else "_active_values"
        active=getattr(self,attr)
        if active is None:
            if sum(bool(x) for x in plan.channels)==0:
                raise ValueError("Original recorder cannot write zero channels")
            other=self._active_values if kind=="data" else self._active_data
            if other is not None and plan.channels!=other[0].channels:
                raise ValueError("Source shared channels locked by another writer")
            if kind=="values" and plan.effective_values_count()==0:
                raise ValueError("Original VALUES has zero selected result flags for selected channels")
            if (len(self.windows)+int(self._active_data is not None)
                    +int(self._active_values is not None)>=MAX_WINDOWS):
                raise ValueError("At most eight checked local write intervals")
            _,samples,aux,frames,_=self._last
            setattr(self,attr,(
                plan,samples,aux,frames,stamp,
                self.source_values_ticks,self.source_setrate_commands_seen,
                file_options))
            if kind=="data":
                self.data_stage=STAGE_OPEN
            else:
                # Source 00809977 opens VALUES file directly into stage1.
                self.values_stage=STAGE_STREAMING
            return self.receipt()
        return self._close_active(kind,stamp)

    def _close_active(self,kind,stamp):
        attr="_active_data" if kind=="data" else "_active_values"
        active=getattr(self,attr)
        if active is None or self._last is None:
            raise ValueError("Source active writer/last accepted counters missing")
        (plan_open,start_samples,start_aux,start_frames,start_stamp,
         start_source_tick,start_tx_commands,start_file_options)=active
        _,end_samples,end_aux,end_frames,_=self._last
        if (any(b<a for a,b in zip(start_samples,end_samples))
                or end_aux<start_aux or end_frames<start_frames):
            self.invalidate("Source counter rolled backwards during write")
            raise ValueError("Original write counters went backwards")
        window=OriginalSourceWriteWindow(
            kind,self.session_id,plan_open.channels,plan_open.spec,
            plan_open.values,start_samples,end_samples,start_aux,end_aux,
            start_frames,end_frames,start_stamp,stamp,
            start_source_values_ticks=start_source_tick,
            end_source_values_ticks=self.source_values_ticks,
            source_setrate_commands_seen=self.source_setrate_commands_seen,
            file_options=start_file_options)
        self.windows.append(window)
        setattr(self,attr,None)
        if kind=="data":
            self.data_stage=STAGE_IDLE
        else:
            self.values_stage=STAGE_IDLE
        return self.receipt()

    def register_native_frame_mark(self,receipt,plan):
        """Bind ONE actually queued GUI event to this authenticated run."""
        if (not self.trustworthy or self.finalizing or
                not isinstance(plan,OriginalLiveFilePlan) or
                not isinstance(receipt,dict) or
                receipt.get("session_id")!=self.session_id or
                receipt.get("sequence")!=len(self.frame_mark_actions)+1 or
                receipt.get("event") not in (
                    "data_begin","data_end","values_begin","values_end") or
                receipt.get("queued_local_only") is not True or
                receipt.get("device_commands_sent") is not False):
            raise ValueError("Source frame mark not queued for this run")
        self.frame_marks_required=True
        self.frame_mark_actions.append({
            "sequence":receipt["sequence"],"event":receipt["event"],
            "channels":tuple(plan.channels),"spec":tuple(plan.spec),
            "values":tuple(plan.values),
        })
        return self.receipt()

    def finish(self,*,accepted:bool):
        """Close only on VERIFIED final Go export; rejects unfinished fault."""
        if type(accepted) is not bool:
            raise ValueError("Native completion proof must be Boolean")
        if not self.finished:
            self.begin_finalization()
            if accepted and self._last is not None and not self.frame_marks_failed:
                for kind in ("data","values"):
                    attr="_active_data" if kind=="data" else "_active_values"
                    if getattr(self,attr) is not None:
                        # Provisional status-poll endpoint; the final
                        # SHA-bound Go frame audit replaces these counters.
                        self._close_active(kind,self._finalizing_utc.isoformat())
            else:
                self.invalidate("Capture ended without a verified writer source")
            self.finished=True
            self.data_stage=STAGE_IDLE
            self.values_stage=STAGE_IDLE
        return self.receipt()

    def receipt(self):
        return {
            "source":SOURCE,
            "session_id":self.session_id,
            "write_data_stage":self.data_stage,
            "write_values_stage":self.values_stage,
            "original_idle_stage":STAGE_IDLE,
            "source_data_open_stage":STAGE_OPEN,
            "source_streaming_stage":STAGE_STREAMING,
            "write_data_requested":self._active_data is not None,
            "write_values_requested":self._active_values is not None,
            "completed_window_count":len(self.windows),
            "source_writer_finalizing":self.finalizing and not self.finished,
            "source_writer_finished":self.finished,
            "has_verifiable_live_status":self.trustworthy and not self.finalizing,
            "errors":list(self.errors),
            "hardware_commands_sent":self.source_setrate_commands_seen,
            "original_source_values_ticks_0x3100":self.source_values_ticks,
            "source_tcp_connection_count":self.source_tcp_connection_count,
            "original_write_bytes_identical":False,
            "native_full_raw_not_filtered":True,
            "source_native_frame_marks_requested":self.frame_marks_required,
            "source_native_frame_marks_verified":self.frame_marks_verified,
            "source_native_mark_event_count":len(self.frame_mark_actions),
            "source_native_frame_marks_failed":self.frame_marks_failed,
        }


def _copy_checked_window(archive,src_name,dst,start,end,sha_expected,
                         source_samples):
    """Verify every input byte while copying ONLY requested Float32 slice."""
    if type(start) is not int or type(end) is not int or not 0<=start<end<=source_samples:
        raise ValueError("Source write window exceeds checked channel samples")
    file=archive.getinfo(src_name)
    if file.file_size!=source_samples*4:
        raise ValueError("Source FLOAT32 size differs from audited sample count")
    whole=sha256()
    copied=sha256()
    bytes_read=0
    lo,hi=start*4,end*4
    with archive.open(src_name) as inp, dst.open("xb") as output:
        while True:
            data=inp.read(1024*1024)
            if not data:
                break
            left=max(0,lo-bytes_read)
            right=min(len(data),hi-bytes_read)
            if left<right:
                selected=data[left:right]
                output.write(selected)
                copied.update(selected)
            whole.update(data)
            bytes_read+=len(data)
    if (bytes_read!=file.file_size or whole.hexdigest()!=sha_expected
            or dst.stat().st_size!=(end-start)*4):
        raise ValueError("Unchanged RAW channel SHA or source boundary mismatch")
    return {"name":dst.name,"sha256":copied.hexdigest(),
            "bytes":dst.stat().st_size,"samples":end-start}


def export_source_write_windows(ledger:OriginalLiveWriteLedger,
                                flow:OfflineMeasurementFlow,
                                parent:Path|str)->dict:
    """Post-capture actual local FLOAT32/VALUES extraction for operator clicks.

    Writes a BRAND-NEW folder beside the SHA-accepted Native ZIP.
    All source floats are copied without gain/filter resampling; ADC
    channels already have Native session gain applied, TACH remains
    explicitly UNSCALED. If anything is malformed, remove ONLY our
    new output folder. The original RAW/ZIP are never modified.
    """
    if (not isinstance(ledger,OriginalLiveWriteLedger) or not ledger.finished
            or not isinstance(flow,OfflineMeasurementFlow) or flow.direct_bin):
        raise ValueError("Original live write windows require one accepted Native ZIP")
    if not ledger.windows:
        return {"windows":0,"new_directory":None,"source":SOURCE}
    if len(ledger.windows)>MAX_WINDOWS or not ledger.session_id:
        raise ValueError("Original writer window count/run identity invalid")
    flow.source_record()
    frame_mark_evidence=None
    if ledger.frame_marks_required:
        from .source_frame_mark_protocol import accept_native_frame_mark_audit
        # Requests to Go require authentic next-frame marks. Never
        # substitute the previous periodic Qt status if Go did not ACK.
        frame_mark_evidence=accept_native_frame_mark_audit(ledger,flow)
    source=Path(flow.session.path).resolve()
    if source.is_symlink() or source.parent.name!=ledger.session_id:
        raise ValueError("This ZIP is NOT from the recorded Native run")
    directory=Path(parent).resolve()
    if directory!=source.parent or not directory.is_dir() or directory.is_symlink():
        raise ValueError("Writer output must stay with the approved capture run")
    target=directory/EXPORT_SUBDIR
    if target.exists() or target.is_symlink():
        raise ValueError("Original local write export already exists; no overwrite")
    created=False
    try:
        target.mkdir(exist_ok=False)
        created=True
        emitted=[]
        skipped=[]
        with zipfile.ZipFile(source) as archive:
            files,audit=require_members(archive)
            provenance=audit["output_file_sha256"]
            tach=validate_tach_evidence(archive,audit)
            source_values_events=None
            source_live_values_evidence=None
            source_wire_evidence=[]
            source_live_data_evidence=None
            source_tsxml_receipts=[]
            raw_summary=None
            native_raw_path=directory/"incoming.raw"
            if (frame_mark_evidence is not None and native_raw_path.exists()):
                summary_path=directory/"summary.json"
                if (summary_path.is_symlink() or not summary_path.is_file()
                        or summary_path.stat().st_size>1048576):
                    raise ValueError("Original source write needs trusted Go summary")
                raw_summary=json.loads(summary_path.read_text(encoding="utf-8"))
                if (not isinstance(raw_summary,dict) or
                        raw_summary.get("raw_sha256")!=audit.get("source_raw_sha256")):
                    raise ValueError("Original wire writer RAW/ZIP mismatch")
                # Stage111Z31FS: independent, per-packet verification of
                # the actual live source WriteData rate/freeze/first-ADC1
                # gate. This proof is DISTINCT from FR's reconstructed
                # ungated RAW sample slices and calibrated Native BIN.
                source_live_data_evidence=verify_native_live_write_data(
                    directory,summary=raw_summary,
                    source_raw_sha256=audit["source_raw_sha256"])
                if source_live_data_evidence is not None:
                    data_windows=sum(w.kind=="data" for w in ledger.windows)
                    if (source_live_data_evidence["verified_source_windows"]!=
                            data_windows):
                        raise ValueError(
                            "Original live Go WriteData window count not agreed with Qt")
                    for proof in source_live_data_evidence["verified_channel_files"]:
                        original=directory/proof["name"]
                        copied=target/proof["name"]
                        if (original.is_symlink() or not original.is_file()
                                or copied.exists() or copied.is_symlink()):
                            raise ValueError("Unsafe source live writer copy")
                        with original.open("rb") as src, copied.open("xb") as dst:
                            copied_hash=sha256()
                            count=0
                            while True:
                                block=src.read(1024*1024)
                                if not block:break
                                dst.write(block)
                                copied_hash.update(block)
                                count+=len(block)
                            if (count!=proof["bytes"] or
                                    copied_hash.hexdigest()!=proof["sha256"]):
                                raise ValueError(
                                    "Source live WriteData changed during local copy")
                        emitted.append({
                            "kind":"source_live_original_rate_freeze_adc1_gated",
                            **proof})
                    # Original Delphi 00806A8C writes a sidecar TSXML on
                    # closing each channel file. Use the source tag order,
                    # types, Windows-1251, byte count and verified Fs; never
                    # replace original metadata such as custom device name,
                    # final Win32 local clock, FRange or units with a claim
                    # of physical parity. A multi-Fs file has no single
                    # correct <FrequencyPerChannel> and is reported only.
                    # Source Go DATA window numbers are independent of
                    # interleaved Qt VALUES intervals. Match by DATA order.
                    xml_options={i:w.file_options for i,w in enumerate(
                        (entry for entry in ledger.windows
                         if entry.kind=="data"),1)}
                    source_tsxml_receipts=write_verified_source_tsxml_sidecars(
                        target,live_proof=source_live_data_evidence,
                        source_run_end_utc=raw_summary.get("ended_utc"),
                        window_options=xml_options)
                    for part in source_tsxml_receipts:
                        if part.get("sidecar_created"):
                            emitted.append({"kind":"source_original_tsxml_structure",
                                            **part})
                        else:
                            skipped.append({"kind":"source_original_tsxml_structure",
                                            **part})
            # A genuine Go writer SHA without its RAW is a hard failure,
            # never a cue to fall back silently to FR's ungated slices.
            if raw_summary is None:
                summary_p=directory/"summary.json"
                if summary_p.is_file() and not summary_p.is_symlink() and (
                        "source_live_write_data_audit_sha256" in
                        summary_p.read_text(encoding="utf-8")):
                    raise ValueError("Source live WriteData audit cannot be verified without RAW")
            if (frame_mark_evidence is not None and
                    any(w.kind=="values" for w in ledger.windows)):
                # The original writer runs on PARAM descriptor 0x3100,
                # NOT on the unrelated 4700-byte AUX snapshot. Replay the
                # one untouched Native RAW, independently verify its SHA,
                # packet count, AUX and source trigger count; use actual Go
                # next-frame marks for every selected VALUES interval.
                if raw_summary is None:
                    raise ValueError("Original VALUES needs authenticated RAW and summary")
                ranges=[(number,w.start_source_values_ticks,
                         w.end_source_values_ticks)
                        for number,w in enumerate(ledger.windows,1)
                        if w.kind=="values"]
                source_values_events=scan_original_values_3100(
                    directory/"incoming.raw",
                    expected_sha256=audit["source_raw_sha256"],
                    expected_raw_bytes=raw_summary.get("raw_bytes"),
                    expected_frames=raw_summary.get("frames_decoded"),
                    expected_aux=raw_summary.get("aux4700_updates"),
                    expected_ticks=raw_summary.get("values_ticks_address_3100"),
                    expected_tail_bytes=raw_summary.get("incomplete_final_frame_bytes"),
                    ranges=ranges,
                    param_gate_path=(directory/SOURCE_PARAM_GATE_NAME if
                         raw_summary.get("source_original_param_gate_sha256") else None),
                    expected_param_gate_sha256=raw_summary.get(
                        "source_original_param_gate_sha256"),
                    expected_param_gate_records=raw_summary.get(
                        "source_original_param_gate_records",0),
                    expected_frozen_param_frames=raw_summary.get(
                        "source_original_param_frames_skipped_frozen",0),
                    expected_frozen_aux=raw_summary.get(
                        "source_original_aux4700_skipped_frozen",0),
                    expected_frozen_values=raw_summary.get(
                        "source_original_values_3100_skipped_frozen",0),
                    capture_register_prefix=raw_summary.get(
                        "source_live_values_audit_sha256") is not None)
                source_live_values_evidence=verify_original_live_values(
                    directory,summary=raw_summary,
                    source_sha=audit["source_raw_sha256"],
                    qt_values_windows=[
                        (number,w) for number,w in enumerate(ledger.windows,1)
                        if w.kind=="values"],
                    replayed_events=source_values_events)
                if source_live_values_evidence is not None:
                    for proof in source_live_values_evidence["verified_files"]:
                        original=directory/proof["name"]
                        copied=target/proof["name"]
                        if (original.is_symlink() or not original.is_file()
                                or copied.exists() or copied.is_symlink()):
                            raise ValueError("Unsafe source live Values file copy")
                        with original.open("rb") as src, copied.open("xb") as dst:
                            copied_hash=sha256()
                            copied_bytes=0
                            while True:
                                block=src.read(1024*1024)
                                if not block:break
                                dst.write(block)
                                copied_hash.update(block)
                                copied_bytes+=len(block)
                            if (copied_bytes!=proof["bytes"] or
                                    copied_hash.hexdigest()!=proof["sha256"]):
                                raise ValueError("Source live VALUES changed during copy")
                        emitted.append({"kind":"source_live_values_3100_proof",**proof})
                        layout=proof.get("source_raw_layout")
                        if layout is not None:
                            original_layout=directory/layout["name"]
                            copied_layout=target/layout["name"]
                            if (original_layout.is_symlink() or not original_layout.is_file()
                                    or copied_layout.exists() or copied_layout.is_symlink()):
                                raise ValueError("Unsafe source live VALUES layout copy")
                            # The independent verifier already bounded this file.
                            content=original_layout.read_bytes()
                            if (len(content)!=layout["bytes"] or
                                    sha256(content).hexdigest()!=layout["sha256"]):
                                raise ValueError("Source live VALUES layout changed during copy")
                            with copied_layout.open("xb") as dst:
                                dst.write(content)
                            emitted.append({"kind":"source_live_values_trigger_prefix_layout",
                                            "window":proof["window"],**layout})
            if (raw_summary is not None and frame_mark_evidence is not None
                    and any(w.kind=="data" for w in ledger.windows)):
                # Never silently re-scale raw ADC/TACH bytes: exact source
                # TmpStream.FMemory from original Execute 008082D3..
                # 008082DE is distinct from Native gain-corrected .f32.
                # Actual Delphi rate/freeze gate and file naming still
                # require a matching live original session to prove 1:1.
                go_channels=raw_summary.get("channels")
                if (not isinstance(go_channels,list) or len(go_channels)!=10):
                    raise ValueError("Original wire export missing Go ten-channel counts")
                final_counts=[]
                for i,item in enumerate(go_channels):
                    if not isinstance(item,dict):
                        raise ValueError("Original wire export invalid Go channel counter")
                    final_counts.append(_int(item.get("samples"),
                                             f"original wire channel {i+1}"))
                wire_cuts=[]
                for number,window in enumerate(ledger.windows,1):
                    if window.kind!="data":continue
                    for ch,chosen in enumerate(window.channels,1):
                        if chosen and (window.end_samples[ch-1]>
                                       window.start_samples[ch-1]):
                            wire_cuts.append((number,ch,
                                              window.start_samples[ch-1],
                                              window.end_samples[ch-1]))
                source_wire_evidence=export_source_wire_write_intervals(
                    native_raw_path,target,
                    expected_sha256=audit["source_raw_sha256"],
                    expected_raw_bytes=raw_summary.get("raw_bytes"),
                    expected_frames=raw_summary.get("frames_decoded"),
                    expected_tail_bytes=raw_summary.get(
                        "incomplete_final_frame_bytes"),
                    expected_channel_samples=final_counts,
                    cuts=wire_cuts)
                emitted.extend({"kind":"source_raw_wire_payload",**item}
                               for item in source_wire_evidence)
            for number,window in enumerate(ledger.windows,1):
                if window.session_id!=ledger.session_id:
                    raise ValueError("Cross-run source write interval")
                if window.kind=="data":
                    for ch,chosen in enumerate(window.channels,1):
                        if not chosen:
                            continue
                        first,last=(window.start_samples[ch-1],
                                    window.end_samples[ch-1])
                        if first==last:
                            skipped.append({"window":number,"channel":ch,
                                            "reason":"No verified incoming sample"})
                            continue
                        if ch<=8:
                            record=flow.select(channel=ch).source_record()
                            name=files[ch-1]
                            expected=provenance[name]
                            count=record["sample_count"]
                            label=f"DATA{number:02d}_ADC{ch}_NATIVE_CALIBRATED.f32"
                        else:
                            if tach is None or not tach.channels[ch-9].safe_local_raw_export:
                                raise ValueError("Selected TACH stream cannot be exported as continuous")
                            channel=tach.channels[ch-9]
                            name=channel.filename
                            expected=channel.digest
                            count=channel.samples
                            label=f"DATA{number:02d}_TACH{ch-8}_NATIVE_UNSCALED.f32"
                        emitted.append({"window":number,"native_channel":ch,
                                        **_copy_checked_window(
                                            archive,name,target/label,first,last,
                                            expected,count)})
                elif window.kind=="values":
                    if source_values_events is not None:
                        events=source_values_events[number]
                        if not events:
                            skipped.append({"window":number,"kind":"values",
                                            "reason":"No original PARAM 0x3100 trigger in verified frame interval"})
                            continue
                        if any(window.values[67:]):
                            raise ValueError("Source TACH textual VALUES are not yet byte-verified")
                        selected=OriginalPageFileSelection(
                            window.channels,window.spec,window.values)
                        selected.validate(flow)
                        # This is a REAL original trigger ledger, retaining the
                        # 0x3100 PARAM bytes without claiming these are the
                        # original TMvkCellList.GetValueText formatted cells.
                        evidence_name=f"VALUES{number:02d}_SOURCE_3100_EVENTS.csv"
                        with (target/evidence_name).open(
                                "x",newline="",encoding="utf-8-sig") as efile:
                            writer=csv.writer(efile,delimiter=";")
                            writer.writerow((
                                "SOURCE_3100_TICK_INDEX","RECEIVED_FRAME_INDEX",
                                "REGISTER_ADDRESS","WORD_COUNT","PARAM_PAYLOAD_LE_HEX",
                                "PARAM_PAYLOAD_SHA256","LATEST_PRECEDING_AUX_INDEX"))
                            for event in events:
                                writer.writerow((
                                    event["source_tick_index"],event["frame_index"],
                                    event["source_register_address"],event["register_words"],
                                    event["register_bytes_hex"],
                                    event["register_payload_sha256"],
                                    event["latest_earlier_aux_index"] if
                                    event["latest_earlier_aux_index"] is not None else ""))
                        evidence=target/evidence_name
                        emitted.append({
                            "window":number,"kind":"source_3100_evidence",
                            "name":evidence_name,"rows":len(events),
                            "bytes":evidence.stat().st_size,
                            "sha256":sha256(evidence.read_bytes()).hexdigest()})
                        # Selected numerical values remain explicitly
                        # reconstructed, using only the latest PREVIOUS
                        # authenticated AUX snapshot at each actual 0x3100
                        # event. They are NOT the original Delphi CSV bytes.
                        name=f"VALUES{number:02d}_NATIVE_VERIFIED_SELECTED.csv"
                        rows=0
                        with (target/name).open(
                                "x",newline="",encoding="utf-8-sig") as output:
                            writer=csv.writer(output,delimiter=";")
                            writer.writerow((
                                "SOURCE_3100_TICK_INDEX","RECEIVED_FRAME_INDEX",
                                "PRECEDING_AUX_INDEX","ADC","CATEGORY",
                                "SOURCE_INDEX","FIELD","VALUE","UNIT"))
                            for event in events:
                                aux_index=event["latest_earlier_aux_index"]
                                if aux_index is None:
                                    skipped.append({
                                        "window":number,"kind":"values_snapshot",
                                        "source_tick_index":event["source_tick_index"],
                                        "reason":"0x3100 arrived before any verified AUX result"})
                                    continue
                                if not 0<=aux_index<flow.session.updates:
                                    raise ValueError("0x3100 references an unverified AUX index")
                                current=flow.select(tick_index=aux_index)
                                for row in table_rows(current,selected):
                                    writer.writerow((
                                        event["source_tick_index"],event["frame_index"],
                                        aux_index,*row))
                                    rows+=1
                                    if rows>MAX_SELECTED_ROWS:
                                        raise ValueError("Too many source 0x3100 selected rows")
                        out=target/name
                        emitted.append({
                            "window":number,"kind":"values_3100_anchored",
                            "name":name,"rows":rows,"source_events":len(events),
                            "bytes":out.stat().st_size,
                            "sha256":sha256(out.read_bytes()).hexdigest(),
                            "original_tmkvcelllist_text_parity":False})
                    else:
                        # Older offline/status-poll selection files are a
                        # backward-compatible AUX approximation, not proof
                        # of the original 0x3100-triggered VALUES writer.
                        start,end=window.start_aux,window.end_aux
                        if start==end:
                            skipped.append({"window":number,"kind":"values",
                                            "reason":"No verified AUX tick in the requested interval"})
                            continue
                        if (end>flow.session.updates or end-start>MAX_TICKS_PER_WINDOW
                                or any(window.values[67:])):
                            raise ValueError("VALUES output lacks authenticated source ticks")
                        selected=OriginalPageFileSelection(
                            window.channels,window.spec,window.values)
                        selected.validate(flow)
                        name=f"VALUES{number:02d}_NATIVE_VERIFIED_SELECTED.csv"
                        rows=0
                        with (target/name).open("x",newline="",encoding="utf-8-sig") as f:
                            writer=csv.writer(f,delimiter=";")
                            writer.writerow(
                                ("AUX_TICK_INDEX","ADC","CATEGORY","SOURCE_INDEX",
                                 "FIELD","VALUE","UNIT"))
                            for tick in range(start,end):
                                chosen_flow=flow.select(tick_index=tick)
                                for row in table_rows(chosen_flow,selected):
                                    writer.writerow((tick,*row))
                                    rows+=1
                                    if rows>MAX_SELECTED_ROWS:
                                        raise ValueError("Too many verified original result rows")
                        out=target/name
                        emitted.append({"window":number,"kind":"values",
                                        "name":name,"rows":rows,
                                        "bytes":out.stat().st_size,
                                        "sha256":sha256(out.read_bytes()).hexdigest()})
                else:
                    raise ValueError("Invalid source recording type")
        receipt={
            "source":SOURCE,
            "run_id":ledger.session_id,
            "source_raw_sha256":audit.get("source_raw_sha256"),
            "windows":[w.receipt() for w in ledger.windows],
            "source_original_writer_name_candidates":[
                source_writer_name_candidates(w) for w in ledger.windows],
            "source_original_runtime_filenames_verified":False,
            "files":emitted,
            "missing_source_channels":skipped,
            "source_segment_boundaries_are_last_native_status_poll":
                not ledger.frame_marks_required,
            "source_segment_boundaries_at_next_native_complete_frame":
                bool(ledger.frame_marks_verified),
            "native_source_frame_mark_evidence":frame_mark_evidence,
            "original_tmkvthread_byte_exact_recording":False,
            "original_write_data_stage_recovered":True,
            "original_write_values_stage_recovered":True,
            "native_full_raw_recorded_independently":True,
            "hardware_command_sent":bool(ledger.source_setrate_commands_seen),
            "source_setrate_sent_commands":ledger.source_setrate_commands_seen,
            "source_setrate_sent_bytes":(frame_mark_evidence or {}).get("source_setrate_sent_bytes"),
            "actual_source_values_tick_trigger_word":"0x3100",
            "source_values_tick_is_distinct_from_aux4700":True,
            "source_values_export_anchored_to_verified_3100":
                source_values_events is not None,
            "source_3100_trigger_events_replayed":
                sum(map(len,source_values_events.values())) if
                source_values_events is not None else 0,
            "legacy_aux_result_export_is_not_original_values_trigger":
                source_values_events is None,
            "source_values_csv_exact_delphi_layout_verified":False,
            "source_write_data_wire_payload_files":len(source_wire_evidence),
            "source_write_data_wire_payload_byte_exact":
                bool(source_wire_evidence),
            "source_write_data_delphi_rate_freeze_parity_verified":False,
            "source_live_source_gate_verified":
                source_live_data_evidence is not None,
            "source_live_original_writer_evidence":source_live_data_evidence,
            "source_live_original_writer_files":
                len(source_live_data_evidence["verified_channel_files"]) if
                source_live_data_evidence is not None else 0,
            "source_original_tsxml_structural_sidecars":
                sum(item.get("sidecar_created",False) for item in
                    source_tsxml_receipts),
            "source_original_tsxml_delphi_full_parity_verified":False,
            "source_original_tsxml_skipped_by_operator":sum(
                x.get("reason")=="ORIGINAL_XML_CHECKBOX_OFF"
                for x in source_tsxml_receipts),
            "source_original_tsxml_settings_snapshot_verified":all(
                w.file_options is not None for w in ledger.windows
                if w.kind=="data"),
            "source_original_filename_algorithm_recovered":True,
            "source_live_values_3100_verified":
                source_live_values_evidence is not None,
            "source_live_values_trigger_prefix_registers_verified":
                bool(source_live_values_evidence and
                     source_live_values_evidence["source_trigger_prefix_registers_verified"]),
            "source_live_values_3100_windows":
                source_live_values_evidence["verified_windows"] if
                source_live_values_evidence is not None else 0,
            "source_live_values_3100_events":
                source_live_values_evidence["verified_events"] if
                source_live_values_evidence is not None else 0,
            "original_tach_calibration_verified":False,
        }
        (target/"SOURCE_WRITE_WINDOWS_AUDIT.json").write_text(
            json.dumps(receipt,indent=2,ensure_ascii=False)+"\n",
            encoding="utf-8")
        return {"source":SOURCE,"windows":len(ledger.windows),
                "files_written":len(emitted),"new_directory":str(target),
                "verified_frame_boundaries":bool(ledger.frame_marks_verified),
                "native_mark_requests":len(ledger.frame_mark_actions),
                "hardware_command_sent":bool(ledger.source_setrate_commands_seen),
                "source_setrate_sent_commands":ledger.source_setrate_commands_seen,
                "source_setrate_sent_bytes":(frame_mark_evidence or {}).get("source_setrate_sent_bytes"),
                "source_values_export_anchored_to_verified_3100":
                    source_values_events is not None,
                "source_3100_trigger_events_replayed":
                    sum(map(len,source_values_events.values())) if
                    source_values_events is not None else 0,
                "source_thread_auto_closed_writers":(frame_mark_evidence or {}).get(
                    "source_thread_auto_closed_writers",0),
                "source_write_data_wire_payload_files":len(source_wire_evidence),
                "source_write_data_wire_payload_byte_exact":
                    bool(source_wire_evidence),
                "source_write_data_delphi_rate_freeze_parity_verified":False,
                "source_live_source_gate_verified":
                    source_live_data_evidence is not None,
                "source_live_original_writer_files":
                    len(source_live_data_evidence["verified_channel_files"]) if
                    source_live_data_evidence is not None else 0,
                "source_live_original_packet_gate_records":
                    source_live_data_evidence["verified_source_packet_records"] if
                    source_live_data_evidence is not None else 0,
                "source_original_tsxml_structural_sidecars":
                    sum(item.get("sidecar_created",False) for item in
                        source_tsxml_receipts),
                "source_original_tsxml_delphi_full_parity_verified":False,
                "source_original_tsxml_skipped_by_operator":sum(
                    x.get("reason")=="ORIGINAL_XML_CHECKBOX_OFF"
                    for x in source_tsxml_receipts),
                "source_original_tsxml_settings_snapshot_verified":all(
                    w.file_options is not None for w in ledger.windows
                    if w.kind=="data"),
                "source_original_filename_algorithm_recovered":True,
                "source_live_values_3100_verified":
                    source_live_values_evidence is not None,
                "source_live_values_3100_windows":
                    source_live_values_evidence["verified_windows"] if
                    source_live_values_evidence is not None else 0,
                "source_live_values_3100_events":
                    source_live_values_evidence["verified_events"] if
                    source_live_values_evidence is not None else 0,
                "source_values_csv_exact_delphi_layout_verified":False}
    except Exception:
        if created:
            shutil.rmtree(target)
        raise
