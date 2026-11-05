"""Stage111Z31K: reproducible spectrum *calculation* acceptance matrix.

Use ONLY locally selected operator Power/Y manifests. No private files,
FFT input, x32dbg captures or credentials are ever exported or uploaded.
The original reference loader checks SHA256, all N/2 Float32 output
words, and 3 summary words when the source manifest contains them.

Crucial boundary: these are POST-FFT Power -> Y and summary checks,
NOT reconstruction of the original ADC -> Hann -> radix-2 FFT
for every sample/window/N/Fs, not provenance of one process/frame.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .original_spectrum_x32dbg_reference import (
    load_original_spectrum_reference,
)

SOURCE = "APP_DERIVED_SPECTRUM_MATH_ACCEPTANCE_STAGE111Z31K"
MODE_NAMES = (
    "Tag0_logarithmic",
    "Tag1_linear_acceleration",
    "Tag2_linear_velocity_integrated",
    "Tag3_linear_displacement_double_integrated",
)
_MAX_MANIFESTS = 16


def spectrum_calculation_acceptance(manifests=()):
    """Read-only fail-closed acceptance over user-local Power/Y references.

    Exact Float32 parity is asserted by load_original_spectrum_reference.
    Original *runtime provenance* is still operator-reported, not
    cryptographically authenticated by the tool. The output contains NO
    source paths, raw values, buffer payloads, or original filenames.
    """
    if not isinstance(manifests, (tuple,list)):
        raise ValueError("Manifests must be an explicit bounded list/tuple")
    if len(manifests) > _MAX_MANIFESTS:
        raise ValueError("Too many local reference manifests")
    seen = set()
    rows = []
    for manifest in manifests:
        if not isinstance(manifest,(str,Path)):
            raise ValueError("Each local reference must be a path")
        selected = Path(manifest)
        if selected.is_symlink():
            raise ValueError("Original reference manifest cannot be a symlink")
        canonical = selected.resolve()
        if canonical in seen:
            raise ValueError("Duplicate reference: one runtime capture cannot count twice")
        seen.add(canonical)
        ref = load_original_spectrum_reference(selected)
        rows.append({
            "spectrum_mode":int(ref.mode),
            "mode_name":MODE_NAMES[ref.mode],
            "n_fft":int(ref.n_fft),
            "sample_rate_hz":int(ref.fs_hz),
            "original_f_range_single_used":float(ref.f_range),
            "captured_power_float32_bins":int(ref.power.size),
            "source_model_display_y_bits_equal":True,
            "source_model_display_y_equal_bins":int(ref.display_y.size),
            "source_model_display_y_max_ulp":0,
            "operator_supplied_summary_hex_matched":
                ref.original_summary_words_equal is True,
            "operator_supplied_summary_hex_missing":
                ref.original_summary_words_equal is None,
            "original_runtime_same_frame_independently_authenticated":False,
            "native_pre_fft_signal_window_compared":False,
            "native_pre_fft_hann_and_fft_power_recomputed_bitwise":False,
        })
    modes = sorted(set(row["spectrum_mode"] for row in rows))
    summaries = [
        row for row in rows if row["operator_supplied_summary_hex_matched"]
    ]
    complete = modes == [0,1,2,3]
    complete_summaries = complete and all(
        any(row["spectrum_mode"] == mode and
            row["operator_supplied_summary_hex_matched"]
            for row in rows) for mode in range(4))
    return {
        "source":SOURCE,
        "mode_names":list(MODE_NAMES),
        "local_manifest_count":len(rows),
        "replayed_modes":modes,
        "missing_modes":[m for m in range(4) if m not in modes],
        "verified_post_fft_y_float32_bins":sum(
            row["source_model_display_y_equal_bins"] for row in rows),
        "operator_summary_three_words_verified_captures":len(summaries),
        "source_model_post_fft_all_four_modes_replayed_from_local_inputs":
            complete,
        "source_model_three_summary_words_each_mode_replayed":
            complete_summaries,
        "captures":rows,
        "calculation_stages":{
            "adc_ring_window_identity":{
                "source_reconstructed":True,
                "original_same_session_bitwise_verified":False},
            "float32_running_mean":{
                "source_reconstructed":True,
                "original_all_inputs_bitwise_verified":False},
            "hann_rms_262144_table":{
                "source_reconstructed":True,
                "original_entries_bitwise_verified":4,
                "original_all_entries_bitwise_verified":False},
            "float32_radix2_fft_and_power":{
                "source_reconstructed":True,
                "original_full_power_from_same_raw_window_bitwise_verified":False},
            "post_mode_power_integration":{
                "source_reconstructed":True,
                "original_selected_mode_captures_previously_compared":True,
                "original_all_inputs_bitwise_verified":False},
            "post_fft_power_to_four_display_modes":{
                "source_reconstructed":True,
                "local_manifest_replay_modes":modes,
                "original_any_input_bitwise_verified":False},
            "summary_mean_peak_x_peak_y":{
                "source_reconstructed":True,
                "local_manifest_summary_hex_modes":sorted(set(
                    row["spectrum_mode"] for row in summaries)),
                "original_any_input_bitwise_verified":False},
            "envelope_fir_iq":{
                "source_reconstructed":True,
                "original_same_window_runtime_bitwise_verified":False},
            "gain_f_range_adc_units":{
                "source_reconstructed":True,
                "original_all_inputs_bitwise_verified":False},
            "tqgrapher_canvas_cursor":{
                "source_reconstructed":True,
                "original_pixel_runtime_verified":False},
        },
        "original_manifest_provenance_independently_authenticated":False,
        "original_universal_fft_and_spectrum_calculation_parity_verified":False,
        "full_mvkview_spectrum_recovered":False,
        "next_evidence_required":[
            "Same-signal original pre-FFT Float32 ring snapshot with N/Fs/FRange/window metadata",
            "Original Win32 post-FFT power from that exact same window for full-bin comparison",
            "Original Hann/twiddle x87 stores outside four checked Hann entries",
            "Original envelope original process pre/post-IQ buffers for the same time window",
            "Original calibration and source ADC sensor-unit provenance",
            "Original TQGrapher runtime PaintBox/GDI image and cursor comparison",
        ],
        "privacy":{
            "reads_only_explicit_local_files":True,
            "source_filenames_or_paths_in_output":False,
            "raw_samples_in_output":False,
            "network_or_instrument_access":False,
            "writes_files":False,
        },
    }


def main(argv=None):
    parser=argparse.ArgumentParser(
        description="Local spectrum calculations audit. No raw samples exported.")
    parser.add_argument("--manifest",action="append",default=[],
                        help="Explicit local x32dbg Power/Y reference.json; repeat 1-16 times")
    parser.add_argument("--require-four-modes",action="store_true",
                        help="Exit 2 if supplied local captures do not cover all 4 modes with summary HEX")
    args=parser.parse_args(argv)
    try:
        report=spectrum_calculation_acceptance(args.manifest)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        parser.exit(2,"Local spectrum audit rejected: "+str(exc)+"\n")
    print(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2))
    if args.require_four_modes and not report[
        "source_model_three_summary_words_each_mode_replayed"
    ]:
        return 2
    return 0


if __name__=="__main__":
    raise SystemExit(main())
