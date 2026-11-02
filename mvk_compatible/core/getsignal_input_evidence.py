"""Stage111Z29A: same-source input-window evidence for GetSignal & GetSpectrum.

The original methods are *different*: GetSignal may omit DC removal in AC+DC,
returns a reverse-ordered buffer and has its own RMS; GetSpectrum ALWAYS
removes mean and applies Hann before IDR FFT. A matching preprocessed input
SHA proves only that our TWO local candidates picked identical archive BIN
samples. It is NOT same-run original MVKView parity.

No writes, sockets, GPS/PC clock inference, or calibration reapplication.
"""
from __future__ import annotations

import hashlib
import math
import numpy as np

SCHEMA="MVK_GETSIGNAL_GETSPECTRUM_LOCAL_INPUT_WINDOW_V1"
TIME_KIND="ADC_ABSOLUTE_SAMPLE_INDEX_RELATIVE_TO_ARCHIVE_NOT_HOST_UTC"


def archive_input_window_evidence(samples, *, first: int, end: int,
                                  sample_rate_hz: float, native_audit: bool
                                  ) -> dict:
    """Explicitly bounded, nonpadded Float32 archive segment fingerprint."""
    if (type(first) is not int or type(end) is not int or
            type(native_audit) is not bool or
            first<0 or end<=first or
            not isinstance(sample_rate_hz,(float,int)) or
            isinstance(sample_rate_hz,bool) or
            not math.isfinite(sample_rate_hz) or sample_rate_hz<=0):
        raise ValueError("GetSignal source input: invalid archive window metadata")
    arr=np.asarray(samples)
    if arr.ndim!=1 or end>len(arr):
        raise ValueError("GetSignal source input: real BIN history not available; NO padding")
    exact=np.asarray(arr[first:end],dtype="<f4")
    if not bool(np.isfinite(exact).all()):
        raise ValueError("GetSignal source input: nonfinite source window")
    return {
        "schema":SCHEMA,
        "time_kind":TIME_KIND,
        "first_archive_sample_index":first,
        "last_archive_sample_exclusive":end,
        "source_sample_count":end-first,
        "sample_rate_hz":float(sample_rate_hz),
        "source_float32_le_sha256":hashlib.sha256(exact.tobytes()).hexdigest(),
        "no_zero_padding":True,
        "source_is_native_r6_sha_audited_export":native_audit,
        "native_calibration_must_not_be_applied_twice":True,
        "original_delphi_ring_position_verified":False,
        "original_same_run_bin_verified":False,
        "original_runtime_getsignal_fft_window_parity_verified":False,
    }


def compare_local_input_windows(a:dict,b:dict)->dict:
    """Strict proof ONLY of SAME input samples within our local processing."""
    keys=("schema","time_kind","first_archive_sample_index",
          "last_archive_sample_exclusive","source_sample_count",
          "sample_rate_hz","source_float32_le_sha256",
          "no_zero_padding","source_is_native_r6_sha_audited_export")
    if (not isinstance(a,dict) or not isinstance(b,dict) or
            any(k not in a or k not in b for k in keys) or
            a["schema"]!=SCHEMA or b["schema"]!=SCHEMA or
            a["time_kind"]!=TIME_KIND or b["time_kind"]!=TIME_KIND or
            a["no_zero_padding"] is not True or
            b["no_zero_padding"] is not True):
        raise ValueError("GetSignal source input: incompatible window provenance")
    return {
        "source":"LOCAL_ARCHIVE_WINDOW_SOURCE_BYTE_EQUIVALENCE_ONLY",
        "same_input_bytes_and_bounds":all(a[k]==b[k] for k in keys),
        "getsignal_processing_equals_getspectrum_processing":False,
        "original_delphi_runtime_parity_verified":False,
        "original_selected_record_and_ring_end_verified":False,
    }
