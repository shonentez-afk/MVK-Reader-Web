"""Stage111Z.22: independent DOUBLE NumPy reference for original captured FFT.

Privacy-preserving offline instrument QA. Two user-local x32dbg memory
snapshots are never included in repository or CI:
  before_fft(1).bin: 262144 little-endian Float32 input samples.
  after_power(1).bin: 131072 little-endian Float32 original power bins.

Original IDR 008C1064..008C10C9 constructs 262144-point periodic window:
 (1-cos(2*pi*j/262144))/sqrt(1.5).
Original 007D205A..2080 applies sampled window; GetSpectrum calls forward
FFT 007CC3F8 and computes power.

This is NOT the IDR Float32 radix-2 FFT implementation. It is an
independent float64/NumPy BASELINE. Numerical proximity is not bitwise
parity and the original Windows x87 rounding sequence remains separate.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np

REFERENCE_SOURCE="APP_DERIVED_INDEPENDENT_NUMPY_PERIODIC_HANN_FFT_POWER_QA"
_ORIGINAL_WAVEFORM_BYTES_MAX=262_144*4
_MAX_ORIGINAL_POWER_BYTES=(_ORIGINAL_WAVEFORM_BYTES_MAX//2)


def _read_local_single_snapshot(path:str | Path, *,max_bytes:int)->tuple[np.ndarray,str]:
    selected=Path(path)
    if selected.is_symlink() or not selected.is_file():
        raise ValueError("Нужен обычный локальный файл, не symlink")
    size=selected.stat().st_size
    if size==0 or size>max_bytes or size%4:
        raise ValueError("Недопустимый размер локального Float32 снимка")
    payload=selected.read_bytes()
    if len(payload)!=size:
        raise ValueError("Локальный снимок изменился при чтении")
    values=np.frombuffer(payload,dtype="<f4")
    if not np.isfinite(values).all():
        raise ValueError("Локальный снимок содержит NaN/Inf")
    return values,hashlib.sha256(payload).hexdigest()


def independent_numpy_hann_power(signal:np.ndarray)->np.ndarray:
    """Periodic RMS-normalized Hann + float64 FFT + float32 power store.

    Source's period and normalization match the original IDR algorithm,
    but NumPy trig and FFT are DOUBLE precision, *not* its x87/Single stores.
    """
    arr=np.asarray(signal,dtype=np.float32)
    n=arr.size
    if (arr.ndim!=1 or n<1024 or n>262_144 or n & (n-1) or
            not bool(np.isfinite(arr).all())):
        raise ValueError("Для независимой сверки нужен конечный NFFT=2^k <=262144")
    index=np.arange(n,dtype=np.float64)
    periodic_hann=(
        1.-np.cos((2.*math.pi*index)/n))/math.sqrt(1.5)
    weighted=arr.astype(np.float64)*periodic_hann
    fft=np.fft.fft(weighted)[:n//2]
    return np.asarray(fft.real*fft.real+fft.imag*fft.imag,dtype="<f4")


def compare_original_snapshot_pair(
    time_file:str|Path,power_file:str|Path,*,sample_rate_hz:int|None=None
)->dict:
    """Read ONLY local copies, report hashed/aggregate metrics; never upload."""
    before,before_hash=_read_local_single_snapshot(
        time_file,max_bytes=_ORIGINAL_WAVEFORM_BYTES_MAX)
    actual,actual_hash=_read_local_single_snapshot(
        power_file,max_bytes=_MAX_ORIGINAL_POWER_BYTES)
    n=len(before)
    if n<1024 or n & (n-1) or n>262_144 or len(actual)!=n//2:
        raise ValueError("Неверная пара: original power должен быть NFFT/2")
    if not bool(np.any(before)) or not bool(np.any(actual)):
        raise ValueError(
            "Оригинальные snapshots содержат пустой/нулевой буфер. "
            "Не считать этот захват валидной FFT-сверкой.")
    if np.any(actual<0):
        raise ValueError("Original power не может быть отрицательной")
    if sample_rate_hz is not None and (
        type(sample_rate_hz) is not int or
        not 1<=sample_rate_hz<=1_000_000
    ):
        raise ValueError("Частота отсчётов должна быть положительным целым Гц")
    predicted=independent_numpy_hann_power(before)
    ref=np.asarray(actual,dtype=np.float64)
    trial=np.asarray(predicted,dtype=np.float64)
    difference=np.abs(trial-ref)
    relative=difference/np.maximum(1e-9,np.abs(ref))
    reference_peak=int(np.argmax(actual))
    expected_peak=int(np.argmax(predicted))
    power_sum=float(np.sum(ref))
    return {
        "source":REFERENCE_SOURCE,
        "original_source":"ORIGINAL_USER_LOCAL_X32DBG_MEMORY_SNAPSHOT",
        "n_fft":n,
        "power_bins":len(actual),
        "before_fft_sha256":before_hash,
        "after_power_sha256":actual_hash,
        "original_power_peak_bin":reference_peak,
        "independent_power_peak_bin":expected_peak,
        "peak_bin_equal":reference_peak==expected_peak,
        "original_power_peak_value":float(actual[reference_peak]),
        "independent_power_peak_value":float(predicted[expected_peak]),
        "sample_rate_hz":sample_rate_hz,
        "peak_frequency_hz":(
            None if sample_rate_hz is None else
            reference_peak*sample_rate_hz/n
        ),
        "float32_bit_exact_bins":int(np.count_nonzero(
            actual.view("<u4")==predicted.view("<u4"))),
        "within_0_1_percent_bins":int(np.count_nonzero(relative<=.001)),
        "within_1_percent_bins":int(np.count_nonzero(relative<=.01)),
        "relative_error_median":float(np.median(relative)),
        "relative_error_p99":float(np.quantile(relative,.99)),
        "max_absolute_power_error":float(np.max(difference)),
        "integrated_power_relative_error":float(
            np.abs(np.sum(trial)-power_sum)/power_sum),
        "original_float32_radix2_bit_parity_verified":False,
        "original_bin_to_storage_calibration_verified":False,
        "original_runtime_gdi_plot_pixel_parity_verified":False,
        "privacy":{
            "raw_input_contents_in_report":False,
            "source_file_paths_in_report":False,
            "binary_captures_ever_uploaded_by_tool":False,
        },
    }



def compare_source_idr_fft_capture_pair(
    pre_fft_file: str | Path,
    reference_fft_power_file: str | Path,
    *, pre_fft_is_after_original_dc_and_filters: bool,
    reference_power_is_before_low_bin_and_mode_changes: bool,
    sample_rate_hz: int | None = None,
) -> dict:
    """Stage111Z31K: source Float32 radix2 candidate vs user-local FFT power.

    Original GetSpectrum first loads ring data, subtracts DC and can apply
    envelope filtering. The original trace at 007D1FE8 then applies Hann
    and the actual FFT. Caller must explicitly certify BOTH snapshot
    stage identities; never silently subtract DC twice or compare
    post-integration Power to raw FFT Power.

    Returns only aggregate discrepancies. A synthetic candidate-created
    target can pass bitwise; it is NOT evidence of original Win32 parity.
    """
    from .fft_idr_candidate import idr_power_spectrum

    if (type(pre_fft_is_after_original_dc_and_filters) is not bool
            or type(reference_power_is_before_low_bin_and_mode_changes)
            is not bool):
        raise ValueError("Explicit original snapshot stage flags required")
    if not pre_fft_is_after_original_dc_and_filters:
        raise ValueError("Pre-FFT buffer stage must be operator-confirmed")
    if not reference_power_is_before_low_bin_and_mode_changes:
        raise ValueError("Power must be captured before GetSpectrum mode changes")
    if sample_rate_hz is not None and (
            type(sample_rate_hz) is not int
            or not 1<=sample_rate_hz<=1_000_000):
        raise ValueError("Sample rate must be a valid source integer")
    source,source_sha=_read_local_single_snapshot(
        pre_fft_file,max_bytes=_ORIGINAL_WAVEFORM_BYTES_MAX)
    target,target_sha=_read_local_single_snapshot(
        reference_fft_power_file,max_bytes=_MAX_ORIGINAL_POWER_BYTES)
    n=int(source.size)
    if (n<1024 or n>262_144 or n & (n-1) or len(target)!=n//2
            or not np.any(source) or not np.any(target)
            or np.any(target<0)):
        raise ValueError("Source FFT comparison needs one valid N/2 power pair")
    source_bits=source.view("<u4").copy()
    target_bits=target.view("<u4").copy()
    candidate,_=idr_power_spectrum(
        source,backend="idr_float32",remove_dc=False)
    double_baseline=independent_numpy_hann_power(source)
    if not np.array_equal(source.view("<u4"),source_bits):
        raise ValueError("Source snapshot was unexpectedly modified")
    if not np.array_equal(target.view("<u4"),target_bits):
        raise ValueError("Reference power snapshot was unexpectedly modified")
    good=int(np.count_nonzero(
        np.asarray(candidate,dtype="<f4").view("<u4")==target_bits))
    benchmark=int(np.count_nonzero(
        np.asarray(double_baseline,dtype="<f4").view("<u4")==target_bits))
    actual=target.astype(np.float64)
    diff=np.abs(candidate.astype(np.float64)-actual)
    relative=diff/np.maximum(np.abs(actual),1e-9)
    total=float(np.sum(actual,dtype=np.float64))
    return {
        "source":"LOCAL_OPERATOR_FFT_INPUT_TO_POWER_STAGE111Z31K",
        "captured_n_fft":n,
        "captured_power_float32_bins":n//2,
        "input_float32_sha256":source_sha,
        "reference_power_float32_sha256":target_sha,
        "idr_float32_fft_bitwise_equal_bins":good,
        "idr_float32_fft_bitwise_equal_fraction":good/len(target),
        "independent_double_numpy_bitwise_equal_bins":benchmark,
        "source_candidate_peak_bin":int(np.argmax(candidate)),
        "reference_power_peak_bin":int(np.argmax(target)),
        "same_peak_bin":int(np.argmax(candidate))==int(np.argmax(target)),
        "source_candidate_p99_relative_error":float(np.quantile(relative,.99)),
        "source_candidate_max_absolute_power_error":float(np.max(diff)),
        "source_candidate_integrated_power_relative_error":
            abs(float(np.sum(candidate,dtype=np.float64))-total)/
                max(total,1e-9),
        "sample_rate_hz":sample_rate_hz,
        "same_source_window_authenticated_by_original_runtime":False,
        "input_stage_declared_by_operator_not_proven_by_tool":True,
        "power_stage_declared_by_operator_not_proven_by_tool":True,
        "original_all_fft_input_bitwise_parity_verified":False,
        "private_file_paths_in_result":False,
        "raw_samples_in_result":False,
        "no_dc_removed_again":True,
        "network_or_instrument_access":False,
    }
