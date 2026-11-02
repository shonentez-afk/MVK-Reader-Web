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
