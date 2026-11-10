#!/usr/bin/env python3
"""Stage111Z31AM: original MVKView EnvelopeCode20/LOG0 full bitwise regression.

OFFLINE ONLY: accepts user-held original B ZIP, IDP and optional physical ADC1
BIN/older LOG. Never controls x32dbg, hardware, Windows GUI or the network.
Never exports original raw coefficients. Only the exact verified single window.
Requires installed numpy and project mvk_compatible.core modules.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mvk_compatible.core.envelope_idr_candidate import (
    EnvelopeProfile, process_original_envelope_candidate)
from mvk_compatible.core.fft_idr_candidate import (
    idr_power_spectrum, mean_center_float32)
from mvk_compatible.core.spectrum_display_source import source_derived_mode_display
from mvk_compatible.core.spectrum_metrics_idr_candidate import original_spectrum_summary

ORIGINAL_CAPTURE_SHA = "78e7c095d8b1a9d21a26bb9b21b6edaf826a8a9ba34e67af625e6717ff775292"
PRIVATE_IDP_SHA = "77e59f98febdd7df94e71cb538a2df69ea4de4624f15b088a81c86e61bb5a438"
PHYSICAL_ADC1_SHA = "b598d466f9f70f49e4a5f6a0f2a20d4870af43f9864f5e4c9f7cfd51c9d2fad1"
ORIGINAL_PRE_DC_SHA = "86856251ab33201aec2ccbf43f0e33ea0bf658cd3f1112183071d13b665949c5"
RAW_N, FFT_N, HALF_N = 262195, 131072, 65536
END_INDEX, OLDEST = 557107, 294912
PHYSICAL_FIRST, PHYSICAL_END = 1703230, 1965425


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_f32(raw: bytes, n: int, label: str) -> np.ndarray:
    if len(raw) != 4 * n:
        raise ValueError(f"{label}: {len(raw)} bytes, expected {4*n}")
    a = np.frombuffer(raw, dtype="<f4")
    if not bool(np.isfinite(a).all()):
        raise ValueError(f"{label}: NaN/Inf")
    return a


def compare(original: np.ndarray, reproduced: np.ndarray, label: str, rows: list) -> None:
    aa = np.asarray(original, dtype="<f4").tobytes()
    bb = np.asarray(reproduced, dtype="<f4").tobytes()
    if len(aa) != len(bb):
        raise ValueError(f"{label}: size mismatch")
    a = np.frombuffer(aa, dtype="<u4")
    b = np.frombuffer(bb, dtype="<u4")
    matches = int(np.count_nonzero(a == b))
    rows.append({"stage": label, "matching_float32": matches, "total_float32": len(a),
                 "original_sha256": sha(aa), "replayed_sha256": sha(bb),
                 "bitwise_pass": matches == len(a)})
    if matches != len(a):
        ix = int(np.flatnonzero(a != b)[0])
        raise ValueError(f"{label}: bitwise mismatch at Float32 index {ix}; {matches}/{len(a)} equal")


def verify(capture: Path, idp: Path, physical: Path | None, prior_log: Path | None) -> dict:
    if capture.is_symlink() or not capture.is_file() or capture.stat().st_size > 25_000_000:
        raise ValueError("Expected small regular original capture ZIP")
    if idp.is_symlink() or not idp.is_file() or idp.stat().st_size > 80_000_000:
        raise ValueError("Expected local private IDP file")
    if sha(capture.read_bytes()) != ORIGINAL_CAPTURE_SHA:
        raise ValueError("Capture package fingerprint differs from original Z31AL")
    if sha(idp.read_bytes()) != PRIVATE_IDP_SHA:
        raise ValueError("Private original IDP fingerprint mismatch")
    required = ["input_normalized_pre_dc.bin", "input_after_dc.bin", "before_fft.bin",
                "power_before_mode.bin", "power_after_mode.bin", "display_y.bin",
                "summary_triplet.bin", "ring_head.bin", "frange.bin",
                "params_pre_dc.bin", "params_pre_fft.bin", "params_final.bin"]
    with zipfile.ZipFile(capture) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or len(names) > 32 or any("/" in v or "\\" in v for v in names):
            raise ValueError("Duplicate/unsafe/unexpected capture ZIP paths")
        buffers = {v: z.read(v) for v in required}
    raw = load_f32(buffers["input_normalized_pre_dc.bin"], RAW_N, "preDC")
    dc = load_f32(buffers["input_after_dc.bin"], RAW_N, "afterDC")
    fir = load_f32(buffers["before_fft.bin"], FFT_N, "postFIR")
    power_before = load_f32(buffers["power_before_mode.bin"], HALF_N, "FFT Power")
    power_after = load_f32(buffers["power_after_mode.bin"], HALF_N, "Power mode0")
    y = load_f32(buffers["display_y.bin"], HALF_N, "LOG Y")
    summary = load_f32(buffers["summary_triplet.bin"], 3, "Summary")
    ring = load_f32(buffers["ring_head.bin"], RAW_N, "Original raw ring")
    if buffers["frange.bin"].hex() != "5348ff43":
        raise ValueError("FRange != 0x43FF4853")
    frange = float(np.frombuffer(buffers["frange.bin"], dtype="<f4")[0])
    for name, length, fs, half in (
        ("params_pre_dc.bin", RAW_N, 65536, 131072),
        ("params_pre_fft.bin", FFT_N, 32768, HALF_N),
        ("params_final.bin", FFT_N, 32768, HALF_N),
    ):
        params = buffers[name]
        if len(params) != 60:
            raise ValueError(f"{name}: wrong byte length")
        values = [struct.unpack_from("<I", params, x)[0] for x in (4, 8, 24, 32, 40, 44)]
        if values != [length, 20, 0, END_INDEX, half, fs]:
            raise ValueError(f"{name}: runtime params mismatch: {values}")
    if END_INDEX - RAW_N != OLDEST:
        raise ValueError("Original source window inconsistent")
    rows: list[dict] = []
    compare(raw, np.asarray(ring / np.float32(frange), dtype=np.float32),
            "ring_to_normalized_pre_dc", rows)
    if sha(raw.tobytes()) != ORIGINAL_PRE_DC_SHA:
        raise ValueError("preDC not identical to previously accepted Stage111Z31AH")
    if physical is not None:
        if physical.is_symlink() or not physical.is_file() or sha(physical.read_bytes()) != PHYSICAL_ADC1_SHA:
            raise ValueError("Unexpected physical ADC1 BIN")
        all_adc = load_f32(physical.read_bytes(), 1965824, "physical ADC1 BIN")
        compare(raw, np.asarray(all_adc[PHYSICAL_FIRST:PHYSICAL_END] / np.float32(frange),
                                dtype=np.float32), "physical_ADC1_to_pre_dc", rows)
    if prior_log is not None:
        if prior_log.is_symlink() or not prior_log.is_file():
            raise ValueError("Prior LOG archive absent")
        with zipfile.ZipFile(prior_log) as z:
            older = z.read("input_normalized_pre_dc.bin")
        if raw[51:].tobytes() != older:
            raise ValueError("Code20 FIR lead-in/tail differs from original plain LOG")
        rows.append({"stage": "same_end_LOG_overlap", "matching_float32": 262144,
                     "total_float32": 262144, "bitwise_pass": True})
    centered, running_dc = mean_center_float32(raw)
    compare(dc, centered, "float32_running_mean_DC", rows)
    profile = EnvelopeProfile.from_original_local_idp(idp)
    env = process_original_envelope_candidate(raw, 65536, 20, profile, f_range=1.0)
    compare(fir, env["chronological"], "51_tap_IQ_FIR_decim2", rows)
    predicted_power, secondary_dc = idr_power_spectrum(fir, "idr_float32", remove_dc=False)
    if secondary_dc != 0.0:
        raise ValueError("Extra DC removed after FIR, which original does not do")
    compare(power_before, predicted_power, "Hann_RMS_IDR_FFT_Power", rows)
    predicted_power = predicted_power.copy()
    predicted_power[:2] = np.float32(0.)
    compare(power_after, predicted_power, "mode0_first_two_bin_mask", rows)
    predicted_y = source_derived_mode_display(predicted_power, n_fft=FFT_N, mode=0, f_range=frange)
    compare(y, predicted_y, "LOG_Y_float32", rows)
    metrics = original_spectrum_summary(predicted_power, n_fft=FFT_N, fs_out=32768.,
                                         f_range=frange, spectrum_mode=0)
    predicted_summary = np.asarray([metrics["output_mean"], metrics["output_peak_x_bin"],
                                    metrics["output_peak_y"]], dtype="<f4")
    compare(summary, predicted_summary, "OutputMean_PeakX_PeakY", rows)
    peak_bin = int(np.argmax(y))
    return {"status": "FULL_NUMERICAL_CODE20_LOG0_SINGLE_WINDOW_BITWISE_PASS",
            "scope": "ONE ORIGINAL ADC1 WINDOW only; all other modes/UI unverified",
            "capture_sha256": ORIGINAL_CAPTURE_SHA, "private_idp_sha256": PRIVATE_IDP_SHA,
            "raw_n": RAW_N, "fft_n": FFT_N, "half_bins": HALF_N, "df_hz": .25,
            "dc_running_mean_float32": float(running_dc),
            "summary_float32": summary.tolist(), "max_y_bin": peak_bin,
            "max_y_frequency_hz": peak_bin * .25, "max_y_db": float(y[peak_bin]),
            "weighted_peak_frequency_hz": float(summary[1]) * .25,
            "comparison": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-zip", type=Path, required=True)
    parser.add_argument("--private-idp", type=Path, required=True)
    parser.add_argument("--adc1-bin", type=Path)
    parser.add_argument("--previous-log-capture", type=Path)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.capture_zip, args.private_idp, args.adc1_bin,
                        args.previous_log_capture)
    except (OSError, ValueError, zipfile.BadZipFile, KeyError, struct.error) as exc:
        print(json.dumps({"status": "REJECT", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    report = json.dumps(result, ensure_ascii=False, indent=2)
    print(report)
    if args.report_json:
        if args.report_json.exists():
            print("REFUSE_OVERWRITE_REPORT", file=sys.stderr)
            return 2
        args.report_json.write_text(report + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
