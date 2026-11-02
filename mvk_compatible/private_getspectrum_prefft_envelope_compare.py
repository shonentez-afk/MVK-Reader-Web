"""Stage111Z29C2: PRIVATE read-only original GetSpectrum pre-Hann FIR input comparator.

Reuses ALREADY CAPTURED original x32dbg before_fft(1).bin if its
GetSpectrum EnvelopeCode, ADC, original source window, N/Fs and FRange can
actually be established from that same runtime. Original x32dbg
007D153D saves the buffer BEFORE Hann/FFT, AFTER optional mean/FIR;
it is NOT GetSignal's reversed return buffer. New recording is not
automatically needed, but the historical N=262144 snapshot alone has
UNKNOWN EnvelopeCode and CANNOT substantiate original FIR parity.

Source Native R6 ZIP and exact original IDP are PRIVATE local inputs. Neither
original file bytes, proprietary coefficients, file paths, nor individual
sample values are sent anywhere or printed. The tool NEVER opens a socket.
No original-runtime identity/capture source is silently promoted to verified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from .core.offline_export import OfflineSession
from .core.envelope_idr_candidate import EnvelopeProfile,process_original_envelope_candidate
from .core.envelope_spectrum_idr_candidate import required_original_history
from .core.storage_f_range_idr_candidate import (
    DOMAIN_ORIGINAL_STORAGE,DOMAIN_CALIBRATED_BIN,prepare_original_fft_input)
from .core.getsignal_input_evidence import archive_input_window_evidence

SCHEMA="MVK_ORIGINAL_GETSPECTRUM_PREFFT_ENVELOPE_LOCAL_FLOAT32_PAIR_V1"


def _read_private_prefft(path, expected_len:int)->np.ndarray:
    p=Path(path)
    if (p.is_symlink() or not p.is_file() or p.suffix.lower()!=".bin"
            or p.stat().st_size!=4*expected_len):
        raise ValueError("Original pre-FFT reference missing or wrong Float32 length")
    arr=np.fromfile(p,dtype="<f4")
    if len(arr)!=expected_len or not bool(np.isfinite(arr).all()):
        raise ValueError("Original pre-FFT reference has nonfinite or incomplete data")
    if not np.count_nonzero(arr):
        raise ValueError("Zero-only placeholder cannot attest original envelope")
    return arr


def _ordered_f32_words(w):
    x=w.astype(np.uint64)
    return np.where((x & 0x80000000)!=0,
                    np.uint64(0x80000000)-(x & 0x7FFFFFFF),
                    x | np.uint64(0x80000000)).astype(np.int64)


def compare_original_prefft_envelope(
    source_native_zip, original_idp, original_prefft_bin, *,
    channel:int, first_sample:int, n_fft:int,
    envelope_code:int, f_range:float, input_domain:str
)->dict:
    """Compare exact BEFORE-HANN array; same-run original provenance is OPEN.

    All runtime metadata must be supplied explicitly, never inferred from
    the earlier FFT power golden or blindly from a PC clock.
    """
    if (type(channel) is not int or not 1<=channel<=8 or
        type(first_sample) is not int or first_sample<0 or
        type(envelope_code) is not int or not 1<=envelope_code<=31 or
        input_domain not in (DOMAIN_CALIBRATED_BIN,DOMAIN_ORIGINAL_STORAGE)):
        raise ValueError("Invalid original pre-FFT source metadata")
    # validates FFT N, original FIR inverse and supported ADC sample rate
    profile=EnvelopeProfile.from_original_local_idp(original_idp)
    session=OfflineSession.open(source_native_zip)
    samples,fs,audit,_=session.samples(channel)
    if not float(fs).is_integer():
        raise ValueError("Original GetSpectrum FIR requires integer sample rate")
    plan=required_original_history(n_fft,int(fs),envelope_code)
    end=first_sample+plan["input_samples"]
    if end>len(samples):
        raise ValueError("Audited source has insufficient real FIR history")
    provenance=archive_input_window_evidence(
        samples,first=first_sample,end=end,sample_rate_hz=fs,
        native_audit=True,channel=channel,
        source_raw_sha256=audit.get("source_raw_sha256"))
    prepared=prepare_original_fft_input(
        samples[first_sample:end],f_range=f_range,input_domain=input_domain)
    original=_read_private_prefft(original_prefft_bin,n_fft)
    derived=process_original_envelope_candidate(
        prepared["samples_before_dc_removal"],int(fs),
        envelope_code,profile,f_range=1.)["chronological"]
    if len(derived)!=n_fft or not bool(np.isfinite(derived).all()):
        raise ValueError("Source envelope-to-FFT length or finite state mismatch")
    ref_bits=original.view("<u4")
    actual_bits=np.asarray(derived,dtype="<f4").view("<u4")
    exact=ref_bits==actual_bits
    d=np.abs(_ordered_f32_words(ref_bits)-_ordered_f32_words(actual_bits))
    mismatches=np.flatnonzero(~exact)
    return {
        "schema":SCHEMA,
        "source":"LOCAL_OPERATOR_PREFFT_FIR_CANDIDATE_VS_AUDITED_NATIVE_R6",
        "input_domain":input_domain,
        "original_source_buffer_provenance_verified":False,
        "channel":channel,
        "envelope_code":envelope_code,
        "n_fft":n_fft,
        "input_history_samples":int(plan["input_samples"]),
        "first_archive_sample_index":first_sample,
        "source_float32_le_sha256":provenance["source_float32_le_sha256"],
        "normalized_pre_fir_float32_sha256":hashlib.sha256(
            np.asarray(prepared["samples_before_dc_removal"],dtype="<f4").tobytes()).hexdigest(),
        "original_pre_fft_float32_sha256":hashlib.sha256(original.tobytes()).hexdigest(),
        "candidate_pre_fft_float32_sha256":hashlib.sha256(derived.tobytes()).hexdigest(),
        "original_pre_fft_full_array_bitwise_equal":bool(np.all(exact)),
        "float32_exact_words":int(exact.sum()),
        "float32_total_words":n_fft,
        "float32_first_mismatch_index":int(mismatches[0]) if len(mismatches) else None,
        "float32_max_ulp":int(d.max()),
        "float32_median_ulp":float(np.median(d)),
        "original_historical_before_fft_envelope_code_verified":False,
        "original_same_run_device_and_window_authenticated":False,
        "original_runtime_f_range_and_storage_domain_verified":False,
        "original_x87_precision_parity_verified":False,
        "original_four_spectrum_modes_numeric_parity_verified":False,
        "private_original_paths_coefficients_samples_in_report":False,
    }


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(
        description="PRIVATE offline original pre-FFT envelope source comparator")
    parser.add_argument("--source-native-zip",required=True)
    parser.add_argument("--local-original-idp",required=True)
    parser.add_argument("--original-before-fft-bin",required=True)
    parser.add_argument("--channel",type=int,required=True)
    parser.add_argument("--first-sample",type=int,required=True)
    parser.add_argument("--n-fft",type=int,required=True)
    parser.add_argument("--envelope-code",type=int,required=True)
    parser.add_argument("--f-range",type=float,required=True)
    parser.add_argument("--input-domain",required=True,
                        choices=(DOMAIN_CALIBRATED_BIN,DOMAIN_ORIGINAL_STORAGE))
    a=parser.parse_args(argv)
    try:
        outcome=compare_original_prefft_envelope(
            a.source_native_zip,a.local_original_idp,a.original_before_fft_bin,
            channel=a.channel,first_sample=a.first_sample,n_fft=a.n_fft,
            envelope_code=a.envelope_code,f_range=a.f_range,
            input_domain=a.input_domain)
    except (TypeError,ValueError,OSError,OverflowError,RuntimeError):
        parser.exit(2,"Private original pre-FFT pairing invalid; details withheld\n")
    print(json.dumps(outcome,ensure_ascii=False,indent=2,sort_keys=True))
    return 0 if outcome["original_pre_fft_full_array_bitwise_equal"] else 1


if __name__=="__main__":
    raise SystemExit(main())
