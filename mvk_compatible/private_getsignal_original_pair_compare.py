"""Stage111Z29A: read-only local original GetSignal output vs Native R6 BIN.

Usage (PRIVATE local workstation; no upload to GitHub/CI):
python -m mvk_compatible.private_getsignal_original_pair_compare \
    --source-native-zip C:\MVK_LOCAL\completed.zip \
    --original-getsignal-bin C:\MVK_LOCAL\getsignal_return.bin \
    --channel 1 --first-sample 0 --sample-count 65536 --mode ac

The original x32dbg buffer must be *GetSignal's RETURN array* (reversed
order, _Unit115:007D0DEC), not chronological BIN or pre-FFT data. Explicit
mode and BIN sample window come from the operator: NEVER guess them.
A zero-only return is uninformative, and same-run process/capture identity
is NOT established merely because two arrays happen to be bit-equal.

Private values, filenames and directory paths are NEVER printed or saved.
This diagnostic never opens a network connection, writes to a source file,
or sends instrument commands. It uses only already audited Native ZIP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from .core.offline_export import OfflineSession
from .core.signal_idr_candidate import unfiltered_getsignal
from .core.getsignal_input_evidence import archive_input_window_evidence

SOURCE="LOCAL_OPERATOR_GETSIGNAL_RETURN_VS_AUDITED_NATIVE_BIN_FLOAT32_V1"
MAX_SAMPLES=262144


def _read_original_return(p: str | Path, n: int) -> np.ndarray:
    path=Path(p)
    if (path.is_symlink() or not path.is_file() or
            path.suffix.lower() != ".bin" or
            path.stat().st_size != n*4):
        raise ValueError("Invalid original GetSignal return dump length or local path")
    data=np.fromfile(path,dtype="<f4")
    if len(data)!=n or not bool(np.isfinite(data).all()):
        raise ValueError("Invalid original GetSignal return Float32 values")
    if not bool(np.count_nonzero(data)):
        raise ValueError("Original GetSignal return is all zero; not an informative golden")
    return data


def compare_original_getsignal_return(source_native_zip: str | Path,
                                      original_return_bin: str | Path, *,
                                      channel: int, first_sample: int,
                                      sample_count: int, mode: str) -> dict:
    """Compare a declared source channel/window to an operator-provided array.

    Source XOR process/capture provenance is strictly UNKNOWN even when
    all f32 words agree. No rejected bytes are included in the report.
    """
    if (type(channel) is not int or not 1<=channel<=8 or
            type(first_sample) is not int or first_sample<0 or
            type(sample_count) is not int or
            not 1<=sample_count<=MAX_SAMPLES or mode not in ("ac","acdc")):
        raise ValueError("Invalid explicit GetSignal channel/window/mode")
    session=OfflineSession.open(source_native_zip)
    samples,fs,audit,_=session.samples(channel)
    last=first_sample+sample_count
    if last>len(samples):
        raise ValueError("Audited Native BIN lacks full original window")
    evidence=archive_input_window_evidence(
        samples,first=first_sample,end=last,sample_rate_hz=fs,
        native_audit=True,channel=channel,
        source_raw_sha256=audit["source_raw_sha256"])
    reference=_read_original_return(original_return_bin,sample_count)
    local=unfiltered_getsignal(
        samples[first_sample:last],fs,no_dc=(mode=="ac"))
    candidate=local.getsignal_buffer
    if not bool(np.isfinite(candidate).all()):
        raise ValueError("Invalid derived Float32 GetSignal output")
    expected=reference.view("<u4")
    got=candidate.view("<u4")
    exact=expected==got
    # Ordered float bit representation for robust ULP summary across signs;
    # stay within signed int64 after folding the 32-bit word.
    def ordered(words):
        values=words.astype(np.uint64)
        return np.where(values & 0x80000000,
                        np.uint64(0x80000000)-(values & 0x7fffffff),
                        values | 0x80000000).astype(np.int64)
    distance=np.abs(ordered(expected)-ordered(got))
    mismatch=np.flatnonzero(~exact)
    return {
        "source":SOURCE,
        "channel":channel,
        "first_archive_sample_index":first_sample,
        "sample_count":sample_count,
        "mode":mode,
        "source_sample_rate_hz":fs,
        "input_source_window_float32_sha256":evidence[
            "source_float32_le_sha256"],
        "original_getsignal_output_sha256":hashlib.sha256(
            reference.tobytes()).hexdigest(),
        "candidate_output_sha256":hashlib.sha256(
            candidate.tobytes()).hexdigest(),
        "float32_words_exact":int(exact.sum()),
        "float32_words_total":sample_count,
        "float32_first_mismatch_index":(
            int(mismatch[0]) if len(mismatch) else None),
        "float32_ulp_max":int(distance.max()),
        "float32_ulp_median":float(np.median(distance)),
        "candidate_output_matches_operator_dump_bitwise":bool(np.all(exact)),
        "no_second_f_range_calibration_applied":True,
        "original_return_buffer_expected_reverse_order":True,
        "original_same_run_identity_authenticated":False,
        "original_frange_and_ring_end_runtime_verified":False,
        "original_pageadc_pixel_parity_verified":False,
        "private_byte_values_or_source_paths_in_report":False,
    }


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(
        description="Local, read-only original GetSignal return-buffer comparison")
    parser.add_argument("--source-native-zip",required=True)
    parser.add_argument("--original-getsignal-bin",required=True)
    parser.add_argument("--channel",type=int,required=True)
    parser.add_argument("--first-sample",type=int,required=True)
    parser.add_argument("--sample-count",type=int,required=True)
    parser.add_argument("--mode",choices=("ac","acdc"),required=True)
    args=parser.parse_args(argv)
    try:
        result=compare_original_getsignal_return(
            args.source_native_zip,args.original_getsignal_bin,
            channel=args.channel,first_sample=args.first_sample,
            sample_count=args.sample_count,mode=args.mode)
    except (ValueError,TypeError,OSError,OverflowError):
        parser.exit(2,"Original GetSignal capture cannot be compared; private details withheld\n")
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    return 0 if result["candidate_output_matches_operator_dump_bitwise"] else 1


if __name__=="__main__":
    raise SystemExit(main())
