"""Stage111Z29C1: PRIVATE original GetSignal ENVELOPE return vs R6 ZIP+IDP.

No original samples or proprietary FIR banks are included in source or CI.
The tool requires THREE operator-local files: a completed SHA-audited Native
R6 ZIP; the user's exact original mvkview.idp with pinned SHA; and a
Float32 little-endian original GetSignal RETURN BUFFER from x32dbg.
Its GetSignal buffer is reversed; it is NOT the already-windowed FFT input.

Usage:
  python -m mvk_compatible.private_getsignal_envelope_compare \
    --source-native-zip "C:\MVK_PRIVATE\capture.zip" \
    --local-original-idp "C:\MVK_PRIVATE\mvkview.idp" \
    --original-getsignal-bin "C:\MVK_PRIVATE\envelope_return.bin" \
    --channel 1 --first-sample 1000 --input-samples 4096 \
    --envelope-code 20 --f-range 1.0 --output-samples 2022

The output-samples value is an example ONLY; the operator must copy the
actual Params+0x28 OutputLength from original runtime. Do not guess it.
All input paths/measurement numbers are local; summary contains no path,
individual original Float32 output, coefficient arrays or raw BIN bytes.
No network activity or instrument commands.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math

import numpy as np

from .core.offline_export import OfflineSession
from .core.envelope_idr_candidate import (
    EnvelopeProfile, process_original_envelope_candidate)
from .core.getsignal_input_evidence import archive_input_window_evidence
from .private_getsignal_original_pair_compare import _read_original_return

SCHEMA="LOCAL_OPERATOR_ORIGINAL_GETSIGNAL_ENVELOPE_RETURN_COMPARE_V1"
MAX_SOURCE=2_000_000
MAX_OUTPUT=500_000


def compare_original_getsignal_envelope_return(
    source_native_zip, original_idp, original_return_bin, *,
    channel:int, first_sample:int, input_samples:int,
    envelope_code:int, f_range:float, output_samples:int
)->dict:
    if (type(channel) is not int or not 1<=channel<=8 or
        type(first_sample) is not int or first_sample<0 or
        type(input_samples) is not int or not 1<=input_samples<=MAX_SOURCE or
        type(envelope_code) is not int or not 1<=envelope_code<=31 or
        type(output_samples) is not int or not 1<=output_samples<=MAX_OUTPUT or
        type(f_range) not in (float,int) or
        not math.isfinite(f_range) or f_range<=0):
        raise ValueError("Invalid original GetSignal envelope metadata")
    # A runtime-provided Float32 FRange is rounded ONCE before candidate
    # arithmetic. It is not inferred or re-estimated from spectrum matching.
    effective_range=float(np.float32(f_range))
    if not math.isfinite(effective_range) or effective_range<=0:
        raise ValueError("Invalid Float32 original FRange")
    profile=EnvelopeProfile.from_original_local_idp(original_idp)
    source=OfflineSession.open(source_native_zip)
    samples,fs,audit,_=source.samples(channel)
    if not fs.is_integer():
        raise ValueError("Original envelope requires integer sample rate")
    end=first_sample+input_samples
    if end>len(samples):
        raise ValueError("Insufficient real audited BIN history, zero padding prohibited")
    provenance=archive_input_window_evidence(
        samples,first=first_sample,end=end,sample_rate_hz=fs,
        native_audit=True,channel=channel,
        source_raw_sha256=audit.get("source_raw_sha256"))
    result=process_original_envelope_candidate(
        samples[first_sample:end],int(fs),envelope_code,
        profile,f_range=effective_range)
    if result["output_samples"] != output_samples:
        raise ValueError("Original returned OutputLength and candidate FIR output length disagree")
    actual=_read_original_return(original_return_bin,output_samples)
    candidate=result["getsignal_buffer"]
    if len(actual)!=len(candidate) or not bool(np.isfinite(candidate).all()):
        raise ValueError("Invalid finite original/candidate envelope buffer size")
    original_bits=actual.view("<u4")
    candidate_bits=np.asarray(candidate,dtype="<f4").view("<u4")
    exact=original_bits==candidate_bits

    def order(b):
        w=b.astype(np.uint64)
        return np.where(w & 0x80000000,
                        np.uint64(0x80000000)-(w & 0x7fffffff),
                        w | np.uint64(0x80000000)).astype(np.int64)

    diff=np.abs(order(original_bits)-order(candidate_bits))
    mismatched=np.flatnonzero(~exact)
    return {
        "schema":SCHEMA,
        "channel":channel,
        "envelope_code":envelope_code,
        "source_sample_rate_hz":int(fs),
        "first_archive_sample_index":first_sample,
        "input_sample_count":input_samples,
        "output_sample_count":output_samples,
        "source_float32_le_sha256":provenance["source_float32_le_sha256"],
        "original_return_float32_le_sha256":hashlib.sha256(actual.tobytes()).hexdigest(),
        "candidate_return_float32_le_sha256":hashlib.sha256(candidate.tobytes()).hexdigest(),
        "float32_words_exact":int(exact.sum()),
        "float32_words_total":output_samples,
        "first_float32_mismatch_index":(
            int(mismatched[0]) if len(mismatched) else None),
        "float32_ulp_max":int(diff.max()),
        "float32_ulp_median":float(np.median(diff)),
        "candidate_matches_operator_captured_reverse_buffer_bitwise":bool(np.all(exact)),
        "original_idp_fingerprint_verified":True,
        "original_f_range_from_original_runtime_verified":False,
        "original_same_run_device_and_window_authenticated":False,
        "original_x87_extended_runtime_parity_verified":False,
        "original_envelope_spectrum_four_mode_parity_verified":False,
        "original_pageadc_ui_parity_verified":False,
        "private_sources_paths_coefficients_and_values_in_report":False,
    }


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(
        description="Private read-only GetSignal envelope Float32 output comparison")
    parser.add_argument("--source-native-zip",required=True)
    parser.add_argument("--local-original-idp",required=True)
    parser.add_argument("--original-getsignal-bin",required=True)
    parser.add_argument("--channel",type=int,required=True)
    parser.add_argument("--first-sample",type=int,required=True)
    parser.add_argument("--input-samples",type=int,required=True)
    parser.add_argument("--envelope-code",type=int,required=True)
    parser.add_argument("--f-range",type=float,required=True)
    parser.add_argument("--output-samples",type=int,required=True)
    a=parser.parse_args(argv)
    try:
        result=compare_original_getsignal_envelope_return(
            a.source_native_zip,a.local_original_idp,a.original_getsignal_bin,
            channel=a.channel,first_sample=a.first_sample,
            input_samples=a.input_samples,envelope_code=a.envelope_code,
            f_range=a.f_range,output_samples=a.output_samples)
    except (ValueError,TypeError,RuntimeError,OSError,OverflowError):
        parser.exit(2,"Private envelope return cannot be verified; source details withheld\n")
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    return 0 if result["candidate_matches_operator_captured_reverse_buffer_bitwise"] else 1


if __name__=="__main__":
    raise SystemExit(main())
