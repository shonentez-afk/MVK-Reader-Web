"""Offline, local-only reference-vs-candidate Mode2 numerical/file comparator.

Compares a REAL operator-supplied original MVKView file with a candidate
output. No network, no device TX, no original EXE or private FIR banks.
Synthetic fixtures passing this comparator NEVER certify Win32 Delphi 1:1;
the original reference's physical provenance is independently unverified.

Kinds: ADC_BIN_F32, TACH_BIN_BYTES, GETSIGNAL_F32, GETSPECTRUM_POWER_F32,
       GETSPECTRUM_Y_F32, TSXML_CP1251, VALUES_CSV.
For numerical files: compare exact Single words and aggregate differences.
For exported files: compare bytes, SHA-256 and first mismatch, not guesses
about CSV delimiters, locale, Win32 timestamps or user-selected names.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import re

import numpy as np

KINDS=frozenset((
    "ADC_BIN_F32","TACH_BIN_BYTES","GETSIGNAL_F32",
    "GETSPECTRUM_POWER_F32","GETSPECTRUM_Y_F32",
    "TSXML_CP1251","VALUES_CSV",
))
FLOAT_KINDS=frozenset((
    "ADC_BIN_F32","GETSIGNAL_F32",
    "GETSPECTRUM_POWER_F32","GETSPECTRUM_Y_F32",
))
_FILE_NAME=re.compile(r"[A-Za-z0-9_\-. #$()А-Яа-я]{1,240}\Z")
_SHA=re.compile(r"[0-9a-f]{64}\Z")
MAX_PAIRS=40
MAX_PAIR_BYTES=128*1024*1024
MAX_TOTAL_BYTES=512*1024*1024


def _regular_dir(value):
    p=Path(value)
    if p.is_symlink() or not p.is_dir():
        raise ValueError("Mode2 paired evidence must use existing local directories")
    return p


def _safe_name(name):
    if (not isinstance(name,str) or not _FILE_NAME.fullmatch(name) or
            name.startswith(".") or ".." in name):
        raise ValueError("Mode2 paired evidence invalid file basename")
    return name


def _regular_file(directory,name):
    p=directory/_safe_name(name)
    if (p.is_symlink() or not p.is_file() or
            p.stat().st_size>MAX_PAIR_BYTES):
        raise ValueError("Mode2 paired evidence missing/linked/oversized file")
    return p


def _file_bytes(folder,name):
    p=_regular_file(folder,name)
    body=p.read_bytes()
    if len(body)>MAX_PAIR_BYTES:
        raise ValueError("Mode2 paired evidence changed during reading")
    return body


def _first_different_byte(before,after):
    return next((i for i,(a,b) in enumerate(zip(before,after))
                 if a!=b),min(len(before),len(after)) if
                 len(before)!=len(after) else None)


def _numeric_diff(before,after,kind):
    if len(before)%4 or len(after)%4 or not before or not after:
        raise ValueError("Mode2 Float32 evidence requires nonempty full words")
    x=np.frombuffer(before,dtype="<f4")
    y=np.frombuffer(after,dtype="<f4")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("Mode2 original/candidate Float32 contains NaN/Inf")
    comparable=min(len(x),len(y))
    bits=x[:comparable].view("<u4")==y[:comparable].view("<u4")
    err=np.abs(x[:comparable].astype(np.float64)-
               y[:comparable].astype(np.float64))
    ref=np.abs(x[:comparable].astype(np.float64))
    rel=err/np.maximum(ref,1e-9)
    original_count=len(x)
    candidate_count=len(y)
    return {
        "reference_float32_words":original_count,
        "candidate_float32_words":candidate_count,
        "bitwise_equal_float32_words":int(np.count_nonzero(bits)),
        "different_float32_words":int(comparable-np.count_nonzero(bits)
                                    +abs(original_count-candidate_count)),
        "max_absolute_error":float(np.max(err)),
        "median_relative_error":float(np.median(rel)),
        "p99_relative_error":float(np.quantile(rel,.99)),
        "first_different_float32_word":(
            int(np.flatnonzero(~bits)[0]) if not np.all(bits) else
            comparable if original_count!=candidate_count else None),
        "exact_float32_bitwise_match":bool(
            original_count==candidate_count and np.all(bits)),
    }


def compare_original_mode2_pair(
        reference_dir:Path|str,candidate_dir:Path|str,
        *,files:list[dict],session_id:str,
        reference_raw_name:str|None=None,
        candidate_raw_name:str|None=None,
)->dict:
    """Compare explicit same-measurement files; no inferred 1:1 parity.

    No actual instrument/Win32 ownership can be proven from file names or
    a synthetic test. Optional RAW is read and hashed from BOTH local
    directories; unequal RAW blocks any shared-input acceptance.
    """
    reference=_regular_dir(reference_dir)
    candidate=_regular_dir(candidate_dir)
    if (not isinstance(session_id,str) or not session_id or
            len(session_id)>120 or any(ord(c)<32 for c in session_id)):
        raise ValueError("Mode2 pair requires a named source measurement")
    if (not isinstance(files,list) or not 1<=len(files)<=MAX_PAIRS):
        raise ValueError("Mode2 paired evidence requires bounded file pairs")
    if (reference_raw_name is None)!=(candidate_raw_name is None):
        raise ValueError("Mode2 RAW proof must provide both streams")
    raw_proof=None
    total=0
    if reference_raw_name is not None:
        a=_file_bytes(reference,reference_raw_name)
        b=_file_bytes(candidate,candidate_raw_name)
        total+=len(a)+len(b)
        raw_proof={
            "reference_raw_sha256":sha256(a).hexdigest(),
            "candidate_raw_sha256":sha256(b).hexdigest(),
            "same_original_tcp_bytes":a==b,
            "reference_raw_bytes":len(a),
            "candidate_raw_bytes":len(b),
        }
        if not raw_proof["same_original_tcp_bytes"]:
            raise ValueError("Mode2 paired outputs originate from different RAW TCP streams")
    records=[]
    unique=set()
    for entry in files:
        if not isinstance(entry,dict) or set(entry)!={
                "kind","reference_name","candidate_name"}:
            raise ValueError("Mode2 paired file descriptor incomplete")
        kind=entry["kind"]
        if kind not in KINDS:
            raise ValueError("Mode2 paired output kind unsupported")
        a_name=_safe_name(entry["reference_name"])
        b_name=_safe_name(entry["candidate_name"])
        key=(kind,a_name,b_name)
        if key in unique:
            raise ValueError("Mode2 duplicate original/candidate pair")
        unique.add(key)
        a=_file_bytes(reference,a_name)
        b=_file_bytes(candidate,b_name)
        total+=len(a)+len(b)
        if total>MAX_TOTAL_BYTES:
            raise ValueError("Mode2 pair exceeds bounded local evidence budget")
        row={
            "kind":kind,
            "reference_file_sha256":sha256(a).hexdigest(),
            "candidate_file_sha256":sha256(b).hexdigest(),
            "reference_bytes":len(a),
            "candidate_bytes":len(b),
            "same_basename":a_name==b_name,
            "byte_identical":a==b,
            "first_different_byte":_first_different_byte(a,b),
        }
        if kind in FLOAT_KINDS:
            row.update(_numeric_diff(a,b,kind))
        records.append(row)
    equal=all(x["byte_identical"] for x in records)
    return {
        "schema":"MVK_ORIGINAL_MODE2_OPERATOR_LOCAL_COMPARISON_V1",
        "session_id":session_id,
        "reference_origin":"OPERATOR_SUPPLIED_NOT_AUTHENTICATED_BY_THIS_TOOL",
        "same_input_tcp_raw_verified":raw_proof is not None,
        "raw_proof":raw_proof,
        "file_pairs_compared":len(records),
        "all_pairs_byte_identical":bool(equal),
        "exact_file_contents_match_for_supplied_pairs":bool(equal),
        "original_delphi_compatibility_verified":False,
        "original_hardware_parity_verified":False,
        "original_1_to_1_release_gate_passed":False,
        "missing_original_runtime_x87_and_hardware_attestation":True,
        "no_device_commands":True,
        "no_original_binary_or_signal_bytes_in_report":True,
        "no_file_paths_in_report":True,
        "pairs":records,
    }


def main(argv=None)->int:
    parser=argparse.ArgumentParser(
        description="LOCAL compare MVKView original vs candidate Mode2 outputs")
    parser.add_argument("--reference-dir",required=True)
    parser.add_argument("--candidate-dir",required=True)
    parser.add_argument("--manifest",required=True,
                        help="local JSON: session_id, files, optional two RAW basenames")
    args=parser.parse_args(argv)
    manifest=Path(args.manifest)
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size>20000:
        parser.error("Manifest must be a small local regular JSON file")
    data=json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data,dict) or not {
            "session_id","files"}.issubset(data):
        parser.error("Manifest requires session_id and files")
    report=compare_original_mode2_pair(
        args.reference_dir,args.candidate_dir,
        files=data["files"],session_id=data["session_id"],
        reference_raw_name=data.get("reference_raw_name"),
        candidate_raw_name=data.get("candidate_raw_name"),
    )
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report["all_pairs_byte_identical"] else 2


if __name__=="__main__":
    raise SystemExit(main())
