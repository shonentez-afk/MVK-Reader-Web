#!/usr/bin/env python3
"""Independent, read-only verification of MVKView EnvelopeCode20 input.

Checks both: (a) unique exact normalized Float32 match inside a physical ADC1
BIN file; (b) the new FIR work buffer's tail against an earlier captured
original LOG pre-DC buffer. Does not control x32dbg, prove memory provenance,
calculate FIR/FFT, or transmit original measurements.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path
import numpy as np


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def check(work: bytes, bin_bytes: bytes, log_capture_bytes: bytes,
          *, frange_bits: int = 0x43FF4853, extra_taps: int = 51,
          raw_n: int = 262195, expected_end: int | None = 1965425) -> dict:
    if len(work) != raw_n * 4:
        raise ValueError(f"work raw length must be {raw_n*4} bytes; got {len(work)}")
    if len(bin_bytes) % 4:
        raise ValueError("physical BIN size is not a multiple of Float32")
    f_range = struct.unpack('<f', struct.pack('<I', frange_bits))[0]
    if not np.isfinite(f_range) or f_range <= 0:
        raise ValueError("FRange must be a finite positive Float32")
    arr = np.frombuffer(work, dtype='<f4')
    bin_arr = np.frombuffer(bin_bytes, dtype='<f4')
    if not np.isfinite(arr).all() or not np.isfinite(bin_arr).all():
        raise ValueError("input contains NaN or infinity")
    if raw_n > bin_arr.size:
        raise ValueError("work longer than BIN")
    with zipfile.ZipFile(__import__('io').BytesIO(log_capture_bytes)) as z:
        with z.open('input_normalized_pre_dc.bin') as f:
            old_pre_dc = f.read()
    if len(old_pre_dc) != (raw_n-extra_taps)*4:
        raise ValueError("prior original LOG buffer does not have expected 262144 Float32")
    if extra_taps <= 0 or extra_taps >= raw_n:
        raise ValueError("invalid number of FIR lead-in samples")
    suffix = work[extra_taps*4:]
    overlap = sum(1 for i in range(0,len(suffix),4)
                  if suffix[i:i+4] == old_pre_dc[i:i+4])
    normalized = np.asarray(bin_arr / np.float32(f_range), dtype=np.float32)
    work_u = arr.view('<u4')
    norm_u = normalized.view('<u4')
    candidate_indices = np.flatnonzero(norm_u[:norm_u.size-raw_n+1] == work_u[0])
    exact_indices = [int(i) for i in candidate_indices
                     if np.array_equal(norm_u[i:i+raw_n], work_u)]
    physical_end = exact_indices[0]+raw_n if len(exact_indices)==1 else None
    ok = (len(exact_indices)==1 and
          overlap==raw_n-extra_taps and
          (expected_end is None or physical_end==expected_end))
    result = {
        'status': ('FULL_PHYSICAL_ADC1_AND_PREVIOUS_LOG_BITWISE_PASS' if ok else 'REJECT'),
        'source_provenance_note': ('Match proves numeric identity of supplied bytes;'
                                   ' it does not independently authenticate the live x32dbg process.'),
        'raw_input_samples': raw_n,
        'raw_input_bytes': len(work),
        'fir_leadin_samples': extra_taps,
        'log_overlap_samples_exact': overlap,
        'log_overlap_expected': raw_n-extra_taps,
        'f_range_bits': f'0x{frange_bits:08X}',
        'normalized_bin_unique_matches': exact_indices,
        'physical_bin_end_exclusive': physical_end,
        'expected_end_exclusive': expected_end,
        'work_sha256': sha(work),
        'bin_sha256': sha(bin_bytes),
        'prior_log_capture_sha256': sha(log_capture_bytes),
        'prior_log_pre_dc_sha256': sha(old_pre_dc),
        'matched_normalized_sha256': (sha(normalized[exact_indices[0]:physical_end].tobytes())
                                       if physical_end is not None else None),
        'matched_physical_bin_window_sha256': (sha(bin_arr[exact_indices[0]:physical_end].tobytes())
                                               if physical_end is not None else None),
        'pre_dc_mean': float(arr.mean(dtype=np.float64)),
        'first_zero_samples': int(np.argmax(arr.view('u4')!=0)) if np.any(arr.view('u4')!=0) else raw_n,
        'post_fir_n_expected_not_runtime_verified': (raw_n - extra_taps)//2,
        'post_fir_half_bins_expected_not_runtime_verified': (raw_n - extra_taps)//4,
    }
    return result


def cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--adc1-bin', dest='adc', type=Path, required=True)
    parser.add_argument('--previous-log-capture', dest='old', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--expected-end', type=int, default=1965425)
    args = parser.parse_args()
    try:
        result=check(args.work.read_bytes(), args.adc.read_bytes(), args.old.read_bytes(),
                     expected_end=args.expected_end)
    except (ValueError, OSError, zipfile.BadZipFile, KeyError) as exc:
        result={'status':'REJECT', 'reason':str(exc)}
    output=json.dumps(result,ensure_ascii=False,indent=2)
    print(output)
    if args.report:
        args.report.write_text(output+'\n',encoding='utf-8')
    return 0 if result['status'].endswith('_PASS') else 2


if __name__=='__main__':
    sys.exit(cli())
