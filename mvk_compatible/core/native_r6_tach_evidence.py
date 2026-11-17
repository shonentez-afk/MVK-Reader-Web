"""SHA-verified, *unscaled* TACH1/TACH2 raw input from Native R6.1.

This is explicitly NOT a source MVKView TACH BIN/TSXML or calibrated RPM.
The Go capture never transmits commands. TACH bytes are copied from the
already captured 284-byte original TCP packets. No sample value is changed.

A verifier must bind every optional TACH stream to the SAME original RAW SHA
and the SHA-checked Native ZIP, including old archives that contain no TACH.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import zipfile

from .original_mode2_gain_fallback import resolve_channel_gain_units

SCHEMA="MVK_NATIVE_R6_TACH_RAW_INPUT_V1"
FILENAME="TACH_RAW_SOURCE_AUDIT.json"
DOMAIN="DEVICE_TACH_INPUT_FLOAT32_UNSCALED"
SAMPLE_RATES={512,2048,8192,32768,65536}
_SHA=re.compile(r"[0-9a-f]{64}\Z")
_MAX_JSON=65536
_MAX_TACH_FILE=1024*1024*1024
_CHUNK=1024*1024


def _nat(value,name,maximum=2**64-1):
    if type(value) is not int or not 0<=value<=maximum:
        raise ValueError(f"Native TACH invalid {name}")
    return value


def _sha(value,name):
    if not isinstance(value,str) or not _SHA.fullmatch(value):
        raise ValueError(f"Native TACH missing or invalid SHA256: {name}")
    return value


@dataclass(frozen=True)
class NativeTachChannel:
    number:int  # 9/10 in Native 1-based enumeration, source TACH1/2
    present:bool
    filename:str|None
    frames:int
    samples:int
    byte_count:int
    first_index:int
    last_index:int
    sample_rate_hz:int
    discontinuities:int
    rate_changes:int
    digest:str|None
    continuous:bool
    source_calibrated:bool=False

    @property
    def safe_local_raw_export(self):
        # TACH may change sample frequency or skip packets; those bytes
        # remain forensic evidence, not a continuous measured signal.
        return self.present and self.continuous and not self.source_calibrated

    def receipt(self):
        # Original TMvkChannelStorage for 8/9 has static unity gain and
        # empty storage units; Native raw TACH bytes are NOT rescaled.
        source_storage = resolve_channel_gain_units(self.number - 1).receipt()
        return {
            "original_source_storage_gain_units":source_storage,
            "native_channel":self.number,
            "source_tab":"TACH"+str(self.number-8),
            "present":self.present,
            "frames":self.frames,
            "samples":self.samples,
            "rate_hz":self.sample_rate_hz if self.present else None,
            "sequence_gaps":self.discontinuities,
            "rate_changes":self.rate_changes,
            "sha256":self.digest,
            "safe_for_local_raw_export":self.safe_local_raw_export,
            "physical_rpm_verified":False,
            "original_mvkview_tach_format_verified":False,
            "original_tach_output_units_verified":False,
        }


@dataclass(frozen=True)
class NativeTachEvidence:
    source_raw_sha256:str
    channels:tuple[NativeTachChannel,NativeTachChannel]
    input_domain:str=DOMAIN
    provenance:str=SCHEMA

    @property
    def safe_native_channels(self):
        return tuple(c.number for c in self.channels
                     if c.safe_local_raw_export)

    def receipt(self):
        return {
            "source":self.provenance,
            "source_raw_sha256":self.source_raw_sha256,
            "input_domain":self.input_domain,
            "channels":[c.receipt() for c in self.channels],
            "safe_native_tach_channels":list(self.safe_native_channels),
            "device_commands_sent":False,
            "source_tach_bin_tsxml_created":False,
            "physical_rpm_calibration_verified":False,
        }


def _digest_member(archive:zipfile.ZipFile,name:str,size:int):
    info=archive.getinfo(name)
    if info.file_size!=size or info.file_size>_MAX_TACH_FILE:
        raise ValueError("Native TACH source byte count changed")
    digest=sha256()
    count=0
    with archive.open(name) as stream:
        while True:
            piece=stream.read(_CHUNK)
            if not piece:
                break
            count+=len(piece)
            if count>size:
                raise ValueError("Native TACH stream exceeds declared bytes")
            digest.update(piece)
    if count!=size:
        raise ValueError("Native TACH stream truncated")
    return digest.hexdigest()


def validate_tach_evidence(archive:zipfile.ZipFile,
                           audit:dict)->NativeTachEvidence|None:
    """Bound only to independently verified Native ZIP + export audit.

    Legacy 19-member Stage107/R6.1 exports have no sidecar and remain valid.
    Any unmanifested sidecar, raw data, malformed indexes or altered bytes
    rejects the complete source (no silent fallback to ADC-only).
    """
    if not isinstance(audit,dict) or not isinstance(
            audit.get("output_file_sha256"),dict):
        raise ValueError("Native TACH requires an authenticated export manifest")
    manifest=audit["output_file_sha256"]
    members=archive.namelist()
    declared=FILENAME in manifest
    present=FILENAME in members
    tach_names={f"TACH{i}_NATIVE_UNCALIBRATED.f32" for i in (1,2)}
    if not declared and not present:
        if tach_names.intersection(set(members)|set(manifest)):
            raise ValueError("Unverified TACH files without source audit")
        return None
    if declared!=present:
        raise ValueError("TACH provenance sidecar not paired with manifest")
    blob=archive.getinfo(FILENAME)
    if blob.file_size>_MAX_JSON:
        raise ValueError("TACH source audit exceeds fixed schema bound")
    raw=archive.read(FILENAME)
    if sha256(raw).hexdigest()!=_sha(manifest[FILENAME],FILENAME):
        raise ValueError("TACH provenance SHA256 mismatch")
    try:
        doc=json.loads(raw)
    except (UnicodeError,ValueError) as exc:
        raise ValueError("TACH source audit not JSON") from exc
    if (not isinstance(doc,dict) or doc.get("schema")!=SCHEMA
            or doc.get("input_domain")!=DOMAIN
            or doc.get("device_commands_sent") is not False
            or doc.get("original_tach_bin_parity_verified") is not False):
        raise ValueError("TACH provenance cannot claim original calibration")
    raw_sha=_sha(doc.get("source_raw_sha256"),"source RAW")
    if raw_sha!=_sha(audit.get("source_raw_sha256"),"export RAW"):
        raise ValueError("TACH source from another capture")
    rows=doc.get("channels")
    if not isinstance(rows,list) or len(rows)!=2:
        raise ValueError("TACH evidence must list exactly two original channels")
    validated=[]
    declared_files=set()
    for i,row in enumerate(rows,1):
        if not isinstance(row,dict) or _nat(row.get("channel"),"channel",10)!=8+i:
            raise ValueError("TACH channel index/order changed")
        visible=row.get("present")
        if type(visible) is not bool or row.get(
                "physical_calibration_verified") is not False:
            raise ValueError("TACH source cannot assert physical calibration")
        frames=_nat(row.get("frames"),"frames")
        samples=_nat(row.get("samples"),"samples")
        size=_nat(row.get("bytes"),"bytes")
        gaps=_nat(row.get("sequence_discontinuities"),"gaps")
        changes=_nat(row.get("sample_rate_changes"),"rate changes")
        first=_nat(row.get("first_sample_index"),"first index",2**32-1)
        last=_nat(row.get("last_frame_first_sample_index"),"last index",2**32-1)
        rate=_nat(row.get("first_sample_rate_hz"),"rate",2**32-1)
        continuous=row.get("contiguous_constant_rate")
        if type(continuous) is not bool:
            raise ValueError("TACH continuity assertion not Boolean")
        if visible:
            filename=f"TACH{i}_NATIVE_UNCALIBRATED.f32"
            if (row.get("filename")!=filename or frames==0
                    or samples!=frames*64 or size!=samples*4
                    or rate not in SAMPLE_RATES
                    or continuous!=(gaps==0 and changes==0)):
                raise ValueError("TACH source Float32 frame/index contract failed")
            if filename not in manifest or filename not in members:
                raise ValueError("TACH raw Float32 payload missing")
            digest=_sha(row.get("sha256"),filename)
            if _sha(manifest[filename],filename)!=digest:
                raise ValueError("TACH raw SHA changed in source manifest")
            if _digest_member(archive,filename,size)!=digest:
                raise ValueError("TACH raw payload modified after capture")
            declared_files.add(filename)
        else:
            filename=None
            digest=None
            if (frames or samples or size or gaps or changes or first
                    or last or rate or continuous or row.get("filename")
                    or row.get("sha256")):
                raise ValueError("Absent TACH cannot contain invented samples")
        validated.append(NativeTachChannel(
            8+i,visible,filename,frames,samples,size,first,last,rate,
            gaps,changes,digest,continuous))
    if (set(manifest)|set(members)).intersection(tach_names)!=declared_files:
        raise ValueError("Unexpected or unmanifested TACH stream")
    return NativeTachEvidence(raw_sha,tuple(validated))


def read_tach_evidence(path:str|Path)->NativeTachEvidence|None:
    """Always recheck sidecar/data SHA on the current on-disk ZIP."""
    with zipfile.ZipFile(path) as archive:
        try:
            metadata=json.loads(archive.read("EXPORT_AUDIT.json"))
        except (KeyError,UnicodeError,ValueError) as exc:
            raise ValueError("Missing verified native export audit") from exc
        return validate_tach_evidence(archive,metadata)
