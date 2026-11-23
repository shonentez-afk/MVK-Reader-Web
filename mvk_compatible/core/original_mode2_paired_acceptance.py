"""Offline, local-only reference-vs-candidate Mode2 numerical/file comparator.

Compares a REAL operator-supplied original MVKView file with a candidate
output. No network, no device TX, no original EXE or private FIR banks.
Synthetic fixtures passing this comparator NEVER certify Win32 Delphi 1:1;
the original reference's physical provenance is independently unverified.

Kinds: ADC_BIN_F32, TACH_BIN_BYTES, GETSIGNAL_F32, GETSPECTRUM_POWER_F32,
       GETSPECTRUM_Y_F32, TSXML_CP1251, VALUES_CSV, TABLE_CSV.
Optional source-stage pairs: PRE_HANN_F32, WINDOWED_F32, FFT_COMPLEX_F32
(interleaved Re,Im), POSTMODE_POWER_F32. Stop runtime not attested.
The operator can attach source_spectrum_mode=0..3 to Y and POSTMODE_POWER
files. All four mode tags + Tag2/3 intermediate Power, full stages and
matching RAW are required for a complete explicit four-mode comparison.
No file comparison alone authenticates original Win32 runtime/window.
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
    "GETSPECTRUM_PRE_HANN_F32","GETSPECTRUM_WINDOWED_F32",
    "GETSPECTRUM_FFT_COMPLEX_F32","GETSPECTRUM_POSTMODE_POWER_F32",
    "TSXML_CP1251","VALUES_CSV","TABLE_CSV",
))
FLOAT_KINDS=frozenset((
    "ADC_BIN_F32","GETSIGNAL_F32",
    "GETSPECTRUM_POWER_F32","GETSPECTRUM_Y_F32",
    "GETSPECTRUM_PRE_HANN_F32","GETSPECTRUM_WINDOWED_F32",
    "GETSPECTRUM_FFT_COMPLEX_F32","GETSPECTRUM_POSTMODE_POWER_F32",
))
_FILE_NAME=re.compile(r"[A-Za-z0-9_\-. #$()А-Яа-я]{1,240}\Z")
_SHA=re.compile(r"[0-9a-f]{64}\Z")
MAX_PAIRS=40
MAX_PAIR_BYTES=128*1024*1024
MAX_TOTAL_BYTES=512*1024*1024
MAX_RAW_BYTES=2048*1024*1024
RAW_CHUNK_BYTES=2*1024*1024


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


def _regular_file(directory,name,*,limit=MAX_PAIR_BYTES):
    p=directory/_safe_name(name)
    if (p.is_symlink() or not p.is_file() or
            p.stat().st_size>limit):
        raise ValueError("Mode2 paired evidence missing/linked/oversized file")
    return p


def _file_bytes(folder,name):
    p=_regular_file(folder,name)
    body=p.read_bytes()
    if len(body)>MAX_PAIR_BYTES:
        raise ValueError("Mode2 paired evidence changed during reading")
    return body


def _stream_same_original_tcp_raw(reference,candidate,ref_name,new_name):
    """Bounded streaming RAW SHA: up to 2 GiB per file, no full RAM copy.

    Both files must remain immutable during the compare. A live writer
    changing the source invalidates provenance even if the current bytes
    happen to match. Do not follow symlinks or return private paths.
    """
    ra=_regular_file(reference,ref_name,limit=MAX_RAW_BYTES)
    cb=_regular_file(candidate,new_name,limit=MAX_RAW_BYTES)
    original_info,clone_info=ra.stat(),cb.stat()
    if not original_info.st_size or not clone_info.st_size:
        raise ValueError("Mode2 original TCP RAW must contain received bytes")
    original_sha,candidate_sha=sha256(),sha256()
    original_size,candidate_size=0,0
    same=original_info.st_size==clone_info.st_size
    with ra.open("rb") as original,cb.open("rb") as clone:
        while True:
            x=original.read(RAW_CHUNK_BYTES)
            y=clone.read(RAW_CHUNK_BYTES)
            if not x and not y:
                break
            original_sha.update(x);candidate_sha.update(y)
            original_size+=len(x);candidate_size+=len(y)
            if x!=y:
                same=False
    if (ra.stat().st_size!=original_info.st_size or
            cb.stat().st_size!=clone_info.st_size or
            ra.stat().st_mtime_ns!=original_info.st_mtime_ns or
            cb.stat().st_mtime_ns!=clone_info.st_mtime_ns or
            original_size!=original_info.st_size or
            candidate_size!=clone_info.st_size):
        raise ValueError("Mode2 paired original TCP RAW changed while reading")
    return {
        "reference_raw_sha256":original_sha.hexdigest(),
        "candidate_raw_sha256":candidate_sha.hexdigest(),
        "same_original_tcp_bytes":bool(same),
        "reference_raw_bytes":original_size,
        "candidate_raw_bytes":candidate_size,
        "comparison_method":"BOUNDED_STREAMING_SHA256_AND_BYTE_EQUALITY",
    }


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
    if kind=="GETSPECTRUM_FFT_COMPLEX_F32" and (
            len(x)%2 or len(y)%2):
        raise ValueError("Mode2 FFT complex requires interleaved Re/Im Single pairs")
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
        raw_proof=_stream_same_original_tcp_raw(
            reference,candidate,reference_raw_name,candidate_raw_name)
        if not raw_proof["same_original_tcp_bytes"]:
            raise ValueError("Mode2 paired outputs originate from different RAW TCP streams")
    records=[]
    unique=set()
    mode_pairs=set()
    tagged_reference_files=set()
    tagged_candidate_files=set()
    for entry in files:
        basic={"kind","reference_name","candidate_name"}
        if (not isinstance(entry,dict) or
                set(entry) not in (basic,basic|{"source_spectrum_mode"})):
            raise ValueError("Mode2 paired file descriptor incomplete")
        kind=entry["kind"]
        if kind not in KINDS:
            raise ValueError("Mode2 paired output kind unsupported")
        mode=entry.get("source_spectrum_mode")
        if "source_spectrum_mode" in entry:
            if (kind not in ("GETSPECTRUM_Y_F32",
                             "GETSPECTRUM_POSTMODE_POWER_F32")
                    or type(mode) is not int or not 0<=mode<=3):
                raise ValueError("Mode2 spectrum mode requires Tag0..3 Y/Power")
            pair_mode=(kind,mode)
            if pair_mode in mode_pairs:
                raise ValueError("Mode2 duplicate original spectrum mode Tag")
            mode_pairs.add(pair_mode)
        a_name=_safe_name(entry["reference_name"])
        b_name=_safe_name(entry["candidate_name"])
        key=(kind,a_name,b_name)
        if key in unique:
            raise ValueError("Mode2 duplicate original/candidate pair")
        unique.add(key)
        if mode is not None:
            # A single original Y file cannot represent all four modes.
            # Source modes imply distinct local named Y/power artifacts.
            orig_key=(kind,a_name)
            clone_key=(kind,b_name)
            if (orig_key in tagged_reference_files or
                    clone_key in tagged_candidate_files):
                raise ValueError("Mode2 same tagged spectrum file reused")
            tagged_reference_files.add(orig_key)
            tagged_candidate_files.add(clone_key)
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
        if mode is not None:
            row["source_spectrum_mode"]=mode
        records.append(row)
    equal=all(x["byte_identical"] for x in records)
    found={x["kind"] for x in records}
    spectrum_families=frozenset((
        "GETSPECTRUM_PRE_HANN_F32","GETSPECTRUM_WINDOWED_F32",
        "GETSPECTRUM_FFT_COMPLEX_F32","GETSPECTRUM_POWER_F32",
        "GETSPECTRUM_POSTMODE_POWER_F32","GETSPECTRUM_Y_F32"))
    writer_families=frozenset((
        "ADC_BIN_F32","TSXML_CP1251","VALUES_CSV","TABLE_CSV"))
    tagged_y={r["source_spectrum_mode"]:r for r in records
              if r["kind"]=="GETSPECTRUM_Y_F32"
              and "source_spectrum_mode" in r}
    tagged_post_power={r["source_spectrum_mode"]:r for r in records
                       if r["kind"]=="GETSPECTRUM_POSTMODE_POWER_F32"
                       and "source_spectrum_mode" in r}
    all_four_y=set(tagged_y)==set(range(4))
    all_integrations={2,3}.issubset(tagged_post_power)
    explicit_four_mode_comparison=(all_four_y and all_integrations and
        spectrum_families.issubset(found) and raw_proof is not None)
    mode_comparison_equal=bool(explicit_four_mode_comparison and
        all(r["byte_identical"] for r in
            list(tagged_y.values())+[
                tagged_post_power[2],tagged_post_power[3]]))
    return {
        "schema":"MVK_ORIGINAL_MODE2_OPERATOR_LOCAL_COMPARISON_V1",
        "session_id":session_id,
        "reference_origin":"OPERATOR_SUPPLIED_NOT_AUTHENTICATED_BY_THIS_TOOL",
        "same_input_tcp_raw_verified":raw_proof is not None,
        "raw_proof":raw_proof,
        "file_pairs_compared":len(records),
        "source_hann_fft_power_intermediate_families_supplied":(
            spectrum_families.issubset(found)),
        "source_spectrum_y_pair_count":sum(
            x["kind"]=="GETSPECTRUM_Y_F32" for x in records),
        "source_four_mode_y_tags_explicitly_supplied":sorted(tagged_y),
        "source_integrated_postmode_power_tags_explicitly_supplied":(
            sorted(tagged_post_power)),
        "source_four_mode_y_tag_coverage_complete":bool(all_four_y),
        "source_same_raw_four_mode_numeric_comparison_complete":bool(
            explicit_four_mode_comparison),
        "source_same_raw_four_mode_numeric_pairs_byte_identical":(
            mode_comparison_equal),
        "source_all_four_modes_original_win32_same_window_attested":False,
        "source_write_data_values_output_families_supplied":(
            writer_families.issubset(found)),
        "source_stop_boundary_authenticated_with_original_win32":False,
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
