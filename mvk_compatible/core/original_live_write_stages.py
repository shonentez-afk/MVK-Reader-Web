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
from .original_live_pagefile import OriginalLiveFilePlan
from .offline_measurement_flow import OfflineMeasurementFlow
from .offline_export import require_members
from .native_r6_tach_evidence import validate_tach_evidence
from .original_pagefile_recording import OriginalPageFileSelection
from .original_measure_controls import table_rows

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
    if payload.get("read_only_no_app_payload_sent") is not True:
        raise ValueError("Native capture must stay read-only")
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
        if count!=frames*(256 if number<=8 else 64):
            raise ValueError("Go source frames/samples mismatch")
        rates=ch.get("sample_rates_hz")
        if (not isinstance(rates,list) or len(rates)>3 or
                any(type(v) is not int or v not in SOURCE_RATES for v in rates)):
            raise ValueError("Native Go source rate values not checked")
        counters.append(count)
    aux=_int(payload.get("aux4700_updates"),"AUX updates")
    frames=_int(payload.get("frames_decoded"),"decoded frames")
    raw=_int(payload.get("raw_bytes"),"RAW bytes")
    if frames==0 or raw==0:
        raise ValueError("No read-only source frames")
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
            "hardware_command_sent":False,
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
        self.frame_marks_required=False
        self.frame_marks_verified=False
        self.frame_marks_failed=False
        self.frame_mark_actions=[]

    @property
    def trustworthy(self):
        # An operator frame-mark failure is terminal for this run.
        # A later good TCP status must not silently re-arm the same
        # source recording buttons with an unusable pending mark log.
        return (self._last is not None and not self.finished
                and not self.frame_marks_failed)

    def observe(self,payload):
        try:
            proof=_status_proof(payload)
            sid,counters,aux,frames,raw=proof
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

    def toggle(self,kind:str,plan:OriginalLiveFilePlan,*,now=None):
        if kind not in ("data","values"):
            raise ValueError("Unknown original source write flag")
        if not isinstance(plan,OriginalLiveFilePlan):
            raise ValueError("Source channel/SPEC/VALUES mask is missing")
        if not self.trustworthy:
            raise ValueError("Source recording requires verified active Go status")
        if plan.session_id is not None and plan.session_id!=self.session_id:
            raise ValueError("Operator checkboxes belong to another Native run")
        now=now or datetime.now(timezone.utc)
        if not isinstance(now,datetime) or now.tzinfo is None:
            raise ValueError("Operator write time must include timezone")
        stamp=now.astimezone(timezone.utc).isoformat()
        attr="_active_data" if kind=="data" else "_active_values"
        active=getattr(self,attr)
        if active is None:
            if sum(bool(x) for x in plan.channels)==0:
                raise ValueError("Original recorder cannot write zero channels")
            if kind=="values" and not (any(plan.values) or any(plan.spec)):
                raise ValueError("Original VALUES has zero selected result flags")
            if len(self.windows)>=MAX_WINDOWS:
                raise ValueError("At most eight checked local write intervals")
            _,samples,aux,frames,_=self._last
            setattr(self,attr,(plan,samples,aux,frames,stamp))
            if kind=="data":
                self.data_stage=STAGE_OPEN
            else:
                # Source 00809977 opens VALUES file directly into stage1.
                self.values_stage=STAGE_STREAMING
            return self.receipt()
        plan_open,start_samples,start_aux,start_frames,start_stamp=active
        _,end_samples,end_aux,end_frames,_=self._last
        if (any(b<a for a,b in zip(start_samples,end_samples))
                or end_aux<start_aux or end_frames<start_frames):
            self.invalidate("Source counter rolled backwards during write")
            raise ValueError("Original write counters went backwards")
        window=OriginalSourceWriteWindow(
            kind,self.session_id,plan_open.channels,plan_open.spec,
            plan_open.values,start_samples,end_samples,start_aux,end_aux,
            start_frames,end_frames,start_stamp,stamp)
        self.windows.append(window)
        setattr(self,attr,None)
        if kind=="data":
            self.data_stage=STAGE_IDLE
        else:
            self.values_stage=STAGE_IDLE
        return self.receipt()

    def register_native_frame_mark(self,receipt,plan):
        """Bind ONE actually queued GUI event to this authenticated run."""
        if (not self.trustworthy or
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
            if accepted and self._last is not None:
                for kind in ("data","values"):
                    attr="_active_data" if kind=="data" else "_active_values"
                    if getattr(self,attr) is not None:
                        # Finalization only knows the last Go status; it does
                        # not invent packets after the last status poll.
                        self.toggle(kind,getattr(self,attr)[0])
            else:
                self.invalidate("Capture ended without a verified ZIP")
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
            "has_verifiable_live_status":self.trustworthy,
            "errors":list(self.errors),
            "hardware_commands_sent":False,
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
            "hardware_command_sent":False,
            "original_tach_calibration_verified":False,
        }
        (target/"SOURCE_WRITE_WINDOWS_AUDIT.json").write_text(
            json.dumps(receipt,indent=2,ensure_ascii=False)+"\n",
            encoding="utf-8")
        return {"source":SOURCE,"windows":len(ledger.windows),
                "files_written":len(emitted),"new_directory":str(target),
                "verified_frame_boundaries":bool(ledger.frame_marks_verified),
                "native_mark_requests":len(ledger.frame_mark_actions),
                "hardware_command_sent":False}
    except Exception:
        if created:
            shutil.rmtree(target)
        raise
